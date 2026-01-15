"""Unit tests for GroupStore."""

from __future__ import annotations

import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from src.models import Resource, Snapshot
from src.models.group import GroupMember, ResourceGroup, extract_resource_name
from src.storage import Database, GroupStore, SnapshotStore


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db = Database(db_path=db_path)
        db.ensure_schema()
        yield db


@pytest.fixture
def group_store(temp_db):
    """Create a GroupStore instance with temp database."""
    return GroupStore(temp_db)


@pytest.fixture
def snapshot_store(temp_db):
    """Create a SnapshotStore instance with temp database."""
    return SnapshotStore(temp_db)


class TestGroupStoreBasicCRUD:
    """Test basic CRUD operations for GroupStore."""

    def test_save_new_group(self, group_store):
        """Test creating a new group."""
        group = ResourceGroup(
            name="test-group",
            description="A test group",
            source_snapshot="test-snapshot"
        )

        group_id = group_store.save(group)

        assert group_id > 0

    def test_save_group_with_members(self, group_store):
        """Test saving a group with members."""
        members = [
            GroupMember(resource_name="bucket-1", resource_type="s3:bucket"),
            GroupMember(resource_name="bucket-2", resource_type="s3:bucket"),
        ]
        group = ResourceGroup(
            name="test-group",
            description="A test group",
            members=members
        )

        group_id = group_store.save(group)
        loaded = group_store.load("test-group")

        assert loaded is not None
        assert len(loaded.members) == 2
        assert loaded.resource_count == 2

    def test_load_existing_group(self, group_store):
        """Test loading an existing group."""
        group = ResourceGroup(
            name="my-group",
            description="My test group",
            source_snapshot="snap-1"
        )
        group_store.save(group)

        loaded = group_store.load("my-group")

        assert loaded is not None
        assert loaded.name == "my-group"
        assert loaded.description == "My test group"
        assert loaded.source_snapshot == "snap-1"

    def test_load_nonexistent_group(self, group_store):
        """Test loading a group that doesn't exist."""
        loaded = group_store.load("nonexistent")

        assert loaded is None

    def test_exists_true(self, group_store):
        """Test exists returns True for existing group."""
        group = ResourceGroup(name="exists-group")
        group_store.save(group)

        assert group_store.exists("exists-group") is True

    def test_exists_false(self, group_store):
        """Test exists returns False for non-existing group."""
        assert group_store.exists("not-exists") is False

    def test_delete_group(self, group_store):
        """Test deleting a group."""
        group = ResourceGroup(name="to-delete")
        group_store.save(group)

        result = group_store.delete("to-delete")

        assert result is True
        assert group_store.exists("to-delete") is False

    def test_delete_nonexistent_group(self, group_store):
        """Test deleting a non-existent group."""
        result = group_store.delete("nonexistent")

        assert result is False

    def test_list_all_groups(self, group_store):
        """Test listing all groups."""
        group_store.save(ResourceGroup(name="group-a", description="First"))
        group_store.save(ResourceGroup(name="group-b", description="Second"))
        group_store.save(ResourceGroup(name="group-c", description="Third"))

        groups = group_store.list_all()

        assert len(groups) == 3
        names = [g["name"] for g in groups]
        assert "group-a" in names
        assert "group-b" in names
        assert "group-c" in names

    def test_list_all_empty(self, group_store):
        """Test listing groups when none exist."""
        groups = group_store.list_all()

        assert groups == []


class TestGroupStoreFavorites:
    """Test favorite functionality."""

    def test_toggle_favorite_on(self, group_store):
        """Test toggling favorite on."""
        group_store.save(ResourceGroup(name="fav-group"))

        group_store.toggle_favorite("fav-group")
        loaded = group_store.load("fav-group")

        assert loaded.is_favorite is True

    def test_toggle_favorite_off(self, group_store):
        """Test toggling favorite off."""
        group = ResourceGroup(name="fav-group", is_favorite=True)
        group_store.save(group)

        group_store.toggle_favorite("fav-group")
        loaded = group_store.load("fav-group")

        assert loaded.is_favorite is False

    def test_toggle_favorite_nonexistent(self, group_store):
        """Test toggling favorite on nonexistent group."""
        result = group_store.toggle_favorite("nonexistent")

        assert result is None


