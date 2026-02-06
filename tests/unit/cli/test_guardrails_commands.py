"""Unit tests for guardrails CLI commands (T062-T063)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import click
import pytest
from rich.console import Console
from typer.testing import CliRunner

from src.cli.guardrails import _warn_missing_config
from src.cli.main import app

runner = CliRunner()


class TestGuardrailsCheckCommand:
    """Tests for `awsinv guardrails check` command."""

    def test_check_requires_snapshot_or_file(self) -> None:
        """Check command requires either snapshot name or --from-file."""
        result = runner.invoke(app, ["guardrails", "check"])
        assert result.exit_code != 0
        assert "snapshot" in result.stdout.lower() or "from-file" in result.stdout.lower()

    def test_check_with_nonexistent_snapshot(self) -> None:
        """Check command fails gracefully with nonexistent snapshot."""
        result = runner.invoke(app, ["guardrails", "check", "nonexistent-snapshot"])
        assert result.exit_code != 0

    @patch("src.cli.guardrails.load_policy")
    @patch("src.cli.guardrails.load_builtin_guardrails")
    @patch("src.cli.guardrails.GuardrailEvaluator")
    @patch("src.cli.guardrails.SnapshotStorage")
    def test_check_with_snapshot_no_violations(
        self,
        mock_storage_class: MagicMock,
        mock_evaluator_class: MagicMock,
        mock_load_builtin: MagicMock,
        mock_load_policy: MagicMock,
    ) -> None:
        """Check command returns 0 when no violations found."""
        # Setup mocks - return object with resources attribute
        mock_snapshot = MagicMock()
        mock_snapshot.resources = [{"resource_type": "s3:bucket", "name": "test", "config": {"BucketName": "test"}}]
        mock_storage = MagicMock()
        mock_storage.load_snapshot.return_value = mock_snapshot
        mock_storage_class.return_value = mock_storage

        mock_evaluator = MagicMock()
        mock_report = MagicMock()
        mock_report.blocked = False
        mock_report.summary.total = 1
        mock_report.summary.passed = 1
        mock_report.summary.failed = 0
        mock_report.summary.skipped = 0
        mock_report.summary.auto_fixed = 0
        mock_report.summary.warnings = 0
        mock_report.evaluations = []
        mock_report.get_blocking_violations.return_value = []
        mock_report.to_dict.return_value = {}
        mock_evaluator.evaluate_all.return_value = mock_report
        mock_evaluator_class.return_value = mock_evaluator

        mock_load_builtin.return_value = []

        result = runner.invoke(app, ["guardrails", "check", "test-snapshot"])
        assert result.exit_code == 0

    @patch("src.cli.guardrails.load_policy")
    @patch("src.cli.guardrails.load_builtin_guardrails")
    @patch("src.cli.guardrails.GuardrailEvaluator")
    @patch("src.cli.guardrails.SnapshotStorage")
    def test_check_with_violations_returns_exit_code_1(
        self,
        mock_storage_class: MagicMock,
        mock_evaluator_class: MagicMock,
        mock_load_builtin: MagicMock,
        mock_load_policy: MagicMock,
    ) -> None:
        """Check command returns 1 when CRITICAL/HIGH violations found."""
        from src.guardrails.models import Action, EvaluationResult, Severity

        # Setup mocks - return object with resources attribute
        mock_snapshot = MagicMock()
        mock_snapshot.resources = [{"resource_type": "s3:bucket", "name": "test", "config": {"BucketName": "test"}}]
        mock_storage = MagicMock()
        mock_storage.load_snapshot.return_value = mock_snapshot
        mock_storage_class.return_value = mock_storage

        mock_evaluator = MagicMock()
        mock_report = MagicMock()
        mock_report.blocked = True
        mock_report.summary.total = 1
        mock_report.summary.passed = 0
        mock_report.summary.failed = 1
        mock_report.summary.skipped = 0
        mock_report.summary.auto_fixed = 0
        mock_report.summary.warnings = 0
        mock_eval = MagicMock()
        mock_eval.result = EvaluationResult.FAIL
        mock_eval.severity = Severity.CRITICAL
        mock_eval.action = Action.BLOCK
        mock_eval.guardrail_id = "GR-TEST-001"
        mock_eval.guardrail_short_description = "Test"
        mock_eval.resource_type = "s3:bucket"
        mock_eval.resource_name = "test"
        mock_eval.failure_reason = "Test failure"
        mock_eval.is_blocking = True
        mock_report.evaluations = [mock_eval]
        mock_report.get_blocking_violations.return_value = [mock_eval]
        mock_report.to_dict.return_value = {}
        mock_evaluator.evaluate_all.return_value = mock_report
        mock_evaluator_class.return_value = mock_evaluator

        mock_load_builtin.return_value = []

        result = runner.invoke(app, ["guardrails", "check", "test-snapshot"])
        assert result.exit_code == 1

    @patch("src.cli.guardrails.load_policy")
    @patch("src.cli.guardrails.GuardrailEvaluator")
    @patch("src.cli.guardrails.SnapshotStorage")
    def test_check_with_custom_policy(
        self,
        mock_storage_class: MagicMock,
        mock_evaluator_class: MagicMock,
        mock_load_policy: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Check command loads custom policy when --policy specified."""
        policy_file = tmp_path / "policy.yaml"
        policy_file.write_text(
            """
name: test-policy
version: "1.0"
guardrails: []
"""
        )

        # Setup mocks - return object with resources attribute
        mock_snapshot = MagicMock()
        mock_snapshot.resources = []
        mock_storage = MagicMock()
        mock_storage.load_snapshot.return_value = mock_snapshot
        mock_storage_class.return_value = mock_storage

        mock_evaluator = MagicMock()
        mock_report = MagicMock()
        mock_report.blocked = False
        mock_report.summary.total = 0
        mock_report.summary.passed = 0
        mock_report.summary.failed = 0
        mock_report.summary.skipped = 0
        mock_report.summary.auto_fixed = 0
        mock_report.summary.warnings = 0
        mock_report.evaluations = []
        mock_report.get_blocking_violations.return_value = []
        mock_report.to_dict.return_value = {}
        mock_evaluator.evaluate_all.return_value = mock_report
        mock_evaluator_class.return_value = mock_evaluator

        mock_policy = MagicMock()
        mock_policy.guardrails = []
        mock_load_policy.return_value = mock_policy

        runner.invoke(app, ["guardrails", "check", "test-snapshot", "--policy", str(policy_file)])

        mock_load_policy.assert_called_once()
        assert str(policy_file) in str(mock_load_policy.call_args)

    @patch("src.cli.guardrails.load_policy")
    @patch("src.cli.guardrails.load_builtin_guardrails")
    @patch("src.cli.guardrails.GuardrailEvaluator")
    @patch("src.cli.guardrails.SnapshotStorage")
    def test_check_strict_mode_fails_on_any_violation(
        self,
        mock_storage_class: MagicMock,
        mock_evaluator_class: MagicMock,
        mock_load_builtin: MagicMock,
        mock_load_policy: MagicMock,
    ) -> None:
        """Check command with --strict returns 1 on any violation (even LOW)."""
        from src.guardrails.models import Action, EvaluationResult, Severity

        # Setup mocks - return object with resources attribute
        mock_snapshot = MagicMock()
        mock_snapshot.resources = [{"resource_type": "s3:bucket", "name": "test", "config": {"BucketName": "test"}}]
        mock_storage = MagicMock()
        mock_storage.load_snapshot.return_value = mock_snapshot
        mock_storage_class.return_value = mock_storage

        mock_evaluator = MagicMock()
        mock_report = MagicMock()
        mock_report.blocked = False  # Not normally blocking
        mock_report.summary.total = 1
        mock_report.summary.passed = 0
        mock_report.summary.failed = 1
        mock_report.summary.skipped = 0
        mock_report.summary.auto_fixed = 0
        mock_report.summary.warnings = 0
        mock_eval = MagicMock()
        mock_eval.result = EvaluationResult.FAIL
        mock_eval.severity = Severity.LOW  # LOW severity
        mock_eval.action = Action.WARN
        mock_eval.is_blocking = False
        mock_report.evaluations = [mock_eval]
        mock_report.get_blocking_violations.return_value = []
        mock_report.to_dict.return_value = {}
        mock_evaluator.evaluate_all.return_value = mock_report
        mock_evaluator_class.return_value = mock_evaluator

        mock_load_builtin.return_value = []

        result = runner.invoke(app, ["guardrails", "check", "test-snapshot", "--strict"])
        assert result.exit_code == 1

    @patch("src.cli.guardrails.load_builtin_guardrails")
    @patch("src.cli.guardrails.GuardrailEvaluator")
    def test_check_from_file(
        self,
        mock_evaluator_class: MagicMock,
        mock_load_builtin: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Check command works with --from-file option."""
        inventory_file = tmp_path / "inventory.yaml"
        inventory_file.write_text(
            """
resources:
  - resource_type: s3:bucket
    name: test-bucket
    config:
      BucketName: test-bucket
"""
        )

        mock_evaluator = MagicMock()
        mock_report = MagicMock()
        mock_report.blocked = False
        mock_report.summary.total = 1
        mock_report.summary.passed = 1
        mock_report.summary.failed = 0
        mock_report.summary.skipped = 0
        mock_report.summary.auto_fixed = 0
        mock_report.summary.warnings = 0
        mock_report.evaluations = []
        mock_report.get_blocking_violations.return_value = []
        mock_report.to_dict.return_value = {}
        mock_evaluator.evaluate_all.return_value = mock_report
        mock_evaluator_class.return_value = mock_evaluator

        mock_load_builtin.return_value = []

        result = runner.invoke(app, ["guardrails", "check", "--from-file", str(inventory_file)])
        assert result.exit_code == 0


class TestGuardrailsListCommand:
    """Tests for `awsinv guardrails list` command."""

    @patch("src.cli.guardrails.load_builtin_guardrails")
    def test_list_builtin_guardrails(self, mock_load_builtin: MagicMock) -> None:
        """List command shows built-in guardrails."""
        from src.guardrails.models import Action, Guardrail, Severity

        mock_load_builtin.return_value = [
            Guardrail(
                id="GR-ENC-001",
                short_description="S3 encryption required",
                severity=Severity.CRITICAL,
                action=Action.BLOCK,
                applies_to=["s3:bucket"],
                condition="Encryption exists",
            ),
        ]

        result = runner.invoke(app, ["guardrails", "list"])
        assert result.exit_code == 0
        assert "GR-ENC-001" in result.stdout

    @patch("src.cli.guardrails.load_policy")
    def test_list_with_custom_policy(self, mock_load_policy: MagicMock, tmp_path: Path) -> None:
        """List command shows guardrails from custom policy."""
        from src.guardrails.models import (
            Action,
            Guardrail,
            GuardrailPolicy,
            Severity,
        )

        policy_file = tmp_path / "policy.yaml"
        policy_file.write_text("name: test\nversion: '1.0'\nguardrails: []")

        mock_policy = GuardrailPolicy(
            name="test",
            version="1.0",
            guardrails=[
                Guardrail(
                    id="ACME-SEC-001",
                    short_description="Custom guardrail",
                    severity=Severity.HIGH,
                    action=Action.WARN,
                    applies_to=["*"],
                    condition="Tags.Owner exists",
                ),
            ],
        )
        mock_load_policy.return_value = mock_policy

        result = runner.invoke(app, ["guardrails", "list", "--policy", str(policy_file)])
        assert result.exit_code == 0
        assert "ACME-SEC-001" in result.stdout

    @patch("src.cli.guardrails.load_builtin_guardrails")
    def test_list_filter_by_severity(self, mock_load_builtin: MagicMock) -> None:
        """List command filters by --severity."""
        from src.guardrails.models import Action, Guardrail, Severity

        mock_load_builtin.return_value = [
            Guardrail(
                id="GR-ENC-001",
                short_description="Critical guardrail",
                severity=Severity.CRITICAL,
                action=Action.BLOCK,
                applies_to=["s3:bucket"],
                condition="Encryption exists",
            ),
            Guardrail(
                id="GR-TAG-001",
                short_description="Low guardrail",
                severity=Severity.LOW,
                action=Action.WARN,
                applies_to=["*"],
                condition="Tags exists",
            ),
        ]

        result = runner.invoke(app, ["guardrails", "list", "--severity", "CRITICAL"])
        assert result.exit_code == 0
        assert "GR-ENC-001" in result.stdout
        assert "GR-TAG-001" not in result.stdout

    @patch("src.cli.guardrails.load_builtin_guardrails")
    def test_list_filter_by_category(self, mock_load_builtin: MagicMock) -> None:
        """List command filters by --category."""
        from src.guardrails.models import Action, Guardrail, Severity

        mock_load_builtin.return_value = [
            Guardrail(
                id="GR-ENC-001",
                short_description="Encryption guardrail",
                severity=Severity.CRITICAL,
                action=Action.BLOCK,
                applies_to=["s3:bucket"],
                condition="Encryption exists",
            ),
            Guardrail(
                id="GR-NET-001",
                short_description="Network guardrail",
                severity=Severity.HIGH,
                action=Action.BLOCK,
                applies_to=["ec2:security-group"],
                condition="IpPermissions exists",
            ),
        ]

        result = runner.invoke(app, ["guardrails", "list", "--category", "ENC"])
        assert result.exit_code == 0
        assert "GR-ENC-001" in result.stdout
        assert "GR-NET-001" not in result.stdout

    @patch("src.cli.guardrails.load_builtin_guardrails")
    def test_list_json_format(self, mock_load_builtin: MagicMock) -> None:
        """List command outputs JSON with --format json."""
        from src.guardrails.models import Action, Guardrail, Severity

        mock_load_builtin.return_value = [
            Guardrail(
                id="GR-ENC-001",
                short_description="Test guardrail",
                severity=Severity.CRITICAL,
                action=Action.BLOCK,
                applies_to=["s3:bucket"],
                condition="Encryption exists",
            ),
        ]

        result = runner.invoke(app, ["guardrails", "list", "--format", "json"])
        assert result.exit_code == 0
        assert '"id": "GR-ENC-001"' in result.stdout or '"id":"GR-ENC-001"' in result.stdout


class TestGuardrailsCommandHelp:
    """Tests for guardrails command help."""

    def test_guardrails_help(self) -> None:
        """Guardrails command group shows help."""
        result = runner.invoke(app, ["guardrails", "--help"])
        assert result.exit_code == 0
        assert "check" in result.stdout
        assert "list" in result.stdout

    def test_guardrails_check_help(self) -> None:
        """Check command shows help with all options."""
        result = runner.invoke(app, ["guardrails", "check", "--help"])
        assert result.exit_code == 0
        assert "--policy" in result.stdout
        assert "--env" in result.stdout
        assert "--strict" in result.stdout
        assert "--format" in result.stdout

    def test_guardrails_list_help(self) -> None:
        """List command shows help with all options."""
        result = runner.invoke(app, ["guardrails", "list", "--help"])
        assert result.exit_code == 0
        assert "--policy" in result.stdout
        assert "--severity" in result.stdout
        assert "--category" in result.stdout
        assert "--format" in result.stdout


class TestWarnMissingConfig:
    """Tests for _warn_missing_config validation helper."""

    def _make_resource(self, config: object = None, raw_config: object = None) -> MagicMock:
        r = MagicMock()
        r.config = config
        r.raw_config = raw_config
        return r

    def test_empty_list_returns_zero(self) -> None:
        assert _warn_missing_config([], Console()) == 0

    def test_all_have_config_returns_zero(self) -> None:
        resources = [self._make_resource(config={"BucketName": "x"})]
        assert _warn_missing_config(resources, Console()) == 0

    def test_all_have_raw_config_returns_zero(self) -> None:
        resources = [self._make_resource(raw_config={"BucketName": "x"})]
        assert _warn_missing_config(resources, Console()) == 0

    def test_all_missing_config_exits_1(self) -> None:
        resources = [
            self._make_resource(config=None, raw_config=None),
            self._make_resource(config={}, raw_config={}),
        ]
        with pytest.raises(click.exceptions.Exit):
            _warn_missing_config(resources, Console())

    def test_some_missing_config_returns_count(self) -> None:
        resources = [
            self._make_resource(config={"BucketName": "x"}),
            self._make_resource(config=None, raw_config=None),
        ]
        assert _warn_missing_config(resources, Console()) == 1

    def test_all_missing_error_message(self, capsys: pytest.CaptureFixture[str]) -> None:
        resources = [self._make_resource(config=None, raw_config=None)]
        con = Console()
        with pytest.raises(click.exceptions.Exit):
            _warn_missing_config(resources, con)

    @patch("src.cli.guardrails.load_builtin_guardrails")
    @patch("src.cli.guardrails.GuardrailEvaluator")
    def test_check_from_file_all_missing_config_exits_1(
        self,
        mock_evaluator_class: MagicMock,
        mock_load_builtin: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Check command exits 1 when all resources lack config data."""
        inventory_file = tmp_path / "inventory.yaml"
        inventory_file.write_text(
            """
resources:
  - resource_type: s3:bucket
    name: test-bucket
"""
        )
        mock_load_builtin.return_value = []

        result = runner.invoke(app, ["guardrails", "check", "--from-file", str(inventory_file)])
        assert result.exit_code == 1
        assert "no configuration data" in result.stdout
