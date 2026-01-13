"""
Data models for snapshot resource reporting.

This module defines the data structures used for generating and displaying
snapshot resource reports, including metadata, summaries, filtered views,
and detailed resource information.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Literal, Optional, Tuple


@dataclass
class SnapshotMetadata:
    """
    Snapshot identification information for report header.

    Attributes:
        name: Snapshot name (e.g., "baseline-2025-01-29")
        created_at: Snapshot creation timestamp
        account_id: AWS account ID
        regions: List of AWS regions included in snapshot
        inventory_name: Parent inventory name
        total_resource_count: Total number of resources in snapshot
    """

    name: str
    created_at: datetime
    account_id: str
    regions: List[str]
    inventory_name: str
    total_resource_count: int

    @property
    def region_summary(self) -> str:
        """Human-readable region list (e.g., 'us-east-1, us-west-2 (2 regions)')."""
        if len(self.regions) <= 3:
            return ", ".join(self.regions)
        else:
            return f"{', '.join(self.regions[:3])} ... ({len(self.regions)} regions)"


@dataclass
class ResourceSummary:
    """
    Aggregated resource counts for summary view.

    Attributes:
        total_count: Total number of resources
        by_service: Count per AWS service (e.g., {"EC2": 100, "S3": 50})
        by_region: Count per AWS region (e.g., {"us-east-1": 80, "us-west-2": 70})
        by_type: Count per resource type (e.g., {"AWS::EC2::Instance": 50})
    """

    total_count: int = 0
    by_service: Dict[str, int] = field(default_factory=dict)
    by_region: Dict[str, int] = field(default_factory=dict)
    by_type: Dict[str, int] = field(default_factory=dict)

    @property
    def service_count(self) -> int:
        """Number of distinct AWS services."""
        return len(self.by_service)

    @property
    def region_count(self) -> int:
        """Number of distinct AWS regions."""
        return len(self.by_region)

    @property
    def type_count(self) -> int:
        """Number of distinct resource types."""
        return len(self.by_type)

    def top_services(self, limit: int = 5) -> List[Tuple[str, int]]:
        """Return top N services by resource count."""
        return sorted(self.by_service.items(), key=lambda x: x[1], reverse=True)[:limit]

    def top_regions(self, limit: int = 5) -> List[Tuple[str, int]]:
        """Return top N regions by resource count."""
        return sorted(self.by_region.items(), key=lambda x: x[1], reverse=True)[:limit]


@dataclass
class FilteredResource:
    """
    Minimal resource info for filtered view (non-detailed).

    Attributes:
        arn: AWS Resource Name (unique identifier)
        resource_type: CloudFormation resource type (e.g., "AWS::EC2::Instance")
        name: Resource name or identifier
        region: AWS region (e.g., "us-east-1")
    """

    arn: str
    resource_type: str
    name: str
    region: str

    @property
    def service(self) -> str:
        """Extract service name from resource type (e.g., "EC2" from "AWS::EC2::Instance")."""
        parts = self.resource_type.split("::")
        return parts[1] if len(parts) >= 2 else "Unknown"

    @property
    def short_type(self) -> str:
        """Short resource type (e.g., "Instance" from "AWS::EC2::Instance")."""
        parts = self.resource_type.split("::")
        return parts[-1] if parts else self.resource_type


@dataclass
class DetailedResource:
    """
    Full resource details for detailed view.

    Attributes:
        arn: AWS Resource Name
        resource_type: CloudFormation resource type
        name: Resource name or identifier
        region: AWS region
        tags: Key-value tag pairs
        created_at: Resource creation timestamp (if available)
        config_hash: Configuration hash for change detection
    """

    arn: str
    resource_type: str
    name: str
    region: str
    tags: Dict[str, str]
    created_at: Optional[datetime]
    config_hash: str

    @property
    def service(self) -> str:
        """Extract service name from resource type."""
        parts = self.resource_type.split("::")
        return parts[1] if len(parts) >= 2 else "Unknown"

    @property
    def age_days(self) -> Optional[int]:
        """Calculate resource age in days (if creation date available)."""
        if self.created_at:
            from datetime import timezone

            # Handle string dates (convert to datetime)
            created_at = self.created_at
            if isinstance(created_at, str):
                try:
                    created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                except ValueError:
                    return None

            # Ensure we have a datetime object
            if not isinstance(created_at, datetime):
                return None

            # Ensure we're comparing timezone-aware datetimes
            now_utc = datetime.now(timezone.utc)
            created = created_at if created_at.tzinfo else created_at.replace(tzinfo=timezone.utc)
            return (now_utc - created).days
        return None

    @property
    def tag_count(self) -> int:
        """Number of tags applied to resource."""
        return len(self.tags)

    def has_tag(self, key: str, value: Optional[str] = None) -> bool:
        """Check if resource has specific tag (optionally with value)."""
        if key not in self.tags:
            return False
        if value is not None:
            return self.tags[key] == value
        return True


@dataclass
class FilterCriteria:
    """
    Filter specification for narrowing report results.

    Attributes:
        resource_types: List of resource types to include (flexible matching)
        regions: List of AWS regions to include (exact matching)
        match_mode: Matching strategy ("flexible" or "exact")
    """

    resource_types: Optional[List[str]] = None
    regions: Optional[List[str]] = None
    match_mode: Literal["flexible", "exact"] = "flexible"

    def __post_init__(self) -> None:
        """Normalize filter values (lowercase for case-insensitive matching)."""
        if self.resource_types:
            self.resource_types = [rt.lower() for rt in self.resource_types]
        if self.regions:
            self.regions = [r.lower() for r in self.regions]

    @property
    def has_filters(self) -> bool:
        """Check if any filters are applied."""
        return bool(self.resource_types or self.regions)

    @property
    def filter_count(self) -> int:
        """Total number of filter criteria."""
        count = 0
        if self.resource_types:
            count += len(self.resource_types)
        if self.regions:
            count += len(self.regions)
        return count

    def matches_resource(self, resource: FilteredResource) -> bool:
        """
        Check if resource matches filter criteria.

        Uses flexible matching for resource types (see research.md Task 2).
        Uses exact matching for regions (case-insensitive).
        """
        # Region filter (exact match, case-insensitive)
        if self.regions and resource.region.lower() not in self.regions:
            return False

        # Resource type filter (flexible matching)
        if self.resource_types:
            type_match = any(
                self._match_resource_type(resource.resource_type, filter_type) for filter_type in self.resource_types
            )
            if not type_match:
                return False

        return True

    def _match_resource_type(self, resource_type: str, filter_value: str) -> bool:
        """Three-tier matching: exact → prefix → contains (see research.md)."""
        resource_lower = resource_type.lower()
        filter_lower = filter_value.lower()

        # Tier 1: Exact match
        if resource_lower == filter_lower:
            return True

        # Tier 2: Service prefix match
        service_prefix = f"aws::{filter_lower}::"
        if resource_lower.startswith(service_prefix):
            return True

        # Tier 3: Contains match
        if filter_lower in resource_lower:
            return True

        return False


@dataclass
class ResourceReport:
    """
    Complete report data structure.

    Attributes:
        snapshot_metadata: Information about the snapshot being reported
        summary: Aggregated resource counts by service/region/type
        filtered_resources: Minimal resource list (if filtering applied)
        detailed_resources: Full resource details (if detailed view requested)
    """

    snapshot_metadata: SnapshotMetadata
    summary: ResourceSummary
    filtered_resources: Optional[List[FilteredResource]] = None
    detailed_resources: Optional[List[DetailedResource]] = None

    @property
    def has_filters(self) -> bool:
        """Check if report includes filtered results."""
        return self.filtered_resources is not None

    @property
    def has_details(self) -> bool:
        """Check if report includes detailed resource info."""
        return self.detailed_resources is not None
