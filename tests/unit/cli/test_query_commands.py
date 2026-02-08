"""Tests for CLI query commands."""

import json
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from src.cli.main import app


@pytest.fixture
def cli_runner():
    """Create a Typer CLI runner."""
    return CliRunner()


@pytest.fixture
def mock_database():
    """Create a mock database with test data."""
    mock_db = MagicMock()
    mock_db.fetchall.return_value = [{"id": 1}]
    return mock_db


class TestQuerySqlCommand:
    """Tests for awsinv query sql command."""

    @patch("src.storage.Database")
    @patch("src.storage.ResourceStore")
    def test_basic_query(self, mock_store_cls, mock_db_cls, cli_runner):
        """Test basic SQL query execution."""
        mock_store = MagicMock()
        mock_store.query_raw.return_value = [{"resource_type": "AWS::EC2::Instance", "count": 5}]
        mock_store_cls.return_value = mock_store

        result = cli_runner.invoke(
            app,
            ["query", "sql", "SELECT resource_type, COUNT(*) as count FROM resources GROUP BY resource_type"],
        )

        assert result.exit_code == 0
        assert "AWS::EC2::Instance" in result.stdout
        assert "5" in result.stdout

    @patch("src.storage.Database")
    @patch("src.storage.ResourceStore")
    def test_query_with_limit_flag(self, mock_store_cls, mock_db_cls, cli_runner):
        """Test query with --limit flag."""
        mock_store = MagicMock()
        mock_store.query_raw.return_value = [{"name": "test"}]
        mock_store_cls.return_value = mock_store

        result = cli_runner.invoke(
            app,
            ["query", "sql", "SELECT * FROM resources", "--limit", "500"],
        )

        assert result.exit_code == 0
        # Verify LIMIT was added to query
        call_args = mock_store.query_raw.call_args[0][0]
        assert "LIMIT 500" in call_args

    @patch("src.storage.Database")
    @patch("src.storage.ResourceStore")
    def test_query_preserves_existing_limit(self, mock_store_cls, mock_db_cls, cli_runner):
        """Test that existing LIMIT in query is preserved."""
        mock_store = MagicMock()
        mock_store.query_raw.return_value = [{"name": "test"}]
        mock_store_cls.return_value = mock_store

        result = cli_runner.invoke(
            app,
            ["query", "sql", "SELECT * FROM resources LIMIT 10"],
        )

        assert result.exit_code == 0
        call_args = mock_store.query_raw.call_args[0][0]
        # Should NOT have double LIMIT
        assert call_args.count("LIMIT") == 1
        assert "LIMIT 10" in call_args

    @patch("src.storage.Database")
    @patch("src.storage.ResourceStore")
    def test_query_json_format(self, mock_store_cls, mock_db_cls, cli_runner):
        """Test query with JSON output format."""
        mock_store = MagicMock()
        mock_store.query_raw.return_value = [{"name": "test-resource", "region": "us-east-1"}]
        mock_store_cls.return_value = mock_store

        result = cli_runner.invoke(
            app,
            ["query", "sql", "SELECT * FROM resources", "--format", "json"],
        )

        assert result.exit_code == 0
        # JSON output contains the data followed by row count
        assert "test-resource" in result.stdout
        assert "us-east-1" in result.stdout
        # Verify it's valid JSON by finding the JSON array in output
        import re

        json_match = re.search(r"\[.*\]", result.stdout, re.DOTALL)
        assert json_match is not None
        parsed = json.loads(json_match.group())
        assert parsed[0]["name"] == "test-resource"

    @patch("src.storage.Database")
    @patch("src.storage.ResourceStore")
    def test_query_csv_format(self, mock_store_cls, mock_db_cls, cli_runner):
        """Test query with CSV output format."""
        mock_store = MagicMock()
        mock_store.query_raw.return_value = [{"name": "test-resource", "region": "us-east-1"}]
        mock_store_cls.return_value = mock_store

        result = cli_runner.invoke(
            app,
            ["query", "sql", "SELECT * FROM resources", "--format", "csv"],
        )

        assert result.exit_code == 0
        assert "name,region" in result.stdout or "name" in result.stdout
        assert "test-resource" in result.stdout

    @patch("src.storage.Database")
    @patch("src.storage.ResourceStore")
    def test_query_no_results(self, mock_store_cls, mock_db_cls, cli_runner):
        """Test query with no results."""
        mock_store = MagicMock()
        mock_store.query_raw.return_value = []
        mock_store_cls.return_value = mock_store

        result = cli_runner.invoke(
            app,
            ["query", "sql", "SELECT * FROM resources WHERE 1=0"],
        )

        assert result.exit_code == 0
        assert "No results found" in result.stdout


