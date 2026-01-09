"""Inventory model for organizing snapshots by account and purpose."""

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class Inventory:
    """Named container for organizing snapshots by account and purpose.

    Attributes:
        name: Unique identifier within account (alphanumeric + hyphens + underscores, 1-50 chars)
        account_id: AWS account ID (12 digits)
        include_tags: Tag filters (resource MUST have ALL)
        exclude_tags: Tag filters (resource MUST NOT have ANY)
        snapshots: List of snapshot filenames in this inventory
        active_snapshot: Filename of active baseline snapshot
        description: Human-readable description
        created_at: Inventory creation timestamp (timezone-aware UTC)
        last_updated: Last modification timestamp (timezone-aware UTC, auto-updated)
    """

    name: str
    account_id: str
    include_tags: Dict[str, str] = field(default_factory=dict)
    exclude_tags: Dict[str, str] = field(default_factory=dict)
    snapshots: List[str] = field(default_factory=list)
    active_snapshot: Optional[str] = None
    description: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for YAML storage.

        Returns:
            Dictionary representation suitable for YAML serialization
        """
        return {
            "name": self.name,
            "account_id": self.account_id,
            "description": self.description,
            "include_tags": self.include_tags,
            "exclude_tags": self.exclude_tags,
            "snapshots": self.snapshots,
            "active_snapshot": self.active_snapshot,
            "created_at": self.created_at.isoformat(),
            "last_updated": self.last_updated.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Inventory":
        """Deserialize from dictionary (YAML load).

        Args:
            data: Dictionary loaded from YAML

        Returns:
            Inventory instance
        """
        # Handle datetime fields being either string or datetime (PyYAML can auto-parse)
        created_at = data["created_at"]
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)

        last_updated = data["last_updated"]
        if isinstance(last_updated, str):
            last_updated = datetime.fromisoformat(last_updated)

        return cls(
            name=data["name"],
            account_id=data["account_id"],
            description=data.get("description", ""),
            include_tags=data.get("include_tags", {}),
            exclude_tags=data.get("exclude_tags", {}),
            snapshots=data.get("snapshots", []),
            active_snapshot=data.get("active_snapshot"),
            created_at=created_at,
            last_updated=last_updated,
        )

    def add_snapshot(self, snapshot_filename: str, set_active: bool = False) -> None:
        """Add snapshot to inventory, optionally marking as active.

        Args:
            snapshot_filename: Name of snapshot file to add
            set_active: Whether to mark this snapshot as active baseline
        """
        if snapshot_filename not in self.snapshots:
            self.snapshots.append(snapshot_filename)
        if set_active:
            self.active_snapshot = snapshot_filename
        self.last_updated = datetime.now(timezone.utc)

    def remove_snapshot(self, snapshot_filename: str) -> None:
        """Remove snapshot from inventory, clearing active if it was active.

        Args:
            snapshot_filename: Name of snapshot file to remove
        """
        if snapshot_filename in self.snapshots:
            self.snapshots.remove(snapshot_filename)
        if self.active_snapshot == snapshot_filename:
            self.active_snapshot = None
        self.last_updated = datetime.now(timezone.utc)

    def validate(self) -> List[str]:
        """Validate inventory data, return list of errors.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        # Validate name format (alphanumeric + hyphens + underscores only)
        if not self.name or not re.match(r"^[a-zA-Z0-9_-]+$", self.name):
            errors.append("Name must contain only alphanumeric characters, hyphens, and underscores")

        # Validate name length
        if len(self.name) > 50:
            errors.append("Name must be 50 characters or less")

        # Validate account ID format (12 digits)
        if not self.account_id or not re.match(r"^\d{12}$", self.account_id):
            errors.append("Account ID must be 12 digits")

        # Validate active snapshot exists in snapshots list
        if self.active_snapshot and self.active_snapshot not in self.snapshots:
            errors.append("Active snapshot must exist in snapshots list")

        return errors