class TestGroupStoreMemberManagement:
    """Test member management operations."""

    def test_add_members(self, group_store):
        """Test adding members to a group."""
        group_store.save(ResourceGroup(name="members-group"))

        members = [
            GroupMember(resource_name="func-1", resource_type="lambda:function"),
            GroupMember(resource_name="func-2", resource_type="lambda:function"),
        ]
        added = group_store.add_members("members-group", members)

        assert added == 2

        loaded = group_store.load("members-group")
        assert loaded.resource_count == 2

    def test_add_duplicate_members(self, group_store):
        """Test adding duplicate members (should be skipped)."""
        group_store.save(ResourceGroup(name="dup-group"))

        members = [GroupMember(resource_name="item-1", resource_type="s3:bucket")]
        group_store.add_members("dup-group", members)

        # Add the same member again - should skip duplicates
        added = group_store.add_members("dup-group", members)

        assert added == 0

    def test_add_members_from_arns(self, group_store):
        """Test adding members from ARNs."""
        group_store.save(ResourceGroup(name="arn-group"))

        arns = [
            {"arn": "arn:aws:s3:::my-bucket", "resource_type": "s3:bucket"},
            {"arn": "arn:aws:lambda:us-east-1:123456789012:function:my-func", "resource_type": "lambda:function"},
        ]
        added = group_store.add_members_from_arns("arn-group", arns)

        assert added == 2

        loaded = group_store.load("arn-group")
        names = [m.resource_name for m in loaded.members]
        assert "my-bucket" in names
        assert "my-func" in names

    def test_remove_member(self, group_store):
        """Test removing a member from a group."""
        members = [GroupMember(resource_name="to-remove", resource_type="s3:bucket")]
        group = ResourceGroup(name="remove-group", members=members)
        group_store.save(group)

        result = group_store.remove_member("remove-group", "to-remove", "s3:bucket")

        assert result is True
        loaded = group_store.load("remove-group")
        assert loaded.resource_count == 0

    def test_remove_nonexistent_member(self, group_store):
        """Test removing a member that doesn't exist."""
        group_store.save(ResourceGroup(name="empty-group"))

        result = group_store.remove_member("empty-group", "nonexistent", "s3:bucket")

        assert result is False

    def test_get_members(self, group_store):
        """Test getting members of a group."""
        members = [
            GroupMember(resource_name="m1", resource_type="type1"),
            GroupMember(resource_name="m2", resource_type="type2"),
        ]
        group = ResourceGroup(name="get-members-group", members=members)
        group_store.save(group)

        loaded_members = group_store.get_members("get-members-group")

        assert len(loaded_members) == 2

    def test_get_members_with_pagination(self, group_store):
        """Test getting members with pagination."""
        members = [
            GroupMember(resource_name=f"m{i}", resource_type="type") for i in range(10)
        ]
        group = ResourceGroup(name="paginate-group", members=members)
        group_store.save(group)

        page1 = group_store.get_members("paginate-group", limit=5, offset=0)
        page2 = group_store.get_members("paginate-group", limit=5, offset=5)

        assert len(page1) == 5
        assert len(page2) == 5
        # No overlap
        names1 = {m.resource_name for m in page1}
        names2 = {m.resource_name for m in page2}
        assert names1.isdisjoint(names2)


class TestGroupStoreComparison:
    """Test group comparison operations."""

    def test_is_resource_in_group(self, group_store):
        """Test checking if a resource is in a group."""
        members = [GroupMember(resource_name="in-group", resource_type="s3:bucket")]
        group = ResourceGroup(name="check-group", members=members)
        group_store.save(group)

        assert group_store.is_resource_in_group("check-group", "in-group", "s3:bucket") is True
        assert group_store.is_resource_in_group("check-group", "not-in", "s3:bucket") is False

    def test_compare_snapshot(self, group_store, snapshot_store, temp_db):
        """Test comparing a snapshot against a group."""
        from datetime import datetime

        # Create a group with some members
        members = [
            GroupMember(resource_name="common-resource", resource_type="s3:bucket"),
            GroupMember(resource_name="missing-resource", resource_type="s3:bucket"),
        ]
        group = ResourceGroup(name="compare-group", members=members)
        group_store.save(group)

        # Create a snapshot with resources
        from src.models import Resource, Snapshot
        snapshot = Snapshot(
            name="test-snap",
            created_at=datetime.now(),
            account_id="123456789012",
            regions=["global"],
            resources=[
                Resource(
                    arn="arn:aws:s3:::common-resource",
                    resource_type="s3:bucket",
                    region="global",
                    name="common-resource",
                    config_hash="hash1"
                ),
                Resource(
                    arn="arn:aws:s3:::extra-resource",
                    resource_type="s3:bucket",
                    region="global",
                    name="extra-resource",
                    config_hash="hash2"
                ),
            ]
        )
        snapshot_store.save(snapshot)

        # Compare
        result = group_store.compare_snapshot("compare-group", "test-snap")

        assert result["group_name"] == "compare-group"
        assert result["snapshot_name"] == "test-snap"
        assert result["total_in_group"] == 2
        assert result["matched"] == 1
        assert result["missing_from_snapshot"] == 1
        assert result["not_in_group"] == 1


