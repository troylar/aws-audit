"""Snapshot storage operations for SQLite backend."""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..matching import ResourceNormalizer
from ..models.resource import Resource
from ..models.snapshot import Snapshot
from .database import Database, json_deserialize, json_serialize

logger = logging.getLogger(__name__)


def compute_canonical_name(name: str, tags: Optional[Dict[str, str]], arn: str) -> str:
    """Compute canonical name for a resource.

    Priority order:
    1. aws:cloudformation:logical-id tag (stable across recreations)
    2. Resource name
    3. ARN as fallback

    Args:
        name: Resource physical name
        tags: Resource tags
        arn: Resource ARN

    Returns:
        Canonical name for matching
    """
    if tags and "aws:cloudformation:logical-id" in tags:
        return tags["aws:cloudformation:logical-id"]
    return name or arn


class SnapshotStore:
    """CRUD operations for snapshots in SQLite database."""

    def __init__(self, db: Database):
        """Initialize snapshot store.

        Args:
            db: Database connection manager
        """
        self.db = db

    def save(self, snapshot: Snapshot) -> int:
        """Save snapshot and all its resources to database.

        Args:
            snapshot: Snapshot to save

        Returns:
            Database ID of saved snapshot
        """
        # Create normalizer for computing normalized names
        normalizer = ResourceNormalizer()

        with self.db.transaction() as cursor:
            # Insert snapshot
            cursor.execute(
                """
                INSERT INTO snapshots (
                    name, created_at, account_id, regions, resource_count,
                    total_resources_before_filter, service_counts, metadata,
                    filters_applied, schema_version, inventory_name, is_active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot.name,
                    snapshot.created_at.isoformat(),
                    snapshot.account_id,
                    json_serialize(snapshot.regions),
                    snapshot.resource_count,
                    snapshot.total_resources_before_filter,
                    json_serialize(snapshot.service_counts),
                    json_serialize(snapshot.metadata),
                    json_serialize(snapshot.filters_applied),
                    snapshot.schema_version,
                    snapshot.inventory_name,
                    snapshot.is_active,
                ),
            )
            snapshot_id = cursor.lastrowid

            # Insert resources
            for resource in snapshot.resources:
                # Compute canonical name (for backward compatibility)
                canonical = compute_canonical_name(resource.name, resource.tags, resource.arn)

                # Compute normalized name with pattern extraction
                norm_result = normalizer.normalize_single(
                    resource.name,
                    resource.resource_type,
                    resource.tags,
                )

                cursor.execute(
                    """
                    INSERT INTO resources (
                        snapshot_id, arn, resource_type, name, region,
                        config_hash, raw_config, created_at, source, canonical_name,
                        normalized_name, extracted_patterns, normalization_method
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        snapshot_id,
                        resource.arn,
                        resource.resource_type,
                        resource.name,
                        resource.region,
                        resource.config_hash,
                        json_serialize(resource.raw_config),
                        resource.created_at.isoformat() if resource.created_at else None,
                        resource.source,
                        canonical,
                        norm_result.normalized_name,
                        json_serialize(norm_result.extracted_patterns),
                        norm_result.method,
                    ),
                )
                resource_id = cursor.lastrowid

                # Insert tags
                if resource.tags:
                    tag_data = [(resource_id, k, v) for k, v in resource.tags.items()]
                    cursor.executemany(
                        "INSERT INTO resource_tags (resource_id, key, value) VALUES (?, ?, ?)",
                        tag_data,
                    )

            logger.debug(
                f"Saved snapshot '{snapshot.name}' with {len(snapshot.resources)} resources (id={snapshot_id})"
            )
            return snapshot_id

    def load(self, name: str) -> Optional[Snapshot]:
        """Load snapshot by name with all resources.

        Args:
            name: Snapshot name

        Returns:
            Snapshot object or None if not found
        """
        # Get snapshot
        snapshot_row = self.db.fetchone("SELECT * FROM snapshots WHERE name = ?", (name,))
        if not snapshot_row:
            return None

        snapshot_id = snapshot_row["id"]

        # Get resources
        resource_rows = self.db.fetchall(
            "SELECT * FROM resources WHERE snapshot_id = ?",
            (snapshot_id,),
        )

        # Get tags for all resources in one query
        resource_ids = [r["id"] for r in resource_rows]
        tags_by_resource: Dict[int, Dict[str, str]] = {}

        if resource_ids:
            placeholders = ",".join("?" * len(resource_ids))
            tag_rows = self.db.fetchall(
                f"SELECT resource_id, key, value FROM resource_tags WHERE resource_id IN ({placeholders})",
                tuple(resource_ids),
            )
            for tag_row in tag_rows:
                rid = tag_row["resource_id"]
                if rid not in tags_by_resource:
                    tags_by_resource[rid] = {}
                tags_by_resource[rid][tag_row["key"]] = tag_row["value"]

        # Build Resource objects
        resources = []
        for row in resource_rows:
            created_at = None
            if row["created_at"]:
                try:
                    created_at = datetime.fromisoformat(row["created_at"])
                except ValueError:
                    pass

            resource = Resource(
                arn=row["arn"],
                resource_type=row["resource_type"],
                name=row["name"],
                region=row["region"],
                config_hash=row["config_hash"],
                raw_config=json_deserialize(row["raw_config"]),
                tags=tags_by_resource.get(row["id"], {}),
                created_at=created_at,
                source=row["source"] or "direct_api",
            )
            resources.append(resource)

        # Build Snapshot
        created_at = datetime.fromisoformat(snapshot_row["created_at"])
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)

        snapshot = Snapshot(
            name=snapshot_row["name"],
            created_at=created_at,
            account_id=snapshot_row["account_id"],
            regions=json_deserialize(snapshot_row["regions"]) or [],
            resources=resources,
            is_active=bool(snapshot_row["is_active"]),
            resource_count=snapshot_row["resource_count"],
            total_resources_before_filter=snapshot_row.get("total_resources_before_filter"),
            service_counts=json_deserialize(snapshot_row["service_counts"]) or {},
            metadata=json_deserialize(snapshot_row["metadata"]) or {},
            filters_applied=json_deserialize(snapshot_row["filters_applied"]),
            inventory_name=snapshot_row["inventory_name"] or "default",
            schema_version=snapshot_row["schema_version"] or "1.1",
        )

        logger.debug(f"Loaded snapshot '{name}' with {len(resources)} resources")
        return snapshot

    def list_all(self) -> List[Dict[str, Any]]:
        """List all snapshots with metadata (no resources).

        Returns:
            List of snapshot metadata dictionaries
        """
        rows = self.db.fetchall(
            """
            SELECT name, created_at, account_id, regions, resource_count,
                   service_counts, is_active, inventory_name
            FROM snapshots
            ORDER BY created_at DESC
            """
        )

        results = []
        for row in rows:
            created_at = datetime.fromisoformat(row["created_at"])
            results.append(
                {
                    "name": row["name"],
                    "created_at": created_at,
                    "account_id": row["account_id"],
                    "regions": json_deserialize(row["regions"]) or [],
                    "resource_count": row["resource_count"],
                    "service_counts": json_deserialize(row["service_counts"]) or {},
                    "is_active": bool(row["is_active"]),
                    "inventory_name": row["inventory_name"],
                }
            )

        return results

    def delete(self, name: str) -> bool:
        """Delete snapshot and cascade to resources.

        Args:
            name: Snapshot name to delete

        Returns:
            True if deleted, False if not found
        """
        with self.db.transaction() as cursor:
            cursor.execute("DELETE FROM snapshots WHERE name = ?", (name,))
            deleted = cursor.rowcount > 0

        if deleted:
            logger.debug(f"Deleted snapshot '{name}'")
        return deleted

    def exists(self, name: str) -> bool:
        """Check if snapshot exists.

        Args:
            name: Snapshot name

        Returns:
            True if exists
        """
        row = self.db.fetchone("SELECT 1 FROM snapshots WHERE name = ?", (name,))
        return row is not None

    def rename(self, old_name: str, new_name: str) -> bool:
        """Rename a snapshot.

        Args:
            old_name: Current snapshot name
            new_name: New snapshot name

        Returns:
            True if renamed, False if old_name not found

        Raises:
            ValueError: If new_name already exists
        """
        if not self.exists(old_name):
            return False

        if self.exists(new_name):
            raise ValueError(f"Snapshot '{new_name}' already exists")

        with self.db.transaction() as cursor:
            cursor.execute(
                "UPDATE snapshots SET name = ? WHERE name = ?",
                (new_name, old_name),
            )

        logger.debug(f"Renamed snapshot '{old_name}' to '{new_name}'")
        return True

    def get_active(self) -> Optional[str]:
        """Get name of active snapshot.

        Returns:
            Active snapshot name or None
        """
        row = self.db.fetchone("SELECT name FROM snapshots WHERE is_active = 1")
        return row["name"] if row else None

    def set_active(self, name: str) -> None:
        """Set snapshot as active baseline.

        Args:
            name: Snapshot name to set as active
        """
        with self.db.transaction() as cursor:
            # Clear previous active
            cursor.execute("UPDATE snapshots SET is_active = 0 WHERE is_active = 1")
            # Set new active
            cursor.execute("UPDATE snapshots SET is_active = 1 WHERE name = ?", (name,))

        logger.debug(f"Set active snapshot: '{name}'")

    def get_id(self, name: str) -> Optional[int]:
        """Get database ID for snapshot.

        Args:
            name: Snapshot name

        Returns:
            Database ID or None
        """
        row = self.db.fetchone("SELECT id FROM snapshots WHERE name = ?", (name,))
        return row["id"] if row else None

    def get_resource_count(self) -> int:
        """Get total resource count across all snapshots.

        Returns:
            Total resource count
        """
        row = self.db.fetchone("SELECT COUNT(*) as count FROM resources")
        return row["count"] if row else 0

    def get_snapshot_count(self) -> int:
        """Get total snapshot count.

        Returns:
            Snapshot count
        """
        row = self.db.fetchone("SELECT COUNT(*) as count FROM snapshots")
        return row["count"] if row else 0

    def update_resource_config(
        self,
        snapshot_name: str,
        resource_arn: str,
        raw_config: Dict[str, Any],
        config_hash: Optional[str] = None,
    ) -> bool:
        """Update raw_config for a specific resource in a snapshot.

        Args:
            snapshot_name: Name of the snapshot
            resource_arn: ARN of the resource to update
            raw_config: New raw_config dictionary
            config_hash: Optional new config hash (computed if not provided)

        Returns:
            True if updated, False if resource not found
        """
        snapshot_id = self.get_id(snapshot_name)
        if not snapshot_id:
            return False

        # Compute config hash if not provided
        if config_hash is None:
            from ..utils.hash import compute_config_hash

            config_hash = compute_config_hash(raw_config)

        with self.db.transaction() as cursor:
            cursor.execute(
                """
                UPDATE resources
                SET raw_config = ?, config_hash = ?
                WHERE snapshot_id = ? AND arn = ?
                """,
                (json_serialize(raw_config), config_hash, snapshot_id, resource_arn),
            )
            updated = cursor.rowcount > 0

        if updated:
            logger.debug(f"Updated raw_config for {resource_arn} in snapshot '{snapshot_name}'")

        return updated