class TestQuerySqlSnapshotFilter:
    """Tests for --snapshot filter in query sql command."""

    @patch("src.storage.Database")
    @patch("src.storage.ResourceStore")
    def test_snapshot_filter_simple_query(self, mock_store_cls, mock_db_cls, cli_runner):
        """Test --snapshot filter with simple query (no WHERE clause)."""
        mock_db = MagicMock()
        mock_db.fetchall.return_value = [{"id": 42}]
        mock_db_cls.return_value = mock_db

        mock_store = MagicMock()
        mock_store.query_raw.return_value = [{"name": "test"}]
        mock_store_cls.return_value = mock_store

        result = cli_runner.invoke(
            app,
            ["query", "sql", "SELECT * FROM resources", "--snapshot", "my-snapshot"],
        )

        assert result.exit_code == 0
        # Verify snapshot_id filter was injected
        call_args = mock_store.query_raw.call_args[0][0]
        assert "snapshot_id = 42" in call_args
        assert "WHERE" in call_args

    @patch("src.storage.Database")
    @patch("src.storage.ResourceStore")
    def test_snapshot_filter_with_existing_where(self, mock_store_cls, mock_db_cls, cli_runner):
        """Test --snapshot filter with query that has existing WHERE clause."""
        mock_db = MagicMock()
        mock_db.fetchall.return_value = [{"id": 42}]
        mock_db_cls.return_value = mock_db

        mock_store = MagicMock()
        mock_store.query_raw.return_value = [{"name": "test"}]
        mock_store_cls.return_value = mock_store

        result = cli_runner.invoke(
            app,
            [
                "query",
                "sql",
                "SELECT * FROM resources WHERE resource_type = 'AWS::EC2::Instance'",
                "--snapshot",
                "my-snapshot",
            ],
        )

        assert result.exit_code == 0
        call_args = mock_store.query_raw.call_args[0][0]
        assert "snapshot_id = 42" in call_args
        assert "resource_type = 'AWS::EC2::Instance'" in call_args

    @patch("src.storage.Database")
    @patch("src.storage.ResourceStore")
    def test_snapshot_filter_with_group_by(self, mock_store_cls, mock_db_cls, cli_runner):
        """Test --snapshot filter with GROUP BY clause."""
        mock_db = MagicMock()
        mock_db.fetchall.return_value = [{"id": 42}]
        mock_db_cls.return_value = mock_db

        mock_store = MagicMock()
        mock_store.query_raw.return_value = [{"resource_type": "AWS::EC2::Instance", "count": 5}]
        mock_store_cls.return_value = mock_store

        result = cli_runner.invoke(
            app,
            [
                "query",
                "sql",
                "SELECT resource_type, COUNT(*) as count FROM resources GROUP BY resource_type",
                "--snapshot",
                "my-snapshot",
            ],
        )

        assert result.exit_code == 0
        call_args = mock_store.query_raw.call_args[0][0]
        assert "snapshot_id = 42" in call_args
        assert "WHERE" in call_args
        assert "GROUP BY" in call_args

    @patch("src.storage.Database")
    @patch("src.storage.ResourceStore")
    def test_snapshot_filter_with_order_by(self, mock_store_cls, mock_db_cls, cli_runner):
        """Test --snapshot filter with ORDER BY clause."""
        mock_db = MagicMock()
        mock_db.fetchall.return_value = [{"id": 42}]
        mock_db_cls.return_value = mock_db

        mock_store = MagicMock()
        mock_store.query_raw.return_value = [{"name": "test"}]
        mock_store_cls.return_value = mock_store

        result = cli_runner.invoke(
            app,
            ["query", "sql", "SELECT * FROM resources ORDER BY name", "--snapshot", "my-snapshot"],
        )

        assert result.exit_code == 0
        call_args = mock_store.query_raw.call_args[0][0]
        assert "snapshot_id = 42" in call_args
        assert "WHERE" in call_args
        assert "ORDER BY" in call_args

    @patch("src.storage.Database")
    @patch("src.storage.ResourceStore")
    def test_snapshot_filter_not_found(self, mock_store_cls, mock_db_cls, cli_runner):
        """Test --snapshot filter with non-existent snapshot."""
        mock_db = MagicMock()
        mock_db.fetchall.return_value = []  # No snapshot found
        mock_db_cls.return_value = mock_db

        result = cli_runner.invoke(
            app,
            ["query", "sql", "SELECT * FROM resources", "--snapshot", "non-existent"],
        )

        assert result.exit_code == 1
        assert "not found" in result.stdout.lower()


