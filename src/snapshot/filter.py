"""Resource filtering for creating historical and tagged baselines."""

import logging
from datetime import datetime
from typing import Dict, List, Optional

from ..models.resource import Resource

logger = logging.getLogger(__name__)


class ResourceFilter:
    """Filter resources by creation date and tags."""

    def __init__(
        self,
        before_date: Optional[datetime] = None,
        after_date: Optional[datetime] = None,
        required_tags: Optional[Dict[str, str]] = None,
        include_tags: Optional[Dict[str, str]] = None,
        exclude_tags: Optional[Dict[str, str]] = None,
    ):
        """Initialize resource filter.

        Args:
            before_date: Include only resources created before this date (exclusive)
            after_date: Include only resources created on or after this date (inclusive)
            required_tags: DEPRECATED - use include_tags instead (kept for backward compatibility)
            include_tags: Resources must have ALL these tags (AND logic)
            exclude_tags: Resources must NOT have ANY of these tags (OR logic)
        """
        self.before_date = before_date
        self.after_date = after_date
        # Support both required_tags (deprecated) and include_tags (new)
        self.include_tags = include_tags or required_tags or {}
        self.exclude_tags = exclude_tags or {}
        # Keep required_tags for backward compatibility
        self.required_tags = self.include_tags

        # Statistics
        self.stats = {
            "total_collected": 0,
            "date_matched": 0,
            "tag_matched": 0,
            "final_count": 0,
            "filtered_out_by_date": 0,
            "filtered_out_by_tags": 0,
            "filtered_out_by_exclude_tags": 0,
            "missing_creation_date": 0,
        }

    def apply(self, resources: List[Resource]) -> List[Resource]:
        """Apply filters to a list of resources.

        Args:
            resources: List of resources to filter

        Returns:
            Filtered list of resources
        """
        self.stats["total_collected"] = len(resources)
        filtered = []

        for resource in resources:
            if self._matches_filters(resource):
                filtered.append(resource)

        self.stats["final_count"] = len(filtered)

        logger.debug(
            f"Filtering complete: {self.stats['total_collected']} collected, "
            f"{self.stats['final_count']} matched filters"
        )

        return filtered

    def _matches_filters(self, resource: Resource) -> bool:
        """Check if a resource matches all filters.

        Args:
            resource: Resource to check

        Returns:
            True if resource matches all filters
        """
        # Check date filters
        if not self._matches_date_filter(resource):
            self.stats["filtered_out_by_date"] += 1
            return False

        self.stats["date_matched"] += 1

        # Check exclude tags first (if resource has any excluded tags, reject immediately)
        if not self._matches_exclude_filter(resource):
            self.stats["filtered_out_by_exclude_tags"] += 1
            return False

        # Check include tag filters
        if not self._matches_tag_filter(resource):
            self.stats["filtered_out_by_tags"] += 1
            return False

        self.stats["tag_matched"] += 1

        return True

    def _matches_date_filter(self, resource: Resource) -> bool:
        """Check if resource matches date filters.

        Args:
            resource: Resource to check

        Returns:
            True if resource matches date filters (or no date filters specified)
        """
        # If no date filters, everything matches
        if not self.before_date and not self.after_date:
            return True

        # If resource has no creation date or invalid type, we can't filter by date
        # Many AWS resources don't expose creation timestamps (VPCs, Security Groups, etc.)
        if not resource.created_at:
            self.stats["missing_creation_date"] += 1
            logger.debug(f"Resource {resource.arn} has no creation date - including by default")
            return True

        # Handle string dates (convert to datetime)
        resource_date = resource.created_at
        if isinstance(resource_date, str):
            try:
                resource_date = datetime.fromisoformat(resource_date.replace("Z", "+00:00"))
            except ValueError:
                self.stats["missing_creation_date"] += 1
                logger.debug(f"Resource {resource.arn} has invalid date format - including by default")
                return True

        # Ensure we have a datetime object
        if not isinstance(resource_date, datetime):
            self.stats["missing_creation_date"] += 1
            logger.debug(f"Resource {resource.arn} has no valid creation date - including by default")
            return True

        # Make sure resource.created_at is timezone-aware for comparison
        if resource_date.tzinfo is None:
            # Assume UTC if no timezone
            from datetime import timezone as tz

            resource_date = resource_date.replace(tzinfo=tz.utc)

        # Check before_date filter (exclusive)
        if self.before_date:
            # Make sure before_date is timezone-aware
            before_date_aware = self.before_date
            if before_date_aware.tzinfo is None:
                from datetime import timezone as tz

                before_date_aware = before_date_aware.replace(tzinfo=tz.utc)

            if resource_date >= before_date_aware:
                logger.debug(f"Resource {resource.name} created {resource_date} is not before {before_date_aware}")
                return False

        # Check after_date filter (inclusive)
        if self.after_date:
            # Make sure after_date is timezone-aware
            after_date_aware = self.after_date
            if after_date_aware.tzinfo is None:
                from datetime import timezone as tz

                after_date_aware = after_date_aware.replace(tzinfo=tz.utc)

            if resource_date < after_date_aware:
                logger.debug(f"Resource {resource.name} created {resource_date} is before {after_date_aware}")
                return False

        return True

    def _matches_tag_filter(self, resource: Resource) -> bool:
        """Check if resource has all include tags (AND logic).

        Args:
            resource: Resource to check

        Returns:
            True if resource has all include tags (or no tag filters specified)
        """
        # If no include tag filters, everything matches
        if not self.include_tags:
            return True

        # Check if resource has ALL include tags with matching values (AND logic)
        for key, value in self.include_tags.items():
            if key not in resource.tags:
                logger.debug(f"Resource {resource.name} missing include tag: {key}")
                return False

            if resource.tags[key] != value:
                logger.debug(
                    f"Resource {resource.name} tag {key}={resource.tags[key]} does not match required value {value}"
                )
                return False

        return True

    def _matches_exclude_filter(self, resource: Resource) -> bool:
        """Check if resource has any exclude tags (OR logic).

        Args:
            resource: Resource to check

        Returns:
            True if resource does NOT have any exclude tags (or no exclude filters specified)
        """
        # If no exclude tag filters, everything matches
        if not self.exclude_tags:
            return True

        # Check if resource has ANY of the exclude tags (OR logic)
        for key, value in self.exclude_tags.items():
            if key in resource.tags and resource.tags[key] == value:
                logger.debug(f"Resource {resource.name} has exclude tag {key}={value}")
                return False

        return True

    def get_filter_summary(self) -> str:
        """Get a human-readable summary of applied filters.

        Returns:
            Formatted string describing the filters
        """
        parts = []

        if self.before_date:
            parts.append(f"created before {self.before_date.strftime('%Y-%m-%d')}")

        if self.after_date:
            parts.append(f"created on/after {self.after_date.strftime('%Y-%m-%d')}")

        if self.include_tags:
            tag_strs = [f"{k}={v}" for k, v in self.include_tags.items()]
            parts.append(f"include tags: {', '.join(tag_strs)}")

        if self.exclude_tags:
            tag_strs = [f"{k}={v}" for k, v in self.exclude_tags.items()]
            parts.append(f"exclude tags: {', '.join(tag_strs)}")

        if not parts:
            return "No filters applied"

        return "Filters: " + " AND ".join(parts)

    def get_statistics_summary(self) -> Dict[str, int]:
        """Get filtering statistics.

        Returns:
            Dictionary of filtering statistics
        """
        return self.stats.copy()
