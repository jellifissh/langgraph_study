from audit_pipeline_poc.tool_calling_graph import (
    build_audit_recommendation,
    calculate_profit_margin,
    classify_profit_margin,
    execute_tools,
    run_case,
)


def test_profit_margin_tool_calculates_margin():
    result = calculate_profit_margin(revenue=1000, net_profit=120)

    assert result == {
        "revenue": 1000,
        "net_profit": 120,
        "profit_margin": 0.12,
    }


def test_classify_profit_margin_tool_returns_review_for_low_margin():
    result = classify_profit_margin(0.03)

    assert result["status"] == "need_review"
    assert result["risk_level"] == "medium"
    assert result["reason"] == "profit margin is low and requires human review"


def test_build_audit_recommendation_tool_returns_action():
    result = build_audit_recommendation("DemoCorp", 0.12, "low")

    assert result == {
        "action": "deliver",
        "recommendation": "DemoCorp can be delivered automatically.",
        "margin_text": "12.00%",
    }


def test_execute_tools_records_tool_error_without_crashing():
    result = execute_tools(
        {
            "tool_calls": [
                {
                    "name": "calculate_profit_margin",
                    "args": {"revenue": 0, "net_profit": 10},
                }
            ]
        }
    )

    assert result["tool_results"] == [
        {
            "name": "calculate_profit_margin",
            "ok": False,
            "result": None,
            "error": "revenue must be greater than 0",
        }
    ]
    assert result["workflow_path"] == ["execute_tools"]


def test_tool_calling_graph_passed_case():
    result = run_case("passed")

    assert result["audit_status"] == "passed"
    assert result["normalized_fields"]["profit_margin"] == 0.12
    assert result["tool_calls"] == [
        {
            "name": "calculate_profit_margin",
            "args": {"revenue": 1000.0, "net_profit": 120.0},
        }
    ]
    assert [item["name"] for item in result["tool_results"]] == [
        "calculate_profit_margin",
        "classify_profit_margin",
        "build_audit_recommendation",
    ]
    assert result["workflow_path"] == [
        "intake",
        "plan_tool_calls",
        "execute_tools",
        "synthesize_audit",
        "delivery",
    ]


def test_tool_calling_graph_need_review_case():
    result = run_case("need_review")

    assert result["audit_status"] == "need_review"
    assert result["warnings"] == ["profit margin is low and requires human review"]
    assert result["review_note"] == "Manual reviewer should inspect low margin before delivery."
    assert result["workflow_path"] == [
        "intake",
        "plan_tool_calls",
        "execute_tools",
        "synthesize_audit",
        "review",
        "delivery",
    ]


def test_tool_calling_graph_failed_negative_case():
    result = run_case("failed_negative")

    assert result["audit_status"] == "failed"
    assert result["audit_errors"] == ["profit margin is negative"]
    assert result["workflow_path"] == [
        "intake",
        "plan_tool_calls",
        "execute_tools",
        "synthesize_audit",
        "error_report",
    ]


def test_tool_calling_graph_failed_missing_input_skips_tool_calling():
    result = run_case("failed_missing")

    assert result["audit_status"] == "failed"
    assert result["audit_errors"] == ["net_profit is missing"]
    assert result.get("tool_calls") is None
    assert result["tool_results"] == []
    assert result["workflow_path"] == [
        "intake",
        "plan_tool_calls",
        "execute_tools",
        "synthesize_audit",
        "error_report",
    ]
