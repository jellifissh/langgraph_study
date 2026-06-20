from audit_pipeline_poc.basic_graph import build_graph, run_demo


def test_run_demo_passed_case():
    result = run_demo()

    assert result["company"] == "DemoCorp"
    assert result["revenue"] == 1000.0
    assert result["net_profit"] == 120.0
    assert result["profit_margin"] == 0.12
    assert result["audit_status"] == "passed"
    assert "profit margin = 12.00%" in result["delivery_message"]


def test_negative_profit_fails_case():
    app = build_graph()

    result = app.invoke(
        {
            "company": "LossCorp",
            "revenue": 1000,
            "net_profit": -50,
        }
    )

    assert result["profit_margin"] == -0.05
    assert result["audit_status"] == "failed"
    assert "LossCorp audit failed" in result["delivery_message"]


def test_zero_revenue_fails_case():
    app = build_graph()

    result = app.invoke(
        {
            "company": "ZeroRevenueCorp",
            "revenue": 0,
            "net_profit": 10,
        }
    )

    assert result["profit_margin"] == 0.0
    assert result["audit_status"] == "failed"
    assert "ZeroRevenueCorp audit failed" in result["delivery_message"]
