"""Day 4: design a clearer State schema for the audit workflow.

大白话版本：

- State = 账本。
- Day 1/2 的账本是平铺字段：company、revenue、net_profit...
- Day 4 的重点是把账本分区：原始输入、标准化字段、审计结果、输出、调试路线。

这样做不是为了显得高级，而是为了以后流程变大时还能看懂。
"""

from __future__ import annotations

import json
from typing import Literal

from typing_extensions import TypedDict

from langgraph.graph import END, START, StateGraph

AuditStatus = Literal["passed", "need_review", "failed"]
RouteName = Literal["delivery", "review", "error_report"]


class RawFields(TypedDict, total=False):
    """原始输入区：外部传进来的字段，可能类型混乱或缺字段。"""

    revenue: float | int | str | None
    net_profit: float | int | str | None


class NormalizedFields(TypedDict, total=False):
    """标准化字段区：normalize 节点清洗后的可信数值。"""

    revenue: float
    net_profit: float
    profit_margin: float


class AuditState(TypedDict, total=False):
    """更清楚的 State 账本。

    分区思路：
    - company：任务主体。
    - raw_fields：原始字段，不保证干净。
    - normalized_fields：清洗后的字段，后续节点优先读这里。
    - audit_errors：硬错误，通常会进入 failed。
    - warnings：软风险，可能进入 need_review。
    - audit_status：路由判断用的结论。
    - review_note：人工复核说明。
    - delivery_message：最终交付表达。
    - workflow_path：调试路线，记录这次实际走过哪些点。
    """

    company: str
    raw_fields: RawFields
    normalized_fields: NormalizedFields
    audit_errors: list[str]
    warnings: list[str]
    audit_status: AuditStatus
    review_note: str
    delivery_message: str
    workflow_path: list[str]


def _append_path(state: AuditState, step: str) -> list[str]:
    """workflow_path = 路线记录本，方便观察这次实际怎么走。"""

    return [*state.get("workflow_path", []), step]


def intake(state: AuditState) -> AuditState:
    """intake 点：只接收原始数据，不做复杂清洗。"""

    if "company" not in state:
        raise ValueError("Missing required field: company")
    if "raw_fields" not in state:
        raise ValueError("Missing required field: raw_fields")

    return {
        "company": str(state["company"]),
        "raw_fields": state["raw_fields"],
        "audit_errors": [],
        "warnings": [],
        "workflow_path": _append_path(state, "intake"),
    }


def _to_float(value: float | int | str | None, field_name: str) -> tuple[float | None, str | None]:
    """把原始字段转成 float；失败时返回错误信息。"""

    if value is None:
        return None, f"{field_name} is missing"

    try:
        return float(value), None
    except (TypeError, ValueError):
        return None, f"{field_name} is not a number: {value!r}"


def normalize(state: AuditState) -> AuditState:
    """normalize 点：把原始字段清洗成后续节点可用的数值。"""

    raw_fields = state["raw_fields"]
    audit_errors = list(state.get("audit_errors", []))

    revenue, revenue_error = _to_float(raw_fields.get("revenue"), "revenue")
    net_profit, net_profit_error = _to_float(raw_fields.get("net_profit"), "net_profit")

    for error in [revenue_error, net_profit_error]:
        if error:
            audit_errors.append(error)

    normalized_fields: NormalizedFields = {}
    if revenue is not None:
        normalized_fields["revenue"] = revenue
    if net_profit is not None:
        normalized_fields["net_profit"] = net_profit

    return {
        "normalized_fields": normalized_fields,
        "audit_errors": audit_errors,
        "workflow_path": _append_path(state, "normalize"),
    }


def audit(state: AuditState) -> AuditState:
    """audit 点：只读 normalized_fields，写审计结论。"""

    normalized_fields = dict(state.get("normalized_fields", {}))
    audit_errors = list(state.get("audit_errors", []))
    warnings = list(state.get("warnings", []))

    if audit_errors:
        return {
            "audit_status": "failed",
            "audit_errors": audit_errors,
            "warnings": warnings,
            "workflow_path": _append_path(state, "audit"),
        }

    revenue = normalized_fields["revenue"]
    net_profit = normalized_fields["net_profit"]

    if revenue <= 0:
        audit_errors.append("revenue must be greater than 0")
        return {
            "audit_status": "failed",
            "audit_errors": audit_errors,
            "warnings": warnings,
            "workflow_path": _append_path(state, "audit"),
        }

    profit_margin = net_profit / revenue
    normalized_fields["profit_margin"] = round(profit_margin, 4)

    if profit_margin < 0:
        audit_errors.append("profit margin is negative")
        audit_status: AuditStatus = "failed"
    elif profit_margin < 0.05:
        warnings.append("profit margin is low and requires review")
        audit_status = "need_review"
    else:
        audit_status = "passed"

    return {
        "normalized_fields": normalized_fields,
        "audit_errors": audit_errors,
        "warnings": warnings,
        "audit_status": audit_status,
        "workflow_path": _append_path(state, "audit"),
    }


def route_by_audit_result(state: AuditState) -> RouteName:
    """分岔路口：只根据 audit_status 选路，不做业务计算。"""

    status = state["audit_status"]

    if status == "passed":
        return "delivery"
    if status == "need_review":
        return "review"
    return "error_report"


def review(state: AuditState) -> AuditState:
    """review 点：现在仍然只是模拟人工复核。"""

    return {
        "review_note": "manual review required because warnings exist",
        "workflow_path": _append_path(state, "review"),
    }


def delivery(state: AuditState) -> AuditState:
    """delivery 点：根据结构化账本生成交付说明。"""

    fields = state["normalized_fields"]
    profit_margin = fields.get("profit_margin", 0.0)

    return {
        "delivery_message": (
            f"{state['company']} audit {state['audit_status']}: "
            f"profit margin = {profit_margin:.2%}"
        ),
        "workflow_path": _append_path(state, "delivery"),
    }


def error_report(state: AuditState) -> AuditState:
    """error_report 点：把错误列表整理成失败说明。"""

    errors = "; ".join(state.get("audit_errors", [])) or "unknown error"

    return {
        "delivery_message": f"{state['company']} audit failed: {errors}",
        "workflow_path": _append_path(state, "error_report"),
    }


def build_graph():
    """创建带 normalize 节点和结构化 State 的流程图。"""

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


def run_case(case_name: str) -> AuditState:
    """按案例名跑一次结构化 State 工作流。"""

    cases: dict[str, AuditState] = {
        "passed": {
            "company": "DemoCorp",
            "raw_fields": {
                "revenue": "1000",
                "net_profit": "120",
            },
        },
        "need_review": {
            "company": "LowProfitCorp",
            "raw_fields": {
                "revenue": "2000",
                "net_profit": "60",
            },
        },
        "failed_missing": {
            "company": "MissingProfitCorp",
            "raw_fields": {
                "revenue": "1000",
                "net_profit": None,
            },
        },
        "failed_zero_revenue": {
            "company": "ZeroRevenueCorp",
            "raw_fields": {
                "revenue": 0,
                "net_profit": 10,
            },
        },
    }

    if case_name not in cases:
        raise ValueError(f"Unknown case: {case_name}. Expected one of: {sorted(cases)}")

    app = build_graph()
    return app.invoke(cases[case_name])


if __name__ == "__main__":
    for case_name in ["passed", "need_review", "failed_missing", "failed_zero_revenue"]:
        result = run_case(case_name)
        print(f"\n=== {case_name} ===")
        print(json.dumps(result, ensure_ascii=False, indent=2))