class TestQuerySqlEnvVar:
    """Tests for AWSINV_SNAPSHOT_ID environment variable in query sql command."""

    @patch("src.storage.Database")
    @patch("src.storage.ResourceStore")
    def test_snapshot_from_env_var(self, mock_store_cls, mock_db_cls, cli_runner):
        """Test that AWSINV_SNAPSHOT_ID env var is used."""
        mock_db = MagicMock()
        mock_db.fetchall.return_value = [{"id": 99}]
        mock_db_cls.return_value = mock_db

        mock_store = MagicMock()
        mock_store.query_raw.return_value = [{"name": "test"}]
        mock_store_cls.return_value = mock_store

        result = cli_runner.invoke(
            app,
            ["query", "sql", "SELECT * FROM resources"],
            env={"AWSINV_SNAPSHOT_ID": "env-snapshot"},
        )

        assert result.exit_code == 0
        call_args = mock_store.query_raw.call_args[0][0]
        assert "snapshot_id = 99" in call_args

    @patch("src.storage.Database")
    @patch("src.storage.ResourceStore")
    def test_cli_flag_overrides_env_var(self, mock_store_cls, mock_db_cls, cli_runner):
        """Test that --snapshot flag overrides AWSINV_SNAPSHOT_ID env var."""
        mock_db = MagicMock()

        # Return different IDs based on snapshot name
        def mock_fetchall(query, params):
            if params[0] == "cli-snapshot":
                return [{"id": 100}]
            elif params[0] == "env-snapshot":
                return [{"id": 200}]
            return []

        mock_db.fetchall.side_effect = mock_fetchall
        mock_db_cls.return_value = mock_db

        mock_store = MagicMock()
        mock_store.query_raw.return_value = [{"name": "test"}]
        mock_store_cls.return_value = mock_store

        result = cli_runner.invoke(
            app,
            ["query", "sql", "SELECT * FROM resources", "--snapshot", "cli-snapshot"],
            env={"AWSINV_SNAPSHOT_ID": "env-snapshot"},
        )

        assert result.exit_code == 0
        call_args = mock_store.query_raw.call_args[0][0]
        # Should use CLI flag value (100), not env var value (200)
        assert "snapshot_id = 100" in call_args


class TestEnvironmentVariables:
    """Tests for environment variable support in CLI commands."""

    @patch("src.storage.Database")
    @patch("src.storage.ResourceStore")
    @patch("src.snapshot.storage.SnapshotStorage")
    def test_profile_from_awsinv_profile_env(self, mock_storage, mock_store_cls, mock_db_cls, cli_runner):
        """Test AWSINV_PROFILE environment variable."""
        # Mock the storage to not actually connect
        mock_storage_instance = MagicMock()
        mock_storage.return_value = mock_storage_instance
        mock_storage_instance.list_snapshots.return_value = []

        result = cli_runner.invoke(
            app,
            ["snapshot", "list"],
            env={"AWSINV_PROFILE": "test-profile"},
        )

        # Command should execute (we're just testing env var is read)
        # The actual profile usage is handled by boto3
        assert result.exit_code == 0

    @patch("src.storage.Database")
    @patch("src.storage.ResourceStore")
    @patch("src.snapshot.storage.SnapshotStorage")
    def test_profile_from_aws_profile_env(self, mock_storage, mock_store_cls, mock_db_cls, cli_runner):
        """Test AWS_PROFILE environment variable as fallback."""
        mock_storage_instance = MagicMock()
        mock_storage.return_value = mock_storage_instance
        mock_storage_instance.list_snapshots.return_value = []

        result = cli_runner.invoke(
            app,
            ["snapshot", "list"],
            env={"AWS_PROFILE": "aws-profile"},
        )

        assert result.exit_code == 0

    @patch("src.storage.Database")
    @patch("src.storage.ResourceStore")
    @patch("src.snapshot.storage.SnapshotStorage")
    def test_awsinv_profile_takes_precedence(self, mock_storage, mock_store_cls, mock_db_cls, cli_runner):
        """Test that AWSINV_PROFILE takes precedence over AWS_PROFILE."""
        mock_storage_instance = MagicMock()
        mock_storage.return_value = mock_storage_instance
        mock_storage_instance.list_snapshots.return_value = []

        # Both env vars set - AWSINV_PROFILE should win
        result = cli_runner.invoke(
            app,
            ["snapshot", "list"],
            env={
                "AWSINV_PROFILE": "awsinv-profile",
                "AWS_PROFILE": "aws-profile",
            },
        )

        assert result.exit_code == 0


