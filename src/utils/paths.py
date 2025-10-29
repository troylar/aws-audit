"""Path resolution utilities for snapshot storage."""

import os
from pathlib import Path
from typing import Optional, Union


def get_snapshot_storage_path(custom_path: Optional[Union[str, Path]] = None) -> Path:
    """Resolve snapshot storage path with precedence: parameter > env var > default.

    Precedence order:
    1. custom_path parameter (if provided)
    2. AWS_INVENTORY_STORAGE_PATH environment variable (if set)
    3. ~/.snapshots (default)

    Args:
        custom_path: Optional custom path override

    Returns:
        Resolved Path object for snapshot storage

    Examples:
        # Use default
        >>> get_snapshot_storage_path()
        Path.home() / '.snapshots'

        # Use environment variable
        >>> os.environ['AWS_INVENTORY_STORAGE_PATH'] = '/data/snapshots'
        >>> get_snapshot_storage_path()
        Path('/data/snapshots')

        # Use parameter (highest priority)
        >>> get_snapshot_storage_path('/custom/path')
        Path('/custom/path')
    """
    # Priority 1: Custom path parameter (but not empty string)
    if custom_path:
        # Handle both str and Path types
        if isinstance(custom_path, str):
            if custom_path.strip():
                return Path(custom_path).expanduser().resolve()
        else:  # Path object
            return custom_path.expanduser().resolve()

    # Priority 2: Environment variable
    env_path = os.getenv("AWS_INVENTORY_STORAGE_PATH")
    if env_path:
        return Path(env_path).expanduser().resolve()

    # Priority 3: Default to ~/.snapshots
    return Path.home() / ".snapshots"
