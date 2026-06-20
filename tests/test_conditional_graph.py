from audit_pipeline_poc.conditional_graph import build_graph, run_case


def test_passed_case_goes_directly_to_delivery():
    result = run_case("passed")

    assert result["company"] == "DemoCorp"
    assert result["profit_margin"] == 0.12
    assert result["audit_status"] == "passed"
    assert result["workflow_path"] == ["intake", "audit", "delivery"]
    assert "review_note" not in result
    assert "DemoCorp audit passed" in result["delivery_message"]


def test_low_profit_case_goes_to_review_then_delivery():
    result = run_case("need_review")

    assert result["company"] == "LowProfitCorp"
    assert result["profit_margin"] == 0.03
    assert result["audit_status"] == "need_review"
    assert result["workflow_path"] == ["intake", "audit", "review", "delivery"]
    assert "manual review required" in result["review_note"]
    assert "LowProfitCorp audit need_review" in result["delivery_message"]


def test_zero_revenue_case_goes_to_error_report():
    result = run_case("failed")

    assert result["company"] == "ZeroRevenueCorp"
    assert result["profit_margin"] == 0.0
    assert result["audit_status"] == "failed"
    assert result["workflow_path"] == ["intake", "audit", "error_report"]
    assert result["error_message"] == "revenue must be greater than 0"
    assert "ZeroRevenueCorp audit failed" in result["delivery_message"]


def test_custom_negative_profit_case_goes_to_error_report():
    app = build_graph()

    result = app.invoke(
        {
            "company": "LossCorp",
            "revenue": 1000,
            "net_profit": -10,
        }
    )

    assert result["profit_margin"] == -0.01
    assert result["audit_status"] == "failed"
    assert result["workflow_path"] == ["intake", "audit", "error_report"]
