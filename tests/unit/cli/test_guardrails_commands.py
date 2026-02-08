"""Unit tests for guardrails CLI commands (T062-T063)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import click
import pytest
from rich.console import Console
from typer.testing import CliRunner

from src.cli.guardrails import (
    GuardrailsProgressDisplay,
    _print_error_tip,
    _warn_missing_config,
)
from src.cli.main import app

runner = CliRunner()


def _strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


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
        output = _strip_ansi(result.stdout)
        assert "--policy" in output
        assert "--env" in output
        assert "--strict" in output
        assert "--format" in output

    def test_guardrails_list_help(self) -> None:
        """List command shows help with all options."""
        result = runner.invoke(app, ["guardrails", "list", "--help"])
        assert result.exit_code == 0
        output = _strip_ansi(result.stdout)
        assert "--policy" in output
        assert "--severity" in output
        assert "--category" in output
        assert "--format" in output


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


class TestGuardrailsProgressDisplay:
    """Tests for GuardrailsProgressDisplay."""

    def test_build_display_with_current_resource_and_guardrail(self) -> None:
        """Build display shows current resource and guardrail when set."""
        con = Console()
        display = GuardrailsProgressDisplay(con, total_resources=5, total_guardrails=3)
        display.current_resource_name = "my-bucket"
        display.current_guardrail = "GR-ENC-001"
        group = display._build_display()
        assert group is not None

    def test_build_display_with_guardrail_only(self) -> None:
        """Build display shows guardrail without resource name."""
        con = Console()
        display = GuardrailsProgressDisplay(con, total_resources=2, total_guardrails=1)
        display.current_guardrail = "GR-NET-001"
        group = display._build_display()
        assert group is not None

    def test_build_display_with_auto_fixed_and_warnings(self) -> None:
        """Build display shows auto_fixed and warnings counts when > 0."""
        con = Console()
        display = GuardrailsProgressDisplay(con, total_resources=5, total_guardrails=3)
        display.auto_fixed = 2
        display.warnings = 3
        group = display._build_display()
        assert group is not None

    def test_update_sets_fields_and_refreshes_live(self) -> None:
        """Update method sets all fields and calls live.update when live is active."""
        con = Console()
        display = GuardrailsProgressDisplay(con, total_resources=5, total_guardrails=3)
        display.live = MagicMock()

        display.update(
            current=2,
            total=5,
            guardrail_id="GR-ENC-001",
            resource_name="my-bucket",
            passed=1,
            failed=2,
            auto_fixed=1,
            warnings=1,
        )

        assert display.current_resource == 2
        assert display.current_guardrail == "GR-ENC-001"
        assert display.current_resource_name == "my-bucket"
        assert display.passed == 1
        assert display.failed == 2
        assert display.auto_fixed == 1
        assert display.warnings == 1
        display.live.update.assert_called_once()

    def test_update_without_live_does_not_error(self) -> None:
        """Update method works when live display is not started."""
        con = Console()
        display = GuardrailsProgressDisplay(con, total_resources=5, total_guardrails=3)
        display.update(current=1, total=5)
        assert display.current_resource == 1


class TestCheckCommandFromFile:
    """Additional tests for check command --from-file scenarios."""

    def test_check_from_file_nonexistent(self) -> None:
        """Check with --from-file pointing to nonexistent file exits 1."""
        result = runner.invoke(app, ["guardrails", "check", "--from-file", "/nonexistent/path/file.yaml"])
        assert result.exit_code == 1
        assert "not found" in result.stdout.lower() or "error" in result.stdout.lower()

    @patch("src.cli.guardrails.format_terminal_report")
    @patch("src.cli.guardrails.load_builtin_guardrails")
    @patch("src.cli.guardrails.GuardrailEvaluator")
    def test_check_from_json_file(
        self,
        mock_evaluator_class: MagicMock,
        mock_load_builtin: MagicMock,
        mock_format_report: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Check command loads JSON file when --from-file has .json extension."""
        inventory_file = tmp_path / "inventory.json"
        data = {"resources": [{"resource_type": "s3:bucket", "name": "test", "config": {"BucketName": "test"}}]}
        inventory_file.write_text(json.dumps(data))

        mock_evaluator = MagicMock()
        mock_report = MagicMock()
        mock_report.blocked = False
        mock_report.summary.total = 1
        mock_report.summary.passed = 1
        mock_report.summary.failed = 0
        mock_report.to_dict.return_value = {}
        mock_evaluator.evaluate_all.return_value = mock_report
        mock_evaluator_class.return_value = mock_evaluator
        mock_load_builtin.return_value = []

        result = runner.invoke(app, ["guardrails", "check", "--from-file", str(inventory_file)])
        assert result.exit_code == 0

    @patch("src.cli.guardrails.format_terminal_report")
    @patch("src.cli.guardrails.load_builtin_guardrails")
    @patch("src.cli.guardrails.GuardrailEvaluator")
    def test_check_from_file_list_format(
        self,
        mock_evaluator_class: MagicMock,
        mock_load_builtin: MagicMock,
        mock_format_report: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Check command handles file containing a list of resources (not dict)."""
        inventory_file = tmp_path / "inventory.yaml"
        inventory_file.write_text(
            """
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
        mock_report.to_dict.return_value = {}
        mock_evaluator.evaluate_all.return_value = mock_report
        mock_evaluator_class.return_value = mock_evaluator
        mock_load_builtin.return_value = []

        result = runner.invoke(app, ["guardrails", "check", "--from-file", str(inventory_file)])
        assert result.exit_code == 0

    @patch("src.cli.guardrails.load_builtin_guardrails")
    @patch("src.cli.guardrails.GuardrailEvaluator")
    def test_check_from_file_invalid_content(
        self,
        mock_evaluator_class: MagicMock,
        mock_load_builtin: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Check command exits 1 when file content is invalid."""
        inventory_file = tmp_path / "inventory.json"
        inventory_file.write_text("{invalid json content")

        mock_load_builtin.return_value = []

        result = runner.invoke(app, ["guardrails", "check", "--from-file", str(inventory_file)])
        assert result.exit_code == 1
        assert "failed to load" in result.stdout.lower()

    @patch("src.cli.guardrails.load_builtin_guardrails")
    @patch("src.cli.guardrails.GuardrailEvaluator")
    @patch("src.cli.guardrails.SnapshotStorage")
    def test_check_snapshot_not_found(
        self,
        mock_storage_class: MagicMock,
        mock_evaluator_class: MagicMock,
        mock_load_builtin: MagicMock,
    ) -> None:
        """Check command exits 1 when snapshot is not found."""
        mock_storage = MagicMock()
        mock_storage.load_snapshot.return_value = None
        mock_storage_class.return_value = mock_storage
        mock_load_builtin.return_value = []

        result = runner.invoke(app, ["guardrails", "check", "missing-snapshot"])
        assert result.exit_code == 1
        assert "not found" in result.stdout.lower() or "error" in result.stdout.lower()

    @patch("src.cli.guardrails.load_builtin_guardrails")
    @patch("src.cli.guardrails.GuardrailEvaluator")
    @patch("src.cli.guardrails.SnapshotStorage")
    def test_check_snapshot_load_exception(
        self,
        mock_storage_class: MagicMock,
        mock_evaluator_class: MagicMock,
        mock_load_builtin: MagicMock,
    ) -> None:
        """Check command exits 1 when snapshot load raises exception."""
        mock_storage = MagicMock()
        mock_storage.load_snapshot.side_effect = Exception("Storage error")
        mock_storage_class.return_value = mock_storage
        mock_load_builtin.return_value = []

        result = runner.invoke(app, ["guardrails", "check", "broken-snapshot"])
        assert result.exit_code == 1

    def test_check_policy_file_not_found(self, tmp_path: Path) -> None:
        """Check command exits 1 when --policy file does not exist."""
        result = runner.invoke(
            app,
            ["guardrails", "check", "test-snap", "--policy", "/nonexistent/policy.yaml"],
        )
        assert result.exit_code == 1


class TestCheckCommandOutputFormats:
    """Tests for check command output format options."""

    def _setup_check_mocks(
        self, mock_storage_class: MagicMock, mock_evaluator_class: MagicMock, mock_load_builtin: MagicMock
    ) -> None:
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
        mock_report.to_dict.return_value = {"summary": {"total": 1, "passed": 1}}
        mock_evaluator.evaluate_all.return_value = mock_report
        mock_evaluator_class.return_value = mock_evaluator
        mock_load_builtin.return_value = []

    @patch("src.cli.guardrails.load_builtin_guardrails")
    @patch("src.cli.guardrails.GuardrailEvaluator")
    @patch("src.cli.guardrails.SnapshotStorage")
    def test_check_json_format(
        self,
        mock_storage_class: MagicMock,
        mock_evaluator_class: MagicMock,
        mock_load_builtin: MagicMock,
    ) -> None:
        """Check command outputs JSON when --format json is specified."""
        self._setup_check_mocks(mock_storage_class, mock_evaluator_class, mock_load_builtin)
        result = runner.invoke(app, ["guardrails", "check", "test-snapshot", "--format", "json"])
        assert result.exit_code == 0
        assert "summary" in result.stdout

    @patch("src.cli.guardrails.load_builtin_guardrails")
    @patch("src.cli.guardrails.GuardrailEvaluator")
    @patch("src.cli.guardrails.SnapshotStorage")
    def test_check_yaml_format(
        self,
        mock_storage_class: MagicMock,
        mock_evaluator_class: MagicMock,
        mock_load_builtin: MagicMock,
    ) -> None:
        """Check command outputs YAML when --format yaml is specified."""
        self._setup_check_mocks(mock_storage_class, mock_evaluator_class, mock_load_builtin)
        result = runner.invoke(app, ["guardrails", "check", "test-snapshot", "--format", "yaml"])
        assert result.exit_code == 0
        assert "summary" in result.stdout

    @patch("src.cli.guardrails.format_terminal_report")
    @patch("src.cli.guardrails.load_builtin_guardrails")
    @patch("src.cli.guardrails.GuardrailEvaluator")
    @patch("src.cli.guardrails.SnapshotStorage")
    def test_check_output_to_json_file(
        self,
        mock_storage_class: MagicMock,
        mock_evaluator_class: MagicMock,
        mock_load_builtin: MagicMock,
        mock_format_report: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Check command saves report to JSON file with --output."""
        self._setup_check_mocks(mock_storage_class, mock_evaluator_class, mock_load_builtin)
        output_file = tmp_path / "report.json"
        result = runner.invoke(
            app,
            ["guardrails", "check", "test-snapshot", "--output", str(output_file)],
        )
        assert result.exit_code == 0
        assert output_file.exists()
        data = json.loads(output_file.read_text())
        assert "summary" in data

    @patch("src.cli.guardrails.format_terminal_report")
    @patch("src.cli.guardrails.load_builtin_guardrails")
    @patch("src.cli.guardrails.GuardrailEvaluator")
    @patch("src.cli.guardrails.SnapshotStorage")
    def test_check_output_to_yaml_file(
        self,
        mock_storage_class: MagicMock,
        mock_evaluator_class: MagicMock,
        mock_load_builtin: MagicMock,
        mock_format_report: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Check command saves report to YAML file with --output."""
        self._setup_check_mocks(mock_storage_class, mock_evaluator_class, mock_load_builtin)
        output_file = tmp_path / "report.yaml"
        result = runner.invoke(
            app,
            ["guardrails", "check", "test-snapshot", "--output", str(output_file)],
        )
        assert result.exit_code == 0
        assert output_file.exists()
        assert "saved to" in result.stdout.lower() or "report" in result.stdout.lower()


class TestListCommandAdditional:
    """Additional tests for the list command."""

    def test_list_policy_not_found(self) -> None:
        """List command exits 1 when --policy file does not exist."""
        result = runner.invoke(app, ["guardrails", "list", "--policy", "/nonexistent/policy.yaml"])
        assert result.exit_code == 1
        assert "not found" in result.stdout.lower()

    @patch("src.cli.guardrails.load_builtin_guardrails")
    def test_list_invalid_severity(self, mock_load_builtin: MagicMock) -> None:
        """List command exits 1 with invalid severity value."""
        from src.guardrails.models import Action, Guardrail, Severity

        mock_load_builtin.return_value = [
            Guardrail(
                id="GR-ENC-001",
                short_description="Test",
                severity=Severity.CRITICAL,
                action=Action.BLOCK,
                applies_to=["s3:bucket"],
                condition="Encryption exists",
            ),
        ]

        result = runner.invoke(app, ["guardrails", "list", "--severity", "INVALID"])
        assert result.exit_code == 1
        assert "invalid severity" in result.stdout.lower()

    @patch("src.cli.guardrails.load_builtin_guardrails")
    def test_list_yaml_format(self, mock_load_builtin: MagicMock) -> None:
        """List command outputs YAML with --format yaml."""
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

        result = runner.invoke(app, ["guardrails", "list", "--format", "yaml"])
        assert result.exit_code == 0
        assert "GR-ENC-001" in result.stdout

    @patch("src.cli.guardrails.load_builtin_guardrails")
    def test_list_no_matching_guardrails(self, mock_load_builtin: MagicMock) -> None:
        """List command shows message when no guardrails match filter criteria."""
        from src.guardrails.models import Action, Guardrail, Severity

        mock_load_builtin.return_value = [
            Guardrail(
                id="GR-ENC-001",
                short_description="Test",
                severity=Severity.CRITICAL,
                action=Action.BLOCK,
                applies_to=["s3:bucket"],
                condition="Encryption exists",
            ),
        ]

        result = runner.invoke(app, ["guardrails", "list", "--category", "ZZZ"])
        assert result.exit_code == 0
        assert "no guardrails found" in result.stdout.lower()


class TestValidateCommand:
    """Tests for `awsinv guardrails validate` command."""

    def test_validate_file_not_found(self) -> None:
        """Validate exits 1 when policy file does not exist."""
        result = runner.invoke(app, ["guardrails", "validate", "/nonexistent/policy.yaml"])
        assert result.exit_code == 1
        assert "not found" in result.stdout.lower()

    def test_validate_invalid_yaml_syntax(self, tmp_path: Path) -> None:
        """Validate exits 1 on YAML syntax error."""
        bad_file = tmp_path / "bad.yaml"
        bad_file.write_text(":\n  invalid: yaml:\n  - [unbalanced")

        result = runner.invoke(app, ["guardrails", "validate", str(bad_file)])
        assert result.exit_code == 1
        assert "yaml" in result.stdout.lower() or "syntax" in result.stdout.lower()

    def test_validate_empty_file(self, tmp_path: Path) -> None:
        """Validate exits 1 on empty policy file."""
        empty_file = tmp_path / "empty.yaml"
        empty_file.write_text("")

        result = runner.invoke(app, ["guardrails", "validate", str(empty_file)])
        assert result.exit_code == 1
        assert "empty" in result.stdout.lower()

    @patch("src.guardrails.validator.validate_policy")
    def test_validate_with_errors(self, mock_validate: MagicMock, tmp_path: Path) -> None:
        """Validate exits 1 and shows errors when policy has issues."""
        policy_file = tmp_path / "policy.yaml"
        policy_file.write_text("name: test\nversion: '1.0'\nguardrails: []\n")

        mock_validate.return_value = ["Missing required field: guardrails"]

        result = runner.invoke(app, ["guardrails", "validate", str(policy_file)])
        assert result.exit_code == 1
        assert "error" in result.stdout.lower()

    @patch("src.guardrails.validator.validate_policy")
    def test_validate_with_guardrail_errors_grouped(self, mock_validate: MagicMock, tmp_path: Path) -> None:
        """Validate groups errors by guardrail ID."""
        policy_file = tmp_path / "policy.yaml"
        policy_file.write_text("name: test\nversion: '1.0'\nguardrails:\n  - id: GR-ENC-001\n    severity: INVALID\n")

        mock_validate.return_value = [
            "guardrails[0]: Invalid severity value",
            "guardrails[0]: Missing condition",
        ]

        result = runner.invoke(app, ["guardrails", "validate", str(policy_file)])
        assert result.exit_code == 1
        assert "GR-ENC-001" in result.stdout

    @patch("src.guardrails.validator.validate_policy")
    def test_validate_with_guardrail_errors_verbose(self, mock_validate: MagicMock, tmp_path: Path) -> None:
        """Validate shows tips for common errors in verbose mode."""
        policy_file = tmp_path / "policy.yaml"
        policy_file.write_text("name: test\nversion: '1.0'\nguardrails:\n  - id: GR-ENC-001\n    severity: INVALID\n")

        mock_validate.return_value = [
            "guardrails[0]: Invalid severity value",
        ]

        result = runner.invoke(app, ["guardrails", "validate", str(policy_file), "--verbose"])
        assert result.exit_code == 1

    @patch("src.guardrails.validator.validate_policy")
    def test_validate_valid_policy(self, mock_validate: MagicMock, tmp_path: Path) -> None:
        """Validate exits 0 and shows summary for valid policy."""
        policy_file = tmp_path / "policy.yaml"
        policy_file.write_text(
            "name: my-policy\nversion: '2.0'\nguardrails:\n"
            "  - id: GR-ENC-001\n    action: BLOCK\noverrides:\n  prod:\n    some: val\n"
            "context:\n  region: us-east-1\n"
        )

        mock_validate.return_value = []

        result = runner.invoke(app, ["guardrails", "validate", str(policy_file)])
        assert result.exit_code == 0
        assert "valid" in result.stdout.lower()
        assert "my-policy" in result.stdout
        assert "2.0" in result.stdout

    @patch("src.guardrails.validator.validate_policy")
    def test_validate_valid_policy_shows_action_breakdown(self, mock_validate: MagicMock, tmp_path: Path) -> None:
        """Validate shows action breakdown for valid policy with guardrails."""
        policy_file = tmp_path / "policy.yaml"
        policy_file.write_text(
            "name: test\nversion: '1.0'\n"
            "guardrails:\n"
            "  - id: GR-ENC-001\n    action: BLOCK\n"
            "  - id: GR-NET-001\n    action: WARN\n"
        )

        mock_validate.return_value = []

        result = runner.invoke(app, ["guardrails", "validate", str(policy_file)])
        assert result.exit_code == 0
        assert "BLOCK" in result.stdout or "WARN" in result.stdout

    @patch("src.guardrails.validator.validate_policy")
    def test_validate_errors_with_condition_tip(self, mock_validate: MagicMock, tmp_path: Path) -> None:
        """Validate shows formula syntax tip when condition errors present."""
        policy_file = tmp_path / "policy.yaml"
        policy_file.write_text("name: test\nversion: '1.0'\nguardrails: []\n")

        mock_validate.return_value = ["Invalid condition formula in guardrail"]

        result = runner.invoke(app, ["guardrails", "validate", str(policy_file)])
        assert result.exit_code == 1

    @patch("src.guardrails.validator.validate_policy")
    def test_validate_errors_with_id_pattern_tip(self, mock_validate: MagicMock, tmp_path: Path) -> None:
        """Validate shows ID pattern tip when ID errors present."""
        policy_file = tmp_path / "policy.yaml"
        policy_file.write_text("name: test\nversion: '1.0'\nguardrails: []\n")

        mock_validate.return_value = ["id does not match pattern PREFIX-CATEGORY-NNN"]

        result = runner.invoke(app, ["guardrails", "validate", str(policy_file)])
        assert result.exit_code == 1


class TestExportCommand:
    """Tests for `awsinv guardrails export` command."""

    @patch("src.cli.guardrails.export_builtin_policy_yaml")
    def test_export_to_stdout(self, mock_export: MagicMock) -> None:
        """Export command outputs YAML to stdout."""
        mock_export.return_value = "name: builtin\nversion: '1.0'\nguardrails: []\n"

        result = runner.invoke(app, ["guardrails", "export"])
        assert result.exit_code == 0
        assert "builtin" in result.stdout

    @patch("src.cli.guardrails.export_builtin_policy_yaml")
    def test_export_to_file(self, mock_export: MagicMock, tmp_path: Path) -> None:
        """Export command saves YAML to file with --output."""
        mock_export.return_value = "name: builtin\nversion: '1.0'\nguardrails: []\n"
        output_file = tmp_path / "exported.yaml"

        result = runner.invoke(app, ["guardrails", "export", "--output", str(output_file)])
        assert result.exit_code == 0
        assert output_file.exists()
        assert "builtin" in output_file.read_text()

    @patch("src.cli.guardrails.export_builtin_policy_yaml")
    def test_export_with_category_filter(self, mock_export: MagicMock) -> None:
        """Export command passes category filter to export function."""
        mock_export.return_value = "name: builtin\nguardrails: []\n"

        result = runner.invoke(app, ["guardrails", "export", "--category", "encryption"])
        assert result.exit_code == 0
        mock_export.assert_called_once_with(category="encryption")

    @patch("src.cli.guardrails.export_builtin_policy_yaml")
    def test_export_to_file_write_error(self, mock_export: MagicMock) -> None:
        """Export command exits 1 when file write fails."""
        mock_export.return_value = "name: builtin\n"

        result = runner.invoke(
            app,
            ["guardrails", "export", "--output", "/nonexistent/dir/exported.yaml"],
        )
        assert result.exit_code == 1


class TestPrintErrorTip:
    """Tests for _print_error_tip helper."""

    def test_severity_tip(self) -> None:
        """Prints severity tip for severity-related errors."""
        con = Console(file=MagicMock())
        _print_error_tip("Invalid severity value", con)
        con.file.write.assert_called()

    def test_action_tip(self) -> None:
        """Prints action tip for action-related errors."""
        con = Console(file=MagicMock())
        _print_error_tip("Invalid action type", con)
        con.file.write.assert_called()

    def test_applies_to_tip(self) -> None:
        """Prints applies_to tip for applies_to-related errors."""
        con = Console(file=MagicMock())
        _print_error_tip("Missing applies_to field", con)
        con.file.write.assert_called()

    def test_not_exists_tip(self) -> None:
        """Prints tip for 'not exists' syntax errors."""
        con = Console(file=MagicMock())
        _print_error_tip("attribute not exists issue", con)
        con.file.write.assert_called()

    def test_unbalanced_tip(self) -> None:
        """Prints tip for unbalanced parentheses errors."""
        con = Console(file=MagicMock())
        _print_error_tip("unbalanced parentheses in formula", con)
        con.file.write.assert_called()

    def test_unknown_function_tip(self) -> None:
        """Prints tip for unknown function errors."""
        con = Console(file=MagicMock())
        _print_error_tip("unknown function in condition", con)
        con.file.write.assert_called()

    def test_no_matching_tip(self) -> None:
        """No tip printed for unrecognized errors."""
        con = Console(file=MagicMock())
        _print_error_tip("some completely unrelated error xyzzy", con)


class TestCreateCommand:
    """Tests for `awsinv guardrails create` command."""

    @patch("src.cli.guardrails._get_bedrock_client")
    def test_create_no_bedrock_client(self, mock_get_client: MagicMock) -> None:
        """Create command exits 1 when Bedrock client is unavailable."""
        mock_get_client.return_value = None

        result = runner.invoke(app, ["guardrails", "create", "S3 buckets must have encryption"])
        assert result.exit_code == 1

    @patch("src.guardrails.generator.generate_guardrail")
    @patch("src.cli.guardrails._get_bedrock_client")
    def test_create_generation_fails(self, mock_get_client: MagicMock, mock_generate: MagicMock) -> None:
        """Create command exits 1 when generation returns None."""
        mock_get_client.return_value = MagicMock()
        mock_generate.return_value = None

        result = runner.invoke(app, ["guardrails", "create", "S3 buckets must have encryption"])
        assert result.exit_code == 1
        assert "failed" in result.stdout.lower()

    @patch("src.guardrails.generator.guardrail_to_yaml")
    @patch("src.guardrails.generator.generate_guardrail")
    @patch("src.cli.guardrails._get_bedrock_client")
    def test_create_success_stdout(
        self,
        mock_get_client: MagicMock,
        mock_generate: MagicMock,
        mock_to_yaml: MagicMock,
    ) -> None:
        """Create command outputs YAML to stdout on success."""
        mock_get_client.return_value = MagicMock()
        mock_generate.return_value = MagicMock()
        mock_to_yaml.return_value = "- id: GR-ENC-099\n  description: test\n"

        result = runner.invoke(app, ["guardrails", "create", "S3 buckets must have encryption"])
        assert result.exit_code == 0
        assert "GR-ENC-099" in result.stdout

    @patch("src.guardrails.generator.guardrail_to_yaml")
    @patch("src.guardrails.generator.generate_guardrail")
    @patch("src.cli.guardrails._get_bedrock_client")
    def test_create_output_to_file(
        self,
        mock_get_client: MagicMock,
        mock_generate: MagicMock,
        mock_to_yaml: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Create command appends to file with --output."""
        mock_get_client.return_value = MagicMock()
        mock_generate.return_value = MagicMock()
        mock_to_yaml.return_value = "- id: GR-ENC-099\n  description: test\n"

        output_file = tmp_path / "policy.yaml"
        output_file.write_text("guardrails:\n")

        result = runner.invoke(
            app,
            ["guardrails", "create", "S3 must be encrypted", "--output", str(output_file)],
        )
        assert result.exit_code == 0
        content = output_file.read_text()
        assert "GR-ENC-099" in content

    @patch("src.guardrails.generator.guardrail_to_yaml")
    @patch("src.guardrails.generator.generate_guardrail")
    @patch("src.cli.guardrails._get_bedrock_client")
    def test_create_output_to_new_file(
        self,
        mock_get_client: MagicMock,
        mock_generate: MagicMock,
        mock_to_yaml: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Create command writes new file when --output path does not exist."""
        mock_get_client.return_value = MagicMock()
        mock_generate.return_value = MagicMock()
        mock_to_yaml.return_value = "- id: GR-ENC-099\n"

        output_file = tmp_path / "new-policy.yaml"

        result = runner.invoke(
            app,
            ["guardrails", "create", "S3 encryption", "--output", str(output_file)],
        )
        assert result.exit_code == 0
        assert output_file.exists()


class TestGenerateCommand:
    """Tests for `awsinv guardrails generate` command."""

    @patch("src.cli.guardrails._get_bedrock_client")
    def test_generate_no_bedrock_client(self, mock_get_client: MagicMock) -> None:
        """Generate command exits 1 when Bedrock client unavailable."""
        mock_get_client.return_value = None

        result = runner.invoke(app, ["guardrails", "generate", "production security baseline"])
        assert result.exit_code == 1

    @patch("src.guardrails.generator.generate_guardrails_batch")
    @patch("src.cli.guardrails._get_bedrock_client")
    def test_generate_batch_fails(self, mock_get_client: MagicMock, mock_batch: MagicMock) -> None:
        """Generate command exits 1 when batch generation returns None."""
        mock_get_client.return_value = MagicMock()
        mock_batch.return_value = None

        result = runner.invoke(app, ["guardrails", "generate", "security baseline"])
        assert result.exit_code == 1
        assert "failed" in result.stdout.lower()

    @patch("src.guardrails.generator.guardrail_to_yaml")
    @patch("src.guardrails.generator.generate_guardrails_batch")
    @patch("src.cli.guardrails._get_bedrock_client")
    def test_generate_success_stdout(
        self,
        mock_get_client: MagicMock,
        mock_batch: MagicMock,
        mock_to_yaml: MagicMock,
    ) -> None:
        """Generate command outputs generated guardrails to stdout."""
        mock_get_client.return_value = MagicMock()
        mock_batch.return_value = [MagicMock(), MagicMock()]
        mock_to_yaml.return_value = "- id: GR-GEN-001\n"

        result = runner.invoke(app, ["guardrails", "generate", "security baseline"])
        assert result.exit_code == 0
        assert "generated 2 guardrails" in result.stdout.lower()

    @patch("src.guardrails.generator.guardrail_to_yaml")
    @patch("src.guardrails.generator.generate_guardrails_batch")
    @patch("src.cli.guardrails._get_bedrock_client")
    def test_generate_with_types_filter(
        self,
        mock_get_client: MagicMock,
        mock_batch: MagicMock,
        mock_to_yaml: MagicMock,
    ) -> None:
        """Generate command passes resource types when --types specified."""
        mock_get_client.return_value = MagicMock()
        mock_batch.return_value = [MagicMock()]
        mock_to_yaml.return_value = "- id: GR-GEN-001\n"

        result = runner.invoke(
            app,
            ["guardrails", "generate", "secure S3 and RDS", "--types", "s3,rds"],
        )
        assert result.exit_code == 0
        assert mock_batch.call_args.kwargs.get("resource_types") == ["s3", "rds"]

    @patch("src.guardrails.generator.guardrail_to_yaml")
    @patch("src.guardrails.generator.generate_guardrails_batch")
    @patch("src.cli.guardrails._get_bedrock_client")
    def test_generate_output_to_new_file(
        self,
        mock_get_client: MagicMock,
        mock_batch: MagicMock,
        mock_to_yaml: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Generate command creates new policy file with --output."""
        mock_get_client.return_value = MagicMock()
        mock_batch.return_value = [MagicMock()]
        mock_to_yaml.return_value = "- id: GR-GEN-001\n  description: test\n"

        output_file = tmp_path / "generated.yaml"

        result = runner.invoke(
            app,
            ["guardrails", "generate", "baseline", "--output", str(output_file)],
        )
        assert result.exit_code == 0
        assert output_file.exists()
        content = output_file.read_text()
        assert "generated-policy" in content or "GR-GEN-001" in content

    @patch("src.guardrails.generator.guardrail_to_yaml")
    @patch("src.guardrails.generator.generate_guardrails_batch")
    @patch("src.cli.guardrails._get_bedrock_client")
    def test_generate_output_append_to_existing(
        self,
        mock_get_client: MagicMock,
        mock_batch: MagicMock,
        mock_to_yaml: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Generate command appends to existing file with --output."""
        mock_get_client.return_value = MagicMock()
        mock_batch.return_value = [MagicMock()]
        mock_to_yaml.return_value = "- id: GR-GEN-002\n"

        output_file = tmp_path / "existing.yaml"
        output_file.write_text("name: existing\nguardrails:\n")

        result = runner.invoke(
            app,
            ["guardrails", "generate", "add more rules", "--output", str(output_file)],
        )
        assert result.exit_code == 0
        content = output_file.read_text()
        assert "existing" in content
        assert "GR-GEN-002" in content

    @patch("src.guardrails.generator.guardrail_to_yaml")
    @patch("src.guardrails.generator.generate_guardrails_batch")
    @patch("src.cli.guardrails._get_bedrock_client")
    def test_generate_with_count(
        self,
        mock_get_client: MagicMock,
        mock_batch: MagicMock,
        mock_to_yaml: MagicMock,
    ) -> None:
        """Generate command passes count to batch function."""
        mock_get_client.return_value = MagicMock()
        mock_batch.return_value = [MagicMock()] * 10
        mock_to_yaml.return_value = "- id: GR-GEN-001\n"

        result = runner.invoke(
            app,
            ["guardrails", "generate", "comprehensive policy", "--count", "10"],
        )
        assert result.exit_code == 0
        assert mock_batch.call_args.kwargs.get("count") == 10


class TestGetBedrockClient:
    """Tests for _get_bedrock_client helper."""

    @patch("boto3.client")
    def test_get_bedrock_client_success(self, mock_client_fn: MagicMock) -> None:
        """Returns Bedrock client on success."""
        from src.cli.guardrails import _get_bedrock_client

        mock_client = MagicMock()
        mock_client_fn.return_value = mock_client

        result = _get_bedrock_client()
        assert result == mock_client
        mock_client_fn.assert_called_once_with("bedrock-runtime")

    @patch("boto3.client", side_effect=Exception("No credentials"))
    def test_get_bedrock_client_failure(self, mock_client_fn: MagicMock) -> None:
        """Returns None when boto3 client creation fails."""
        from src.cli.guardrails import _get_bedrock_client

        result = _get_bedrock_client()
        assert result is None
