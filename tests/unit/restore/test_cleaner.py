"""Tests for ResourceCleaner class.

Test coverage for resource cleanup orchestration and preview functionality.
"""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from src.models.deletion_operation import OperationMode, OperationStatus
from src.restore.cleaner import ResourceCleaner


class TestResourceCleanerPreview:
    """Test suite for ResourceCleaner preview functionality (US1)."""

    def _create_mock_delta_calculator(self, mock_delta_calc_class: Mock, added_resources: list[dict]) -> None:
        """Helper to create mock delta calculator with added resources.

        Args:
            mock_delta_calc_class: Mocked DeltaCalculator class
            added_resources: List of resource dicts to convert to mock Resource objects
        """
        mock_resource_objects = []
        for res_dict in added_resources:
            mock_res = Mock()
            mock_res.name = res_dict.get("resource_id", "")
            mock_res.resource_type = res_dict.get("resource_type", "")
            mock_res.region = res_dict.get("region", "")
            mock_res.arn = res_dict.get("arn", "")
            mock_res.tags = res_dict.get("tags", {})
            mock_resource_objects.append(mock_res)

        mock_calc_instance = Mock()
        mock_delta_result = Mock()
        mock_delta_result.added_resources = mock_resource_objects
        mock_calc_instance.calculate.return_value = mock_delta_result
        mock_delta_calc_class.return_value = mock_calc_instance

    @pytest.fixture
    def mock_snapshot_storage(self) -> Mock:
        """Create mock snapshot storage."""
        # Create mock resource
        mock_resource = Mock()
        mock_resource.resource_id = "vpc-baseline"
        mock_resource.resource_type = "AWS::EC2::VPC"
        mock_resource.region = "us-east-1"
        mock_resource.arn = "arn:aws:ec2:us-east-1:123456789012:vpc/vpc-baseline"
        mock_resource.tags = {}

        # Create mock snapshot
        mock_snapshot = Mock()
        mock_snapshot.name = "baseline-snapshot"
        mock_snapshot.account_id = "123456789012"
        mock_snapshot.resources = [mock_resource]

        storage = Mock()
        storage.load_snapshot.return_value = mock_snapshot
        return storage

    @pytest.fixture
    def mock_current_resources(self) -> list[dict]:
        """Create mock current resources (baseline + new)."""
        return [
            {
                "resource_id": "vpc-baseline",
                "resource_type": "AWS::EC2::VPC",
                "region": "us-east-1",
                "arn": "arn:aws:ec2:us-east-1:123456789012:vpc/vpc-baseline",
            },
            {
                "resource_id": "i-new-001",
                "resource_type": "AWS::EC2::Instance",
                "region": "us-east-1",
                "arn": "arn:aws:ec2:us-east-1:123456789012:instance/i-new-001",
                "tags": {"Environment": "test"},
            },
            {
                "resource_id": "i-new-002",
                "resource_type": "AWS::EC2::Instance",
                "region": "us-west-2",
                "arn": "arn:aws:ec2:us-west-2:123456789012:instance/i-new-002",
                "tags": {"Environment": "dev"},
            },
        ]

    def test_init_creates_cleaner_with_dependencies(self) -> None:
        """Test initialization creates cleaner with all dependencies."""
        cleaner = ResourceCleaner(
            snapshot_storage=Mock(),
            safety_checker=Mock(),
            audit_storage=Mock(),
        )

        assert cleaner.snapshot_storage is not None
        assert cleaner.safety_checker is not None
        assert cleaner.audit_storage is not None

    @patch("src.restore.cleaner.DeltaCalculator")
    def test_preview_identifies_new_resources(
        self, mock_delta_calc_class: Mock, mock_snapshot_storage: Mock, mock_current_resources: list[dict]
    ) -> None:
        """Test preview identifies resources created after baseline."""
        # Create mock resources for delta result
        mock_resource_1 = Mock()
        mock_resource_1.name = "i-new-001"
        mock_resource_1.resource_type = "AWS::EC2::Instance"
        mock_resource_1.region = "us-east-1"
        mock_resource_1.arn = "arn:aws:ec2:us-east-1:123456789012:instance/i-new-001"
        mock_resource_1.tags = {"Environment": "test"}

        mock_resource_2 = Mock()
        mock_resource_2.name = "i-new-002"
        mock_resource_2.resource_type = "AWS::EC2::Instance"
        mock_resource_2.region = "us-west-2"
        mock_resource_2.arn = "arn:aws:ec2:us-west-2:123456789012:instance/i-new-002"
        mock_resource_2.tags = {"Environment": "dev"}

        # Setup delta calculator mock
        mock_calc_instance = Mock()
        mock_delta_result = Mock()
        mock_delta_result.added_resources = [mock_resource_1, mock_resource_2]
        mock_calc_instance.calculate.return_value = mock_delta_result
        mock_delta_calc_class.return_value = mock_calc_instance

        # Setup safety checker mock
        mock_safety = Mock()
        mock_safety.is_protected.return_value = (False, None)

        cleaner = ResourceCleaner(
            snapshot_storage=mock_snapshot_storage,
            safety_checker=mock_safety,
            audit_storage=Mock(),
        )

        # Mock resource collection
        with patch.object(cleaner, "_collect_current_resources", return_value=mock_current_resources):
            operation = cleaner.preview(
                baseline_snapshot="baseline-snapshot",
                account_id="123456789012",
            )

        assert operation.mode == OperationMode.DRY_RUN
        assert operation.status == OperationStatus.PLANNED
        assert operation.total_resources == 2
        assert operation.baseline_snapshot == "baseline-snapshot"

    @patch("src.restore.cleaner.DeltaCalculator")
    def test_preview_filters_by_resource_type(
        self, mock_delta_calc_class: Mock, mock_snapshot_storage: Mock, mock_current_resources: list[dict]
    ) -> None:
        """Test preview filters resources by type."""
        # Setup delta calculator mock with added resources
        self._create_mock_delta_calculator(mock_delta_calc_class, mock_current_resources[1:])

        mock_safety = Mock()
        mock_safety.is_protected.return_value = (False, None)

        cleaner = ResourceCleaner(
            snapshot_storage=mock_snapshot_storage,
            safety_checker=mock_safety,
            audit_storage=Mock(),
        )

        with patch.object(cleaner, "_collect_current_resources", return_value=mock_current_resources):
            operation = cleaner.preview(
                baseline_snapshot="baseline-snapshot",
                account_id="123456789012",
                resource_types=["AWS::EC2::Instance"],
            )

        assert operation.total_resources == 2
        assert operation.filters["resource_types"] == ["AWS::EC2::Instance"]

    @patch("src.restore.cleaner.DeltaCalculator")
    def test_preview_filters_by_region(
        self, mock_delta_calc_class: Mock, mock_snapshot_storage: Mock, mock_current_resources: list[dict]
    ) -> None:
        """Test preview filters resources by region."""
        # Setup delta calculator mock with added resources
        self._create_mock_delta_calculator(mock_delta_calc_class, mock_current_resources[1:])

        mock_safety = Mock()
        mock_safety.is_protected.return_value = (False, None)

        cleaner = ResourceCleaner(
            snapshot_storage=mock_snapshot_storage,
            safety_checker=mock_safety,
            audit_storage=Mock(),
        )

        with patch.object(cleaner, "_collect_current_resources", return_value=mock_current_resources):
            operation = cleaner.preview(
                baseline_snapshot="baseline-snapshot",
                account_id="123456789012",
                regions=["us-east-1"],
            )

        # Should only include resources in us-east-1
        assert operation.total_resources == 1
        assert operation.filters["regions"] == ["us-east-1"]

    @patch("src.restore.cleaner.DeltaCalculator")
    def test_preview_applies_protection_rules(
        self, mock_delta_calc_class: Mock, mock_snapshot_storage: Mock, mock_current_resources: list[dict]
    ) -> None:
        """Test preview applies protection rules and marks protected resources."""
        # Setup delta calculator mock with added resources
        self._create_mock_delta_calculator(mock_delta_calc_class, mock_current_resources[1:])

        # Create safety checker that protects first resource
        mock_safety = Mock()
        mock_safety.is_protected.side_effect = [
            (True, "Tag Protection=true"),  # First resource protected
            (False, None),  # Second resource not protected
        ]

        cleaner = ResourceCleaner(
            snapshot_storage=mock_snapshot_storage,
            safety_checker=mock_safety,
            audit_storage=Mock(),
        )

        with patch.object(cleaner, "_collect_current_resources", return_value=mock_current_resources):
            operation = cleaner.preview(
                baseline_snapshot="baseline-snapshot",
                account_id="123456789012",
            )

        # Should identify 2 resources but mark 1 as skipped
        assert operation.total_resources == 2
        assert operation.skipped_count == 1

    def test_preview_validates_snapshot_exists(self, mock_snapshot_storage: Mock) -> None:
        """Test preview validates snapshot exists."""
        mock_snapshot_storage.load_snapshot.side_effect = FileNotFoundError("Snapshot not found")

        cleaner = ResourceCleaner(
            snapshot_storage=mock_snapshot_storage,
            safety_checker=Mock(),
            audit_storage=Mock(),
        )

        with pytest.raises(ValueError, match="Snapshot .* not found"):
            cleaner.preview(
                baseline_snapshot="nonexistent-snapshot",
                account_id="123456789012",
            )

    def test_preview_validates_account_id_matches(self) -> None:
        """Test preview validates account ID matches snapshot."""
        # Create mock snapshot with different account ID
        mock_snapshot = Mock()
        mock_snapshot.account_id = "123456789012"

        mock_storage = Mock()
        mock_storage.load_snapshot.return_value = mock_snapshot

        cleaner = ResourceCleaner(
            snapshot_storage=mock_storage,
            safety_checker=Mock(),
            audit_storage=Mock(),
        )

        with pytest.raises(ValueError, match="Account ID mismatch"):
            cleaner.preview(
                baseline_snapshot="baseline-snapshot",
                account_id="999999999999",  # Different account
            )

    @patch("src.restore.cleaner.DeltaCalculator")
    def test_preview_returns_no_resources_when_environment_matches_baseline(
        self, mock_delta_calc_class: Mock, mock_snapshot_storage: Mock
    ) -> None:
        """Test preview returns empty result when no new resources."""
        # Setup delta calculator mock with no added resources
        self._create_mock_delta_calculator(mock_delta_calc_class, [])

        mock_safety = Mock()
        mock_safety.is_protected.return_value = (False, None)

        cleaner = ResourceCleaner(
            snapshot_storage=mock_snapshot_storage,
            safety_checker=mock_safety,
            audit_storage=Mock(),
        )

        with patch.object(cleaner, "_collect_current_resources", return_value=[]):
            operation = cleaner.preview(
                baseline_snapshot="baseline-snapshot",
                account_id="123456789012",
            )

        assert operation.total_resources == 0
        assert operation.mode == OperationMode.DRY_RUN
        assert operation.status == OperationStatus.PLANNED


