"""Day 13: Agent loop / ReAct-style tool loop.

Day 12：
    LLM 一次性生成 tool_calls。

Day 13：
    LLM 每一轮看当前状态和工具结果，决定下一步：
    - 继续调用一个工具
    - 或者给出 final answer

这就是 Agent loop 的核心：

    decide -> execute tool -> observe -> decide -> execute tool -> observe -> final

今天仍然支持 DeepSeek 环境变量：

    DEEPSEEK_API_KEY
    DEEPSEEK_BASE_URL
    DEEPSEEK_MODEL

但测试全部用 FakeClient，不真的请求模型。
没有环境变量时，本地 demo 会用 rule fallback loop，方便你不折腾 API 也能跑通。

重点：
    LLM 不直接替代工具，也不直接替代业务代码。
    它负责“下一步该干什么”。
    工具执行、工具名校验、状态流转仍然由代码控制。

这才像个正常 Agent。不是“模型输出一大段自信废话，然后大家一起假装它能交付”。
"""

from __future__ import annotations

import json
import re
from operator import add
from typing import Annotated, Any, Literal, Protocol

from typing_extensions import TypedDict

from langgraph.graph import END, START, StateGraph

from audit_pipeline_poc.llm_planner_graph import DeepSeekChatClient
from audit_pipeline_poc.tool_calling_graph import (
    TOOL_REGISTRY,
    AuditState as ToolAuditState,
    ToolName,
    ToolResult,
    delivery,
    error_report,
    initial_state as base_initial_state,
    intake,
    review,
    route_by_audit_status,
)

AuditStatus = Literal["passed", "need_review", "failed"]
AgentActionType = Literal["tool", "final"]
PlannerMode = Literal["llm", "rule_fallback", "skip_due_to_input_error"]


class ChatClient(Protocol):
    def complete(self, messages: list[dict[str, str]]) -> str:
        """返回模型文本。"""


class AgentAction(TypedDict, total=False):
    """LLM 每一轮输出的动作。

    两种合法格式：

    调工具：
        {
          "action": "tool",
          "tool_name": "calculate_profit_margin",
          "args": {"revenue": 1000, "net_profit": 120},
          "reason": "Need margin first"
        }

    结束：
        {
          "action": "final",
          "audit_status": "passed",
          "final_answer": "...",
          "reason": "All required evidence collected"
        }
    """

    action: AgentActionType
    tool_name: ToolName
    args: dict[str, Any]
    audit_status: AuditStatus
    final_answer: str
    reason: str


class AgentStep(TypedDict):
    """记录 Agent 每轮决定。"""

    step_index: int
    action: AgentAction
    planner_mode: PlannerMode


class AuditState(ToolAuditState, total=False):
    """Day 13 的 State。"""

    current_action: AgentAction
    agent_steps: Annotated[list[AgentStep], add]
    llm_prompts: Annotated[list[str], add]
    llm_responses: Annotated[list[str], add]
    planner_mode: PlannerMode
    final_answer: str
    max_agent_steps: int


def _extract_json_object(text: str) -> dict[str, Any]:
    """从模型输出中解析 JSON 对象。"""

    stripped = text.strip()
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", stripped, flags=re.DOTALL)
    if fence_match:
        stripped = fence_match.group(1)
    return json.loads(stripped)


def parse_agent_action(text: str) -> AgentAction:
    """解析并校验 Agent action。"""

    data = _extract_json_object(text)
    action = data.get("action")

    if action == "tool":
        tool_name = data.get("tool_name")
        args = data.get("args", {})
        if tool_name not in TOOL_REGISTRY:
            raise ValueError(f"Unknown tool name from LLM: {tool_name!r}")
        if not isinstance(args, dict):
            raise ValueError("tool args must be an object")
        return {
            "action": "tool",
            "tool_name": tool_name,
            "args": args,
            "reason": str(data.get("reason", "")),
        }  # type: ignore[typeddict-item]

    if action == "final":
        audit_status = data.get("audit_status")
        if audit_status not in {"passed", "need_review", "failed"}:
            raise ValueError(f"Invalid final audit_status: {audit_status!r}")
        return {
            "action": "final",
            "audit_status": audit_status,
            "final_answer": str(data.get("final_answer", "")),
            "reason": str(data.get("reason", "")),
        }  # type: ignore[typeddict-item]

    raise ValueError("Agent action must be 'tool' or 'final'")


