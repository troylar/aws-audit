"""Copilot module for GitHub Copilot instructions and prompts installation."""

from .models import (
    FileType,
    InstalledFile,
    InstallResult,
    ModelVersionHeader,
    UninstallResult,
)
from .version import get_installed_file_info, parse_frontmatter

__all__ = [
    "FileType",
    "InstalledFile",
    "InstallResult",
    "ModelVersionHeader",
    "UninstallResult",
    "get_installed_file_info",
    "parse_frontmatter",
]
