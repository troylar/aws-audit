"""Integration tests for copilot CLI commands (T018-T020)."""

import tempfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from src.cli.main import app


runner = CliRunner()


class TestCopilotInstallCommand:
    """Integration tests for copilot install command (T018)."""

    def test_install_creates_files(self, tmp_path: Path) -> None:
        """awsinv copilot install creates files in target directory."""
        result = runner.invoke(app, ["copilot", "install", "--path", str(tmp_path)])

        assert result.exit_code == 0
        assert "Installed" in result.stdout or "installed" in result.stdout.lower()

        # Verify files created
        github_dir = tmp_path / ".github"
        assert (github_dir / "copilot-instructions.md").exists()
        assert (github_dir / "prompts" / "generate-terraform.prompt.md").exists()
        assert (github_dir / "prompts" / "generate-cdk-typescript.prompt.md").exists()
        assert (github_dir / "prompts" / "generate-cdk-python.prompt.md").exists()

    def test_install_defaults_to_current_dir(self) -> None:
        """awsinv copilot install uses current directory by default."""
        with tempfile.TemporaryDirectory() as tmp:
            # Change to temp directory and run install
            import os

            original_cwd = os.getcwd()
            try:
                os.chdir(tmp)
                result = runner.invoke(app, ["copilot", "install"])

                assert result.exit_code == 0
                assert Path(tmp) / ".github" / "copilot-instructions.md"
            finally:
                os.chdir(original_cwd)

    def test_install_invalid_path(self) -> None:
        """awsinv copilot install fails for invalid path."""
        result = runner.invoke(app, ["copilot", "install", "--path", "/nonexistent/path/12345"])

        assert result.exit_code != 0
        assert "does not exist" in result.stdout or "Error" in result.stdout

    def test_install_backup_existing(self, tmp_path: Path) -> None:
        """awsinv copilot install backs up existing files."""
        # Create existing file
        github_dir = tmp_path / ".github"
        github_dir.mkdir()
        existing_file = github_dir / "copilot-instructions.md"
        existing_file.write_text("Original content")

        result = runner.invoke(app, ["copilot", "install", "--path", str(tmp_path)])

        assert result.exit_code == 0
        assert "backed up" in result.stdout.lower() or "backup" in result.stdout.lower()

        # Verify backup exists
        backups = list(github_dir.glob("copilot-instructions.md.bak.*"))
        assert len(backups) == 1

    def test_install_json_output(self, tmp_path: Path) -> None:
        """awsinv copilot install --json produces JSON output."""
        result = runner.invoke(app, ["copilot", "install", "--path", str(tmp_path), "--json"])

        assert result.exit_code == 0
        import json

        data = json.loads(result.stdout)
        assert "installed" in data
        assert isinstance(data["installed"], list)


class TestCopilotUninstallCommand:
    """Integration tests for copilot uninstall command (T019)."""

    def test_uninstall_removes_files(self, tmp_path: Path) -> None:
        """awsinv copilot uninstall removes installed files."""
        # First install
        runner.invoke(app, ["copilot", "install", "--path", str(tmp_path)])

        # Then uninstall
        result = runner.invoke(app, ["copilot", "uninstall", "--path", str(tmp_path)])

        assert result.exit_code == 0
        assert "removed" in result.stdout.lower() or "uninstalled" in result.stdout.lower()

        # Verify files removed
        github_dir = tmp_path / ".github"
        assert not (github_dir / "copilot-instructions.md").exists()
        assert not (github_dir / "prompts" / "generate-terraform.prompt.md").exists()

    def test_uninstall_preserves_custom_file(self, tmp_path: Path) -> None:
        """awsinv copilot uninstall preserves custom file."""
        # Install and create custom file
        runner.invoke(app, ["copilot", "install", "--path", str(tmp_path)])
        custom_file = tmp_path / ".github" / "copilot-custom.md"
        custom_file.write_text("My org standards")

        result = runner.invoke(app, ["copilot", "uninstall", "--path", str(tmp_path)])

        assert result.exit_code == 0
        assert custom_file.exists()
        assert "preserved" in result.stdout.lower() or "custom" in result.stdout.lower()

    def test_uninstall_nothing_installed(self, tmp_path: Path) -> None:
        """awsinv copilot uninstall handles no files to remove."""
        result = runner.invoke(app, ["copilot", "uninstall", "--path", str(tmp_path)])

        # Should succeed even with nothing to remove
        assert result.exit_code == 0

    def test_uninstall_json_output(self, tmp_path: Path) -> None:
        """awsinv copilot uninstall --json produces JSON output."""
        # First install
        runner.invoke(app, ["copilot", "install", "--path", str(tmp_path)])

        result = runner.invoke(app, ["copilot", "uninstall", "--path", str(tmp_path), "--json"])

        assert result.exit_code == 0
        import json

        data = json.loads(result.stdout)
        assert "removed" in data
        assert isinstance(data["removed"], list)


