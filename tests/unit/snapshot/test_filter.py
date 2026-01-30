"""Tests for resource filtering."""

from datetime import datetime, timezone

import pytest

from src.models.resource import Resource
from src.snapshot.filter import ResourceFilter


def make_resource(
    name="test-resource",
    resource_type="AWS::EC2::Instance",
    region="us-east-1",
    tags=None,
    created_at=None,
):
    """Helper to create Resource objects."""
    return Resource(
        name=name,
        resource_type=resource_type,
        arn=f"arn:aws:ec2:{region}:123456789012:instance/{name}",
        region=region,
        config_hash="hash123",
        tags=tags or {},
        created_at=created_at,
    )


class TestResourceFilterInit:
    """Tests for ResourceFilter initialization."""

    def test_init_defaults(self):
        """Test default initialization."""
        filter = ResourceFilter()
        assert filter.before_date is None
        assert filter.after_date is None
        assert filter.include_tags == {}
        assert filter.exclude_tags == {}

    def test_init_with_before_date(self):
        """Test initialization with before_date."""
        date = datetime(2025, 1, 1, tzinfo=timezone.utc)
        filter = ResourceFilter(before_date=date)
        assert filter.before_date == date

    def test_init_with_after_date(self):
        """Test initialization with after_date."""
        date = datetime(2025, 1, 1, tzinfo=timezone.utc)
        filter = ResourceFilter(after_date=date)
        assert filter.after_date == date

    def test_init_with_include_tags(self):
        """Test initialization with include_tags."""
        tags = {"Environment": "prod", "Team": "alpha"}
        filter = ResourceFilter(include_tags=tags)
        assert filter.include_tags == tags

    def test_init_with_exclude_tags(self):
        """Test initialization with exclude_tags."""
        tags = {"Temporary": "true"}
        filter = ResourceFilter(exclude_tags=tags)
        assert filter.exclude_tags == tags

    def test_init_with_required_tags_deprecated(self):
        """Test backward compatibility with required_tags."""
        tags = {"Environment": "prod"}
        filter = ResourceFilter(required_tags=tags)
        assert filter.include_tags == tags
        assert filter.required_tags == tags


class TestResourceFilterApply:
    """Tests for ResourceFilter.apply method."""

    def test_apply_no_filters(self):
        """Test applying with no filters returns all resources."""
        resources = [
            make_resource(name="r1"),
            make_resource(name="r2"),
            make_resource(name="r3"),
        ]
        filter = ResourceFilter()

        result = filter.apply(resources)

        assert len(result) == 3

    def test_apply_empty_list(self):
        """Test applying to empty list."""
        filter = ResourceFilter()
        result = filter.apply([])
        assert result == []

    def test_apply_updates_statistics(self):
        """Test that apply updates statistics."""
        resources = [make_resource(name="r1")]
        filter = ResourceFilter()

        filter.apply(resources)

        assert filter.stats["total_collected"] == 1
        assert filter.stats["final_count"] == 1


