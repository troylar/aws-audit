"""Inventory storage operations for SQLite backend."""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..models.inventory import Inventory
from .database import Database, json_deserialize, json_serialize

logger = logging.getLogger(__name__)


class InventoryStore:
    """CRUD operations for inventories in SQLite database."""

    def __init__(self, db: Database):
        """Initialize inventory store.

        Args:
            db: Database connection manager
        """
        self.db = db

    def save(self, inventory: Inventory) -> int:
        """Save or update inventory in database.

        Args:
            inventory: Inventory to save

        Returns:
            Database ID of saved inventory
        """
        # Get active snapshot ID if set
        active_snapshot_id = None
        if inventory.active_snapshot:
            # Look up snapshot ID by name (remove file extensions if present)
            snap_name = inventory.active_snapshot.replace(".yaml.gz", "").replace(".yaml", "")
            row = self.db.fetchone("SELECT id FROM snapshots WHERE name = ?", (snap_name,))
            if row:
                active_snapshot_id = row["id"]

        with self.db.transaction() as cursor:
            # Check if inventory exists
            existing = self.db.fetchone(
                "SELECT id FROM inventories WHERE name = ? AND account_id = ?",
                (inventory.name, inventory.account_id),
            )

            if existing:
                # Update existing
                cursor.execute(
                    """
                    UPDATE inventories SET
                        description = ?,
                        include_tags = ?,
                        exclude_tags = ?,
                        active_snapshot_id = ?,
                        last_updated = ?
                    WHERE id = ?
                    """,
                    (
                        inventory.description,
                        json_serialize(inventory.include_tags),
                        json_serialize(inventory.exclude_tags),
                        active_snapshot_id,
                        inventory.last_updated.isoformat(),
                        existing["id"],
                    ),
                )
                inventory_id = existing["id"]

                # Update snapshot links
                self._update_snapshot_links(cursor, inventory_id, inventory.snapshots)

                logger.debug(f"Updated inventory '{inventory.name}' (id={inventory_id})")
            else:
                # Insert new
                cursor.execute(
                    """
                    INSERT INTO inventories (
                        name, account_id, description, include_tags, exclude_tags,
                        active_snapshot_id, created_at, last_updated
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        inventory.name,
                        inventory.account_id,
                        inventory.description,
                        json_serialize(inventory.include_tags),
                        json_serialize(inventory.exclude_tags),
                        active_snapshot_id,
                        inventory.created_at.isoformat(),
                        inventory.last_updated.isoformat(),
                    ),
                )
                inventory_id = cursor.lastrowid

                # Add snapshot links
                self._update_snapshot_links(cursor, inventory_id, inventory.snapshots)

                logger.debug(f"Saved inventory '{inventory.name}' (id={inventory_id})")

            return inventory_id

    def _update_snapshot_links(self, cursor, inventory_id: int, snapshot_names: List[str]) -> None:
        """Update inventory-snapshot links.

        Args:
            cursor: Database cursor
            inventory_id: Inventory ID
            snapshot_names: List of snapshot names to link
        """
        # Clear existing links
        cursor.execute("DELETE FROM inventory_snapshots WHERE inventory_id = ?", (inventory_id,))

        # Add new links
        for snap_name in snapshot_names:
            # Remove file extensions if present
            snap_name = snap_name.replace(".yaml.gz", "").replace(".yaml", "")
            row = self.db.fetchone("SELECT id FROM snapshots WHERE name = ?", (snap_name,))
            if row:
                cursor.execute(
                    "INSERT OR IGNORE INTO inventory_snapshots (inventory_id, snapshot_id) VALUES (?, ?)",
                    (inventory_id, row["id"]),
                )

    def load(self, name: str, account_id: str) -> Optional[Inventory]:
        """Load inventory by name and account.

        Args:
            name: Inventory name
            account_id: AWS account ID

        Returns:
            Inventory object or None if not found
        """
        row = self.db.fetchone(
            "SELECT * FROM inventories WHERE name = ? AND account_id = ?",
            (name, account_id),
        )
        if not row:
            return None

        return self._row_to_inventory(row)

    def _row_to_inventory(self, row: Dict[str, Any]) -> Inventory:
        """Convert database row to Inventory object.

        Args:
            row: Database row dict

        Returns:
            Inventory object
        """
        inventory_id = row["id"]

        # Get linked snapshot names
        snapshot_rows = self.db.fetchall(
            """
            SELECT s.name FROM snapshots s
            JOIN inventory_snapshots is_link ON s.id = is_link.snapshot_id
            WHERE is_link.inventory_id = ?
            ORDER BY s.created_at DESC
            """,
            (inventory_id,),
        )
        snapshots = [r["name"] for r in snapshot_rows]

        # Get active snapshot name
        active_snapshot = None
        if row["active_snapshot_id"]:
            active_row = self.db.fetchone(
                "SELECT name FROM snapshots WHERE id = ?",
                (row["active_snapshot_id"],),
            )
            if active_row:
                active_snapshot = active_row["name"]

        # Parse timestamps
        created_at = datetime.fromisoformat(row["created_at"])
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)

        last_updated = datetime.fromisoformat(row["last_updated"])
        if last_updated.tzinfo is None:
            last_updated = last_updated.replace(tzinfo=timezone.utc)

        return Inventory(
            name=row["name"],
            account_id=row["account_id"],
            description=row["description"] or "",
            include_tags=json_deserialize(row["include_tags"]) or {},
            exclude_tags=json_deserialize(row["exclude_tags"]) or {},
            snapshots=snapshots,
            active_snapshot=active_snapshot,
            created_at=created_at,
            last_updated=last_updated,
        )

    def list_all(self) -> List[Inventory]:
        """List all inventories.

        Returns:
            List of all Inventory objects
        """
        rows = self.db.fetchall("SELECT * FROM inventories ORDER BY account_id, name")
        return [self._row_to_inventory(row) for row in rows]

    def list_by_account(self, account_id: str) -> List[Inventory]:
        """List inventories for a specific account.

        Args:
            account_id: AWS account ID

        Returns:
            List of Inventory objects for the account
        """
        rows = self.db.fetchall(
            "SELECT * FROM inventories WHERE account_id = ? ORDER BY name",
            (account_id,),
        )
        return [self._row_to_inventory(row) for row in rows]

    def delete(self, name: str, account_id: str) -> bool:
        """Delete inventory.

        Args:
            name: Inventory name
            account_id: AWS account ID

        Returns:
            True if deleted, False if not found
        """
        with self.db.transaction() as cursor:
            cursor.execute(
                "DELETE FROM inventories WHERE name = ? AND account_id = ?",
                (name, account_id),
            )
            deleted = cursor.rowcount > 0

        if deleted:
            logger.debug(f"Deleted inventory '{name}' for account {account_id}")
        return deleted

    def exists(self, name: str, account_id: str) -> bool:
        """Check if inventory exists.

        Args:
            name: Inventory name
            account_id: AWS account ID

        Returns:
            True if exists
        """
        row = self.db.fetchone(
            "SELECT 1 FROM inventories WHERE name = ? AND account_id = ?",
            (name, account_id),
        )
        return row is not None

    def add_snapshot_to_inventory(
        self, name: str, account_id: str, snapshot_name: str, set_active: bool = False
    ) -> bool:
        """Add a snapshot to an inventory.

        Args:
            name: Inventory name
            account_id: AWS account ID
            snapshot_name: Snapshot name to add
            set_active: Whether to set this as the active snapshot

        Returns:
            True if successful, False if inventory not found
        """
        inventory = self.load(name, account_id)
        if not inventory:
            return False

        inventory.add_snapshot(snapshot_name, set_active)
        self.save(inventory)
        return True

    def remove_snapshot_from_inventory(self, name: str, account_id: str, snapshot_name: str) -> bool:
        """Remove a snapshot from an inventory.

        Args:
            name: Inventory name
            account_id: AWS account ID
            snapshot_name: Snapshot name to remove

        Returns:
            True if successful, False if inventory not found
        """
        inventory = self.load(name, account_id)
        if not inventory:
            return False

        inventory.remove_snapshot(snapshot_name)
        self.save(inventory)
        return True

    def get_id(self, name: str, account_id: str) -> Optional[int]:
        """Get database ID for inventory.

        Args:
            name: Inventory name
            account_id: AWS account ID

        Returns:
            Database ID or None
        """
        row = self.db.fetchone(
            "SELECT id FROM inventories WHERE name = ? AND account_id = ?",
            (name, account_id),
        )
        return row["id"] if row else None
