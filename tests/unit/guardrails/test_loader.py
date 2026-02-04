"""Unit tests for guardrails loader."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
import yaml


class TestLoadPolicy:
    """Tests for load_policy() (T027)."""

    def test_load_valid_policy(self, tmp_path: Path) -> None:
        from src.guardrails.loader import load_policy

        policy_yaml = """
name: test-policy
version: "1.0"
description: Test policy

guardrails:
  - id: GR-ENC-001
    short_description: "S3 bucket must have encryption"
    severity: CRITICAL
    action: AUTO-FIX
    applies_to:
      - s3:bucket
    condition:
      attribute: ServerSideEncryptionConfiguration
      operator: exists
    ai_context: "WHY: Compliance"
"""
        policy_file = tmp_path / "policy.yaml"
        policy_file.write_text(policy_yaml)

        policy = load_policy(str(policy_file))

        assert policy.name == "test-policy"
        assert policy.version == "1.0"
        assert len(policy.guardrails) == 1
        assert policy.guardrails[0].id == "GR-ENC-001"

    def test_load_policy_file_not_found(self) -> None:
        from src.guardrails.loader import load_policy
        from src.guardrails.models import GuardrailLoadError

        with pytest.raises(GuardrailLoadError) as exc_info:
            load_policy("/nonexistent/path/policy.yaml")

        assert "not found" in str(exc_info.value).lower()

    def test_load_policy_invalid_yaml(self, tmp_path: Path) -> None:
        from src.guardrails.loader import load_policy
        from src.guardrails.models import GuardrailLoadError

        policy_file = tmp_path / "invalid.yaml"
        policy_file.write_text("invalid: yaml: content: [unclosed")

        with pytest.raises(GuardrailLoadError):
            load_policy(str(policy_file))

    def test_load_policy_validation_error(self, tmp_path: Path) -> None:
        from src.guardrails.loader import load_policy
        from src.guardrails.models import GuardrailValidationError

        policy_yaml = """
name: invalid-policy
version: "1.0"
guardrails:
  - id: invalid-format
    short_description: "Test"
    severity: INVALID
    action: BLOCK
    applies_to: ["*"]
    condition:
      attribute: test
      operator: exists
"""
        policy_file = tmp_path / "invalid_policy.yaml"
        policy_file.write_text(policy_yaml)

        with pytest.raises(GuardrailValidationError):
            load_policy(str(policy_file))

    def test_load_policy_with_environment_overrides(self, tmp_path: Path) -> None:
        from src.guardrails.loader import load_policy
        from src.guardrails.models import Action, Severity

        policy_yaml = """
name: multi-env-policy
version: "1.0"

guardrails:
  - id: GR-TAG-001
    short_description: "Tags required"
    severity: HIGH
    action: WARN
    applies_to: ["*"]
    condition:
      attribute: Tags
      operator: exists

overrides:
  production:
    - guardrail_id: GR-TAG-001
      severity: CRITICAL
      action: BLOCK
"""
        policy_file = tmp_path / "policy.yaml"
        policy_file.write_text(policy_yaml)

        # Load for default env
        policy = load_policy(str(policy_file), environment="default")
        guardrails = policy.get_guardrails_for_env("default")
        assert guardrails[0].severity == Severity.HIGH
        assert guardrails[0].action == Action.WARN

        # Load for production env
        prod_guardrails = policy.get_guardrails_for_env("production")
        assert prod_guardrails[0].severity == Severity.CRITICAL
        assert prod_guardrails[0].action == Action.BLOCK

    def test_load_policy_with_disabled_guardrail(self, tmp_path: Path) -> None:
        from src.guardrails.loader import load_policy

        policy_yaml = """
name: test-policy
version: "1.0"

guardrails:
  - id: GR-TEST-001
    short_description: "Test"
    severity: HIGH
    action: BLOCK
    applies_to: ["*"]
    condition:
      attribute: test
      operator: exists

overrides:
  development:
    - guardrail_id: GR-TEST-001
      enabled: false
"""
        policy_file = tmp_path / "policy.yaml"
        policy_file.write_text(policy_yaml)

        policy = load_policy(str(policy_file))

        # Default env - guardrail active
        default_guardrails = policy.get_guardrails_for_env("default")
        assert len(default_guardrails) == 1

        # Development env - guardrail disabled
        dev_guardrails = policy.get_guardrails_for_env("development")
        assert len(dev_guardrails) == 0

    def test_load_policy_with_builtin_include(self, tmp_path: Path) -> None:
        from src.guardrails.loader import load_policy

        policy_yaml = """
name: test-policy
version: "1.0"

include:
  - builtin:encryption

guardrails:
  - id: ACME-SEC-001
    short_description: "Custom guardrail"
    severity: HIGH
    action: BLOCK
    applies_to: ["*"]
    condition:
      attribute: test
      operator: exists
"""
        policy_file = tmp_path / "policy.yaml"
        policy_file.write_text(policy_yaml)

        policy = load_policy(str(policy_file))

        # Should have both built-in and custom guardrails
        guardrail_ids = [g.id for g in policy.guardrails]
        assert "ACME-SEC-001" in guardrail_ids
        # Should have GR-ENC-* from builtin:encryption
        assert any(g_id.startswith("GR-ENC-") for g_id in guardrail_ids)


class TestLoadBuiltinGuardrails:
    """Tests for load_builtin_guardrails() (T028)."""

    def test_load_builtin_guardrails(self) -> None:
        from src.guardrails.loader import load_builtin_guardrails

        guardrails = load_builtin_guardrails()

        # Should have guardrails from all builtin categories
        ids = [g.id for g in guardrails]

        # Check encryption guardrails exist
        assert any(id.startswith("GR-ENC-") for id in ids)

        # Check network guardrails exist
        assert any(id.startswith("GR-NET-") for id in ids)

        # Check tagging guardrails exist
        assert any(id.startswith("GR-TAG-") for id in ids)

        # Check logging guardrails exist
        assert any(id.startswith("GR-LOG-") for id in ids)

    def test_builtin_guardrails_have_required_fields(self) -> None:
        from src.guardrails.loader import load_builtin_guardrails

        guardrails = load_builtin_guardrails()

        for g in guardrails:
            assert g.id, f"Guardrail missing id"
            assert g.short_description, f"Guardrail {g.id} missing short_description"
            assert g.severity, f"Guardrail {g.id} missing severity"
            assert g.action, f"Guardrail {g.id} missing action"
            assert g.applies_to, f"Guardrail {g.id} missing applies_to"
            assert g.condition, f"Guardrail {g.id} missing condition"

    def test_builtin_auto_fix_guardrails_have_ai_context(self) -> None:
        from src.guardrails.loader import load_builtin_guardrails
        from src.guardrails.models import Action

        guardrails = load_builtin_guardrails()
        auto_fix_guardrails = [g for g in guardrails if g.action == Action.AUTO_FIX]

        for g in auto_fix_guardrails:
            assert g.ai_context, f"AUTO-FIX guardrail {g.id} should have ai_context"
