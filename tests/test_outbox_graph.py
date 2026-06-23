from audit_pipeline_poc.outbox_graph import (
    OUTBOX_EVENTS,
    SENT_MESSAGES,
    dispatch_outbox_events,
    enqueue_outbox_event_once,
    make_outbox_event_id,
    reset_external_systems,
    run_review_flow,
)


def test_outbox_event_id_is_stable():
    event_id = make_outbox_event_id("task-1:human_review:round1", "approved")

    assert event_id == "task-1:human_review:round1:decision:approved"


def test_enqueue_outbox_event_once_creates_one_pending_event():
    reset_external_systems()

    event_id, first_created = enqueue_outbox_event_once(
        "task-outbox:human_review:round1",
        "approved",
        "Approved once.",
    )
    same_event_id, second_created = enqueue_outbox_event_once(
        "task-outbox:human_review:round1",
        "approved",
        "Approved once.",
    )

    assert event_id == same_event_id
    assert first_created is True
    assert second_created is False
    assert list(OUTBOX_EVENTS) == ["task-outbox:human_review:round1:decision:approved"]
    assert OUTBOX_EVENTS[event_id]["status"] == "pending"
    assert SENT_MESSAGES == []


def test_graph_records_outbox_event_but_does_not_send_immediately():
    report = run_review_flow(
        "approved",
        task_id="task-outbox-approved",
        thread_id="thread-outbox-approved",
        dispatch_after_graph=False,
    )

    event_id = "task-outbox-approved:human_review:round1:decision:approved"

    assert report["paused_has_interrupt"] is True
    assert list(report["outbox_events"]) == [event_id]
    assert report["outbox_events"][event_id]["status"] == "pending"
    assert report["sent_messages"] == []
    assert report["final"]["audit_status"] == "passed"
    assert report["final"]["outbox_event_id"] == event_id


def test_dispatcher_sends_pending_event_once_and_marks_sent():
    report = run_review_flow(
        "approved",
        task_id="task-outbox-dispatch",
        thread_id="thread-outbox-dispatch",
        dispatch_after_graph=False,
    )

    event_id = "task-outbox-dispatch:human_review:round1:decision:approved"
    assert report["outbox_events"][event_id]["status"] == "pending"
    assert SENT_MESSAGES == []

    first_dispatch = dispatch_outbox_events()
    second_dispatch = dispatch_outbox_events()

    assert first_dispatch == [event_id]
    assert second_dispatch == []
    assert OUTBOX_EVENTS[event_id]["status"] == "sent"
    assert SENT_MESSAGES == [
        {
            "event_id": event_id,
            "type": "review.decision_saved",
            "review_request_id": "task-outbox-dispatch:human_review:round1",
            "decision": "approved",
        }
    ]


def test_rejected_review_records_rejected_outbox_event():
    report = run_review_flow(
        "rejected",
        task_id="task-outbox-rejected",
        thread_id="thread-outbox-rejected",
        dispatch_after_graph=True,
    )

    event_id = "task-outbox-rejected:human_review:round1:decision:rejected"

    assert list(report["outbox_events"]) == [event_id]
    assert report["outbox_events"][event_id]["status"] == "sent"
    assert report["sent_messages"] == [
        {
            "event_id": event_id,
            "type": "review.decision_saved",
            "review_request_id": "task-outbox-rejected:human_review:round1",
            "decision": "rejected",
        }
    ]
    assert report["final"]["audit_status"] == "failed"
    assert report["final"]["workflow_path"] == [
        "intake",
        "normalize",
        "audit",
        "human_review_with_outbox",
        "error_report",
    ]
