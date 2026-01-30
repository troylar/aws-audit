"""Export utilities for JSON and CSV formats."""

import csv
import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List

if TYPE_CHECKING:
    from src.models.report import DetailedResource, ResourceSummary, SnapshotMetadata

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


def detect_format(filepath: str) -> str:
    """
    Detect export format from file extension.

    Args:
        filepath: Path to file

    Returns:
        Format string: 'json', 'csv', or 'txt'

    Raises:
        ValueError: If format is not supported
    """
    path = Path(filepath)
    extension = path.suffix.lower()

    if extension == ".json":
        return "json"
    elif extension == ".csv":
        return "csv"
    elif extension == ".txt":
        return "txt"
    else:
        raise ValueError(f"Unsupported export format '{extension}'. Supported formats: .json, .csv, .txt")


def export_report_json(
    filepath: str,
    metadata: "SnapshotMetadata",
    summary: "ResourceSummary",
    resources: List["DetailedResource"],
) -> Path:
    """
    Export snapshot report to JSON format.

    Args:
        filepath: Destination file path
        metadata: Snapshot metadata
        summary: Resource summary
        resources: List of detailed resources

    Returns:
        Path to exported file

    Raises:
        FileExistsError: If file already exists
        FileNotFoundError: If parent directory doesn't exist
    """
    path = Path(filepath)

    # Check if file already exists
    if path.exists():
        raise FileExistsError(f"Export file '{filepath}' already exists")

    # Check if parent directory exists
    if not path.parent.exists():
        raise FileNotFoundError(f"Parent directory '{path.parent}' does not exist")

    # Build report data structure
    report_data = {
        "snapshot_metadata": {
            "name": metadata.name,
            "created_at": metadata.created_at.isoformat(),
            "account_id": metadata.account_id,
            "regions": metadata.regions,
            "inventory_name": metadata.inventory_name,
            "total_resource_count": metadata.total_resource_count,
        },
        "summary": {
            "total_count": summary.total_count,
            "by_service": dict(summary.by_service),
            "by_region": dict(summary.by_region),
            "by_type": dict(summary.by_type),
        },
        "resources": [
            {
                "arn": r.arn,
                "resource_type": r.resource_type,
                "name": r.name,
                "region": r.region,
                "tags": r.tags,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "config_hash": r.config_hash,
            }
            for r in resources
        ],
    }

    # Write to file
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2)

    logger.info(f"Exported report to JSON: {path}")
    return path


def export_report_csv(filepath: str, resources: List["DetailedResource"]) -> Path:
    """
    Export resources to CSV format.

    Args:
        filepath: Destination file path
        resources: List of detailed resources

    Returns:
        Path to exported file

    Raises:
        FileExistsError: If file already exists
        FileNotFoundError: If parent directory doesn't exist
    """
    path = Path(filepath)

    # Check if file already exists
    if path.exists():
        raise FileExistsError(f"Export file '{filepath}' already exists")

    # Check if parent directory exists
    if not path.parent.exists():
        raise FileNotFoundError(f"Parent directory '{path.parent}' does not exist")

    # Write CSV
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        # Write header
        writer.writerow(["ARN", "ResourceType", "Name", "Region", "CreatedAt", "Tags"])

        # Write resources
        for resource in resources:
            writer.writerow(
                [
                    resource.arn,
                    resource.resource_type,
                    resource.name,
                    resource.region,
                    resource.created_at.isoformat() if resource.created_at else "",
                    json.dumps(resource.tags) if resource.tags else "{}",
                ]
            )

    logger.info(f"Exported {len(resources)} resources to CSV: {path}")
    return path


def export_report_txt(
    filepath: str,
    metadata: "SnapshotMetadata",
    summary: "ResourceSummary",
) -> Path:
    """
    Export report summary to plain text format.

    Args:
        filepath: Destination file path
        metadata: Snapshot metadata
        summary: Resource summary

    Returns:
        Path to exported file

    Raises:
        FileExistsError: If file already exists
        FileNotFoundError: If parent directory doesn't exist
    """
    path = Path(filepath)

    # Check if file already exists
    if path.exists():
        raise FileExistsError(f"Export file '{filepath}' already exists")

    # Check if parent directory exists
    if not path.parent.exists():
        raise FileNotFoundError(f"Parent directory '{path.parent}' does not exist")

    # Build text content
    lines = []
    lines.append("=" * 65)
    lines.append(f"Snapshot Report: {metadata.name}")
    lines.append("=" * 65)
    lines.append("")
    lines.append(f"Inventory:     {metadata.inventory_name}")
    lines.append(f"Account ID:    {metadata.account_id}")
    lines.append(f"Created:       {metadata.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    lines.append(f"Regions:       {metadata.region_summary}")
    lines.append("")
    lines.append("─" * 65)
    lines.append("")
    lines.append("Resource Summary")
    lines.append("")
    lines.append(f"Total Resources: {summary.total_count:,}")
    lines.append("")

    if summary.by_service:
        lines.append("By Service:")
        for service, count in summary.top_services(limit=10):
            percentage = (count / summary.total_count) * 100 if summary.total_count > 0 else 0
            lines.append(f"  {service:20} {count:5}  ({percentage:.1f}%)")
        lines.append("")

    if summary.by_region:
        lines.append("By Region:")
        for region, count in summary.top_regions(limit=10):
            percentage = (count / summary.total_count) * 100 if summary.total_count > 0 else 0
            lines.append(f"  {region:20} {count:5}  ({percentage:.1f}%)")
        lines.append("")

    # Write to file
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    logger.info(f"Exported report to TXT: {path}")
    return path
