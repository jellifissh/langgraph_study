from audit_pipeline_poc.reducer_graph import build_graph, run_case


def test_passed_case_accumulates_path_and_events():
    result = run_case("passed")

    assert result["audit_status"] == "passed"
    assert result["workflow_path"] == ["intake", "normalize", "audit", "delivery"]
    assert result["audit_events"] == [
        "intake: received raw fields",
        "normalize: converted raw fields to numeric fields",
        "audit: passed all rules",
        "delivery: final message generated",
    ]
    assert result["audit_errors"] == []
    assert result["warnings"] == []


def test_need_review_case_accumulates_warning_and_review_event():
    result = run_case("need_review")

    assert result["audit_status"] == "need_review"
    assert result["warnings"] == ["profit margin is low and requires review"]
    assert result["workflow_path"] == ["intake", "normalize", "audit", "review", "delivery"]
    assert result["audit_events"] == [
        "intake: received raw fields",
        "normalize: converted raw fields to numeric fields",
        "audit: low profit margin requires review",
        "review: human review placeholder executed",
        "delivery: final message generated",
    ]


def test_missing_field_case_accumulates_normalize_error():
    result = run_case("failed_missing")

    assert result["audit_status"] == "failed"
    assert result["audit_errors"] == ["net_profit is missing"]
    assert result["workflow_path"] == ["intake", "normalize", "audit", "error_report"]
    assert result["audit_events"] == [
        "intake: received raw fields",
        "normalize: converted raw fields to numeric fields",
        "audit: stopped because normalize produced errors",
        "error_report: failure message generated",
    ]


def test_bad_number_case_accumulates_parse_error():
    result = run_case("failed_bad_number")

    assert result["audit_status"] == "failed"
    assert result["normalized_fields"] == {"net_profit": 20.0}
    assert result["audit_errors"] == ["revenue is not a number: 'abc'"]
    assert result["workflow_path"] == ["intake", "normalize", "audit", "error_report"]


def test_custom_negative_profit_accumulates_business_error():
    app = build_graph()

    result = app.invoke(
        {
            "company": "LossCorp",
            "raw_fields": {"revenue": "1000", "net_profit": "-50"},
            "audit_errors": [],
            "warnings": [],
            "audit_events": [],
            "workflow_path": [],
        }
    )

    assert result["audit_status"] == "failed"
    assert result["audit_errors"] == ["profit margin is negative"]
    assert result["workflow_path"] == ["intake", "normalize", "audit", "error_report"]