class TestQuerySqlEdgeCases:
    """Edge case tests for query sql command."""

    @patch("src.storage.Database")
    @patch("src.storage.ResourceStore")
    def test_snapshot_filter_case_insensitive_where(self, mock_store_cls, mock_db_cls, cli_runner):
        """Test --snapshot filter with lowercase 'where' keyword."""
        mock_db = MagicMock()
        mock_db.fetchall.return_value = [{"id": 42}]
        mock_db_cls.return_value = mock_db

        mock_store = MagicMock()
        mock_store.query_raw.return_value = [{"name": "test"}]
        mock_store_cls.return_value = mock_store

        result = cli_runner.invoke(
            app,
            ["query", "sql", "select * from resources where name = 'test'", "--snapshot", "my-snapshot"],
        )

        assert result.exit_code == 0
        call_args = mock_store.query_raw.call_args[0][0]
        assert "snapshot_id = 42" in call_args

    @patch("src.storage.Database")
    @patch("src.storage.ResourceStore")
    def test_snapshot_filter_with_having(self, mock_store_cls, mock_db_cls, cli_runner):
        """Test --snapshot filter with HAVING clause."""
        mock_db = MagicMock()
        mock_db.fetchall.return_value = [{"id": 42}]
        mock_db_cls.return_value = mock_db

        mock_store = MagicMock()
        mock_store.query_raw.return_value = [{"resource_type": "AWS::EC2::Instance", "count": 5}]
        mock_store_cls.return_value = mock_store

        result = cli_runner.invoke(
            app,
            [
                "query",
                "sql",
                "SELECT resource_type, COUNT(*) as count FROM resources GROUP BY resource_type HAVING count > 1",
                "--snapshot",
                "my-snapshot",
            ],
        )

        assert result.exit_code == 0
        call_args = mock_store.query_raw.call_args[0][0]
        assert "snapshot_id = 42" in call_args
        assert "WHERE" in call_args
        # WHERE should come before GROUP BY
        where_pos = call_args.upper().find("WHERE")
        group_pos = call_args.upper().find("GROUP BY")
        assert where_pos < group_pos

    @patch("src.storage.Database")
    @patch("src.storage.ResourceStore")
    def test_snapshot_filter_complex_query(self, mock_store_cls, mock_db_cls, cli_runner):
        """Test --snapshot filter with complex multi-table query."""
        mock_db = MagicMock()
        mock_db.fetchall.return_value = [{"id": 42}]
        mock_db_cls.return_value = mock_db

        mock_store = MagicMock()
        mock_store.query_raw.return_value = [{"name": "test", "key": "Environment", "value": "prod"}]
        mock_store_cls.return_value = mock_store

        # Complex query with JOIN
        query = (
            "SELECT r.name, t.key, t.value FROM resources r "
            "JOIN resource_tags t ON r.id = t.resource_id ORDER BY r.name"
        )

        result = cli_runner.invoke(
            app,
            ["query", "sql", query, "--snapshot", "my-snapshot"],
        )

        assert result.exit_code == 0
        call_args = mock_store.query_raw.call_args[0][0]
        assert "snapshot_id = 42" in call_args


# ---------------------------------------------------------------------------
# query resources
# ---------------------------------------------------------------------------