class TestGroupStoreCreateFromSnapshot:
    """Test creating groups from snapshots."""

    def test_create_from_snapshot(self, group_store, snapshot_store):
        """Test creating a group from a snapshot."""
        from datetime import datetime
        from src.models import Resource, Snapshot

        snapshot = Snapshot(
            name="source-snap",
            created_at=datetime.now(),
            account_id="123456789012",
            regions=["global"],
            resources=[
                Resource(
                    arn="arn:aws:s3:::bucket-1",
                    resource_type="s3:bucket",
                    region="global",
                    name="bucket-1",
                    config_hash="hash1"
                ),
                Resource(
                    arn="arn:aws:s3:::bucket-2",
                    resource_type="s3:bucket",
                    region="global",
                    name="bucket-2",
                    config_hash="hash2"
                ),
            ]
        )
        snapshot_store.save(snapshot)

        count = group_store.create_from_snapshot("new-group", "source-snap")

        assert count == 2
        loaded = group_store.load("new-group")
        assert loaded.source_snapshot == "source-snap"
        assert loaded.resource_count == 2

    def test_create_from_snapshot_with_type_filter(self, group_store, snapshot_store):
        """Test creating a group from a snapshot with type filter."""
        from datetime import datetime
        from src.models import Resource, Snapshot

        snapshot = Snapshot(
            name="filter-snap",
            created_at=datetime.now(),
            account_id="123456789012",
            regions=["global", "us-east-1"],
            resources=[
                Resource(
                    arn="arn:aws:s3:::bucket-1",
                    resource_type="s3:bucket",
                    region="global",
                    name="bucket-1",
                    config_hash="hash1"
                ),
                Resource(
                    arn="arn:aws:lambda:us-east-1:123:function:func-1",
                    resource_type="lambda:function",
                    region="us-east-1",
                    name="func-1",
                    config_hash="hash2"
                ),
            ]
        )
        snapshot_store.save(snapshot)

        count = group_store.create_from_snapshot(
            "filtered-group",
            "filter-snap",
            type_filter="s3:bucket"
        )

        assert count == 1
        loaded = group_store.load("filtered-group")
        assert loaded.members[0].resource_type == "s3:bucket"


class TestExtractResourceName:
    """Test the extract_resource_name utility function."""

    def test_s3_bucket(self):
        """Test extracting name from S3 bucket ARN."""
        arn = "arn:aws:s3:::my-bucket-name"
        name = extract_resource_name(arn, "s3:bucket")
        assert name == "my-bucket-name"

    def test_lambda_function(self):
        """Test extracting name from Lambda function ARN."""
        arn = "arn:aws:lambda:us-east-1:123456789012:function:my-function"
        name = extract_resource_name(arn, "lambda:function")
        assert name == "my-function"

    def test_iam_role(self):
        """Test extracting name from IAM role ARN."""
        arn = "arn:aws:iam::123456789012:role/my-role-name"
        name = extract_resource_name(arn, "iam:role")
        assert name == "my-role-name"

    def test_iam_user(self):
        """Test extracting name from IAM user ARN."""
        arn = "arn:aws:iam::123456789012:user/my-user"
        name = extract_resource_name(arn, "iam:user")
        assert name == "my-user"

    def test_dynamodb_table(self):
        """Test extracting name from DynamoDB table ARN."""
        arn = "arn:aws:dynamodb:us-east-1:123456789012:table/my-table"
        name = extract_resource_name(arn, "dynamodb:table")
        assert name == "my-table"

    def test_ec2_instance(self):
        """Test extracting name from EC2 instance ARN."""
        arn = "arn:aws:ec2:us-east-1:123456789012:instance/i-1234567890abcdef0"
        name = extract_resource_name(arn, "ec2:instance")
        assert name == "i-1234567890abcdef0"

    def test_rds_cluster(self):
        """Test extracting name from RDS cluster ARN."""
        arn = "arn:aws:rds:us-east-1:123456789012:cluster:my-cluster"
        name = extract_resource_name(arn, "rds:cluster")
        assert name == "my-cluster"

    def test_sqs_queue(self):
        """Test extracting name from SQS queue ARN."""
        arn = "arn:aws:sqs:us-east-1:123456789012:my-queue"
        name = extract_resource_name(arn, "sqs:queue")
        assert name == "my-queue"

    def test_sns_topic(self):
        """Test extracting name from SNS topic ARN."""
        arn = "arn:aws:sns:us-east-1:123456789012:my-topic"
        name = extract_resource_name(arn, "sns:topic")
        assert name == "my-topic"

    def test_secretsmanager_secret(self):
        """Test extracting name from Secrets Manager secret ARN."""
        # Test with simple name (no dashes)
        arn = "arn:aws:secretsmanager:us-east-1:123456789012:secret:mysecret-AbCdEf"
        name = extract_resource_name(arn, "secretsmanager:secret")
        # Returns the part before the first dash
        assert name == "mysecret"

    def test_secretsmanager_secret_no_suffix(self):
        """Test extracting name from Secrets Manager secret ARN without suffix."""
        arn = "arn:aws:secretsmanager:us-east-1:123456789012:secret:mysecret"
        name = extract_resource_name(arn, "secretsmanager:secret")
        assert name == "mysecret"

    def test_unknown_format_with_slash(self):
        """Test extracting name from unknown ARN format with slash."""
        arn = "arn:aws:service:region:account:type/resource-name"
        name = extract_resource_name(arn, "service:type")
        assert name == "resource-name"

    def test_unknown_format_with_colon(self):
        """Test extracting name from unknown ARN format with colon."""
        arn = "arn:aws:service:region:account:type:resource-name"
        name = extract_resource_name(arn, "service:type")
        assert name == "resource-name"


