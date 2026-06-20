"""Day 7: pause and resume an audit workflow with interrupt.

大白话版本：

- Checkpointer = 存档系统。
- Interrupt = 真正的暂停点。
- Command(resume=...) = 继续游戏时给回去的人类输入。

今天我们把 Day 5 的 `review` 节点升级成真正的人类复核节点：

1. 如果 audit 结果是 passed，直接 delivery。
2. 如果 audit 结果是 failed，直接 error_report。
3. 如果 audit 结果是 need_review，进入 human_review。
4. human_review 内部调用 interrupt(...) 暂停流程。
5. 外部用 Command(resume={...}) 提交人工复核意见。
6. 如果 approve，进入 delivery。
7. 如果 reject，进入 error_report。
"""

from __future__ import annotations

import json
from operator import add
from typing import Annotated, Any, Literal

from typing_extensions import TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from audit_pipeline_poc.reducer_graph import (
    RawFields,
    NormalizedFields,
    audit,
    delivery,
    error_report,
    intake,
    normalize,
    route_by_audit_result,
)

AuditStatus = Literal["passed", "need_review", "failed"]
ReviewDecision = Literal["approved", "rejected"]
ReviewRoute = Literal["delivery", "error_report"]


class AuditState(TypedDict, total=False):
    """Day 7 的 State。

    和 Day 5 相比，新增：
    - review_decision：人工复核决定，approved / rejected。
    - review_note：人工复核说明。

    注意：
    workflow_path / audit_events / audit_errors / warnings 仍然使用 reducer 追加。
    """

    company: str
    raw_fields: RawFields
    normalized_fields: NormalizedFields
    audit_errors: Annotated[list[str], add]
    warnings: Annotated[list[str], add]
    audit_events: Annotated[list[str], add]
    audit_status: AuditStatus
    review_decision: ReviewDecision
    review_note: str
    delivery_message: str
    workflow_path: Annotated[list[str], add]


def human_review(state: AuditState) -> AuditState:
    """真正会暂停的人工复核节点。

    源码细讲：

    1. payload 是给外部人类看的复核信息。
       它必须是 JSON-serializable，也就是字符串、数字、list、dict 这类东西。
       别把数据库连接、Python 对象、函数塞进去。那不是 payload，那是召唤异常。

    2. decision = interrupt(payload)
       这一行第一次执行时不会继续往下跑，而是暂停。
       LangGraph 会保存当前 State，并把 payload 交给调用方。

    3. 外部调用 Command(resume={...}) 后，这个节点会从头重新执行。
       但这一次 interrupt(payload) 不会再暂停，而是返回 resume 传进来的值。

    4. 所以 decision 就是人类复核意见。
       我们根据 decision 决定是 approved 还是 rejected。
    """

    fields = state.get("normalized_fields", {})
    profit_margin = fields.get("profit_margin")

    payload = {
        "question": "Low profit margin requires human review. Approve this audit result?",
        "company": state.get("company"),
        "profit_margin": profit_margin,
        "warnings": state.get("warnings", []),
        "allowed_decisions": ["approved", "rejected"],
        "example_resume_payload": {
            "decision": "approved",
            "note": "Reviewed low margin and approved for delivery.",
        },
    }

    decision = interrupt(payload)

    if isinstance(decision, dict):
        review_decision = decision.get("decision", "rejected")
        review_note = decision.get("note", "human review completed")
    else:
        review_decision = str(decision)
        review_note = "human review completed"

    if review_decision == "approved":
        return {
            "audit_status": "passed",
            "review_decision": "approved",
            "review_note": review_note,
            "workflow_path": ["human_review"],
            "audit_events": ["human_review: approved by reviewer"],
        }

    return {
        "audit_status": "failed",
        "review_decision": "rejected",
        "review_note": review_note,
        "audit_errors": ["human reviewer rejected low profit margin"],
        "workflow_path": ["human_review"],
        "audit_events": ["human_review: rejected by reviewer"],
    }


def route_after_human_review(state: AuditState) -> ReviewRoute:
    """人工复核后的第二个分岔路口。

    approve -> delivery
    reject  -> error_report
    """

    if state.get("review_decision") == "approved":
        return "delivery"
    return "error_report"


