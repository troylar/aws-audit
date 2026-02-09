"""Creator cache storage for CloudTrail enrichment results."""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from .database import Database

logger = logging.getLogger(__name__)


class CreatorCacheStore:
    """Cache for resource creator lookups from CloudTrail.

    Stores resource_type:resource_name -> creator_info mappings
    so repeat enrichment runs can skip CloudTrail API calls.
    """

    def __init__(self, db: Database):
        self.db = db

    def lookup(
        self,
        account_id: str,
        resource_keys: List[str],
    ) -> Dict[str, Dict[str, str]]:
        """Bulk lookup cached creator info for resource keys.

        Args:
            account_id: AWS account ID
            resource_keys: List of "resource_type:resource_name" keys

        Returns:
            Dict mapping key -> {"created_by", "created_by_type", "created_at"}
        """
        if not resource_keys:
            return {}

        results: Dict[str, Dict[str, str]] = {}

        # Parse keys into (resource_type, resource_name) pairs
        pairs = []
        for key in resource_keys:
            parts = key.split(":", 1)
            if len(parts) == 2:
                pairs.append((parts[0], parts[1]))

        if not pairs:
            return results

        # Query in batches to avoid SQLite variable limit
        batch_size = 500
        for i in range(0, len(pairs), batch_size):
            batch = pairs[i : i + batch_size]
            placeholders = " OR ".join(
                ["(resource_type = ? AND resource_name = ?)"] * len(batch)
            )
            params: list = [account_id]
            for rt, rn in batch:
                params.extend([rt, rn])

            rows = self.db.fetchall(
                f"""
                SELECT resource_type, resource_name, created_by, created_by_type, created_at
                FROM creator_cache
                WHERE account_id = ? AND ({placeholders})
                """,
                tuple(params),
            )

            for row in rows:
                key = f"{row['resource_type']}:{row['resource_name']}"
                results[key] = {
                    "created_by": row["created_by"],
                    "created_by_type": row["created_by_type"],
                    "created_at": row["created_at"],
                }

        return results

    def save_batch(
        self,
        account_id: str,
        creators: Dict[str, Dict[str, str]],
    ) -> int:
        """Bulk save creator info to cache.

        Args:
            account_id: AWS account ID
            creators: Dict mapping "resource_type:resource_name" -> creator info

        Returns:
            Number of records saved
        """
        if not creators:
            return 0

        now = datetime.now(timezone.utc).isoformat()

        with self.db.transaction() as cursor:
            data = []
            for key, info in creators.items():
                parts = key.split(":", 1)
                if len(parts) != 2:
                    continue
                resource_type, resource_name = parts
                data.append((
                    account_id,
                    resource_type,
                    resource_name,
                    info["created_by"],
                    info["created_by_type"],
                    info["created_at"],
                    now,
                ))

            cursor.executemany(
                """
                INSERT OR REPLACE INTO creator_cache (
                    account_id, resource_type, resource_name,
                    created_by, created_by_type, created_at, cached_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                data,
            )

        logger.debug(f"Cached {len(data)} creator entries for account {account_id}")
        return len(data)

    def clear(self, account_id: Optional[str] = None) -> int:
        """Clear cached creator entries.

        Args:
            account_id: If provided, only clear entries for this account.
                        If None, clear all entries.

        Returns:
            Number of records deleted
        """
        with self.db.transaction() as cursor:
            if account_id:
                cursor.execute(
                    "DELETE FROM creator_cache WHERE account_id = ?",
                    (account_id,),
                )
            else:
                cursor.execute("DELETE FROM creator_cache")
            deleted = cursor.rowcount

        logger.debug(f"Cleared {deleted} creator cache entries")
        return deleted
