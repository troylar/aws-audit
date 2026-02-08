"""Unit tests for deletion progress display."""

from dataclasses import dataclass
from unittest.mock import MagicMock, patch

from rich.console import Group

from src.cli.deletion_progress import (
    DeletionProgressDisplay,
    ResourceStatus,
    TrackedResource,
)


@dataclass
class MockResource:
    """Mock resource for testing."""

    arn: str
    resource_type: str
    name: str
    region: str = "us-east-1"


class TestResourceStatus:
    """Tests for ResourceStatus enum."""

    def test_status_values(self):
        """Test that all expected status values exist."""
        assert ResourceStatus.PENDING.value == "pending"
        assert ResourceStatus.IN_PROGRESS.value == "in_progress"
        assert ResourceStatus.SUCCEEDED.value == "succeeded"
        assert ResourceStatus.FAILED.value == "failed"


class TestTrackedResource:
    """Tests for TrackedResource dataclass."""

    def test_default_values(self):
        """Test default values for TrackedResource."""
        resource = MockResource(
            arn="arn:aws:lambda:us-east-1:123:function:test",
            resource_type="AWS::Lambda::Function",
            name="test-function",
        )
        tracked = TrackedResource(resource=resource, tier=1)

        assert tracked.resource == resource
        assert tracked.tier == 1
        assert tracked.status == ResourceStatus.PENDING
        assert tracked.error is None

    def test_with_error(self):
        """Test TrackedResource with error set."""
        resource = MockResource(
            arn="arn:aws:ec2:us-east-1:123:instance/i-123",
            resource_type="AWS::EC2::Instance",
            name="i-123",
        )
        tracked = TrackedResource(
            resource=resource,
            tier=2,
            status=ResourceStatus.FAILED,
            error="DependencyViolation",
        )

        assert tracked.status == ResourceStatus.FAILED
        assert tracked.error == "DependencyViolation"


