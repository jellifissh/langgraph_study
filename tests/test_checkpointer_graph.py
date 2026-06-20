from audit_pipeline_poc.checkpointer_graph import (
    build_graph,
    initial_state,
    run_case_with_checkpoints,
    thread_config,
)


def test_checkpointer_saves_latest_state_for_passed_case():
    report = run_case_with_checkpoints("passed", thread_id="test-day6-passed")

    assert report["thread_id"] == "test-day6-passed"
    assert report["result"]["audit_status"] == "passed"
    assert report["latest"]["next"] == []
    assert report["latest"]["audit_status"] == "passed"
    assert report["latest"]["workflow_path"] == ["intake", "normalize", "audit", "delivery"]
    assert report["history_length"] >= 5


def test_checkpointer_history_contains_intermediate_review_state():
    report = run_case_with_checkpoints("need_review", thread_id="test-day6-review")

    workflow_paths = [snapshot["workflow_path"] for snapshot in report["history"]]

    assert report["result"]["audit_status"] == "need_review"
    assert report["latest"]["workflow_path"] == [
        "intake",
        "normalize",
        "audit",
        "review",
        "delivery",
    ]
    assert ["intake", "normalize", "audit"] in workflow_paths
    assert ["intake", "normalize", "audit", "review"] in workflow_paths


def test_thread_ids_keep_checkpoint_state_separate():
    app = build_graph()

    passed_config = thread_config("test-day6-thread-a")
    failed_config = thread_config("test-day6-thread-b")

    app.invoke(initial_state("passed"), passed_config)
    app.invoke(initial_state("failed_missing"), failed_config)

    passed_snapshot = app.get_state(passed_config)
    failed_snapshot = app.get_state(failed_config)

    assert passed_snapshot.values["company"] == "DemoCorp"
    assert passed_snapshot.values["audit_status"] == "passed"
    assert failed_snapshot.values["company"] == "MissingProfitCorp"
    assert failed_snapshot.values["audit_status"] == "failed"
    assert failed_snapshot.values["audit_errors"] == ["net_profit is missing"]


def test_same_thread_keeps_history_across_multiple_invocations():
    app = build_graph()
    config = thread_config("test-day6-same-thread")

    app.invoke(initial_state("passed"), config)
    first_history_length = len(list(app.get_state_history(config)))

    app.invoke(initial_state("need_review"), config)
    second_history_length = len(list(app.get_state_history(config)))

    snapshot = app.get_state(config)

    assert second_history_length > first_history_length
    assert snapshot.values["company"] == "LowProfitCorp"
    assert snapshot.values["audit_status"] == "need_review"
