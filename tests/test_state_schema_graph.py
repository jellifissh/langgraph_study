from audit_pipeline_poc.state_schema_graph import build_graph, run_case


def test_passed_case_uses_normalized_fields():
    result = run_case("passed")

    assert result["company"] == "DemoCorp"
    assert result["raw_fields"] == {"revenue": "1000", "net_profit": "120"}
    assert result["normalized_fields"] == {
        "revenue": 1000.0,
        "net_profit": 120.0,
        "profit_margin": 0.12,
    }
    assert result["audit_errors"] == []
    assert result["warnings"] == []
    assert result["audit_status"] == "passed"
    assert result["workflow_path"] == ["intake", "normalize", "audit", "delivery"]


def test_low_profit_case_records_warning_and_review_path():
    result = run_case("need_review")

    assert result["company"] == "LowProfitCorp"
    assert result["normalized_fields"]["profit_margin"] == 0.03
    assert result["audit_errors"] == []
    assert result["warnings"] == ["profit margin is low and requires review"]
    assert result["audit_status"] == "need_review"
    assert result["review_note"] == "manual review required because warnings exist"
    assert result["workflow_path"] == ["intake", "normalize", "audit", "review", "delivery"]


def test_missing_net_profit_case_records_audit_error():
    result = run_case("failed_missing")

    assert result["company"] == "MissingProfitCorp"
    assert result["normalized_fields"] == {"revenue": 1000.0}
    assert result["audit_errors"] == ["net_profit is missing"]
    assert result["warnings"] == []
    assert result["audit_status"] == "failed"
    assert result["workflow_path"] == ["intake", "normalize", "audit", "error_report"]
    assert "net_profit is missing" in result["delivery_message"]


def test_zero_revenue_case_records_business_error():
    result = run_case("failed_zero_revenue")

    assert result["company"] == "ZeroRevenueCorp"
    assert result["normalized_fields"] == {
        "revenue": 0.0,
        "net_profit": 10.0,
    }
    assert result["audit_errors"] == ["revenue must be greater than 0"]
    assert result["audit_status"] == "failed"
    assert result["workflow_path"] == ["intake", "normalize", "audit", "error_report"]


def test_custom_non_numeric_field_records_schema_error():
    app = build_graph()

    result = app.invoke(
        {
            "company": "BadInputCorp",
            "raw_fields": {
                "revenue": "not-a-number",
                "net_profit": "10",
            },
        }
    )

    assert result["normalized_fields"] == {"net_profit": 10.0}
    assert result["audit_errors"] == ["revenue is not a number: 'not-a-number'"]
    assert result["audit_status"] == "failed"
    assert result["workflow_path"] == ["intake", "normalize", "audit", "error_report"]
