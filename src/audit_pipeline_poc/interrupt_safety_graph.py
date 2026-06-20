"""Day 8: understand side-effect safety around interrupt.

大白话版本：

- Day 7 学会了暂停和恢复。
- Day 8 学一个真实工程坑：interrupt 恢复时，节点会从头重新执行。
- 所以写在 interrupt(...) 之前的外部副作用，可能执行两次。

这里用一个全局 list 模拟外部系统：

- EXTERNAL_REVIEW_LOG = 外部日志 / 数据库 / 短信系统 / 消息队列。
- unsafe_human_review 会在 interrupt 前写外部日志，所以恢复后会写两次。
- safe_human_review 只在 resume 之后写外部日志，所以只写一次。

注意：真实生产不要用全局 list 存业务数据。这里是教学用的外部副作用模拟器。
人类已经发明了足够多的坏数据库设计，没必要再加一个全局 list 宇宙。
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
ReviewMode = Literal["safe", "unsafe"]

# 用来模拟外部副作用：数据库写入、消息队列、短信、邮件、审计日志等。
# 测试时会主动清空它。
EXTERNAL_REVIEW_LOG: list[str] = []


class AuditState(TypedDict, total=False):
    """Day 8 的 State。

    和 Day 7 很像，但我们额外关注副作用安全。
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


def reset_external_review_log() -> None:
    """清空模拟外部日志，保证 demo / test 不互相污染。"""

    EXTERNAL_REVIEW_LOG.clear()


def _review_payload(state: AuditState) -> dict[str, Any]:
    """准备给人类看的复核材料。

    这个函数只做纯计算，不写外部系统。
    纯计算放在 interrupt 前面通常没问题。
    真正危险的是：发消息、写数据库、扣库存、调支付、发邮件这类外部副作用。
    """

    fields = state.get("normalized_fields", {})
    return {
        "question": "Low profit margin requires human review. Approve this audit result?",
        "company": state.get("company"),
        "profit_margin": fields.get("profit_margin"),
        "warnings": state.get("warnings", []),
        "allowed_decisions": ["approved", "rejected"],
    }


def _parse_resume_decision(decision: Any) -> tuple[ReviewDecision, str]:
    """把 Command(resume=...) 传回来的值整理成 decision + note。"""

    if isinstance(decision, dict):
        raw_decision = decision.get("decision", "rejected")
        review_note = decision.get("note", "human review completed")
    else:
        raw_decision = str(decision)
        review_note = "human review completed"

    review_decision: ReviewDecision = "approved" if raw_decision == "approved" else "rejected"
    return review_decision, review_note


def _review_result_update(review_decision: ReviewDecision, review_note: str, mode: ReviewMode) -> AuditState:
    """根据人工决定返回 State 更新。

    mode 用来标记 safe / unsafe，方便你在输出里看清楚是哪条示例路径。
    """

    if review_decision == "approved":
        return {
            "audit_status": "passed",
            "review_decision": "approved",
            "review_note": review_note,
            "workflow_path": [f"{mode}_human_review"],
            "audit_events": [f"{mode}_human_review: approved by reviewer"],
        }

    return {
        "audit_status": "failed",
        "review_decision": "rejected",
        "review_note": review_note,
        "audit_errors": [f"{mode} human reviewer rejected low profit margin"],
        "workflow_path": [f"{mode}_human_review"],
        "audit_events": [f"{mode}_human_review: rejected by reviewer"],
    }


def unsafe_human_review(state: AuditState) -> AuditState:
    """错误示范：interrupt 前写外部系统。

    源码细讲：

    1. EXTERNAL_REVIEW_LOG.append("unsafe: before interrupt")
       这是外部副作用。你可以把它想象成：
       - 发了一条短信
       - 写了一条数据库记录
       - 发了一条 MQ 消息
       - 调了一个扣费接口

    2. decision = interrupt(payload)
       第一次执行到这里会暂停。

    3. 恢复时，这个节点会从头重新执行。
       于是 append("unsafe: before interrupt") 会再执行一次。

    结果：同一件事被外部系统记录了两次。
    这就是人类项目里“为什么通知发了两遍”的一种优雅灾难。
    """

    payload = _review_payload(state)
    EXTERNAL_REVIEW_LOG.append("unsafe: before interrupt")

    decision = interrupt(payload)

    review_decision, review_note = _parse_resume_decision(decision)
    EXTERNAL_REVIEW_LOG.append(f"unsafe: after resume {review_decision}")

    return _review_result_update(review_decision, review_note, "unsafe")


def safe_human_review(state: AuditState) -> AuditState:
    """正确示范：interrupt 前只准备 payload，不做外部副作用。

    源码细讲：

    1. payload = _review_payload(state)
       只是从 State 里整理展示信息，属于纯计算。

    2. decision = interrupt(payload)
       第一次执行暂停，恢复时返回 Command(resume=...) 里的值。

    3. EXTERNAL_REVIEW_LOG.append(...)
       外部副作用放在 resume 之后。
       这样它只会在真正收到人工决定后执行一次。

    这就是今天的核心规则：
    interrupt 前可以做纯计算，别做不可重复的外部副作用。
    """

    payload = _review_payload(state)
    decision = interrupt(payload)

    review_decision, review_note = _parse_resume_decision(decision)
    EXTERNAL_REVIEW_LOG.append(f"safe: after resume {review_decision}")

    return _review_result_update(review_decision, review_note, "safe")


def route_after_human_review(state: AuditState) -> ReviewRoute:
    """人工复核后的分岔路口。"""

    if state.get("review_decision") == "approved":
        return "delivery"
    return "error_report"


def build_graph(
    review_mode: ReviewMode = "safe",
    checkpointer: InMemorySaver | None = None,
):
    """创建 Day 8 图。

    review_mode:
    - safe：使用 safe_human_review，演示正确写法。
    - unsafe：使用 unsafe_human_review，演示副作用重复执行。
    """

    checkpointer = checkpointer or InMemorySaver()
    review_node = safe_human_review if review_mode == "safe" else unsafe_human_review

    graph = StateGraph(AuditState)

    graph.add_node("intake", intake)
    graph.add_node("normalize", normalize)
    graph.add_node("audit", audit)
    graph.add_node("human_review", review_node)
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


def initial_state() -> AuditState:
    """生成一个一定会进入人工复核的案例。"""

    return {
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


def run_review_flow(review_mode: ReviewMode, decision: ReviewDecision) -> dict[str, Any]:
    """运行一次 safe / unsafe 对比流程。"""

    reset_external_review_log()

    app = build_graph(review_mode=review_mode)
    config = thread_config(f"day8-{review_mode}-{decision}")

    paused = app.invoke(initial_state(), config)
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
        "review_mode": review_mode,
        "decision": decision,
        "paused_has_interrupt": "__interrupt__" in paused,
        "external_review_log": list(EXTERNAL_REVIEW_LOG),
        "final": final,
    }


def run_demo() -> dict[str, Any]:
    """给命令行看的 demo：对比 unsafe 和 safe。"""

    unsafe_report = run_review_flow("unsafe", "approved")
    safe_report = run_review_flow("safe", "approved")

    return {
        "unsafe_report": unsafe_report,
        "safe_report": safe_report,
    }


if __name__ == "__main__":
    print(json.dumps(run_demo(), ensure_ascii=False, indent=2, default=str))
