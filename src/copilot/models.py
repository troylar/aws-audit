"""Data models for copilot module."""

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class FileType(Enum):
    """Type of copilot file."""

    INSTRUCTIONS = "instructions"  # copilot-instructions.md
    PROMPT = "prompt"  # prompts/*.prompt.md
    INSTRUCTION = "instruction"  # instructions/*.instructions.md
    CUSTOM = "custom"  # copilot-custom.md (user-created)


@dataclass
class InstalledFile:
    """Represents a file installed by the copilot installer."""

    path: Path
    filename: str
    file_type: FileType
    model: Optional[str] = None
    last_updated: Optional[date] = None
    is_custom: bool = False


@dataclass
class ModelVersionHeader:
    """Represents the YAML frontmatter in prompt files."""

    model: str
    optimizations: List[str]
    last_updated: date
    constraints: Dict[str, Any] = field(default_factory=dict)


@dataclass
class InstallResult:
    """Result of an install operation."""

    installed: List[Path] = field(default_factory=list)
    backed_up: List[Tuple[Path, Path]] = field(default_factory=list)
    skipped: List[Path] = field(default_factory=list)
    errors: List[Tuple[Path, str]] = field(default_factory=list)

    @property
    def success(self) -> bool:
        """Check if installation succeeded (no errors)."""
        return len(self.errors) == 0


@dataclass
class UninstallResult:
    """Result of an uninstall operation."""

    removed: List[Path] = field(default_factory=list)
    not_found: List[Path] = field(default_factory=list)
    preserved: List[Path] = field(default_factory=list)
    errors: List[Tuple[Path, str]] = field(default_factory=list)

    @property
    def success(self) -> bool:
        """Check if uninstallation succeeded (no errors)."""
        return len(self.errors) == 0
