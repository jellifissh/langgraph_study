import json

import pytest

from audit_pipeline_poc.llm_planner_graph import (
    DeepSeekChatClient,
    build_graph,
    parse_tool_calls_from_llm_response,
    run_case,
)


class FakeClient:
    def __init__(self, response: str):
        self.response = response
        self.messages = []

    def complete(self, messages):
        self.messages.append(messages)
        return self.response


class ExplodingClient:
    def complete(self, messages):
        raise RuntimeError("model is unavailable")


def fake_margin_client(revenue: float, net_profit: float) -> FakeClient:
    return FakeClient(
        json.dumps(
            {
                "tool_calls": [
                    {
                        "name": "calculate_profit_margin",
                        "args": {"revenue": revenue, "net_profit": net_profit},
                    }
                ]
            }
        )
    )


def test_parse_tool_calls_accepts_plain_json():
    text = '{"tool_calls":[{"name":"calculate_profit_margin","args":{"revenue":1000,"net_profit":120}}]}'

    result = parse_tool_calls_from_llm_response(text)

    assert result == [
        {
            "name": "calculate_profit_margin",
            "args": {"revenue": 1000, "net_profit": 120},
        }
    ]


def test_parse_tool_calls_accepts_json_fence():
    text = """```json
{"tool_calls":[{"name":"calculate_profit_margin","args":{"revenue":2000,"net_profit":60}}]}
```"""

    result = parse_tool_calls_from_llm_response(text)

    assert result == [
        {
            "name": "calculate_profit_margin",
            "args": {"revenue": 2000, "net_profit": 60},
        }
    ]


def test_parse_tool_calls_rejects_unknown_tool_name():
    text = json.dumps({"tool_calls": [{"name": "magic_stock_tool", "args": {}}]})

    with pytest.raises(ValueError, match="Unknown tool name"):
        parse_tool_calls_from_llm_response(text)


def test_llm_planner_graph_passed_case_with_fake_client():
    client = fake_margin_client(1000.0, 120.0)

    result = run_case("passed", client=client, allow_rule_fallback=False)

    assert result["planner_mode"] == "llm"
    assert result["audit_status"] == "passed"
    assert result["normalized_fields"]["profit_margin"] == 0.12
    assert result["tool_calls"] == [
        {
            "name": "calculate_profit_margin",
            "args": {"revenue": 1000.0, "net_profit": 120.0},
        }
    ]
    assert result["workflow_path"] == [
        "intake",
        "llm_plan_tool_calls",
        "execute_tools",
        "synthesize_audit",
        "delivery",
    ]
    assert len(client.messages) == 1
    assert "available_tools" in client.messages[0][1]["content"]


def test_llm_planner_graph_need_review_case_with_fake_client():
    client = fake_margin_client(2000.0, 60.0)

    result = run_case("need_review", client=client, allow_rule_fallback=False)

    assert result["planner_mode"] == "llm"
    assert result["audit_status"] == "need_review"
    assert result["warnings"] == ["profit margin is low and requires human review"]
    assert result["workflow_path"] == [
        "intake",
        "llm_plan_tool_calls",
        "execute_tools",
        "synthesize_audit",
        "review",
        "delivery",
    ]


def test_llm_planner_failure_uses_rule_fallback():
    result = run_case("passed", client=ExplodingClient(), allow_rule_fallback=True)

    assert result["planner_mode"] == "rule_fallback"
    assert result["audit_status"] == "passed"
    assert result["tool_calls"] == [
        {
            "name": "calculate_profit_margin",
            "args": {"revenue": 1000.0, "net_profit": 120.0},
        }
    ]
    assert result["warnings"][0].startswith("LLM planner failed, used rule fallback")


def test_llm_planner_failure_without_fallback_fails_graph():
    result = run_case("passed", client=ExplodingClient(), allow_rule_fallback=False)

    assert result["planner_mode"] == "llm"
    assert result["audit_status"] == "failed"
    assert result["audit_errors"] == ["LLM planner failed: model is unavailable"]
    assert result["workflow_path"] == [
        "intake",
        "llm_plan_tool_calls",
        "execute_tools",
        "synthesize_audit",
        "error_report",
    ]


def test_missing_input_skips_llm_client_call():
    client = fake_margin_client(1000.0, 120.0)

    result = run_case("failed_missing", client=client, allow_rule_fallback=False)

    assert result["planner_mode"] == "skip_due_to_input_error"
    assert result["audit_status"] == "failed"
    assert result["audit_errors"] == ["net_profit is missing"]
    assert len(client.messages) == 0


def test_deepseek_client_from_env(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://example.com")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-test")

    client = DeepSeekChatClient.from_env()

    assert client.api_key == "test-key"
    assert client.base_url == "https://example.com"
    assert client.model == "deepseek-test"
    assert client.chat_completions_url == "https://example.com/chat/completions"


def test_build_graph_uses_rule_fallback_when_env_is_missing(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_BASE_URL", raising=False)
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)

    app = build_graph(client=None, allow_rule_fallback=True)
    result = app.invoke(
        {
            "company": "DemoCorp",
            "raw_fields": {"revenue": "1000", "net_profit": "120"},
        }
    )

    assert result["planner_mode"] == "rule_fallback"
    assert result["audit_status"] == "passed"
