"""Progress indicator utilities using Rich library."""

from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
    TimeRemainingColumn,
    TaskID,
)
from typing import Optional
from contextlib import contextmanager


@contextmanager
def create_progress():
    """Create a Rich progress context for tracking operations.

    Yields:
        Progress instance configured for multi-task tracking
    """
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
    ) as progress:
        yield progress


def create_spinner_progress():
    """Create a simple spinner progress for indeterminate operations.

    Returns:
        Progress instance with spinner
    """
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
    )
