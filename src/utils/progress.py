"""Progress indicator utilities using Rich library."""

from contextlib import contextmanager

from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)


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
