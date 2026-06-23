"""Day 10: write outbox events instead of directly sending external notifications.

大白话版本：

- Day 9 学到：如果 interrupt 前必须创建审批单，就用幂等键防重复。
- Day 10 学到：流程里不要直接发短信 / 发 MQ / 发通知。
- 更稳的做法是：先写 outbox event，再由 dispatcher 发送。

为什么？

直接发送的问题：

    业务状态还没完全落稳，通知已经发出去了。
    或者通知发出去了，后面流程崩了。
    或者重试时通知又发了一遍。

Outbox 的做法：

    业务流程只负责登记一条“待发送事件”。
    发送器 dispatcher 负责真正发送。
    发送成功后，把事件标记成 sent。

这就是把“业务状态变化”和“外部通知发送”解耦。
软件系统终于稍微像个系统，而不是一串紧张的 if else 在裸奔。
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
    NormalizedFields,
    RawFields,
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
OutboxStatus = Literal["pending", "sent"]

# 模拟外部审批系统。
EXTERNAL_REVIEW_REQUESTS: dict[str, dict[str, Any]] = {}

# 模拟 outbox 表。
# key = event_id
# value = event 内容 + 状态
OUTBOX_EVENTS: dict[str, dict[str, Any]] = {}

# 模拟真正发出去的外部消息。
# 真实系统里这可能是短信、邮件、Webhook、MQ。
SENT_MESSAGES: list[dict[str, Any]] = []

# 调用流水，方便教学观察。
EXTERNAL_CALL_LOG: list[str] = []


class AuditState(TypedDict, total=False):
    """Day 10 的 State。

    新增：
    - outbox_event_id：本次审批结论对应的 outbox 事件 ID。
    """

    task_id: str
    company: str
    raw_fields: RawFields
    normalized_fields: NormalizedFields
    audit_errors: Annotated[list[str], add]
    warnings: Annotated[list[str], add]
    audit_events: Annotated[list[str], add]
    audit_status: AuditStatus
    review_request_id: str
    outbox_event_id: str
    review_decision: ReviewDecision
    review_note: str
    delivery_message: str
    workflow_path: Annotated[list[str], add]


def reset_external_systems() -> None:
    """清空模拟外部系统，避免测试互相污染。"""

    EXTERNAL_REVIEW_REQUESTS.clear()
    OUTBOX_EVENTS.clear()
    SENT_MESSAGES.clear()
    EXTERNAL_CALL_LOG.clear()


def make_review_request_id(state: AuditState) -> str:
    """稳定生成审批单幂等键。"""

    return f"{state['task_id']}:human_review:round1"


def create_review_request_once(state: AuditState) -> tuple[str, bool]:
    """创建待审批单，但用 review_request_id 防重复。"""

    review_request_id = make_review_request_id(state)
    EXTERNAL_CALL_LOG.append(f"try_create_review:{review_request_id}")

    if review_request_id in EXTERNAL_REVIEW_REQUESTS:
        EXTERNAL_CALL_LOG.append(f"review_duplicate_skipped:{review_request_id}")
        return review_request_id, False

    EXTERNAL_REVIEW_REQUESTS[review_request_id] = {
        "review_request_id": review_request_id,
        "task_id": state["task_id"],
        "company": state["company"],
        "profit_margin": state.get("normalized_fields", {}).get("profit_margin"),
        "status": "waiting_for_human",
    }
    EXTERNAL_CALL_LOG.append(f"review_created:{review_request_id}")
    return review_request_id, True


def make_outbox_event_id(review_request_id: str, decision: ReviewDecision) -> str:
    """稳定生成 outbox 事件 ID。

    一个审批单 + 一个审批决定，只应该产生一条对应通知事件。
    这仍然是幂等思维：事件也要有稳定 key。
    """

    return f"{review_request_id}:decision:{decision}"


def update_review_request_decision(
    review_request_id: str,
    decision: ReviewDecision,
    note: str,
) -> None:
    """把人工复核决定写回审批单。"""

    request = EXTERNAL_REVIEW_REQUESTS.setdefault(
        review_request_id,
        {
            "review_request_id": review_request_id,
            "status": "created_during_resume",
        },
    )
    request["status"] = decision
    request["note"] = note
    EXTERNAL_CALL_LOG.append(f"decision_saved:{review_request_id}:{decision}")


def enqueue_outbox_event_once(
    review_request_id: str,
    decision: ReviewDecision,
    note: str,
) -> tuple[str, bool]:
    """登记一条 outbox 事件，但不直接发送。

    返回：
    - event_id
    - created：这次是否真的创建了新事件

    这里故意不调用 send_xxx。
    graph 只负责把“要通知外部世界”这件事写进 outbox。
    真发送交给 dispatch_outbox_events()。
    """

    event_id = make_outbox_event_id(review_request_id, decision)
    EXTERNAL_CALL_LOG.append(f"try_enqueue_outbox:{event_id}")

    if event_id in OUTBOX_EVENTS:
        EXTERNAL_CALL_LOG.append(f"outbox_duplicate_skipped:{event_id}")
        return event_id, False

    OUTBOX_EVENTS[event_id] = {
        "event_id": event_id,
        "type": "review.decision_saved",
        "status": "pending",
        "review_request_id": review_request_id,
        "decision": decision,
        "note": note,
    }
    EXTERNAL_CALL_LOG.append(f"outbox_enqueued:{event_id}")
    return event_id, True


def dispatch_outbox_events() -> list[str]:
    """发送所有 pending 的 outbox 事件。

    真实系统里这通常是后台 worker / 定时任务 / 消费者。
    这里用一个函数模拟。

    重要点：
    - pending 才发送。
    - 发送后标记 sent。
    - 再跑一次 dispatcher 不会重复发送已 sent 的事件。
    """

    sent_event_ids: list[str] = []

    for event_id, event in OUTBOX_EVENTS.items():
        if event.get("status") != "pending":
            continue

        SENT_MESSAGES.append(
            {
                "event_id": event_id,
                "type": event["type"],
                "review_request_id": event["review_request_id"],
                "decision": event["decision"],
            }
        )
        event["status"] = "sent"
        EXTERNAL_CALL_LOG.append(f"outbox_sent:{event_id}")
        sent_event_ids.append(event_id)

    return sent_event_ids


def _review_payload(state: AuditState, review_request_id: str, created: bool) -> dict[str, Any]:
    """准备给人类看的复核材料。"""

    fields = state.get("normalized_fields", {})
    return {
        "question": "Low profit margin requires human review. Approve this audit result?",
        "task_id": state.get("task_id"),
        "company": state.get("company"),
        "profit_margin": fields.get("profit_margin"),
        "warnings": state.get("warnings", []),
        "review_request_id": review_request_id,
        "review_request_created_now": created,
        "allowed_decisions": ["approved", "rejected"],
    }


def _parse_resume_decision(decision: Any) -> tuple[ReviewDecision, str]:
    """解析 Command(resume=...) 传回来的人工决定。"""

    if isinstance(decision, dict):
        raw_decision = decision.get("decision", "rejected")
        review_note = decision.get("note", "human review completed")
    else:
        raw_decision = str(decision)
        review_note = "human review completed"

    review_decision: ReviewDecision = "approved" if raw_decision == "approved" else "rejected"
    return review_decision, review_note


def human_review_with_outbox(state: AuditState) -> AuditState:
    """人工复核节点：创建审批单，暂停，恢复后写审批结果和 outbox。

    源码细讲：

    1. create_review_request_once(state)
       interrupt 前创建待审批单。
       用幂等键防止 resume 重跑时重复创建。

    2. decision = interrupt(payload)
       暂停等人类。

    3. update_review_request_decision(...)
       恢复后更新审批单本身。

    4. enqueue_outbox_event_once(...)
       不直接发通知，只登记 outbox 事件。
       真正发送交给 dispatch_outbox_events()。
    """

    review_request_id, created = create_review_request_once(state)
    payload = _review_payload(state, review_request_id, created)

    decision = interrupt(payload)

    review_decision, review_note = _parse_resume_decision(decision)
    update_review_request_decision(review_request_id, review_decision, review_note)
    outbox_event_id, _ = enqueue_outbox_event_once(review_request_id, review_decision, review_note)

    if review_decision == "approved":
        return {
            "audit_status": "passed",
            "review_request_id": review_request_id,
            "outbox_event_id": outbox_event_id,
            "review_decision": "approved",
            "review_note": review_note,
            "workflow_path": ["human_review_with_outbox"],
            "audit_events": ["human_review_with_outbox: approved and outbox event recorded"],
        }

    return {
        "audit_status": "failed",
        "review_request_id": review_request_id,
        "outbox_event_id": outbox_event_id,
        "review_decision": "rejected",
        "review_note": review_note,
        "audit_errors": ["human reviewer rejected low profit margin"],
        "workflow_path": ["human_review_with_outbox"],
        "audit_events": ["human_review_with_outbox: rejected and outbox event recorded"],
    }


def route_after_human_review(state: AuditState) -> ReviewRoute:
    """人工复核后的分岔路口。"""

    if state.get("review_decision") == "approved":
        return "delivery"
    return "error_report"


def build_graph(checkpointer: InMemorySaver | None = None):
    """创建 Day 10 outbox 图。"""

    checkpointer = checkpointer or InMemorySaver()

    graph = StateGraph(AuditState)

    graph.add_node("intake", intake)
    graph.add_node("normalize", normalize)
    graph.add_node("audit", audit)
    graph.add_node("human_review", human_review_with_outbox)
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


def initial_state(task_id: str = "task-day10-001") -> AuditState:
    """生成一个一定进入人工复核的初始 State。"""

    return {
        "task_id": task_id,
        "company": "LowProfitCorp",
        "raw_fields": {"revenue": "2000", "net_profit": "60"},
        "audit_errors": [],
        "warnings": [],
        "audit_events": [],
        "workflow_path": [],
    }


def thread_config(thread_id: str) -> dict[str, dict[str, str]]:
    """生成存档槽位配置。"""

    return {"configurable": {"thread_id": thread_id}}


def run_review_flow(
    decision: ReviewDecision,
    task_id: str = "task-day10-001",
    thread_id: str = "day10-thread-001",
    dispatch_after_graph: bool = False,
) -> dict[str, Any]:
    """运行一次人工复核流程，可选择是否随后 dispatch outbox。"""

    reset_external_systems()

    app = build_graph()
    config = thread_config(thread_id)

    paused = app.invoke(initial_state(task_id), config)
    final = app.invoke(
        Command(
            resume={
                "decision": decision,
                "note": f"Reviewer {decision} this low margin case.",
            }
        ),
        config,
    )

    dispatched_event_ids: list[str] = []
    if dispatch_after_graph:
        dispatched_event_ids = dispatch_outbox_events()

    return {
        "decision": decision,
        "paused_has_interrupt": "__interrupt__" in paused,
        "external_review_requests": dict(EXTERNAL_REVIEW_REQUESTS),
        "outbox_events": dict(OUTBOX_EVENTS),
        "sent_messages": list(SENT_MESSAGES),
        "dispatched_event_ids": dispatched_event_ids,
        "external_call_log": list(EXTERNAL_CALL_LOG),
        "final": final,
    }


def run_demo() -> dict[str, Any]:
    """给命令行看的 demo。"""

    without_dispatch = run_review_flow("approved", dispatch_after_graph=False)
    with_dispatch = run_review_flow(
        "approved",
        task_id="task-day10-002",
        thread_id="day10-thread-002",
        dispatch_after_graph=True,
    )

    return {
        "without_dispatch": without_dispatch,
        "with_dispatch": with_dispatch,
    }


if __name__ == "__main__":
    print(json.dumps(run_demo(), ensure_ascii=False, indent=2, default=str))