class TestResourceGroupModel:
    """Test ResourceGroup dataclass."""

    def test_create_empty_group(self):
        """Test creating an empty group."""
        group = ResourceGroup(name="empty")

        assert group.name == "empty"
        assert group.description == ""
        assert group.members == []
        assert group.resource_count == 0
        assert group.is_favorite is False

    def test_create_group_with_members(self):
        """Test creating a group with members."""
        members = [
            GroupMember(resource_name="r1", resource_type="t1"),
            GroupMember(resource_name="r2", resource_type="t2"),
        ]
        group = ResourceGroup(
            name="full",
            description="A full group",
            members=members,
            resource_count=2
        )

        assert group.name == "full"
        assert len(group.members) == 2
        assert group.resource_count == 2


class TestGroupMemberModel:
    """Test GroupMember dataclass."""

    def test_create_member(self):
        """Test creating a group member."""
        member = GroupMember(
            resource_name="my-resource",
            resource_type="s3:bucket",
            original_arn="arn:aws:s3:::my-resource"
        )

        assert member.resource_name == "my-resource"
        assert member.resource_type == "s3:bucket"
        assert member.original_arn == "arn:aws:s3:::my-resource"

    def test_create_member_without_arn(self):
        """Test creating a group member without original ARN."""
        member = GroupMember(
            resource_name="my-resource",
            resource_type="s3:bucket"
        )

        assert member.original_arn is None


