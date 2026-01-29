"""Unit tests for copilot data models (T005, T007)."""

from datetime import date
from pathlib import Path

import pytest

from src.copilot.models import (
    FileType,
    InstalledFile,
    InstallResult,
    ModelVersionHeader,
    UninstallResult,
)


class TestFileType:
    """Tests for FileType enum."""

    def test_file_type_values(self) -> None:
        """FileType enum has expected values."""
        assert FileType.INSTRUCTIONS.value == "instructions"
        assert FileType.PROMPT.value == "prompt"
        assert FileType.CUSTOM.value == "custom"

    def test_file_type_members(self) -> None:
        """FileType enum has exactly 3 members."""
        assert len(FileType) == 3


class TestInstalledFile:
    """Tests for InstalledFile dataclass."""

    def test_installed_file_creation(self) -> None:
        """InstalledFile can be created with required fields."""
        file = InstalledFile(
            path=Path("/project/.github/copilot-instructions.md"),
            filename="copilot-instructions.md",
            file_type=FileType.INSTRUCTIONS,
        )
        assert file.path == Path("/project/.github/copilot-instructions.md")
        assert file.filename == "copilot-instructions.md"
        assert file.file_type == FileType.INSTRUCTIONS
        assert file.model is None
        assert file.last_updated is None
        assert file.is_custom is False

    def test_installed_file_with_optional_fields(self) -> None:
        """InstalledFile can be created with optional fields."""
        file = InstalledFile(
            path=Path("/project/.github/copilot-prompts/generate-terraform.md"),
            filename="generate-terraform.md",
            file_type=FileType.PROMPT,
            model="gpt-4.1",
            last_updated=date(2026, 1, 29),
            is_custom=False,
        )
        assert file.model == "gpt-4.1"
        assert file.last_updated == date(2026, 1, 29)
        assert file.is_custom is False

    def test_installed_file_custom_file(self) -> None:
        """InstalledFile correctly represents custom file."""
        file = InstalledFile(
            path=Path("/project/.github/copilot-custom.md"),
            filename="copilot-custom.md",
            file_type=FileType.CUSTOM,
            is_custom=True,
        )
        assert file.file_type == FileType.CUSTOM
        assert file.is_custom is True
        assert file.model is None


class TestModelVersionHeader:
    """Tests for ModelVersionHeader dataclass."""

    def test_model_version_header_creation(self) -> None:
        """ModelVersionHeader can be created with required fields."""
        header = ModelVersionHeader(
            model="gpt-4.1",
            optimizations=["token-efficient", "terse rules"],
            last_updated=date(2026, 1, 29),
        )
        assert header.model == "gpt-4.1"
        assert header.optimizations == ["token-efficient", "terse rules"]
        assert header.last_updated == date(2026, 1, 29)
        assert header.constraints == {}

    def test_model_version_header_with_constraints(self) -> None:
        """ModelVersionHeader can include constraints."""
        header = ModelVersionHeader(
            model="gpt-4.1",
            optimizations=["token-efficient"],
            last_updated=date(2026, 1, 29),
            constraints={
                "base-instructions-tokens": 4000,
                "task-prompt-tokens": 2000,
                "batch-threshold-resources": 50,
            },
        )
        assert header.constraints["base-instructions-tokens"] == 4000
        assert header.constraints["task-prompt-tokens"] == 2000
        assert header.constraints["batch-threshold-resources"] == 50


class TestInstallResult:
    """Tests for InstallResult dataclass."""

    def test_install_result_empty(self) -> None:
        """InstallResult initializes with empty lists."""
        result = InstallResult()
        assert result.installed == []
        assert result.backed_up == []
        assert result.skipped == []
        assert result.errors == []
        assert result.success is True

    def test_install_result_with_installed_files(self) -> None:
        """InstallResult tracks installed files."""
        result = InstallResult(
            installed=[
                Path("/project/.github/copilot-instructions.md"),
                Path("/project/.github/copilot-prompts/generate-terraform.md"),
            ]
        )
        assert len(result.installed) == 2
        assert result.success is True

    def test_install_result_with_backup(self) -> None:
        """InstallResult tracks backed up files."""
        result = InstallResult(
            backed_up=[
                (
                    Path("/project/.github/copilot-instructions.md"),
                    Path("/project/.github/copilot-instructions.md.bak.20260129-143022"),
                )
            ]
        )
        assert len(result.backed_up) == 1
        original, backup = result.backed_up[0]
        assert original.name == "copilot-instructions.md"
        assert ".bak." in backup.name

    def test_install_result_with_skipped(self) -> None:
        """InstallResult tracks skipped files."""
        result = InstallResult(skipped=[Path("/project/.github/copilot-custom.md")])
        assert len(result.skipped) == 1
        assert result.success is True

    def test_install_result_with_errors(self) -> None:
        """InstallResult tracks errors and reports failure."""
        result = InstallResult(
            errors=[(Path("/project/.github/test.md"), "Permission denied")]
        )
        assert len(result.errors) == 1
        assert result.success is False

    def test_install_result_success_property(self) -> None:
        """InstallResult.success is True only when no errors."""
        # No errors = success
        result1 = InstallResult(installed=[Path("/test.md")])
        assert result1.success is True

        # With errors = failure
        result2 = InstallResult(errors=[(Path("/test.md"), "Error")])
        assert result2.success is False


class TestUninstallResult:
    """Tests for UninstallResult dataclass."""

    def test_uninstall_result_empty(self) -> None:
        """UninstallResult initializes with empty lists."""
        result = UninstallResult()
        assert result.removed == []
        assert result.not_found == []
        assert result.preserved == []
        assert result.errors == []
        assert result.success is True

    def test_uninstall_result_with_removed_files(self) -> None:
        """UninstallResult tracks removed files."""
        result = UninstallResult(
            removed=[
                Path("/project/.github/copilot-instructions.md"),
                Path("/project/.github/copilot-prompts/generate-terraform.md"),
            ]
        )
        assert len(result.removed) == 2
        assert result.success is True

    def test_uninstall_result_with_not_found(self) -> None:
        """UninstallResult tracks files that weren't found."""
        result = UninstallResult(
            not_found=[Path("/project/.github/copilot-instructions.md")]
        )
        assert len(result.not_found) == 1
        assert result.success is True

    def test_uninstall_result_with_preserved(self) -> None:
        """UninstallResult tracks preserved files."""
        result = UninstallResult(preserved=[Path("/project/.github/copilot-custom.md")])
        assert len(result.preserved) == 1
        assert result.success is True

    def test_uninstall_result_with_errors(self) -> None:
        """UninstallResult tracks errors and reports failure."""
        result = UninstallResult(
            errors=[(Path("/project/.github/test.md"), "Permission denied")]
        )
        assert len(result.errors) == 1
        assert result.success is False
