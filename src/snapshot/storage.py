"""Snapshot storage manager for saving and loading snapshots."""

import gzip
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml

from ..models.snapshot import Snapshot
from ..utils.paths import get_snapshot_storage_path

logger = logging.getLogger(__name__)


class SnapshotStorage:
    """Manages snapshot persistence to local filesystem."""

    def __init__(self, storage_dir: Optional[Union[str, Path]] = None):
        """Initialize snapshot storage.

        Args:
            storage_dir: Directory to store snapshots (default: ~/.snapshots via get_snapshot_storage_path())
        """
        self.storage_dir = get_snapshot_storage_path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.active_file = self.storage_dir / ".active"
        self.index_file = self.storage_dir / ".index.yaml"

    def save_snapshot(self, snapshot: Snapshot, compress: bool = False) -> Path:
        """Save snapshot to YAML file, optionally compressed.

        Args:
            snapshot: Snapshot instance to save
            compress: Whether to compress with gzip (default: False)

        Returns:
            Path to saved snapshot file
        """
        filename = f"{snapshot.name}.yaml"
        if compress:
            filename += ".gz"

        filepath = self.storage_dir / filename

        # Convert snapshot to dict
        snapshot_dict = snapshot.to_dict()

        # Serialize to YAML
        yaml_str = yaml.dump(
            snapshot_dict,
            default_flow_style=False,  # Block style (more readable)
            sort_keys=False,  # Preserve insertion order
            allow_unicode=True,
        )

        # Save (compressed or uncompressed)
        if compress:
            with gzip.open(filepath, "wt", encoding="utf-8") as f:
                f.write(yaml_str)
            logger.debug(f"Saved compressed snapshot to {filepath}")
        else:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(yaml_str)
            logger.debug(f"Saved snapshot to {filepath}")

        # Update index
        self._update_index(snapshot)

        # Set as active if requested
        if snapshot.is_active:
            self.set_active_snapshot(snapshot.name)

        return filepath

    def load_snapshot(self, snapshot_name: str) -> Snapshot:
        """Load snapshot from YAML file (auto-detects compression).

        Args:
            snapshot_name: Name of snapshot to load

        Returns:
            Snapshot instance

        Raises:
            FileNotFoundError: If snapshot file doesn't exist
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

        raise FileNotFoundError(f"Snapshot '{snapshot_name}' not found")

    def list_snapshots(self) -> List[Dict[str, Any]]:
        """List all available snapshots with metadata.

        Returns:
            List of snapshot metadata dictionaries
        """
        snapshots = []
        active_name = self.get_active_snapshot_name()

        # Find all snapshot files
        for filepath in self.storage_dir.glob("*.yaml*"):
            if filepath.name.startswith("."):
                continue  # Skip hidden files

            name = filepath.stem
            if name.endswith(".yaml"):  # Handle .yaml.gz case
                name = name[:-5]

            # Get file stats
            stats = filepath.stat()
            size_mb = stats.st_size / (1024 * 1024)

            snapshots.append(
                {
                    "name": name,
                    "filepath": str(filepath),
                    "size_mb": round(size_mb, 2),
                    "modified": datetime.fromtimestamp(stats.st_mtime),
                    "is_active": (name == active_name),
                }
            )

        # Sort by modified date (newest first)
        snapshots.sort(key=lambda x: x["modified"], reverse=True)  # type: ignore

        logger.debug(f"Found {len(snapshots)} snapshots")
        return snapshots

    def delete_snapshot(self, snapshot_name: str) -> bool:
        """Delete a snapshot file.

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
            raise ValueError(
                f"Cannot delete active snapshot '{snapshot_name}'. " "Set another snapshot as active first."
            )

        # Try to delete both compressed and uncompressed versions
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

        if not deleted:
            raise FileNotFoundError(f"Snapshot '{snapshot_name}' not found")

        # Update index
        self._remove_from_index(snapshot_name)

        return True

    def get_active_snapshot_name(self) -> Optional[str]:
        """Get the name of the currently active snapshot.

        Returns:
            Active snapshot name, or None if no active snapshot
        """
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
        # Verify snapshot exists
        try:
            self.load_snapshot(snapshot_name)
        except FileNotFoundError:
            raise FileNotFoundError(f"Cannot set active: snapshot '{snapshot_name}' not found")

        # Update active file
        self.active_file.write_text(snapshot_name)
        logger.debug(f"Set active snapshot to: {snapshot_name}")

    def _update_index(self, snapshot: Snapshot) -> None:
        """Update the snapshot index file.

        Args:
            snapshot: Snapshot to add/update in index
        """
        # Load existing index
        index = self._load_index()

        # Update entry
        index[snapshot.name] = {
            "name": snapshot.name,
            "created_at": snapshot.created_at.isoformat(),
            "account_id": snapshot.account_id,
            "regions": snapshot.regions,
            "resource_count": snapshot.resource_count,
            "service_counts": snapshot.service_counts,
        }

        # Save index
        self._save_index(index)

    def _remove_from_index(self, snapshot_name: str) -> None:
        """Remove snapshot from index.

        Args:
            snapshot_name: Name of snapshot to remove
        """
        index = self._load_index()
        if snapshot_name in index:
            del index[snapshot_name]
            self._save_index(index)

    def _load_index(self) -> Dict[str, Any]:
        """Load snapshot index from file."""
        if self.index_file.exists():
            with open(self.index_file, "r") as f:
                return yaml.safe_load(f) or {}
        return {}

    def _save_index(self, index: Dict[str, Any]) -> None:
        """Save snapshot index to file."""
        with open(self.index_file, "w") as f:
            yaml.dump(index, f, default_flow_style=False)
