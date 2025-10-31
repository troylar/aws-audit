"""
Unit tests for pagination utilities.

Tests for paginate_resources() and related pagination helpers.
"""

from __future__ import annotations

from src.utils.pagination import paginate_resources


class TestPaginateResources:
    """Tests for paginate_resources() function."""

    def test_paginate_basic(self):
        """Test basic pagination with multiple pages."""
        items = list(range(250))  # 250 items
        pages = list(paginate_resources(items, page_size=100))

        assert len(pages) == 3
        assert len(pages[0]) == 100
        assert len(pages[1]) == 100
        assert len(pages[2]) == 50

    def test_paginate_exact_boundary(self):
        """Test pagination with exact page boundary."""
        items = list(range(200))  # Exactly 2 pages of 100
        pages = list(paginate_resources(items, page_size=100))

        assert len(pages) == 2
        assert len(pages[0]) == 100
        assert len(pages[1]) == 100

    def test_paginate_single_item(self):
        """Test pagination with single resource."""
        items = ["single-item"]
        pages = list(paginate_resources(items, page_size=100))

        assert len(pages) == 1
        assert len(pages[0]) == 1
        assert pages[0][0] == "single-item"

    def test_paginate_empty_list(self):
        """Test pagination with empty list."""
        items = []
        pages = list(paginate_resources(items, page_size=100))

        assert len(pages) == 0

    def test_paginate_custom_page_size(self):
        """Test pagination with custom page size."""
        items = list(range(150))
        pages = list(paginate_resources(items, page_size=50))

        assert len(pages) == 3
        assert all(len(page) == 50 for page in pages[:2])
        assert len(pages[2]) == 50

    def test_paginate_generator_pattern(self):
        """Test that paginate_resources returns generator (memory efficient)."""
        items = list(range(1000))
        result = paginate_resources(items, page_size=100)

        # Should be a generator
        assert hasattr(result, "__iter__")
        assert hasattr(result, "__next__")

        # Can iterate
        first_page = next(result)
        assert len(first_page) == 100
        assert first_page[0] == 0

    def test_paginate_preserves_order(self):
        """Test that pagination preserves item order."""
        items = ["a", "b", "c", "d", "e", "f"]
        pages = list(paginate_resources(items, page_size=2))

        assert pages[0] == ["a", "b"]
        assert pages[1] == ["c", "d"]
        assert pages[2] == ["e", "f"]


class TestPaginationEdgeCases:
    """Tests for pagination edge cases."""

    def test_paginate_very_large_page_size(self):
        """Test pagination with page size larger than dataset."""
        items = list(range(50))
        pages = list(paginate_resources(items, page_size=1000))

        assert len(pages) == 1
        assert len(pages[0]) == 50

    def test_paginate_page_size_one(self):
        """Test pagination with page size of 1."""
        items = ["a", "b", "c"]
        pages = list(paginate_resources(items, page_size=1))

        assert len(pages) == 3
        assert all(len(page) == 1 for page in pages)