class TestQueryResources:
    """Tests for awsinv query resources command."""

    @patch("src.storage.Database")
    @patch("src.storage.ResourceStore")
    def test_resources_basic(self, mock_store_cls, mock_db_cls, cli_runner):
        mock_store = MagicMock()
        mock_store.search.return_value = [
            {
                "arn": "arn:aws:s3:::my-bucket",
                "resource_type": "s3:bucket",
                "name": "my-bucket",
                "region": "us-east-1",
                "snapshot_name": "snap-1",
            }
        ]
        mock_store_cls.return_value = mock_store

        result = cli_runner.invoke(app, ["query", "resources"])

        assert result.exit_code == 0
        assert "my-bucket" in result.stdout

    @patch("src.storage.Database")
    @patch("src.storage.ResourceStore")
    def test_resources_with_type_filter(self, mock_store_cls, mock_db_cls, cli_runner):
        mock_store = MagicMock()
        mock_store.search.return_value = [
            {
                "arn": "arn:aws:s3:::bucket-1",
                "resource_type": "s3:bucket",
                "name": "bucket-1",
                "region": "us-east-1",
                "snapshot_name": "snap-1",
            }
        ]
        mock_store_cls.return_value = mock_store

        result = cli_runner.invoke(app, ["query", "resources", "--type", "s3:bucket"])

        assert result.exit_code == 0
        assert "bucket-1" in result.stdout

    @patch("src.storage.Database")
    @patch("src.storage.ResourceStore")
    def test_resources_with_tag_filter(self, mock_store_cls, mock_db_cls, cli_runner):
        mock_store = MagicMock()
        mock_store.search.return_value = [
            {
                "arn": "arn:aws:ec2:us-east-1:123:instance/i-abc",
                "resource_type": "ec2:instance",
                "name": "web-server",
                "region": "us-east-1",
                "snapshot_name": "snap-1",
            }
        ]
        mock_store_cls.return_value = mock_store

        result = cli_runner.invoke(app, ["query", "resources", "--tag", "Env=prod"])

        assert result.exit_code == 0
        assert "1 resource(s) found" in result.stdout

    @patch("src.storage.Database")
    @patch("src.storage.ResourceStore")
    def test_resources_with_tag_key_only(self, mock_store_cls, mock_db_cls, cli_runner):
        mock_store = MagicMock()
        mock_store.search.return_value = [
            {
                "arn": "arn:aws:ec2:us-east-1:123:instance/i-abc",
                "resource_type": "ec2:instance",
                "name": "web-server",
                "region": "us-east-1",
                "snapshot_name": "snap-1",
            }
        ]
        mock_store_cls.return_value = mock_store

        result = cli_runner.invoke(app, ["query", "resources", "--tag", "Environment"])

        assert result.exit_code == 0

    @patch("src.storage.Database")
    @patch("src.storage.ResourceStore")
    def test_resources_json_format(self, mock_store_cls, mock_db_cls, cli_runner):
        mock_store = MagicMock()
        mock_store.search.return_value = [
            {
                "arn": "arn:aws:s3:::bucket-1",
                "resource_type": "s3:bucket",
                "name": "bucket-1",
                "region": "us-east-1",
                "snapshot_name": "snap-1",
            }
        ]
        mock_store_cls.return_value = mock_store

        result = cli_runner.invoke(app, ["query", "resources", "--format", "json"])

        assert result.exit_code == 0
        assert "bucket-1" in result.stdout

    @patch("src.storage.Database")
    @patch("src.storage.ResourceStore")
    def test_resources_no_results(self, mock_store_cls, mock_db_cls, cli_runner):
        mock_store = MagicMock()
        mock_store.search.return_value = []
        mock_store_cls.return_value = mock_store

        result = cli_runner.invoke(app, ["query", "resources", "--type", "nonexistent"])

        assert result.exit_code == 0
        assert "No resources found" in result.stdout

    @patch("src.storage.Database")
    @patch("src.storage.ResourceStore")
    def test_resources_error(self, mock_store_cls, mock_db_cls, cli_runner):
        mock_store = MagicMock()
        mock_store.search.side_effect = Exception("DB error")
        mock_store_cls.return_value = mock_store

        result = cli_runner.invoke(app, ["query", "resources"])

        assert result.exit_code == 1
        assert "Error" in result.stdout

    @patch("src.storage.Database")
    @patch("src.storage.ResourceStore")
    def test_resources_with_arn_filter(self, mock_store_cls, mock_db_cls, cli_runner):
        mock_store = MagicMock()
        mock_store.search.return_value = [
            {
                "arn": "arn:aws:s3:::my-bucket",
                "resource_type": "s3:bucket",
                "name": "my-bucket",
                "region": "us-east-1",
                "snapshot_name": "snap-1",
            }
        ]
        mock_store_cls.return_value = mock_store

        result = cli_runner.invoke(
            app, ["query", "resources", "--arn", "arn:aws:s3:::my-bucket*"]
        )

        assert result.exit_code == 0
        assert "my-bucket" in result.stdout

    @patch("src.storage.Database")
    @patch("src.storage.ResourceStore")
    def test_resources_with_snapshot_filter(self, mock_store_cls, mock_db_cls, cli_runner):
        mock_store = MagicMock()
        mock_store.search.return_value = [
            {
                "arn": "arn:aws:s3:::my-bucket",
                "resource_type": "s3:bucket",
                "name": "my-bucket",
                "region": "us-east-1",
                "snapshot_name": "baseline-2024",
            }
        ]
        mock_store_cls.return_value = mock_store

        result = cli_runner.invoke(
            app, ["query", "resources", "--snapshot", "baseline-2024"]
        )

        assert result.exit_code == 0
        assert "my-bucket" in result.stdout

    @patch("src.storage.Database")
    @patch("src.storage.ResourceStore")
    def test_resources_long_arn_truncated(self, mock_store_cls, mock_db_cls, cli_runner):
        long_arn = "arn:aws:lambda:us-east-1:123456789012:function:" + "a" * 100
        mock_store = MagicMock()
        mock_store.search.return_value = [
            {
                "arn": long_arn,
                "resource_type": "lambda:function",
                "name": "long-func",
                "region": "us-east-1",
                "snapshot_name": "snap-1",
            }
        ]
        mock_store_cls.return_value = mock_store

        result = cli_runner.invoke(app, ["query", "resources"])

        assert result.exit_code == 0
        assert "..." in result.stdout


