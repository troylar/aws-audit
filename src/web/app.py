"""FastAPI application factory for AWS Inventory Browser."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .dependencies import init_database

# Get the directory where this module is located
MODULE_DIR = Path(__file__).parent
TEMPLATES_DIR = MODULE_DIR / "templates"
STATIC_DIR = MODULE_DIR / "static"


def get_templates() -> Jinja2Templates:
    """Get configured Jinja2Templates instance."""
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

    # Add custom filters
    def format_number(value: int) -> str:
        """Format number with commas."""
        return f"{value:,}"

    def truncate_arn(arn: str, max_length: int = 50) -> str:
        """Truncate ARN for display."""
        if len(arn) <= max_length:
            return arn
        return arn[: max_length - 3] + "..."

    def service_from_type(resource_type: str) -> str:
        """Extract service name from resource type."""
        if ":" in resource_type:
            return resource_type.split(":")[0]
        return resource_type

    templates.env.filters["format_number"] = format_number
    templates.env.filters["truncate_arn"] = truncate_arn
    templates.env.filters["service"] = service_from_type

    return templates


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    # Startup: Initialize database
    storage_path = getattr(app.state, "storage_path", None)
    init_database(storage_path)
    yield
    # Shutdown: Nothing to clean up


def create_app(storage_path: Optional[str] = None) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        storage_path: Optional path to storage directory.
                     If not provided, uses default from Config.

    Returns:
        Configured FastAPI application instance.
    """
    app = FastAPI(
        title="AWS Inventory Browser",
        description="Browse and analyze AWS resource inventory",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Store config for lifespan access
    app.state.storage_path = storage_path

    # Mount static files if directory exists
    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    # Get templates
    templates = get_templates()

    # Include API routes
    from .routes.api import router as api_router

    app.include_router(api_router, prefix="/api")

    # Include page routes
    from .routes import pages

    app.include_router(pages.router)

    # Add templates to app state for access in routes
    app.state.templates = templates

    return app
