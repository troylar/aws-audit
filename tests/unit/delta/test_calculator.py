"""Tests for delta calculator."""

from datetime import datetime, timezone
from unittest.mock import patch

from src.delta.calculator import DeltaCalculator, compare_to_current_state
from src.models.resource import Resource
from src.models.snapshot import Snapshot


def make_resource(
    name="test-resource",
    resource_type="AWS::EC2::Instance",
    region="us-east-1",
    config_hash="hash123",
    raw_config=None,
):
    """Helper to create Resource objects."""
    return Resource(
        name=name,
        resource_type=resource_type,
        arn=f"arn:aws:ec2:{region}:123456789012:instance/{name}",
        region=region,
        config_hash=config_hash,
        tags={},
        raw_config=raw_config,
    )


def make_snapshot(name="test-snapshot", resources=None, regions=None):
    """Helper to create Snapshot objects."""
    return Snapshot(
        name=name,
        created_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        account_id="123456789012",
        regions=regions or ["us-east-1"],
        resources=resources or [],
    )


class TestDeltaCalculatorInit:
    """Tests for DeltaCalculator initialization."""

    def test_init_creates_indexes(self):
        """Test that init creates resource indexes."""
        resource1 = make_resource(name="instance-1")
        resource2 = make_resource(name="instance-2")
        reference = make_snapshot(resources=[resource1])
        current = make_snapshot(resources=[resource2])

        calculator = DeltaCalculator(reference, current)

        assert resource1.arn in calculator.reference_index
        assert resource2.arn in calculator.current_index

    def test_init_stores_snapshots(self):
        """Test that init stores snapshot references."""
        reference = make_snapshot(name="ref")
        current = make_snapshot(name="cur")

        calculator = DeltaCalculator(reference, current)

        assert calculator.reference == reference
        assert calculator.current == current