class TestResourceFilterDateFiltering:
    """Tests for date-based filtering."""

    def test_before_date_filter_excludes_newer(self):
        """Test before_date excludes resources created after."""
        cutoff = datetime(2025, 1, 15, tzinfo=timezone.utc)
        old_resource = make_resource(name="old", created_at=datetime(2025, 1, 1, tzinfo=timezone.utc))
        new_resource = make_resource(name="new", created_at=datetime(2025, 1, 20, tzinfo=timezone.utc))

        filter = ResourceFilter(before_date=cutoff)
        result = filter.apply([old_resource, new_resource])

        assert len(result) == 1
        assert result[0].name == "old"

    def test_before_date_filter_exclusive(self):
        """Test before_date is exclusive (same date excluded)."""
        cutoff = datetime(2025, 1, 15, tzinfo=timezone.utc)
        exact_resource = make_resource(name="exact", created_at=datetime(2025, 1, 15, tzinfo=timezone.utc))

        filter = ResourceFilter(before_date=cutoff)
        result = filter.apply([exact_resource])

        assert len(result) == 0

    def test_after_date_filter_excludes_older(self):
        """Test after_date excludes resources created before."""
        cutoff = datetime(2025, 1, 15, tzinfo=timezone.utc)
        old_resource = make_resource(name="old", created_at=datetime(2025, 1, 1, tzinfo=timezone.utc))
        new_resource = make_resource(name="new", created_at=datetime(2025, 1, 20, tzinfo=timezone.utc))

        filter = ResourceFilter(after_date=cutoff)
        result = filter.apply([old_resource, new_resource])

        assert len(result) == 1
        assert result[0].name == "new"

    def test_after_date_filter_inclusive(self):
        """Test after_date is inclusive (same date included)."""
        cutoff = datetime(2025, 1, 15, tzinfo=timezone.utc)
        exact_resource = make_resource(name="exact", created_at=datetime(2025, 1, 15, tzinfo=timezone.utc))

        filter = ResourceFilter(after_date=cutoff)
        result = filter.apply([exact_resource])

        assert len(result) == 1

    def test_date_range_filter(self):
        """Test combined before and after date filters."""
        start = datetime(2025, 1, 10, tzinfo=timezone.utc)
        end = datetime(2025, 1, 20, tzinfo=timezone.utc)

        too_early = make_resource(name="early", created_at=datetime(2025, 1, 5, tzinfo=timezone.utc))
        in_range = make_resource(name="inrange", created_at=datetime(2025, 1, 15, tzinfo=timezone.utc))
        too_late = make_resource(name="late", created_at=datetime(2025, 1, 25, tzinfo=timezone.utc))

        filter = ResourceFilter(after_date=start, before_date=end)
        result = filter.apply([too_early, in_range, too_late])

        assert len(result) == 1
        assert result[0].name == "inrange"

    def test_missing_created_at_included_by_default(self):
        """Test resources without created_at are included."""
        resource = make_resource(name="no-date", created_at=None)

        filter = ResourceFilter(before_date=datetime(2025, 1, 15, tzinfo=timezone.utc))
        result = filter.apply([resource])

        assert len(result) == 1
        assert filter.stats["missing_creation_date"] == 1

    def test_naive_datetime_handling(self):
        """Test handling of naive datetime (no timezone)."""
        # Naive datetime for cutoff
        cutoff = datetime(2025, 1, 15)
        resource = make_resource(name="resource", created_at=datetime(2025, 1, 10))  # Naive

        filter = ResourceFilter(before_date=cutoff)
        result = filter.apply([resource])

        # Should still work, treating as UTC
        assert len(result) == 1


class TestResourceFilterTagFiltering:
    """Tests for tag-based filtering."""

    def test_include_tags_filters_by_key_and_value(self):
        """Test include_tags filters by both key and value."""
        matching = make_resource(name="matching", tags={"Environment": "prod", "Team": "alpha"})
        wrong_value = make_resource(name="wrong-value", tags={"Environment": "dev", "Team": "alpha"})
        missing_key = make_resource(name="missing-key", tags={"Team": "alpha"})

        filter = ResourceFilter(include_tags={"Environment": "prod"})
        result = filter.apply([matching, wrong_value, missing_key])

        assert len(result) == 1
        assert result[0].name == "matching"

    def test_include_tags_and_logic(self):
        """Test include_tags uses AND logic (all must match)."""
        all_tags = make_resource(name="all-tags", tags={"Environment": "prod", "Team": "alpha"})
        partial_tags = make_resource(name="partial-tags", tags={"Environment": "prod"})

        filter = ResourceFilter(include_tags={"Environment": "prod", "Team": "alpha"})
        result = filter.apply([all_tags, partial_tags])

        assert len(result) == 1
        assert result[0].name == "all-tags"

    def test_exclude_tags_filters_out_matching(self):
        """Test exclude_tags filters out resources with matching tags."""
        normal = make_resource(name="normal", tags={"Type": "normal"})
        temporary = make_resource(name="temporary", tags={"Temporary": "true"})

        filter = ResourceFilter(exclude_tags={"Temporary": "true"})
        result = filter.apply([normal, temporary])

        assert len(result) == 1
        assert result[0].name == "normal"

    def test_exclude_tags_or_logic(self):
        """Test exclude_tags uses OR logic (any match excludes)."""
        resource1 = make_resource(name="test1", tags={"Skip": "yes"})
        resource2 = make_resource(name="test2", tags={"Ignore": "true"})
        resource3 = make_resource(name="keep", tags={"Type": "normal"})

        filter = ResourceFilter(exclude_tags={"Skip": "yes", "Ignore": "true"})
        result = filter.apply([resource1, resource2, resource3])

        assert len(result) == 1
        assert result[0].name == "keep"

    def test_combined_include_exclude_tags(self):
        """Test combining include and exclude tags."""
        good = make_resource(name="good", tags={"Environment": "prod", "Type": "normal"})
        excluded = make_resource(name="excluded", tags={"Environment": "prod", "Temporary": "true"})
        wrong_env = make_resource(name="wrong-env", tags={"Environment": "dev"})

        filter = ResourceFilter(include_tags={"Environment": "prod"}, exclude_tags={"Temporary": "true"})
        result = filter.apply([good, excluded, wrong_env])

        assert len(result) == 1
        assert result[0].name == "good"


