"""Tests for CLI compare command (IaC coverage comparison)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from src.cli.main import app


@pytest.fixture
def cli_runner():
    return CliRunner()


class TestCompareCommand:
    """Tests for awsinv compare command."""

    def test_compare_no_input(self, cli_runner):
        result = cli_runner.invoke(app, ["compare"])

        assert result.exit_code == 1
        assert "Either provide a snapshot name" in result.stdout

    @patch("src.generate.compare.compare_coverage")
    def test_compare_snapshot_success(self, mock_compare, cli_runner):
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.coverage_percentage = 85.0
        mock_result.total_resources = 20
        mock_result.represented_count = 17
        mock_result.missing_count = 3
        mock_result.represented_resources = []
        mock_result.missing_resources = [
            {"type": "s3:bucket", "name": "orphan-bucket", "reason": "Not in Terraform"},
        ]
        mock_result.issues = []
        mock_result.summary = "Good coverage overall"
        mock_result.errors = []
        mock_compare.return_value = mock_result

        result = cli_runner.invoke(
            app,
            ["compare", "my-snapshot", "--iac-dir", "./terraform"],
        )

        assert result.exit_code == 0
        assert "85.0%" in result.stdout
        assert "17" in result.stdout
        mock_compare.assert_called_once()

    @patch("src.generate.compare.compare_coverage")
    def test_compare_from_file(self, mock_compare, cli_runner):
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.coverage_percentage = 100.0
        mock_result.total_resources = 5
        mock_result.represented_count = 5
        mock_result.missing_count = 0
        mock_result.missing_resources = []
        mock_result.issues = []
        mock_result.summary = "Full coverage"
        mock_result.errors = []
        mock_compare.return_value = mock_result

        result = cli_runner.invoke(
            app,
            ["compare", "--from-file", "inventory.yaml", "--iac-dir", "./infra"],
        )

        assert result.exit_code == 0
        assert "100.0%" in result.stdout

    @patch("src.generate.compare.compare_coverage")
    def test_compare_json_output(self, mock_compare, cli_runner):
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.coverage_percentage = 90.0
        mock_result.total_resources = 10
        mock_result.represented_count = 9
        mock_result.missing_count = 1
        mock_result.represented_resources = ["resource-1"]
        mock_result.missing_resources = [{"type": "lambda:function", "name": "func-1"}]
        mock_result.issues = []
        mock_result.summary = "Near full coverage"
        mock_result.errors = []
        mock_compare.return_value = mock_result

        result = cli_runner.invoke(
            app,
            ["compare", "my-snapshot", "--iac-dir", "./terraform", "--json"],
        )

        assert result.exit_code == 0
        assert "coverage_percentage" in result.stdout
        assert "90.0" in result.stdout

    @patch("src.generate.compare.compare_coverage")
    def test_compare_with_missing_resources(self, mock_compare, cli_runner):
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.coverage_percentage = 60.0
        mock_result.total_resources = 10
        mock_result.represented_count = 6
        mock_result.missing_count = 4
        mock_result.missing_resources = [
            {"type": "s3:bucket", "name": "bucket-1", "reason": "No matching resource"},
            {"type": "lambda:function", "name": "func-1", "reason": "Not found"},
            {"type": "ec2:instance", "name": "i-abc123"},
            {"type": "rds:instance", "name": "my-db"},
        ]
        mock_result.issues = [
            {"severity": "warning", "description": "Some resources have partial matches"},
        ]
        mock_result.summary = "Coverage is low"
        mock_result.errors = []
        mock_compare.return_value = mock_result

        result = cli_runner.invoke(
            app,
            ["compare", "my-snapshot", "--iac-dir", "./terraform"],
        )

        assert result.exit_code == 0
        assert "60.0%" in result.stdout
        assert "Missing" in result.stdout

    @patch("src.generate.compare.compare_coverage")
    def test_compare_with_issues_and_errors(self, mock_compare, cli_runner):
        mock_result = MagicMock()
        mock_result.success = False
        mock_result.coverage_percentage = 0.0
        mock_result.total_resources = 0
        mock_result.represented_count = 0
        mock_result.missing_count = 0
        mock_result.missing_resources = []
        mock_result.issues = [
            {"severity": "error", "description": "Failed to parse terraform files"},
        ]
        mock_result.summary = ""
        mock_result.errors = ["Could not read terraform directory"]
        mock_compare.return_value = mock_result

        result = cli_runner.invoke(
            app,
            ["compare", "my-snapshot", "--iac-dir", "./bad-dir"],
        )

        assert result.exit_code == 1
        assert "Errors" in result.stdout or "error" in result.stdout.lower()

    @patch("src.generate.compare.compare_coverage")
    def test_compare_low_coverage_color(self, mock_compare, cli_runner):
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.coverage_percentage = 50.0
        mock_result.total_resources = 10
        mock_result.represented_count = 5
        mock_result.missing_count = 5
        mock_result.missing_resources = []
        mock_result.issues = []
        mock_result.summary = "Low coverage"
        mock_result.errors = []
        mock_compare.return_value = mock_result

        result = cli_runner.invoke(
            app,
            ["compare", "my-snapshot", "--iac-dir", "./terraform"],
        )

        assert result.exit_code == 0
        assert "50.0%" in result.stdout

    @patch("src.generate.compare.compare_coverage")
    def test_compare_with_model_and_region(self, mock_compare, cli_runner):
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.coverage_percentage = 75.0
        mock_result.total_resources = 8
        mock_result.represented_count = 6
        mock_result.missing_count = 2
        mock_result.missing_resources = []
        mock_result.issues = []
        mock_result.summary = ""
        mock_result.errors = []
        mock_compare.return_value = mock_result

        result = cli_runner.invoke(
            app,
            [
                "compare",
                "my-snapshot",
                "--iac-dir",
                "./terraform",
                "--model-id",
                "anthropic.claude-3",
                "--region",
                "us-west-2",
            ],
        )

        assert result.exit_code == 0
