"""Storage service for inventory management.

This module provides the main interface for inventory persistence.
It uses SQLite as the primary storage backend, with automatic migration
from legacy YAML files on first use.
"""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Union

import yaml

from ..models.inventory import Inventory
from ..storage import Database, InventoryStore
from ..utils.paths import get_snapshot_storage_path

logger = logging.getLogger(__name__)


class InventoryNotFoundError(Exception):
    """Raised when an inventory cannot be found."""

    pass


class InventoryStorage:
    """Manage inventory storage and retrieval using SQLite backend.

    Handles CRUD operations for inventories with automatic migration
    from legacy YAML files on first use.
    """

    def __init__(self, storage_dir: Optional[Union[str, Path]] = None):
        """Initialize inventory storage.

        Args:
            storage_dir: Directory for storage (default: ~/.snapshots via get_snapshot_storage_path())
        """
        self.storage_dir = get_snapshot_storage_path(storage_dir)
        self.inventory_file = self.storage_dir / "inventories.yaml"

        # Ensure storage directory exists
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        # Initialize SQLite database
        self.db = Database(storage_path=self.storage_dir)
        self.db.ensure_schema()

        # Initialize inventory store
        self._store = InventoryStore(self.db)

        # Auto-migrate YAML inventories on first use
        self._migrate_yaml_if_needed()

    def _migrate_yaml_if_needed(self) -> None:
        """Migrate inventories from YAML to SQLite if needed."""
        if not self.inventory_file.exists():
            return

        # Check if we have inventories in SQLite already
        existing = self._store.list_all()
        if existing:
            return  # Already migrated

        try:
            with open(self.inventory_file, "r") as f:
                data = yaml.safe_load(f)

            if not data or "inventories" not in data:
                return

            for inv_data in data["inventories"]:
                inventory = Inventory.from_dict(inv_data)
                self._store.save(inventory)
                logger.debug(f"Migrated inventory '{inventory.name}' to SQLite")

            logger.info(f"Migrated {len(data['inventories'])} inventories from YAML to SQLite")

        except Exception as e:
            logger.warning(f"Failed to migrate YAML inventories: {e}")

    def load_all(self) -> List[Inventory]:
        """Load all inventories.

        Returns:
            List of all inventories (empty list if none exist)
        """
        inventories = self._store.list_all()
        logger.debug(f"Loaded {len(inventories)} inventories from storage")
        return inventories

    def load_by_account(self, account_id: str) -> List[Inventory]:
        """Load inventories for specific account.

        Args:
            account_id: AWS account ID (12 digits)

        Returns:
            List of inventories for the account
        """
        inventories = self._store.list_by_account(account_id)
        logger.debug(f"Found {len(inventories)} inventories for account {account_id}")
        return inventories

    def get_by_name(self, name: str, account_id: str) -> Inventory:
        """Get specific inventory by name and account.

        Args:
            name: Inventory name
            account_id: AWS account ID

        Returns:
            Inventory instance

        Raises:
            InventoryNotFoundError: If inventory not found
        """
        inventory = self._store.load(name, account_id)
        if inventory:
            logger.debug(f"Found inventory '{name}' for account {account_id}")
            return inventory

        raise InventoryNotFoundError(f"Inventory '{name}' not found for account {account_id}")

    def get_or_create_default(self, account_id: str) -> Inventory:
        """Get default inventory, creating if it doesn't exist.

        Args:
            account_id: AWS account ID

        Returns:
            Default inventory instance
        """
        try:
            return self.get_by_name("default", account_id)
        except InventoryNotFoundError:
            # Auto-create default inventory
            default = Inventory(
                name="default",
                account_id=account_id,
                description="Auto-created default inventory",
                include_tags={},
                exclude_tags={},
                snapshots=[],
                active_snapshot=None,
                created_at=datetime.now(timezone.utc),
                last_updated=datetime.now(timezone.utc),
            )
            self.save(default)
            logger.info(f"Created default inventory for account {account_id}")
            return default

    def save(self, inventory: Inventory) -> None:
        """Save/update inventory.

        Args:
            inventory: Inventory to save

        Raises:
            ValueError: If inventory validation fails
        """
        # Validate inventory before saving
        errors = inventory.validate()
        if errors:
            raise ValueError(f"Invalid inventory: {', '.join(errors)}")

        self._store.save(inventory)
        logger.debug(f"Saved inventory '{inventory.name}' for account {inventory.account_id}")

    def delete(self, name: str, account_id: str, delete_snapshots: bool = False) -> int:
        """Delete inventory, optionally deleting its snapshot files.

        Args:
            name: Inventory name
            account_id: AWS account ID
            delete_snapshots: Whether to delete snapshot files

        Returns:
            Number of snapshot files deleted (0 if delete_snapshots=False)

        Raises:
            InventoryNotFoundError: If inventory not found
        """
        # Load inventory to get snapshot list
        inventory = self.get_by_name(name, account_id)

        # Delete snapshot files if requested
        deleted_count = 0
        if delete_snapshots:
            from ..storage import SnapshotStore

            snapshot_store = SnapshotStore(self.db)
            for snapshot_name in inventory.snapshots:
                # Remove file extensions if present
                snap_name = snapshot_name.replace(".yaml.gz", "").replace(".yaml", "")
                if snapshot_store.delete(snap_name):
                    deleted_count += 1
                    logger.debug(f"Deleted snapshot: {snap_name}")

        # Delete inventory
        self._store.delete(name, account_id)
        logger.info(f"Deleted inventory '{name}' for account {account_id}")

        return deleted_count

    def exists(self, name: str, account_id: str) -> bool:
        """Check if inventory exists.

        Args:
            name: Inventory name
            account_id: AWS account ID

        Returns:
            True if inventory exists, False otherwise
        """
        return self._store.exists(name, account_id)

    def validate_unique(self, name: str, account_id: str) -> bool:
        """Validate that (name, account_id) combination is unique.

        Args:
            name: Inventory name
            account_id: AWS account ID

        Returns:
            True if unique, False if already exists
        """
        return not self.exists(name, account_id)

    # Legacy methods for backward compatibility
    def _atomic_write(self, inventories: List[Inventory]) -> None:
        """Write inventories using atomic rename pattern (legacy, no-op for SQLite)."""
        pass  # SQLite handles atomicity
