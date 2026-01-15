"""Dependency injection for FastAPI routes."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..storage import AuditStore, Database, GroupStore, InventoryStore, ResourceStore, SnapshotStore

# Global instances (initialized at startup)
_db: Optional[Database] = None
_storage_path: Optional[str] = None


def init_database(storage_path: Optional[str] = None) -> None:
    """Initialize the database connection.

    Args:
        storage_path: Optional path to storage directory.
                     If not provided, uses default from Config.
    """
    global _db, _storage_path
    _storage_path = storage_path

    if storage_path:
        db_path = Path(storage_path) / "inventory.db"
        _db = Database(db_path=db_path)
    else:
        _db = Database()

    _db.ensure_schema()


def get_database() -> Database:
    """Get the database instance."""
    global _db
    if _db is None:
        init_database(_storage_path)
    return _db  # type: ignore


def get_snapshot_store() -> SnapshotStore:
    """Get a SnapshotStore instance."""
    return SnapshotStore(get_database())


def get_resource_store() -> ResourceStore:
    """Get a ResourceStore instance."""
    return ResourceStore(get_database())


def get_inventory_store() -> InventoryStore:
    """Get an InventoryStore instance."""
    return InventoryStore(get_database())


def get_audit_store() -> AuditStore:
    """Get an AuditStore instance."""
    return AuditStore(get_database())


def get_group_store() -> GroupStore:
    """Get a GroupStore instance."""
    return GroupStore(get_database())


def get_storage_path() -> Optional[str]:
    """Get the configured storage path."""
    return _storage_path