class TestGetResourcesInGroup:
    """Test get_resources_in_group method."""

    def _create_snapshot(self, snapshot_store, name, resources):
        """Helper to create a snapshot with Resource objects."""
        resource_objects = [
            Resource(
                arn=r["arn"],
                resource_type=r["resource_type"],
                region=r["region"],
                name=r["name"],
                config_hash=f"hash-{r['name']}",
            )
            for r in resources
        ]
        snapshot = Snapshot(
            name=name,
            created_at=datetime.now(),
            account_id="123456789012",
            regions=["us-east-1"],
            resources=resource_objects,
            inventory_name="test-inventory",
        )
        snapshot_store.save(snapshot)

    def test_get_resources_in_group_success(self, group_store, snapshot_store):
        """Test getting resources that are in a group."""
        # Create a snapshot with resources
        self._create_snapshot(
            snapshot_store,
            "test-snapshot",
            [
                {"arn": "arn:aws:s3:::bucket-1", "resource_type": "s3:bucket", "name": "bucket-1", "region": "us-east-1"},
                {"arn": "arn:aws:s3:::bucket-2", "resource_type": "s3:bucket", "name": "bucket-2", "region": "us-east-1"},
                {"arn": "arn:aws:s3:::bucket-3", "resource_type": "s3:bucket", "name": "bucket-3", "region": "us-west-2"},
            ],
        )

        # Create a group with some of those resources
        members = [
            GroupMember(resource_name="bucket-1", resource_type="s3:bucket"),
            GroupMember(resource_name="bucket-2", resource_type="s3:bucket"),
        ]
        group = ResourceGroup(name="test-group", members=members)
        group_store.save(group)

        # Get resources in group
        resources = group_store.get_resources_in_group("test-group", "test-snapshot")

        assert len(resources) == 2
        names = {r["name"] for r in resources}
        assert names == {"bucket-1", "bucket-2"}

    def test_get_resources_in_group_empty(self, group_store, snapshot_store):
        """Test getting resources when none are in the group."""
        # Create a snapshot with resources
        self._create_snapshot(
            snapshot_store,
            "test-snapshot",
            [
                {"arn": "arn:aws:s3:::bucket-1", "resource_type": "s3:bucket", "name": "bucket-1", "region": "us-east-1"},
            ],
        )

        # Create an empty group
        group = ResourceGroup(name="empty-group")
        group_store.save(group)

        # Get resources in group
        resources = group_store.get_resources_in_group("empty-group", "test-snapshot")

        assert len(resources) == 0

    def test_get_resources_in_group_not_found(self, group_store, snapshot_store):
        """Test with non-existent group."""
        self._create_snapshot(snapshot_store, "test-snapshot", [])

        with pytest.raises(ValueError, match="not found"):
            group_store.get_resources_in_group("nonexistent", "test-snapshot")

    def test_get_resources_in_group_snapshot_not_found(self, group_store):
        """Test with non-existent snapshot."""
        group = ResourceGroup(name="test-group")
        group_store.save(group)

        with pytest.raises(ValueError, match="not found"):
            group_store.get_resources_in_group("test-group", "nonexistent")

    def test_get_resources_in_group_with_pagination(self, group_store, snapshot_store):
        """Test pagination works correctly."""
        # Create snapshot with many resources
        resources = [
            {"arn": f"arn:aws:s3:::bucket-{i}", "resource_type": "s3:bucket", "name": f"bucket-{i}", "region": "us-east-1"}
            for i in range(10)
        ]
        self._create_snapshot(snapshot_store, "test-snapshot", resources)

        # Create group with all resources
        members = [GroupMember(resource_name=f"bucket-{i}", resource_type="s3:bucket") for i in range(10)]
        group = ResourceGroup(name="test-group", members=members)
        group_store.save(group)

        # Get first page
        page1 = group_store.get_resources_in_group("test-group", "test-snapshot", limit=5, offset=0)
        assert len(page1) == 5

        # Get second page
        page2 = group_store.get_resources_in_group("test-group", "test-snapshot", limit=5, offset=5)
        assert len(page2) == 5

        # Verify no overlap
        names1 = {r["name"] for r in page1}
        names2 = {r["name"] for r in page2}
        assert names1.isdisjoint(names2)


