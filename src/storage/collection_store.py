"""Collection storage operations for SQLite backend."""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..models.collection import Collection
from .database import Database, json_deserialize, json_serialize

logger = logging.getLogger(__name__)


class CollectionStore:
    """CRUD operations for collections in SQLite database."""

    def __init__(self, db: Database):
        """Initialize collection store.

        Args:
            db: Database connection manager
        """
        self.db = db

    def save(self, collection: Collection) -> int:
        """Save or update collection in database.

        Args:
            collection: Collection to save

        Returns:
            Database ID of saved collection
        """
        # Get active snapshot ID if set
        active_snapshot_id = None
        if collection.active_snapshot:
            # Look up snapshot ID by name (remove file extensions if present)
            snap_name = collection.active_snapshot.replace(".yaml.gz", "").replace(".yaml", "")
            row = self.db.fetchone("SELECT id FROM snapshots WHERE name = ?", (snap_name,))
            if row:
                active_snapshot_id = row["id"]

        with self.db.transaction() as cursor:
            # Check if collection exists
            existing = self.db.fetchone(
                "SELECT id FROM collections WHERE name = ? AND account_id = ?",
                (collection.name, collection.account_id),
            )

            if existing:
                # Update existing
                cursor.execute(
                    """
                    UPDATE collections SET
                        description = ?,
                        include_tags = ?,
                        exclude_tags = ?,
                        active_snapshot_id = ?,
                        last_updated = ?
                    WHERE id = ?
                    """,
                    (
                        collection.description,
                        json_serialize(collection.include_tags),
                        json_serialize(collection.exclude_tags),
                        active_snapshot_id,
                        collection.last_updated.isoformat(),
                        existing["id"],
                    ),
                )
                collection_id = existing["id"]

                # Update snapshot links
                self._update_snapshot_links(cursor, collection_id, collection.snapshots)

                logger.debug(f"Updated collection '{collection.name}' (id={collection_id})")
            else:
                # Insert new
                cursor.execute(
                    """
                    INSERT INTO collections (
                        name, account_id, description, include_tags, exclude_tags,
                        active_snapshot_id, created_at, last_updated
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        collection.name,
                        collection.account_id,
                        collection.description,
                        json_serialize(collection.include_tags),
                        json_serialize(collection.exclude_tags),
                        active_snapshot_id,
                        collection.created_at.isoformat(),
                        collection.last_updated.isoformat(),
                    ),
                )
                collection_id = cursor.lastrowid

                # Add snapshot links
                self._update_snapshot_links(cursor, collection_id, collection.snapshots)

                logger.debug(f"Saved collection '{collection.name}' (id={collection_id})")

            return collection_id

    def _update_snapshot_links(self, cursor, collection_id: int, snapshot_names: List[str]) -> None:
        """Update collection-snapshot links.

        Args:
            cursor: Database cursor
            collection_id: Collection ID
            snapshot_names: List of snapshot names to link
        """
        # Clear existing links
        cursor.execute("DELETE FROM collection_snapshots WHERE collection_id = ?", (collection_id,))

        # Add new links
        for snap_name in snapshot_names:
            # Remove file extensions if present
            snap_name = snap_name.replace(".yaml.gz", "").replace(".yaml", "")
            row = self.db.fetchone("SELECT id FROM snapshots WHERE name = ?", (snap_name,))
            if row:
                cursor.execute(
                    "INSERT OR IGNORE INTO collection_snapshots (collection_id, snapshot_id) VALUES (?, ?)",
                    (collection_id, row["id"]),
                )

    def load(self, name: str, account_id: str) -> Optional[Collection]:
        """Load collection by name and account.

        Args:
            name: Collection name
            account_id: AWS account ID

        Returns:
            Collection object or None if not found
        """
        row = self.db.fetchone(
            "SELECT * FROM collections WHERE name = ? AND account_id = ?",
            (name, account_id),
        )
        if not row:
            return None

        return self._row_to_collection(row)

    def _row_to_collection(self, row: Dict[str, Any]) -> Collection:
        """Convert database row to Collection object.

        Args:
            row: Database row dict

        Returns:
            Collection object
        """
        collection_id = row["id"]

        # Get linked snapshot names
        snapshot_rows = self.db.fetchall(
            """
            SELECT s.name FROM snapshots s
            JOIN collection_snapshots cs_link ON s.id = cs_link.snapshot_id
            WHERE cs_link.collection_id = ?
            ORDER BY s.created_at DESC
            """,
            (collection_id,),
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

        return Collection(
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

    def list_all(self) -> List[Collection]:
        """List all collections.

        Returns:
            List of all Collection objects
        """
        rows = self.db.fetchall("SELECT * FROM collections ORDER BY account_id, name")
        return [self._row_to_collection(row) for row in rows]

    def list_by_account(self, account_id: str) -> List[Collection]:
        """List collections for a specific account.

        Args:
            account_id: AWS account ID

        Returns:
            List of Collection objects for the account
        """
        rows = self.db.fetchall(
            "SELECT * FROM collections WHERE account_id = ? ORDER BY name",
            (account_id,),
        )
        return [self._row_to_collection(row) for row in rows]

    def delete(self, name: str, account_id: str) -> bool:
        """Delete collection.

        Args:
            name: Collection name
            account_id: AWS account ID

        Returns:
            True if deleted, False if not found
        """
        with self.db.transaction() as cursor:
            cursor.execute(
                "DELETE FROM collections WHERE name = ? AND account_id = ?",
                (name, account_id),
            )
            deleted = cursor.rowcount > 0

        if deleted:
            logger.debug(f"Deleted collection '{name}' for account {account_id}")
        return deleted

    def exists(self, name: str, account_id: str) -> bool:
        """Check if collection exists.

        Args:
            name: Collection name
            account_id: AWS account ID

        Returns:
            True if exists
        """
        row = self.db.fetchone(
            "SELECT 1 FROM collections WHERE name = ? AND account_id = ?",
            (name, account_id),
        )
        return row is not None

    def add_snapshot_to_collection(
        self, name: str, account_id: str, snapshot_name: str, set_active: bool = False
    ) -> bool:
        """Add a snapshot to a collection.

        Args:
            name: Collection name
            account_id: AWS account ID
            snapshot_name: Snapshot name to add
            set_active: Whether to set this as the active snapshot

        Returns:
            True if successful, False if collection not found
        """
        collection = self.load(name, account_id)
        if not collection:
            return False

        collection.add_snapshot(snapshot_name, set_active)
        self.save(collection)
        return True

    def remove_snapshot_from_collection(self, name: str, account_id: str, snapshot_name: str) -> bool:
        """Remove a snapshot from a collection.

        Args:
            name: Collection name
            account_id: AWS account ID
            snapshot_name: Snapshot name to remove

        Returns:
            True if successful, False if collection not found
        """
        collection = self.load(name, account_id)
        if not collection:
            return False

        collection.remove_snapshot(snapshot_name)
        self.save(collection)
        return True

    def get_id(self, name: str, account_id: str) -> Optional[int]:
        """Get database ID for collection.

        Args:
            name: Collection name
            account_id: AWS account ID

        Returns:
            Database ID or None
        """
        row = self.db.fetchone(
            "SELECT id FROM collections WHERE name = ? AND account_id = ?",
            (name, account_id),
        )
        return row["id"] if row else None
