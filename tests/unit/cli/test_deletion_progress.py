"""Unit tests for deletion progress display."""

import pytest
from dataclasses import dataclass
from typing import Optional
from unittest.mock import MagicMock, patch

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