class TestDeltaCalculatorCalculate:
    """Tests for DeltaCalculator.calculate method."""

    def test_calculate_no_changes(self):
        """Test calculate with identical snapshots."""
        resource = make_resource(name="instance-1")
        reference = make_snapshot(resources=[resource])
        current = make_snapshot(resources=[resource])

        calculator = DeltaCalculator(reference, current)
        report = calculator.calculate()

        assert len(report.added_resources) == 0
        assert len(report.deleted_resources) == 0
        assert len(report.modified_resources) == 0

    def test_calculate_added_resources(self):
        """Test calculate detects added resources."""
        resource1 = make_resource(name="instance-1")
        resource2 = make_resource(name="instance-2")
        reference = make_snapshot(resources=[resource1])
        current = make_snapshot(resources=[resource1, resource2])

        calculator = DeltaCalculator(reference, current)
        report = calculator.calculate()

        assert len(report.added_resources) == 1
        assert report.added_resources[0].name == "instance-2"
        assert len(report.deleted_resources) == 0
        assert len(report.modified_resources) == 0

    def test_calculate_deleted_resources(self):
        """Test calculate detects deleted resources."""
        resource1 = make_resource(name="instance-1")
        resource2 = make_resource(name="instance-2")
        reference = make_snapshot(resources=[resource1, resource2])
        current = make_snapshot(resources=[resource1])

        calculator = DeltaCalculator(reference, current)
        report = calculator.calculate()

        assert len(report.added_resources) == 0
        assert len(report.deleted_resources) == 1
        assert report.deleted_resources[0].name == "instance-2"
        assert len(report.modified_resources) == 0

    def test_calculate_modified_resources(self):
        """Test calculate detects modified resources."""
        resource_old = make_resource(name="instance-1", config_hash="old-hash")
        resource_new = make_resource(name="instance-1", config_hash="new-hash")
        reference = make_snapshot(resources=[resource_old])
        current = make_snapshot(resources=[resource_new])

        calculator = DeltaCalculator(reference, current)
        report = calculator.calculate()

        assert len(report.added_resources) == 0
        assert len(report.deleted_resources) == 0
        assert len(report.modified_resources) == 1
        assert report.modified_resources[0].old_config_hash == "old-hash"
        assert report.modified_resources[0].new_config_hash == "new-hash"

    def test_calculate_multiple_changes(self):
        """Test calculate with multiple change types."""
        # Reference: r1, r2
        # Current: r1 (modified), r3 (new)
        # Result: r2 deleted, r1 modified, r3 added
        r1_old = make_resource(name="instance-1", config_hash="v1")
        r2 = make_resource(name="instance-2", config_hash="v1")
        r1_new = make_resource(name="instance-1", config_hash="v2")
        r3 = make_resource(name="instance-3", config_hash="v1")

        reference = make_snapshot(resources=[r1_old, r2])
        current = make_snapshot(resources=[r1_new, r3])

        calculator = DeltaCalculator(reference, current)
        report = calculator.calculate()

        assert len(report.added_resources) == 1
        assert len(report.deleted_resources) == 1
        assert len(report.modified_resources) == 1

    def test_calculate_with_resource_type_filter(self):
        """Test calculate with resource type filter."""
        ec2_resource = make_resource(name="instance-1", resource_type="AWS::EC2::Instance")
        s3_resource = make_resource(
            name="bucket-1",
            resource_type="AWS::S3::Bucket",
        )
        # Make S3 resource have a different ARN format
        s3_resource.arn = "arn:aws:s3:::bucket-1"

        reference = make_snapshot(resources=[])
        current = make_snapshot(resources=[ec2_resource, s3_resource])

        calculator = DeltaCalculator(reference, current)
        report = calculator.calculate(resource_type_filter=["AWS::EC2::Instance"])

        # Only EC2 should show as added
        assert len(report.added_resources) == 1
        assert report.added_resources[0].resource_type == "AWS::EC2::Instance"

    def test_calculate_with_region_filter(self):
        """Test calculate with region filter."""
        east_resource = make_resource(name="instance-east", region="us-east-1")
        west_resource = make_resource(name="instance-west", region="us-west-2")

        reference = make_snapshot(resources=[])
        current = make_snapshot(resources=[east_resource, west_resource])

        calculator = DeltaCalculator(reference, current)
        report = calculator.calculate(region_filter=["us-east-1"])

        # Only east should show as added
        assert len(report.added_resources) == 1
        assert report.added_resources[0].region == "us-east-1"

    def test_calculate_sets_report_metadata(self):
        """Test that calculate sets correct report metadata."""
        r1 = make_resource(name="instance-1")
        r2 = make_resource(name="instance-2")
        reference = make_snapshot(name="baseline", resources=[r1])
        current = make_snapshot(name="current", resources=[r1, r2])

        calculator = DeltaCalculator(reference, current)
        report = calculator.calculate()

        assert report.baseline_snapshot_name == "baseline"
        assert report.current_snapshot_name == "current"
        assert report.baseline_resource_count == 1
        assert report.current_resource_count == 2
        assert report.generated_at is not None