class TestCopilotListCommand:
    """Integration tests for copilot list command (T020)."""

    def test_list_installed_files(self, tmp_path: Path) -> None:
        """awsinv copilot list shows installed files."""
        # Install first
        runner.invoke(app, ["copilot", "install", "--path", str(tmp_path)])

        result = runner.invoke(app, ["copilot", "list", "--path", str(tmp_path)])

        assert result.exit_code == 0
        assert "copilot-instructions.md" in result.stdout
        assert "generate-terraform.prompt.md" in result.stdout

    def test_list_empty_directory(self, tmp_path: Path) -> None:
        """awsinv copilot list handles empty directory."""
        result = runner.invoke(app, ["copilot", "list", "--path", str(tmp_path)])

        assert result.exit_code == 0
        assert "no" in result.stdout.lower() or "0" in result.stdout

    def test_list_shows_version_info(self, tmp_path: Path) -> None:
        """awsinv copilot list shows version info from frontmatter."""
        runner.invoke(app, ["copilot", "install", "--path", str(tmp_path)])

        result = runner.invoke(app, ["copilot", "list", "--path", str(tmp_path)])

        assert result.exit_code == 0
        # Should show model version
        assert "gpt-4.1" in result.stdout

    def test_list_shows_custom_file(self, tmp_path: Path) -> None:
        """awsinv copilot list shows custom file when present."""
        runner.invoke(app, ["copilot", "install", "--path", str(tmp_path)])
        custom_file = tmp_path / ".github" / "copilot-custom.md"
        custom_file.write_text("# Custom\n\nMy org standards")

        result = runner.invoke(app, ["copilot", "list", "--path", str(tmp_path)])

        assert result.exit_code == 0
        assert "copilot-custom.md" in result.stdout
        assert "custom" in result.stdout.lower()

    def test_list_json_output(self, tmp_path: Path) -> None:
        """awsinv copilot list --json produces JSON output."""
        runner.invoke(app, ["copilot", "install", "--path", str(tmp_path)])

        result = runner.invoke(app, ["copilot", "list", "--path", str(tmp_path), "--json"])

        assert result.exit_code == 0
        import json

        data = json.loads(result.stdout)
        assert "files" in data
        assert isinstance(data["files"], list)
        assert len(data["files"]) == 7


class TestCopilotHelp:
    """Tests for copilot command help."""

    def test_copilot_help(self) -> None:
        """awsinv copilot --help shows available commands."""
        result = runner.invoke(app, ["copilot", "--help"])

        assert result.exit_code == 0
        assert "install" in result.stdout
        assert "uninstall" in result.stdout
        assert "list" in result.stdout

    def test_copilot_install_help(self) -> None:
        """awsinv copilot install --help shows options."""
        result = runner.invoke(app, ["copilot", "install", "--help"])

        assert result.exit_code == 0
        assert "--path" in result.stdout
        assert "--json" in result.stdout
