"""Day 5: use reducers to accumulate list fields in State.

大白话版本：

- State = 账本。
- 默认情况下，同一个字段被节点更新时会被覆盖。
- Reducer = 字段更新规则。
- 对 list 字段来说，常见需求不是覆盖，而是追加。

今天我们把 `workflow_path`、`audit_errors`、`warnings`、`audit_events`
改成带 reducer 的字段，节点只需要返回本次新增的一小段记录，
LangGraph 会负责把它们合并到账本里。
"""

from __future__ import annotations

import json
from operator import add
from typing import Annotated, Literal

from typing_extensions import TypedDict

from langgraph.graph import END, START, StateGraph

AuditStatus = Literal["passed", "need_review", "failed"]
RouteName = Literal["delivery", "review", "error_report"]


class RawFields(TypedDict, total=False):
    """原始输入区：外部传进来的字段，可能不干净。"""

    revenue: float | int | str | None
    net_profit: float | int | str | None


class NormalizedFields(TypedDict, total=False):
    """标准化字段区：清洗后给后续节点使用。"""

    revenue: float
    net_profit: float
    profit_margin: float


class AuditState(TypedDict, total=False):
    """带 reducer 的 State 账本。

    注意这些字段：
    - audit_errors: Annotated[list[str], add]
    - warnings: Annotated[list[str], add]
    - audit_events: Annotated[list[str], add]
    - workflow_path: Annotated[list[str], add]

    它们的更新方式不是覆盖，而是追加。
    """

    company: str
    raw_fields: RawFields
    normalized_fields: NormalizedFields
    audit_errors: Annotated[list[str], add]
    warnings: Annotated[list[str], add]
    audit_events: Annotated[list[str], add]
    audit_status: AuditStatus
    review_note: str
    delivery_message: str
    workflow_path: Annotated[list[str], add]


def _event(message: str) -> list[str]:
    """返回一条事件记录。用 list 包起来，是为了让 reducer 追加。"""

    return [message]


def intake(state: AuditState) -> AuditState:
    """intake 点：接收原始输入。"""

    if "company" not in state:
        raise ValueError("Missing required field: company")
    if "raw_fields" not in state:
        raise ValueError("Missing required field: raw_fields")

    return {
        "company": str(state["company"]),
        "raw_fields": state["raw_fields"],
        "workflow_path": ["intake"],
        "audit_events": _event("intake: received raw fields"),
    }


def _to_float(value: float | int | str | None, field_name: str) -> tuple[float | None, str | None]:
    """把原始字段转成 float。"""

    if value is None:
        return None, f"{field_name} is missing"

    try:
        return float(value), None
    except (TypeError, ValueError):
        return None, f"{field_name} is not a number: {value!r}"


def normalize(state: AuditState) -> AuditState:
    """normalize 点：把 raw_fields 变成 normalized_fields。"""

    raw_fields = state["raw_fields"]
    revenue, revenue_error = _to_float(raw_fields.get("revenue"), "revenue")
    net_profit, net_profit_error = _to_float(raw_fields.get("net_profit"), "net_profit")

    normalized_fields: NormalizedFields = {}
    errors: list[str] = []

    if revenue is not None:
        normalized_fields["revenue"] = revenue
    if net_profit is not None:
        normalized_fields["net_profit"] = net_profit

    for error in [revenue_error, net_profit_error]:
        if error:
            errors.append(error)

    return {
        "normalized_fields": normalized_fields,
        "audit_errors": errors,
        "workflow_path": ["normalize"],
        "audit_events": _event("normalize: converted raw fields to numeric fields"),
    }