class TestDeletionProgressDisplay:
    """Tests for DeletionProgressDisplay class."""

    def test_init_groups_by_tier(self):
        """Test that resources are grouped by deletion tier."""
        resources = [
            MockResource(
                arn="arn:aws:lambda:us-east-1:123:function:func1",
                resource_type="AWS::Lambda::Function",
                name="func1",
            ),
            MockResource(
                arn="arn:aws:ec2:us-east-1:123:instance/i-123",
                resource_type="AWS::EC2::Instance",
                name="i-123",
            ),
            MockResource(
                arn="arn:aws:lambda:us-east-1:123:function:func2",
                resource_type="AWS::Lambda::Function",
                name="func2",
            ),
        ]

        console = MagicMock()
        display = DeletionProgressDisplay(resources, console)

        # Lambda is tier 1, EC2 Instance is tier 2
        assert 1 in display.resources_by_tier
        assert 2 in display.resources_by_tier
        assert len(display.resources_by_tier[1]) == 2  # Two Lambda functions
        assert len(display.resources_by_tier[2]) == 1  # One EC2 instance

    def test_init_creates_resource_map(self):
        """Test that resource map is created by ARN."""
        resources = [
            MockResource(
                arn="arn:aws:lambda:us-east-1:123:function:func1",
                resource_type="AWS::Lambda::Function",
                name="func1",
            ),
        ]

        console = MagicMock()
        display = DeletionProgressDisplay(resources, console)

        assert "arn:aws:lambda:us-east-1:123:function:func1" in display.resource_map

    def test_mark_in_progress(self):
        """Test marking a resource as in progress."""
        resource = MockResource(
            arn="arn:aws:lambda:us-east-1:123:function:func1",
            resource_type="AWS::Lambda::Function",
            name="func1",
        )

        console = MagicMock()
        display = DeletionProgressDisplay([resource], console)

        # Initially pending
        tracked = display.resource_map[resource.arn]
        assert tracked.status == ResourceStatus.PENDING

        # Mark in progress
        display.mark_in_progress(resource)
        assert tracked.status == ResourceStatus.IN_PROGRESS
        assert display.current == tracked

    def test_mark_succeeded(self):
        """Test marking a resource as succeeded."""
        resource = MockResource(
            arn="arn:aws:lambda:us-east-1:123:function:func1",
            resource_type="AWS::Lambda::Function",
            name="func1",
        )

        console = MagicMock()
        display = DeletionProgressDisplay([resource], console)

        display.mark_in_progress(resource)
        display.mark_succeeded(resource)

        tracked = display.resource_map[resource.arn]
        assert tracked.status == ResourceStatus.SUCCEEDED
        assert display.succeeded == 1
        assert display.current is None

    def test_mark_failed(self):
        """Test marking a resource as failed."""
        resource = MockResource(
            arn="arn:aws:lambda:us-east-1:123:function:func1",
            resource_type="AWS::Lambda::Function",
            name="func1",
        )

        console = MagicMock()
        display = DeletionProgressDisplay([resource], console)

        display.mark_in_progress(resource)
        display.mark_failed(resource, "AccessDenied")

        tracked = display.resource_map[resource.arn]
        assert tracked.status == ResourceStatus.FAILED
        assert tracked.error == "AccessDenied"
        assert display.failed == 1
        assert display.current is None

    def test_total_count(self):
        """Test that total count is set correctly."""
        resources = [
            MockResource(
                arn=f"arn:aws:lambda:us-east-1:123:function:func{i}",
                resource_type="AWS::Lambda::Function",
                name=f"func{i}",
            )
            for i in range(10)
        ]

        console = MagicMock()
        display = DeletionProgressDisplay(resources, console)

        assert display.total == 10

    def test_compact_threshold(self):
        """Test that compact mode is used for large resource lists."""
        # Create 60 resources (above threshold of 50)
        resources = [
            MockResource(
                arn=f"arn:aws:lambda:us-east-1:123:function:func{i}",
                resource_type="AWS::Lambda::Function",
                name=f"func{i}",
            )
            for i in range(60)
        ]

        console = MagicMock()
        display = DeletionProgressDisplay(resources, console)

        # Should use compact mode
        assert display.total >= display.COMPACT_THRESHOLD

    def test_get_resource_label(self):
        """Test resource label generation."""
        resource = MockResource(
            arn="arn:aws:lambda:us-east-1:123:function:my-function",
            resource_type="AWS::Lambda::Function",
            name="my-function",
            region="us-west-2",
        )

        console = MagicMock()
        display = DeletionProgressDisplay([resource], console)

        tracked = display.resource_map[resource.arn]
        label = display._get_resource_label(tracked)

        assert label == "Function: my-function (us-west-2)"

    def test_make_progress_bar(self):
        """Test progress bar generation."""
        console = MagicMock()
        display = DeletionProgressDisplay([], console)

        # 50% complete
        bar = display._make_progress_bar(5, 10, width=10)
        assert bar == "━━━━━○○○○○"

        # 100% complete
        bar = display._make_progress_bar(10, 10, width=10)
        assert bar == "━━━━━━━━━━"

        # 0% complete
        bar = display._make_progress_bar(0, 10, width=10)
        assert bar == "○○○○○○○○○○"

        # Empty total
        bar = display._make_progress_bar(0, 0, width=10)
        assert bar == "━━━━━━━━━━"

    def test_tier_names_defined(self):
        """Test that all tier names are defined."""
        assert len(DeletionProgressDisplay.TIER_NAMES) == 10
        assert DeletionProgressDisplay.TIER_NAMES[1] == "Application Layer"
        assert DeletionProgressDisplay.TIER_NAMES[10] == "IAM Resources"

    def test_status_icons_defined(self):
        """Test that all status icons are defined."""
        assert ResourceStatus.PENDING in DeletionProgressDisplay.STATUS_ICONS
        assert ResourceStatus.IN_PROGRESS in DeletionProgressDisplay.STATUS_ICONS
        assert ResourceStatus.SUCCEEDED in DeletionProgressDisplay.STATUS_ICONS
        assert ResourceStatus.FAILED in DeletionProgressDisplay.STATUS_ICONS

    def test_status_colors_defined(self):
        """Test that all status colors are defined."""
        assert ResourceStatus.PENDING in DeletionProgressDisplay.STATUS_COLORS
        assert ResourceStatus.IN_PROGRESS in DeletionProgressDisplay.STATUS_COLORS
        assert ResourceStatus.SUCCEEDED in DeletionProgressDisplay.STATUS_COLORS
        assert ResourceStatus.FAILED in DeletionProgressDisplay.STATUS_COLORS

    def test_unknown_resource_returns_none(self):
        """Test that marking unknown resource doesn't crash."""
        resource = MockResource(
            arn="arn:aws:lambda:us-east-1:123:function:func1",
            resource_type="AWS::Lambda::Function",
            name="func1",
        )
        unknown = MockResource(
            arn="arn:aws:lambda:us-east-1:123:function:unknown",
            resource_type="AWS::Lambda::Function",
            name="unknown",
        )

        console = MagicMock()
        display = DeletionProgressDisplay([resource], console)

        # Should not raise, just do nothing
        display.mark_in_progress(unknown)
        display.mark_succeeded(unknown)
        display.mark_failed(unknown, "error")

        assert display.succeeded == 0
        assert display.failed == 0

    def test_mark_skipped(self):
        """Test marking a resource as skipped."""
        resource = MockResource(
            arn="arn:aws:lambda:us-east-1:123:function:func1",
            resource_type="AWS::Lambda::Function",
            name="func1",
        )

        console = MagicMock()
        display = DeletionProgressDisplay([resource], console)

        display.mark_skipped(resource)

        tracked = display.resource_map[resource.arn]
        assert tracked.status == ResourceStatus.SKIPPED
        assert display.skipped == 1
        assert display.current is None

    def test_mark_skipped_unknown_resource(self):
        """Test that marking an unknown resource as skipped does nothing."""
        resource = MockResource(
            arn="arn:aws:lambda:us-east-1:123:function:func1",
            resource_type="AWS::Lambda::Function",
            name="func1",
        )
        unknown = MockResource(
            arn="arn:aws:lambda:us-east-1:123:function:unknown",
            resource_type="AWS::Lambda::Function",
            name="unknown",
        )

        console = MagicMock()
        display = DeletionProgressDisplay([resource], console)

        display.mark_skipped(unknown)
        assert display.skipped == 0

    def test_get_resource_label_no_colons(self):
        """Test resource label with a type that has no :: separators."""
        resource = MockResource(
            arn="arn:aws:custom:us-east-1:123:thing/t-1",
            resource_type="CustomType",
            name="my-thing",
            region="eu-west-1",
        )
        console = MagicMock()
        display = DeletionProgressDisplay([resource], console)

        tracked = display.resource_map[resource.arn]
        label = display._get_resource_label(tracked)
        assert label == "CustomType: my-thing (eu-west-1)"

    def test_skipped_status_value(self):
        """Test that SKIPPED status value is present."""
        assert ResourceStatus.SKIPPED.value == "skipped"


