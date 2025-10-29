"""Storage service for inventory management."""

import logging
import os
from pathlib import Path
from typing import List, Optional, Union

import yaml

from ..models.inventory import Inventory
from ..utils.paths import get_snapshot_storage_path

logger = logging.getLogger(__name__)


class InventoryNotFoundError(Exception):
    """Raised when an inventory cannot be found."""

    pass


class InventoryStorage:
    """Manage inventory storage and retrieval.

    Handles CRUD operations for inventories stored in inventories.yaml file.
    Uses atomic writes (temp file + rename) for crash safety.
    """

    def __init__(self, storage_dir: Optional[Union[str, Path]] = None):
        """Initialize inventory storage.

        Args:
            storage_dir: Directory containing inventories.yaml (default: ~/.snapshots via get_snapshot_storage_path())
        """
        self.storage_dir = get_snapshot_storage_path(storage_dir)
        self.inventory_file = self.storage_dir / "inventories.yaml"

        # Ensure storage directory exists
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def load_all(self) -> List[Inventory]:
        """Load all inventories from inventories.yaml.

        Returns:
            List of all inventories (empty list if file doesn't exist)
        """
        if not self.inventory_file.exists():
            logger.debug("No inventories.yaml file found, returning empty list")
            return []

        try:
            with open(self.inventory_file, "r") as f:
                data = yaml.safe_load(f)

            if not data or "inventories" not in data:
                logger.debug("Empty or invalid inventories.yaml, returning empty list")
                return []

            inventories = [Inventory.from_dict(inv_data) for inv_data in data["inventories"]]
            logger.debug(f"Loaded {len(inventories)} inventories from storage")
            return inventories

        except yaml.YAMLError as e:
            logger.error(f"Failed to parse inventories.yaml: {e}")
            raise ValueError(f"Corrupted inventories file: {e}")
        except Exception as e:
            logger.error(f"Failed to load inventories: {e}")
            raise

    def load_by_account(self, account_id: str) -> List[Inventory]:
        """Load inventories for specific account.

        Args:
            account_id: AWS account ID (12 digits)

        Returns:
            List of inventories for the account
        """
        all_inventories = self.load_all()
        account_inventories = [inv for inv in all_inventories if inv.account_id == account_id]
        logger.debug(f"Found {len(account_inventories)} inventories for account {account_id}")
        return account_inventories

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
        account_inventories = self.load_by_account(account_id)

        for inventory in account_inventories:
            if inventory.name == name:
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
            from datetime import datetime, timezone

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
        """Save/update single inventory using atomic write.

        Args:
            inventory: Inventory to save

        Raises:
            ValueError: If inventory validation fails
        """
        # Validate inventory before saving
        errors = inventory.validate()
        if errors:
            raise ValueError(f"Invalid inventory: {', '.join(errors)}")

        # Load all inventories
        all_inventories = self.load_all()

        # Find and update existing, or append new
        updated = False
        for i, existing in enumerate(all_inventories):
            if existing.name == inventory.name and existing.account_id == inventory.account_id:
                all_inventories[i] = inventory
                updated = True
                logger.debug(f"Updated inventory '{inventory.name}' for account {inventory.account_id}")
                break

        if not updated:
            all_inventories.append(inventory)
            logger.debug(f"Added new inventory '{inventory.name}' for account {inventory.account_id}")

        # Write atomically
        self._atomic_write(all_inventories)

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
            snapshots_dir = self.storage_dir / "snapshots"
            for snapshot_file in inventory.snapshots:
                snapshot_path = snapshots_dir / snapshot_file
                try:
                    if snapshot_path.exists():
                        snapshot_path.unlink()
                        deleted_count += 1
                        logger.debug(f"Deleted snapshot file: {snapshot_file}")
                except Exception as e:
                    logger.warning(f"Failed to delete snapshot file {snapshot_file}: {e}")

        # Remove inventory from list
        all_inventories = self.load_all()
        all_inventories = [inv for inv in all_inventories if not (inv.name == name and inv.account_id == account_id)]

        # Write atomically
        self._atomic_write(all_inventories)
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
        try:
            self.get_by_name(name, account_id)
            return True
        except InventoryNotFoundError:
            return False

    def validate_unique(self, name: str, account_id: str) -> bool:
        """Validate that (name, account_id) combination is unique.

        Args:
            name: Inventory name
            account_id: AWS account ID

        Returns:
            True if unique, False if already exists
        """
        return not self.exists(name, account_id)

    def _atomic_write(self, inventories: List[Inventory]) -> None:
        """Write inventories using atomic rename pattern.

        This ensures crash safety - either the full write succeeds or it doesn't.
        Uses temp file + os.replace() which is atomic on all platforms.

        Args:
            inventories: List of all inventories to write
        """
        # Prepare data structure
        data = {"inventories": [inv.to_dict() for inv in inventories]}

        # Write to temp file
        temp_path = self.inventory_file.with_suffix(".tmp")
        try:
            with open(temp_path, "w") as f:
                yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)

            # Atomic rename (replaces existing file)
            os.replace(temp_path, self.inventory_file)
            logger.debug(f"Wrote {len(inventories)} inventories to storage")

        except Exception:
            # Clean up temp file on error
            if temp_path.exists():
                temp_path.unlink()
            raise
