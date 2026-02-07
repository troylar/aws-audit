"""Unit tests for ResourceStore."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import pytest

from src.storage.database import Database
from src.storage.resource_store import ResourceStore


@pytest.fixture
def db(tmp_path: Path) -> Database:
    """Create a test database with schema."""
    database = Database(storage_path=tmp_path)
    database.ensure_schema()
    return database


@pytest.fixture
def store(db: Database) -> ResourceStore:
    """Create a resource store."""
    return ResourceStore(db)


def _insert_snapshot(db: Database, name: str, created_at: str = "2025-01-10T00:00:00+00:00", account_id: str = "123456789012") -> int:
    """Insert a snapshot and return its id."""
    with db.transaction() as cursor:
        cursor.execute(
            "INSERT INTO snapshots (name, created_at, account_id, regions, resource_count) VALUES (?, ?, ?, ?, ?)",
            (name, created_at, account_id, "[]", 0),
        )
        return cursor.lastrowid


def _insert_resource(
    db: Database,
    snapshot_id: int,
    arn: str,
    resource_type: str = "s3:bucket",
    name: str = "test",
    region: str = "us-east-1",
    config_hash: str = "a" * 64,
    created_at: str = "2025-01-10T00:00:00+00:00",
    source: str = "collector",
) -> int:
    """Insert a resource and return its id."""
    with db.transaction() as cursor:
        cursor.execute(
            """INSERT INTO resources (snapshot_id, arn, resource_type, name, region, config_hash, created_at, source)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (snapshot_id, arn, resource_type, name, region, config_hash, created_at, source),
        )
        return cursor.lastrowid


def _insert_tag(db: Database, resource_id: int, key: str, value: str) -> None:
    """Insert a resource tag."""
    with db.transaction() as cursor:
        cursor.execute(
            "INSERT INTO resource_tags (resource_id, key, value) VALUES (?, ?, ?)",
            (resource_id, key, value),
        )


class TestQueryRaw:
    """Tests for query_raw method."""

    def test_valid_select(self, store: ResourceStore, db: Database) -> None:
        snap_id = _insert_snapshot(db, "snap1")
        _insert_resource(db, snap_id, "arn:aws:s3:::bucket1", name="bucket1")
        results = store.query_raw("SELECT arn FROM resources")
        assert len(results) == 1
        assert results[0]["arn"] == "arn:aws:s3:::bucket1"

    def test_parameterized_query(self, store: ResourceStore, db: Database) -> None:
        snap_id = _insert_snapshot(db, "snap1")
        _insert_resource(db, snap_id, "arn:aws:s3:::bucket1", name="bucket1")
        _insert_resource(db, snap_id, "arn:aws:ec2:::instance1", resource_type="ec2:instance", name="instance1")
        results = store.query_raw("SELECT arn FROM resources WHERE resource_type = ?", ("s3:bucket",))
        assert len(results) == 1

    def test_reject_insert(self, store: ResourceStore) -> None:
        with pytest.raises(ValueError, match="Only SELECT"):
            store.query_raw("INSERT INTO resources (arn) VALUES ('test')")

    def test_reject_drop(self, store: ResourceStore) -> None:
        with pytest.raises(ValueError, match="forbidden keyword: DROP"):
            store.query_raw("SELECT * FROM resources; DROP TABLE resources")

    def test_reject_delete(self, store: ResourceStore) -> None:
        with pytest.raises(ValueError, match="forbidden keyword: DELETE"):
            store.query_raw("SELECT * FROM resources; DELETE FROM resources")

    def test_reject_update(self, store: ResourceStore) -> None:
        with pytest.raises(ValueError, match="forbidden keyword: UPDATE"):
            store.query_raw("SELECT * FROM resources; UPDATE resources SET arn='x'")

    def test_reject_alter(self, store: ResourceStore) -> None:
        with pytest.raises(ValueError, match="forbidden keyword: ALTER"):
            store.query_raw("SELECT * FROM resources; ALTER TABLE resources ADD col TEXT")

    def test_reject_create(self, store: ResourceStore) -> None:
        with pytest.raises(ValueError, match="forbidden keyword: CREATE"):
            store.query_raw("SELECT * FROM resources; CREATE TABLE evil (id INT)")

    def test_reject_truncate(self, store: ResourceStore) -> None:
        with pytest.raises(ValueError, match="forbidden keyword: TRUNCATE"):
            store.query_raw("SELECT * FROM resources; TRUNCATE TABLE resources")


