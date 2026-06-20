from audit_pipeline_poc.interrupt_graph import (
    build_graph,
    extract_interrupt_payload,
    initial_state,
    run_need_review_until_interrupt,
    run_need_review_with_human_decision,
    thread_config,
)
from langgraph.types import Command


def test_need_review_case_pauses_at_human_review():
    report = run_need_review_until_interrupt("test-day7-paused")

    payload = report["interrupt_payload"]
    latest_state = report["latest_state"]

    assert payload["company"] == "LowProfitCorp"
    assert payload["profit_margin"] == 0.03
    assert payload["allowed_decisions"] == ["approved", "rejected"]
    assert latest_state["workflow_path"] == ["intake", "normalize", "audit"]
    assert latest_state["audit_status"] == "need_review"


def test_approved_resume_continues_to_delivery():
    report = run_need_review_with_human_decision(
        "approved",
        thread_id="test-day7-approved",
        note="Approved after checking context.",
    )

    final = report["final"]

    assert final["audit_status"] == "passed"
    assert final["review_decision"] == "approved"
    assert final["review_note"] == "Approved after checking context."
    assert final["workflow_path"] == [
        "intake",
        "normalize",
        "audit",
        "human_review",
        "delivery",
    ]
    assert final["audit_events"][-2:] == [
        "human_review: approved by reviewer",
        "delivery: final message generated",
    ]
    assert "__interrupt__" not in final


def test_rejected_resume_continues_to_error_report():
    report = run_need_review_with_human_decision(
        "rejected",
        thread_id="test-day7-rejected",
        note="Rejected because margin is too low.",
    )

    final = report["final"]

    assert final["audit_status"] == "failed"
    assert final["review_decision"] == "rejected"
    assert final["review_note"] == "Rejected because margin is too low."
    assert final["audit_errors"] == ["human reviewer rejected low profit margin"]
    assert final["workflow_path"] == [
        "intake",
        "normalize",
        "audit",
        "human_review",
        "error_report",
    ]
    assert final["audit_events"][-2:] == [
        "human_review: rejected by reviewer",
        "error_report: failure message generated",
    ]


def test_passed_case_does_not_interrupt():
    app = build_graph()
    config = thread_config("test-day7-no-interrupt")

    result = app.invoke(initial_state("passed"), config)

    assert "__interrupt__" not in result
    assert result["audit_status"] == "passed"
    assert result["workflow_path"] == ["intake", "normalize", "audit", "delivery"]


def test_resume_value_becomes_interrupt_return_value():
    app = build_graph()
    config = thread_config("test-day7-manual-resume")

    paused = app.invoke(initial_state("need_review"), config)
    payload = extract_interrupt_payload(paused)

    assert payload["company"] == "LowProfitCorp"

    final = app.invoke(
        Command(
            resume={
                "decision": "approved",
                "note": "Manual resume payload became review note.",
            }
        ),
        config,
    )

    assert final["review_decision"] == "approved"
    assert final["review_note"] == "Manual resume payload became review note."
    assert final["audit_status"] == "passed"