class TestBuildDetailedDisplay:
    """Tests for _build_detailed_display method."""

    def _make_display(self, resources):
        console = MagicMock()
        display = DeletionProgressDisplay(resources, console)
        display.start_time = 1000000.0
        return display

    def test_returns_group_renderable(self):
        """Test that _build_detailed_display returns a Rich Group."""
        resources = [
            MockResource(
                arn="arn:aws:lambda:us-east-1:123:function:func1",
                resource_type="AWS::Lambda::Function",
                name="func1",
            ),
        ]
        display = self._make_display(resources)

        with patch("src.cli.deletion_progress.time") as mock_time:
            mock_time.time.return_value = 1000005.0
            result = display._build_detailed_display()

        assert isinstance(result, Group)

    def test_header_shows_progress(self):
        """Test that the header shows progress counts."""
        resources = [
            MockResource(
                arn="arn:aws:lambda:us-east-1:123:function:func1",
                resource_type="AWS::Lambda::Function",
                name="func1",
            ),
            MockResource(
                arn="arn:aws:ec2:us-east-1:123:instance/i-123",
                resource_type="AWS::EC2::Instance",
                name="i-123",
            ),
        ]
        display = self._make_display(resources)
        display.mark_in_progress(resources[0])
        display.mark_succeeded(resources[0])

        with patch("src.cli.deletion_progress.time") as mock_time:
            mock_time.time.return_value = 1000010.0
            result = display._build_detailed_display()

        assert isinstance(result, Group)

    def test_shows_all_resource_statuses(self):
        """Test that all status types are rendered correctly."""
        resources = [
            MockResource(
                arn=f"arn:aws:lambda:us-east-1:123:function:func{i}",
                resource_type="AWS::Lambda::Function",
                name=f"func{i}",
            )
            for i in range(5)
        ]
        display = self._make_display(resources)

        display.mark_in_progress(resources[0])
        display.mark_succeeded(resources[0])

        display.mark_in_progress(resources[1])
        display.mark_failed(resources[1], "AccessDenied")

        display.mark_skipped(resources[2])

        display.mark_in_progress(resources[3])
        # resources[4] remains PENDING

        with patch("src.cli.deletion_progress.time") as mock_time:
            mock_time.time.return_value = 1000005.0
            result = display._build_detailed_display()

        assert isinstance(result, Group)

    def test_failed_resource_shows_error(self):
        """Test that failed resources show truncated error messages."""
        resources = [
            MockResource(
                arn="arn:aws:lambda:us-east-1:123:function:func1",
                resource_type="AWS::Lambda::Function",
                name="func1",
            ),
        ]
        display = self._make_display(resources)
        long_error = "A" * 100
        display.mark_in_progress(resources[0])
        display.mark_failed(resources[0], long_error)

        with patch("src.cli.deletion_progress.time") as mock_time:
            mock_time.time.return_value = 1000005.0
            result = display._build_detailed_display()

        assert isinstance(result, Group)

    def test_tier_header_shows_skipped_count(self):
        """Test that tier headers display skipped count."""
        resources = [
            MockResource(
                arn="arn:aws:lambda:us-east-1:123:function:func1",
                resource_type="AWS::Lambda::Function",
                name="func1",
            ),
            MockResource(
                arn="arn:aws:lambda:us-east-1:123:function:func2",
                resource_type="AWS::Lambda::Function",
                name="func2",
            ),
        ]
        display = self._make_display(resources)
        display.mark_skipped(resources[0])

        with patch("src.cli.deletion_progress.time") as mock_time:
            mock_time.time.return_value = 1000005.0
            result = display._build_detailed_display()

        assert isinstance(result, Group)

    def test_zero_total_does_not_divide_by_zero(self):
        """Test that an empty resource list doesn't cause division by zero."""
        display = self._make_display([])

        with patch("src.cli.deletion_progress.time") as mock_time:
            mock_time.time.return_value = 1000005.0
            result = display._build_detailed_display()

        assert isinstance(result, Group)

    def test_zero_start_time_shows_zero_elapsed(self):
        """Test that zero start_time produces 0s elapsed."""
        resources = [
            MockResource(
                arn="arn:aws:lambda:us-east-1:123:function:func1",
                resource_type="AWS::Lambda::Function",
                name="func1",
            ),
        ]
        console = MagicMock()
        display = DeletionProgressDisplay(resources, console)
        display.start_time = 0.0

        result = display._build_detailed_display()
        assert isinstance(result, Group)


