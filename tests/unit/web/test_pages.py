"""Unit tests for web page routes (T020)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

pytest.importorskip("fastapi", reason="Requires 'web' optional dependencies")


class TestDashboard:
    """Tests for GET / dashboard page."""

    def test_dashboard_renders(self, web_client, mock_snapshot_store, mock_resource_store, make_snapshot_obj):
        snap = make_snapshot_obj("snap-1", resource_count=42)
        mock_snapshot_store.list_all.return_value = [snap]
        mock_snapshot_store.get_resource_count.return_value = 42
        mock_snapshot_store.get_active.return_value = snap
        mock_resource_store.get_stats.return_value = [{"type": "ec2:instance", "count": 10}]

        response = web_client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_dashboard_empty_state(self, web_client, mock_snapshot_store, mock_resource_store):
        mock_snapshot_store.list_all.return_value = []
        mock_snapshot_store.get_resource_count.return_value = 0
        mock_snapshot_store.get_active.return_value = None
        mock_resource_store.get_stats.return_value = []

        response = web_client.get("/")
        assert response.status_code == 200


class TestSnapshotsPage:
    """Tests for GET /snapshots page."""

    def test_snapshots_list_renders(self, web_client, mock_snapshot_store, make_snapshot_obj):
        mock_snapshot_store.list_all.return_value = [
            make_snapshot_obj("snap-1"),
            make_snapshot_obj("snap-2"),
        ]
        mock_snapshot_store.get_active.return_value = make_snapshot_obj("snap-1")

        response = web_client.get("/snapshots")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_snapshots_list_empty(self, web_client, mock_snapshot_store):
        mock_snapshot_store.list_all.return_value = []
        mock_snapshot_store.get_active.return_value = None

        response = web_client.get("/snapshots")
        assert response.status_code == 200


class TestSnapshotDetail:
    """Tests for GET /snapshots/{name} page."""

    def test_snapshot_detail_found(self, web_client, mock_snapshot_store, mock_resource_store, make_snapshot_obj):
        mock_snapshot_store.load.return_value = make_snapshot_obj("snap-1")
        mock_resource_store.get_stats.return_value = []

        response = web_client.get("/snapshots/snap-1")
        assert response.status_code == 200

    def test_snapshot_detail_not_found(self, web_client, mock_snapshot_store):
        mock_snapshot_store.load.return_value = None

        response = web_client.get("/snapshots/nonexistent")
        assert response.status_code == 404


class TestResourcesPage:
    """Tests for GET /resources page."""

    def test_resources_list_renders(self, web_client, mock_resource_store, mock_snapshot_store):
        mock_resource_store.get_unique_resource_types.return_value = ["ec2:instance", "s3:bucket"]
        mock_resource_store.get_unique_regions.return_value = ["us-east-1"]
        mock_snapshot_store.list_all.return_value = []

        response = web_client.get("/resources")
        assert response.status_code == 200


class TestDiffPage:
    """Tests for GET /diff page."""

    def test_diff_page_renders(self, web_client, mock_snapshot_store, make_snapshot_obj):
        mock_snapshot_store.list_all.return_value = [
            make_snapshot_obj("snap-1"),
            make_snapshot_obj("snap-2"),
        ]

        response = web_client.get("/diff")
        assert response.status_code == 200


class TestQueriesPage:
    """Tests for GET /queries page."""

    def test_queries_page_renders(self, web_client):
        response = web_client.get("/queries")
        assert response.status_code == 200


class TestCleanupPage:
    """Tests for GET /cleanup page."""

    def test_cleanup_page_renders(self, web_client, mock_snapshot_store, make_snapshot_obj):
        mock_snapshot_store.list_all.return_value = [make_snapshot_obj("snap-1")]

        response = web_client.get("/cleanup")
        assert response.status_code == 200

    def test_cleanup_page_empty(self, web_client, mock_snapshot_store):
        mock_snapshot_store.list_all.return_value = []

        response = web_client.get("/cleanup")
        assert response.status_code == 200


class TestAuditPage:
    """Tests for GET /audit page."""

    def test_audit_page_renders(self, web_client, mock_audit_store):
        mock_audit_store.list_operations.return_value = []

        response = web_client.get("/audit")
        assert response.status_code == 200


class TestGroupsPage:
    """Tests for GET /groups page."""

    def test_groups_page_renders(self, web_client, mock_group_store, mock_snapshot_store):
        mock_group_store.list_all.return_value = []
        mock_snapshot_store.list_all.return_value = []

        response = web_client.get("/groups")
        assert response.status_code == 200
