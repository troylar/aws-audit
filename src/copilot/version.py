"""Version parsing utilities for copilot files."""

import re
from datetime import date
from pathlib import Path
from typing import Any, Dict

import yaml

from .models import FileType, InstalledFile


def parse_frontmatter(content: str) -> Dict[str, Any]:
    """Parse YAML frontmatter from markdown content.

    Args:
        content: Markdown content with optional YAML frontmatter

    Returns:
        Dictionary of frontmatter fields, or empty dict if no valid frontmatter
    """
    if not content:
        return {}

    # Match YAML frontmatter between --- delimiters at start of file
    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return {}

    try:
        result = yaml.safe_load(match.group(1))
        return result if result else {}
    except yaml.YAMLError:
        return {}


def get_installed_file_info(path: Path) -> InstalledFile:
    """Get information about an installed copilot file.

    Args:
        path: Path to the installed file

    Returns:
        InstalledFile with parsed information

    Raises:
        FileNotFoundError: If the file does not exist
    """
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    filename = path.name
    content = path.read_text(encoding="utf-8")
    frontmatter = parse_frontmatter(content)

    # Determine file type based on filename and path
    if filename == "copilot-custom.md":
        file_type = FileType.CUSTOM
        is_custom = True
    elif filename == "copilot-instructions.md":
        file_type = FileType.INSTRUCTIONS
        is_custom = False
    elif filename.endswith(".instructions.md") or "/instructions/" in str(path):
        file_type = FileType.INSTRUCTION
        is_custom = False
    elif filename.endswith(".prompt.md") or "/prompts/" in str(path):
        file_type = FileType.PROMPT
        is_custom = False
    else:
        # Default to prompt for unknown files in .github
        file_type = FileType.PROMPT
        is_custom = False

    # Extract version info from frontmatter
    model = frontmatter.get("model")
    last_updated = frontmatter.get("last-updated")

    # Handle date conversion if needed
    if last_updated and not isinstance(last_updated, date):
        try:
            # YAML might parse as string in some cases
            if isinstance(last_updated, str):
                from datetime import datetime

                last_updated = datetime.fromisoformat(last_updated).date()
        except (ValueError, TypeError):
            last_updated = None

    return InstalledFile(
        path=path,
        filename=filename,
        file_type=file_type,
        model=model,
        last_updated=last_updated,
        is_custom=is_custom,
    )