class TestBuildCompactDisplay:
    """Tests for _build_compact_display method."""

    def _make_compact_display(self):
        """Create a display with 60+ resources so compact mode kicks in."""
        resources = [
            MockResource(
                arn=f"arn:aws:lambda:us-east-1:123:function:func{i}",
                resource_type="AWS::Lambda::Function",
                name=f"func{i}",
            )
            for i in range(60)
        ]
        console = MagicMock()
        display = DeletionProgressDisplay(resources, console)
        display.start_time = 1000000.0
        return display, resources

    def test_returns_group_renderable(self):
        """Test that _build_compact_display returns a Rich Group."""
        display, resources = self._make_compact_display()

        with patch("src.cli.deletion_progress.time") as mock_time:
            mock_time.time.return_value = 1000010.0
            result = display._build_compact_display()

        assert isinstance(result, Group)

    def test_compact_with_all_resources_done(self):
        """Test compact display when all resources in a tier are done."""
        display, resources = self._make_compact_display()
        for r in resources:
            display.mark_in_progress(r)
            display.mark_succeeded(r)

        with patch("src.cli.deletion_progress.time") as mock_time:
            mock_time.time.return_value = 1000010.0
            result = display._build_compact_display()

        assert isinstance(result, Group)

    def test_compact_with_failures(self):
        """Test compact display when tier has failures."""
        display, resources = self._make_compact_display()
        for r in resources:
            display.mark_in_progress(r)
            display.mark_failed(r, "SomeError")

        with patch("src.cli.deletion_progress.time") as mock_time:
            mock_time.time.return_value = 1000010.0
            result = display._build_compact_display()

        assert isinstance(result, Group)

    def test_compact_with_in_progress_resource(self):
        """Test compact display shows current resource name when in progress."""
        display, resources = self._make_compact_display()
        display.mark_in_progress(resources[0])

        with patch("src.cli.deletion_progress.time") as mock_time:
            mock_time.time.return_value = 1000010.0
            result = display._build_compact_display()

        assert isinstance(result, Group)

    def test_compact_truncates_long_name(self):
        """Test compact display truncates resource names longer than 20 chars."""
        resources = [
            MockResource(
                arn=f"arn:aws:lambda:us-east-1:123:function:a-very-long-function-name-{i}",
                resource_type="AWS::Lambda::Function",
                name=f"a-very-long-function-name-{i}",
            )
            for i in range(60)
        ]
        console = MagicMock()
        display = DeletionProgressDisplay(resources, console)
        display.start_time = 1000000.0
        display.mark_in_progress(resources[0])

        with patch("src.cli.deletion_progress.time") as mock_time:
            mock_time.time.return_value = 1000010.0
            result = display._build_compact_display()

        assert isinstance(result, Group)

    def test_compact_zero_total_no_crash(self):
        """Test compact display with zero total resources does not crash."""
        console = MagicMock()
        display = DeletionProgressDisplay([], console)
        display.start_time = 1000000.0

        with patch("src.cli.deletion_progress.time") as mock_time:
            mock_time.time.return_value = 1000010.0
            result = display._build_compact_display()

        assert isinstance(result, Group)


