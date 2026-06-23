"""Day 11: tool calling / tool router.

今天开始把主线从“安全护栏”切回 Agent 能力。

大白话版本：

普通 workflow：
    节点自己把所有事情都做了。

Tool-calling Agent：
    节点先决定要调用哪些工具，
    工具节点执行工具，
    再把工具结果交给后续节点综合判断。

这一天还不接真实 LLM。
我们先用一个确定性的 planner 模拟“模型决定调用哪些工具”。
下一天再把这个 planner 换成 LLM。

核心能力：

    用户输入财务数据
      -> planner 生成 tool_calls
      -> executor 执行工具
      -> synthesizer 根据工具结果做审计结论
      -> graph 分流到 delivery / review / error_report

这已经开始像 Agent，而不是一串把自己伪装成架构的 if else。
"""

from __future__ import annotations

import json
from operator import add
from typing import Annotated, Any, Callable, Literal

from typing_extensions import TypedDict

from langgraph.graph import END, START, StateGraph

AuditStatus = Literal["passed", "need_review", "failed"]
RouteName = Literal["delivery", "review", "error_report"]
ToolName = Literal[
    "calculate_profit_margin",
    "classify_profit_margin",
    "build_audit_recommendation",
]


class RawFields(TypedDict, total=False):
    revenue: float | int | str | None
    net_profit: float | int | str | None


class ToolCall(TypedDict):
    """一个工具调用请求。

    这就是 LLM tool calling 里的核心对象的简化版：
    - name：调用哪个工具
    - args：给工具传什么参数

    后面接 LLM 时，模型吐出的也基本是类似结构。
    名字可能更花，但本质就这点东西。人类又一次把函数调用包装出了仪式感。
    """

    name: ToolName
    args: dict[str, Any]


class ToolResult(TypedDict):
    """工具执行结果。"""

    name: ToolName
    ok: bool
    result: Any
    error: str | None


class AuditState(TypedDict, total=False):
    company: str
    raw_fields: RawFields
    normalized_fields: dict[str, float]
    tool_calls: Annotated[list[ToolCall], add]
    tool_results: Annotated[list[ToolResult], add]
    audit_errors: Annotated[list[str], add]
    warnings: Annotated[list[str], add]
    audit_status: AuditStatus
    audit_summary: str
    review_note: str
    delivery_message: str
    workflow_path: Annotated[list[str], add]


ToolFn = Callable[..., Any]


def _to_float(value: float | int | str | None, field_name: str) -> tuple[float | None, str | None]:
    """把输入转成 float。"""

    if value is None:
        return None, f"{field_name} is missing"

    try:
        return float(value), None
    except (TypeError, ValueError):
        return None, f"{field_name} is not a number: {value!r}"


def calculate_profit_margin(revenue: float, net_profit: float) -> dict[str, float]:
    """工具 1：计算利润率。"""

    if revenue <= 0:
        raise ValueError("revenue must be greater than 0")

    return {
        "revenue": revenue,
        "net_profit": net_profit,
        "profit_margin": round(net_profit / revenue, 4),
    }


def classify_profit_margin(profit_margin: float) -> dict[str, Any]:
    """工具 2：根据利润率分类风险。"""

    if profit_margin < 0:
        return {
            "status": "failed",
            "risk_level": "critical",
            "reason": "profit margin is negative",
        }

    if profit_margin < 0.05:
        return {
            "status": "need_review",
            "risk_level": "medium",
            "reason": "profit margin is low and requires human review",
        }

    return {
        "status": "passed",
        "risk_level": "low",
        "reason": "profit margin is acceptable",
    }


def build_audit_recommendation(company: str, profit_margin: float, risk_level: str) -> dict[str, str]:
    """工具 3：生成审计建议。"""

    if risk_level == "critical":
        action = "block_delivery"
        recommendation = f"{company} should not be delivered because the margin is negative."
    elif risk_level == "medium":
        action = "human_review"
        recommendation = f"{company} needs manual review before delivery."
    else:
        action = "deliver"
        recommendation = f"{company} can be delivered automatically."

    return {
        "action": action,
        "recommendation": recommendation,
        "margin_text": f"{profit_margin:.2%}",
    }