# ---------------------------------------------------------------------------
# query history
# ---------------------------------------------------------------------------


class TestQueryHistory:
    """Tests for awsinv query history command."""

    @patch("src.storage.Database")
    @patch("src.storage.ResourceStore")
    def test_history_table(self, mock_store_cls, mock_db_cls, cli_runner):
        mock_store = MagicMock()
        mock_store.get_history.return_value = [
            {
                "snapshot_name": "snap-1",
                "snapshot_created_at": "2025-06-15T12:00:00",
                "config_hash": "abc123def456789",
                "source": "direct_api",
            },
            {
                "snapshot_name": "snap-2",
                "snapshot_created_at": "2025-06-16T12:00:00",
                "config_hash": "xyz789abc123456",
                "source": "aws_config",
            },
        ]
        mock_store_cls.return_value = mock_store

        result = cli_runner.invoke(app, ["query", "history", "arn:aws:s3:::my-bucket"])

        assert result.exit_code == 0
        assert "snap-1" in result.stdout
        assert "snap-2" in result.stdout
        assert "2 snapshot(s)" in result.stdout

    @patch("src.storage.Database")
    @patch("src.storage.ResourceStore")
    def test_history_json(self, mock_store_cls, mock_db_cls, cli_runner):
        mock_store = MagicMock()
        mock_store.get_history.return_value = [
            {
                "snapshot_name": "snap-1",
                "snapshot_created_at": "2025-06-15T12:00:00",
                "config_hash": "abc123",
                "source": "direct_api",
            }
        ]
        mock_store_cls.return_value = mock_store

        result = cli_runner.invoke(
            app,
            ["query", "history", "arn:aws:s3:::my-bucket", "--format", "json"],
        )

        assert result.exit_code == 0
        assert "snap-1" in result.stdout

    @patch("src.storage.Database")
    @patch("src.storage.ResourceStore")
    def test_history_no_results(self, mock_store_cls, mock_db_cls, cli_runner):
        mock_store = MagicMock()
        mock_store.get_history.return_value = []
        mock_store_cls.return_value = mock_store

        result = cli_runner.invoke(app, ["query", "history", "arn:aws:s3:::missing"])

        assert result.exit_code == 0
        assert "No history found" in result.stdout

    @patch("src.storage.Database")
    @patch("src.storage.ResourceStore")
    def test_history_config_change_highlight(self, mock_store_cls, mock_db_cls, cli_runner):
        mock_store = MagicMock()
        mock_store.get_history.return_value = [
            {
                "snapshot_name": "snap-1",
                "snapshot_created_at": "2025-06-15T12:00:00",
                "config_hash": "hash_a_full_length",
                "source": "direct_api",
            },
            {
                "snapshot_name": "snap-2",
                "snapshot_created_at": "2025-06-16T12:00:00",
                "config_hash": "hash_b_changed_xx",
                "source": "direct_api",
            },
        ]
        mock_store_cls.return_value = mock_store

        result = cli_runner.invoke(app, ["query", "history", "arn:aws:s3:::my-bucket"])

        assert result.exit_code == 0
        assert "changed" in result.stdout

    @patch("src.storage.Database")
    @patch("src.storage.ResourceStore")
    def test_history_error(self, mock_store_cls, mock_db_cls, cli_runner):
        mock_store = MagicMock()
        mock_store.get_history.side_effect = Exception("DB error")
        mock_store_cls.return_value = mock_store

        result = cli_runner.invoke(app, ["query", "history", "arn:aws:s3:::my-bucket"])

        assert result.exit_code == 1
        assert "Error" in result.stdout


# ---------------------------------------------------------------------------
# query stats
# ---------------------------------------------------------------------------


