import pytest

from audit_pipeline_poc.idempotency_graph import (
    EXTERNAL_CALL_LOG,
    EXTERNAL_REVIEW_REQUESTS,
    build_graph,
    create_review_request_once,
    initial_state,
    make_review_request_id,
    reset_external_systems,
    run_review_flow,
    thread_config,
)
from langgraph.types import Command


def test_idempotency_key_is_stable_for_same_task():
    state = initial_state("task-stable-001")

    first_key = make_review_request_id(state)
    second_key = make_review_request_id(state)

    assert first_key == second_key
    assert first_key == "task-stable-001:human_review:round1"


def test_create_review_request_once_creates_only_one_external_request():
    reset_external_systems()
    state = initial_state("task-create-once")

    review_request_id, first_created = create_review_request_once(state)
    same_review_request_id, second_created = create_review_request_once(state)

    assert review_request_id == same_review_request_id
    assert first_created is True
    assert second_created is False
    assert list(EXTERNAL_REVIEW_REQUESTS) == ["task-create-once:human_review:round1"]
    assert EXTERNAL_CALL_LOG == [
        "try_create:task-create-once:human_review:round1",
        "created:task-create-once:human_review:round1",
        "try_create:task-create-once:human_review:round1",
        "duplicate_skipped:task-create-once:human_review:round1",
    ]


def test_interrupt_resume_calls_pre_interrupt_creation_twice_but_creates_one_request():
    report = run_review_flow(
        "approved",
        task_id="task-approved-idempotent",
        thread_id="thread-approved-idempotent",
    )

    key = "task-approved-idempotent:human_review:round1"

    assert report["paused_has_interrupt"] is True
    assert list(report["external_review_requests"]) == [key]
    assert report["external_review_requests"][key]["status"] == "approved"
    assert report["external_call_log"] == [
        f"try_create:{key}",
        f"created:{key}",
        f"try_create:{key}",
        f"duplicate_skipped:{key}",
        f"decision_saved:{key}:approved",
    ]
    assert report["final"]["audit_status"] == "passed"
    assert report["final"]["review_request_id"] == key
    assert report["final"]["workflow_path"] == [
        "intake",
        "normalize",
        "audit",
        "human_review_with_idempotency",
        "delivery",
    ]


def test_rejected_review_updates_same_external_request():
    report = run_review_flow(
        "rejected",
        task_id="task-rejected-idempotent",
        thread_id="thread-rejected-idempotent",
    )

    key = "task-rejected-idempotent:human_review:round1"

    assert list(report["external_review_requests"]) == [key]
    assert report["external_review_requests"][key]["status"] == "rejected"
    assert report["external_review_requests"][key]["note"] == "Reviewer rejected this low margin case."
    assert report["final"]["audit_status"] == "failed"
    assert report["final"]["audit_errors"] == ["human reviewer rejected low profit margin"]
    assert report["final"]["workflow_path"] == [
        "intake",
        "normalize",
        "audit",
        "human_review_with_idempotency",
        "error_report",
    ]


def test_wrong_thread_does_not_resume_original_interrupt_or_duplicate_request():
    reset_external_systems()
    app = build_graph()

    original_config = thread_config("thread-original-idempotency")
    wrong_config = thread_config("thread-wrong-idempotency")
    key = "task-wrong-thread:human_review:round1"

    paused = app.invoke(initial_state("task-wrong-thread"), original_config)
    assert "__interrupt__" in paused
    assert list(EXTERNAL_REVIEW_REQUESTS) == [key]

    # A resume command must point to an existing paused thread.
    # With a wrong thread_id, this LangGraph version tries to start a fresh run
    # with an empty state, so our intake validation correctly raises.
    with pytest.raises(ValueError, match="Missing required field: company"):
        app.invoke(Command(resume={"decision": "approved"}), wrong_config)

    assert list(EXTERNAL_REVIEW_REQUESTS) == [key]

    final = app.invoke(
        Command(resume={"decision": "approved", "note": "Correct thread resumed."}),
        original_config,
    )

    assert final["audit_status"] == "passed"
    assert EXTERNAL_REVIEW_REQUESTS[key]["status"] == "approved"
    assert EXTERNAL_REVIEW_REQUESTS[key]["note"] == "Correct thread resumed."