class TestSearch:
    """Tests for search method."""

    @pytest.fixture(autouse=True)
    def _seed_data(self, db: Database) -> None:
        snap_id = _insert_snapshot(db, "snap1", "2025-01-10T00:00:00+00:00")
        r1 = _insert_resource(db, snap_id, "arn:aws:s3:::bucket1", "s3:bucket", "bucket1", "us-east-1")
        r2 = _insert_resource(db, snap_id, "arn:aws:ec2:us-west-2:123:instance/i-1", "ec2:instance", "web-server", "us-west-2")
        _insert_tag(db, r1, "Environment", "prod")
        _insert_tag(db, r1, "Team", "platform")
        _insert_tag(db, r2, "Environment", "dev")

    def test_no_filters(self, store: ResourceStore) -> None:
        results = store.search()
        assert len(results) == 2

    def test_arn_pattern_with_wildcard(self, store: ResourceStore) -> None:
        results = store.search(arn_pattern="arn:aws:s3%")
        assert len(results) == 1
        assert "s3" in results[0]["arn"]

    def test_arn_pattern_without_wildcard(self, store: ResourceStore) -> None:
        results = store.search(arn_pattern="bucket1")
        assert len(results) == 1

    def test_resource_type_exact(self, store: ResourceStore) -> None:
        results = store.search(resource_type="s3:bucket")
        assert len(results) == 1
        assert results[0]["resource_type"] == "s3:bucket"

    def test_resource_type_partial(self, store: ResourceStore) -> None:
        results = store.search(resource_type="ec2")
        assert len(results) == 1
        assert "ec2" in results[0]["resource_type"]

    def test_region_filter(self, store: ResourceStore) -> None:
        results = store.search(region="us-west-2")
        assert len(results) == 1
        assert results[0]["region"] == "us-west-2"

    def test_snapshot_name_filter(self, store: ResourceStore) -> None:
        results = store.search(snapshot_name="snap1")
        assert len(results) == 2

    def test_snapshot_name_filter_no_match(self, store: ResourceStore) -> None:
        results = store.search(snapshot_name="nonexistent")
        assert len(results) == 0

    def test_tag_key_filter(self, store: ResourceStore) -> None:
        results = store.search(tag_key="Team")
        assert len(results) == 1
        assert results[0]["arn"] == "arn:aws:s3:::bucket1"

    def test_tag_key_and_value(self, store: ResourceStore) -> None:
        results = store.search(tag_key="Environment", tag_value="prod")
        assert len(results) == 1
        assert results[0]["arn"] == "arn:aws:s3:::bucket1"

    def test_created_before(self, store: ResourceStore) -> None:
        results = store.search(created_before=datetime(2025, 1, 11, tzinfo=timezone.utc))
        assert len(results) == 2

    def test_created_before_no_match(self, store: ResourceStore) -> None:
        results = store.search(created_before=datetime(2025, 1, 9, tzinfo=timezone.utc))
        assert len(results) == 0

    def test_created_after(self, store: ResourceStore) -> None:
        results = store.search(created_after=datetime(2025, 1, 9, tzinfo=timezone.utc))
        assert len(results) == 2

    def test_created_after_no_match(self, store: ResourceStore) -> None:
        results = store.search(created_after=datetime(2025, 1, 11, tzinfo=timezone.utc))
        assert len(results) == 0

    def test_limit_and_offset(self, store: ResourceStore) -> None:
        results = store.search(limit=1, offset=0)
        assert len(results) == 1
        results2 = store.search(limit=1, offset=1)
        assert len(results2) == 1
        assert results[0]["arn"] != results2[0]["arn"]

    def test_combined_filters(self, store: ResourceStore) -> None:
        results = store.search(region="us-east-1", resource_type="s3:bucket")
        assert len(results) == 1


class TestGetHistory:
    """Tests for get_history method."""

    def test_arn_with_multiple_snapshots(self, store: ResourceStore, db: Database) -> None:
        snap1 = _insert_snapshot(db, "snap1", "2025-01-10T00:00:00+00:00")
        snap2 = _insert_snapshot(db, "snap2", "2025-01-11T00:00:00+00:00")
        _insert_resource(db, snap1, "arn:aws:s3:::bucket1", name="bucket1")
        _insert_resource(db, snap2, "arn:aws:s3:::bucket1", name="bucket1")
        history = store.get_history("arn:aws:s3:::bucket1")
        assert len(history) == 2
        assert history[0]["snapshot_name"] == "snap2"
        assert history[1]["snapshot_name"] == "snap1"

    def test_arn_not_found(self, store: ResourceStore) -> None:
        history = store.get_history("arn:aws:s3:::nonexistent")
        assert history == []