class TestQueryStats:
    """Tests for awsinv query stats command."""

    @patch("src.storage.SnapshotStore")
    @patch("src.storage.ResourceStore")
    @patch("src.storage.Database")
    def test_stats_default(self, mock_db_cls, mock_resource_store_cls, mock_snap_store_cls, cli_runner):
        mock_snap_store = MagicMock()
        mock_snap_store.get_snapshot_count.return_value = 5
        mock_snap_store.get_resource_count.return_value = 100
        mock_snap_store_cls.return_value = mock_snap_store

        mock_resource_store = MagicMock()
        mock_resource_store.get_stats.return_value = [
            {"group_key": "AWS::EC2::Instance", "count": 50},
            {"group_key": "AWS::S3::Bucket", "count": 30},
        ]
        mock_resource_store_cls.return_value = mock_resource_store

        result = cli_runner.invoke(app, ["query", "stats"])

        assert result.exit_code == 0
        assert "5" in result.stdout
        assert "100" in result.stdout

    @patch("src.storage.SnapshotStore")
    @patch("src.storage.ResourceStore")
    @patch("src.storage.Database")
    def test_stats_json(self, mock_db_cls, mock_resource_store_cls, mock_snap_store_cls, cli_runner):
        mock_snap_store = MagicMock()
        mock_snap_store.get_snapshot_count.return_value = 2
        mock_snap_store.get_resource_count.return_value = 10
        mock_snap_store_cls.return_value = mock_snap_store

        mock_resource_store = MagicMock()
        mock_resource_store.get_stats.return_value = [
            {"group_key": "us-east-1", "count": 10},
        ]
        mock_resource_store_cls.return_value = mock_resource_store

        result = cli_runner.invoke(app, ["query", "stats", "--format", "json"])

        assert result.exit_code == 0
        assert "us-east-1" in result.stdout

    @patch("src.storage.SnapshotStore")
    @patch("src.storage.ResourceStore")
    @patch("src.storage.Database")
    def test_stats_group_by_region(self, mock_db_cls, mock_resource_store_cls, mock_snap_store_cls, cli_runner):
        mock_snap_store = MagicMock()
        mock_snap_store.get_snapshot_count.return_value = 1
        mock_snap_store.get_resource_count.return_value = 5
        mock_snap_store_cls.return_value = mock_snap_store

        mock_resource_store = MagicMock()
        mock_resource_store.get_stats.return_value = [
            {"group_key": "us-east-1", "count": 3},
            {"group_key": "us-west-2", "count": 2},
        ]
        mock_resource_store_cls.return_value = mock_resource_store

        result = cli_runner.invoke(app, ["query", "stats", "--group-by", "region"])

        assert result.exit_code == 0
        assert "Region" in result.stdout

    @patch("src.storage.SnapshotStore")
    @patch("src.storage.ResourceStore")
    @patch("src.storage.Database")
    def test_stats_no_results(self, mock_db_cls, mock_resource_store_cls, mock_snap_store_cls, cli_runner):
        mock_snap_store = MagicMock()
        mock_snap_store.get_snapshot_count.return_value = 0
        mock_snap_store.get_resource_count.return_value = 0
        mock_snap_store_cls.return_value = mock_snap_store

        mock_resource_store = MagicMock()
        mock_resource_store.get_stats.return_value = []
        mock_resource_store_cls.return_value = mock_resource_store

        result = cli_runner.invoke(app, ["query", "stats"])

        assert result.exit_code == 0
        assert "No statistics" in result.stdout

    @patch("src.storage.SnapshotStore")
    @patch("src.storage.ResourceStore")
    @patch("src.storage.Database")
    def test_stats_with_snapshot_filter(self, mock_db_cls, mock_resource_store_cls, mock_snap_store_cls, cli_runner):
        mock_snap_store = MagicMock()
        mock_snap_store.get_snapshot_count.return_value = 1
        mock_snap_store.get_resource_count.return_value = 10
        mock_snap_store_cls.return_value = mock_snap_store

        mock_resource_store = MagicMock()
        mock_resource_store.get_stats.return_value = [
            {"group_key": "AWS::EC2::Instance", "count": 10},
        ]
        mock_resource_store_cls.return_value = mock_resource_store

        result = cli_runner.invoke(app, ["query", "stats", "--snapshot", "snap-1"])

        assert result.exit_code == 0
        assert "snap-1" in result.stdout

    @patch("src.storage.SnapshotStore")
    @patch("src.storage.ResourceStore")
    @patch("src.storage.Database")
    def test_stats_error(self, mock_db_cls, mock_resource_store_cls, mock_snap_store_cls, cli_runner):
        mock_db_cls.side_effect = Exception("Connection failed")

        result = cli_runner.invoke(app, ["query", "stats"])

        assert result.exit_code == 1
        assert "Error" in result.stdout


# ---------------------------------------------------------------------------
# query diff
# ---------------------------------------------------------------------------


