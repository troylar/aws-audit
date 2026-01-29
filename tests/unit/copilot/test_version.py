"""Unit tests for copilot version parsing (T006)."""

from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.copilot.models import FileType, InstalledFile, ModelVersionHeader
from src.copilot.version import get_installed_file_info, parse_frontmatter


class TestParseFrontmatter:
    """Tests for parse_frontmatter function."""

    def test_parse_valid_frontmatter(self) -> None:
        """parse_frontmatter extracts YAML from valid frontmatter."""
        content = """---
model: gpt-4.1
optimizations:
  - token-efficient
  - terse rules
last-updated: 2026-01-29
---

# Main content here
"""
        result = parse_frontmatter(content)
        assert result["model"] == "gpt-4.1"
        assert result["optimizations"] == ["token-efficient", "terse rules"]
        assert result["last-updated"] == date(2026, 1, 29)

    def test_parse_frontmatter_with_constraints(self) -> None:
        """parse_frontmatter handles constraints field."""
        content = """---
model: gpt-4.1
optimizations:
  - token-efficient
constraints:
  base-instructions-tokens: 4000
  task-prompt-tokens: 2000
last-updated: 2026-01-29
---

Content
"""
        result = parse_frontmatter(content)
        assert result["constraints"]["base-instructions-tokens"] == 4000
        assert result["constraints"]["task-prompt-tokens"] == 2000

    def test_parse_frontmatter_empty_content(self) -> None:
        """parse_frontmatter returns empty dict for empty content."""
        result = parse_frontmatter("")
        assert result == {}

    def test_parse_frontmatter_no_frontmatter(self) -> None:
        """parse_frontmatter returns empty dict when no frontmatter present."""
        content = "# Just markdown without frontmatter\n\nSome content."
        result = parse_frontmatter(content)
        assert result == {}

    def test_parse_frontmatter_unclosed(self) -> None:
        """parse_frontmatter returns empty dict for unclosed frontmatter."""
        content = """---
model: gpt-4.1

# No closing ---
"""
        result = parse_frontmatter(content)
        assert result == {}

    def test_parse_frontmatter_only_one_delimiter(self) -> None:
        """parse_frontmatter requires both opening and closing delimiters."""
        content = """---
model: gpt-4.1
"""
        result = parse_frontmatter(content)
        assert result == {}

    def test_parse_frontmatter_malformed_yaml(self) -> None:
        """parse_frontmatter returns empty dict for malformed YAML."""
        content = """---
model: [unclosed bracket
---

Content
"""
        result = parse_frontmatter(content)
        assert result == {}

    def test_parse_frontmatter_preserves_types(self) -> None:
        """parse_frontmatter preserves YAML types correctly."""
        content = """---
model: gpt-4.1
optimizations:
  - item1
  - item2
constraints:
  tokens: 4000
  enabled: true
last-updated: 2026-01-29
---
"""
        result = parse_frontmatter(content)
        assert isinstance(result["optimizations"], list)
        assert isinstance(result["constraints"], dict)
        assert isinstance(result["constraints"]["tokens"], int)
        assert isinstance(result["constraints"]["enabled"], bool)


class TestGetInstalledFileInfo:
    """Tests for get_installed_file_info function."""

    def test_get_file_info_instructions_file(self) -> None:
        """get_installed_file_info identifies instructions file."""
        content = """---
model: gpt-4.1
optimizations:
  - token-efficient
last-updated: 2026-01-29
---

# Instructions
"""
        mock_path = MagicMock(spec=Path)
        mock_path.exists.return_value = True
        mock_path.name = "copilot-instructions.md"
        mock_path.read_text.return_value = content
        mock_path.__str__ = lambda self: "/project/.github/copilot-instructions.md"

        info = get_installed_file_info(mock_path)

        assert info.filename == "copilot-instructions.md"
        assert info.file_type == FileType.INSTRUCTIONS
        assert info.model == "gpt-4.1"
        assert info.last_updated == date(2026, 1, 29)
        assert info.is_custom is False

    def test_get_file_info_prompt_file(self) -> None:
        """get_installed_file_info identifies prompt file."""
        content = """---
model: gpt-4.1
optimizations:
  - terraform-specific
last-updated: 2026-01-29
---

# Terraform prompt
"""
        mock_path = MagicMock(spec=Path)
        mock_path.exists.return_value = True
        mock_path.name = "generate-terraform.md"
        mock_path.read_text.return_value = content
        mock_path.__str__ = lambda self: "/project/.github/copilot-prompts/generate-terraform.md"

        info = get_installed_file_info(mock_path)

        assert info.filename == "generate-terraform.md"
        assert info.file_type == FileType.PROMPT
        assert info.model == "gpt-4.1"
        assert info.is_custom is False

    def test_get_file_info_custom_file(self) -> None:
        """get_installed_file_info identifies custom file."""
        content = "# My custom instructions\n\nNo frontmatter here."
        mock_path = MagicMock(spec=Path)
        mock_path.exists.return_value = True
        mock_path.name = "copilot-custom.md"
        mock_path.read_text.return_value = content
        mock_path.__str__ = lambda self: "/project/.github/copilot-custom.md"

        info = get_installed_file_info(mock_path)

        assert info.filename == "copilot-custom.md"
        assert info.file_type == FileType.CUSTOM
        assert info.model is None
        assert info.last_updated is None
        assert info.is_custom is True

    def test_get_file_info_no_frontmatter(self) -> None:
        """get_installed_file_info handles files without frontmatter."""
        content = "# Just content, no frontmatter"
        mock_path = MagicMock(spec=Path)
        mock_path.exists.return_value = True
        mock_path.name = "copilot-instructions.md"
        mock_path.read_text.return_value = content
        mock_path.__str__ = lambda self: "/project/.github/copilot-instructions.md"

        info = get_installed_file_info(mock_path)

        assert info.model is None
        assert info.last_updated is None

    def test_get_file_info_file_not_found(self) -> None:
        """get_installed_file_info raises FileNotFoundError for missing file."""
        mock_path = MagicMock(spec=Path)
        mock_path.exists.return_value = False

        with pytest.raises(FileNotFoundError):
            get_installed_file_info(mock_path)

    def test_get_file_info_cdk_typescript_prompt(self) -> None:
        """get_installed_file_info identifies CDK TypeScript prompt."""
        content = """---
model: gpt-4.1
optimizations:
  - cdk-specific
last-updated: 2026-01-29
---
"""
        mock_path = MagicMock(spec=Path)
        mock_path.exists.return_value = True
        mock_path.name = "generate-cdk-typescript.md"
        mock_path.read_text.return_value = content
        mock_path.__str__ = lambda self: "/project/.github/copilot-prompts/generate-cdk-typescript.md"

        info = get_installed_file_info(mock_path)

        assert info.file_type == FileType.PROMPT
        assert info.filename == "generate-cdk-typescript.md"

    def test_get_file_info_cdk_python_prompt(self) -> None:
        """get_installed_file_info identifies CDK Python prompt."""
        content = """---
model: gpt-4.1
optimizations:
  - cdk-python-specific
last-updated: 2026-01-29
---
"""
        mock_path = MagicMock(spec=Path)
        mock_path.exists.return_value = True
        mock_path.name = "generate-cdk-python.md"
        mock_path.read_text.return_value = content
        mock_path.__str__ = lambda self: "/project/.github/copilot-prompts/generate-cdk-python.md"

        info = get_installed_file_info(mock_path)

        assert info.file_type == FileType.PROMPT
        assert info.filename == "generate-cdk-python.md"
