"""Unit tests for CreatorCacheStore."""

from pathlib import Path

import pytest

from src.storage.creator_cache_store import CreatorCacheStore
from src.storage.database import Database


@pytest.fixture
def db(tmp_path: Path) -> Database:
    """Create a test database."""
    database = Database(storage_path=tmp_path)
    database.ensure_schema()
    return database


@pytest.fixture
def store(db: Database) -> CreatorCacheStore:
    """Create a creator cache store."""
    return CreatorCacheStore(db)


@pytest.fixture
def sample_creators():
    """Sample creator data."""
    return {
        "AWS::S3::Bucket:my-bucket": {
            "created_by": "arn:aws:iam::123456789012:role/AdminRole",
            "created_by_type": "AssumedRole",
            "created_at": "2025-01-15T10:30:00+00:00",
        },
        "AWS::Lambda::Function:my-func": {
            "created_by": "arn:aws:iam::123456789012:user/dev-user",
            "created_by_type": "IAMUser",
            "created_at": "2025-01-16T11:00:00+00:00",
        },
        "AWS::EC2::Instance:i-1234567890abcdef0": {
            "created_by": "arn:aws:iam::123456789012:role/DeployRole",
            "created_by_type": "AssumedRole",
            "created_at": "2025-01-17T09:00:00+00:00",
        },
    }


class TestSaveBatch:
    def test_save_batch_returns_count(self, store, sample_creators):
        count = store.save_batch("123456789012", sample_creators)
        assert count == 3

    def test_save_batch_empty(self, store):
        count = store.save_batch("123456789012", {})
        assert count == 0

    def test_save_batch_upserts_on_duplicate(self, store):
        creators = {
            "AWS::S3::Bucket:my-bucket": {
                "created_by": "arn:aws:iam::123:role/OldRole",
                "created_by_type": "AssumedRole",
                "created_at": "2025-01-01T00:00:00+00:00",
            },
        }
        store.save_batch("123456789012", creators)

        updated = {
            "AWS::S3::Bucket:my-bucket": {
                "created_by": "arn:aws:iam::123:role/NewRole",
                "created_by_type": "AssumedRole",
                "created_at": "2025-01-10T00:00:00+00:00",
            },
        }
        store.save_batch("123456789012", updated)

        result = store.lookup("123456789012", ["AWS::S3::Bucket:my-bucket"])
        assert result["AWS::S3::Bucket:my-bucket"]["created_by"] == "arn:aws:iam::123:role/NewRole"

    def test_save_batch_skips_bad_keys(self, store):
        creators = {
            "no-colon-key": {
                "created_by": "arn",
                "created_by_type": "IAMUser",
                "created_at": "2025-01-01T00:00:00+00:00",
            },
        }
        count = store.save_batch("123456789012", creators)
        assert count == 0


class TestLookup:
    def test_lookup_returns_cached_entries(self, store, sample_creators):
        store.save_batch("123456789012", sample_creators)
        keys = [
            "AWS::S3::Bucket:my-bucket",
            "AWS::Lambda::Function:my-func",
        ]
        result = store.lookup("123456789012", keys)
        assert len(result) == 2
        assert result["AWS::S3::Bucket:my-bucket"]["created_by_type"] == "AssumedRole"
        assert result["AWS::Lambda::Function:my-func"]["created_by_type"] == "IAMUser"

    def test_lookup_empty_keys(self, store):
        result = store.lookup("123456789012", [])
        assert result == {}

    def test_lookup_no_matches(self, store, sample_creators):
        store.save_batch("123456789012", sample_creators)
        result = store.lookup("123456789012", ["AWS::S3::Bucket:nonexistent"])
        assert result == {}

    def test_lookup_different_account(self, store, sample_creators):
        store.save_batch("123456789012", sample_creators)
        result = store.lookup("999999999999", ["AWS::S3::Bucket:my-bucket"])
        assert result == {}

    def test_lookup_partial_match(self, store, sample_creators):
        store.save_batch("123456789012", sample_creators)
        keys = [
            "AWS::S3::Bucket:my-bucket",
            "AWS::RDS::DBInstance:nonexistent",
        ]
        result = store.lookup("123456789012", keys)
        assert len(result) == 1
        assert "AWS::S3::Bucket:my-bucket" in result

    def test_lookup_large_batch(self, store):
        """Test that lookup works with > 500 keys (batch splitting)."""
        creators = {}
        for i in range(600):
            creators[f"AWS::S3::Bucket:bucket-{i}"] = {
                "created_by": f"arn:aws:iam::123:role/Role{i}",
                "created_by_type": "AssumedRole",
                "created_at": "2025-01-01T00:00:00+00:00",
            }
        store.save_batch("123456789012", creators)

        keys = [f"AWS::S3::Bucket:bucket-{i}" for i in range(600)]
        result = store.lookup("123456789012", keys)
        assert len(result) == 600


class TestClear:
    def test_clear_all(self, store, sample_creators):
        store.save_batch("123456789012", sample_creators)
        deleted = store.clear()
        assert deleted == 3
        result = store.lookup("123456789012", ["AWS::S3::Bucket:my-bucket"])
        assert result == {}

    def test_clear_by_account(self, store, sample_creators):
        store.save_batch("123456789012", sample_creators)
        store.save_batch(
            "999999999999",
            {
                "AWS::S3::Bucket:other-bucket": {
                    "created_by": "arn:aws:iam::999:role/Role",
                    "created_by_type": "AssumedRole",
                    "created_at": "2025-01-01T00:00:00+00:00",
                },
            },
        )
        deleted = store.clear("123456789012")
        assert deleted == 3

        # Other account untouched
        result = store.lookup("999999999999", ["AWS::S3::Bucket:other-bucket"])
        assert len(result) == 1

    def test_clear_empty(self, store):
        deleted = store.clear()
        assert deleted == 0
