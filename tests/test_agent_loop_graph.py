import json

import pytest

from audit_pipeline_poc.agent_loop_graph import (
    parse_agent_action,
    run_case,
)


class SequenceClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.messages = []

    def complete(self, messages):
        self.messages.append(messages)
        if len(self.responses) == 1:
            return self.responses[0]
        return self.responses.pop(0)


def tool_action(tool_name, args, reason=""):
    return json.dumps(
        {
            "action": "tool",
            "tool_name": tool_name,
            "args": args,
            "reason": reason,
        }
    )


def final_action(status, answer, reason="done"):
    return json.dumps(
        {
            "action": "final",
            "audit_status": status,
            "final_answer": answer,
            "reason": reason,
        }
    )


def passed_sequence_client():
    return SequenceClient(
        [
            tool_action("calculate_profit_margin", {"revenue": 1000.0, "net_profit": 120.0}),
            tool_action("classify_profit_margin", {"profit_margin": 0.12}),
            tool_action(
                "build_audit_recommendation",
                {"company": "DemoCorp", "profit_margin": 0.12, "risk_level": "low"},
            ),
            final_action("passed", "DemoCorp can be delivered automatically."),
        ]
    )


def test_parse_agent_action_accepts_tool_action():
    action = parse_agent_action(
        '{"action":"tool","tool_name":"calculate_profit_margin","args":{"revenue":1000,"net_profit":120}}'
    )

    assert action == {
        "action": "tool",
        "tool_name": "calculate_profit_margin",
        "args": {"revenue": 1000, "net_profit": 120},
        "reason": "",
    }


def test_parse_agent_action_accepts_final_action():
    action = parse_agent_action(
        '{"action":"final","audit_status":"passed","final_answer":"ok","reason":"enough evidence"}'
    )

    assert action == {
        "action": "final",
        "audit_status": "passed",
        "final_answer": "ok",
        "reason": "enough evidence",
    }


def test_parse_agent_action_rejects_unknown_tool():
    with pytest.raises(ValueError, match="Unknown tool name"):
        parse_agent_action('{"action":"tool","tool_name":"magic_tool","args":{}}')


def test_agent_loop_rule_fallback_passed_case():
    result = run_case("passed", client=None, allow_rule_fallback=True)

    assert result["audit_status"] == "passed"
    assert result["planner_mode"] == "rule_fallback"
    assert [item["name"] for item in result["tool_results"]] == [
        "calculate_profit_margin",
        "classify_profit_margin",
        "build_audit_recommendation",
    ]
    assert [step["action"]["action"] for step in result["agent_steps"]] == [
        "tool",
        "tool",
        "tool",
        "final",
    ]
    assert result["workflow_path"] == [
        "intake",
        "agent_decide",
        "execute_agent_tool",
        "agent_decide",
        "execute_agent_tool",
        "agent_decide",
        "execute_agent_tool",
        "agent_decide",
        "finalize_agent_answer",
        "delivery",
    ]


def test_agent_loop_with_fake_llm_passed_case():
    client = passed_sequence_client()

    result = run_case("passed", client=client, allow_rule_fallback=False)

    assert result["audit_status"] == "passed"
    assert result["planner_mode"] == "llm"
    assert len(client.messages) == 4
    assert result["final_answer"] == "DemoCorp can be delivered automatically."
    assert [step["planner_mode"] for step in result["agent_steps"]] == ["llm", "llm", "llm", "llm"]
    assert [item["name"] for item in result["tool_results"]] == [
        "calculate_profit_margin",
        "classify_profit_margin",
        "build_audit_recommendation",
    ]


def test_agent_loop_need_review_routes_through_review():
    result = run_case("need_review", client=None, allow_rule_fallback=True)

    assert result["audit_status"] == "need_review"
    assert result["review_note"] == "Manual reviewer should inspect low margin before delivery."
    assert result["workflow_path"] == [
        "intake",
        "agent_decide",
        "execute_agent_tool",
        "agent_decide",
        "execute_agent_tool",
        "agent_decide",
        "execute_agent_tool",
        "agent_decide",
        "finalize_agent_answer",
        "review",
        "delivery",
    ]


def test_agent_loop_failed_negative_routes_to_error_report():
    result = run_case("failed_negative", client=None, allow_rule_fallback=True)

    assert result["audit_status"] == "failed"
    assert result["final_answer"] == "LossCorp should not be delivered because the margin is negative."
    assert result["workflow_path"] == [
        "intake",
        "agent_decide",
        "execute_agent_tool",
        "agent_decide",
        "execute_agent_tool",
        "agent_decide",
        "execute_agent_tool",
        "agent_decide",
        "finalize_agent_answer",
        "error_report",
    ]


def test_agent_loop_llm_failure_without_fallback_finalizes_failed():
    client = SequenceClient(["not json"])

    result = run_case("passed", client=client, allow_rule_fallback=False)

    assert result["audit_status"] == "failed"
    assert result["planner_mode"] == "llm"
    assert result["final_answer"].startswith("Agent decision failed:")
    assert result["workflow_path"] == [
        "intake",
        "agent_decide",
        "finalize_agent_answer",
        "error_report",
    ]


def test_agent_loop_stops_at_max_steps():
    client = SequenceClient(
        [tool_action("calculate_profit_margin", {"revenue": 1000.0, "net_profit": 120.0})]
    )

    result = run_case("passed", client=client, allow_rule_fallback=False, max_agent_steps=2)

    assert result["audit_status"] == "failed"
    assert result["final_answer"] == "Agent exceeded max steps: 2"
    assert [step["action"]["action"] for step in result["agent_steps"]] == ["tool", "tool", "final"]
