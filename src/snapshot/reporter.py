"""
Snapshot report generation logic.

This module contains the SnapshotReporter class responsible for generating
reports from snapshot data, including summary generation, filtering, and
detailed resource views.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Generator, Optional

from src.models.report import DetailedResource, FilterCriteria, FilteredResource, ResourceSummary, SnapshotMetadata

if TYPE_CHECKING:
    from src.models.snapshot import Snapshot


class SnapshotReporter:
    """
    Generates reports from snapshot data.

    This class handles extracting metadata, generating summaries, and
    preparing data for formatting and display.
    """

    def __init__(self, snapshot: Snapshot) -> None:
        """
        Initialize reporter with a snapshot.

        Args:
            snapshot: The snapshot to generate reports from
        """
        self.snapshot = snapshot

    def _extract_metadata(self) -> SnapshotMetadata:
        """
        Extract metadata from snapshot for report header.

        Returns:
            SnapshotMetadata with snapshot information
        """
        return SnapshotMetadata(
            name=self.snapshot.name,
            created_at=self.snapshot.created_at,
            account_id=self.snapshot.account_id,
            regions=self.snapshot.regions,
            inventory_name=self.snapshot.inventory_name,
            total_resource_count=len(self.snapshot.resources),
        )

    def generate_summary(self) -> ResourceSummary:
        """
        Generate aggregated resource summary from snapshot.

        Uses streaming single-pass aggregation for memory efficiency.
        Does not load entire dataset into memory.

        Returns:
            ResourceSummary with aggregated counts
        """
        summary = ResourceSummary()

        # Single-pass streaming aggregation
        for resource in self.snapshot.resources:
            summary.total_count += 1

            # Extract service from resource type
            # Handle both formats: "AWS::EC2::Instance" and "ec2:instance"
            if "::" in resource.resource_type:
                # CloudFormation format: AWS::EC2::Instance
                parts = resource.resource_type.split("::")
                service = parts[1] if len(parts) >= 2 else "Unknown"
            else:
                # Simplified format: ec2:instance
                service = (
                    resource.resource_type.split(":")[0] if ":" in resource.resource_type else resource.resource_type
                )

            # Aggregate by service
            summary.by_service[service] = summary.by_service.get(service, 0) + 1

            # Aggregate by region
            summary.by_region[resource.region] = summary.by_region.get(resource.region, 0) + 1

            # Aggregate by type
            summary.by_type[resource.resource_type] = summary.by_type.get(resource.resource_type, 0) + 1

        return summary

    def get_filtered_resources(self, criteria: FilterCriteria) -> Generator[FilteredResource, None, None]:
        """
        Get filtered resources as generator (memory-efficient streaming).

        Args:
            criteria: Filter criteria with resource types and/or regions

        Yields:
            FilteredResource objects matching the criteria
        """
        for resource in self.snapshot.resources:
            # Convert Resource to FilteredResource for matching
            filtered_resource = FilteredResource(
                arn=resource.arn,
                resource_type=resource.resource_type,
                name=resource.name,
                region=resource.region,
            )

            # Apply filter criteria
            if criteria.matches_resource(filtered_resource):
                yield filtered_resource

    def generate_filtered_summary(self, criteria: FilterCriteria) -> ResourceSummary:
        """
        Generate summary for filtered resources only.

        Args:
            criteria: Filter criteria

        Returns:
            ResourceSummary with counts for filtered resources only
        """
        summary = ResourceSummary()

        # Single-pass streaming aggregation of filtered resources
        for filtered_resource in self.get_filtered_resources(criteria):
            summary.total_count += 1

            # Extract service from resource type
            if "::" in filtered_resource.resource_type:
                parts = filtered_resource.resource_type.split("::")
                service = parts[1] if len(parts) >= 2 else "Unknown"
            else:
                service = (
                    filtered_resource.resource_type.split(":")[0]
                    if ":" in filtered_resource.resource_type
                    else filtered_resource.resource_type
                )

            # Aggregate by service
            summary.by_service[service] = summary.by_service.get(service, 0) + 1

            # Aggregate by region
            summary.by_region[filtered_resource.region] = summary.by_region.get(filtered_resource.region, 0) + 1

            # Aggregate by type
            summary.by_type[filtered_resource.resource_type] = (
                summary.by_type.get(filtered_resource.resource_type, 0) + 1
            )

        return summary

    def get_detailed_resources(
        self, criteria: Optional[FilterCriteria] = None
    ) -> Generator[DetailedResource, None, None]:
        """
        Get detailed resource information as generator.

        Args:
            criteria: Optional filter criteria to limit resources

        Yields:
            DetailedResource objects with full information (tags, creation date, etc.)
        """
        for resource in self.snapshot.resources:
            # Apply filtering if criteria provided
            if criteria:
                filtered_resource = FilteredResource(
                    arn=resource.arn,
                    resource_type=resource.resource_type,
                    name=resource.name,
                    region=resource.region,
                )
                if not criteria.matches_resource(filtered_resource):
                    continue

            # Convert Resource to DetailedResource
            detailed_resource = DetailedResource(
                arn=resource.arn,
                resource_type=resource.resource_type,
                name=resource.name,
                region=resource.region,
                tags=resource.tags,
                created_at=resource.created_at,
                config_hash=resource.config_hash,
            )

            yield detailed_resource