class TestDeltaCalculatorMatchesFilters:
    """Tests for DeltaCalculator._matches_filters method."""

    def test_matches_no_filters(self):
        """Test matching with no filters."""
        resource = make_resource()
        reference = make_snapshot()
        current = make_snapshot()
        calculator = DeltaCalculator(reference, current)

        result = calculator._matches_filters(resource, None, None)

        assert result is True

    def test_matches_resource_type_filter_pass(self):
        """Test resource type filter that matches."""
        resource = make_resource(resource_type="AWS::EC2::Instance")
        reference = make_snapshot()
        current = make_snapshot()
        calculator = DeltaCalculator(reference, current)

        result = calculator._matches_filters(resource, ["AWS::EC2::Instance", "AWS::S3::Bucket"], None)

        assert result is True

    def test_matches_resource_type_filter_fail(self):
        """Test resource type filter that doesn't match."""
        resource = make_resource(resource_type="AWS::Lambda::Function")
        reference = make_snapshot()
        current = make_snapshot()
        calculator = DeltaCalculator(reference, current)

        result = calculator._matches_filters(resource, ["AWS::EC2::Instance", "AWS::S3::Bucket"], None)

        assert result is False

    def test_matches_region_filter_pass(self):
        """Test region filter that matches."""
        resource = make_resource(region="us-east-1")
        reference = make_snapshot()
        current = make_snapshot()
        calculator = DeltaCalculator(reference, current)

        result = calculator._matches_filters(resource, None, ["us-east-1", "us-west-2"])

        assert result is True

    def test_matches_region_filter_fail(self):
        """Test region filter that doesn't match."""
        resource = make_resource(region="eu-west-1")
        reference = make_snapshot()
        current = make_snapshot()
        calculator = DeltaCalculator(reference, current)

        result = calculator._matches_filters(resource, None, ["us-east-1", "us-west-2"])

        assert result is False

    def test_matches_both_filters_pass(self):
        """Test both filters matching."""
        resource = make_resource(resource_type="AWS::EC2::Instance", region="us-east-1")
        reference = make_snapshot()
        current = make_snapshot()
        calculator = DeltaCalculator(reference, current)

        result = calculator._matches_filters(resource, ["AWS::EC2::Instance"], ["us-east-1"])

        assert result is True

    def test_matches_both_filters_type_fails(self):
        """Test both filters where type fails."""
        resource = make_resource(resource_type="AWS::S3::Bucket", region="us-east-1")
        reference = make_snapshot()
        current = make_snapshot()
        calculator = DeltaCalculator(reference, current)

        result = calculator._matches_filters(resource, ["AWS::EC2::Instance"], ["us-east-1"])

        assert result is False

    def test_matches_both_filters_region_fails(self):
        """Test both filters where region fails."""
        resource = make_resource(resource_type="AWS::EC2::Instance", region="eu-west-1")
        reference = make_snapshot()
        current = make_snapshot()
        calculator = DeltaCalculator(reference, current)

        result = calculator._matches_filters(resource, ["AWS::EC2::Instance"], ["us-east-1"])

        assert result is False


class TestCompareToCurrentState:
    """Tests for compare_to_current_state function."""

    @patch("src.snapshot.capturer.create_snapshot")
    @patch("src.aws.credentials.get_account_id")
    def test_compare_to_current_state(self, mock_get_account_id, mock_create_snapshot):
        """Test compare_to_current_state function."""
        mock_get_account_id.return_value = "123456789012"

        # Create reference and current snapshots
        reference = make_snapshot(name="reference", regions=["us-east-1"])
        current = make_snapshot(name="current", resources=[make_resource()])
        mock_create_snapshot.return_value = current

        report = compare_to_current_state(reference)

        mock_get_account_id.assert_called_once()
        mock_create_snapshot.assert_called_once()
        assert report is not None

    @patch("src.snapshot.capturer.create_snapshot")
    @patch("src.aws.credentials.get_account_id")
    def test_compare_uses_reference_regions(self, mock_get_account_id, mock_create_snapshot):
        """Test that compare uses reference snapshot regions by default."""
        mock_get_account_id.return_value = "123456789012"

        reference = make_snapshot(regions=["us-east-1", "us-west-2"])
        current = make_snapshot(resources=[])
        mock_create_snapshot.return_value = current

        compare_to_current_state(reference)

        call_kwargs = mock_create_snapshot.call_args.kwargs
        assert call_kwargs["regions"] == ["us-east-1", "us-west-2"]

    @patch("src.snapshot.capturer.create_snapshot")
    @patch("src.aws.credentials.get_account_id")
    def test_compare_with_custom_regions(self, mock_get_account_id, mock_create_snapshot):
        """Test compare with custom regions override."""
        mock_get_account_id.return_value = "123456789012"

        reference = make_snapshot(regions=["us-east-1"])
        current = make_snapshot(resources=[])
        mock_create_snapshot.return_value = current

        compare_to_current_state(reference, regions=["eu-west-1"])

        call_kwargs = mock_create_snapshot.call_args.kwargs
        assert call_kwargs["regions"] == ["eu-west-1"]

    @patch("src.snapshot.capturer.create_snapshot")
    @patch("src.aws.credentials.get_account_id")
    def test_compare_with_profile(self, mock_get_account_id, mock_create_snapshot):
        """Test compare with AWS profile."""
        mock_get_account_id.return_value = "123456789012"

        reference = make_snapshot()
        current = make_snapshot(resources=[])
        mock_create_snapshot.return_value = current

        compare_to_current_state(reference, profile_name="my-profile")

        mock_get_account_id.assert_called_once_with("my-profile")
        call_kwargs = mock_create_snapshot.call_args.kwargs
        assert call_kwargs["profile_name"] == "my-profile"
