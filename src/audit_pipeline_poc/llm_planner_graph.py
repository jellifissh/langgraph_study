"""Day 12: LLM planner with DeepSeek environment variables.

今天把 Day 11 的手写 planner 换成 LLM planner。

Day 11：
    plan_tool_calls() 是我们手写规则。

Day 12：
    LLM 根据输入和工具列表生成 tool_calls。

本文件不会把 API key 写进代码。
它只读取你电脑环境变量：

    DEEPSEEK_API_KEY
    DEEPSEEK_BASE_URL
    DEEPSEEK_MODEL

测试不会真的请求 DeepSeek，而是用 fake client。
你本地运行 demo 时，如果环境变量存在，就会用 DeepSeek；如果没有，就回退到规则 planner。

这就是生产里常见的姿势：
    测试用 mock / fake
    本地或线上才用真实模型

终于开始像 Agent 了，不再只是把 if else 摆成风水阵。
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any, Literal, Protocol

from typing_extensions import TypedDict

from langgraph.graph import END, START, StateGraph

from audit_pipeline_poc.tool_calling_graph import (
    TOOL_REGISTRY,
    AuditState as BaseAuditState,
    ToolCall,
    ToolName,
    delivery,
    error_report,
    execute_tools,
    initial_state as base_initial_state,
    intake,
    review,
    route_by_audit_status,
    synthesize_audit,
)

PlannerMode = Literal["llm", "rule_fallback", "skip_due_to_input_error"]


class AuditState(BaseAuditState, total=False):
    """Day 12 的 State。

    在 Day 11 的 State 基础上新增：
    - llm_prompt：发给模型看的提示词
    - llm_response：模型原始返回
    - planner_mode：这次是 LLM 规划，还是规则回退
    """

    llm_prompt: str
    llm_response: str
    planner_mode: PlannerMode


class ChatClient(Protocol):
    """最小聊天模型接口。

    测试时用 FakeClient。
    本地运行时用 DeepSeekChatClient。
    """

    def complete(self, messages: list[dict[str, str]]) -> str:
        """返回模型文本。"""


class DeepSeekChatClient:
    """使用 DeepSeek/OpenAI-compatible Chat Completions API 的最小客户端。

    只用标准库 urllib，避免为了一个 POST 请求再装一堆依赖。
    软件行业已经够依赖地狱了，不必主动加柴。
    """

    def __init__(self, api_key: str, base_url: str, model: str, timeout: int = 30) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    @classmethod
    def from_env(cls) -> "DeepSeekChatClient":
        """从环境变量读取 DeepSeek 配置。"""

        api_key = os.environ.get("DEEPSEEK_API_KEY")
        base_url = os.environ.get("DEEPSEEK_BASE_URL")
        model = os.environ.get("DEEPSEEK_MODEL")

        missing = [
            name
            for name, value in {
                "DEEPSEEK_API_KEY": api_key,
                "DEEPSEEK_BASE_URL": base_url,
                "DEEPSEEK_MODEL": model,
            }.items()
            if not value
        ]
        if missing:
            raise ValueError(f"Missing DeepSeek environment variables: {', '.join(missing)}")

        return cls(api_key=api_key or "", base_url=base_url or "", model=model or "")

    @property
    def chat_completions_url(self) -> str:
        """兼容 base_url 是否已经带 /chat/completions。"""

        if self.base_url.endswith("/chat/completions"):
            return self.base_url
        return f"{self.base_url}/chat/completions"

    def complete(self, messages: list[dict[str, str]]) -> str:
        """调用 DeepSeek 并返回 message.content。"""

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0,
        }
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        request = urllib.request.Request(
            self.chat_completions_url,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                response_body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"DeepSeek HTTP {exc.code}: {error_body}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"DeepSeek request failed: {exc}") from exc

        data = json.loads(response_body)
        return data["choices"][0]["message"]["content"]


def build_planner_messages(state: AuditState) -> list[dict[str, str]]:
    """构造 LLM planner 提示词。

    重点：把可用工具列表明确给模型。
    模型只能从已有工具里选，不能自己发明工具。
    """

    fields = state.get("normalized_fields", {})
    prompt = {
        "task": "Plan tool calls for a financial audit workflow.",
        "company": state.get("company"),
        "normalized_fields": fields,
        "available_tools": [
            {
                "name": "calculate_profit_margin",
                "description": "Calculate profit margin from revenue and net_profit.",
                "args_schema": {"revenue": "float", "net_profit": "float"},
            }
        ],
        "output_schema": {
            "tool_calls": [
                {
                    "name": "calculate_profit_margin",
                    "args": {"revenue": 1000.0, "net_profit": 120.0},
                }
            ]
        },
        "rules": [
            "Return JSON only.",
            "Do not invent tool names.",
            "Use only the available_tools list.",
            "If the input is enough to calculate margin, call calculate_profit_margin exactly once.",
        ],
    }

    return [
        {
            "role": "system",
            "content": "You are a strict tool planning agent. Return valid JSON only.",
        },
        {
            "role": "user",
            "content": json.dumps(prompt, ensure_ascii=False),
        },
    ]


def _extract_json_object(text: str) -> dict[str, Any]:
    """从模型输出里提取 JSON 对象。

    模型有时会很贴心地包一层 ```json，像给机器读的结果穿礼服。
    这里做一点容错。
    """

    stripped = text.strip()
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", stripped, flags=re.DOTALL)
    if fence_match:
        stripped = fence_match.group(1)

    return json.loads(stripped)


def parse_tool_calls_from_llm_response(text: str) -> list[ToolCall]:
    """把模型返回解析成 tool_calls，并校验工具名。"""

    data = _extract_json_object(text)
    raw_tool_calls = data.get("tool_calls")
    if not isinstance(raw_tool_calls, list):
        raise ValueError("LLM response must contain a tool_calls list")

    parsed: list[ToolCall] = []
    for item in raw_tool_calls:
        if not isinstance(item, dict):
            raise ValueError("Each tool call must be an object")

        name = item.get("name")
        args = item.get("args", {})

        if name not in TOOL_REGISTRY:
            raise ValueError(f"Unknown tool name from LLM: {name!r}")
        if not isinstance(args, dict):
            raise ValueError("Tool args must be an object")

        parsed.append({"name": name, "args": args})  # type: ignore[typeddict-item]

    return parsed


def rule_based_tool_calls(state: AuditState) -> list[ToolCall]:
    """规则 planner，用作 LLM 失败时的安全回退。"""

    fields = state.get("normalized_fields", {})
    revenue = fields.get("revenue")
    net_profit = fields.get("net_profit")

    if revenue is None or net_profit is None:
        raise ValueError("normalized revenue or net_profit is missing")

    return [
        {
            "name": "calculate_profit_margin",
            "args": {"revenue": revenue, "net_profit": net_profit},
        }
    ]


def make_llm_plan_tool_calls_node(
    client: ChatClient | None = None,
    allow_rule_fallback: bool = True,
):
    """创建 LLM planner 节点。

    为什么用工厂函数？
    因为测试时要塞 FakeClient，真实运行时才从环境变量创建 DeepSeekChatClient。
    """

    def llm_plan_tool_calls(state: AuditState) -> AuditState:
        if state.get("audit_errors"):
            return {
                "audit_status": "failed",
                "planner_mode": "skip_due_to_input_error",
                "workflow_path": ["llm_plan_tool_calls"],
            }

        messages = build_planner_messages(state)
        llm_prompt = messages[-1]["content"]

        try:
            active_client = client or DeepSeekChatClient.from_env()
            llm_response = active_client.complete(messages)
            tool_calls = parse_tool_calls_from_llm_response(llm_response)
            return {
                "tool_calls": tool_calls,
                "llm_prompt": llm_prompt,
                "llm_response": llm_response,
                "planner_mode": "llm",
                "workflow_path": ["llm_plan_tool_calls"],
            }
        except Exception as exc:
            if not allow_rule_fallback:
                return {
                    "audit_status": "failed",
                    "audit_errors": [f"LLM planner failed: {exc}"],
                    "llm_prompt": llm_prompt,
                    "llm_response": "",
                    "planner_mode": "llm",
                    "workflow_path": ["llm_plan_tool_calls"],
                }

            try:
                fallback_calls = rule_based_tool_calls(state)
            except Exception as fallback_exc:
                return {
                    "audit_status": "failed",
                    "audit_errors": [
                        f"LLM planner failed: {exc}",
                        f"Rule fallback failed: {fallback_exc}",
                    ],
                    "llm_prompt": llm_prompt,
                    "llm_response": "",
                    "planner_mode": "rule_fallback",
                    "workflow_path": ["llm_plan_tool_calls"],
                }

            return {
                "tool_calls": fallback_calls,
                "warnings": [f"LLM planner failed, used rule fallback: {exc}"],
                "llm_prompt": llm_prompt,
                "llm_response": "",
                "planner_mode": "rule_fallback",
                "workflow_path": ["llm_plan_tool_calls"],
            }

    return llm_plan_tool_calls


def build_graph(client: ChatClient | None = None, allow_rule_fallback: bool = True):
    """创建 Day 12 LLM planner 图。"""

    graph = StateGraph(AuditState)

    graph.add_node("intake", intake)
    graph.add_node(
        "llm_plan_tool_calls",
        make_llm_plan_tool_calls_node(client=client, allow_rule_fallback=allow_rule_fallback),
    )
    graph.add_node("execute_tools", execute_tools)
    graph.add_node("synthesize_audit", synthesize_audit)
    graph.add_node("review", review)
    graph.add_node("delivery", delivery)
    graph.add_node("error_report", error_report)

    graph.add_edge(START, "intake")
    graph.add_edge("intake", "llm_plan_tool_calls")
    graph.add_edge("llm_plan_tool_calls", "execute_tools")
    graph.add_edge("execute_tools", "synthesize_audit")
    graph.add_conditional_edges(
        "synthesize_audit",
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


def initial_state(case_name: str = "passed") -> AuditState:
    """复用 Day 11 的 demo 输入。"""

    return base_initial_state(case_name)  # type: ignore[return-value]


def run_case(
    case_name: str,
    client: ChatClient | None = None,
    allow_rule_fallback: bool = True,
) -> AuditState:
    """运行一个案例。"""

    app = build_graph(client=client, allow_rule_fallback=allow_rule_fallback)
    return app.invoke(initial_state(case_name))


def run_demo() -> dict[str, AuditState]:
    """命令行 demo。

    有 DeepSeek 环境变量时会调用真实模型；没有时回退到规则 planner。
    """

    return {
        "passed": run_case("passed"),
        "need_review": run_case("need_review"),
        "failed_negative": run_case("failed_negative"),
    }


if __name__ == "__main__":
    print(json.dumps(run_demo(), ensure_ascii=False, indent=2, default=str))
