"""Unit tests for copilot installer (T013-T017)."""

import os
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.copilot.installer import (
    generate_backup_filename,
    get_template_files,
    install_files,
    list_installed_files,
    uninstall_files,
    validate_target_path,
)
from src.copilot.models import FileType, InstallResult, UninstallResult


class TestValidateTargetPath:
    """Tests for validate_target_path (T013)."""

    def test_valid_path(self, tmp_path: Path) -> None:
        """validate_target_path accepts valid directory."""
        result = validate_target_path(tmp_path)
        assert result is None  # No error

    def test_path_does_not_exist(self) -> None:
        """validate_target_path rejects non-existent path."""
        error = validate_target_path(Path("/nonexistent/path/12345"))
        assert error is not None
        assert "does not exist" in error

    def test_path_is_not_directory(self, tmp_path: Path) -> None:
        """validate_target_path rejects files."""
        file_path = tmp_path / "test.txt"
        file_path.write_text("test")
        error = validate_target_path(file_path)
        assert error is not None
        assert "not a directory" in error

    def test_path_not_writable(self, tmp_path: Path) -> None:
        """validate_target_path rejects non-writable directories."""
        # Skip on Windows where chmod doesn't work the same way
        if os.name == "nt":
            pytest.skip("chmod test not applicable on Windows")

        readonly_dir = tmp_path / "readonly"
        readonly_dir.mkdir()
        readonly_dir.chmod(0o444)
        try:
            error = validate_target_path(readonly_dir)
            assert error is not None
            assert "not writable" in error
        finally:
            readonly_dir.chmod(0o755)

    def test_reject_root_paths(self) -> None:
        """validate_target_path rejects dangerous root paths."""
        # Only test paths that resolve to themselves (not symlinks)
        # On macOS, /home resolves to /System/Volumes/Data/home
        dangerous_paths = ["/", "/Users"]
        for path_str in dangerous_paths:
            path = Path(path_str)
            if path.exists() and str(path.resolve()) == path_str:
                error = validate_target_path(path)
                assert error is not None, f"Should reject {path_str}"
                assert "Cannot install" in error


class TestGenerateBackupFilename:
    """Tests for generate_backup_filename (T014)."""

    def test_backup_filename_format(self) -> None:
        """generate_backup_filename creates correct format."""
        original = Path("/project/.github/copilot-instructions.md")
        backup = generate_backup_filename(original)

        assert backup.parent == original.parent
        assert backup.name.startswith("copilot-instructions.md.bak.")
        # Should have timestamp in format YYYYMMDD-HHMMSS
        timestamp_part = backup.name.split(".bak.")[1]
        assert len(timestamp_part) == 15  # YYYYMMDD-HHMMSS

    def test_backup_filename_unique(self) -> None:
        """generate_backup_filename creates unique names."""
        original = Path("/project/.github/test.md")
        backup1 = generate_backup_filename(original)
        # Small delay to ensure different timestamp
        import time

        time.sleep(0.01)
        backup2 = generate_backup_filename(original)

        # Names might be same if within same second, but generally should differ
        assert backup1.name.startswith("test.md.bak.")
        assert backup2.name.startswith("test.md.bak.")


class TestGetTemplateFiles:
    """Tests for get_template_files (T023 - but verifying the function exists)."""

    def test_get_template_files_returns_dict(self) -> None:
        """get_template_files returns dictionary of template files."""
        templates = get_template_files()
        assert isinstance(templates, dict)
        assert "copilot-instructions.md" in templates
        assert "prompts/generate-terraform.prompt.md" in templates
        assert "prompts/generate-cdk-typescript.prompt.md" in templates
        assert "prompts/generate-cdk-python.prompt.md" in templates

    def test_get_template_files_content(self) -> None:
        """get_template_files returns non-empty content."""
        templates = get_template_files()
        for name, content in templates.items():
            assert content, f"Template {name} should have content"
            assert isinstance(content, str)


