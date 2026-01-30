"""Unit tests for Groups API endpoints."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.models.group import GroupMember, ResourceGroup
from src.web.routes.api import groups


@pytest.fixture
def mock_group_store():
    """Create a mock GroupStore."""
    return MagicMock()


@pytest.fixture
def client(mock_group_store):
    """Create a test FastAPI app with the groups router and return a test client."""
    app = FastAPI()
    app.include_router(groups.router, prefix="/api")

    # Patch the get_group_store dependency
    with patch.object(groups, "get_group_store", return_value=mock_group_store):
        yield TestClient(app)


class TestListGroups:
    """Test GET /api/groups endpoint."""

    def test_list_empty(self, client, mock_group_store):
        """Test listing groups when none exist."""
        mock_group_store.list_all.return_value = []

        response = client.get("/api/groups")

        assert response.status_code == 200
        data = response.json()
        assert data["groups"] == []
        assert data["count"] == 0

    def test_list_with_groups(self, client, mock_group_store):
        """Test listing groups when some exist."""
        mock_group_store.list_all.return_value = [
            {"name": "group-1", "description": "First", "resource_count": 10},
            {"name": "group-2", "description": "Second", "resource_count": 5},
        ]

        response = client.get("/api/groups")

        assert response.status_code == 200
        data = response.json()
        assert len(data["groups"]) == 2
        assert data["count"] == 2


class TestCreateGroup:
    """Test POST /api/groups endpoint."""

    def test_create_empty_group(self, client, mock_group_store):
        """Test creating an empty group."""
        mock_group_store.exists.return_value = False
        mock_group_store.save.return_value = 1

        response = client.post("/api/groups", json={"name": "new-group", "description": "A new group"})

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "new-group"
        assert data["resource_count"] == 0

    def test_create_duplicate_group(self, client, mock_group_store):
        """Test creating a duplicate group returns error."""
        mock_group_store.exists.return_value = True

        response = client.post("/api/groups", json={"name": "existing"})

        assert response.status_code == 400

    def test_create_group_from_snapshot(self, client, mock_group_store):
        """Test creating a group from a snapshot."""
        mock_group_store.exists.return_value = False
        mock_group_store.create_from_snapshot.return_value = 10

        response = client.post("/api/groups", json={"name": "snap-group", "from_snapshot": "my-snapshot"})

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "snap-group"
        assert data["resource_count"] == 10


class TestGetGroup:
    """Test GET /api/groups/{name} endpoint."""

    def test_get_existing_group(self, client, mock_group_store):
        """Test getting an existing group."""
        mock_group_store.load.return_value = ResourceGroup(
            id=1,
            name="my-group",
            description="Test group",
            source_snapshot="snap-1",
            resource_count=5,
            is_favorite=False,
        )

        response = client.get("/api/groups/my-group")

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "my-group"
        assert data["description"] == "Test group"

    def test_get_nonexistent_group(self, client, mock_group_store):
        """Test getting a non-existent group."""
        mock_group_store.load.return_value = None

        response = client.get("/api/groups/nonexistent")

        assert response.status_code == 404


class TestDeleteGroup:
    """Test DELETE /api/groups/{name} endpoint."""

    def test_delete_existing_group(self, client, mock_group_store):
        """Test deleting an existing group."""
        mock_group_store.delete.return_value = True

        response = client.delete("/api/groups/to-delete")

        assert response.status_code == 200
        mock_group_store.delete.assert_called_once_with("to-delete")

    def test_delete_nonexistent_group(self, client, mock_group_store):
        """Test deleting a non-existent group."""
        mock_group_store.exists.return_value = False

        response = client.delete("/api/groups/nonexistent")

        assert response.status_code == 404


class TestToggleFavorite:
    """Test POST /api/groups/{name}/favorite endpoint."""

    def test_toggle_favorite(self, client, mock_group_store):
        """Test toggling favorite status."""
        mock_group_store.toggle_favorite.return_value = True

        response = client.post("/api/groups/fav-group/favorite")

        assert response.status_code == 200
        data = response.json()
        assert data["is_favorite"] is True

    def test_toggle_favorite_not_found(self, client, mock_group_store):
        """Test toggling favorite on nonexistent group."""
        mock_group_store.toggle_favorite.return_value = None

        response = client.post("/api/groups/nonexistent/favorite")

        assert response.status_code == 404


class TestGetMembers:
    """Test GET /api/groups/{name}/members endpoint."""

    def test_get_members(self, client, mock_group_store):
        """Test getting group members."""
        mock_group_store.exists.return_value = True
        mock_group_store.get_members.return_value = [
            GroupMember(resource_name="r1", resource_type="t1"),
            GroupMember(resource_name="r2", resource_type="t2"),
        ]

        response = client.get("/api/groups/members-group/members")

        assert response.status_code == 200
        data = response.json()
        assert len(data["members"]) == 2
        assert data["count"] == 2


class TestAddMembers:
    """Test POST /api/groups/{name}/members endpoint."""

    def test_add_members_from_arns(self, client, mock_group_store):
        """Test adding members from ARNs."""
        mock_group_store.exists.return_value = True
        mock_group_store.add_members_from_arns.return_value = 2

        response = client.post(
            "/api/groups/add-group/members",
            json={
                "arns": [
                    {"arn": "arn:aws:s3:::bucket-1", "resource_type": "s3:bucket"},
                    {"arn": "arn:aws:s3:::bucket-2", "resource_type": "s3:bucket"},
                ]
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["added"] == 2


class TestRemoveMember:
    """Test DELETE /api/groups/{name}/members endpoint."""

    def test_remove_member(self, client, mock_group_store):
        """Test removing a member."""
        mock_group_store.exists.return_value = True
        mock_group_store.remove_member.return_value = True

        response = client.request(
            "DELETE",
            "/api/groups/remove-group/members",
            params={"resource_name": "to-remove", "resource_type": "s3:bucket"},
        )

        assert response.status_code == 200

    def test_remove_member_not_found_group(self, client, mock_group_store):
        """Test removing member from non-existent group."""
        mock_group_store.exists.return_value = False

        response = client.request(
            "DELETE",
            "/api/groups/nonexistent/members",
            params={"resource_name": "to-remove", "resource_type": "s3:bucket"},
        )

        assert response.status_code == 404

    def test_remove_member_not_in_group(self, client, mock_group_store):
        """Test removing member that doesn't exist in group."""
        mock_group_store.exists.return_value = True
        mock_group_store.remove_member.return_value = False

        response = client.request(
            "DELETE",
            "/api/groups/my-group/members",
            params={"resource_name": "not-there", "resource_type": "s3:bucket"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["removed"] is False


class TestGetMembersValidation:
    """Test GET /api/groups/{name}/members validation."""

    def test_get_members_not_found(self, client, mock_group_store):
        """Test getting members from non-existent group."""
        mock_group_store.exists.return_value = False

        response = client.get("/api/groups/nonexistent/members")

        assert response.status_code == 404

    def test_get_members_limit_exceeded(self, client, mock_group_store):
        """Test that limit > 1000 returns validation error."""
        response = client.get("/api/groups/test-group/members?limit=1001")

        assert response.status_code == 422
        data = response.json()
        assert "limit" in str(data["detail"]).lower()

    def test_get_members_with_pagination(self, client, mock_group_store):
        """Test getting members with pagination parameters."""
        mock_group_store.exists.return_value = True
        mock_group_store.get_members.return_value = []

        response = client.get("/api/groups/test-group/members?limit=50&offset=100")

        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 50
        assert data["offset"] == 100
        mock_group_store.get_members.assert_called_once_with("test-group", limit=50, offset=100)

    def test_get_members_negative_offset(self, client, mock_group_store):
        """Test that negative offset returns validation error."""
        response = client.get("/api/groups/test-group/members?offset=-1")

        assert response.status_code == 422


class TestCompareGroupToSnapshot:
    """Test GET /api/groups/{name}/compare/{snapshot} endpoint."""

    def test_compare_success(self, client, mock_group_store):
        """Test successful comparison."""
        mock_group_store.compare_snapshot.return_value = {
            "group_name": "my-group",
            "snapshot_name": "my-snapshot",
            "total_in_group": 10,
            "total_in_snapshot": 15,
            "matched": 8,
            "missing_from_snapshot": 2,
            "not_in_group": 7,
            "resources": {
                "matched": [],
                "missing_from_snapshot": [],
                "not_in_group": [],
            },
        }

        response = client.get("/api/groups/my-group/compare/my-snapshot")

        assert response.status_code == 200
        data = response.json()
        assert data["group_name"] == "my-group"
        assert data["snapshot_name"] == "my-snapshot"
        assert data["matched"] == 8
        assert data["missing_from_snapshot"] == 2
        assert data["not_in_group"] == 7

    def test_compare_group_not_found(self, client, mock_group_store):
        """Test comparison with non-existent group."""
        mock_group_store.compare_snapshot.side_effect = ValueError("Group 'nonexistent' not found")

        response = client.get("/api/groups/nonexistent/compare/my-snapshot")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_compare_snapshot_not_found(self, client, mock_group_store):
        """Test comparison with non-existent snapshot."""
        mock_group_store.compare_snapshot.side_effect = ValueError("Snapshot 'nonexistent' not found")

        response = client.get("/api/groups/my-group/compare/nonexistent")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestGetResourcesInGroup:
    """Test GET /api/groups/{name}/resources/in endpoint."""

    def test_get_resources_in_group_success(self, client, mock_group_store):
        """Test successfully getting resources in a group."""
        mock_group_store.get_resources_in_group.return_value = [
            {"arn": "arn:aws:s3:::bucket-1", "resource_type": "s3:bucket", "name": "bucket-1", "region": "us-east-1"},
            {"arn": "arn:aws:s3:::bucket-2", "resource_type": "s3:bucket", "name": "bucket-2", "region": "us-west-2"},
        ]

        response = client.get("/api/groups/my-group/resources/in?snapshot=my-snapshot")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2
        assert len(data["resources"]) == 2
        assert data["resources"][0]["name"] == "bucket-1"

    def test_get_resources_in_group_empty(self, client, mock_group_store):
        """Test getting resources when none match."""
        mock_group_store.get_resources_in_group.return_value = []

        response = client.get("/api/groups/my-group/resources/in?snapshot=my-snapshot")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0
        assert data["resources"] == []

    def test_get_resources_in_group_not_found(self, client, mock_group_store):
        """Test with non-existent group."""
        mock_group_store.get_resources_in_group.side_effect = ValueError("Group 'nonexistent' not found")

        response = client.get("/api/groups/nonexistent/resources/in?snapshot=my-snapshot")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_resources_in_group_snapshot_not_found(self, client, mock_group_store):
        """Test with non-existent snapshot."""
        mock_group_store.get_resources_in_group.side_effect = ValueError("Snapshot 'nonexistent' not found")

        response = client.get("/api/groups/my-group/resources/in?snapshot=nonexistent")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_resources_in_group_missing_snapshot_param(self, client, mock_group_store):
        """Test that missing snapshot parameter returns validation error."""
        response = client.get("/api/groups/my-group/resources/in")

        assert response.status_code == 422

    def test_get_resources_in_group_limit_exceeded(self, client, mock_group_store):
        """Test that limit > 1000 returns validation error."""
        response = client.get("/api/groups/my-group/resources/in?snapshot=my-snapshot&limit=1001")

        assert response.status_code == 422

    def test_get_resources_in_group_with_pagination(self, client, mock_group_store):
        """Test pagination parameters are passed correctly."""
        mock_group_store.get_resources_in_group.return_value = []

        response = client.get("/api/groups/my-group/resources/in?snapshot=my-snapshot&limit=50&offset=100")

        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 50
        assert data["offset"] == 100
        mock_group_store.get_resources_in_group.assert_called_once_with("my-group", "my-snapshot", limit=50, offset=100)


class TestGetResourcesNotInGroup:
    """Test GET /api/groups/{name}/resources/not-in endpoint."""

    def test_get_resources_not_in_group_success(self, client, mock_group_store):
        """Test successfully getting resources not in a group."""
        mock_group_store.get_resources_not_in_group.return_value = [
            {
                "arn": "arn:aws:lambda:us-east-1:123456789012:function:func-1",
                "resource_type": "lambda:function",
                "name": "func-1",
                "region": "us-east-1",
            },
            {
                "arn": "arn:aws:lambda:us-east-1:123456789012:function:func-2",
                "resource_type": "lambda:function",
                "name": "func-2",
                "region": "us-east-1",
            },
        ]

        response = client.get("/api/groups/my-group/resources/not-in?snapshot=my-snapshot")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2
        assert len(data["resources"]) == 2
        assert data["resources"][0]["name"] == "func-1"

    def test_get_resources_not_in_group_empty(self, client, mock_group_store):
        """Test when all resources are in the group."""
        mock_group_store.get_resources_not_in_group.return_value = []

        response = client.get("/api/groups/my-group/resources/not-in?snapshot=my-snapshot")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0
        assert data["resources"] == []

    def test_get_resources_not_in_group_not_found(self, client, mock_group_store):
        """Test with non-existent group."""
        mock_group_store.get_resources_not_in_group.side_effect = ValueError("Group 'nonexistent' not found")

        response = client.get("/api/groups/nonexistent/resources/not-in?snapshot=my-snapshot")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_resources_not_in_group_snapshot_not_found(self, client, mock_group_store):
        """Test with non-existent snapshot."""
        mock_group_store.get_resources_not_in_group.side_effect = ValueError("Snapshot 'nonexistent' not found")

        response = client.get("/api/groups/my-group/resources/not-in?snapshot=nonexistent")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_resources_not_in_group_missing_snapshot_param(self, client, mock_group_store):
        """Test that missing snapshot parameter returns validation error."""
        response = client.get("/api/groups/my-group/resources/not-in")

        assert response.status_code == 422

    def test_get_resources_not_in_group_limit_exceeded(self, client, mock_group_store):
        """Test that limit > 1000 returns validation error."""
        response = client.get("/api/groups/my-group/resources/not-in?snapshot=my-snapshot&limit=1001")

        assert response.status_code == 422

    def test_get_resources_not_in_group_with_pagination(self, client, mock_group_store):
        """Test pagination parameters are passed correctly."""
        mock_group_store.get_resources_not_in_group.return_value = []

        response = client.get("/api/groups/my-group/resources/not-in?snapshot=my-snapshot&limit=50&offset=100")

        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 50
        assert data["offset"] == 100
        mock_group_store.get_resources_not_in_group.assert_called_once_with(
            "my-group", "my-snapshot", limit=50, offset=100
        )
