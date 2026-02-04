"""Unit tests for guardrails reporter."""

from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestFormatTerminalReport:
    """Tests for format_terminal_report() (T045)."""

    def _create_mock_report(
        self,
        passed: int = 10,
        failed: int = 2,
        auto_fixed: int = 3,
        warnings: int = 1,
        blocked: bool = False,
    ):
        """Create a mock GuardrailReport for testing."""
        from src.guardrails.models import (
            Action,
            EvaluationResult,
            GuardrailEvaluation,
            GuardrailReport,
            ReportSummary,
            Severity,
        )

        report = GuardrailReport(
            run_id="test-run",
            policy_name="test-policy",
            policy_version="1.0",
            snapshot_name="test-snapshot",
            started_at=datetime(2026, 2, 4, 14, 30, 52, tzinfo=timezone.utc),
            completed_at=datetime(2026, 2, 4, 14, 31, 5, tzinfo=timezone.utc),
            summary=ReportSummary(
                total_resources=passed + failed + auto_fixed + warnings,
                total_evaluations=passed + failed + auto_fixed + warnings,
                passed=passed,
                failed=failed,
                auto_fixed=auto_fixed,
                warnings=warnings,
            ),
            blocked=blocked,
            block_reason="Critical violations found" if blocked else "",
        )

        # Add some mock evaluations
        if failed > 0:
            report.evaluations.append(
                GuardrailEvaluation(
                    guardrail_id="GR-NET-001",
                    guardrail_short_description="No SSH from 0.0.0.0/0",
                    severity=Severity.CRITICAL,
                    action=Action.BLOCK,
                    resource_type="ec2:security-group",
                    resource_name="web-sg",
                    resource_arn="arn:aws:ec2:...:sg/sg-123",
                    result=EvaluationResult.FAIL,
                    failure_reason="Port 22 allows 0.0.0.0/0",
                )
            )

        if auto_fixed > 0:
            report.evaluations.append(
                GuardrailEvaluation(
                    guardrail_id="GR-ENC-001",
                    guardrail_short_description="S3 encryption required",
                    severity=Severity.CRITICAL,
                    action=Action.AUTO_FIX,
                    resource_type="s3:bucket",
                    resource_name="my-bucket",
                    resource_arn="arn:aws:s3:::my-bucket",
                    result=EvaluationResult.AUTO_FIXED,
                    auto_fix_applied="Added AES256 encryption",
                )
            )

        return report

    def test_format_terminal_report_runs(self) -> None:
        from src.guardrails.reporter import format_terminal_report

        report = self._create_mock_report()

        # Should not raise - just verify it runs
        format_terminal_report(report)

    def test_format_terminal_report_with_console(self) -> None:
        from rich.console import Console

        from src.guardrails.reporter import format_terminal_report

        report = self._create_mock_report()
        console = Console(force_terminal=True, width=80)

        # Should not raise
        format_terminal_report(report, console=console)

    def test_format_terminal_report_blocked(self) -> None:
        from src.guardrails.reporter import format_terminal_report

        report = self._create_mock_report(blocked=True, failed=3)

        # Should not raise
        format_terminal_report(report)

    def test_format_terminal_report_all_passed(self) -> None:
        from src.guardrails.reporter import format_terminal_report

        report = self._create_mock_report(passed=20, failed=0, auto_fixed=0, warnings=0)

        # Should not raise
        format_terminal_report(report)


class TestSaveJsonReport:
    """Tests for save_json_report() (T076/US3)."""

    def test_save_json_report(self, tmp_path: Path) -> None:
        from src.guardrails.models import GuardrailReport, ReportSummary
        from src.guardrails.reporter import save_json_report

        report = GuardrailReport(
            run_id="test-run",
            policy_name="test-policy",
            policy_version="1.0",
            snapshot_name="test-snapshot",
            started_at=datetime(2026, 2, 4, 14, 30, 52, tzinfo=timezone.utc),
            completed_at=datetime(2026, 2, 4, 14, 31, 5, tzinfo=timezone.utc),
            summary=ReportSummary(total_resources=10, total_evaluations=50, passed=45, failed=5),
            blocked=False,
        )

        output_path = tmp_path / "report.json"
        save_json_report(report, str(output_path))

        assert output_path.exists()

        with open(output_path, "r") as f:
            data = json.load(f)

        assert data["run_id"] == "test-run"
        assert data["policy_name"] == "test-policy"
        assert data["summary"]["passed"] == 45
        assert data["summary"]["failed"] == 5


class TestSaveYamlReport:
    """Tests for save_yaml_report() (T077/US3)."""

    def test_save_yaml_report(self, tmp_path: Path) -> None:
        import yaml

        from src.guardrails.models import GuardrailReport, ReportSummary
        from src.guardrails.reporter import save_yaml_report

        report = GuardrailReport(
            run_id="test-run",
            policy_name="test-policy",
            policy_version="1.0",
            snapshot_name="test-snapshot",
            started_at=datetime(2026, 2, 4, 14, 30, 52, tzinfo=timezone.utc),
            completed_at=datetime(2026, 2, 4, 14, 31, 5, tzinfo=timezone.utc),
            summary=ReportSummary(total_resources=10, total_evaluations=50, passed=45, failed=5),
            blocked=False,
        )

        output_path = tmp_path / "report.yaml"
        save_yaml_report(report, str(output_path))

        assert output_path.exists()

        with open(output_path, "r") as f:
            data = yaml.safe_load(f)

        assert data["run_id"] == "test-run"
        assert data["policy_name"] == "test-policy"


class TestFormatGuardrailsTable:
    """Tests for format_guardrails_table() (T064/US6)."""

    def test_format_guardrails_table_runs(self) -> None:
        from src.guardrails.models import Action, Condition, Guardrail, Severity
        from src.guardrails.reporter import format_guardrails_table

        guardrails = [
            Guardrail(
                id="GR-ENC-001",
                short_description="S3 encryption required",
                severity=Severity.CRITICAL,
                action=Action.AUTO_FIX,
                applies_to=["s3:bucket"],
                condition=Condition(attribute="test", operator="exists"),
            ),
            Guardrail(
                id="GR-NET-001",
                short_description="No SSH from 0.0.0.0/0",
                severity=Severity.CRITICAL,
                action=Action.BLOCK,
                applies_to=["ec2:security-group"],
                condition=Condition(attribute="test", operator="exists"),
            ),
        ]

        # Should not raise
        format_guardrails_table(guardrails)

    def test_format_guardrails_table_empty(self) -> None:
        from src.guardrails.reporter import format_guardrails_table

        # Should handle empty list
        format_guardrails_table([])
