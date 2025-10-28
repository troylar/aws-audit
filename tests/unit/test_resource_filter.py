"""Unit tests for ResourceFilter."""

import pytest
from datetime import datetime, timezone
from src.snapshot.filter import ResourceFilter
from src.models.resource import Resource


class TestResourceFilter:
    """Test cases for ResourceFilter."""

    def test_filter_creation_no_filters(self):
        """Test creating a filter with no filtering criteria."""
        filter = ResourceFilter()
        assert filter.before_date is None
        assert filter.after_date is None
        assert filter.include_tags == {}
        assert filter.exclude_tags == {}

    def test_filter_creation_with_date_filters(self):
        """Test creating a filter with date filters."""
        before = datetime(2024, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
        after = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

        filter = ResourceFilter(before_date=before, after_date=after)
        assert filter.before_date == before
        assert filter.after_date == after

    def test_filter_creation_with_include_tags(self):
        """Test creating a filter with include tags."""
        filter = ResourceFilter(include_tags={"Environment": "production", "Team": "Alpha"})
        assert filter.include_tags == {"Environment": "production", "Team": "Alpha"}

    def test_filter_creation_with_exclude_tags(self):
        """Test creating a filter with exclude tags."""
        filter = ResourceFilter(exclude_tags={"Status": "archived", "Deprecated": "true"})
        assert filter.exclude_tags == {"Status": "archived", "Deprecated": "true"}

    def test_filter_backward_compatibility_required_tags(self):
        """Test backward compatibility with deprecated required_tags parameter."""
        filter = ResourceFilter(required_tags={"Team": "Beta"})
        assert filter.include_tags == {"Team": "Beta"}
        assert filter.required_tags == {"Team": "Beta"}

    def test_apply_no_filters_returns_all(self):
        """Test that applying no filters returns all resources."""
        resources = [
            Resource(
                arn="arn:aws:s3:::bucket1",
                resource_type="s3:bucket",
                name="bucket1",
                region="us-east-1",
                config_hash="a" * 64,
                raw_config={},
            ),
            Resource(
                arn="arn:aws:s3:::bucket2",
                resource_type="s3:bucket",
                name="bucket2",
                region="us-west-2",
                config_hash="b" * 64,
                raw_config={},
            ),
        ]

        filter = ResourceFilter()
        filtered = filter.apply(resources)

        assert len(filtered) == 2
        assert filter.stats["total_collected"] == 2
        assert filter.stats["final_count"] == 2

    def test_apply_before_date_filter(self):
        """Test applying before date filter."""
        cutoff = datetime(2024, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
        resources = [
            Resource(
                arn="arn:aws:s3:::old-bucket",
                resource_type="s3:bucket",
                name="old-bucket",
                region="us-east-1",
                config_hash="c" * 64,
                raw_config={},
                created_at=datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            ),
            Resource(
                arn="arn:aws:s3:::new-bucket",
                resource_type="s3:bucket",
                name="new-bucket",
                region="us-east-1",
                config_hash="d" * 64,
                raw_config={},
                created_at=datetime(2024, 7, 1, 0, 0, 0, tzinfo=timezone.utc),
            ),
        ]

        filter = ResourceFilter(before_date=cutoff)
        filtered = filter.apply(resources)

        assert len(filtered) == 1
        assert filtered[0].name == "old-bucket"
        assert filter.stats["filtered_out_by_date"] == 1

    def test_apply_after_date_filter(self):
        """Test applying after date filter (inclusive)."""
        cutoff = datetime(2024, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
        resources = [
            Resource(
                arn="arn:aws:s3:::old-bucket",
                resource_type="s3:bucket",
                name="old-bucket",
                region="us-east-1",
                config_hash="e" * 64,
                raw_config={},
                created_at=datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            ),
            Resource(
                arn="arn:aws:s3:::new-bucket",
                resource_type="s3:bucket",
                name="new-bucket",
                region="us-east-1",
                config_hash="f" * 64,
                raw_config={},
                created_at=datetime(2024, 7, 1, 0, 0, 0, tzinfo=timezone.utc),
            ),
            Resource(
                arn="arn:aws:s3:::exact-bucket",
                resource_type="s3:bucket",
                name="exact-bucket",
                region="us-east-1",
                config_hash="g" * 64,
                raw_config={},
                created_at=cutoff,  # Exactly on cutoff date
            ),
        ]

        filter = ResourceFilter(after_date=cutoff)
        filtered = filter.apply(resources)

        assert len(filtered) == 2
        assert any(r.name == "new-bucket" for r in filtered)
        assert any(r.name == "exact-bucket" for r in filtered)
        assert filter.stats["filtered_out_by_date"] == 1

    def test_apply_date_range_filter(self):
        """Test applying both before and after date filters."""
        after = datetime(2024, 3, 1, 0, 0, 0, tzinfo=timezone.utc)
        before = datetime(2024, 9, 1, 0, 0, 0, tzinfo=timezone.utc)

        resources = [
            Resource(
                arn="arn:aws:s3:::too-old",
                resource_type="s3:bucket",
                name="too-old",
                region="us-east-1",
                config_hash="h" * 64,
                raw_config={},
                created_at=datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            ),
            Resource(
                arn="arn:aws:s3:::in-range",
                resource_type="s3:bucket",
                name="in-range",
                region="us-east-1",
                config_hash="i" * 64,
                raw_config={},
                created_at=datetime(2024, 6, 1, 0, 0, 0, tzinfo=timezone.utc),
            ),
            Resource(
                arn="arn:aws:s3:::too-new",
                resource_type="s3:bucket",
                name="too-new",
                region="us-east-1",
                config_hash="j" * 64,
                raw_config={},
                created_at=datetime(2024, 10, 1, 0, 0, 0, tzinfo=timezone.utc),
            ),
        ]

        filter = ResourceFilter(after_date=after, before_date=before)
        filtered = filter.apply(resources)

        assert len(filtered) == 1
        assert filtered[0].name == "in-range"
        assert filter.stats["filtered_out_by_date"] == 2

    def test_apply_include_tags_single_tag(self):
        """Test filtering by single include tag."""
        resources = [
            Resource(
                arn="arn:aws:s3:::prod-bucket",
                resource_type="s3:bucket",
                name="prod-bucket",
                region="us-east-1",
                config_hash="k" * 64,
                raw_config={},
                tags={"Environment": "production"},
            ),
            Resource(
                arn="arn:aws:s3:::dev-bucket",
                resource_type="s3:bucket",
                name="dev-bucket",
                region="us-east-1",
                config_hash="l" * 64,
                raw_config={},
                tags={"Environment": "development"},
            ),
        ]

        filter = ResourceFilter(include_tags={"Environment": "production"})
        filtered = filter.apply(resources)

        assert len(filtered) == 1
        assert filtered[0].name == "prod-bucket"
        assert filter.stats["filtered_out_by_tags"] == 1

    def test_apply_include_tags_multiple_tags_and_logic(self):
        """Test filtering by multiple include tags (AND logic)."""
        resources = [
            Resource(
                arn="arn:aws:s3:::full-match",
                resource_type="s3:bucket",
                name="full-match",
                region="us-east-1",
                config_hash="m" * 64,
                raw_config={},
                tags={"Environment": "production", "Team": "Alpha"},
            ),
            Resource(
                arn="arn:aws:s3:::partial-match",
                resource_type="s3:bucket",
                name="partial-match",
                region="us-east-1",
                config_hash="n" * 64,
                raw_config={},
                tags={"Environment": "production"},  # Missing Team tag
            ),
            Resource(
                arn="arn:aws:s3:::no-match",
                resource_type="s3:bucket",
                name="no-match",
                region="us-east-1",
                config_hash="o" * 64,
                raw_config={},
                tags={"Team": "Beta"},
            ),
        ]

        filter = ResourceFilter(include_tags={"Environment": "production", "Team": "Alpha"})
        filtered = filter.apply(resources)

        assert len(filtered) == 1
        assert filtered[0].name == "full-match"
        assert filter.stats["filtered_out_by_tags"] == 2

    def test_apply_exclude_tags_single_tag(self):
        """Test filtering with single exclude tag."""
        resources = [
            Resource(
                arn="arn:aws:s3:::archived",
                resource_type="s3:bucket",
                name="archived",
                region="us-east-1",
                config_hash="p" * 64,
                raw_config={},
                tags={"Status": "archived"},
            ),
            Resource(
                arn="arn:aws:s3:::active",
                resource_type="s3:bucket",
                name="active",
                region="us-east-1",
                config_hash="q" * 64,
                raw_config={},
                tags={"Status": "active"},
            ),
        ]

        filter = ResourceFilter(exclude_tags={"Status": "archived"})
        filtered = filter.apply(resources)

        assert len(filtered) == 1
        assert filtered[0].name == "active"
        assert filter.stats["filtered_out_by_exclude_tags"] == 1

    def test_apply_exclude_tags_multiple_tags_or_logic(self):
        """Test filtering with multiple exclude tags (OR logic)."""
        resources = [
            Resource(
                arn="arn:aws:s3:::archived",
                resource_type="s3:bucket",
                name="archived",
                region="us-east-1",
                config_hash="r" * 64,
                raw_config={},
                tags={"Status": "archived"},
            ),
            Resource(
                arn="arn:aws:s3:::deprecated",
                resource_type="s3:bucket",
                name="deprecated",
                region="us-east-1",
                config_hash="s" * 64,
                raw_config={},
                tags={"Deprecated": "true"},
            ),
            Resource(
                arn="arn:aws:s3:::active",
                resource_type="s3:bucket",
                name="active",
                region="us-east-1",
                config_hash="t" * 64,
                raw_config={},
                tags={"Status": "active"},
            ),
        ]

        filter = ResourceFilter(exclude_tags={"Status": "archived", "Deprecated": "true"})
        filtered = filter.apply(resources)

        assert len(filtered) == 1
        assert filtered[0].name == "active"
        assert filter.stats["filtered_out_by_exclude_tags"] == 2

    def test_apply_combined_include_and_exclude_tags(self):
        """Test filtering with both include and exclude tags."""
        resources = [
            Resource(
                arn="arn:aws:s3:::prod-active",
                resource_type="s3:bucket",
                name="prod-active",
                region="us-east-1",
                config_hash="u" * 64,
                raw_config={},
                tags={"Environment": "production", "Status": "active"},
            ),
            Resource(
                arn="arn:aws:s3:::prod-archived",
                resource_type="s3:bucket",
                name="prod-archived",
                region="us-east-1",
                config_hash="v" * 64,
                raw_config={},
                tags={"Environment": "production", "Status": "archived"},
            ),
            Resource(
                arn="arn:aws:s3:::dev-active",
                resource_type="s3:bucket",
                name="dev-active",
                region="us-east-1",
                config_hash="w" * 64,
                raw_config={},
                tags={"Environment": "development", "Status": "active"},
            ),
        ]

        filter = ResourceFilter(
            include_tags={"Environment": "production"}, exclude_tags={"Status": "archived"}
        )
        filtered = filter.apply(resources)

        assert len(filtered) == 1
        assert filtered[0].name == "prod-active"

    def test_apply_resource_without_created_at_included(self):
        """Test that resources without created_at are included when date filters present."""
        cutoff = datetime(2024, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
        resources = [
            Resource(
                arn="arn:aws:s3:::no-date",
                resource_type="s3:bucket",
                name="no-date",
                region="us-east-1",
                config_hash="x" * 64,
                raw_config={},
                created_at=None,
            ),
            Resource(
                arn="arn:aws:s3:::with-date",
                resource_type="s3:bucket",
                name="with-date",
                region="us-east-1",
                config_hash="y" * 64,
                raw_config={},
                created_at=datetime(2024, 7, 1, 0, 0, 0, tzinfo=timezone.utc),
            ),
        ]

        filter = ResourceFilter(before_date=cutoff)
        filtered = filter.apply(resources)

        # Resource without created_at should be included by default
        assert len(filtered) == 1
        assert filtered[0].name == "no-date"
        assert filter.stats["missing_creation_date"] == 1

    def test_get_filter_summary_no_filters(self):
        """Test filter summary with no filters."""
        filter = ResourceFilter()
        summary = filter.get_filter_summary()
        assert summary == "No filters applied"

    def test_get_filter_summary_with_date_filters(self):
        """Test filter summary with date filters."""
        before = datetime(2024, 12, 31, tzinfo=timezone.utc)
        after = datetime(2024, 1, 1, tzinfo=timezone.utc)

        filter = ResourceFilter(before_date=before, after_date=after)
        summary = filter.get_filter_summary()

        assert "created before 2024-12-31" in summary
        assert "created on/after 2024-01-01" in summary

    def test_get_filter_summary_with_tag_filters(self):
        """Test filter summary with tag filters."""
        filter = ResourceFilter(
            include_tags={"Environment": "production", "Team": "Alpha"},
            exclude_tags={"Status": "archived"},
        )
        summary = filter.get_filter_summary()

        assert "include tags:" in summary
        assert "Environment=production" in summary
        assert "Team=Alpha" in summary
        assert "exclude tags:" in summary
        assert "Status=archived" in summary

    def test_get_statistics_summary(self):
        """Test getting filtering statistics."""
        resources = [
            Resource(
                arn="arn:aws:s3:::bucket1",
                resource_type="s3:bucket",
                name="bucket1",
                region="us-east-1",
                config_hash="z" * 64,
                raw_config={},
                tags={"Environment": "production"},
            ),
            Resource(
                arn="arn:aws:s3:::bucket2",
                resource_type="s3:bucket",
                name="bucket2",
                region="us-east-1",
                config_hash="0" * 64,
                raw_config={},
                tags={"Environment": "development"},
            ),
        ]

        filter = ResourceFilter(include_tags={"Environment": "production"})
        filtered = filter.apply(resources)

        stats = filter.get_statistics_summary()
        assert stats["total_collected"] == 2
        assert stats["final_count"] == 1
        assert stats["date_matched"] == 2
        assert stats["tag_matched"] == 1
        assert stats["filtered_out_by_tags"] == 1

    def test_apply_empty_resource_list(self):
        """Test applying filters to empty resource list."""
        filter = ResourceFilter(include_tags={"Environment": "production"})
        filtered = filter.apply([])

        assert len(filtered) == 0
        assert filter.stats["total_collected"] == 0
        assert filter.stats["final_count"] == 0