def audit(state: AuditState) -> AuditState:
    """audit 点：基于标准化字段做审计判断。"""

    if state.get("audit_errors"):
        return {
            "audit_status": "failed",
            "workflow_path": ["audit"],
            "audit_events": _event("audit: stopped because normalize produced errors"),
        }

    normalized_fields = dict(state["normalized_fields"])
    revenue = normalized_fields["revenue"]
    net_profit = normalized_fields["net_profit"]

    if revenue <= 0:
        return {
            "audit_status": "failed",
            "audit_errors": ["revenue must be greater than 0"],
            "workflow_path": ["audit"],
            "audit_events": _event("audit: revenue failed business rule"),
        }

    profit_margin = net_profit / revenue
    normalized_fields["profit_margin"] = round(profit_margin, 4)

    if profit_margin < 0:
        return {
            "normalized_fields": normalized_fields,
            "audit_status": "failed",
            "audit_errors": ["profit margin is negative"],
            "workflow_path": ["audit"],
            "audit_events": _event("audit: negative profit margin"),
        }

    if profit_margin < 0.05:
        return {
            "normalized_fields": normalized_fields,
            "audit_status": "need_review",
            "warnings": ["profit margin is low and requires review"],
            "workflow_path": ["audit"],
            "audit_events": _event("audit: low profit margin requires review"),
        }

    return {
        "normalized_fields": normalized_fields,
        "audit_status": "passed",
        "workflow_path": ["audit"],
        "audit_events": _event("audit: passed all rules"),
    }


def route_by_audit_result(state: AuditState) -> RouteName:
    """分岔路口：只根据 audit_status 选路线。"""

    status = state["audit_status"]

    if status == "passed":
        return "delivery"
    if status == "need_review":
        return "review"
    return "error_report"


def review(state: AuditState) -> AuditState:
    """review 点：模拟人工复核。"""

    return {
        "review_note": "manual review required because warnings exist",
        "workflow_path": ["review"],
        "audit_events": _event("review: human review placeholder executed"),
    }


def delivery(state: AuditState) -> AuditState:
    """delivery 点：生成交付信息。"""

    profit_margin = state["normalized_fields"].get("profit_margin", 0.0)

    return {
        "delivery_message": (
            f"{state['company']} audit {state['audit_status']}: "
            f"profit margin = {profit_margin:.2%}"
        ),
        "workflow_path": ["delivery"],
        "audit_events": _event("delivery: final message generated"),
    }


def error_report(state: AuditState) -> AuditState:
    """error_report 点：生成失败说明。"""

    errors = "; ".join(state.get("audit_errors", [])) or "unknown error"

    return {
        "delivery_message": f"{state['company']} audit failed: {errors}",
        "workflow_path": ["error_report"],
        "audit_events": _event("error_report: failure message generated"),
    }


def build_graph():
    """创建使用 reducer 累积列表字段的流程图。"""

    graph = StateGraph(AuditState)

    graph.add_node("intake", intake)
    graph.add_node("normalize", normalize)
    graph.add_node("audit", audit)
    graph.add_node("review", review)
    graph.add_node("delivery", delivery)
    graph.add_node("error_report", error_report)

    graph.add_edge(START, "intake")
    graph.add_edge("intake", "normalize")
    graph.add_edge("normalize", "audit")
    graph.add_conditional_edges(
        "audit",
        route_by_audit_result,
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


def _with_empty_lists(state: AuditState) -> AuditState:
    """给 reducer 字段一个空列表起点，让输出更稳定。"""

    return {
        **state,
        "audit_errors": [],
        "warnings": [],
        "audit_events": [],
        "workflow_path": [],
    }


def run_case(case_name: str) -> AuditState:
    """按案例名跑一次 reducer 工作流。"""

    cases: dict[str, AuditState] = {
        "passed": {
            "company": "DemoCorp",
            "raw_fields": {"revenue": "1000", "net_profit": "120"},
        },
        "need_review": {
            "company": "LowProfitCorp",
            "raw_fields": {"revenue": "2000", "net_profit": "60"},
        },
        "failed_missing": {
            "company": "MissingProfitCorp",
            "raw_fields": {"revenue": "1000", "net_profit": None},
        },
        "failed_bad_number": {
            "company": "BadNumberCorp",
            "raw_fields": {"revenue": "abc", "net_profit": "20"},
        },
    }

    if case_name not in cases:
        raise ValueError(f"Unknown case: {case_name}. Expected one of: {sorted(cases)}")

    app = build_graph()
    return app.invoke(_with_empty_lists(cases[case_name]))


if __name__ == "__main__":
    for case_name in ["passed", "need_review", "failed_missing", "failed_bad_number"]:
        result = run_case(case_name)
        print(f"\n=== {case_name} ===")
        print(json.dumps(result, ensure_ascii=False, indent=2))
