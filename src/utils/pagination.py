"""
Terminal pagination utilities for large resource lists.

This module provides pagination functionality for displaying large datasets
in the terminal with user-friendly navigation controls.
"""

from __future__ import annotations

from typing import Generator, List, TypeVar

T = TypeVar("T")


def paginate_resources(items: List[T], page_size: int = 100) -> Generator[List[T], None, None]:
    """
    Paginate a list of items into pages of specified size.

    This is a memory-efficient generator that yields pages of items
    without loading everything into memory at once.

    Args:
        items: List of items to paginate
        page_size: Number of items per page (default: 100)

    Yields:
        Lists of items, each containing up to page_size items

    Example:
        >>> resources = list(range(250))
        >>> for page in paginate_resources(resources, page_size=100):
        ...     print(f"Page has {len(page)} items")
        Page has 100 items
        Page has 100 items
        Page has 50 items
    """
    if not items:
        return

    for i in range(0, len(items), page_size):
        yield items[i : i + page_size]
