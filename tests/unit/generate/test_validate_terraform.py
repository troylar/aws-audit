"""Unit tests for terraform validation node."""

from __future__ import annotations

import json
import subprocess
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest

# Skip entire module if generate dependencies not installed
pytest.importorskip("openai", reason="Requires 'generate' optional dependencies")

from src.generate.nodes.validate_terraform import (
    is_terraform_available,
    run_terraform_fmt,
    validate_terraform,
)


class TestValidateTerraform:
    """Tests for the validate_terraform node."""

    def test_skip_validation_when_no_files(self) -> None:
        """Test that validation is skipped when no files generated."""
        state: Dict[str, Any] = {
            "output_dir": "/tmp/terraform",
            "generated_files": [],
        }

        result = validate_terraform(state)

        assert result["validation_errors"] == []

    @patch("src.generate.nodes.validate_terraform.shutil.which")
    def test_skip_validation_when_terraform_not_found(self, mock_which: MagicMock) -> None:
        """Test that validation is skipped when terraform CLI not in PATH."""
        mock_which.return_value = None

        state: Dict[str, Any] = {
            "output_dir": "/tmp/terraform",
            "generated_files": ["main.tf"],
        }

        result = validate_terraform(state)

        assert len(result["validation_errors"]) == 1
        assert "terraform CLI not found" in result["validation_errors"][0]

    @patch("src.generate.nodes.validate_terraform.shutil.which")
    @patch("os.path.isdir")
    def test_error_when_output_dir_not_exists(self, mock_isdir: MagicMock, mock_which: MagicMock) -> None:
        """Test error when output directory doesn't exist."""
        mock_which.return_value = "/usr/bin/terraform"
        mock_isdir.return_value = False

        state: Dict[str, Any] = {
            "output_dir": "/nonexistent/path",
            "generated_files": ["main.tf"],
        }

        result = validate_terraform(state)

        assert len(result["validation_errors"]) == 1
        assert "does not exist" in result["validation_errors"][0]

    @patch("src.generate.nodes.validate_terraform.subprocess.run")
    @patch("src.generate.nodes.validate_terraform.shutil.which")
    @patch("os.path.isdir")
    def test_init_failure(
        self,
        mock_isdir: MagicMock,
        mock_which: MagicMock,
        mock_run: MagicMock,
    ) -> None:
        """Test handling of terraform init failure."""
        mock_which.return_value = "/usr/bin/terraform"
        mock_isdir.return_value = True
        mock_run.return_value = MagicMock(
            returncode=1,
            stderr="Error: Could not find provider",
            stdout="",
        )

        state: Dict[str, Any] = {
            "output_dir": "/tmp/terraform",
            "generated_files": ["main.tf"],
        }

        result = validate_terraform(state)

        assert len(result["validation_errors"]) == 1
        assert "terraform init failed" in result["validation_errors"][0]
        # Should not proceed to validate
        assert mock_run.call_count == 1

    @patch("src.generate.nodes.validate_terraform.subprocess.run")
    @patch("src.generate.nodes.validate_terraform.shutil.which")
    @patch("os.path.isdir")
    def test_init_timeout(
        self,
        mock_isdir: MagicMock,
        mock_which: MagicMock,
        mock_run: MagicMock,
    ) -> None:
        """Test handling of terraform init timeout."""
        mock_which.return_value = "/usr/bin/terraform"
        mock_isdir.return_value = True
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="terraform", timeout=120)

        state: Dict[str, Any] = {
            "output_dir": "/tmp/terraform",
            "generated_files": ["main.tf"],
        }

        result = validate_terraform(state)

        assert len(result["validation_errors"]) == 1
        assert "timed out" in result["validation_errors"][0]

    @patch("src.generate.nodes.validate_terraform.subprocess.run")
    @patch("src.generate.nodes.validate_terraform.shutil.which")
    @patch("os.path.isdir")
    def test_validate_success(
        self,
        mock_isdir: MagicMock,
        mock_which: MagicMock,
        mock_run: MagicMock,
    ) -> None:
        """Test successful terraform validation."""
        mock_which.return_value = "/usr/bin/terraform"
        mock_isdir.return_value = True

        # Mock init success
        init_result = MagicMock(returncode=0, stderr="", stdout="")
        # Mock validate success
        validate_result = MagicMock(
            returncode=0,
            stderr="",
            stdout=json.dumps({"valid": True, "diagnostics": []}),
        )
        mock_run.side_effect = [init_result, validate_result]

        state: Dict[str, Any] = {
            "output_dir": "/tmp/terraform",
            "generated_files": ["main.tf"],
        }

        result = validate_terraform(state)

        assert result["validation_errors"] == []
        assert mock_run.call_count == 2

    @patch("src.generate.nodes.validate_terraform.subprocess.run")
    @patch("src.generate.nodes.validate_terraform.shutil.which")
    @patch("os.path.isdir")
    def test_validate_with_errors(
        self,
        mock_isdir: MagicMock,
        mock_which: MagicMock,
        mock_run: MagicMock,
    ) -> None:
        """Test terraform validation with errors."""
        mock_which.return_value = "/usr/bin/terraform"
        mock_isdir.return_value = True

        # Mock init success
        init_result = MagicMock(returncode=0, stderr="", stdout="")
        # Mock validate failure with JSON output
        validate_output = {
            "valid": False,
            "diagnostics": [
                {
                    "severity": "error",
                    "summary": "Invalid resource type",
                    "detail": "The resource type 'aws_unknown_resource' is not valid",
                    "range": {
                        "filename": "main.tf",
                        "start": {"line": 10, "column": 1},
                    },
                },
                {
                    "severity": "error",
                    "summary": "Missing required argument",
                    "detail": "The argument 'name' is required",
                },
            ],
        }
        validate_result = MagicMock(
            returncode=1,
            stderr="",
            stdout=json.dumps(validate_output),
        )
        mock_run.side_effect = [init_result, validate_result]

        state: Dict[str, Any] = {
            "output_dir": "/tmp/terraform",
            "generated_files": ["main.tf"],
        }

        result = validate_terraform(state)

        assert len(result["validation_errors"]) == 2
        assert "Invalid resource type" in result["validation_errors"][0]
        assert "main.tf:10" in result["validation_errors"][0]
        assert "Missing required argument" in result["validation_errors"][1]

    @patch("src.generate.nodes.validate_terraform.subprocess.run")
    @patch("src.generate.nodes.validate_terraform.shutil.which")
    @patch("os.path.isdir")
    def test_validate_fallback_to_stderr(
        self,
        mock_isdir: MagicMock,
        mock_which: MagicMock,
        mock_run: MagicMock,
    ) -> None:
        """Test fallback to stderr when JSON parsing fails."""
        mock_which.return_value = "/usr/bin/terraform"
        mock_isdir.return_value = True

        # Mock init success
        init_result = MagicMock(returncode=0, stderr="", stdout="")
        # Mock validate failure with non-JSON output
        validate_result = MagicMock(
            returncode=1,
            stderr="Error: Invalid syntax",
            stdout="not valid json",
        )
        mock_run.side_effect = [init_result, validate_result]

        state: Dict[str, Any] = {
            "output_dir": "/tmp/terraform",
            "generated_files": ["main.tf"],
        }

        result = validate_terraform(state)

        assert len(result["validation_errors"]) == 1
        assert "Invalid syntax" in result["validation_errors"][0]


