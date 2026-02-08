"""Unit tests for the copilot CLI commands."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from src.cli.main import app

runner = CliRunner()


def _make_install_result(
    installed: list | None = None,
    backed_up: list | None = None,
    skipped: list | None = None,
    errors: list | None = None,
) -> MagicMock:
    result = MagicMock()
    result.installed = installed if installed is not None else [Path(".github/copilot-instructions.md")]
    result.backed_up = backed_up or []
    result.skipped = skipped or []
    result.errors = errors or []
    result.success = len(result.errors) == 0
    return result


def _make_uninstall_result(
    removed: list | None = None,
    not_found: list | None = None,
    preserved: list | None = None,
    errors: list | None = None,
) -> MagicMock:
    result = MagicMock()
    result.removed = removed if removed is not None else [Path(".github/copilot-instructions.md")]
    result.not_found = not_found or []
    result.preserved = preserved or []
    result.errors = errors or []
    result.success = len(result.errors) == 0
    return result


def _make_installed_file(
    filename: str = "copilot-instructions.md",
    path: Path | None = None,
    file_type_value: str = "instructions",
    model: str | None = "gpt-4.1",
    last_updated: str | None = "2025-10-01",
    is_custom: bool = False,
) -> MagicMock:
    f = MagicMock()
    f.filename = filename
    f.path = path or Path(f".github/{filename}")
    f.file_type = MagicMock()
    f.file_type.value = file_type_value
    f.model = model
    f.last_updated = last_updated
    f.is_custom = is_custom
    return f


class TestCopilotInstall:
    """Tests for `awsinv copilot install` command."""

    @patch("src.copilot.installer.install_files")
    def test_install_success(self, mock_install: MagicMock) -> None:
        """Install command succeeds and reports installed files."""
        mock_install.return_value = _make_install_result(
            installed=[
                Path(".github/copilot-instructions.md"),
                Path(".github/prompts/generate-terraform.prompt.md"),
            ],
        )

        result = runner.invoke(app, ["copilot", "install"])

        assert result.exit_code == 0
        assert "installed" in result.stdout.lower()
        mock_install.assert_called_once()

    @patch("src.copilot.installer.install_files")
    def test_install_with_custom_path(self, mock_install: MagicMock) -> None:
        """Install command accepts --path option."""
        mock_install.return_value = _make_install_result()

        result = runner.invoke(app, ["copilot", "install", "--path", "/tmp/my-project"])

        assert result.exit_code == 0
        call_args = mock_install.call_args
        assert call_args[0][0] == Path("/tmp/my-project")

    @patch("src.copilot.installer.install_files")
    def test_install_json_output(self, mock_install: MagicMock) -> None:
        """Install command with --json outputs valid JSON."""
        import json

        mock_install.return_value = _make_install_result(
            installed=[Path(".github/copilot-instructions.md")],
        )

        result = runner.invoke(app, ["copilot", "install", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["success"] is True
        assert isinstance(data["installed"], list)
        assert len(data["installed"]) == 1

    @patch("src.copilot.installer.install_files")
    def test_install_failure_exits_nonzero(self, mock_install: MagicMock) -> None:
        """Install command exits 1 when errors occur."""
        mock_install.return_value = _make_install_result(
            installed=[],
            errors=[(Path(".github/copilot-instructions.md"), "Permission denied")],
        )

        result = runner.invoke(app, ["copilot", "install"])

        assert result.exit_code == 1

    @patch("src.copilot.installer.install_files")
    def test_install_with_backups(self, mock_install: MagicMock) -> None:
        """Install command reports backed-up files."""
        mock_install.return_value = _make_install_result(
            installed=[Path(".github/copilot-instructions.md")],
            backed_up=[
                (
                    Path(".github/copilot-instructions.md"),
                    Path(".github/copilot-instructions.md.bak.20250101"),
                )
            ],
        )

        result = runner.invoke(app, ["copilot", "install"])

        assert result.exit_code == 0
        assert "backed up" in result.stdout.lower()


class TestCopilotUninstall:
    """Tests for `awsinv copilot uninstall` command."""

    @patch("src.copilot.installer.uninstall_files")
    def test_uninstall_success(self, mock_uninstall: MagicMock) -> None:
        """Uninstall command succeeds and reports removed files."""
        mock_uninstall.return_value = _make_uninstall_result(
            removed=[
                Path(".github/copilot-instructions.md"),
                Path(".github/prompts/generate-terraform.prompt.md"),
            ],
        )

        result = runner.invoke(app, ["copilot", "uninstall"])

        assert result.exit_code == 0
        assert "removed" in result.stdout.lower()
        mock_uninstall.assert_called_once()

    @patch("src.copilot.installer.uninstall_files")
    def test_uninstall_with_custom_path(self, mock_uninstall: MagicMock) -> None:
        """Uninstall command accepts --path option."""
        mock_uninstall.return_value = _make_uninstall_result()

        result = runner.invoke(app, ["copilot", "uninstall", "--path", "/tmp/my-project"])

        assert result.exit_code == 0
        call_args = mock_uninstall.call_args
        assert call_args[0][0] == Path("/tmp/my-project")

    @patch("src.copilot.installer.uninstall_files")
    def test_uninstall_json_output(self, mock_uninstall: MagicMock) -> None:
        """Uninstall command with --json outputs valid JSON."""
        import json

        mock_uninstall.return_value = _make_uninstall_result(
            removed=[Path(".github/copilot-instructions.md")],
        )

        result = runner.invoke(app, ["copilot", "uninstall", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["success"] is True
        assert isinstance(data["removed"], list)

    @patch("src.copilot.installer.uninstall_files")
    def test_uninstall_no_files_found(self, mock_uninstall: MagicMock) -> None:
        """Uninstall with no installed files reports gracefully."""
        mock_uninstall.return_value = _make_uninstall_result(removed=[])

        result = runner.invoke(app, ["copilot", "uninstall"])

        assert result.exit_code == 0
        assert "no installed files" in result.stdout.lower()


class TestCopilotList:
    """Tests for `awsinv copilot list` command."""

    @patch("src.copilot.installer.list_installed_files")
    def test_list_success(self, mock_list: MagicMock) -> None:
        """List command shows installed files in a table."""
        mock_list.return_value = [
            _make_installed_file(
                filename="copilot-instructions.md",
                file_type_value="instructions",
            ),
            _make_installed_file(
                filename="generate-terraform.prompt.md",
                file_type_value="prompt",
            ),
        ]

        result = runner.invoke(app, ["copilot", "list"])

        assert result.exit_code == 0
        assert "copilot-instructions.md" in result.stdout
        assert "generate-terraform.prompt.md" in result.stdout

    @patch("src.copilot.installer.list_installed_files")
    def test_list_json_output(self, mock_list: MagicMock) -> None:
        """List command with --json outputs valid JSON with file details."""
        import json

        mock_list.return_value = [
            _make_installed_file(
                filename="copilot-instructions.md",
                file_type_value="instructions",
                model="gpt-4.1",
            ),
        ]

        result = runner.invoke(app, ["copilot", "list", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert "files" in data
        assert len(data["files"]) == 1
        assert data["files"][0]["filename"] == "copilot-instructions.md"
        assert data["files"][0]["model"] == "gpt-4.1"

    @patch("src.copilot.installer.list_installed_files")
    def test_list_empty(self, mock_list: MagicMock) -> None:
        """List command with no files installed shows help message."""
        mock_list.return_value = []

        result = runner.invoke(app, ["copilot", "list"])

        assert result.exit_code == 0
        assert "no copilot files" in result.stdout.lower()

    @patch("src.copilot.installer.list_installed_files")
    def test_list_with_custom_path(self, mock_list: MagicMock) -> None:
        """List command accepts --path option."""
        mock_list.return_value = []

        result = runner.invoke(app, ["copilot", "list", "--path", "/tmp/my-project"])

        assert result.exit_code == 0
        call_args = mock_list.call_args
        assert call_args[0][0] == Path("/tmp/my-project")
