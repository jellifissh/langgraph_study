"""Day 1: the smallest useful LangGraph audit workflow.

大白话版本：

- State = 账本：整条流程共用的一份任务记录。
- Node = 点 / 工位：一个处理步骤。
- Edge = 线 / 路：处理完一个点后去哪里。
- Graph = 流程地图：把点和线连起来。

今天的流程：

START -> intake -> audit -> delivery -> END
"""

from __future__ import annotations

import json
from typing_extensions import TypedDict

from langgraph.graph import END, START, StateGraph


class AuditState(TypedDict, total=False):
    """这就是 State：整条审计流程共用的账本。"""

    company: str
    revenue: float
    net_profit: float
    profit_margin: float
    audit_status: str
    delivery_message: str


def intake(state: AuditState) -> AuditState:
    """intake 节点：接收并检查最基本的输入字段。"""

    required_fields = ["company", "revenue", "net_profit"]
    missing_fields = [field for field in required_fields if field not in state]

    if missing_fields:
        raise ValueError(f"Missing required fields: {missing_fields}")

    # 返回值会被 LangGraph 合并回 State，相当于往账本里补记录。
    return {
        "company": str(state["company"]),
        "revenue": float(state["revenue"]),
        "net_profit": float(state["net_profit"]),
    }


def audit(state: AuditState) -> AuditState:
    """audit 节点：做最小审计，计算利润率并给出审计状态。"""

    revenue = state["revenue"]
    net_profit = state["net_profit"]

    if revenue <= 0:
        return {
            "profit_margin": 0.0,
            "audit_status": "failed",
        }

    profit_margin = net_profit / revenue

    # 第 1 天先不做分支，只给出一个状态。分支第 2 阶段再学。
    audit_status = "passed" if profit_margin >= 0 else "failed"

    return {
        "profit_margin": round(profit_margin, 4),
        "audit_status": audit_status,
    }


def delivery(state: AuditState) -> AuditState:
    """delivery 节点：整理最终输出信息。"""

    message = (
        f"{state['company']} audit {state['audit_status']}: "
        f"profit margin = {state['profit_margin']:.2%}"
    )

    return {
        "delivery_message": message,
    }


def build_graph():
    """创建流程地图：把点和线连起来，然后 compile 成可运行对象。"""

    graph = StateGraph(AuditState)

    # add_node = 加点，也就是加一个处理工位。
    graph.add_node("intake", intake)
    graph.add_node("audit", audit)
    graph.add_node("delivery", delivery)

    # add_edge = 加线，也就是规定每一步做完后去哪。
    graph.add_edge(START, "intake")
    graph.add_edge("intake", "audit")
    graph.add_edge("audit", "delivery")
    graph.add_edge("delivery", END)

    # compile = 装配机器，把流程地图变成能运行的图。
    return graph.compile()


def run_demo() -> AuditState:
    """跑一次 demo，返回最终 State。"""

    app = build_graph()

    initial_state: AuditState = {
        "company": "DemoCorp",
        "revenue": 1000,
        "net_profit": 120,
    }

    # invoke = 跑一次完整流程。
    return app.invoke(initial_state)


if __name__ == "__main__":
    result = run_demo()
    print(json.dumps(result, ensure_ascii=False, indent=2))
