"""Unit tests for guardrails generator."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from src.guardrails.generator import translate_rules_to_guardrails


def _sample_guardrail_dict(id: str = "GR-ENC-001", desc: str = "Test guardrail") -> dict:
    return {
        "id": id,
        "short_description": desc,
        "severity": "HIGH",
        "action": "BLOCK",
        "applies_to": ["s3:bucket"],
        "condition": "Encryption exists",
        "ai_context": "Enable encryption",
        "tags": ["security"],
    }


def _make_llm_client(response_data: list) -> MagicMock:
    """Build a mock LLMClient that returns JSON from complete()."""
    client = MagicMock()
    client.complete.return_value = json.dumps(response_data)
    client.config.get_default_model.return_value = "mock-model"
    return client


class TestTranslateRulesToGuardrails:
    """Tests for translate_rules_to_guardrails()."""

    def test_no_llm_client_returns_empty(self) -> None:
        result = translate_rules_to_guardrails(rules=["rule 1"], llm_client=None)
        assert result == []

    def test_empty_rules_returns_empty(self) -> None:
        result = translate_rules_to_guardrails(rules=[], llm_client=MagicMock())
        assert result == []

    def test_single_rule_success(self) -> None:
        client = _make_llm_client([_sample_guardrail_dict()])

        result = translate_rules_to_guardrails(rules=["S3 must be encrypted"], llm_client=client)
        assert len(result) == 1
        assert result[0].id == "GR-ENC-001"
        client.complete.assert_called_once()

    def test_instructions_injected_into_prompt(self) -> None:
        client = _make_llm_client([_sample_guardrail_dict()])

        translate_rules_to_guardrails(
            rules=["A1234: S3 encryption"],
            instructions="format is 'ID: description'",
            llm_client=client,
        )

        call_kwargs = client.complete.call_args.kwargs
        prompt_text = call_kwargs["messages"][0]["content"]
        assert "format is 'ID: description'" in prompt_text

    def test_batch_splitting(self) -> None:
        client = _make_llm_client([_sample_guardrail_dict()])

        rules = [f"Rule {i}" for i in range(25)]
        translate_rules_to_guardrails(rules=rules, llm_client=client)

        assert client.complete.call_count == 3  # 10 + 10 + 5

    def test_partial_failure(self) -> None:
        client = MagicMock()
        client.config.get_default_model.return_value = "mock-model"

        client.complete.side_effect = [
            json.dumps([_sample_guardrail_dict()]),
            Exception("API error"),
        ]

        rules = [f"Rule {i}" for i in range(15)]  # 2 batches
        result = translate_rules_to_guardrails(rules=rules, llm_client=client)

        assert len(result) == 1  # Only first batch succeeded

    def test_multiple_rules_per_batch(self) -> None:
        client = _make_llm_client(
            [
                _sample_guardrail_dict("GR-ENC-001", "Rule 1"),
                _sample_guardrail_dict("GR-ENC-002", "Rule 2"),
                _sample_guardrail_dict("GR-ENC-003", "Rule 3"),
            ]
        )

        rules = ["Rule 1", "Rule 2", "Rule 3"]
        result = translate_rules_to_guardrails(rules=rules, llm_client=client)

        assert len(result) == 3
        assert result[0].id == "GR-ENC-001"
        assert result[2].id == "GR-ENC-003"
