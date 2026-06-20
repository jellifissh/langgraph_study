"""Day 2: conditional routing for a tiny audit workflow.

大白话版本：

- Node = 点 / 工位：负责做一件具体的事。
- Edge = 线 / 路：固定下一步去哪。
- Conditional Edge = 分岔路口：根据 State 里的结果决定下一步去哪。

今天的流程：

START -> intake -> audit -> route_by_audit_result
                           ├─ passed      -> delivery -> END
                           ├─ need_review -> review -> delivery -> END
                           └─ failed      -> error_report -> END
"""

from __future__ import annotations

import json
from typing import Literal

from typing_extensions import TypedDict

from langgraph.graph import END, START, StateGraph


class AuditState(TypedDict, total=False):
    """State = 账本：记录流程里后续还要用的关键信息。"""

    company: str
    revenue: float
    net_profit: float
    profit_margin: float
    audit_status: str
    review_note: str
    error_message: str
    delivery_message: str
    workflow_path: list[str]


def _append_path(state: AuditState, step: str) -> list[str]:
    """把当前节点名记到账本里，方便我们观察流程到底走了哪条路。"""

    return [*state.get("workflow_path", []), step]


def intake(state: AuditState) -> AuditState:
    """intake 点：检查最基本的输入字段，不负责审计判断。"""

    required_fields = ["company", "revenue", "net_profit"]
    missing_fields = [field for field in required_fields if field not in state]

    if missing_fields:
        raise ValueError(f"Missing required fields: {missing_fields}")

    return {
        "company": str(state["company"]),
        "revenue": float(state["revenue"]),
        "net_profit": float(state["net_profit"]),
        "workflow_path": _append_path(state, "intake"),
    }


def audit(state: AuditState) -> AuditState:
    """audit 点：计算利润率，并只负责写下审计结论。"""

    revenue = state["revenue"]
    net_profit = state["net_profit"]

    if revenue <= 0:
        return {
            "profit_margin": 0.0,
            "audit_status": "failed",
            "error_message": "revenue must be greater than 0",
            "workflow_path": _append_path(state, "audit"),
        }

    profit_margin = net_profit / revenue

    if profit_margin < 0:
        audit_status = "failed"
    elif profit_margin < 0.05:
        audit_status = "need_review"
    else:
        audit_status = "passed"

    return {
        "profit_margin": round(profit_margin, 4),
        "audit_status": audit_status,
        "workflow_path": _append_path(state, "audit"),
    }


def route_by_audit_result(
    state: AuditState,
) -> Literal["delivery", "review", "error_report"]:
    """分岔路口：根据 audit_status 决定下一步走哪条线。

    注意：route 函数只负责决定路线，不负责干业务活。
    这里不要计算利润率，也不要生成报告。
    """

    status = state["audit_status"]

    if status == "passed":
        return "delivery"
    if status == "need_review":
        return "review"
    return "error_report"


def review(state: AuditState) -> AuditState:
    """review 点：模拟人工复核。今天先不做 interrupt，只写一条复核说明。"""

    note = (
        "manual review required: profit margin is low but not negative; "
        "keep status as need_review"
    )

    return {
        "review_note": note,
        "workflow_path": _append_path(state, "review"),
    }


def delivery(state: AuditState) -> AuditState:
    """delivery 点：整理最终交付信息。"""

    message = (
        f"{state['company']} audit {state['audit_status']}: "
        f"profit margin = {state['profit_margin']:.2%}"
    )

    return {
        "delivery_message": message,
        "workflow_path": _append_path(state, "delivery"),
    }


def error_report(state: AuditState) -> AuditState:
    """error_report 点：整理失败信息，失败分支到这里结束。"""

    message = f"{state['company']} audit failed: {state.get('error_message', 'unknown error')}"

    return {
        "delivery_message": message,
        "workflow_path": _append_path(state, "error_report"),
    }


def build_graph():
    """创建带分岔路口的流程地图。"""

    graph = StateGraph(AuditState)

    graph.add_node("intake", intake)
    graph.add_node("audit", audit)
    graph.add_node("review", review)
    graph.add_node("delivery", delivery)
    graph.add_node("error_report", error_report)

    graph.add_edge(START, "intake")
    graph.add_edge("intake", "audit")

    # add_conditional_edges = 加分岔路口。
    # audit 做完后，不再固定去 delivery，而是交给 route 函数决定下一站。
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
    """按案例名跑一次流程，方便你观察不同输入会走不同路线。"""

    cases: dict[str, AuditState] = {
        "passed": {
            "company": "DemoCorp",
            "revenue": 1000,
            "net_profit": 120,
        },
        "need_review": {
            "company": "LowProfitCorp",
            "revenue": 2000,
            "net_profit": 60,
        },
        "failed": {
            "company": "ZeroRevenueCorp",
            "revenue": 0,
            "net_profit": 10,
        },
    }

    if case_name not in cases:
        raise ValueError(f"Unknown case: {case_name}. Expected one of: {sorted(cases)}")

    app = build_graph()
    return app.invoke(cases[case_name])


if __name__ == "__main__":
    for case_name in ["passed", "need_review", "failed"]:
        result = run_case(case_name)
        print(f"\n=== {case_name} ===")
        print(json.dumps(result, ensure_ascii=False, indent=2))
