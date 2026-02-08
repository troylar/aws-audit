"""Shared test fixtures for web module tests."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("fastapi", reason="Requires 'web' optional dependencies")

from fastapi.testclient import TestClient

from src.web.app import create_app


def _make_snapshot_obj(name: str = "snap-1", resource_count: int = 10, **kwargs):
    """Create a mock snapshot object with expected attributes."""
    snap = MagicMock()
    snap.name = name
    snap.resource_count = resource_count
    snap.created_at = "2024-01-01T00:00:00+00:00"
    snap.regions = ["us-east-1"]
    snap.service_counts = {"ec2": 5}
    snap.resources = []
    for k, v in kwargs.items():
        setattr(snap, k, v)
    return snap


@pytest.fixture
def make_snapshot_obj():
    """Factory fixture to create snapshot objects."""
    return _make_snapshot_obj


@pytest.fixture
def mock_snapshot_store():
    """Mock SnapshotStore for web tests."""
    store = MagicMock()
    store.list_all.return_value = []
    store.get_resource_count.return_value = 0
    store.get_active.return_value = None
    store.load.return_value = None
    return store


@pytest.fixture
def mock_resource_store():
    """Mock ResourceStore for web tests."""
    store = MagicMock()
    store.get_stats.return_value = []
    store.get_unique_resource_types.return_value = []
    store.get_unique_regions.return_value = []
    store.search.return_value = []
    store.count.return_value = 0
    return store


@pytest.fixture
def mock_collection_store():
    """Mock CollectionStore for web tests."""
    store = MagicMock()
    store.list_all.return_value = []
    return store


@pytest.fixture
def mock_audit_store():
    """Mock AuditStore for web tests."""
    store = MagicMock()
    store.list_operations.return_value = []
    return store


@pytest.fixture
def mock_group_store():
    """Mock GroupStore for web tests."""
    store = MagicMock()
    store.list_all.return_value = []
    return store


@pytest.fixture
def web_client(mock_snapshot_store, mock_resource_store, mock_collection_store, mock_audit_store, mock_group_store):
    """Create a test client with all stores mocked."""
    with (
        patch("src.web.dependencies.init_database"),
        patch("src.web.routes.pages.get_snapshot_store", return_value=mock_snapshot_store),
        patch("src.web.routes.pages.get_resource_store", return_value=mock_resource_store),
        patch("src.web.routes.pages.get_audit_store", return_value=mock_audit_store),
        patch("src.web.routes.pages.get_group_store", return_value=mock_group_store),
        patch("src.web.dependencies.get_snapshot_store", return_value=mock_snapshot_store),
        patch("src.web.dependencies.get_resource_store", return_value=mock_resource_store),
        patch("src.web.dependencies.get_collection_store", return_value=mock_collection_store),
        patch("src.web.dependencies.get_audit_store", return_value=mock_audit_store),
        patch("src.web.dependencies.get_group_store", return_value=mock_group_store),
    ):
        app = create_app(storage_path="/tmp/test-storage")
        yield TestClient(app)
