"""Snapshot data model representing a point-in-time inventory of AWS resources."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class Snapshot:
    """Represents a point-in-time inventory of AWS resources.

    This serves as the baseline reference for delta tracking and cost analysis.

    Schema Versions:
    - v1.0: Basic snapshot with config_hash only
    - v1.1: Added raw_config for drift analysis support
    """

    name: str
    created_at: datetime
    account_id: str
    regions: List[str]
    resources: List[Any]  # List[Resource] - avoiding circular import
    is_active: bool = True
    resource_count: int = 0
    service_counts: Dict[str, int] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    filters_applied: Optional[Dict[str, Any]] = None
    total_resources_before_filter: Optional[int] = None
    inventory_name: str = "default"  # Name of inventory this snapshot belongs to
    schema_version: str = "1.1"  # Schema version for forward/backward compatibility

    def __post_init__(self) -> None:
        """Calculate derived fields after initialization."""
        if self.resource_count == 0:
            self.resource_count = len(self.resources)

        if not self.service_counts:
            self._calculate_service_counts()

    def _calculate_service_counts(self) -> None:
        """Calculate resource counts by service type."""
        counts: Dict[str, int] = {}
        for resource in self.resources:
            service = resource.resource_type.split(":")[0] if ":" in resource.resource_type else resource.resource_type
            counts[service] = counts.get(service, 0) + 1
        self.service_counts = counts

    def to_dict(self) -> Dict[str, Any]:
        """Convert snapshot to dictionary for serialization."""
        return {
            "schema_version": self.schema_version,
            "name": self.name,
            "created_at": self.created_at.isoformat(),
            "account_id": self.account_id,
            "regions": self.regions,
            "is_active": self.is_active,
            "resource_count": self.resource_count,
            "service_counts": self.service_counts,
            "metadata": self.metadata,
            "filters_applied": self.filters_applied,
            "total_resources_before_filter": self.total_resources_before_filter,
            "inventory_name": self.inventory_name,
            "resources": [r.to_dict() for r in self.resources],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Snapshot":
        """Create snapshot from dictionary.

        Supports both v1.0 and v1.1+ snapshot formats for backward compatibility.

        Note: This requires Resource class to be imported at call time
        to avoid circular imports.
        """
        from .resource import Resource

        # Handle created_at being either string or datetime (PyYAML can auto-parse)
        created_at = data["created_at"]
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)

        return cls(
            name=data["name"],
            created_at=created_at,
            account_id=data["account_id"],
            regions=data["regions"],
            resources=[Resource.from_dict(r) for r in data["resources"]],
            is_active=data.get("is_active", True),
            resource_count=data.get("resource_count", 0),
            service_counts=data.get("service_counts", {}),
            metadata=data.get("metadata", {}),
            filters_applied=data.get("filters_applied"),
            total_resources_before_filter=data.get("total_resources_before_filter"),
            inventory_name=data.get("inventory_name", "default"),  # Default for backward compatibility
            schema_version=data.get("schema_version", "1.0"),  # Default to 1.0 for old snapshots
        )

    def validate(self) -> bool:
        """Validate snapshot data integrity.

        Returns:
            True if valid, raises ValueError if invalid
        """
        import re

        # Validate name format (alphanumeric, hyphens, underscores)
        if not re.match(r"^[a-zA-Z0-9_-]+$", self.name):
            raise ValueError(
                f"Invalid snapshot name: {self.name}. "
                f"Must contain only alphanumeric characters, hyphens, and underscores."
            )

        # Validate account ID (12-digit string)
        if not re.match(r"^\d{12}$", self.account_id):
            raise ValueError(f"Invalid AWS account ID: {self.account_id}. Must be a 12-digit string.")

        # Validate regions list is not empty
        if not self.regions:
            raise ValueError("Snapshot must include at least one AWS region.")

        return True