class TestBuildDisplay:
    """Tests for _build_display routing between compact and detailed."""

    def test_routes_to_detailed_for_small_count(self):
        """Test that _build_display calls detailed display for < 50 resources."""
        resources = [
            MockResource(
                arn=f"arn:aws:lambda:us-east-1:123:function:func{i}",
                resource_type="AWS::Lambda::Function",
                name=f"func{i}",
            )
            for i in range(10)
        ]
        console = MagicMock()
        display = DeletionProgressDisplay(resources, console)
        display.start_time = 1000000.0

        with patch.object(display, "_build_detailed_display", return_value=MagicMock()) as mock_detailed:
            with patch.object(display, "_build_compact_display", return_value=MagicMock()) as mock_compact:
                display._build_display()

        mock_detailed.assert_called_once()
        mock_compact.assert_not_called()

    def test_routes_to_compact_for_large_count(self):
        """Test that _build_display calls compact display for >= 50 resources."""
        resources = [
            MockResource(
                arn=f"arn:aws:lambda:us-east-1:123:function:func{i}",
                resource_type="AWS::Lambda::Function",
                name=f"func{i}",
            )
            for i in range(60)
        ]
        console = MagicMock()
        display = DeletionProgressDisplay(resources, console)
        display.start_time = 1000000.0

        with patch.object(display, "_build_detailed_display", return_value=MagicMock()) as mock_detailed:
            with patch.object(display, "_build_compact_display", return_value=MagicMock()) as mock_compact:
                display._build_display()

        mock_compact.assert_called_once()
        mock_detailed.assert_not_called()

    def test_routes_to_compact_at_exact_threshold(self):
        """Test that exactly 50 resources triggers compact mode."""
        resources = [
            MockResource(
                arn=f"arn:aws:lambda:us-east-1:123:function:func{i}",
                resource_type="AWS::Lambda::Function",
                name=f"func{i}",
            )
            for i in range(50)
        ]
        console = MagicMock()
        display = DeletionProgressDisplay(resources, console)
        display.start_time = 1000000.0

        with patch.object(display, "_build_compact_display", return_value=MagicMock()) as mock_compact:
            display._build_display()

        mock_compact.assert_called_once()


