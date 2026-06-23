import pytest

from audit_pipeline_poc.interrupt_safety_graph import (
    EXTERNAL_REVIEW_LOG,
    build_graph,
    initial_state,
    reset_external_review_log,
    run_review_flow,
    thread_config,
)
from langgraph.types import Command


def test_unsafe_review_runs_before_interrupt_side_effect_twice():
    report = run_review_flow("unsafe", "approved")

    assert report["paused_has_interrupt"] is True
    assert report["external_review_log"] == [
        "unsafe: before interrupt",
        "unsafe: before interrupt",
        "unsafe: after resume approved",
    ]
    assert report["final"]["audit_status"] == "passed"
    assert report["final"]["workflow_path"] == [
        "intake",
        "normalize",
        "audit",
        "unsafe_human_review",
        "delivery",
    ]


def test_safe_review_runs_external_side_effect_once_after_resume():
    report = run_review_flow("safe", "approved")

    assert report["paused_has_interrupt"] is True
    assert report["external_review_log"] == ["safe: after resume approved"]
    assert report["final"]["audit_status"] == "passed"
    assert report["final"]["workflow_path"] == [
        "intake",
        "normalize",
        "audit",
        "safe_human_review",
        "delivery",
    ]


def test_safe_rejected_review_records_one_rejection_side_effect():
    report = run_review_flow("safe", "rejected")

    assert report["external_review_log"] == ["safe: after resume rejected"]
    assert report["final"]["audit_status"] == "failed"
    assert report["final"]["audit_errors"] == ["safe human reviewer rejected low profit margin"]
    assert report["final"]["workflow_path"] == [
        "intake",
        "normalize",
        "audit",
        "safe_human_review",
        "error_report",
    ]


def test_interrupt_before_resume_does_not_write_safe_external_log():
    reset_external_review_log()
    app = build_graph(review_mode="safe")
    config = thread_config("test-day8-safe-paused")

    paused = app.invoke(initial_state(), config)

    assert "__interrupt__" in paused
    assert EXTERNAL_REVIEW_LOG == []


def test_resume_must_use_existing_thread_to_continue_paused_run():
    reset_external_review_log()
    app = build_graph(review_mode="safe")

    original_config = thread_config("test-day8-original-thread")
    wrong_config = thread_config("test-day8-wrong-thread")

    paused = app.invoke(initial_state(), original_config)
    assert "__interrupt__" in paused

    # A resume command must point to an existing paused thread.
    # With a wrong thread_id, this LangGraph version tries to start a fresh run
    # with an empty state, so our intake validation correctly raises.
    with pytest.raises(ValueError, match="Missing required field: company"):
        app.invoke(Command(resume={"decision": "approved"}), wrong_config)

    final = app.invoke(
        Command(resume={"decision": "approved", "note": "Correct thread resumed."}),
        original_config,
    )

    assert final["review_note"] == "Correct thread resumed."
    assert final["audit_status"] == "passed"
    assert EXTERNAL_REVIEW_LOG == ["safe: after resume approved"]