class TestQueryDiff:
    """Tests for awsinv query diff command."""

    @patch("src.storage.Database")
    @patch("src.storage.ResourceStore")
    def test_diff_with_changes(self, mock_store_cls, mock_db_cls, cli_runner):
        mock_store = MagicMock()
        mock_store.compare_snapshots.return_value = {
            "added": [
                {"arn": "arn:aws:s3:::new-bucket", "resource_type": "s3:bucket", "region": "us-east-1"}
            ],
            "removed": [
                {"arn": "arn:aws:s3:::old-bucket", "resource_type": "s3:bucket", "region": "us-east-1"}
            ],
            "modified": [
                {
                    "arn": "arn:aws:ec2:us-east-1:123:instance/i-abc",
                    "resource_type": "ec2:instance",
                    "old_hash": "hash_old_abcdef",
                    "new_hash": "hash_new_xyz123",
                }
            ],
            "summary": {
                "snapshot1_count": 10,
                "snapshot2_count": 10,
                "added_count": 1,
                "removed_count": 1,
                "modified_count": 1,
            },
        }
        mock_store_cls.return_value = mock_store

        result = cli_runner.invoke(app, ["query", "diff", "snap-1", "snap-2"])

        assert result.exit_code == 0
        assert "Added" in result.stdout
        assert "Removed" in result.stdout
        assert "Modified" in result.stdout

    @patch("src.storage.Database")
    @patch("src.storage.ResourceStore")
    def test_diff_no_changes(self, mock_store_cls, mock_db_cls, cli_runner):
        mock_store = MagicMock()
        mock_store.compare_snapshots.return_value = {
            "added": [],
            "removed": [],
            "modified": [],
            "summary": {
                "snapshot1_count": 10,
                "snapshot2_count": 10,
                "added_count": 0,
                "removed_count": 0,
                "modified_count": 0,
            },
        }
        mock_store_cls.return_value = mock_store

        result = cli_runner.invoke(app, ["query", "diff", "snap-1", "snap-2"])

        assert result.exit_code == 0
        assert "No differences" in result.stdout

    @patch("src.storage.Database")
    @patch("src.storage.ResourceStore")
    def test_diff_json_format(self, mock_store_cls, mock_db_cls, cli_runner):
        mock_store = MagicMock()
        mock_store.compare_snapshots.return_value = {
            "added": [],
            "removed": [],
            "modified": [],
            "summary": {
                "snapshot1_count": 5,
                "snapshot2_count": 5,
                "added_count": 0,
                "removed_count": 0,
                "modified_count": 0,
            },
        }
        mock_store_cls.return_value = mock_store

        result = cli_runner.invoke(
            app, ["query", "diff", "snap-1", "snap-2", "--format", "json"]
        )

        assert result.exit_code == 0
        assert "snapshot1_count" in result.stdout

    @patch("src.storage.Database")
    @patch("src.storage.ResourceStore")
    def test_diff_summary_format(self, mock_store_cls, mock_db_cls, cli_runner):
        mock_store = MagicMock()
        mock_store.compare_snapshots.return_value = {
            "added": [{"arn": "a", "resource_type": "s3:bucket", "region": "us-east-1"}],
            "removed": [],
            "modified": [],
            "summary": {
                "snapshot1_count": 5,
                "snapshot2_count": 6,
                "added_count": 1,
                "removed_count": 0,
                "modified_count": 0,
            },
        }
        mock_store_cls.return_value = mock_store

        result = cli_runner.invoke(
            app, ["query", "diff", "snap-1", "snap-2", "--format", "summary"]
        )

        assert result.exit_code == 0
        assert "Added" in result.stdout

    @patch("src.storage.Database")
    @patch("src.storage.ResourceStore")
    def test_diff_with_type_filter(self, mock_store_cls, mock_db_cls, cli_runner):
        mock_store = MagicMock()
        mock_store.compare_snapshots.return_value = {
            "added": [
                {"arn": "arn:aws:s3:::bucket-1", "resource_type": "s3:bucket", "region": "us-east-1"},
                {"arn": "arn:aws:ec2:us-east-1:123:instance/i-abc", "resource_type": "ec2:instance", "region": "us-east-1"},
            ],
            "removed": [],
            "modified": [],
            "summary": {
                "snapshot1_count": 5,
                "snapshot2_count": 7,
                "added_count": 2,
                "removed_count": 0,
                "modified_count": 0,
            },
        }
        mock_store_cls.return_value = mock_store

        result = cli_runner.invoke(
            app, ["query", "diff", "snap-1", "snap-2", "--type", "s3"]
        )

        assert result.exit_code == 0

    @patch("src.storage.Database")
    @patch("src.storage.ResourceStore")
    def test_diff_error(self, mock_store_cls, mock_db_cls, cli_runner):
        mock_store = MagicMock()
        mock_store.compare_snapshots.side_effect = Exception("Snapshot not found")
        mock_store_cls.return_value = mock_store

        result = cli_runner.invoke(app, ["query", "diff", "snap-1", "snap-2"])

        assert result.exit_code == 1
        assert "Error" in result.stdout
