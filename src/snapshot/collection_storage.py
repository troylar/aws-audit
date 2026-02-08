"""Storage service for collection management.

This module provides the main interface for collection persistence.
It uses SQLite as the primary storage backend, with automatic migration
from legacy YAML files on first use.
"""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Union

import yaml

from ..models.collection import Collection
from ..storage import CollectionStore, Database
from ..utils.paths import get_snapshot_storage_path

logger = logging.getLogger(__name__)


class CollectionNotFoundError(Exception):
    """Raised when a collection cannot be found."""

    pass


class CollectionStorage:
    """Manage collection storage and retrieval using SQLite backend.

    Handles CRUD operations for collections with automatic migration
    from legacy YAML files on first use.
    """

    def __init__(self, storage_dir: Optional[Union[str, Path]] = None):
        """Initialize collection storage.

        Args:
            storage_dir: Directory for storage (default: ~/.snapshots via get_snapshot_storage_path())
        """
        self.storage_dir = get_snapshot_storage_path(storage_dir)
        self.collections_file = self.storage_dir / "collections.yaml"
        # Also check for legacy inventories.yaml
        self._legacy_inventory_file = self.storage_dir / "inventories.yaml"

        # Ensure storage directory exists
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        # Initialize SQLite database
        self.db = Database(storage_path=self.storage_dir)
        self.db.ensure_schema()

        # Initialize collection store
        self._store = CollectionStore(self.db)

        # Auto-migrate YAML collections on first use
        self._migrate_yaml_if_needed()

    def _migrate_yaml_if_needed(self) -> None:
        """Migrate collections from YAML to SQLite if needed."""
        # Check both new and legacy filenames
        yaml_file = None
        if self.collections_file.exists():
            yaml_file = self.collections_file
        elif self._legacy_inventory_file.exists():
            yaml_file = self._legacy_inventory_file

        if not yaml_file:
            return

        # Check if we have collections in SQLite already
        existing = self._store.list_all()
        if existing:
            return  # Already migrated

        try:
            with open(yaml_file, "r") as f:
                data = yaml.safe_load(f)

            if not data:
                return

            # Support both "collections" and legacy "inventories" keys
            items = data.get("collections", data.get("inventories", []))
            if not items:
                return

            for item_data in items:
                collection = Collection.from_dict(item_data)
                self._store.save(collection)
                logger.debug(f"Migrated collection '{collection.name}' to SQLite")

            logger.info(f"Migrated {len(items)} collections from YAML to SQLite")

        except Exception as e:
            logger.warning(f"Failed to migrate YAML collections: {e}")

    def load_all(self) -> List[Collection]:
        """Load all collections.

        Returns:
            List of all collections (empty list if none exist)
        """
        collections = self._store.list_all()
        logger.debug(f"Loaded {len(collections)} collections from storage")
        return collections

    def load_by_account(self, account_id: str) -> List[Collection]:
        """Load collections for specific account.

        Args:
            account_id: AWS account ID (12 digits)

        Returns:
            List of collections for the account
        """
        collections = self._store.list_by_account(account_id)
        logger.debug(f"Found {len(collections)} collections for account {account_id}")
        return collections

    def get_by_name(self, name: str, account_id: str) -> Collection:
        """Get specific collection by name and account.

        Args:
            name: Collection name
            account_id: AWS account ID

        Returns:
            Collection instance

        Raises:
            CollectionNotFoundError: If collection not found
        """
        collection = self._store.load(name, account_id)
        if collection:
            logger.debug(f"Found collection '{name}' for account {account_id}")
            return collection

        raise CollectionNotFoundError(f"Collection '{name}' not found for account {account_id}")

    def get_or_create_default(self, account_id: str) -> Collection:
        """Get default collection, creating if it doesn't exist.

        Args:
            account_id: AWS account ID

        Returns:
            Default collection instance
        """
        try:
            return self.get_by_name("default", account_id)
        except CollectionNotFoundError:
            # Auto-create default collection
            default = Collection(
                name="default",
                account_id=account_id,
                description="Auto-created default collection",
                include_tags={},
                exclude_tags={},
                snapshots=[],
                active_snapshot=None,
                created_at=datetime.now(timezone.utc),
                last_updated=datetime.now(timezone.utc),
            )
            self.save(default)
            logger.info(f"Created default collection for account {account_id}")
            return default

    def save(self, collection: Collection) -> None:
        """Save/update collection.

        Args:
            collection: Collection to save

        Raises:
            ValueError: If collection validation fails
        """
        # Validate collection before saving
        errors = collection.validate()
        if errors:
            raise ValueError(f"Invalid collection: {', '.join(errors)}")

        self._store.save(collection)
        logger.debug(f"Saved collection '{collection.name}' for account {collection.account_id}")

    def delete(self, name: str, account_id: str, delete_snapshots: bool = False) -> int:
        """Delete collection, optionally deleting its snapshot files.

        Args:
            name: Collection name
            account_id: AWS account ID
            delete_snapshots: Whether to delete snapshot files

        Returns:
            Number of snapshot files deleted (0 if delete_snapshots=False)

        Raises:
            CollectionNotFoundError: If collection not found
        """
        # Load collection to get snapshot list
        collection = self.get_by_name(name, account_id)

        # Delete snapshot files if requested
        deleted_count = 0
        if delete_snapshots:
            from ..storage import SnapshotStore

            snapshot_store = SnapshotStore(self.db)
            for snapshot_name in collection.snapshots:
                # Remove file extensions if present
                snap_name = snapshot_name.replace(".yaml.gz", "").replace(".yaml", "")
                if snapshot_store.delete(snap_name):
                    deleted_count += 1
                    logger.debug(f"Deleted snapshot: {snap_name}")

        # Delete collection
        self._store.delete(name, account_id)
        logger.info(f"Deleted collection '{name}' for account {account_id}")

        return deleted_count

    def exists(self, name: str, account_id: str) -> bool:
        """Check if collection exists.

        Args:
            name: Collection name
            account_id: AWS account ID

        Returns:
            True if collection exists, False otherwise
        """
        return self._store.exists(name, account_id)

    def validate_unique(self, name: str, account_id: str) -> bool:
        """Validate that (name, account_id) combination is unique.

        Args:
            name: Collection name
            account_id: AWS account ID

        Returns:
            True if unique, False if already exists
        """
        return not self.exists(name, account_id)

    # Legacy methods for backward compatibility
    def _atomic_write(self, collections: List[Collection]) -> None:
        """Write collections using atomic rename pattern (legacy, no-op for SQLite)."""
        pass  # SQLite handles atomicity
