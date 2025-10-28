"""Export utilities for JSON and CSV formats."""

import csv
import json
import logging
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def export_to_json(data: Any, filepath: str) -> Path:
    """Export data to JSON file.

    Args:
        data: Data to export (must be JSON-serializable)
        filepath: Destination file path

    Returns:
        Path to exported file
    """
    path = Path(filepath)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)

    logger.info(f"Exported data to JSON: {path}")
    return path


def export_to_csv(data: List[Dict[str, Any]], filepath: str) -> Path:
    """Export list of dictionaries to CSV file.

    Args:
        data: List of dictionaries to export
        filepath: Destination file path

    Returns:
        Path to exported file

    Raises:
        ValueError: If data is empty or not a list of dicts
    """
    if not data:
        raise ValueError("Cannot export empty data to CSV")

    if not isinstance(data, list) or not isinstance(data[0], dict):
        raise ValueError("Data must be a list of dictionaries for CSV export")

    path = Path(filepath)

    # Get fieldnames from first item
    fieldnames = list(data[0].keys())

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)

    logger.info(f"Exported {len(data)} rows to CSV: {path}")
    return path


def flatten_dict(d: Dict[str, Any], parent_key: str = "", sep: str = "_") -> Dict[str, Any]:
    """Flatten a nested dictionary for CSV export.

    Args:
        d: Dictionary to flatten
        parent_key: Parent key for nested items
        sep: Separator for concatenating keys

    Returns:
        Flattened dictionary
    """
    from typing import Any, List, Tuple

    items: List[Tuple[str, Any]] = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        elif isinstance(v, list):
            # Convert lists to comma-separated strings
            items.append((new_key, ", ".join(str(x) for x in v)))
        else:
            items.append((new_key, v))
    return dict(items)
