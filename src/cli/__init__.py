"""CLI module for AWS Baseline Snapshot tool."""

__all__ = ["app", "cli_main"]


def __getattr__(name: str):
    """Lazy import to avoid RuntimeWarning when running with python -m."""
    if name in ("app", "cli_main"):
        from .main import app, cli_main

        return app if name == "app" else cli_main
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