class TestIsTerraformAvailable:
    """Tests for is_terraform_available helper."""

    @patch("src.generate.nodes.validate_terraform.shutil.which")
    def test_terraform_available(self, mock_which: MagicMock) -> None:
        """Test when terraform is available."""
        mock_which.return_value = "/usr/bin/terraform"
        assert is_terraform_available() is True

    @patch("src.generate.nodes.validate_terraform.shutil.which")
    def test_terraform_not_available(self, mock_which: MagicMock) -> None:
        """Test when terraform is not available."""
        mock_which.return_value = None
        assert is_terraform_available() is False


class TestRunTerraformFmt:
    """Tests for run_terraform_fmt helper."""

    @patch("src.generate.nodes.validate_terraform.shutil.which")
    def test_fmt_terraform_not_found(self, mock_which: MagicMock) -> None:
        """Test fmt when terraform not found."""
        mock_which.return_value = None

        success, error = run_terraform_fmt("/tmp/terraform")

        assert success is False
        assert "not found" in error

    @patch("src.generate.nodes.validate_terraform.subprocess.run")
    @patch("src.generate.nodes.validate_terraform.shutil.which")
    def test_fmt_success(self, mock_which: MagicMock, mock_run: MagicMock) -> None:
        """Test successful terraform fmt."""
        mock_which.return_value = "/usr/bin/terraform"
        mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")

        success, error = run_terraform_fmt("/tmp/terraform")

        assert success is True
        assert error == ""

    @patch("src.generate.nodes.validate_terraform.subprocess.run")
    @patch("src.generate.nodes.validate_terraform.shutil.which")
    def test_fmt_failure(self, mock_which: MagicMock, mock_run: MagicMock) -> None:
        """Test terraform fmt failure."""
        mock_which.return_value = "/usr/bin/terraform"
        mock_run.return_value = MagicMock(returncode=1, stderr="Error: Invalid HCL", stdout="")

        success, error = run_terraform_fmt("/tmp/terraform")

        assert success is False
        assert "Invalid HCL" in error

    @patch("src.generate.nodes.validate_terraform.subprocess.run")
    @patch("src.generate.nodes.validate_terraform.shutil.which")
    def test_fmt_timeout(self, mock_which: MagicMock, mock_run: MagicMock) -> None:
        """Test terraform fmt timeout."""
        mock_which.return_value = "/usr/bin/terraform"
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="terraform", timeout=60)

        success, error = run_terraform_fmt("/tmp/terraform")

        assert success is False
        assert "timed out" in error


class TestGenerationResultValidation:
    """Tests for GenerationResult validation properties."""

    def test_generation_result_is_valid_true(self) -> None:
        """Test is_valid returns True when no validation errors."""
        from src.generate.terraform_generator import GenerationResult

        result = GenerationResult(
            success=True,
            output_dir="/tmp/terraform",
            generated_files=["main.tf"],
            validation_errors=[],
        )

        assert result.is_valid is True

    def test_generation_result_is_valid_false(self) -> None:
        """Test is_valid returns False when validation errors exist."""
        from src.generate.terraform_generator import GenerationResult

        result = GenerationResult(
            success=True,
            output_dir="/tmp/terraform",
            generated_files=["main.tf"],
            validation_errors=["error: Invalid resource"],
        )

        assert result.is_valid is False

    def test_generation_result_summary_includes_validation(self) -> None:
        """Test summary includes validation_errors count."""
        from src.generate.terraform_generator import GenerationResult

        result = GenerationResult(
            success=True,
            output_dir="/tmp/terraform",
            generated_files=["main.tf"],
            validation_errors=["error1", "error2"],
        )

        summary = result.summary

        assert "is_valid" in summary
        assert summary["is_valid"] is False
        assert "validation_errors" in summary
        assert summary["validation_errors"] == 2
