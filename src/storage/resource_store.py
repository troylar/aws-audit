"""Resource query operations for SQLite backend."""

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from .database import Database

logger = logging.getLogger(__name__)


class ResourceStore:
    """Query operations for resources across snapshots."""

    def __init__(self, db: Database):
        """Initialize resource store.

        Args:
            db: Database connection manager
        """
        self.db = db

    def query_raw(self, sql: str, params: Tuple = ()) -> List[Dict[str, Any]]:
        """Execute raw SQL query on the database.

        Args:
            sql: SQL query (should be SELECT only)
            params: Query parameters

        Returns:
            List of result dictionaries

        Raises:
            ValueError: If query is not a SELECT statement
        """
        # Basic SQL injection prevention - only allow SELECT
        sql_upper = sql.strip().upper()
        if not sql_upper.startswith("SELECT"):
            raise ValueError("Only SELECT queries are allowed")

        # Block dangerous keywords
        dangerous = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "CREATE", "TRUNCATE"]
        for keyword in dangerous:
            if re.search(rf"\b{keyword}\b", sql_upper):
                raise ValueError(f"Query contains forbidden keyword: {keyword}")

        return self.db.fetchall(sql, params)

    def search(
        self,
        arn_pattern: Optional[str] = None,
        resource_type: Optional[str] = None,
        region: Optional[str] = None,
        tag_key: Optional[str] = None,
        tag_value: Optional[str] = None,
        snapshot_name: Optional[str] = None,
        created_before: Optional[datetime] = None,
        created_after: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Search resources with filters.

        Args:
            arn_pattern: ARN pattern to match (supports % wildcard)
            resource_type: Filter by resource type (exact or partial)
            region: Filter by region
            tag_key: Filter by tag key
            tag_value: Filter by tag value (requires tag_key)
            snapshot_name: Limit to specific snapshot
            created_before: Resources created before this date
            created_after: Resources created after this date
            limit: Maximum results to return
            offset: Offset for pagination

        Returns:
            List of matching resources with snapshot info
        """
        conditions = []
        params: List[Any] = []

        # Build query with joins
        base_query = """
            SELECT DISTINCT
                r.arn,
                r.resource_type,
                r.name,
                r.region,
                r.config_hash,
                r.created_at,
                r.source,
                r.canonical_name,
                r.normalized_name,
                r.normalization_method,
                s.name as snapshot_name,
                s.created_at as snapshot_created_at,
                s.account_id
            FROM resources r
            JOIN snapshots s ON r.snapshot_id = s.id
        """

        # Tag join if filtering by tags
        if tag_key:
            base_query += " JOIN resource_tags t ON r.id = t.resource_id"
            conditions.append("t.key = ?")
            params.append(tag_key)
            if tag_value:
                conditions.append("t.value = ?")
                params.append(tag_value)

        # ARN filter
        if arn_pattern:
            if "%" in arn_pattern:
                conditions.append("r.arn LIKE ?")
            else:
                conditions.append("r.arn LIKE ?")
                arn_pattern = f"%{arn_pattern}%"
            params.append(arn_pattern)

        # Resource type filter
        if resource_type:
            if ":" in resource_type:
                conditions.append("r.resource_type = ?")
            else:
                conditions.append("r.resource_type LIKE ?")
                resource_type = f"%{resource_type}%"
            params.append(resource_type)

        # Region filter
        if region:
            conditions.append("r.region = ?")
            params.append(region)

        # Snapshot filter
        if snapshot_name:
            conditions.append("s.name = ?")
            params.append(snapshot_name)

        # Date filters
        if created_before:
            conditions.append("r.created_at < ?")
            params.append(created_before.isoformat())

        if created_after:
            conditions.append("r.created_at >= ?")
            params.append(created_after.isoformat())

        # Build final query
        if conditions:
            base_query += " WHERE " + " AND ".join(conditions)

        base_query += " ORDER BY s.created_at DESC, r.arn"
        base_query += f" LIMIT {limit} OFFSET {offset}"

        return self.db.fetchall(base_query, tuple(params))

    def get_history(self, arn: str) -> List[Dict[str, Any]]:
        """Get all snapshots containing a specific resource.

        Args:
            arn: Resource ARN

        Returns:
            List of snapshots with resource details, ordered by date
        """
        return self.db.fetchall(
            """
            SELECT
                s.name as snapshot_name,
                s.created_at as snapshot_created_at,
                s.account_id,
                r.config_hash,
                r.created_at as resource_created_at,
                r.source
            FROM resources r
            JOIN snapshots s ON r.snapshot_id = s.id
            WHERE r.arn = ?
            ORDER BY s.created_at DESC
            """,
            (arn,),
        )

    def get_stats(
        self,
        snapshot_name: Optional[str] = None,
        group_by: str = "type",
    ) -> List[Dict[str, Any]]:
        """Get resource statistics.

        Args:
            snapshot_name: Limit to specific snapshot (None for all)
            group_by: Grouping field - 'type', 'region', 'service', 'snapshot'

        Returns:
            List of statistics grouped by specified field
        """
        group_field = {
            "type": "r.resource_type",
            "region": "r.region",
            "service": "SUBSTR(r.resource_type, 1, INSTR(r.resource_type, ':') - 1)",
            "snapshot": "s.name",
        }.get(group_by, "r.resource_type")

        base_query = f"""
            SELECT
                {group_field} as group_key,
                COUNT(*) as count
            FROM resources r
            JOIN snapshots s ON r.snapshot_id = s.id
        """

        params: List[str] = []
        if snapshot_name:
            base_query += " WHERE s.name = ?"
            params.append(snapshot_name)

        base_query += f" GROUP BY {group_field} ORDER BY count DESC"

        return self.db.fetchall(base_query, tuple(params))

    def compare_snapshots(
        self,
        snapshot1_name: str,
        snapshot2_name: str,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Compare resources between two snapshots.

        Args:
            snapshot1_name: First (older) snapshot name
            snapshot2_name: Second (newer) snapshot name

        Returns:
            Dict with 'added', 'removed', 'modified' resource lists
        """
        # Get resources from both snapshots indexed by ARN
        snap1_resources = self.db.fetchall(
            """
            SELECT r.arn, r.resource_type, r.name, r.region, r.config_hash
            FROM resources r
            JOIN snapshots s ON r.snapshot_id = s.id
            WHERE s.name = ?
            """,
            (snapshot1_name,),
        )

        snap2_resources = self.db.fetchall(
            """
            SELECT r.arn, r.resource_type, r.name, r.region, r.config_hash
            FROM resources r
            JOIN snapshots s ON r.snapshot_id = s.id
            WHERE s.name = ?
            """,
            (snapshot2_name,),
        )

        snap1_by_arn = {r["arn"]: r for r in snap1_resources}
        snap2_by_arn = {r["arn"]: r for r in snap2_resources}

        snap1_arns = set(snap1_by_arn.keys())
        snap2_arns = set(snap2_by_arn.keys())

        added = [dict(snap2_by_arn[arn]) for arn in (snap2_arns - snap1_arns)]
        removed = [dict(snap1_by_arn[arn]) for arn in (snap1_arns - snap2_arns)]

        # Find modified (same ARN, different hash)
        modified = []
        for arn in snap1_arns & snap2_arns:
            if snap1_by_arn[arn]["config_hash"] != snap2_by_arn[arn]["config_hash"]:
                modified.append(
                    {
                        "arn": arn,
                        "resource_type": snap2_by_arn[arn]["resource_type"],
                        "name": snap2_by_arn[arn]["name"],
                        "region": snap2_by_arn[arn]["region"],
                        "old_hash": snap1_by_arn[arn]["config_hash"],
                        "new_hash": snap2_by_arn[arn]["config_hash"],
                    }
                )

        return {
            "added": added,
            "removed": removed,
            "modified": modified,
            "summary": {
                "snapshot1": snapshot1_name,
                "snapshot2": snapshot2_name,
                "snapshot1_count": len(snap1_resources),
                "snapshot2_count": len(snap2_resources),
                "added_count": len(added),
                "removed_count": len(removed),
                "modified_count": len(modified),
            },
        }

    def get_tags_for_resource(self, arn: str, snapshot_name: Optional[str] = None) -> Dict[str, str]:
        """Get tags for a specific resource.

        Args:
            arn: Resource ARN
            snapshot_name: Specific snapshot (uses most recent if None)

        Returns:
            Dict of tag key-value pairs
        """
        query = """
            SELECT t.key, t.value
            FROM resource_tags t
            JOIN resources r ON t.resource_id = r.id
            JOIN snapshots s ON r.snapshot_id = s.id
            WHERE r.arn = ?
        """
        params: List[str] = [arn]

        if snapshot_name:
            query += " AND s.name = ?"
            params.append(snapshot_name)
        else:
            query += " ORDER BY s.created_at DESC LIMIT 100"

        rows = self.db.fetchall(query, tuple(params))
        return {row["key"]: row["value"] for row in rows}

    def find_by_tag(
        self,
        tag_key: str,
        tag_value: Optional[str] = None,
        snapshot_name: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Find resources by tag.

        Args:
            tag_key: Tag key to search for
            tag_value: Optional tag value to match
            snapshot_name: Limit to specific snapshot
            limit: Maximum results

        Returns:
            List of matching resources
        """
        query = """
            SELECT DISTINCT
                r.arn,
                r.resource_type,
                r.name,
                r.region,
                s.name as snapshot_name,
                t.key as tag_key,
                t.value as tag_value
            FROM resources r
            JOIN snapshots s ON r.snapshot_id = s.id
            JOIN resource_tags t ON r.id = t.resource_id
            WHERE t.key = ?
        """
        params: List[Any] = [tag_key]

        if tag_value:
            query += " AND t.value = ?"
            params.append(tag_value)

        if snapshot_name:
            query += " AND s.name = ?"
            params.append(snapshot_name)

        query += f" ORDER BY s.created_at DESC LIMIT {limit}"

        return self.db.fetchall(query, tuple(params))

    def get_unique_resource_types(self, snapshot_name: Optional[str] = None) -> List[str]:
        """Get list of unique resource types.

        Args:
            snapshot_name: Limit to specific snapshot

        Returns:
            List of resource type strings
        """
        query = """
            SELECT DISTINCT r.resource_type
            FROM resources r
        """
        params: List[str] = []

        if snapshot_name:
            query += " JOIN snapshots s ON r.snapshot_id = s.id WHERE s.name = ?"
            params.append(snapshot_name)

        query += " ORDER BY r.resource_type"

        rows = self.db.fetchall(query, tuple(params))
        return [row["resource_type"] for row in rows]

    def get_unique_regions(self, snapshot_name: Optional[str] = None) -> List[str]:
        """Get list of unique regions.

        Args:
            snapshot_name: Limit to specific snapshot

        Returns:
            List of region strings
        """
        query = """
            SELECT DISTINCT r.region
            FROM resources r
        """
        params: List[str] = []

        if snapshot_name:
            query += " JOIN snapshots s ON r.snapshot_id = s.id WHERE s.name = ?"
            params.append(snapshot_name)

        query += " ORDER BY r.region"

        rows = self.db.fetchall(query, tuple(params))
        return [row["region"] for row in rows]

    def get_creators_summary(self, snapshot_name: str) -> List[Dict[str, Any]]:
        """Get summary of resource creators for a snapshot.

        Aggregates resources by creator (from _created_by tag) and returns
        statistics including resource counts by type.

        Args:
            snapshot_name: Snapshot name to analyze

        Returns:
            List of creator summaries, each containing:
            - creator: Creator ARN
            - creator_type: Type (AssumedRole, IAMUser, Root, Service)
            - resource_count: Total resources created
            - resource_types: Dict of resource type -> count
            - resources: List of resource details
        """
        # Query all resources with creator info
        query = """
            SELECT
                r.arn,
                r.resource_type,
                r.name,
                r.region,
                t_by.value as created_by,
                t_type.value as created_by_type,
                t_at.value as created_at
            FROM resources r
            JOIN snapshots s ON r.snapshot_id = s.id
            JOIN resource_tags t_by ON r.id = t_by.resource_id AND t_by.key = '_created_by'
            LEFT JOIN resource_tags t_type ON r.id = t_type.resource_id AND t_type.key = '_created_by_type'
            LEFT JOIN resource_tags t_at ON r.id = t_at.resource_id AND t_at.key = '_created_at'
            WHERE s.name = ?
            ORDER BY t_by.value, r.resource_type, r.name
        """

        rows = self.db.fetchall(query, (snapshot_name,))

        # Aggregate by creator
        creators: Dict[str, Dict[str, Any]] = {}

        for row in rows:
            creator = row["created_by"]
            if creator not in creators:
                creators[creator] = {
                    "creator": creator,
                    "creator_type": row.get("created_by_type") or "Unknown",
                    "resource_count": 0,
                    "resource_types": {},
                    "resources": [],
                }

            creators[creator]["resource_count"] += 1

            # Count by resource type
            rtype = row["resource_type"]
            if rtype not in creators[creator]["resource_types"]:
                creators[creator]["resource_types"][rtype] = 0
            creators[creator]["resource_types"][rtype] += 1

            # Add resource details
            creators[creator]["resources"].append(
                {
                    "arn": row["arn"],
                    "resource_type": rtype,
                    "name": row["name"],
                    "region": row["region"],
                    "created_at": row.get("created_at"),
                }
            )

        # Convert to list and sort by resource count descending
        result = list(creators.values())
        result.sort(key=lambda x: x["resource_count"], reverse=True)

        return result

    def get_creators_count(self, snapshot_name: str) -> int:
        """Get count of unique creators in a snapshot.

        Args:
            snapshot_name: Snapshot name to analyze

        Returns:
            Number of unique creators
        """
        query = """
            SELECT COUNT(DISTINCT t.value) as count
            FROM resources r
            JOIN snapshots s ON r.snapshot_id = s.id
            JOIN resource_tags t ON r.id = t.resource_id
            WHERE s.name = ? AND t.key = '_created_by'
        """

        row = self.db.fetchone(query, (snapshot_name,))
        return row["count"] if row else 0

    def get_resources_without_creator(self, snapshot_name: str) -> int:
        """Get count of resources without creator information.

        Args:
            snapshot_name: Snapshot name to analyze

        Returns:
            Number of resources without _created_by tag
        """
        query = """
            SELECT COUNT(*) as count
            FROM resources r
            JOIN snapshots s ON r.snapshot_id = s.id
            WHERE s.name = ?
            AND r.id NOT IN (
                SELECT resource_id FROM resource_tags WHERE key = '_created_by'
            )
        """

        row = self.db.fetchone(query, (snapshot_name,))
        return row["count"] if row else 0