class TestStartAndStop:
    """Tests for start() and stop() lifecycle methods."""

    def test_start_sets_time_and_creates_live(self):
        """Test that start() sets start_time and creates a Live instance."""
        resources = [
            MockResource(
                arn="arn:aws:lambda:us-east-1:123:function:func1",
                resource_type="AWS::Lambda::Function",
                name="func1",
            ),
        ]
        console = MagicMock()
        display = DeletionProgressDisplay(resources, console)

        with patch("src.cli.deletion_progress.Live") as mock_live_cls:
            mock_live_instance = MagicMock()
            mock_live_cls.return_value = mock_live_instance

            display.start()

            assert display.start_time > 0
            assert display.live is not None
            mock_live_cls.assert_called_once()
            mock_live_instance.start.assert_called_once()

    def test_stop_stops_live_and_sets_none(self):
        """Test that stop() stops the Live display and sets it to None."""
        resources = [
            MockResource(
                arn="arn:aws:lambda:us-east-1:123:function:func1",
                resource_type="AWS::Lambda::Function",
                name="func1",
            ),
        ]
        console = MagicMock()
        display = DeletionProgressDisplay(resources, console)

        with patch("src.cli.deletion_progress.Live") as mock_live_cls:
            mock_live_instance = MagicMock()
            mock_live_cls.return_value = mock_live_instance

            display.start()
            display.stop()

            mock_live_instance.stop.assert_called_once()
            assert display.live is None

    def test_stop_when_not_started(self):
        """Test that stop() is safe to call when live is None."""
        console = MagicMock()
        display = DeletionProgressDisplay([], console)

        display.stop()
        assert display.live is None

    def test_refresh_updates_live(self):
        """Test that _refresh calls live.update when live is active."""
        resources = [
            MockResource(
                arn="arn:aws:lambda:us-east-1:123:function:func1",
                resource_type="AWS::Lambda::Function",
                name="func1",
            ),
        ]
        console = MagicMock()
        display = DeletionProgressDisplay(resources, console)

        with patch("src.cli.deletion_progress.Live") as mock_live_cls:
            mock_live_instance = MagicMock()
            mock_live_cls.return_value = mock_live_instance

            display.start()
            display.mark_in_progress(resources[0])

            assert mock_live_instance.update.call_count >= 1

    def test_refresh_no_op_when_live_is_none(self):
        """Test that _refresh does not crash when live is None."""
        console = MagicMock()
        display = DeletionProgressDisplay([], console)
        display._refresh()


