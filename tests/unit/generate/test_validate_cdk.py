"""Unit tests for CDK validation node (T020)."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch


def _setup_mocks() -> None:
    """Setup mocks for langgraph imports."""
    mock_langgraph = MagicMock()
    mock_langgraph.graph = MagicMock()
    mock_langgraph.graph.END = "END"
    mock_langgraph.graph.StateGraph = MagicMock()
    sys.modules["langgraph"] = mock_langgraph
    sys.modules["langgraph.graph"] = mock_langgraph.graph


_setup_mocks()

# Import after mocks are set up
from src.generate.nodes.validate_cdk import (
    cdk_synth,
    is_cdk_available,
    is_npm_available,
    npm_build,
    pip_install,
)


class TestNpmBuild:
    """Tests for npm_build() function."""

    def test_npm_build_skips_when_no_files(self) -> None:
        """Test npm_build skips validation when no files generated."""
        state = {
            "output_dir": "/tmp/test-cdk",
            "generated_files": [],
            "output_format": "cdk-typescript",
        }
        result = npm_build(state)
        assert result.get("npm_build_success") is False
        assert result.get("validation_skipped") is True

    def test_npm_build_skips_for_python(self) -> None:
        """Test npm_build skips for Python CDK projects."""
        state = {
            "output_dir": "/tmp/test-cdk",
            "generated_files": ["stacks/network_stack.py"],
            "output_format": "cdk-python",
        }
        result = npm_build(state)
        assert result.get("npm_build_success") is True
        assert result.get("npm_build_skipped") is True

    @patch("src.generate.nodes.validate_cdk.shutil.which")
    def test_npm_build_fails_when_npm_not_found(self, mock_which: MagicMock) -> None:
        """Test npm_build fails when npm CLI not found."""
        mock_which.return_value = None
        state = {
            "output_dir": "/tmp/test-cdk",
            "generated_files": ["lib/network_stack.ts"],
            "output_format": "cdk-typescript",
        }
        result = npm_build(state)
        assert result.get("npm_build_success") is False
        assert "npm" in str(result.get("validation_errors", []))

    @patch("src.generate.nodes.validate_cdk.subprocess.run")
    @patch("src.generate.nodes.validate_cdk.shutil.which")
    @patch("src.generate.nodes.validate_cdk.os.path.isdir")
    @patch("src.generate.nodes.validate_cdk.os.path.isfile")
    def test_npm_build_runs_npm_install_and_build(
        self,
        mock_isfile: MagicMock,
        mock_isdir: MagicMock,
        mock_which: MagicMock,
        mock_run: MagicMock,
    ) -> None:
        """Test npm_build runs npm install and npm run build."""
        mock_which.return_value = "/usr/bin/npm"
        mock_isdir.return_value = True
        mock_isfile.return_value = True
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        state = {
            "output_dir": "/tmp/test-cdk",
            "generated_files": ["lib/network_stack.ts"],
            "output_format": "cdk-typescript",
        }
        result = npm_build(state)

        assert result.get("npm_build_success") is True
        assert mock_run.call_count >= 2  # npm install + npm run build

    @patch("src.generate.nodes.validate_cdk.subprocess.run")
    @patch("src.generate.nodes.validate_cdk.shutil.which")
    @patch("src.generate.nodes.validate_cdk.os.path.isdir")
    @patch("src.generate.nodes.validate_cdk.os.path.isfile")
    def test_npm_build_handles_install_failure(
        self,
        mock_isfile: MagicMock,
        mock_isdir: MagicMock,
        mock_which: MagicMock,
        mock_run: MagicMock,
    ) -> None:
        """Test npm_build handles npm install failure."""
        mock_which.return_value = "/usr/bin/npm"
        mock_isdir.return_value = True
        mock_isfile.return_value = True
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="Install failed")

        state = {
            "output_dir": "/tmp/test-cdk",
            "generated_files": ["lib/network_stack.ts"],
            "output_format": "cdk-typescript",
        }
        result = npm_build(state)

        assert result.get("npm_build_success") is False
        assert len(result.get("validation_errors", [])) > 0


class TestCdkSynth:
    """Tests for cdk_synth() function."""

    def test_cdk_synth_skips_when_npm_build_failed(self) -> None:
        """Test cdk_synth skips when npm_build failed."""
        state = {
            "output_dir": "/tmp/test-cdk",
            "npm_build_success": False,
            "output_format": "cdk-typescript",
        }
        result = cdk_synth(state)
        assert result == {} or result.get("validation_errors") == []

    @patch("src.generate.nodes.validate_cdk.shutil.which")
    def test_cdk_synth_fails_when_cdk_not_found(self, mock_which: MagicMock) -> None:
        """Test cdk_synth fails when CDK CLI not found."""
        mock_which.return_value = None
        state = {
            "output_dir": "/tmp/test-cdk",
            "npm_build_success": True,
            "output_format": "cdk-typescript",
        }
        result = cdk_synth(state)
        assert "cdk" in str(result.get("validation_errors", [])).lower()

    @patch("src.generate.nodes.validate_cdk.subprocess.run")
    @patch("src.generate.nodes.validate_cdk.shutil.which")
    def test_cdk_synth_runs_cdk_synth(self, mock_which: MagicMock, mock_run: MagicMock) -> None:
        """Test cdk_synth runs cdk synth command."""
        mock_which.return_value = "/usr/bin/cdk"
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        state = {
            "output_dir": "/tmp/test-cdk",
            "npm_build_success": True,
            "output_format": "cdk-typescript",
        }
        result = cdk_synth(state)

        assert result.get("validation_errors") == [] or "validation_errors" not in result
        mock_run.assert_called()

    @patch("src.generate.nodes.validate_cdk.subprocess.run")
    @patch("src.generate.nodes.validate_cdk.shutil.which")
    def test_cdk_synth_handles_synth_failure(self, mock_which: MagicMock, mock_run: MagicMock) -> None:
        """Test cdk_synth handles synthesis failure."""
        mock_which.return_value = "/usr/bin/cdk"
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="Synth failed: missing construct")

        state = {
            "output_dir": "/tmp/test-cdk",
            "npm_build_success": True,
            "output_format": "cdk-typescript",
        }
        result = cdk_synth(state)

        assert len(result.get("validation_errors", [])) > 0


class TestPythonCdkValidation:
    """Tests for Python CDK validation."""

    @patch("src.generate.nodes.validate_cdk.subprocess.run")
    @patch("src.generate.nodes.validate_cdk.shutil.which")
    @patch("src.generate.nodes.validate_cdk.os.path.isdir")
    @patch("src.generate.nodes.validate_cdk.os.path.isfile")
    def test_python_cdk_runs_pip_install(
        self,
        mock_isfile: MagicMock,
        mock_isdir: MagicMock,
        mock_which: MagicMock,
        mock_run: MagicMock,
    ) -> None:
        """Test Python CDK validation runs pip install."""
        mock_which.return_value = "/usr/bin/pip"
        mock_isdir.return_value = True
        mock_isfile.return_value = True
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        state = {
            "output_dir": "/tmp/test-cdk",
            "generated_files": ["stacks/network_stack.py"],
            "output_format": "cdk-python",
        }

        result = pip_install(state)
        assert result.get("pip_install_success") is True


class TestIsCdkAvailable:
    """Tests for is_cdk_available() function."""

    @patch("src.generate.nodes.validate_cdk.shutil.which")
    def test_is_cdk_available_when_cdk_found(self, mock_which: MagicMock) -> None:
        """Test is_cdk_available returns True when CDK is found."""
        mock_which.return_value = "/usr/bin/cdk"
        assert is_cdk_available() is True

    @patch("src.generate.nodes.validate_cdk.shutil.which")
    def test_is_cdk_available_when_cdk_not_found(self, mock_which: MagicMock) -> None:
        """Test is_cdk_available returns False when CDK not found."""
        mock_which.return_value = None
        assert is_cdk_available() is False


class TestIsNpmAvailable:
    """Tests for is_npm_available() function."""

    @patch("src.generate.nodes.validate_cdk.shutil.which")
    def test_is_npm_available_when_npm_found(self, mock_which: MagicMock) -> None:
        """Test is_npm_available returns True when npm is found."""
        mock_which.return_value = "/usr/bin/npm"
        assert is_npm_available() is True

    @patch("src.generate.nodes.validate_cdk.shutil.which")
    def test_is_npm_available_when_npm_not_found(self, mock_which: MagicMock) -> None:
        """Test is_npm_available returns False when npm not found."""
        mock_which.return_value = None
        assert is_npm_available() is False
