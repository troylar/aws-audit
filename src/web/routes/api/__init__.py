"""API routes package."""

from fastapi import APIRouter

from . import charts, cleanup, filters, groups, inventories, queries, resources, snapshots, views

router = APIRouter()
router.include_router(snapshots.router, tags=["snapshots"])
router.include_router(resources.router, tags=["resources"])
router.include_router(queries.router, tags=["queries"])
router.include_router(charts.router, tags=["charts"])
router.include_router(cleanup.router, tags=["cleanup"])
router.include_router(filters.router, tags=["filters"])
router.include_router(views.router, tags=["views"])
router.include_router(groups.router, tags=["groups"])
router.include_router(inventories.router, tags=["inventories"])

__all__ = ["router"]
