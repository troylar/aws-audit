"""Parse rule files (TXT, JSON, CSV) into lists of rule strings."""

from __future__ import annotations

import csv
import io
import json
import logging
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


def detect_format(file_path: str) -> str:
    """Auto-detect file format from extension.

    Args:
        file_path: Path to the file.

    Returns:
        Format string: "txt", "json", or "csv".

    Raises:
        ValueError: If the extension is not recognized.
    """
    ext = Path(file_path).suffix.lower()
    format_map = {
        ".txt": "txt",
        ".json": "json",
        ".csv": "csv",
    }
    if ext not in format_map:
        raise ValueError(
            f"Unrecognized file extension '{ext}'. "
            "Supported extensions: .txt, .json, .csv. "
            "Use --format to specify explicitly."
        )
    return format_map[ext]


def parse_rules_file(file_path: str, format_override: Optional[str] = None) -> List[str]:
    """Parse a file into a list of rule strings.

    Args:
        file_path: Path to the rules file.
        format_override: Explicit format ("txt", "json", "csv"). Auto-detected if None.

    Returns:
        List of rule strings.

    Raises:
        FileNotFoundError: If file does not exist.
        ValueError: On unrecognized format or invalid file content.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    fmt = format_override or detect_format(file_path)
    content = path.read_text(encoding="utf-8")

    parsers = {
        "txt": _parse_txt,
        "json": _parse_json,
        "csv": _parse_csv,
    }

    parser = parsers.get(fmt)
    if parser is None:
        raise ValueError(f"Unsupported format: {fmt}")

    return parser(content)


def _parse_txt(content: str) -> List[str]:
    """Parse TXT: one rule per line, skip blank lines and # comments."""
    rules = []
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        rules.append(stripped)
    return rules


def _parse_json(content: str) -> List[str]:
    """Parse JSON: list of strings, list of objects, or dict with 'rules' key."""
    data = json.loads(content)

    if isinstance(data, dict):
        if "rules" in data:
            data = data["rules"]
        else:
            raise ValueError("JSON object must contain a 'rules' key with a list of rules.")

    if not isinstance(data, list):
        raise ValueError("JSON must be a list of rules or an object with a 'rules' key.")

    rules = []
    for item in data:
        if isinstance(item, str):
            stripped = item.strip()
            if stripped:
                rules.append(stripped)
        elif isinstance(item, dict):
            rule_text = item.get("rule") or item.get("description") or item.get("requirement")
            if rule_text and isinstance(rule_text, str):
                rules.append(rule_text.strip())
        # Skip items that don't match expected shapes
    return rules


def _parse_csv(content: str) -> List[str]:
    """Parse CSV: use column named rule/description/requirement, or first column."""
    reader = csv.DictReader(io.StringIO(content))
    fieldnames = reader.fieldnames or []

    target_col = None
    for col_name in ("rule", "description", "requirement"):
        for fn in fieldnames:
            if fn.strip().lower() == col_name:
                target_col = fn
                break
        if target_col:
            break

    if target_col is None and fieldnames:
        target_col = fieldnames[0]

    if target_col is None:
        return []

    rules = []
    for row in reader:
        value = row.get(target_col, "")
        if value and value.strip():
            rules.append(value.strip())
    return rules
