"""Unit tests for guardrails validator."""

from __future__ import annotations

import pytest


class TestValidateGuardrail:
    """Tests for validate_guardrail() (T025)."""

    def test_valid_guardrail(self) -> None:
        from src.guardrails.validator import validate_guardrail

        guardrail_dict = {
            "id": "GR-ENC-001",
            "short_description": "S3 bucket must have encryption at rest",
            "severity": "CRITICAL",
            "action": "AUTO-FIX",
            "applies_to": ["s3:bucket"],
            "condition": {
                "attribute": "ServerSideEncryptionConfiguration",
                "operator": "exists",
            },
            "ai_context": "WHY: Compliance requires encryption.",
        }
        errors = validate_guardrail(guardrail_dict)
        assert errors == []

    def test_missing_id(self) -> None:
        from src.guardrails.validator import validate_guardrail

        guardrail_dict = {
            "short_description": "Test",
            "severity": "HIGH",
            "action": "BLOCK",
            "applies_to": ["*"],
            "condition": {"attribute": "test", "operator": "exists"},
        }
        errors = validate_guardrail(guardrail_dict)
        assert any("id" in e.lower() for e in errors)

    def test_invalid_id_format(self) -> None:
        from src.guardrails.validator import validate_guardrail

        guardrail_dict = {
            "id": "invalid-id",
            "short_description": "Test",
            "severity": "HIGH",
            "action": "BLOCK",
            "applies_to": ["*"],
            "condition": {"attribute": "test", "operator": "exists"},
        }
        errors = validate_guardrail(guardrail_dict)
        assert any("format" in e.lower() or "pattern" in e.lower() for e in errors)

    def test_valid_custom_id_format(self) -> None:
        from src.guardrails.validator import validate_guardrail

        guardrail_dict = {
            "id": "ACME-SEC-001",
            "short_description": "Custom company guardrail",
            "severity": "HIGH",
            "action": "BLOCK",
            "applies_to": ["*"],
            "condition": {"attribute": "test", "operator": "exists"},
        }
        errors = validate_guardrail(guardrail_dict)
        assert errors == []

    def test_missing_short_description(self) -> None:
        from src.guardrails.validator import validate_guardrail

        guardrail_dict = {
            "id": "GR-TEST-001",
            "severity": "HIGH",
            "action": "BLOCK",
            "applies_to": ["*"],
            "condition": {"attribute": "test", "operator": "exists"},
        }
        errors = validate_guardrail(guardrail_dict)
        assert any("short_description" in e.lower() for e in errors)

    def test_short_description_too_long(self) -> None:
        from src.guardrails.validator import validate_guardrail

        guardrail_dict = {
            "id": "GR-TEST-001",
            "short_description": "x" * 150,  # > 100 chars
            "severity": "HIGH",
            "action": "BLOCK",
            "applies_to": ["*"],
            "condition": {"attribute": "test", "operator": "exists"},
        }
        errors = validate_guardrail(guardrail_dict)
        assert any("100" in e or "length" in e.lower() for e in errors)

    def test_invalid_severity(self) -> None:
        from src.guardrails.validator import validate_guardrail

        guardrail_dict = {
            "id": "GR-TEST-001",
            "short_description": "Test",
            "severity": "SUPER_HIGH",  # Invalid
            "action": "BLOCK",
            "applies_to": ["*"],
            "condition": {"attribute": "test", "operator": "exists"},
        }
        errors = validate_guardrail(guardrail_dict)
        assert any("severity" in e.lower() for e in errors)

    def test_invalid_action(self) -> None:
        from src.guardrails.validator import validate_guardrail

        guardrail_dict = {
            "id": "GR-TEST-001",
            "short_description": "Test",
            "severity": "HIGH",
            "action": "INVALID_ACTION",
            "applies_to": ["*"],
            "condition": {"attribute": "test", "operator": "exists"},
        }
        errors = validate_guardrail(guardrail_dict)
        assert any("action" in e.lower() for e in errors)

    def test_missing_applies_to(self) -> None:
        from src.guardrails.validator import validate_guardrail

        guardrail_dict = {
            "id": "GR-TEST-001",
            "short_description": "Test",
            "severity": "HIGH",
            "action": "BLOCK",
            "condition": {"attribute": "test", "operator": "exists"},
        }
        errors = validate_guardrail(guardrail_dict)
        assert any("applies_to" in e.lower() for e in errors)

    def test_empty_applies_to(self) -> None:
        from src.guardrails.validator import validate_guardrail

        guardrail_dict = {
            "id": "GR-TEST-001",
            "short_description": "Test",
            "severity": "HIGH",
            "action": "BLOCK",
            "applies_to": [],
            "condition": {"attribute": "test", "operator": "exists"},
        }
        errors = validate_guardrail(guardrail_dict)
        assert any("applies_to" in e.lower() for e in errors)

    def test_missing_condition(self) -> None:
        from src.guardrails.validator import validate_guardrail

        guardrail_dict = {
            "id": "GR-TEST-001",
            "short_description": "Test",
            "severity": "HIGH",
            "action": "BLOCK",
            "applies_to": ["*"],
        }
        errors = validate_guardrail(guardrail_dict)
        assert any("condition" in e.lower() for e in errors)

    def test_invalid_condition_missing_attribute(self) -> None:
        from src.guardrails.validator import validate_guardrail

        guardrail_dict = {
            "id": "GR-TEST-001",
            "short_description": "Test",
            "severity": "HIGH",
            "action": "BLOCK",
            "applies_to": ["*"],
            "condition": {"operator": "exists"},  # Missing attribute
        }
        errors = validate_guardrail(guardrail_dict)
        assert any("attribute" in e.lower() for e in errors)

    def test_invalid_condition_missing_operator(self) -> None:
        from src.guardrails.validator import validate_guardrail

        guardrail_dict = {
            "id": "GR-TEST-001",
            "short_description": "Test",
            "severity": "HIGH",
            "action": "BLOCK",
            "applies_to": ["*"],
            "condition": {"attribute": "test"},  # Missing operator
        }
        errors = validate_guardrail(guardrail_dict)
        assert any("operator" in e.lower() for e in errors)

    def test_invalid_operator(self) -> None:
        from src.guardrails.validator import validate_guardrail

        guardrail_dict = {
            "id": "GR-TEST-001",
            "short_description": "Test",
            "severity": "HIGH",
            "action": "BLOCK",
            "applies_to": ["*"],
            "condition": {"attribute": "test", "operator": "invalid_op"},
        }
        errors = validate_guardrail(guardrail_dict)
        assert any("operator" in e.lower() for e in errors)

    def test_all_valid_operators(self) -> None:
        from src.guardrails.validator import validate_guardrail

        valid_operators = [
            "equals",
            "not_equals",
            "exists",
            "not_exists",
            "contains",
            "not_contains",
            "matches",
            "in",
            "not_in",
            "greater_than",
            "less_than",
        ]
        for operator in valid_operators:
            guardrail_dict = {
                "id": "GR-TEST-001",
                "short_description": "Test",
                "severity": "HIGH",
                "action": "BLOCK",
                "applies_to": ["*"],
                "condition": {"attribute": "test", "operator": operator, "value": "test"},
            }
            errors = validate_guardrail(guardrail_dict)
            assert errors == [], f"Operator {operator} should be valid"

    def test_auto_fix_without_ai_context_warning(self) -> None:
        from src.guardrails.validator import validate_guardrail

        guardrail_dict = {
            "id": "GR-TEST-001",
            "short_description": "Test",
            "severity": "HIGH",
            "action": "AUTO-FIX",
            "applies_to": ["*"],
            "condition": {"attribute": "test", "operator": "exists"},
            # Missing ai_context
        }
        errors = validate_guardrail(guardrail_dict)
        # Should have a warning about missing ai_context
        assert any("ai_context" in e.lower() for e in errors)