class TestResourceCleanerExecute:
    """Test suite for ResourceCleaner execute functionality (US2)."""

    @pytest.fixture
    def mock_snapshot_storage(self) -> Mock:
        """Create mock snapshot storage."""
        mock_resource = Mock()
        mock_resource.resource_id = "vpc-baseline"
        mock_resource.resource_type = "AWS::EC2::VPC"
        mock_resource.region = "us-east-1"
        mock_resource.arn = "arn:aws:ec2:us-east-1:123456789012:vpc/vpc-baseline"
        mock_resource.tags = {}

        mock_snapshot = Mock()
        mock_snapshot.name = "baseline-snapshot"
        mock_snapshot.account_id = "123456789012"
        mock_snapshot.regions = ["us-east-1"]
        mock_snapshot.resources = [mock_resource]

        storage = Mock()
        storage.load_snapshot.return_value = mock_snapshot
        return storage

    @pytest.fixture
    def mock_current_resources(self) -> list[dict]:
        """Create mock current resources (baseline + new)."""
        return [
            {
                "resource_id": "vpc-baseline",
                "resource_type": "AWS::EC2::VPC",
                "region": "us-east-1",
                "arn": "arn:aws:ec2:us-east-1:123456789012:vpc/vpc-baseline",
            },
            {
                "resource_id": "i-new-001",
                "resource_type": "AWS::EC2::Instance",
                "region": "us-east-1",
                "arn": "arn:aws:ec2:us-east-1:123456789012:instance/i-new-001",
                "tags": {"Environment": "test"},
            },
        ]

    def test_execute_requires_confirmation(self, mock_snapshot_storage: Mock) -> None:
        """Test execute() requires confirmation flag."""
        cleaner = ResourceCleaner(
            snapshot_storage=mock_snapshot_storage,
            safety_checker=Mock(),
            audit_storage=Mock(),
        )

        with pytest.raises(ValueError, match="confirmation required|confirm"):
            cleaner.execute(
                baseline_snapshot="baseline-snapshot",
                account_id="123456789012",
                confirmed=False,  # Not confirmed!
            )

    @patch("src.restore.cleaner.DeltaCalculator")
    def test_execute_deletes_new_resources(
        self,
        mock_delta_calc_class: Mock,
        mock_snapshot_storage: Mock,
        mock_current_resources: list[dict],
    ) -> None:
        """Test execute() deletes resources created after baseline."""
        # Setup delta calculator mock - only i-new-001 is new
        mock_resource = Mock()
        mock_resource.name = "i-new-001"
        mock_resource.resource_type = "AWS::EC2::Instance"
        mock_resource.region = "us-east-1"
        mock_resource.arn = "arn:aws:ec2:us-east-1:123456789012:instance/i-new-001"
        mock_resource.tags = {"Environment": "test"}

        mock_calc_instance = Mock()
        mock_delta_result = Mock()
        mock_delta_result.added_resources = [mock_resource]
        mock_calc_instance.calculate.return_value = mock_delta_result
        mock_delta_calc_class.return_value = mock_calc_instance

        # Setup safety checker mock
        mock_safety = Mock()
        mock_safety.is_protected.return_value = (False, None)

        # Setup audit storage mock
        mock_audit = Mock()

        cleaner = ResourceCleaner(
            snapshot_storage=mock_snapshot_storage,
            safety_checker=mock_safety,
            audit_storage=mock_audit,
        )

        # Mock AWS deletion
        with patch.object(cleaner, "_collect_current_resources", return_value=mock_current_resources), patch.object(
            cleaner, "_delete_resource", return_value=(True, None)
        ) as mock_delete:
            operation, deletion_records = cleaner.execute(
                baseline_snapshot="baseline-snapshot",
                account_id="123456789012",
                confirmed=True,
            )

        # Verify deletion was attempted
        assert mock_delete.call_count == 1
        assert operation.mode == OperationMode.EXECUTE
        assert operation.status == OperationStatus.COMPLETED
        assert operation.succeeded_count == 1
        assert operation.failed_count == 0

    @patch("src.restore.cleaner.DeltaCalculator")
    def test_execute_skips_protected_resources(
        self,
        mock_delta_calc_class: Mock,
        mock_snapshot_storage: Mock,
        mock_current_resources: list[dict],
    ) -> None:
        """Test execute() skips protected resources."""
        # Setup delta calculator mock
        mock_resource = Mock()
        mock_resource.name = "i-new-001"
        mock_resource.resource_type = "AWS::EC2::Instance"
        mock_resource.region = "us-east-1"
        mock_resource.arn = "arn:aws:ec2:us-east-1:123456789012:instance/i-new-001"
        mock_resource.tags = {"Environment": "test"}

        mock_calc_instance = Mock()
        mock_delta_result = Mock()
        mock_delta_result.added_resources = [mock_resource]
        mock_calc_instance.calculate.return_value = mock_delta_result
        mock_delta_calc_class.return_value = mock_calc_instance

        # Setup safety checker to protect resource
        mock_safety = Mock()
        mock_safety.is_protected.return_value = (True, "Tag Protection=true")

        cleaner = ResourceCleaner(
            snapshot_storage=mock_snapshot_storage,
            safety_checker=mock_safety,
            audit_storage=Mock(),
        )

        # Mock AWS deletion
        with patch.object(cleaner, "_collect_current_resources", return_value=mock_current_resources), patch.object(
            cleaner, "_delete_resource", return_value=(True, None)
        ) as mock_delete:
            operation, deletion_records = cleaner.execute(
                baseline_snapshot="baseline-snapshot",
                account_id="123456789012",
                confirmed=True,
            )

        # Verify deletion was NOT attempted
        assert mock_delete.call_count == 0
        assert operation.succeeded_count == 0
        assert operation.skipped_count == 1

    @patch("src.restore.cleaner.DeltaCalculator")
    def test_execute_handles_deletion_failures(
        self,
        mock_delta_calc_class: Mock,
        mock_snapshot_storage: Mock,
        mock_current_resources: list[dict],
    ) -> None:
        """Test execute() handles AWS deletion failures gracefully."""
        # Setup delta calculator mock
        mock_resource = Mock()
        mock_resource.name = "i-new-001"
        mock_resource.resource_type = "AWS::EC2::Instance"
        mock_resource.region = "us-east-1"
        mock_resource.arn = "arn:aws:ec2:us-east-1:123456789012:instance/i-new-001"
        mock_resource.tags = {"Environment": "test"}

        mock_calc_instance = Mock()
        mock_delta_result = Mock()
        mock_delta_result.added_resources = [mock_resource]
        mock_calc_instance.calculate.return_value = mock_delta_result
        mock_delta_calc_class.return_value = mock_calc_instance

        # Setup safety checker mock
        mock_safety = Mock()
        mock_safety.is_protected.return_value = (False, None)

        cleaner = ResourceCleaner(
            snapshot_storage=mock_snapshot_storage,
            safety_checker=mock_safety,
            audit_storage=Mock(),
        )

        # Mock AWS deletion failure
        with patch.object(cleaner, "_collect_current_resources", return_value=mock_current_resources), patch.object(
            cleaner, "_delete_resource", return_value=(False, "Deletion failed")
        ) as mock_delete:  # Deletion fails
            operation, deletion_records = cleaner.execute(
                baseline_snapshot="baseline-snapshot",
                account_id="123456789012",
                confirmed=True,
            )

        # Verify failure was recorded
        assert mock_delete.call_count == 1
        assert operation.succeeded_count == 0
        assert operation.failed_count == 1
        assert operation.status == OperationStatus.FAILED

    @patch("src.restore.cleaner.DeltaCalculator")
    def test_execute_logs_to_audit_storage(
        self,
        mock_delta_calc_class: Mock,
        mock_snapshot_storage: Mock,
        mock_current_resources: list[dict],
    ) -> None:
        """Test execute() logs operation to audit storage."""
        # Setup delta calculator mock
        mock_resource = Mock()
        mock_resource.name = "i-new-001"
        mock_resource.resource_type = "AWS::EC2::Instance"
        mock_resource.region = "us-east-1"
        mock_resource.arn = "arn:aws:ec2:us-east-1:123456789012:instance/i-new-001"
        mock_resource.tags = {"Environment": "test"}

        mock_calc_instance = Mock()
        mock_delta_result = Mock()
        mock_delta_result.added_resources = [mock_resource]
        mock_calc_instance.calculate.return_value = mock_delta_result
        mock_delta_calc_class.return_value = mock_calc_instance

        # Setup safety checker mock
        mock_safety = Mock()
        mock_safety.is_protected.return_value = (False, None)

        # Setup audit storage mock
        mock_audit = Mock()

        cleaner = ResourceCleaner(
            snapshot_storage=mock_snapshot_storage,
            safety_checker=mock_safety,
            audit_storage=mock_audit,
        )

        # Mock AWS deletion
        with patch.object(cleaner, "_collect_current_resources", return_value=mock_current_resources), patch.object(
            cleaner, "_delete_resource", return_value=(True, None)
        ):
            cleaner.execute(
                baseline_snapshot="baseline-snapshot",
                account_id="123456789012",
                confirmed=True,
            )

        # Verify audit log was called
        assert mock_audit.log_operation.call_count == 1
        logged_operation = mock_audit.log_operation.call_args[0][0]
        assert logged_operation.mode == OperationMode.EXECUTE


