"""Unit tests for SQLite database connection management."""

import json
from pathlib import Path

import pytest

from src.storage.database import Database, json_deserialize, json_serialize


class TestDatabase:
    """Test cases for Database class."""

    def test_initialization_sets_paths(self, tmp_path: Path) -> None:
        """Test that Database sets paths correctly."""
        storage_path = tmp_path / "new_dir"
        db = Database(storage_path=storage_path)

        assert db.db_path == storage_path / "inventory.db"
        assert db.storage_path == storage_path

    def test_connect_creates_directory(self, tmp_path: Path) -> None:
        """Test that connect creates storage directory."""
        storage_path = tmp_path / "new_dir"
        db = Database(storage_path=storage_path)

        db.connect()

        assert storage_path.exists()
        assert db.db_path.exists()

    def test_connect_creates_database_file(self, tmp_path: Path) -> None:
        """Test that connect creates database file."""
        db = Database(storage_path=tmp_path)
        db.connect()

        assert db.db_path.exists()

    def test_ensure_schema_creates_tables(self, tmp_path: Path) -> None:
        """Test that ensure_schema creates all required tables."""
        db = Database(storage_path=tmp_path)
        db.ensure_schema()

        # Verify tables exist
        tables = db.fetchall("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        table_names = {row["name"] for row in tables}

        expected_tables = {
            "snapshots",
            "resources",
            "resource_tags",
            "collections",
            "collection_snapshots",
            "audit_operations",
            "audit_records",
            "schema_info",
        }
        assert expected_tables.issubset(table_names)

    def test_transaction_commits_on_success(self, tmp_path: Path) -> None:
        """Test that transaction commits data on success."""
        db = Database(storage_path=tmp_path)
        db.ensure_schema()

        with db.transaction() as cursor:
            cursor.execute(
                """
                INSERT INTO snapshots (name, created_at, account_id, regions, resource_count)
                VALUES (?, ?, ?, ?, ?)
                """,
                ("test-snap", "2025-01-10T00:00:00+00:00", "123456789012", "[]", 0),
            )

        # Verify data was committed
        row = db.fetchone("SELECT name FROM snapshots WHERE name = ?", ("test-snap",))
        assert row is not None
        assert row["name"] == "test-snap"

    def test_transaction_rollback_on_error(self, tmp_path: Path) -> None:
        """Test that transaction rolls back on error."""
        db = Database(storage_path=tmp_path)
        db.ensure_schema()

        try:
            with db.transaction() as cursor:
                cursor.execute(
                    """
                    INSERT INTO snapshots (name, created_at, account_id, regions, resource_count)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    ("rollback-test", "2025-01-10T00:00:00+00:00", "123456789012", "[]", 0),
                )
                # Force an error
                raise ValueError("Test error")
        except ValueError:
            pass

        # Verify data was rolled back
        row = db.fetchone("SELECT name FROM snapshots WHERE name = ?", ("rollback-test",))
        assert row is None

    def test_fetchone_returns_dict(self, tmp_path: Path) -> None:
        """Test that fetchone returns dict with column names."""
        db = Database(storage_path=tmp_path)
        db.ensure_schema()

        with db.transaction() as cursor:
            cursor.execute(
                """
                INSERT INTO snapshots (name, created_at, account_id, regions, resource_count)
                VALUES (?, ?, ?, ?, ?)
                """,
                ("fetch-test", "2025-01-10T00:00:00+00:00", "123456789012", "[]", 5),
            )

        row = db.fetchone("SELECT * FROM snapshots WHERE name = ?", ("fetch-test",))
        assert "name" in row
        assert "account_id" in row
        assert row["resource_count"] == 5

    def test_fetchone_returns_none_when_not_found(self, tmp_path: Path) -> None:
        """Test that fetchone returns None when no match."""
        db = Database(storage_path=tmp_path)
        db.ensure_schema()

        row = db.fetchone("SELECT * FROM snapshots WHERE name = ?", ("nonexistent",))
        assert row is None

    def test_fetchall_returns_list_of_dicts(self, tmp_path: Path) -> None:
        """Test that fetchall returns list of dicts."""
        db = Database(storage_path=tmp_path)
        db.ensure_schema()

        with db.transaction() as cursor:
            cursor.executemany(
                """
                INSERT INTO snapshots (name, created_at, account_id, regions, resource_count)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    ("snap1", "2025-01-10T00:00:00+00:00", "123456789012", "[]", 1),
                    ("snap2", "2025-01-10T00:00:00+00:00", "123456789012", "[]", 2),
                    ("snap3", "2025-01-10T00:00:00+00:00", "123456789012", "[]", 3),
                ],
            )

        rows = db.fetchall("SELECT * FROM snapshots ORDER BY name")
        assert len(rows) == 3
        assert rows[0]["name"] == "snap1"
        assert rows[1]["name"] == "snap2"
        assert rows[2]["name"] == "snap3"

    def test_fetchall_returns_empty_list(self, tmp_path: Path) -> None:
        """Test that fetchall returns empty list when no matches."""
        db = Database(storage_path=tmp_path)
        db.ensure_schema()

        rows = db.fetchall("SELECT * FROM snapshots")
        assert rows == []

    def test_execute_runs_statement(self, tmp_path: Path) -> None:
        """Test that execute runs SQL statement."""
        db = Database(storage_path=tmp_path)
        db.ensure_schema()

        db.execute(
            """
            INSERT INTO snapshots (name, created_at, account_id, regions, resource_count)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("exec-test", "2025-01-10T00:00:00+00:00", "123456789012", "[]", 0),
        )

        row = db.fetchone("SELECT * FROM snapshots WHERE name = ?", ("exec-test",))
        assert row is not None

    def test_close_closes_connection(self, tmp_path: Path) -> None:
        """Test that close properly closes connection."""
        db = Database(storage_path=tmp_path)
        db.ensure_schema()
        db.close()

        # Connection should be closed
        assert db._connection is None


class TestJsonSerialization:
    """Test cases for JSON serialization helpers."""

    def test_json_serialize_dict(self) -> None:
        """Test serializing dict to JSON."""
        data = {"key": "value", "nested": {"a": 1}}
        result = json_serialize(data)

        assert '"key": "value"' in result
        assert '"nested"' in result

    def test_json_serialize_list(self) -> None:
        """Test serializing list to JSON."""
        data = ["a", "b", "c"]
        result = json_serialize(data)

        assert result == '["a", "b", "c"]'

    def test_json_serialize_none(self) -> None:
        """Test serializing None returns None."""
        result = json_serialize(None)
        assert result is None

    def test_json_deserialize_dict(self) -> None:
        """Test deserializing JSON to dict."""
        data = '{"key": "value"}'
        result = json_deserialize(data)

        assert result == {"key": "value"}

    def test_json_deserialize_list(self) -> None:
        """Test deserializing JSON to list."""
        data = '["a", "b", "c"]'
        result = json_deserialize(data)

        assert result == ["a", "b", "c"]

    def test_json_deserialize_none(self) -> None:
        """Test deserializing None returns None."""
        result = json_deserialize(None)
        assert result is None

    def test_json_deserialize_empty_string(self) -> None:
        """Test deserializing empty string raises error."""
        # Empty string is not valid JSON
        with pytest.raises(json.JSONDecodeError):
            json_deserialize("")