class TestGetResourcesNotInGroup:
    """Test get_resources_not_in_group method."""

    def _create_snapshot(self, snapshot_store, name, resources):
        """Helper to create a snapshot with Resource objects."""
        resource_objects = [
            Resource(
                arn=r["arn"],
                resource_type=r["resource_type"],
                region=r["region"],
                name=r["name"],
                config_hash=f"hash-{r['name']}",
            )
            for r in resources
        ]
        snapshot = Snapshot(
            name=name,
            created_at=datetime.now(),
            account_id="123456789012",
            regions=["us-east-1"],
            resources=resource_objects,
            inventory_name="test-inventory",
        )
        snapshot_store.save(snapshot)

    def test_get_resources_not_in_group_success(self, group_store, snapshot_store):
        """Test getting resources that are not in a group."""
        # Create a snapshot with resources
        self._create_snapshot(
            snapshot_store,
            "test-snapshot",
            [
                {"arn": "arn:aws:s3:::bucket-1", "resource_type": "s3:bucket", "name": "bucket-1", "region": "us-east-1"},
                {"arn": "arn:aws:s3:::bucket-2", "resource_type": "s3:bucket", "name": "bucket-2", "region": "us-east-1"},
                {"arn": "arn:aws:s3:::bucket-3", "resource_type": "s3:bucket", "name": "bucket-3", "region": "us-west-2"},
            ],
        )

        # Create a group with only one resource
        members = [GroupMember(resource_name="bucket-1", resource_type="s3:bucket")]
        group = ResourceGroup(name="test-group", members=members)
        group_store.save(group)

        # Get resources NOT in group
        resources = group_store.get_resources_not_in_group("test-group", "test-snapshot")

        assert len(resources) == 2
        names = {r["name"] for r in resources}
        assert names == {"bucket-2", "bucket-3"}

    def test_get_resources_not_in_group_all_in_group(self, group_store, snapshot_store):
        """Test when all resources are already in the group."""
        # Create a snapshot with resources
        self._create_snapshot(
            snapshot_store,
            "test-snapshot",
            [
                {"arn": "arn:aws:s3:::bucket-1", "resource_type": "s3:bucket", "name": "bucket-1", "region": "us-east-1"},
            ],
        )

        # Create a group with that resource
        members = [GroupMember(resource_name="bucket-1", resource_type="s3:bucket")]
        group = ResourceGroup(name="full-group", members=members)
        group_store.save(group)

        # Get resources NOT in group (should be empty)
        resources = group_store.get_resources_not_in_group("full-group", "test-snapshot")

        assert len(resources) == 0

    def test_get_resources_not_in_group_empty_group(self, group_store, snapshot_store):
        """Test with empty group returns all snapshot resources."""
        # Create a snapshot with resources
        self._create_snapshot(
            snapshot_store,
            "test-snapshot",
            [
                {"arn": "arn:aws:s3:::bucket-1", "resource_type": "s3:bucket", "name": "bucket-1", "region": "us-east-1"},
                {"arn": "arn:aws:s3:::bucket-2", "resource_type": "s3:bucket", "name": "bucket-2", "region": "us-east-1"},
            ],
        )

        # Create empty group
        group = ResourceGroup(name="empty-group")
        group_store.save(group)

        # Get resources NOT in group (should be all)
        resources = group_store.get_resources_not_in_group("empty-group", "test-snapshot")

        assert len(resources) == 2

    def test_get_resources_not_in_group_not_found(self, group_store, snapshot_store):
        """Test with non-existent group."""
        self._create_snapshot(snapshot_store, "test-snapshot", [])

        with pytest.raises(ValueError, match="not found"):
            group_store.get_resources_not_in_group("nonexistent", "test-snapshot")

    def test_get_resources_not_in_group_snapshot_not_found(self, group_store):
        """Test with non-existent snapshot."""
        group = ResourceGroup(name="test-group")
        group_store.save(group)

        with pytest.raises(ValueError, match="not found"):
            group_store.get_resources_not_in_group("test-group", "nonexistent")

    def test_get_resources_not_in_group_with_pagination(self, group_store, snapshot_store):
        """Test pagination works correctly."""
        # Create snapshot with many resources
        resources = [
            {"arn": f"arn:aws:s3:::bucket-{i}", "resource_type": "s3:bucket", "name": f"bucket-{i}", "region": "us-east-1"}
            for i in range(10)
        ]
        self._create_snapshot(snapshot_store, "test-snapshot", resources)

        # Create empty group so all resources are "not in"
        group = ResourceGroup(name="empty-group")
        group_store.save(group)

        # Get first page
        page1 = group_store.get_resources_not_in_group("empty-group", "test-snapshot", limit=5, offset=0)
        assert len(page1) == 5

        # Get second page
        page2 = group_store.get_resources_not_in_group("empty-group", "test-snapshot", limit=5, offset=5)
        assert len(page2) == 5

        # Verify no overlap
        names1 = {r["name"] for r in page1}
        names2 = {r["name"] for r in page2}
        assert names1.isdisjoint(names2)

    def test_get_resources_not_in_group_different_types(self, group_store, snapshot_store):
        """Test that resources with same name but different type are handled correctly."""
        # Create snapshot with resources of different types
        self._create_snapshot(
            snapshot_store,
            "test-snapshot",
            [
                {"arn": "arn:aws:s3:::my-resource", "resource_type": "s3:bucket", "name": "my-resource", "region": "us-east-1"},
                {"arn": "arn:aws:lambda:us-east-1:123:function:my-resource", "resource_type": "lambda:function", "name": "my-resource", "region": "us-east-1"},
            ],
        )

        # Create group with only the S3 bucket
        members = [GroupMember(resource_name="my-resource", resource_type="s3:bucket")]
        group = ResourceGroup(name="test-group", members=members)
        group_store.save(group)

        # Get resources NOT in group - should only include lambda function
        resources = group_store.get_resources_not_in_group("test-group", "test-snapshot")

        assert len(resources) == 1
        assert resources[0]["resource_type"] == "lambda:function"