class TestValidatePolicy:
    """Tests for validate_policy() (T026)."""

    def test_valid_policy(self) -> None:
        from src.guardrails.validator import validate_policy

        policy_dict = {
            "name": "production",
            "version": "1.0",
            "description": "Production policy",
            "guardrails": [
                {
                    "id": "GR-ENC-001",
                    "short_description": "S3 encryption",
                    "severity": "CRITICAL",
                    "action": "AUTO-FIX",
                    "applies_to": ["s3:bucket"],
                    "condition": {"attribute": "ServerSideEncryption", "operator": "exists"},
                    "ai_context": "WHY: Compliance",
                }
            ],
        }
        errors = validate_policy(policy_dict)
        assert errors == []

    def test_missing_name(self) -> None:
        from src.guardrails.validator import validate_policy

        policy_dict = {
            "version": "1.0",
            "guardrails": [],
        }
        errors = validate_policy(policy_dict)
        assert any("name" in e.lower() for e in errors)

    def test_missing_version(self) -> None:
        from src.guardrails.validator import validate_policy

        policy_dict = {
            "name": "test",
            "guardrails": [],
        }
        errors = validate_policy(policy_dict)
        assert any("version" in e.lower() for e in errors)

    def test_invalid_guardrail_in_policy(self) -> None:
        from src.guardrails.validator import validate_policy

        policy_dict = {
            "name": "test",
            "version": "1.0",
            "guardrails": [
                {
                    "id": "invalid",  # Invalid format
                    "short_description": "Test",
                    "severity": "HIGH",
                    "action": "BLOCK",
                    "applies_to": ["*"],
                    "condition": {"attribute": "test", "operator": "exists"},
                }
            ],
        }
        errors = validate_policy(policy_dict)
        assert len(errors) > 0

    def test_duplicate_guardrail_ids(self) -> None:
        from src.guardrails.validator import validate_policy

        policy_dict = {
            "name": "test",
            "version": "1.0",
            "guardrails": [
                {
                    "id": "GR-TEST-001",
                    "short_description": "First",
                    "severity": "HIGH",
                    "action": "BLOCK",
                    "applies_to": ["*"],
                    "condition": {"attribute": "test", "operator": "exists"},
                },
                {
                    "id": "GR-TEST-001",  # Duplicate
                    "short_description": "Second",
                    "severity": "HIGH",
                    "action": "BLOCK",
                    "applies_to": ["*"],
                    "condition": {"attribute": "test", "operator": "exists"},
                },
            ],
        }
        errors = validate_policy(policy_dict)
        assert any("duplicate" in e.lower() for e in errors)

    def test_valid_overrides(self) -> None:
        from src.guardrails.validator import validate_policy

        policy_dict = {
            "name": "test",
            "version": "1.0",
            "guardrails": [
                {
                    "id": "GR-TAG-001",
                    "short_description": "Tags required",
                    "severity": "HIGH",
                    "action": "WARN",
                    "applies_to": ["*"],
                    "condition": {"attribute": "Tags", "operator": "exists"},
                }
            ],
            "overrides": {
                "production": [
                    {"guardrail_id": "GR-TAG-001", "severity": "CRITICAL", "action": "BLOCK"}
                ]
            },
        }
        errors = validate_policy(policy_dict)
        assert errors == []

    def test_override_for_nonexistent_guardrail(self) -> None:
        from src.guardrails.validator import validate_policy

        policy_dict = {
            "name": "test",
            "version": "1.0",
            "guardrails": [
                {
                    "id": "GR-TAG-001",
                    "short_description": "Tags required",
                    "severity": "HIGH",
                    "action": "WARN",
                    "applies_to": ["*"],
                    "condition": {"attribute": "Tags", "operator": "exists"},
                }
            ],
            "overrides": {
                "production": [
                    {"guardrail_id": "GR-NONEXISTENT-001", "severity": "CRITICAL"}
                ]
            },
        }
        errors = validate_policy(policy_dict)
        assert any("nonexistent" in e.lower() or "not found" in e.lower() for e in errors)