def _latest_tool_result(state: AuditState, name: ToolName) -> ToolResult | None:
    """取某个工具的最后一次结果。"""

    for result in reversed(state.get("tool_results", [])):
        if result["name"] == name:
            return result
    return None


def _any_failed_tool_result(state: AuditState) -> ToolResult | None:
    for result in state.get("tool_results", []):
        if not result["ok"]:
            return result
    return None


def build_agent_messages(state: AuditState) -> list[dict[str, str]]:
    """构造每轮 Agent 决策提示词。"""

    payload = {
        "task": "You are controlling a financial audit tool loop. Decide the next action.",
        "company": state.get("company"),
        "normalized_fields": state.get("normalized_fields", {}),
        "previous_tool_results": state.get("tool_results", []),
        "available_tools": [
            {
                "name": "calculate_profit_margin",
                "description": "Calculate profit margin from revenue and net_profit.",
                "args_schema": {"revenue": "float", "net_profit": "float"},
            },
            {
                "name": "classify_profit_margin",
                "description": "Classify risk from profit_margin.",
                "args_schema": {"profit_margin": "float"},
            },
            {
                "name": "build_audit_recommendation",
                "description": "Build final recommendation from company, profit_margin, and risk_level.",
                "args_schema": {"company": "str", "profit_margin": "float", "risk_level": "str"},
            },
        ],
        "allowed_outputs": [
            {
                "action": "tool",
                "tool_name": "calculate_profit_margin",
                "args": {"revenue": 1000.0, "net_profit": 120.0},
                "reason": "Need to calculate margin first.",
            },
            {
                "action": "final",
                "audit_status": "passed",
                "final_answer": "The audit can be delivered.",
                "reason": "All required tool results are available.",
            },
        ],
        "rules": [
            "Return JSON only.",
            "Do not invent tool names.",
            "Call one tool at a time.",
            "Use final only when enough tool evidence exists.",
        ],
    }

    return [
        {
            "role": "system",
            "content": "You are a strict ReAct-style agent controller. Return valid JSON only.",
        },
        {
            "role": "user",
            "content": json.dumps(payload, ensure_ascii=False),
        },
    ]


def rule_based_agent_action(state: AuditState) -> AgentAction:
    """规则版 Agent loop，用作 LLM 失败或无环境变量时的回退。"""

    if state.get("audit_errors"):
        return {
            "action": "final",
            "audit_status": "failed",
            "final_answer": "; ".join(state.get("audit_errors", [])),
            "reason": "Input validation failed.",
        }

    failed_tool = _any_failed_tool_result(state)
    if failed_tool:
        return {
            "action": "final",
            "audit_status": "failed",
            "final_answer": failed_tool["error"] or "tool execution failed",
            "reason": "A tool returned an error.",
        }

    fields = state.get("normalized_fields", {})

    margin_result = _latest_tool_result(state, "calculate_profit_margin")
    if margin_result is None:
        return {
            "action": "tool",
            "tool_name": "calculate_profit_margin",
            "args": {
                "revenue": fields.get("revenue"),
                "net_profit": fields.get("net_profit"),
            },
            "reason": "Need profit margin before risk classification.",
        }

    profit_margin = margin_result["result"]["profit_margin"]

    classify_result = _latest_tool_result(state, "classify_profit_margin")
    if classify_result is None:
        return {
            "action": "tool",
            "tool_name": "classify_profit_margin",
            "args": {"profit_margin": profit_margin},
            "reason": "Need risk classification after margin calculation.",
        }

    risk_level = classify_result["result"]["risk_level"]

    recommendation_result = _latest_tool_result(state, "build_audit_recommendation")
    if recommendation_result is None:
        return {
            "action": "tool",
            "tool_name": "build_audit_recommendation",
            "args": {
                "company": state.get("company", "UnknownCo"),
                "profit_margin": profit_margin,
                "risk_level": risk_level,
            },
            "reason": "Need recommendation after risk classification.",
        }

    status: AuditStatus = classify_result["result"]["status"]
    recommendation = recommendation_result["result"]["recommendation"]
    return {
        "action": "final",
        "audit_status": status,
        "final_answer": recommendation,
        "reason": "All required tool results are available.",
    }