def build_graph(checkpointer: InMemorySaver | None = None):
    """创建带 interrupt 的人工复核图。

    关键点：
    interrupt 必须配合 checkpointer 和 thread_id。
    没有 checkpointer，就像游戏没有存档却想暂停恢复，属于自欺欺人型架构。
    """

    checkpointer = checkpointer or InMemorySaver()

    graph = StateGraph(AuditState)

    graph.add_node("intake", intake)
    graph.add_node("normalize", normalize)
    graph.add_node("audit", audit)
    graph.add_node("human_review", human_review)
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
            "review": "human_review",
            "error_report": "error_report",
        },
    )
    graph.add_conditional_edges(
        "human_review",
        route_after_human_review,
        {
            "delivery": "delivery",
            "error_report": "error_report",
        },
    )
    graph.add_edge("delivery", END)
    graph.add_edge("error_report", END)

    return graph.compile(checkpointer=checkpointer)


def initial_state(case_name: str) -> AuditState:
    """按案例名生成初始 State。

    Day 7 最重要的案例是 need_review，因为它会触发 interrupt。
    passed / failed_missing 用来证明不是所有路线都会暂停。
    """

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
    }

    if case_name not in cases:
        raise ValueError(f"Unknown case: {case_name}. Expected one of: {sorted(cases)}")

    return {
        **cases[case_name],
        "audit_errors": [],
        "warnings": [],
        "audit_events": [],
        "workflow_path": [],
    }


def thread_config(thread_id: str) -> dict[str, dict[str, str]]:
    """生成存档槽位配置。"""

    return {"configurable": {"thread_id": thread_id}}


def extract_interrupt_payload(paused_result: dict[str, Any]) -> dict[str, Any]:
    """从 invoke 返回值里取出 interrupt payload。

    默认 invoke API 会把 interrupt 信息放在 `__interrupt__` 下面。
    这里做一个小函数，是为了让 demo 和测试都不用反复写下标访问。
    """

    interrupts = paused_result.get("__interrupt__", ())
    if not interrupts:
        raise ValueError("Expected an interrupt, but graph did not pause.")
    return interrupts[0].value


def run_need_review_until_interrupt(thread_id: str = "day7-need-review") -> dict[str, Any]:
    """运行 need_review 案例，停在 human_review。"""

    app = build_graph()
    config = thread_config(thread_id)
    paused = app.invoke(initial_state("need_review"), config)

    return {
        "thread_id": thread_id,
        "paused": paused,
        "interrupt_payload": extract_interrupt_payload(paused),
        "latest_state": dict(app.get_state(config).values),
    }


def run_need_review_with_human_decision(
    decision: ReviewDecision,
    thread_id: str = "day7-need-review-decision",
    note: str | None = None,
) -> dict[str, Any]:
    """运行 need_review 案例，先暂停，再用人工决定恢复。"""

    app = build_graph()
    config = thread_config(thread_id)

    paused = app.invoke(initial_state("need_review"), config)
    interrupt_payload = extract_interrupt_payload(paused)

    final = app.invoke(
        Command(
            resume={
                "decision": decision,
                "note": note or f"Human reviewer {decision} this audit result.",
            }
        ),
        config,
    )

    return {
        "thread_id": thread_id,
        "interrupt_payload": interrupt_payload,
        "final": final,
        "latest_state": dict(app.get_state(config).values),
    }


def run_demo() -> dict[str, Any]:
    """给命令行看的 demo：展示暂停、批准恢复、拒绝恢复三件事。"""

    paused_report = run_need_review_until_interrupt("day7-demo-paused")
    approved_report = run_need_review_with_human_decision(
        "approved",
        thread_id="day7-demo-approved",
        note="Reviewer approved low margin after checking context.",
    )
    rejected_report = run_need_review_with_human_decision(
        "rejected",
        thread_id="day7-demo-rejected",
        note="Reviewer rejected because margin is too low.",
    )

    return {
        "paused_report": paused_report,
        "approved_report": approved_report,
        "rejected_report": rejected_report,
    }


if __name__ == "__main__":
    print(json.dumps(run_demo(), ensure_ascii=False, indent=2, default=str))
