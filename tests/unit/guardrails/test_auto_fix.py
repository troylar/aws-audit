"""Unit tests for guardrails auto-fix."""

from __future__ import annotations

from unittest.mock import MagicMock, patch


class TestAttemptAutoFix:
    """Tests for attempt_auto_fix() (T046)."""

    def _create_mock_guardrail(self, ai_context: str = ""):
        from src.guardrails.models import Action, Condition, Guardrail, Severity

        return Guardrail(
            id="GR-ENC-001",
            short_description="S3 encryption required",
            severity=Severity.CRITICAL,
            action=Action.AUTO_FIX,
            applies_to=["s3:bucket"],
            condition=Condition(attribute="ServerSideEncryption", operator="exists"),
            ai_context=ai_context,
        )

    def _create_mock_resource(self):
        mock_resource = MagicMock()
        mock_resource.resource_type = "s3:bucket"
        mock_resource.name = "my-bucket"
        mock_resource.arn = "arn:aws:s3:::my-bucket"
        mock_resource.config = {"BucketName": "my-bucket"}
        return mock_resource

    def test_attempt_auto_fix_no_ai_context(self) -> None:
        from src.guardrails.auto_fix import attempt_auto_fix

        guardrail = self._create_mock_guardrail(ai_context="")
        resource = self._create_mock_resource()

        success, fix, description = attempt_auto_fix(
            guardrail=guardrail,
            resource=resource,
            output_format="terraform",
            bedrock_client=None,
        )

        # Without ai_context, auto-fix should fail
        assert success is False
        assert fix == {}
        assert "ai_context" in description.lower() or "context" in description.lower()

    def test_attempt_auto_fix_no_bedrock_client(self) -> None:
        from src.guardrails.auto_fix import attempt_auto_fix

        guardrail = self._create_mock_guardrail(ai_context="WHY: Compliance\nHOW TO FIX: Add encryption")
        resource = self._create_mock_resource()

        success, fix, description = attempt_auto_fix(
            guardrail=guardrail,
            resource=resource,
            output_format="terraform",
            bedrock_client=None,
        )

        # Without Bedrock client, auto-fix should fail gracefully
        assert success is False

    @patch("src.guardrails.auto_fix._call_bedrock_for_fix")
    def test_attempt_auto_fix_success(self, mock_bedrock) -> None:
        from src.guardrails.auto_fix import attempt_auto_fix

        # Mock successful Bedrock response
        mock_bedrock.return_value = {
            "success": True,
            "fix": {"server_side_encryption_configuration": {"rule": {"sse_algorithm": "AES256"}}},
            "description": "Added AES256 encryption configuration",
        }

        guardrail = self._create_mock_guardrail(ai_context="WHY: Compliance\nHOW TO FIX: Add encryption")
        resource = self._create_mock_resource()
        mock_client = MagicMock()

        success, fix, description = attempt_auto_fix(
            guardrail=guardrail,
            resource=resource,
            output_format="terraform",
            bedrock_client=mock_client,
        )

        assert success is True
        assert "server_side_encryption_configuration" in fix
        assert "AES256" in description or "encryption" in description.lower()

    @patch("src.guardrails.auto_fix._call_bedrock_for_fix")
    def test_attempt_auto_fix_bedrock_error(self, mock_bedrock) -> None:
        from src.guardrails.auto_fix import attempt_auto_fix

        # Mock Bedrock failure
        mock_bedrock.return_value = {
            "success": False,
            "fix": {},
            "description": "Bedrock API error",
        }

        guardrail = self._create_mock_guardrail(ai_context="WHY: Compliance\nHOW TO FIX: Add encryption")
        resource = self._create_mock_resource()
        mock_client = MagicMock()

        success, fix, description = attempt_auto_fix(
            guardrail=guardrail,
            resource=resource,
            output_format="terraform",
            bedrock_client=mock_client,
        )

        assert success is False
        assert fix == {}
