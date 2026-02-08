"""Deprecation warning utility for CLI option transitions."""

from typing import Any, Optional

import typer


def emit_deprecation_warning(
    old_name: str,
    new_name: str,
    since_version: str = "1.4.0",
    remove_in: str = "2.0.0",
) -> None:
    """Emit a deprecation warning to stderr for a renamed CLI option.

    Args:
        old_name: The deprecated option name (e.g., "--regions").
        new_name: The canonical option name (e.g., "--region").
        since_version: Version when the option was deprecated.
        remove_in: Version when the old option will be removed.
    """
    typer.echo(
        f"Warning: {old_name} is deprecated since v{since_version} "
        f"and will be removed in v{remove_in}. Use {new_name} instead.",
        err=True,
    )


def handle_deprecated_option(
    old_value: Any,
    new_value: Any,
    old_name: str,
    new_name: str,
    since: str = "1.4.0",
    remove_in: str = "2.0.0",
) -> Any:
    """Resolve a deprecated option to the canonical value.

    If the old option was provided but the new one was not, emit a
    deprecation warning and return the old value. If both were provided,
    prefer the new value (still warn). If neither was provided, return
    the new_value default.

    Args:
        old_value: Value from the deprecated option.
        new_value: Value from the canonical option.
        old_name: The deprecated option name.
        new_name: The canonical option name.
        since: Version when deprecated.
        remove_in: Version when the old option will be removed.

    Returns:
        The resolved canonical value.
    """
    old_provided = _is_provided(old_value)
    new_provided = _is_provided(new_value)

    if old_provided and not new_provided:
        emit_deprecation_warning(old_name, new_name, since, remove_in)
        return old_value

    if old_provided and new_provided:
        emit_deprecation_warning(old_name, new_name, since, remove_in)
        return new_value

    return new_value


def _is_provided(value: Any) -> bool:
    """Check if a CLI option value was explicitly provided (not a default)."""
    if value is None:
        return False
    if isinstance(value, bool) and value is False:
        return False
    if isinstance(value, (list, tuple)) and len(value) == 0:
        return False
    if isinstance(value, str) and value == "":
        return False
    return True
