"""Delta calculator for comparing snapshots."""

import logging
from datetime import datetime, timezone
from typing import List, Optional

from ..models.delta_report import DeltaReport, ResourceChange
from ..models.resource import Resource
from ..models.snapshot import Snapshot

logger = logging.getLogger(__name__)


class DeltaCalculator:
    """Calculate differences between two snapshots."""

    def __init__(self, reference_snapshot: Snapshot, current_snapshot: Snapshot):
        """Initialize delta calculator.

        Args:
            reference_snapshot: The reference snapshot to compare against
            current_snapshot: The current snapshot
        """
        self.reference = reference_snapshot
        self.current = current_snapshot

        # Index resources by ARN for fast lookup
        self.reference_index = {r.arn: r for r in reference_snapshot.resources}
        self.current_index = {r.arn: r for r in current_snapshot.resources}

    def calculate(
        self,
        resource_type_filter: Optional[List[str]] = None,
        region_filter: Optional[List[str]] = None,
    ) -> DeltaReport:
        """Calculate delta between reference and current snapshots.

        Args:
            resource_type_filter: Optional list of resource types to include
            region_filter: Optional list of regions to include

        Returns:
            DeltaReport with added, deleted, and modified resources
        """
        logger.info("Calculating delta between reference and current snapshots")

        added_resources = []
        deleted_resources = []
        modified_resources = []

        reference_arns = set(self.reference_index.keys())
        current_arns = set(self.current_index.keys())

        # Find added resources (in current but not in reference)
        added_arns = current_arns - reference_arns
        for arn in added_arns:
            resource = self.current_index[arn]
            if self._matches_filters(resource, resource_type_filter, region_filter):
                added_resources.append(resource)

        # Find deleted resources (in reference but not in current)
        deleted_arns = reference_arns - current_arns
        for arn in deleted_arns:
            resource = self.reference_index[arn]
            if self._matches_filters(resource, resource_type_filter, region_filter):
                deleted_resources.append(resource)

        # Find modified resources (in both but with different config)
        common_arns = reference_arns & current_arns
        for arn in common_arns:
            reference_resource = self.reference_index[arn]
            current_resource = self.current_index[arn]

            if self._matches_filters(current_resource, resource_type_filter, region_filter):
                # Compare config hashes to detect modifications
                if reference_resource.config_hash != current_resource.config_hash:
                    change = ResourceChange(
                        resource=current_resource,
                        baseline_resource=reference_resource,
                        change_type="modified",
                        old_config_hash=reference_resource.config_hash,
                        new_config_hash=current_resource.config_hash,
                    )
                    modified_resources.append(change)

        # Create delta report
        report = DeltaReport(
            generated_at=datetime.now(timezone.utc),
            baseline_snapshot_name=self.reference.name,
            current_snapshot_name=self.current.name,
            added_resources=added_resources,
            deleted_resources=deleted_resources,
            modified_resources=modified_resources,
            baseline_resource_count=len(self.reference.resources),
            current_resource_count=len(self.current.resources),
        )

        logger.info(
            f"Delta calculated: {len(added_resources)} added, "
            f"{len(deleted_resources)} deleted, {len(modified_resources)} modified"
        )

        return report

    def _matches_filters(
        self,
        resource: Resource,
        resource_type_filter: Optional[List[str]],
        region_filter: Optional[List[str]],
    ) -> bool:
        """Check if resource matches the specified filters.

        Args:
            resource: Resource to check
            resource_type_filter: Optional list of resource types to include
            region_filter: Optional list of regions to include

        Returns:
            True if resource matches all filters
        """
        # Check resource type filter
        if resource_type_filter:
            if resource.resource_type not in resource_type_filter:
                return False

        # Check region filter
        if region_filter:
            if resource.region not in region_filter:
                return False

        return True


def compare_to_current_state(
    reference_snapshot: Snapshot,
    profile_name: Optional[str] = None,
    regions: Optional[List[str]] = None,
    resource_type_filter: Optional[List[str]] = None,
    region_filter: Optional[List[str]] = None,
) -> DeltaReport:
    """Compare reference snapshot to current AWS state.

    This is a convenience function that captures current state and calculates delta.

    Args:
        reference_snapshot: The reference snapshot to compare against
        profile_name: AWS profile name (optional)
        regions: Regions to scan (defaults to reference snapshot regions)
        resource_type_filter: Optional list of resource types to include in delta
        region_filter: Optional list of regions to include in delta

    Returns:
        DeltaReport with changes
    """
    from ..aws.credentials import get_account_id
    from ..snapshot.capturer import create_snapshot

    # Use reference snapshot regions if not specified
    if not regions:
        regions = reference_snapshot.regions

    # Get account ID
    account_id = get_account_id(profile_name)

    # Capture current state (don't save it, just use for comparison)
    logger.info("Capturing current AWS state for comparison...")
    current_snapshot = create_snapshot(
        name=f"temp-current-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}",
        regions=regions,
        account_id=account_id,
        profile_name=profile_name,
        set_active=False,
    )

    # Calculate delta
    calculator = DeltaCalculator(reference_snapshot, current_snapshot)
    return calculator.calculate(
        resource_type_filter=resource_type_filter,
        region_filter=region_filter,
    )