TOOL_REGISTRY: dict[ToolName, ToolFn] = {
    "calculate_profit_margin": calculate_profit_margin,
    "classify_profit_margin": classify_profit_margin,
    "build_audit_recommendation": build_audit_recommendation,
}


def intake(state: AuditState) -> AuditState:
    """读取原始输入，并做基础类型转换。"""

    raw_fields = state.get("raw_fields", {})
    errors: list[str] = []

    revenue, revenue_error = _to_float(raw_fields.get("revenue"), "revenue")
    net_profit, net_profit_error = _to_float(raw_fields.get("net_profit"), "net_profit")

    if revenue_error:
        errors.append(revenue_error)
    if net_profit_error:
        errors.append(net_profit_error)

    normalized_fields: dict[str, float] = {}
    if revenue is not None:
        normalized_fields["revenue"] = revenue
    if net_profit is not None:
        normalized_fields["net_profit"] = net_profit

    return {
        "company": str(state.get("company", "UnknownCo")),
        "normalized_fields": normalized_fields,
        "audit_errors": errors,
        "workflow_path": ["intake"],
    }


def plan_tool_calls(state: AuditState) -> AuditState:
    """规划要调用哪些工具。

    这一步就是 Agent 的“想一想该用哪些工具”。

    今天先不用 LLM，而是确定性规划：
    - 输入已经缺字段：不规划工具，直接失败。
    - 输入完整：规划利润率计算工具。

    后面 Day 12 会把这个节点替换成 LLM planner。
    """

    if state.get("audit_errors"):
        return {
            "audit_status": "failed",
            "workflow_path": ["plan_tool_calls"],
        }

    fields = state.get("normalized_fields", {})
    revenue = fields.get("revenue")
    net_profit = fields.get("net_profit")

    if revenue is None or net_profit is None:
        return {
            "audit_status": "failed",
            "audit_errors": ["normalized revenue or net_profit is missing"],
            "workflow_path": ["plan_tool_calls"],
        }

    return {
        "tool_calls": [
            {
                "name": "calculate_profit_margin",
                "args": {
                    "revenue": revenue,
                    "net_profit": net_profit,
                },
            }
        ],
        "workflow_path": ["plan_tool_calls"],
    }


def execute_tools(state: AuditState) -> AuditState:
    """执行 planner 规划出来的工具。

    注意：这里是工具执行节点。
    它不负责做审计结论，只负责：
    - 找工具
    - 传参数
    - 收结果
    - 把 ToolResult 写回 State
    """

    results: list[ToolResult] = []

    for tool_call in state.get("tool_calls", []):
        name = tool_call["name"]
        args = tool_call["args"]
        tool = TOOL_REGISTRY[name]

        try:
            result = tool(**args)
            results.append({"name": name, "ok": True, "result": result, "error": None})
        except Exception as exc:  # 真实系统里要更细分错误类型，这里先抓住教学主线
            results.append({"name": name, "ok": False, "result": None, "error": str(exc)})

    return {
        "tool_results": results,
        "workflow_path": ["execute_tools"],
    }


def _latest_tool_result(state: AuditState, name: ToolName) -> ToolResult | None:
    """按工具名取最后一个结果。"""

    for result in reversed(state.get("tool_results", [])):
        if result["name"] == name:
            return result
    return None