def make_agent_decide_node(
    client: ChatClient | None = None,
    allow_rule_fallback: bool = True,
):
    """创建 Agent 决策节点。"""

    def agent_decide(state: AuditState) -> AuditState:
        max_steps = int(state.get("max_agent_steps", 8))
        step_index = len(state.get("agent_steps", [])) + 1

        if step_index > max_steps:
            final_action: AgentAction = {
                "action": "final",
                "audit_status": "failed",
                "final_answer": f"Agent exceeded max steps: {max_steps}",
                "reason": "Step limit reached.",
            }
            return {
                "current_action": final_action,
                "audit_status": "failed",
                "agent_steps": [
                    {"step_index": step_index, "action": final_action, "planner_mode": "rule_fallback"}
                ],
                "workflow_path": ["agent_decide"],
            }

        messages = build_agent_messages(state)
        prompt = messages[-1]["content"]

        if state.get("audit_errors"):
            action = rule_based_agent_action(state)
            return {
                "current_action": action,
                "planner_mode": "skip_due_to_input_error",
                "agent_steps": [
                    {"step_index": step_index, "action": action, "planner_mode": "skip_due_to_input_error"}
                ],
                "llm_prompts": [prompt],
                "workflow_path": ["agent_decide"],
            }

        try:
            active_client = client or DeepSeekChatClient.from_env()
            response = active_client.complete(messages)
            action = parse_agent_action(response)
            planner_mode: PlannerMode = "llm"
            return {
                "current_action": action,
                "planner_mode": planner_mode,
                "agent_steps": [{"step_index": step_index, "action": action, "planner_mode": planner_mode}],
                "llm_prompts": [prompt],
                "llm_responses": [response],
                "workflow_path": ["agent_decide"],
            }
        except Exception as exc:
            if not allow_rule_fallback:
                action = {
                    "action": "final",
                    "audit_status": "failed",
                    "final_answer": f"Agent decision failed: {exc}",
                    "reason": "LLM decision failed and fallback is disabled.",
                }
                return {
                    "current_action": action,
                    "planner_mode": "llm",
                    "agent_steps": [
                        {"step_index": step_index, "action": action, "planner_mode": "llm"}
                    ],
                    "llm_prompts": [prompt],
                    "workflow_path": ["agent_decide"],
                }

            action = rule_based_agent_action(state)
            return {
                "current_action": action,
                "planner_mode": "rule_fallback",
                "warnings": [f"LLM agent decision failed, used rule fallback: {exc}"],
                "agent_steps": [
                    {"step_index": step_index, "action": action, "planner_mode": "rule_fallback"}
                ],
                "llm_prompts": [prompt],
                "workflow_path": ["agent_decide"],
            }

    return agent_decide


def route_after_agent_decide(state: AuditState) -> Literal["execute_tool", "finalize"]:
    """根据 Agent 当前动作决定下一站。"""

    if state.get("current_action", {}).get("action") == "tool":
        return "execute_tool"
    return "finalize"


