"""Day 6: add a checkpointer to persist graph state snapshots.

大白话版本：

- 前几天我们只是在“跑流程”。
- 今天我们让流程“存档”。
- Checkpointer = 存档器。
- thread_id = 存档槽位 / 任务编号。
- get_state = 读取这个任务最新存档。
- get_state_history = 读取这个任务所有存档记录。

注意：这里使用 InMemorySaver，只适合学习和测试。
程序退出后，内存里的存档就没了。生产环境要换数据库型 checkpointer。
"""

from __future__ import annotations

import json
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from audit_pipeline_poc.reducer_graph import (
    AuditState,
    audit,
    delivery,
    error_report,
    intake,
    normalize,
    review,
    route_by_audit_result,
)


def build_graph(checkpointer: InMemorySaver | None = None):
    """创建一个带 checkpointer 的 reducer 工作流。

    源码细讲：

    1. checkpointer = checkpointer or InMemorySaver()
       - 如果外面传了 checkpointer，就用外面的。
       - 如果没传，就创建一个内存存档器。
       - 这样测试可以自己控制 checkpointer，demo 也能直接跑。

    2. StateGraph(AuditState)
       - 仍然使用 Day 5 的 State 设计。
       - reducer、workflow_path、audit_events 这些能力都保留。

    3. graph.compile(checkpointer=checkpointer)
       - 这是 Day 6 的关键。
       - 不只是 compile 成可运行图，还告诉 LangGraph：每一步执行后要保存状态快照。
    """

    checkpointer = checkpointer or InMemorySaver()

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

    return graph.compile(checkpointer=checkpointer)


def initial_state(case_name: str) -> AuditState:
    """按案例名生成初始 State。

    这里单独拆出来，是为了让测试和 demo 都能复用同一批输入。
    这比复制粘贴一堆 dict 稳一点。复制粘贴是 bug 的无性繁殖。
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
    """生成 LangGraph 存档配置。

    checkpointer 需要 thread_id。
    大白话：thread_id 就是这次任务的存档槽位。

    如果两个任务用了同一个 thread_id，它们就会写进同一个线程历史里。
    如果两个任务用了不同 thread_id，它们的存档互不影响。
    """

    return {"configurable": {"thread_id": thread_id}}


def summarize_snapshot(snapshot: Any) -> dict[str, Any]:
    """把 StateSnapshot 转成更容易看的小字典。

    StateSnapshot 里东西很多。今天只看几个最重要的：
    - values：这个存档点里的 State 内容。
    - next：下一步要执行哪些节点。空 tuple 说明流程结束。
    - metadata.step：第几个 super-step。
    - metadata.writes：这个 step 是哪个节点写了什么。
    """

    values = dict(snapshot.values)
    metadata = dict(snapshot.metadata or {})

    return {
        "step": metadata.get("step"),
        "next": list(snapshot.next),
        "writes": metadata.get("writes", {}),
        "workflow_path": values.get("workflow_path", []),
        "audit_status": values.get("audit_status"),
        "audit_errors": values.get("audit_errors", []),
        "warnings": values.get("warnings", []),
    }


def run_case_with_checkpoints(case_name: str, thread_id: str | None = None) -> dict[str, Any]:
    """运行一次图，并返回最终结果 + 最新存档 + 历史存档摘要。"""

    final_thread_id = thread_id or f"day6-{case_name}"
    config = thread_config(final_thread_id)

    app = build_graph()
    result = app.invoke(initial_state(case_name), config)

    latest_snapshot = app.get_state(config)
    history = list(app.get_state_history(config))

    return {
        "thread_id": final_thread_id,
        "result": result,
        "latest": summarize_snapshot(latest_snapshot),
        # LangGraph 返回历史时，最新 checkpoint 通常在最前面。
        "history": [summarize_snapshot(snapshot) for snapshot in history],
        "history_length": len(history),
    }


if __name__ == "__main__":
    for case_name in ["passed", "need_review", "failed_missing"]:
        report = run_case_with_checkpoints(case_name)
        print(f"\n=== {case_name} / thread_id={report['thread_id']} ===")
        print(json.dumps(report, ensure_ascii=False, indent=2))
