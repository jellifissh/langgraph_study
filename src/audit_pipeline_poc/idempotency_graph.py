"""Day 9: protect pre-interrupt side effects with idempotency keys.

大白话版本：

- Day 8 学到：interrupt 前的外部副作用可能执行两次。
- Day 9 学到：有些外部写入必须放在 interrupt 前，那就要用幂等键保护。

幂等键 idempotency key：

同一件业务动作，生成同一个唯一 key。
外部系统看到这个 key 已经处理过，就不要重复创建。

这里模拟一个真实场景：

- audit 判断利润率低，需要人工复核。
- human_review 节点在 interrupt 前创建一条“待审批单”。
- 因为 resume 时 human_review 会从头再执行一次，所以创建审批单的代码会被调用两次。
- 但是它们使用同一个 review_request_id。
- 外部系统只创建一条审批单，第二次识别为重复，直接跳过。

这就是：可以重复调用，但结果只发生一次。
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

# 模拟外部审批系统。
# key = review_request_id
# value = 审批单内容
EXTERNAL_REVIEW_REQUESTS: dict[str, dict[str, Any]] = {}

# 模拟外部系统调用日志。
# 注意：调用日志会记录“尝试创建”和“跳过重复”，但真正的审批单只会有一条。
EXTERNAL_CALL_LOG: list[str] = []


class AuditState(TypedDict, total=False):
    """Day 9 的 State。

    新增：
    - task_id：某次审计任务的业务 ID。
    - review_request_id：幂等键，用来保护外部审批单创建。
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
    review_decision: ReviewDecision
    review_note: str
    delivery_message: str
    workflow_path: Annotated[list[str], add]


def reset_external_systems() -> None:
    """清空模拟外部系统，避免测试互相污染。"""

    EXTERNAL_REVIEW_REQUESTS.clear()
    EXTERNAL_CALL_LOG.clear()


def make_review_request_id(state: AuditState) -> str:
    """生成幂等键。

    源码细讲：

    幂等键必须稳定。
    同一个 task_id、同一个节点、同一轮 review，应该生成同一个 key。

    这里先用最简单的：

        task_id + human_review + round1

    真实生产里可以更复杂，比如：

        report_task_id + source_file_sha256 + node_name + review_round

    但别用随机数。随机数每次都不一样，那叫反幂等。人类有时候真的会这么写，
    然后惊讶地发现“为什么去重没生效”。嗯，为什么呢。
    """

    return f"{state['task_id']}:human_review:round1"


def create_review_request_once(state: AuditState) -> tuple[str, bool]:
    """在外部审批系统里创建待审批单，但用幂等键保护。

    返回：
    - review_request_id
    - created：这次是否真的创建了新审批单

    第一次调用：
    - key 不存在
    - 创建审批单
    - created=True

    第二次调用：
    - key 已存在
    - 不重复创建
    - created=False
    """

    review_request_id = make_review_request_id(state)
    EXTERNAL_CALL_LOG.append(f"try_create:{review_request_id}")

    if review_request_id in EXTERNAL_REVIEW_REQUESTS:
        EXTERNAL_CALL_LOG.append(f"duplicate_skipped:{review_request_id}")
        return review_request_id, False

    EXTERNAL_REVIEW_REQUESTS[review_request_id] = {
        "review_request_id": review_request_id,
        "task_id": state["task_id"],
        "company": state["company"],
        "profit_margin": state.get("normalized_fields", {}).get("profit_margin"),
        "status": "waiting_for_human",
    }
    EXTERNAL_CALL_LOG.append(f"created:{review_request_id}")
    return review_request_id, True


def update_review_request_decision(
    review_request_id: str,
    decision: ReviewDecision,
    note: str,
) -> None:
    """把人工复核决定写回外部审批系统。

    这里也故意做成幂等：同一个 review_request_id 最后只更新同一条记录。
    """

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


def human_review_with_idempotency(state: AuditState) -> AuditState:
    """在 interrupt 前创建审批单，但使用幂等键防止重复创建。

    源码细讲：

    1. create_review_request_once(state)
       这一步在 interrupt 前。
       按 Day 8 的规则，它会在 resume 时再次被调用。

    2. 为什么这次可以接受？
       因为它有幂等键 review_request_id。
       第二次调用时，外部系统发现这个 key 已经创建过，就不会再创建第二条审批单。

    3. decision = interrupt(payload)
       第一次暂停，恢复时返回 Command(resume=...) 的值。

    4. update_review_request_decision(...)
       resume 后保存人工复核结果。
    """

    review_request_id, created = create_review_request_once(state)
    payload = _review_payload(state, review_request_id, created)

    decision = interrupt(payload)

    review_decision, review_note = _parse_resume_decision(decision)
    update_review_request_decision(review_request_id, review_decision, review_note)

    if review_decision == "approved":
        return {
            "audit_status": "passed",
            "review_request_id": review_request_id,
            "review_decision": "approved",
            "review_note": review_note,
            "workflow_path": ["human_review_with_idempotency"],
            "audit_events": ["human_review_with_idempotency: approved by reviewer"],
        }

    return {
        "audit_status": "failed",
        "review_request_id": review_request_id,
        "review_decision": "rejected",
        "review_note": review_note,
        "audit_errors": ["human reviewer rejected low profit margin"],
        "workflow_path": ["human_review_with_idempotency"],
        "audit_events": ["human_review_with_idempotency: rejected by reviewer"],
    }


def route_after_human_review(state: AuditState) -> ReviewRoute:
    """人工复核后的分岔路口。"""

    if state.get("review_decision") == "approved":
        return "delivery"
    return "error_report"


def build_graph(checkpointer: InMemorySaver | None = None):
    """创建 Day 9 幂等保护图。"""

    checkpointer = checkpointer or InMemorySaver()

    graph = StateGraph(AuditState)

    graph.add_node("intake", intake)
    graph.add_node("normalize", normalize)
    graph.add_node("audit", audit)
    graph.add_node("human_review", human_review_with_idempotency)
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


def initial_state(task_id: str = "task-day9-001") -> AuditState:
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
    task_id: str = "task-day9-001",
    thread_id: str = "day9-thread-001",
) -> dict[str, Any]:
    """运行一次需要人工复核的流程。"""

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

    return {
        "decision": decision,
        "paused_has_interrupt": "__interrupt__" in paused,
        "external_review_requests": dict(EXTERNAL_REVIEW_REQUESTS),
        "external_call_log": list(EXTERNAL_CALL_LOG),
        "final": final,
    }


def run_demo() -> dict[str, Any]:
    """给命令行看的 demo。"""

    approved_report = run_review_flow("approved")
    rejected_report = run_review_flow(
        "rejected",
        task_id="task-day9-002",
        thread_id="day9-thread-002",
    )

    return {
        "approved_report": approved_report,
        "rejected_report": rejected_report,
    }


if __name__ == "__main__":
    print(json.dumps(run_demo(), ensure_ascii=False, indent=2, default=str))