class TestGetStats:
    """Tests for get_stats method."""

    @pytest.fixture(autouse=True)
    def _seed_data(self, db: Database) -> None:
        snap_id = _insert_snapshot(db, "snap1")
        _insert_resource(db, snap_id, "arn:aws:s3:::b1", "s3:bucket", "b1", "us-east-1")
        _insert_resource(db, snap_id, "arn:aws:s3:::b2", "s3:bucket", "b2", "us-east-1")
        _insert_resource(db, snap_id, "arn:aws:ec2:us-west-2:123:i/i-1", "ec2:instance", "i1", "us-west-2")

    def test_group_by_type(self, store: ResourceStore) -> None:
        stats = store.get_stats(group_by="type")
        by_key = {s["group_key"]: s["count"] for s in stats}
        assert by_key["s3:bucket"] == 2
        assert by_key["ec2:instance"] == 1

    def test_group_by_region(self, store: ResourceStore) -> None:
        stats = store.get_stats(group_by="region")
        by_key = {s["group_key"]: s["count"] for s in stats}
        assert by_key["us-east-1"] == 2
        assert by_key["us-west-2"] == 1

    def test_group_by_service(self, store: ResourceStore) -> None:
        stats = store.get_stats(group_by="service")
        by_key = {s["group_key"]: s["count"] for s in stats}
        assert by_key["s3"] == 2
        assert by_key["ec2"] == 1

    def test_group_by_snapshot(self, store: ResourceStore) -> None:
        stats = store.get_stats(group_by="snapshot")
        assert len(stats) == 1
        assert stats[0]["group_key"] == "snap1"
        assert stats[0]["count"] == 3

    def test_with_snapshot_filter(self, store: ResourceStore) -> None:
        stats = store.get_stats(snapshot_name="snap1", group_by="type")
        total = sum(s["count"] for s in stats)
        assert total == 3

    def test_invalid_group_by_defaults_to_type(self, store: ResourceStore) -> None:
        stats = store.get_stats(group_by="invalid")
        by_key = {s["group_key"]: s["count"] for s in stats}
        assert "s3:bucket" in by_key


class TestCompareSnapshots:
    """Tests for compare_snapshots method."""

    def test_added_removed_modified(self, store: ResourceStore, db: Database) -> None:
        snap1 = _insert_snapshot(db, "snap1", "2025-01-10T00:00:00+00:00")
        snap2 = _insert_snapshot(db, "snap2", "2025-01-11T00:00:00+00:00")

        _insert_resource(db, snap1, "arn:aws:s3:::shared", config_hash="a" * 64, name="shared")
        _insert_resource(db, snap1, "arn:aws:s3:::removed-bucket", name="removed")
        _insert_resource(db, snap1, "arn:aws:s3:::modified", config_hash="a" * 64, name="modified")

        _insert_resource(db, snap2, "arn:aws:s3:::shared", config_hash="a" * 64, name="shared")
        _insert_resource(db, snap2, "arn:aws:s3:::added-bucket", name="added")
        _insert_resource(db, snap2, "arn:aws:s3:::modified", config_hash="b" * 64, name="modified")

        result = store.compare_snapshots("snap1", "snap2")
        assert result["summary"]["added_count"] == 1
        assert result["summary"]["removed_count"] == 1
        assert result["summary"]["modified_count"] == 1
        added_arns = {r["arn"] for r in result["added"]}
        removed_arns = {r["arn"] for r in result["removed"]}
        modified_arns = {r["arn"] for r in result["modified"]}
        assert "arn:aws:s3:::added-bucket" in added_arns
        assert "arn:aws:s3:::removed-bucket" in removed_arns
        assert "arn:aws:s3:::modified" in modified_arns

    def test_identical_snapshots(self, store: ResourceStore, db: Database) -> None:
        snap1 = _insert_snapshot(db, "snap1")
        snap2 = _insert_snapshot(db, "snap2")
        _insert_resource(db, snap1, "arn:aws:s3:::bucket1", config_hash="a" * 64, name="b1")
        _insert_resource(db, snap2, "arn:aws:s3:::bucket1", config_hash="a" * 64, name="b1")
        result = store.compare_snapshots("snap1", "snap2")
        assert result["summary"]["added_count"] == 0
        assert result["summary"]["removed_count"] == 0
        assert result["summary"]["modified_count"] == 0

    def test_empty_snapshots(self, store: ResourceStore, db: Database) -> None:
        _insert_snapshot(db, "snap1")
        _insert_snapshot(db, "snap2")
        result = store.compare_snapshots("snap1", "snap2")
        assert result["summary"]["snapshot1_count"] == 0
        assert result["summary"]["snapshot2_count"] == 0


