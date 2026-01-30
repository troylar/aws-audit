"""Snapshot storage manager for saving and loading snapshots.

This module provides the main interface for snapshot persistence
using SQLite as the primary storage backend.
"""

import gzip
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml

from ..models.snapshot import Snapshot
from ..storage import Database, SnapshotStore
from ..utils.paths import get_snapshot_storage_path

logger = logging.getLogger(__name__)


class SnapshotStorage:
    """Manages snapshot persistence using SQLite backend."""

    def __init__(self, storage_dir: Optional[Union[str, Path]] = None):
        """Initialize snapshot storage.

        Args:
            storage_dir: Directory to store snapshots (default: ~/.snapshots via get_snapshot_storage_path())
        """
        self.storage_dir = get_snapshot_storage_path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.active_file = self.storage_dir / ".active"
        self.index_file = self.storage_dir / ".index.yaml"

        # Initialize SQLite database
        self.db = Database(storage_path=self.storage_dir)
        self.db.ensure_schema()

        # Initialize snapshot store
        self._store = SnapshotStore(self.db)

    def save_snapshot(self, snapshot: Snapshot, compress: bool = False) -> Path:
        """Save snapshot to SQLite database.

        Args:
            snapshot: Snapshot instance to save
            compress: Ignored (kept for backward compatibility)

        Returns:
            Path to database file (for compatibility)
        """
        # Save to SQLite
        self._store.save(snapshot)

        # Set as active if requested
        if snapshot.is_active:
            self._store.set_active(snapshot.name)
            # Also update legacy active file for compatibility
            self.active_file.write_text(snapshot.name)

        logger.debug(f"Saved snapshot '{snapshot.name}' with {len(snapshot.resources)} resources to SQLite")
        return self.db.db_path

    def load_snapshot(self, snapshot_name: str) -> Snapshot:
        """Load snapshot from SQLite database.

        Falls back to YAML files if not in database (for backward compatibility).

        Args:
            snapshot_name: Name of snapshot to load

        Returns:
            Snapshot instance

        Raises:
            FileNotFoundError: If snapshot doesn't exist
        """
        # Try SQLite first
        snapshot = self._store.load(snapshot_name)
        if snapshot:
            logger.debug(f"Loaded snapshot '{snapshot_name}' from SQLite")
            return snapshot

        # Fall back to YAML for backward compatibility
        snapshot = self._load_from_yaml(snapshot_name)
        if snapshot:
            # Migrate to SQLite on load
            logger.info(f"Migrating snapshot '{snapshot_name}' from YAML to SQLite")
            self._store.save(snapshot)
            return snapshot

        raise FileNotFoundError(f"Snapshot '{snapshot_name}' not found")

    def _load_from_yaml(self, snapshot_name: str) -> Optional[Snapshot]:
        """Load snapshot from legacy YAML file.

        Args:
            snapshot_name: Name of snapshot to load

        Returns:
            Snapshot instance or None if not found
        """
        # Try compressed first
        filepath_gz = self.storage_dir / f"{snapshot_name}.yaml.gz"
        if filepath_gz.exists():
            with gzip.open(filepath_gz, "rt", encoding="utf-8") as f:
                snapshot_dict = yaml.safe_load(f)
            logger.debug(f"Loaded compressed snapshot from {filepath_gz}")
            return Snapshot.from_dict(snapshot_dict)

        # Try uncompressed
        filepath = self.storage_dir / f"{snapshot_name}.yaml"
        if filepath.exists():
            with open(filepath, "r", encoding="utf-8") as f:
                snapshot_dict = yaml.safe_load(f)
            logger.debug(f"Loaded snapshot from {filepath}")
            return Snapshot.from_dict(snapshot_dict)

        return None

    def list_snapshots(self) -> List[Dict[str, Any]]:
        """List all available snapshots with metadata.

        Returns:
            List of snapshot metadata dictionaries
        """
        # Get snapshots from SQLite
        snapshots = self._store.list_all()

        # Get active snapshot name
        active_name = self.get_active_snapshot_name()

        # Convert to expected format and add is_active flag
        result = []
        for snap in snapshots:
            result.append(
                {
                    "name": snap["name"],
                    "filepath": str(self.db.db_path),
                    "size_mb": 0,  # Not applicable for SQLite
                    "modified": snap["created_at"],
                    "is_active": (snap["name"] == active_name),
                    "created_at": snap["created_at"],
                    "account_id": snap["account_id"],
                    "regions": snap["regions"],
                    "resource_count": snap["resource_count"],
                    "service_counts": snap["service_counts"],
                    "inventory_name": snap.get("inventory_name", "default"),
                }
            )

        logger.debug(f"Found {len(result)} snapshots")
        return result

    def delete_snapshot(self, snapshot_name: str) -> bool:
        """Delete a snapshot.

        Args:
            snapshot_name: Name of snapshot to delete

        Returns:
            True if deleted successfully

        Raises:
            ValueError: If trying to delete active snapshot
            FileNotFoundError: If snapshot doesn't exist
        """
        # Check if it's the active snapshot
        if snapshot_name == self.get_active_snapshot_name():
            raise ValueError(f"Cannot delete active snapshot '{snapshot_name}'. Set another snapshot as active first.")

        # Delete from SQLite
        if self._store.delete(snapshot_name):
            logger.debug(f"Deleted snapshot '{snapshot_name}' from SQLite")

            # Also delete YAML files if they exist (cleanup)
            self._delete_yaml_files(snapshot_name)
            return True

        # Try deleting YAML files directly (legacy)
        if self._delete_yaml_files(snapshot_name):
            return True

        raise FileNotFoundError(f"Snapshot '{snapshot_name}' not found")

    def _delete_yaml_files(self, snapshot_name: str) -> bool:
        """Delete legacy YAML files for a snapshot.

        Args:
            snapshot_name: Name of snapshot

        Returns:
            True if any files were deleted
        """
        deleted = False

        filepath_gz = self.storage_dir / f"{snapshot_name}.yaml.gz"
        if filepath_gz.exists():
            filepath_gz.unlink()
            deleted = True
            logger.debug(f"Deleted {filepath_gz}")

        filepath = self.storage_dir / f"{snapshot_name}.yaml"
        if filepath.exists():
            filepath.unlink()
            deleted = True
            logger.debug(f"Deleted {filepath}")

        return deleted

    def get_active_snapshot_name(self) -> Optional[str]:
        """Get the name of the currently active snapshot.

        Returns:
            Active snapshot name, or None if no active snapshot
        """
        # Try SQLite first
        active = self._store.get_active()
        if active:
            return active

        # Fall back to legacy file
        if self.active_file.exists():
            return self.active_file.read_text().strip()

        return None

    def set_active_snapshot(self, snapshot_name: str) -> None:
        """Set a snapshot as the active baseline.

        Args:
            snapshot_name: Name of snapshot to set as active

        Raises:
            FileNotFoundError: If snapshot doesn't exist
        """
        # Verify snapshot exists (in SQLite or YAML)
        if not self._store.exists(snapshot_name):
            # Try loading from YAML (will migrate to SQLite)
            try:
                self.load_snapshot(snapshot_name)
            except FileNotFoundError:
                raise FileNotFoundError(f"Cannot set active: snapshot '{snapshot_name}' not found")

        # Update in SQLite
        self._store.set_active(snapshot_name)

        # Update legacy active file for compatibility
        self.active_file.write_text(snapshot_name)
        logger.debug(f"Set active snapshot to: {snapshot_name}")

    def snapshot_exists(self, snapshot_name: str) -> bool:
        """Check if a snapshot exists.

        Args:
            snapshot_name: Name of snapshot

        Returns:
            True if snapshot exists
        """
        # Check SQLite
        if self._store.exists(snapshot_name):
            return True

        # Check YAML files
        filepath_gz = self.storage_dir / f"{snapshot_name}.yaml.gz"
        filepath = self.storage_dir / f"{snapshot_name}.yaml"
        return filepath_gz.exists() or filepath.exists()

    def exists(self, snapshot_name: str) -> bool:
        """Alias for snapshot_exists for consistency.

        Args:
            snapshot_name: Name of snapshot

        Returns:
            True if snapshot exists
        """
        return self.snapshot_exists(snapshot_name)

    def rename_snapshot(self, old_name: str, new_name: str) -> bool:
        """Rename a snapshot.

        Args:
            old_name: Current snapshot name
            new_name: New snapshot name

        Returns:
            True if renamed successfully

        Raises:
            FileNotFoundError: If old_name doesn't exist
            ValueError: If new_name already exists
        """
        if not self.snapshot_exists(old_name):
            raise FileNotFoundError(f"Snapshot '{old_name}' not found")

        if self.snapshot_exists(new_name):
            raise ValueError(f"Snapshot '{new_name}' already exists")

        # Rename in SQLite
        if self._store.exists(old_name):
            self._store.rename(old_name, new_name)

            # Update active snapshot reference if needed
            if self.get_active_snapshot_name() == old_name:
                self._store.set_active(new_name)
                self.active_file.write_text(new_name)

            logger.debug(f"Renamed snapshot '{old_name}' to '{new_name}' in SQLite")
            return True

        # Handle YAML files (legacy)
        renamed = False
        for ext in [".yaml.gz", ".yaml"]:
            old_path = self.storage_dir / f"{old_name}{ext}"
            new_path = self.storage_dir / f"{new_name}{ext}"
            if old_path.exists():
                old_path.rename(new_path)
                renamed = True
                logger.debug(f"Renamed {old_path} to {new_path}")
                break

        # Update active if needed
        if renamed and self.get_active_snapshot_name() == old_name:
            self.active_file.write_text(new_name)

        return renamed

    # Legacy index methods (kept for backward compatibility)
    def _update_index(self, snapshot: Snapshot) -> None:
        """Update the snapshot index file (no-op for SQLite)."""
        pass  # Index is now managed by SQLite

    def _remove_from_index(self, snapshot_name: str) -> None:
        """Remove snapshot from index (no-op for SQLite)."""
        pass  # Index is now managed by SQLite

    def _load_index(self) -> Dict[str, Any]:
        """Load snapshot index from file (deprecated)."""
        if self.index_file.exists():
            with open(self.index_file, "r") as f:
                return yaml.safe_load(f) or {}
        return {}

    def _save_index(self, index: Dict[str, Any]) -> None:
        """Save snapshot index to file (deprecated)."""
        pass  # Index is now managed by SQLite