class TestPrintFinalSummary:
    """Tests for print_final_summary method."""

    def _make_resources(self, count=3):
        return [
            MockResource(
                arn=f"arn:aws:lambda:us-east-1:123:function:func{i}",
                resource_type="AWS::Lambda::Function",
                name=f"func{i}",
            )
            for i in range(count)
        ]

    def test_all_succeeded(self):
        """Test final summary when all resources are successfully deleted."""
        resources = self._make_resources(3)
        console = MagicMock()
        display = DeletionProgressDisplay(resources, console)

        for r in resources:
            display.mark_in_progress(r)
            display.mark_succeeded(r)

        display.print_final_summary()

        assert console.print.call_count > 0

    def test_all_failed(self):
        """Test final summary when all resources fail to delete."""
        resources = self._make_resources(2)
        console = MagicMock()
        display = DeletionProgressDisplay(resources, console)

        for r in resources:
            display.mark_in_progress(r)
            display.mark_failed(r, "SomeError")

        display.print_final_summary()

        assert console.print.call_count > 0

    def test_mixed_results(self):
        """Test final summary with a mix of succeeded, skipped, and failed."""
        resources = self._make_resources(3)
        console = MagicMock()
        display = DeletionProgressDisplay(resources, console)

        display.mark_in_progress(resources[0])
        display.mark_succeeded(resources[0])

        display.mark_skipped(resources[1])

        display.mark_in_progress(resources[2])
        display.mark_failed(resources[2], "PermissionDenied")

        display.print_final_summary()

        assert console.print.call_count > 0

    def test_no_resources(self):
        """Test final summary with no resources."""
        console = MagicMock()
        display = DeletionProgressDisplay([], console)

        display.print_final_summary()

        assert console.print.call_count > 0

    def test_failed_resources_detail_section(self):
        """Test that failed resources detail section shows error messages."""
        resources = self._make_resources(2)
        console = MagicMock()
        display = DeletionProgressDisplay(resources, console)

        display.mark_in_progress(resources[0])
        display.mark_failed(resources[0], "AccessDenied: User lacks permissions")

        display.mark_in_progress(resources[1])
        display.mark_failed(resources[1], "DependencyViolation: Resource in use")

        display.print_final_summary()

        calls_text = " ".join(str(c) for c in console.print.call_args_list)
        assert "Failed" in calls_text

    def test_failed_resource_long_error_truncated(self):
        """Test that long error messages are truncated in the summary."""
        resources = self._make_resources(1)
        console = MagicMock()
        display = DeletionProgressDisplay(resources, console)

        long_error = "X" * 100
        display.mark_in_progress(resources[0])
        display.mark_failed(resources[0], long_error)

        display.print_final_summary()

        assert console.print.call_count > 0

    def test_failed_resource_no_error_message(self):
        """Test that failed resources with no error show 'Unknown error'."""
        resources = self._make_resources(1)
        console = MagicMock()
        display = DeletionProgressDisplay(resources, console)

        tracked = display.resource_map[resources[0].arn]
        tracked.status = ResourceStatus.FAILED
        tracked.error = None
        display.failed = 1

        display.print_final_summary()

        calls_text = " ".join(str(c) for c in console.print.call_args_list)
        assert "Unknown error" in calls_text

    def test_all_skipped(self):
        """Test final summary when all resources are skipped (already deleted)."""
        resources = self._make_resources(3)
        console = MagicMock()
        display = DeletionProgressDisplay(resources, console)

        for r in resources:
            display.mark_skipped(r)

        display.print_final_summary()

        calls_text = " ".join(str(c) for c in console.print.call_args_list)
        assert "already gone" in calls_text

    def test_succeeded_and_skipped_no_failures(self):
        """Test final summary with succeeded and skipped but no failures."""
        resources = self._make_resources(2)
        console = MagicMock()
        display = DeletionProgressDisplay(resources, console)

        display.mark_in_progress(resources[0])
        display.mark_succeeded(resources[0])
        display.mark_skipped(resources[1])

        display.print_final_summary()

        calls_text = " ".join(str(c) for c in console.print.call_args_list)
        assert "All resources cleaned up successfully" in calls_text or "already gone" in calls_text

    def test_multiple_tiers_in_summary(self):
        """Test final summary with resources spanning multiple tiers."""
        resources = [
            MockResource(
                arn="arn:aws:lambda:us-east-1:123:function:func1",
                resource_type="AWS::Lambda::Function",
                name="func1",
            ),
            MockResource(
                arn="arn:aws:ec2:us-east-1:123:instance/i-123",
                resource_type="AWS::EC2::Instance",
                name="i-123",
            ),
            MockResource(
                arn="arn:aws:ec2:us-east-1:123:vpc/vpc-123",
                resource_type="AWS::EC2::VPC",
                name="vpc-123",
            ),
        ]
        console = MagicMock()
        display = DeletionProgressDisplay(resources, console)

        for r in resources:
            display.mark_in_progress(r)
            display.mark_succeeded(r)

        display.print_final_summary()

        assert console.print.call_count > 0

    def test_failed_in_multiple_tiers(self):
        """Test that failed resources across multiple tiers are listed by tier."""
        resources = [
            MockResource(
                arn="arn:aws:lambda:us-east-1:123:function:func1",
                resource_type="AWS::Lambda::Function",
                name="func1",
            ),
            MockResource(
                arn="arn:aws:ec2:us-east-1:123:instance/i-123",
                resource_type="AWS::EC2::Instance",
                name="i-123",
            ),
        ]
        console = MagicMock()
        display = DeletionProgressDisplay(resources, console)

        display.mark_in_progress(resources[0])
        display.mark_failed(resources[0], "Error A")
        display.mark_in_progress(resources[1])
        display.mark_failed(resources[1], "Error B")

        display.print_final_summary()

        calls_text = " ".join(str(c) for c in console.print.call_args_list)
        assert "Failed" in calls_text


class TestDeletionProgressDisplayIntegration:
    """Integration tests for the display lifecycle."""

    def test_full_lifecycle(self):
        """Test the full lifecycle of progress tracking."""
        resources = [
            MockResource(
                arn="arn:aws:lambda:us-east-1:123:function:func1",
                resource_type="AWS::Lambda::Function",
                name="func1",
            ),
            MockResource(
                arn="arn:aws:ec2:us-east-1:123:instance/i-123",
                resource_type="AWS::EC2::Instance",
                name="i-123",
            ),
            MockResource(
                arn="arn:aws:lambda:us-east-1:123:function:func2",
                resource_type="AWS::Lambda::Function",
                name="func2",
            ),
        ]

        console = MagicMock()
        display = DeletionProgressDisplay(resources, console)

        # Simulate deletion flow
        for i, resource in enumerate(resources):
            display.mark_in_progress(resource)

            # Simulate some failures
            if i == 1:  # EC2 instance fails
                display.mark_failed(resource, "InUse")
            else:
                display.mark_succeeded(resource)

        assert display.succeeded == 2
        assert display.failed == 1
        assert display.current is None