class TestResourceCleanerEdgeCases:
    """Test edge cases and error conditions for 100% coverage."""

    @pytest.fixture
    def mock_snapshot_storage(self) -> Mock:
        """Create mock snapshot storage that raises FileNotFoundError."""
        mock_storage = Mock()
        mock_storage.load_snapshot.side_effect = FileNotFoundError("Snapshot not found")
        return mock_storage

    @pytest.fixture
    def mock_safety_checker(self) -> Mock:
        """Create mock safety checker."""
        mock_safety = Mock()
        mock_safety.is_protected.return_value = (False, None)
        return mock_safety

    @pytest.fixture
    def mock_audit_storage(self) -> Mock:
        """Create mock audit storage."""
        return Mock()

    def test_preview_raises_error_when_snapshot_not_found(
        self,
        mock_snapshot_storage: Mock,
        mock_safety_checker: Mock,
        mock_audit_storage: Mock,
    ) -> None:
        """Test preview raises ValueError when snapshot doesn't exist."""
        cleaner = ResourceCleaner(
            snapshot_storage=mock_snapshot_storage,
            safety_checker=mock_safety_checker,
            audit_storage=mock_audit_storage,
        )

        with pytest.raises(ValueError, match="Snapshot 'nonexistent' not found"):
            cleaner.preview(
                baseline_snapshot="nonexistent",
                account_id="123456789012",
            )

    def test_preview_raises_error_on_account_id_mismatch(
        self,
        mock_safety_checker: Mock,
        mock_audit_storage: Mock,
    ) -> None:
        """Test preview raises ValueError when account IDs don't match."""
        # Create mock snapshot with different account ID
        mock_snapshot = Mock()
        mock_snapshot.account_id = "999999999999"  # Different account
        mock_snapshot.regions = ["us-east-1"]

        mock_storage = Mock()
        mock_storage.load_snapshot.return_value = mock_snapshot

        cleaner = ResourceCleaner(
            snapshot_storage=mock_storage,
            safety_checker=mock_safety_checker,
            audit_storage=mock_audit_storage,
        )

        with pytest.raises(ValueError, match="Account ID mismatch"):
            cleaner.preview(
                baseline_snapshot="test-snapshot",
                account_id="123456789012",  # Different from snapshot
            )

    def test_execute_raises_error_when_snapshot_not_found(
        self,
        mock_snapshot_storage: Mock,
        mock_safety_checker: Mock,
        mock_audit_storage: Mock,
    ) -> None:
        """Test execute raises ValueError when snapshot doesn't exist."""
        cleaner = ResourceCleaner(
            snapshot_storage=mock_snapshot_storage,
            safety_checker=mock_safety_checker,
            audit_storage=mock_audit_storage,
        )

        with pytest.raises(ValueError, match="Snapshot 'nonexistent' not found"):
            cleaner.execute(
                baseline_snapshot="nonexistent",
                account_id="123456789012",
                confirmed=True,
            )

    def test_execute_raises_error_on_account_id_mismatch(
        self,
        mock_safety_checker: Mock,
        mock_audit_storage: Mock,
    ) -> None:
        """Test execute raises ValueError when account IDs don't match."""
        # Create mock snapshot with different account ID
        mock_snapshot = Mock()
        mock_snapshot.account_id = "999999999999"  # Different account
        mock_snapshot.regions = ["us-east-1"]

        mock_storage = Mock()
        mock_storage.load_snapshot.return_value = mock_snapshot

        cleaner = ResourceCleaner(
            snapshot_storage=mock_storage,
            safety_checker=mock_safety_checker,
            audit_storage=mock_audit_storage,
        )

        with pytest.raises(ValueError, match="Account ID mismatch"):
            cleaner.execute(
                baseline_snapshot="test-snapshot",
                account_id="123456789012",  # Different from snapshot
                confirmed=True,
            )

    @patch("src.restore.cleaner.DeltaCalculator")
    def test_execute_with_partial_failure_status(
        self,
        mock_delta_calc_class: Mock,
        mock_safety_checker: Mock,
        mock_audit_storage: Mock,
    ) -> None:
        """Test execute returns PARTIAL status when some deletions fail and some succeed."""
        # Setup mocks
        mock_snapshot = Mock()
        mock_snapshot.account_id = "123456789012"
        mock_snapshot.regions = ["us-east-1"]

        mock_storage = Mock()
        mock_storage.load_snapshot.return_value = mock_snapshot

        # Create mock resources that will be added
        resources_to_delete = [
            {
                "resource_id": "i-success",
                "resource_type": "AWS::EC2::Instance",
                "region": "us-east-1",
                "arn": "arn:aws:ec2:us-east-1:123456789012:instance/i-success",
                "tags": {},
            },
            {
                "resource_id": "i-fail",
                "resource_type": "AWS::EC2::Instance",
                "region": "us-east-1",
                "arn": "arn:aws:ec2:us-east-1:123456789012:instance/i-fail",
                "tags": {},
            },
        ]

        # Setup delta calculator
        mock_resource_objects = []
        for res_dict in resources_to_delete:
            mock_res = Mock()
            mock_res.name = res_dict["resource_id"]
            mock_res.resource_type = res_dict["resource_type"]
            mock_res.region = res_dict["region"]
            mock_res.arn = res_dict["arn"]
            mock_res.tags = res_dict["tags"]
            mock_resource_objects.append(mock_res)

        mock_calc_instance = Mock()
        mock_delta_result = Mock()
        mock_delta_result.added_resources = mock_resource_objects
        mock_calc_instance.calculate.return_value = mock_delta_result
        mock_delta_calc_class.return_value = mock_calc_instance

        # Setup safety checker (none protected)
        mock_safety_checker.is_protected.return_value = (False, None)

        cleaner = ResourceCleaner(
            snapshot_storage=mock_storage,
            safety_checker=mock_safety_checker,
            audit_storage=mock_audit_storage,
        )

        # Mock _delete_resource to return success for first, fail for second
        with patch.object(cleaner, "_delete_resource", side_effect=[(True, None), (False, "Deletion failed")]):
            operation, deletion_records = cleaner.execute(
                baseline_snapshot="test-snapshot",
                account_id="123456789012",
                confirmed=True,
            )

        # Should have PARTIAL status (some succeeded, some failed)
        assert operation.status == OperationStatus.PARTIAL
        assert operation.succeeded_count == 1
        assert operation.failed_count == 1

    @patch("src.restore.cleaner.DeltaCalculator")
    def test_delete_resource_logs_warning_on_failure(
        self,
        mock_delta_calc_class: Mock,
        mock_safety_checker: Mock,
        mock_audit_storage: Mock,
    ) -> None:
        """Test _delete_resource logs warning when deletion fails."""
        # Setup mocks
        mock_snapshot = Mock()
        mock_snapshot.account_id = "123456789012"
        mock_snapshot.regions = ["us-east-1"]

        mock_storage = Mock()
        mock_storage.load_snapshot.return_value = mock_snapshot

        # Create mock resource
        resources = [
            {
                "resource_id": "i-fail",
                "resource_type": "AWS::EC2::Instance",
                "region": "us-east-1",
                "arn": "arn:aws:ec2:us-east-1:123456789012:instance/i-fail",
                "tags": {},
            },
        ]

        mock_resource_objects = []
        for res_dict in resources:
            mock_res = Mock()
            mock_res.name = res_dict["resource_id"]
            mock_res.resource_type = res_dict["resource_type"]
            mock_res.region = res_dict["region"]
            mock_res.arn = res_dict["arn"]
            mock_res.tags = res_dict["tags"]
            mock_resource_objects.append(mock_res)

        mock_calc_instance = Mock()
        mock_delta_result = Mock()
        mock_delta_result.added_resources = mock_resource_objects
        mock_calc_instance.calculate.return_value = mock_delta_result
        mock_delta_calc_class.return_value = mock_calc_instance

        mock_safety_checker.is_protected.return_value = (False, None)

        cleaner = ResourceCleaner(
            snapshot_storage=mock_storage,
            safety_checker=mock_safety_checker,
            audit_storage=mock_audit_storage,
        )

        # Mock ResourceDeleter to fail (imported inside _delete_resource)
        with patch("src.restore.deleter.ResourceDeleter") as mock_deleter_class:
            mock_deleter = Mock()
            mock_deleter.delete_resource.return_value = (False, "DependencyViolation")
            mock_deleter_class.return_value = mock_deleter

            with patch("src.restore.cleaner.logger") as mock_logger:
                cleaner.execute(
                    baseline_snapshot="test-snapshot",
                    account_id="123456789012",
                    confirmed=True,
                )

                # Verify warning was logged
                mock_logger.warning.assert_called_once()
                warning_call = mock_logger.warning.call_args[0][0]
                assert "Failed to delete" in warning_call
                assert "AWS::EC2::Instance" in warning_call
                assert "i-fail" in warning_call
