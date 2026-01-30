"""Resource Group storage operations for SQLite backend."""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..models.group import GroupMember, ResourceGroup, extract_resource_name
from .database import Database

logger = logging.getLogger(__name__)


class GroupStore:
    """CRUD and query operations for resource groups in SQLite database."""

    def __init__(self, db: Database):
        """Initialize group store.

        Args:
            db: Database connection manager
        """
        self.db = db

    def save(self, group: ResourceGroup) -> int:
        """Save or update resource group in database.

        Args:
            group: ResourceGroup to save

        Returns:
            Database ID of saved group
        """
        now = datetime.now(timezone.utc)

        with self.db.transaction() as cursor:
            # Check if group exists
            existing = self.db.fetchone(
                "SELECT id FROM resource_groups WHERE name = ?",
                (group.name,),
            )

            if existing:
                # Update existing
                cursor.execute(
                    """
                    UPDATE resource_groups SET
                        description = ?,
                        source_snapshot = ?,
                        resource_count = ?,
                        is_favorite = ?,
                        last_updated = ?
                    WHERE id = ?
                    """,
                    (
                        group.description,
                        group.source_snapshot,
                        len(group.members),
                        group.is_favorite,
                        now.isoformat(),
                        existing["id"],
                    ),
                )
                group_id = existing["id"]

                # Update members - clear and re-add
                cursor.execute("DELETE FROM resource_group_members WHERE group_id = ?", (group_id,))
                self._insert_members(cursor, group_id, group.members)

                logger.debug(f"Updated group '{group.name}' (id={group_id})")
            else:
                # Insert new
                cursor.execute(
                    """
                    INSERT INTO resource_groups (
                        name, description, source_snapshot, resource_count,
                        is_favorite, created_at, last_updated
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        group.name,
                        group.description,
                        group.source_snapshot,
                        len(group.members),
                        group.is_favorite,
                        now.isoformat(),
                        now.isoformat(),
                    ),
                )
                group_id = cursor.lastrowid

                # Insert members
                self._insert_members(cursor, group_id, group.members)

                logger.debug(f"Saved group '{group.name}' (id={group_id})")

            return group_id

    def _insert_members(self, cursor, group_id: int, members: List[GroupMember]) -> None:
        """Insert group members.

        Args:
            cursor: Database cursor
            group_id: Group ID
            members: List of members to insert
        """
        for member in members:
            cursor.execute(
                """
                INSERT OR IGNORE INTO resource_group_members
                (group_id, resource_name, resource_type, original_arn, match_strategy)
                VALUES (?, ?, ?, ?, ?)
                """,
                (group_id, member.resource_name, member.resource_type, member.original_arn, member.match_strategy),
            )

    def load(self, name: str) -> Optional[ResourceGroup]:
        """Load resource group by name.

        Args:
            name: Group name

        Returns:
            ResourceGroup object or None if not found
        """
        row = self.db.fetchone(
            "SELECT * FROM resource_groups WHERE name = ?",
            (name,),
        )
        if not row:
            return None

        return self._row_to_group(row, include_members=True)

    def _row_to_group(self, row: Dict[str, Any], include_members: bool = False) -> ResourceGroup:
        """Convert database row to ResourceGroup object.

        Args:
            row: Database row dict
            include_members: Whether to load members

        Returns:
            ResourceGroup object
        """
        group_id = row["id"]

        # Parse timestamps
        created_at = datetime.fromisoformat(row["created_at"])
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)

        last_updated = datetime.fromisoformat(row["last_updated"])
        if last_updated.tzinfo is None:
            last_updated = last_updated.replace(tzinfo=timezone.utc)

        # Load members if requested
        members = []
        if include_members:
            member_rows = self.db.fetchall(
                "SELECT * FROM resource_group_members WHERE group_id = ? ORDER BY resource_type, resource_name",
                (group_id,),
            )
            members = [
                GroupMember(
                    resource_name=r["resource_name"],
                    resource_type=r["resource_type"],
                    original_arn=r["original_arn"],
                    match_strategy=r.get("match_strategy", "physical_name"),
                )
                for r in member_rows
            ]

        return ResourceGroup(
            id=group_id,
            name=row["name"],
            description=row["description"] or "",
            source_snapshot=row["source_snapshot"],
            members=members,
            resource_count=row["resource_count"],
            is_favorite=bool(row["is_favorite"]),
            created_at=created_at,
            last_updated=last_updated,
        )

    def list_all(self) -> List[Dict[str, Any]]:
        """List all groups (metadata only, no members).

        Returns:
            List of group metadata dictionaries
        """
        rows = self.db.fetchall("SELECT * FROM resource_groups ORDER BY is_favorite DESC, name")
        results = []
        for row in rows:
            created_at = row["created_at"]
            last_updated = row["last_updated"]
            # Convert datetime to ISO string for JSON serialization
            if hasattr(created_at, "isoformat"):
                created_at = created_at.isoformat()
            if hasattr(last_updated, "isoformat"):
                last_updated = last_updated.isoformat()
            results.append(
                {
                    "id": row["id"],
                    "name": row["name"],
                    "description": row["description"] or "",
                    "source_snapshot": row["source_snapshot"],
                    "resource_count": row["resource_count"],
                    "is_favorite": bool(row["is_favorite"]),
                    "created_at": created_at,
                    "last_updated": last_updated,
                }
            )
        return results

    def delete(self, name: str) -> bool:
        """Delete group by name.

        Args:
            name: Group name

        Returns:
            True if deleted, False if not found
        """
        with self.db.transaction() as cursor:
            cursor.execute("DELETE FROM resource_groups WHERE name = ?", (name,))
            deleted = cursor.rowcount > 0

        if deleted:
            logger.debug(f"Deleted group '{name}'")
        return deleted

    def exists(self, name: str) -> bool:
        """Check if group exists.

        Args:
            name: Group name

        Returns:
            True if exists
        """
        row = self.db.fetchone(
            "SELECT 1 FROM resource_groups WHERE name = ?",
            (name,),
        )
        return row is not None

    def get_id(self, name: str) -> Optional[int]:
        """Get database ID for group.

        Args:
            name: Group name

        Returns:
            Database ID or None
        """
        row = self.db.fetchone(
            "SELECT id FROM resource_groups WHERE name = ?",
            (name,),
        )
        return row["id"] if row else None

    def toggle_favorite(self, name: str) -> Optional[bool]:
        """Toggle favorite status of a group.

        Args:
            name: Group name

        Returns:
            New favorite status, or None if not found
        """
        row = self.db.fetchone(
            "SELECT id, is_favorite FROM resource_groups WHERE name = ?",
            (name,),
        )
        if not row:
            return None

        new_favorite = not row["is_favorite"]
        with self.db.transaction() as cursor:
            cursor.execute(
                "UPDATE resource_groups SET is_favorite = ?, last_updated = ? WHERE id = ?",
                (new_favorite, datetime.now(timezone.utc).isoformat(), row["id"]),
            )
        return new_favorite

    # Member management methods

    def add_members(self, group_name: str, members: List[GroupMember]) -> int:
        """Add members to a group.

        Args:
            group_name: Group name
            members: List of members to add

        Returns:
            Number of members added
        """
        group_id = self.get_id(group_name)
        if not group_id:
            raise ValueError(f"Group '{group_name}' not found")

        added = 0
        with self.db.transaction() as cursor:
            for member in members:
                try:
                    cursor.execute(
                        """
                        INSERT INTO resource_group_members
                        (group_id, resource_name, resource_type, original_arn, match_strategy)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            group_id,
                            member.resource_name,
                            member.resource_type,
                            member.original_arn,
                            member.match_strategy,
                        ),
                    )
                    added += 1
                except Exception:
                    # Unique constraint violation - member already exists
                    pass

            # Update resource count
            cursor.execute(
                """
                UPDATE resource_groups
                SET resource_count = (SELECT COUNT(*) FROM resource_group_members WHERE group_id = ?),
                    last_updated = ?
                WHERE id = ?
                """,
                (group_id, datetime.now(timezone.utc).isoformat(), group_id),
            )

        return added

    def add_members_from_arns(self, group_name: str, arns: List[Dict[str, str]]) -> int:
        """Add members to a group from a list of ARNs with types.

        Args:
            group_name: Group name
            arns: List of dicts with 'arn', 'resource_type' keys, and optional 'logical_id'

        Returns:
            Number of members added
        """
        members = []
        for item in arns:
            arn = item["arn"]
            resource_type = item["resource_type"]
            logical_id = item.get("logical_id")

            if logical_id:
                # Use logical ID for stable matching across resource recreations
                resource_name = logical_id
                match_strategy = "logical_id"
            else:
                # Fallback to physical name from ARN
                resource_name = extract_resource_name(arn, resource_type)
                match_strategy = "physical_name"

            members.append(GroupMember(resource_name, resource_type, arn, match_strategy))

        return self.add_members(group_name, members)

    def remove_member(self, group_name: str, resource_name: str, resource_type: str) -> bool:
        """Remove a member from a group.

        Args:
            group_name: Group name
            resource_name: Resource name
            resource_type: Resource type

        Returns:
            True if removed, False if not found
        """
        group_id = self.get_id(group_name)
        if not group_id:
            return False

        with self.db.transaction() as cursor:
            cursor.execute(
                """
                DELETE FROM resource_group_members
                WHERE group_id = ? AND resource_name = ? AND resource_type = ?
                """,
                (group_id, resource_name, resource_type),
            )
            removed = cursor.rowcount > 0

            if removed:
                # Update resource count
                cursor.execute(
                    """
                    UPDATE resource_groups
                    SET resource_count = (SELECT COUNT(*) FROM resource_group_members WHERE group_id = ?),
                        last_updated = ?
                    WHERE id = ?
                    """,
                    (group_id, datetime.now(timezone.utc).isoformat(), group_id),
                )

        return removed

    def get_members(
        self,
        group_name: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[GroupMember]:
        """Get members of a group with pagination.

        Args:
            group_name: Group name
            limit: Maximum results
            offset: Offset for pagination

        Returns:
            List of GroupMember objects
        """
        group_id = self.get_id(group_name)
        if not group_id:
            return []

        rows = self.db.fetchall(
            """
            SELECT * FROM resource_group_members
            WHERE group_id = ?
            ORDER BY resource_type, resource_name
            LIMIT ? OFFSET ?
            """,
            (group_id, limit, offset),
        )

        return [
            GroupMember(
                resource_name=r["resource_name"],
                resource_type=r["resource_type"],
                original_arn=r["original_arn"],
                match_strategy=r.get("match_strategy", "physical_name"),
            )
            for r in rows
        ]

    # Group creation and comparison methods

    def create_from_snapshot(
        self,
        group_name: str,
        snapshot_name: str,
        description: str = "",
        type_filter: Optional[str] = None,
        region_filter: Optional[str] = None,
    ) -> int:
        """Create a group from all resources in a snapshot.

        Args:
            group_name: Name for the new group
            snapshot_name: Source snapshot name
            description: Group description
            type_filter: Optional resource type filter
            region_filter: Optional region filter

        Returns:
            Number of resources added to the group
        """
        # Get snapshot ID
        snap_row = self.db.fetchone(
            "SELECT id FROM snapshots WHERE name = ?",
            (snapshot_name,),
        )
        if not snap_row:
            raise ValueError(f"Snapshot '{snapshot_name}' not found")

        snapshot_id = snap_row["id"]

        # Build query for resources
        conditions = ["r.snapshot_id = ?"]
        params: List[Any] = [snapshot_id]

        if type_filter:
            if ":" in type_filter:
                conditions.append("r.resource_type = ?")
            else:
                conditions.append("r.resource_type LIKE ?")
                type_filter = f"%{type_filter}%"
            params.append(type_filter)

        if region_filter:
            conditions.append("r.region = ?")
            params.append(region_filter)

        query = f"""
            SELECT r.arn, r.resource_type, r.name, r.canonical_name,
                   r.normalized_name, r.normalization_method
            FROM resources r
            WHERE {" AND ".join(conditions)}
            ORDER BY r.resource_type, r.name
        """

        resource_rows = self.db.fetchall(query, tuple(params))

        # Create group with members
        # Choose the best match strategy based on how the resource was normalized
        members = []
        for row in resource_rows:
            physical_name = row["name"] or extract_resource_name(row["arn"], row["resource_type"])
            normalized_name = row.get("normalized_name")
            normalization_method = row.get("normalization_method") or "none"

            # Choose match strategy based on normalization method
            if normalization_method == "tag:logical-id":
                # CloudFormation logical ID - most reliable
                resource_name = row.get("canonical_name") or normalized_name
                match_strategy = "logical_id"
            elif normalization_method in ("tag:Name", "pattern"):
                # Name tag or pattern extraction - use normalized name
                resource_name = normalized_name or physical_name
                match_strategy = "normalized"
            else:
                # No normalization - use physical name
                resource_name = physical_name
                match_strategy = "physical_name"

            members.append(
                GroupMember(
                    resource_name=resource_name,
                    resource_type=row["resource_type"],
                    original_arn=row["arn"],
                    match_strategy=match_strategy,
                )
            )

        group = ResourceGroup(
            name=group_name,
            description=description,
            source_snapshot=snapshot_name,
            members=members,
            resource_count=len(members),
        )

        self.save(group)
        logger.info(f"Created group '{group_name}' with {len(members)} resources from snapshot '{snapshot_name}'")

        return len(members)

    def compare_snapshot(
        self,
        group_name: str,
        snapshot_name: str,
    ) -> Dict[str, Any]:
        """Compare a snapshot against a group.

        Resources are matched by name + type.

        Args:
            group_name: Group name
            snapshot_name: Snapshot to compare

        Returns:
            Comparison results with matched, missing, and extra resources
        """
        # Get group members
        group = self.load(group_name)
        if not group:
            raise ValueError(f"Group '{group_name}' not found")

        # Get snapshot resources
        snap_row = self.db.fetchone(
            "SELECT id FROM snapshots WHERE name = ?",
            (snapshot_name,),
        )
        if not snap_row:
            raise ValueError(f"Snapshot '{snapshot_name}' not found")

        resource_rows = self.db.fetchall(
            """
            SELECT r.arn, r.resource_type, r.name, r.region
            FROM resources r
            WHERE r.snapshot_id = ?
            """,
            (snap_row["id"],),
        )

        # Build sets for comparison
        group_set = {(m.resource_name, m.resource_type) for m in group.members}
        snapshot_resources = {}
        for row in resource_rows:
            resource_name = row["name"] or extract_resource_name(row["arn"], row["resource_type"])
            key = (resource_name, row["resource_type"])
            snapshot_resources[key] = {
                "arn": row["arn"],
                "resource_type": row["resource_type"],
                "name": resource_name,
                "region": row["region"],
            }

        snapshot_set = set(snapshot_resources.keys())

        # Calculate differences
        matched_keys = group_set & snapshot_set
        missing_keys = group_set - snapshot_set  # In group but not in snapshot
        extra_keys = snapshot_set - group_set  # In snapshot but not in group

        # Build result lists
        matched = [snapshot_resources[k] for k in matched_keys]
        missing = [{"name": k[0], "resource_type": k[1]} for k in missing_keys]
        extra = [snapshot_resources[k] for k in extra_keys]

        return {
            "group_name": group_name,
            "snapshot_name": snapshot_name,
            "total_in_group": len(group.members),
            "total_in_snapshot": len(snapshot_resources),
            "matched": len(matched),
            "missing_from_snapshot": len(missing),
            "not_in_group": len(extra),
            "resources": {
                "matched": sorted(matched, key=lambda x: (x["resource_type"], x["name"])),
                "missing": sorted(missing, key=lambda x: (x["resource_type"], x["name"])),
                "extra": sorted(extra, key=lambda x: (x["resource_type"], x["name"])),
            },
        }

    def is_resource_in_group(
        self,
        group_name: str,
        resource_name: str,
        resource_type: str,
    ) -> bool:
        """Check if a resource is in a group.

        Args:
            group_name: Group name
            resource_name: Resource name
            resource_type: Resource type

        Returns:
            True if resource is in the group
        """
        group_id = self.get_id(group_name)
        if not group_id:
            return False

        row = self.db.fetchone(
            """
            SELECT 1 FROM resource_group_members
            WHERE group_id = ? AND resource_name = ? AND resource_type = ?
            """,
            (group_id, resource_name, resource_type),
        )
        return row is not None

    def get_resources_not_in_group(
        self,
        group_name: str,
        snapshot_name: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Get resources from a snapshot that are NOT in a group.

        Args:
            group_name: Group name
            snapshot_name: Snapshot name
            limit: Maximum results
            offset: Offset for pagination

        Returns:
            List of resources not in the group
        """
        group_id = self.get_id(group_name)
        if not group_id:
            raise ValueError(f"Group '{group_name}' not found")

        snap_row = self.db.fetchone(
            "SELECT id FROM snapshots WHERE name = ?",
            (snapshot_name,),
        )
        if not snap_row:
            raise ValueError(f"Snapshot '{snapshot_name}' not found")

        # Use NOT EXISTS to find resources not in group
        # Match strategy determines how to compare:
        # - 'logical_id': match on canonical_name (CloudFormation logical ID)
        # - 'normalized': match on normalized_name (pattern-stripped semantic name)
        # - 'physical_name': match on physical name or ARN
        rows = self.db.fetchall(
            """
            SELECT r.arn, r.resource_type, r.name, r.region, r.created_at,
                   r.canonical_name, r.normalized_name, r.normalization_method
            FROM resources r
            WHERE r.snapshot_id = ?
                AND NOT EXISTS (
                    SELECT 1 FROM resource_group_members gm
                    WHERE gm.group_id = ?
                    AND r.resource_type = gm.resource_type
                    AND (
                        (gm.match_strategy = 'logical_id' AND r.canonical_name = gm.resource_name)
                        OR (gm.match_strategy = 'normalized' AND r.normalized_name = gm.resource_name)
                        OR (COALESCE(gm.match_strategy, 'physical_name') = 'physical_name'
                            AND COALESCE(r.name, r.arn) = gm.resource_name)
                    )
                )
            ORDER BY r.resource_type, r.name
            LIMIT ? OFFSET ?
            """,
            (snap_row["id"], group_id, limit, offset),
        )

        return [dict(r) for r in rows]

    def get_resources_in_group(
        self,
        group_name: str,
        snapshot_name: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Get resources from a snapshot that ARE in a group.

        Args:
            group_name: Group name
            snapshot_name: Snapshot name
            limit: Maximum results
            offset: Offset for pagination

        Returns:
            List of resources in the group
        """
        group_id = self.get_id(group_name)
        if not group_id:
            raise ValueError(f"Group '{group_name}' not found")

        snap_row = self.db.fetchone(
            "SELECT id FROM snapshots WHERE name = ?",
            (snapshot_name,),
        )
        if not snap_row:
            raise ValueError(f"Snapshot '{snapshot_name}' not found")

        # Use INNER JOIN to find resources in group
        # Match strategy determines how to compare:
        # - 'logical_id': match on canonical_name (CloudFormation logical ID)
        # - 'normalized': match on normalized_name (pattern-stripped semantic name)
        # - 'physical_name': match on physical name or ARN
        rows = self.db.fetchall(
            """
            SELECT r.arn, r.resource_type, r.name, r.region, r.created_at,
                   r.canonical_name, r.normalized_name, r.normalization_method
            FROM resources r
            INNER JOIN resource_group_members gm
                ON (
                    (gm.match_strategy = 'logical_id' AND r.canonical_name = gm.resource_name)
                    OR (gm.match_strategy = 'normalized' AND r.normalized_name = gm.resource_name)
                    OR (COALESCE(gm.match_strategy, 'physical_name') = 'physical_name'
                        AND COALESCE(r.name, r.arn) = gm.resource_name)
                )
                AND r.resource_type = gm.resource_type
                AND gm.group_id = ?
            WHERE r.snapshot_id = ?
            ORDER BY r.resource_type, r.name
            LIMIT ? OFFSET ?
            """,
            (group_id, snap_row["id"], limit, offset),
        )

        return [dict(r) for r in rows]