class TestGetTagsForResource:
    """Tests for get_tags_for_resource method."""

    def test_with_tags(self, store: ResourceStore, db: Database) -> None:
        snap_id = _insert_snapshot(db, "snap1")
        r_id = _insert_resource(db, snap_id, "arn:aws:s3:::bucket1")
        _insert_tag(db, r_id, "Env", "prod")
        _insert_tag(db, r_id, "Team", "platform")
        tags = store.get_tags_for_resource("arn:aws:s3:::bucket1")
        assert tags == {"Env": "prod", "Team": "platform"}

    def test_with_snapshot_name(self, store: ResourceStore, db: Database) -> None:
        snap1 = _insert_snapshot(db, "snap1", "2025-01-10T00:00:00+00:00")
        snap2 = _insert_snapshot(db, "snap2", "2025-01-11T00:00:00+00:00")
        r1 = _insert_resource(db, snap1, "arn:aws:s3:::bucket1")
        r2 = _insert_resource(db, snap2, "arn:aws:s3:::bucket1")
        _insert_tag(db, r1, "Env", "prod")
        _insert_tag(db, r2, "Env", "staging")
        tags = store.get_tags_for_resource("arn:aws:s3:::bucket1", snapshot_name="snap1")
        assert tags["Env"] == "prod"

    def test_no_tags(self, store: ResourceStore, db: Database) -> None:
        snap_id = _insert_snapshot(db, "snap1")
        _insert_resource(db, snap_id, "arn:aws:s3:::bucket1")
        tags = store.get_tags_for_resource("arn:aws:s3:::bucket1")
        assert tags == {}


class TestFindByTag:
    """Tests for find_by_tag method."""

    @pytest.fixture(autouse=True)
    def _seed_data(self, db: Database) -> None:
        snap_id = _insert_snapshot(db, "snap1")
        r1 = _insert_resource(db, snap_id, "arn:aws:s3:::bucket1", name="bucket1")
        r2 = _insert_resource(db, snap_id, "arn:aws:ec2:::i-1", "ec2:instance", "i-1")
        _insert_tag(db, r1, "Env", "prod")
        _insert_tag(db, r2, "Env", "dev")

    def test_by_key_only(self, store: ResourceStore) -> None:
        results = store.find_by_tag("Env")
        assert len(results) == 2

    def test_by_key_and_value(self, store: ResourceStore) -> None:
        results = store.find_by_tag("Env", "prod")
        assert len(results) == 1
        assert results[0]["arn"] == "arn:aws:s3:::bucket1"

    def test_with_snapshot_name(self, store: ResourceStore) -> None:
        results = store.find_by_tag("Env", snapshot_name="snap1")
        assert len(results) == 2

    def test_with_limit(self, store: ResourceStore) -> None:
        results = store.find_by_tag("Env", limit=1)
        assert len(results) == 1


class TestGetUniqueResourceTypes:
    """Tests for get_unique_resource_types method."""

    def test_all_snapshots(self, store: ResourceStore, db: Database) -> None:
        snap_id = _insert_snapshot(db, "snap1")
        _insert_resource(db, snap_id, "arn:aws:s3:::b1", "s3:bucket", "b1")
        _insert_resource(db, snap_id, "arn:aws:ec2:::i-1", "ec2:instance", "i-1")
        types = store.get_unique_resource_types()
        assert sorted(types) == ["ec2:instance", "s3:bucket"]

    def test_specific_snapshot(self, store: ResourceStore, db: Database) -> None:
        snap1 = _insert_snapshot(db, "snap1")
        snap2 = _insert_snapshot(db, "snap2")
        _insert_resource(db, snap1, "arn:aws:s3:::b1", "s3:bucket", "b1")
        _insert_resource(db, snap2, "arn:aws:ec2:::i-1", "ec2:instance", "i-1")
        types = store.get_unique_resource_types(snapshot_name="snap1")
        assert types == ["s3:bucket"]

    def test_empty(self, store: ResourceStore) -> None:
        types = store.get_unique_resource_types()
        assert types == []


class TestGetUniqueRegions:
    """Tests for get_unique_regions method."""

    def test_all_snapshots(self, store: ResourceStore, db: Database) -> None:
        snap_id = _insert_snapshot(db, "snap1")
        _insert_resource(db, snap_id, "arn:aws:s3:::b1", region="us-east-1")
        _insert_resource(db, snap_id, "arn:aws:ec2:::i-1", "ec2:instance", "i-1", region="us-west-2")
        regions = store.get_unique_regions()
        assert sorted(regions) == ["us-east-1", "us-west-2"]

    def test_specific_snapshot(self, store: ResourceStore, db: Database) -> None:
        snap1 = _insert_snapshot(db, "snap1")
        snap2 = _insert_snapshot(db, "snap2")
        _insert_resource(db, snap1, "arn:aws:s3:::b1", region="us-east-1")
        _insert_resource(db, snap2, "arn:aws:ec2:::i-1", "ec2:instance", "i-1", region="us-west-2")
        regions = store.get_unique_regions(snapshot_name="snap1")
        assert regions == ["us-east-1"]

    def test_empty(self, store: ResourceStore) -> None:
        regions = store.get_unique_regions()
        assert regions == []