def execute_agent_tool(state: AuditState) -> AuditState:
    """执行 Agent 当前决定的一个工具。"""

    action = state.get("current_action", {})
    if action.get("action") != "tool":
        return {"workflow_path": ["execute_agent_tool"]}

    tool_name = action["tool_name"]
    args = action.get("args", {})
    tool = TOOL_REGISTRY[tool_name]

    try:
        result = tool(**args)
        tool_result: ToolResult = {"name": tool_name, "ok": True, "result": result, "error": None}
        normalized_update: dict[str, float] = {}
        if tool_name == "calculate_profit_margin":
            normalized_update = {
                **state.get("normalized_fields", {}),
                "profit_margin": result["profit_margin"],
            }
        return {
            "tool_results": [tool_result],
            "normalized_fields": normalized_update or state.get("normalized_fields", {}),
            "workflow_path": ["execute_agent_tool"],
        }
    except Exception as exc:
        return {
            "tool_results": [
                {"name": tool_name, "ok": False, "result": None, "error": str(exc)}
            ],
            "workflow_path": ["execute_agent_tool"],
        }


def finalize_agent_answer(state: AuditState) -> AuditState:
    """把 Agent final action 写成业务状态。"""

    action = state.get("current_action", {})
    status: AuditStatus = action.get("audit_status", "failed")  # type: ignore[assignment]
    final_answer = action.get("final_answer", "")

    errors: list[str] = []
    warnings: list[str] = []
    if status == "failed" and final_answer:
        errors.append(final_answer)
    if status == "need_review" and final_answer:
        warnings.append(final_answer)

    return {
        "audit_status": status,
        "audit_summary": final_answer,
        "final_answer": final_answer,
        "audit_errors": errors,
        "warnings": warnings,
        "workflow_path": ["finalize_agent_answer"],
    }


def build_graph(client: ChatClient | None = None, allow_rule_fallback: bool = True):
    """创建 Day 13 Agent loop 图。"""

    graph = StateGraph(AuditState)

    graph.add_node("intake", intake)
    graph.add_node("agent_decide", make_agent_decide_node(client, allow_rule_fallback))
    graph.add_node("execute_agent_tool", execute_agent_tool)
    graph.add_node("finalize_agent_answer", finalize_agent_answer)
    graph.add_node("review", review)
    graph.add_node("delivery", delivery)
    graph.add_node("error_report", error_report)

    graph.add_edge(START, "intake")
    graph.add_edge("intake", "agent_decide")
    graph.add_conditional_edges(
        "agent_decide",
        route_after_agent_decide,
        {
            "execute_tool": "execute_agent_tool",
            "finalize": "finalize_agent_answer",
        },
    )
    graph.add_edge("execute_agent_tool", "agent_decide")
    graph.add_conditional_edges(
        "finalize_agent_answer",
        route_by_audit_status,
        {
            "delivery": "delivery",
            "review": "review",
            "error_report": "error_report",
        },
    )
    graph.add_edge("review", "delivery")
    graph.add_edge("delivery", END)
    graph.add_edge("error_report", END)

    return graph.compile()


def initial_state(case_name: str = "passed", max_agent_steps: int = 8) -> AuditState:
    """复用 Day 11 输入，并加上 step limit。"""

    state = base_initial_state(case_name)  # type: ignore[assignment]
    state["max_agent_steps"] = max_agent_steps
    return state  # type: ignore[return-value]


def run_case(
    case_name: str,
    client: ChatClient | None = None,
    allow_rule_fallback: bool = True,
    max_agent_steps: int = 8,
) -> AuditState:
    """运行一个案例。"""

    app = build_graph(client=client, allow_rule_fallback=allow_rule_fallback)
    return app.invoke(initial_state(case_name, max_agent_steps=max_agent_steps))


def run_demo() -> dict[str, AuditState]:
    """命令行 demo。

    有 DeepSeek 环境变量时会调用真实模型；没有时回退到规则 agent loop。
    """

    return {
        "passed": run_case("passed"),
        "need_review": run_case("need_review"),
        "failed_negative": run_case("failed_negative"),
    }


if __name__ == "__main__":
    print(json.dumps(run_demo(), ensure_ascii=False, indent=2, default=str))
