"""Unit tests for evaluate_guardrails LangGraph node (T044)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock


class TestEvaluateGuardrailsNode:
    """Tests for evaluate_guardrails LangGraph node."""

    def _create_mock_resource(
        self,
        resource_type: str = "s3:bucket",
        name: str = "test-bucket",
        config: dict | None = None,
    ):
        mock = MagicMock()
        mock.resource_type = resource_type
        mock.name = name
        mock.arn = f"arn:aws:{resource_type.split(':')[0]}::::{name}"
        mock.config = config or {}
        return mock

    def test_evaluate_guardrails_disabled(self) -> None:
        from src.generate.nodes.evaluate_guardrails import evaluate_guardrails

        state = {
            "guardrails_enabled": False,
            "best_practices_enabled": False,
            "resources": [self._create_mock_resource()],
            "snapshot_name": "test-snapshot",
        }

        result = evaluate_guardrails(state)

        # Should skip guardrails and return unchanged state
        assert result.get("guardrails_blocked") is False
        assert result.get("guardrails_report") is None

    def test_evaluate_best_practices_mode(self) -> None:
        """Best-practice mode runs advisory checks (WARN only, never blocks)."""
        from src.generate.nodes.evaluate_guardrails import evaluate_guardrails

        # Resource without encryption - would be BLOCK in enforcement mode
        resource = self._create_mock_resource(config={})

        state = {
            "guardrails_enabled": False,
            "best_practices_enabled": True,
            "resources": [resource],
            "snapshot_name": "test-snapshot",
            "output_format": "terraform",
        }

        result = evaluate_guardrails(state)

        # Should NOT be blocked (best practices never block)
        assert result.get("guardrails_blocked") is False
        # But should have a report with evaluations
        assert result.get("guardrails_report") is not None
        report = result["guardrails_report"]
        # All actions should be WARN in best-practice mode
        for evaluation in report.get("evaluations", []):
            assert evaluation["action"] == "WARN"

    def test_evaluate_guardrails_no_resources(self) -> None:
        from src.generate.nodes.evaluate_guardrails import evaluate_guardrails

        state = {
            "guardrails_enabled": True,
            "resources": [],
            "snapshot_name": "test-snapshot",
        }

        result = evaluate_guardrails(state)

        assert result.get("guardrails_blocked") is False
        assert result.get("guardrails_report") is not None

    def test_evaluate_guardrails_with_builtin(self) -> None:
        from src.generate.nodes.evaluate_guardrails import evaluate_guardrails

        # Create resource with encryption (should pass GR-ENC-001)
        resource_with_encryption = self._create_mock_resource(
            config={"ServerSideEncryptionConfiguration": {"Rule": {}}}
        )

        state = {
            "guardrails_enabled": True,
            "guardrails_policy_path": None,  # Use built-in
            "guardrails_environment": "default",
            "resources": [resource_with_encryption],
            "snapshot_name": "test-snapshot",
            "output_format": "terraform",
        }

        result = evaluate_guardrails(state)

        assert "guardrails_report" in result
        assert "guardrails_blocked" in result

    def test_evaluate_guardrails_with_violation(self, tmp_path: Path) -> None:
        from src.generate.nodes.evaluate_guardrails import evaluate_guardrails

        # Create a simple policy
        policy_yaml = """
name: test-policy
version: "1.0"
guardrails:
  - id: GR-TEST-001
    short_description: "Test must have attribute X"
    severity: CRITICAL
    action: BLOCK
    applies_to:
      - s3:bucket
    condition:
      attribute: RequiredAttribute
      operator: exists
"""
        policy_file = tmp_path / "policy.yaml"
        policy_file.write_text(policy_yaml)

        # Create resource WITHOUT required attribute
        resource = self._create_mock_resource(config={})

        state = {
            "guardrails_enabled": True,
            "guardrails_policy_path": str(policy_file),
            "guardrails_environment": "default",
            "resources": [resource],
            "snapshot_name": "test-snapshot",
            "output_format": "terraform",
        }

        result = evaluate_guardrails(state)

        # Should be blocked due to CRITICAL violation
        assert result.get("guardrails_blocked") is True
        assert result.get("guardrails_report", {}).get("blocked") is True

    def test_evaluate_guardrails_passing(self, tmp_path: Path) -> None:
        from src.generate.nodes.evaluate_guardrails import evaluate_guardrails

        # Create a simple policy
        policy_yaml = """
name: test-policy
version: "1.0"
guardrails:
  - id: GR-TEST-001
    short_description: "Test must have attribute X"
    severity: CRITICAL
    action: BLOCK
    applies_to:
      - s3:bucket
    condition:
      attribute: RequiredAttribute
      operator: exists
"""
        policy_file = tmp_path / "policy.yaml"
        policy_file.write_text(policy_yaml)

        # Create resource WITH required attribute
        resource = self._create_mock_resource(config={"RequiredAttribute": "value"})

        state = {
            "guardrails_enabled": True,
            "guardrails_policy_path": str(policy_file),
            "guardrails_environment": "default",
            "resources": [resource],
            "snapshot_name": "test-snapshot",
            "output_format": "terraform",
        }

        result = evaluate_guardrails(state)

        # Should NOT be blocked
        assert result.get("guardrails_blocked") is False

    def test_evaluate_guardrails_strict_mode(self, tmp_path: Path) -> None:
        from src.generate.nodes.evaluate_guardrails import evaluate_guardrails

        # Create a policy with LOW severity WARN action
        policy_yaml = """
name: test-policy
version: "1.0"
guardrails:
  - id: GR-TEST-001
    short_description: "Test attribute"
    severity: LOW
    action: WARN
    applies_to:
      - s3:bucket
    condition:
      attribute: SomeAttribute
      operator: exists
"""
        policy_file = tmp_path / "policy.yaml"
        policy_file.write_text(policy_yaml)

        # Create resource without attribute
        resource = self._create_mock_resource(config={})

        state = {
            "guardrails_enabled": True,
            "guardrails_policy_path": str(policy_file),
            "guardrails_environment": "default",
            "guardrails_strict": True,  # Strict mode
            "resources": [resource],
            "snapshot_name": "test-snapshot",
            "output_format": "terraform",
        }

        result = evaluate_guardrails(state)

        # In strict mode, even LOW/WARN violations should block
        assert result.get("guardrails_blocked") is True
