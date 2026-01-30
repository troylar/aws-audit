"""Resource cleaner for restoration operations.

Main orchestrator for resource cleanup/restoration with preview and execution modes.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any, Optional

from src.delta.calculator import DeltaCalculator
from src.models.deletion_operation import DeletionOperation, OperationMode, OperationStatus
from src.models.deletion_record import DeletionRecord, DeletionStatus
from src.restore.audit import AuditStorage
from src.restore.dependency import DependencyResolver
from src.restore.safety import SafetyChecker
from src.snapshot.storage import SnapshotStorage

logger = logging.getLogger(__name__)


class ResourceCleaner:
    """Resource cleaner orchestrator.

    Coordinates resource cleanup/restoration operations with safety checks,
    dependency resolution, and audit logging. Supports both preview (dry-run)
    and execution modes.

    Attributes:
        snapshot_storage: Snapshot storage for baseline comparison
        safety_checker: Safety checker for protection rules
        audit_storage: Audit storage for deletion logs
        dependency_resolver: Dependency resolver for deletion ordering
    """

    def __init__(
        self,
        snapshot_storage: SnapshotStorage,
        safety_checker: SafetyChecker,
        audit_storage: AuditStorage,
    ) -> None:
        """Initialize resource cleaner.

        Args:
            snapshot_storage: Snapshot storage instance
            safety_checker: Safety checker with protection rules
            audit_storage: Audit storage for logging
        """
        self.snapshot_storage = snapshot_storage
        self.safety_checker = safety_checker
        self.audit_storage = audit_storage
        self.dependency_resolver = DependencyResolver()

    def preview(
        self,
        baseline_snapshot: str,
        account_id: str,
        aws_profile: Optional[str] = None,
        resource_types: Optional[list[str]] = None,
        regions: Optional[list[str]] = None,
    ) -> DeletionOperation:
        """Preview resources that would be deleted (dry-run mode).

        Identifies resources created after baseline snapshot and applies protection
        rules without performing any deletions.

        Args:
            baseline_snapshot: Name of baseline snapshot to compare against
            account_id: AWS account ID to validate
            aws_profile: AWS profile name (optional)
            resource_types: Filter by resource types (optional)
            regions: Filter by regions (optional)

        Returns:
            DeletionOperation in planned status with resource counts

        Raises:
            ValueError: If snapshot not found or account ID mismatch
        """
        # Validate snapshot exists and load it
        try:
            snapshot = self.snapshot_storage.load_snapshot(baseline_snapshot)
        except (FileNotFoundError, ValueError):
            raise ValueError(f"Snapshot '{baseline_snapshot}' not found")

        # Validate account ID matches
        snapshot_account = snapshot.account_id
        if snapshot_account != account_id:
            raise ValueError(
                f"Account ID mismatch: snapshot has {snapshot_account}, current credentials have {account_id}"
            )

        # Collect current resources
        current_resources = self._collect_current_resources(account_id, regions)

        # Create a temporary snapshot for current state
        from src.models.snapshot import Snapshot

        current_snapshot = Snapshot(
            name="current",
            created_at=datetime.utcnow(),
            account_id=account_id,
            regions=regions or snapshot.regions,
            resources=[self._dict_to_resource(r) for r in current_resources],
            resource_count=len(current_resources),
        )

        # Calculate delta (new resources since baseline)
        delta_calc = DeltaCalculator(reference_snapshot=snapshot, current_snapshot=current_snapshot)
        delta_result = delta_calc.calculate()

        # Get added resources (convert back to dict format for filtering)
        new_resources = [self._resource_to_dict(r) for r in delta_result.added_resources]

        # Apply filters
        filtered_resources = self._apply_filters(
            new_resources,
            resource_types=resource_types,
            regions=regions,
        )

        # Apply protection rules and count protected resources
        protected_count = 0

        for resource in filtered_resources:
            is_protected, reason = self.safety_checker.is_protected(resource)

            if is_protected:
                protected_count += 1

        # Create operation
        operation = DeletionOperation(
            operation_id=f"op_{uuid.uuid4()}",
            baseline_snapshot=baseline_snapshot,
            timestamp=datetime.utcnow(),
            account_id=account_id,
            mode=OperationMode.DRY_RUN,
            status=OperationStatus.PLANNED,
            total_resources=len(filtered_resources),
            succeeded_count=0,
            failed_count=0,
            skipped_count=protected_count,
            aws_profile=aws_profile,
            filters=self._build_filters_dict(resource_types, regions),
        )

        return operation

    def execute(
        self,
        baseline_snapshot: str,
        account_id: str,
        confirmed: bool = False,
        aws_profile: Optional[str] = None,
        resource_types: Optional[list[str]] = None,
        regions: Optional[list[str]] = None,
    ) -> tuple:
        """Execute resource deletion to restore to baseline (execution mode).

        Performs actual deletion of resources created after baseline snapshot with
        protection checks and audit logging.

        Args:
            baseline_snapshot: Name of baseline snapshot to restore to
            account_id: AWS account ID to validate
            confirmed: Must be True to proceed with deletion
            aws_profile: AWS profile name (optional)
            resource_types: Filter by resource types (optional)
            regions: Filter by regions (optional)

        Returns:
            Tuple of (DeletionOperation, List[DeletionRecord]) with execution results

        Raises:
            ValueError: If not confirmed or snapshot not found or account ID mismatch
        """
        # Require confirmation for destructive operations
        if not confirmed:
            raise ValueError("Deletion requires explicit confirmation. Set confirmed=True or use --confirm flag.")

        # Validate snapshot exists and load it
        try:
            snapshot = self.snapshot_storage.load_snapshot(baseline_snapshot)
        except (FileNotFoundError, ValueError):
            raise ValueError(f"Snapshot '{baseline_snapshot}' not found")

        # Validate account ID matches
        snapshot_account = snapshot.account_id
        if snapshot_account != account_id:
            raise ValueError(
                f"Account ID mismatch: snapshot has {snapshot_account}, current credentials have {account_id}"
            )

        # Collect current resources
        current_resources = self._collect_current_resources(account_id, regions)

        # Create a temporary snapshot for current state
        from src.models.snapshot import Snapshot

        current_snapshot = Snapshot(
            name="current",
            created_at=datetime.utcnow(),
            account_id=account_id,
            regions=regions or snapshot.regions,
            resources=[self._dict_to_resource(r) for r in current_resources],
            resource_count=len(current_resources),
        )

        # Calculate delta (new resources since baseline)
        delta_calc = DeltaCalculator(reference_snapshot=snapshot, current_snapshot=current_snapshot)
        delta_result = delta_calc.calculate()

        # Get added resources (convert back to dict format for filtering)
        new_resources = [self._resource_to_dict(r) for r in delta_result.added_resources]

        # Apply filters
        filtered_resources = self._apply_filters(
            new_resources,
            resource_types=resource_types,
            regions=regions,
        )

        # Import at module level to avoid UnboundLocalError

        # Execute deletions with protection checks
        succeeded_count = 0
        failed_count = 0
        skipped_count = 0
        deletion_records = []
        operation_id = f"op_{uuid.uuid4()}"

        for resource in filtered_resources:
            record_id = f"rec_{uuid.uuid4()}"

            # Check protection rules
            is_protected, reason = self.safety_checker.is_protected(resource)

            if is_protected:
                skipped_count += 1
                # Create deletion record for skipped resource
                record = DeletionRecord(
                    record_id=record_id,
                    operation_id=operation_id,
                    resource_id=resource.get("resource_id", ""),
                    resource_arn=resource.get("arn", ""),
                    resource_type=resource.get("resource_type", ""),
                    region=resource.get("region", ""),
                    status=DeletionStatus.SKIPPED,
                    protection_reason=reason or "Protected by safety rules",
                    timestamp=datetime.utcnow(),
                )
                deletion_records.append(record)
                continue

            # Attempt deletion
            success, error_message = self._delete_resource(resource, aws_profile)

            if success:
                succeeded_count += 1
                # Create successful deletion record
                record = DeletionRecord(
                    record_id=record_id,
                    operation_id=operation_id,
                    resource_id=resource.get("resource_id", ""),
                    resource_arn=resource.get("arn", ""),
                    resource_type=resource.get("resource_type", ""),
                    region=resource.get("region", ""),
                    status=DeletionStatus.SUCCEEDED,
                    timestamp=datetime.utcnow(),
                )
            else:
                failed_count += 1
                # Create failed deletion record with actual error message
                record = DeletionRecord(
                    record_id=record_id,
                    operation_id=operation_id,
                    resource_id=resource.get("resource_id", ""),
                    resource_arn=resource.get("arn", ""),
                    resource_type=resource.get("resource_type", ""),
                    region=resource.get("region", ""),
                    status=DeletionStatus.FAILED,
                    error_code="DeletionFailed",
                    error_message=error_message or "Resource deletion failed",
                    timestamp=datetime.utcnow(),
                )
            deletion_records.append(record)

        # Determine final status
        if failed_count > 0:
            if succeeded_count > 0:
                final_status = OperationStatus.PARTIAL
            else:
                final_status = OperationStatus.FAILED
        else:
            final_status = OperationStatus.COMPLETED

        # Create operation (use same operation_id from records)
        operation = DeletionOperation(
            operation_id=operation_id,
            baseline_snapshot=baseline_snapshot,
            timestamp=datetime.utcnow(),
            account_id=account_id,
            mode=OperationMode.EXECUTE,
            status=final_status,
            total_resources=len(filtered_resources),
            succeeded_count=succeeded_count,
            failed_count=failed_count,
            skipped_count=skipped_count,
            aws_profile=aws_profile,
            filters=self._build_filters_dict(resource_types, regions),
        )

        # Log operation to audit storage with deletion records
        self.audit_storage.log_operation(operation, deletion_records)

        return operation, deletion_records

    def _delete_resource(self, resource: dict, aws_profile: Optional[str] = None) -> tuple:
        """Delete a single AWS resource.

        Args:
            resource: Resource dictionary with type, ARN, region
            aws_profile: AWS profile name (optional)

        Returns:
            Tuple of (success: bool, error_message: str or None)
        """
        from src.restore.deleter import ResourceDeleter

        deleter = ResourceDeleter(aws_profile=aws_profile)

        resource_type = resource.get("resource_type", "")
        resource_id = resource.get("resource_id", "")
        region = resource.get("region", "")
        arn = resource.get("arn", "")

        success, error_message = deleter.delete_resource(
            resource_type=resource_type,
            resource_id=resource_id,
            region=region,
            arn=arn,
        )

        if not success:
            logger.warning(f"Failed to delete {resource_type} {resource_id}: {error_message}")

        return success, error_message

    def _collect_current_resources(self, account_id: str, regions: Optional[list[str]] = None) -> list[dict]:
        """Collect current resources from AWS account.

        This is a placeholder that would normally call AWS APIs to collect
        current resource state. For testing, this is mocked.

        Args:
            account_id: AWS account ID
            regions: Regions to collect from (optional)

        Returns:
            List of current resources
        """
        # Placeholder - in real implementation, would use snapshot capturer
        # or similar mechanism to collect current state
        return []

    def _apply_filters(
        self,
        resources: list[dict],
        resource_types: Optional[list[str]] = None,
        regions: Optional[list[str]] = None,
    ) -> list[dict]:
        """Apply filters to resource list.

        Args:
            resources: List of resources to filter
            resource_types: Filter by resource types (optional)
            regions: Filter by regions (optional)

        Returns:
            Filtered list of resources
        """
        filtered = resources

        if resource_types:
            filtered = [r for r in filtered if r.get("resource_type") in resource_types]

        if regions:
            filtered = [r for r in filtered if r.get("region") in regions]

        return filtered

    def _build_filters_dict(
        self,
        resource_types: Optional[list[str]] = None,
        regions: Optional[list[str]] = None,
    ) -> Optional[dict]:
        """Build filters dictionary for operation metadata.

        Args:
            resource_types: Resource types filter
            regions: Regions filter

        Returns:
            Filters dictionary or None if no filters
        """
        filters = {}

        if resource_types:
            filters["resource_types"] = resource_types

        if regions:
            filters["regions"] = regions

        return filters if filters else None

    def _resource_to_dict(self, resource: Any) -> dict:
        """Convert Resource object to dictionary format.

        Args:
            resource: Resource object from snapshot

        Returns:
            Dictionary representation of resource
        """
        # Resource objects have these attributes
        return {
            "resource_id": resource.name,  # Resource uses 'name' field
            "resource_type": resource.resource_type,
            "region": resource.region,
            "arn": resource.arn,
            "tags": resource.tags,
            "estimated_monthly_cost": getattr(resource, "estimated_monthly_cost", None),
        }

    def _dict_to_resource(self, resource_dict: dict) -> Any:
        """Convert dictionary to Resource object.

        Args:
            resource_dict: Dictionary representation of resource

        Returns:
            Resource object
        """
        import hashlib

        from src.models.resource import Resource

        # Generate config hash from resource dict for comparison
        config_str = f"{resource_dict.get('arn', '')}{resource_dict.get('resource_type', '')}"
        config_hash = hashlib.sha256(config_str.encode()).hexdigest()

        return Resource(
            arn=resource_dict.get("arn", ""),
            resource_type=resource_dict.get("resource_type", ""),
            name=resource_dict.get("resource_id", ""),
            region=resource_dict.get("region", ""),
            config_hash=config_hash,
            tags=resource_dict.get("tags", {}),
        )