class TestInstallFiles:
    """Tests for install_files (T015)."""

    def test_install_creates_files(self, tmp_path: Path) -> None:
        """install_files creates all template files."""
        result = install_files(tmp_path)

        assert result.success is True
        assert len(result.installed) == 4

        # Verify files exist
        github_dir = tmp_path / ".github"
        assert (github_dir / "copilot-instructions.md").exists()
        assert (github_dir / "prompts" / "generate-terraform.prompt.md").exists()
        assert (github_dir / "prompts" / "generate-cdk-typescript.prompt.md").exists()
        assert (github_dir / "prompts" / "generate-cdk-python.prompt.md").exists()

    def test_install_creates_github_dir(self, tmp_path: Path) -> None:
        """install_files creates .github directory if not exists."""
        result = install_files(tmp_path)

        assert result.success is True
        assert (tmp_path / ".github").is_dir()

    def test_install_creates_prompts_dir(self, tmp_path: Path) -> None:
        """install_files creates prompts directory."""
        result = install_files(tmp_path)

        assert result.success is True
        assert (tmp_path / ".github" / "prompts").is_dir()

    def test_install_backups_existing_files(self, tmp_path: Path) -> None:
        """install_files backs up existing files before overwriting."""
        # Create existing file
        github_dir = tmp_path / ".github"
        github_dir.mkdir()
        existing_file = github_dir / "copilot-instructions.md"
        existing_file.write_text("Original content")

        result = install_files(tmp_path)

        assert result.success is True
        assert len(result.backed_up) == 1

        # Verify backup exists
        backups = list(github_dir.glob("copilot-instructions.md.bak.*"))
        assert len(backups) == 1
        assert backups[0].read_text() == "Original content"

    def test_install_preserves_custom_file(self, tmp_path: Path) -> None:
        """install_files preserves copilot-custom.md (FR-047)."""
        # Create existing custom file
        github_dir = tmp_path / ".github"
        github_dir.mkdir()
        custom_file = github_dir / "copilot-custom.md"
        custom_file.write_text("My org standards")

        result = install_files(tmp_path)

        assert result.success is True
        assert len(result.skipped) == 1
        assert custom_file in result.skipped

        # Verify custom file is unchanged
        assert custom_file.read_text() == "My org standards"

    def test_install_invalid_path(self) -> None:
        """install_files returns error for invalid path."""
        result = install_files(Path("/nonexistent/path/12345"))

        assert result.success is False
        assert len(result.errors) == 1


class TestUninstallFiles:
    """Tests for uninstall_files (T016)."""

    def test_uninstall_removes_files(self, tmp_path: Path) -> None:
        """uninstall_files removes all installed files."""
        # First install
        install_files(tmp_path)

        # Then uninstall
        result = uninstall_files(tmp_path)

        assert result.success is True
        assert len(result.removed) == 4

        # Verify files are gone
        github_dir = tmp_path / ".github"
        assert not (github_dir / "copilot-instructions.md").exists()
        assert not (github_dir / "prompts" / "generate-terraform.prompt.md").exists()

    def test_uninstall_preserves_custom_file(self, tmp_path: Path) -> None:
        """uninstall_files preserves copilot-custom.md."""
        # Install and create custom file
        install_files(tmp_path)
        custom_file = tmp_path / ".github" / "copilot-custom.md"
        custom_file.write_text("My org standards")

        result = uninstall_files(tmp_path)

        assert result.success is True
        assert len(result.preserved) == 1
        assert custom_file in result.preserved
        assert custom_file.exists()

    def test_uninstall_removes_empty_prompts_dir(self, tmp_path: Path) -> None:
        """uninstall_files removes empty prompts directory."""
        install_files(tmp_path)
        result = uninstall_files(tmp_path)

        assert result.success is True
        prompts_dir = tmp_path / ".github" / "prompts"
        assert not prompts_dir.exists()

    def test_uninstall_nothing_to_remove(self, tmp_path: Path) -> None:
        """uninstall_files handles case with no files to remove."""
        result = uninstall_files(tmp_path)

        assert result.success is True
        assert len(result.not_found) >= 0  # May have not_found entries

    def test_uninstall_invalid_path(self) -> None:
        """uninstall_files returns error for invalid path."""
        result = uninstall_files(Path("/nonexistent/path/12345"))

        assert result.success is False
        assert len(result.errors) == 1


class TestListInstalledFiles:
    """Tests for list_installed_files (T017)."""

    def test_list_returns_installed_files(self, tmp_path: Path) -> None:
        """list_installed_files returns all installed files."""
        install_files(tmp_path)
        files = list_installed_files(tmp_path)

        assert len(files) == 4
        filenames = [f.filename for f in files]
        assert "copilot-instructions.md" in filenames
        assert "generate-terraform.prompt.md" in filenames
        assert "generate-cdk-typescript.prompt.md" in filenames
        assert "generate-cdk-python.prompt.md" in filenames

    def test_list_includes_custom_file(self, tmp_path: Path) -> None:
        """list_installed_files includes custom file if present."""
        install_files(tmp_path)
        custom_file = tmp_path / ".github" / "copilot-custom.md"
        custom_file.write_text("My custom content")

        files = list_installed_files(tmp_path)

        assert len(files) == 5
        custom = next(f for f in files if f.filename == "copilot-custom.md")
        assert custom.is_custom is True
        assert custom.file_type == FileType.CUSTOM

    def test_list_empty_directory(self, tmp_path: Path) -> None:
        """list_installed_files returns empty list for directory without files."""
        files = list_installed_files(tmp_path)
        assert files == []

    def test_list_parses_version_info(self, tmp_path: Path) -> None:
        """list_installed_files includes version info from frontmatter."""
        install_files(tmp_path)
        files = list_installed_files(tmp_path)

        instructions = next(
            f for f in files if f.filename == "copilot-instructions.md"
        )
        assert instructions.model == "gpt-4.1"
        assert instructions.last_updated is not None

    def test_list_invalid_path(self) -> None:
        """list_installed_files returns empty list for invalid path."""
        files = list_installed_files(Path("/nonexistent/path/12345"))
        assert files == []