class TestResourceFilterGetFilterSummary:
    """Tests for get_filter_summary method."""

    def test_no_filters_summary(self):
        """Test summary when no filters applied."""
        filter = ResourceFilter()
        summary = filter.get_filter_summary()
        assert "No filters applied" in summary

    def test_before_date_summary(self):
        """Test summary includes before_date."""
        filter = ResourceFilter(before_date=datetime(2025, 1, 15, tzinfo=timezone.utc))
        summary = filter.get_filter_summary()
        assert "created before" in summary
        assert "2025-01-15" in summary

    def test_after_date_summary(self):
        """Test summary includes after_date."""
        filter = ResourceFilter(after_date=datetime(2025, 1, 10, tzinfo=timezone.utc))
        summary = filter.get_filter_summary()
        assert "created on/after" in summary
        assert "2025-01-10" in summary

    def test_include_tags_summary(self):
        """Test summary includes include_tags."""
        filter = ResourceFilter(include_tags={"Environment": "prod"})
        summary = filter.get_filter_summary()
        assert "include tags" in summary
        assert "Environment=prod" in summary

    def test_exclude_tags_summary(self):
        """Test summary includes exclude_tags."""
        filter = ResourceFilter(exclude_tags={"Temporary": "true"})
        summary = filter.get_filter_summary()
        assert "exclude tags" in summary
        assert "Temporary=true" in summary

    def test_combined_filters_summary(self):
        """Test summary with multiple filters."""
        filter = ResourceFilter(
            before_date=datetime(2025, 1, 15, tzinfo=timezone.utc),
            include_tags={"Environment": "prod"},
            exclude_tags={"Temporary": "true"},
        )
        summary = filter.get_filter_summary()
        assert "created before" in summary
        assert "include tags" in summary
        assert "exclude tags" in summary
        assert "AND" in summary


class TestResourceFilterGetStatisticsSummary:
    """Tests for get_statistics_summary method."""

    def test_statistics_returned(self):
        """Test that statistics are returned correctly."""
        resources = [
            make_resource(name="r1", tags={"Environment": "prod"}),
            make_resource(name="r2", tags={"Environment": "dev"}),
        ]
        filter = ResourceFilter(include_tags={"Environment": "prod"})

        filter.apply(resources)
        stats = filter.get_statistics_summary()

        assert stats["total_collected"] == 2
        assert stats["final_count"] == 1
        assert stats["filtered_out_by_tags"] == 1

    def test_statistics_copy_returned(self):
        """Test that a copy of statistics is returned."""
        filter = ResourceFilter()
        filter.apply([make_resource()])

        stats1 = filter.get_statistics_summary()
        stats2 = filter.get_statistics_summary()

        assert stats1 is not stats2
        assert stats1 == stats2