def synthesize_audit(state: AuditState) -> AuditState:
    """综合工具结果，生成下一轮工具调用或最终审计结论。"""

    if state.get("audit_status") == "failed" and state.get("audit_errors"):
        return {
            "audit_summary": "Input validation failed before tool execution.",
            "workflow_path": ["synthesize_audit"],
        }

    margin_result = _latest_tool_result(state, "calculate_profit_margin")
    if margin_result is None:
        return {
            "audit_status": "failed",
            "audit_errors": ["profit margin tool was not executed"],
            "workflow_path": ["synthesize_audit"],
        }

    if not margin_result["ok"]:
        return {
            "audit_status": "failed",
            "audit_errors": [margin_result["error"] or "profit margin tool failed"],
            "workflow_path": ["synthesize_audit"],
        }

    margin_payload = margin_result["result"]
    profit_margin = margin_payload["profit_margin"]

    classification = classify_profit_margin(profit_margin)
    recommendation = build_audit_recommendation(
        state.get("company", "UnknownCo"),
        profit_margin,
        classification["risk_level"],
    )

    tool_results: list[ToolResult] = [
        {
            "name": "classify_profit_margin",
            "ok": True,
            "result": classification,
            "error": None,
        },
        {
            "name": "build_audit_recommendation",
            "ok": True,
            "result": recommendation,
            "error": None,
        },
    ]

    warnings: list[str] = []
    errors: list[str] = []
    status: AuditStatus = classification["status"]

    if status == "need_review":
        warnings.append(classification["reason"])
    if status == "failed":
        errors.append(classification["reason"])

    return {
        "normalized_fields": {
            **state.get("normalized_fields", {}),
            "profit_margin": profit_margin,
        },
        "tool_results": tool_results,
        "audit_status": status,
        "warnings": warnings,
        "audit_errors": errors,
        "audit_summary": recommendation["recommendation"],
        "workflow_path": ["synthesize_audit"],
    }


def route_by_audit_status(state: AuditState) -> RouteName:
    """根据审计结论分流。"""

    status = state.get("audit_status")
    if status == "passed":
        return "delivery"
    if status == "need_review":
        return "review"
    return "error_report"


def review(state: AuditState) -> AuditState:
    """模拟人工复核。"""

    return {
        "review_note": "Manual reviewer should inspect low margin before delivery.",
        "workflow_path": ["review"],
    }


def delivery(state: AuditState) -> AuditState:
    """生成交付消息。"""

    fields = state.get("normalized_fields", {})
    return {
        "delivery_message": (
            f"{state.get('company')} audit passed: "
            f"profit margin = {fields.get('profit_margin', 0.0):.2%}. "
            f"{state.get('audit_summary', '')}"
        ),
        "workflow_path": ["delivery"],
    }


def error_report(state: AuditState) -> AuditState:
    """生成错误消息。"""

    errors = state.get("audit_errors", [])
    return {
        "delivery_message": f"{state.get('company')} audit failed: {'; '.join(errors)}",
        "workflow_path": ["error_report"],
    }


def build_graph():
    """创建 Day 11 tool calling 图。"""

    graph = StateGraph(AuditState)

    graph.add_node("intake", intake)
    graph.add_node("plan_tool_calls", plan_tool_calls)
    graph.add_node("execute_tools", execute_tools)
    graph.add_node("synthesize_audit", synthesize_audit)
    graph.add_node("review", review)
    graph.add_node("delivery", delivery)
    graph.add_node("error_report", error_report)

    graph.add_edge(START, "intake")
    graph.add_edge("intake", "plan_tool_calls")
    graph.add_edge("plan_tool_calls", "execute_tools")
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
    """生成 demo 输入。"""

    cases: dict[str, AuditState] = {
        "passed": {
            "company": "DemoCorp",
            "raw_fields": {"revenue": "1000", "net_profit": "120"},
        },
        "need_review": {
            "company": "LowProfitCorp",
            "raw_fields": {"revenue": "2000", "net_profit": "60"},
        },
        "failed_negative": {
            "company": "LossCorp",
            "raw_fields": {"revenue": "1000", "net_profit": "-50"},
        },
        "failed_zero_revenue": {
            "company": "ZeroRevenueCorp",
            "raw_fields": {"revenue": "0", "net_profit": "10"},
        },
        "failed_missing": {
            "company": "MissingProfitCorp",
            "raw_fields": {"revenue": "1000", "net_profit": None},
        },
    }

    return cases[case_name]


def run_case(case_name: str) -> AuditState:
    """运行一个案例。"""

    app = build_graph()
    return app.invoke(initial_state(case_name))


def run_demo() -> dict[str, AuditState]:
    """命令行 demo。"""

    return {
        "passed": run_case("passed"),
        "need_review": run_case("need_review"),
        "failed_negative": run_case("failed_negative"),
        "failed_zero_revenue": run_case("failed_zero_revenue"),
    }


if __name__ == "__main__":
    print(json.dumps(run_demo(), ensure_ascii=False, indent=2, default=str))
