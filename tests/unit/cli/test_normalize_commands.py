"""Tests for CLI normalize command."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from src.cli.main import app


@pytest.fixture
def cli_runner():
    return CliRunner()


def _make_mock_resource(arn: str = "arn:aws:s3:::my-bucket", name: str = "my-bucket", resource_type: str = "s3:bucket"):
    r = MagicMock()
    r.arn = arn
    r.name = name
    r.resource_type = resource_type
    r.tags = {}
    return r


class TestNormalizeCommand:
    """Tests for awsinv normalize command."""

    @patch("src.cli.main.Config.load")
    @patch("src.storage.SnapshotStore")
    @patch("src.storage.Database")
    def test_normalize_snapshot_not_found(self, mock_db_cls, mock_snap_store_cls, mock_config_load, cli_runner):
        mock_config = MagicMock()
        mock_config.storage_path = None
        mock_config.log_level = "INFO"
        mock_config.aws_profile = None
        mock_config_load.return_value = mock_config

        mock_snap_store = MagicMock()
        mock_snap_store.exists.return_value = False
        mock_snap_store_cls.return_value = mock_snap_store

        result = cli_runner.invoke(app, ["normalize", "--snapshot", "nonexistent"])

        assert result.exit_code == 1
        assert "not found" in result.stdout

    @patch("src.cli.main.Config.load")
    @patch("src.storage.SnapshotStore")
    @patch("src.storage.Database")
    def test_normalize_empty_snapshot(self, mock_db_cls, mock_snap_store_cls, mock_config_load, cli_runner):
        mock_config = MagicMock()
        mock_config.storage_path = None
        mock_config.log_level = "INFO"
        mock_config.aws_profile = None
        mock_config_load.return_value = mock_config

        mock_snap_store = MagicMock()
        mock_snap_store.exists.return_value = True
        mock_snap_obj = MagicMock()
        mock_snap_obj.resources = []
        mock_snap_store.load.return_value = mock_snap_obj
        mock_snap_store_cls.return_value = mock_snap_store

        result = cli_runner.invoke(app, ["normalize", "--snapshot", "empty-snap"])

        assert result.exit_code == 0
        assert "no resources" in result.stdout.lower()

    @patch("src.cli.main.Config.load")
    @patch("src.storage.SnapshotStore")
    @patch("src.storage.Database")
    @patch("src.matching.ResourceNormalizer")
    @patch("src.matching.NormalizerConfig")
    def test_normalize_dry_run(self, mock_norm_config_cls, mock_normalizer_cls, mock_db_cls, mock_snap_store_cls, mock_config_load, cli_runner):
        mock_config = MagicMock()
        mock_config.storage_path = None
        mock_config.log_level = "INFO"
        mock_config.aws_profile = None
        mock_config_load.return_value = mock_config

        resources = [
            _make_mock_resource("arn:aws:s3:::bucket-1", "bucket-1", "s3:bucket"),
            _make_mock_resource("arn:aws:lambda:us-east-1:123:function:func-1", "func-1", "lambda:function"),
        ]

        mock_snap_store = MagicMock()
        mock_snap_store.exists.return_value = True
        mock_snap_obj = MagicMock()
        mock_snap_obj.resources = resources
        mock_snap_store.load.return_value = mock_snap_obj
        mock_snap_store_cls.return_value = mock_snap_store

        mock_norm_config = MagicMock()
        mock_norm_config.is_ai_enabled = False
        mock_norm_config_cls.from_env.return_value = mock_norm_config

        mock_normalizer = MagicMock()
        mock_normalizer.normalize_resources.return_value = {
            "arn:aws:s3:::bucket-1": "bucket-1",
            "arn:aws:lambda:us-east-1:123:function:func-1": "func-1",
        }
        mock_normalizer.tokens_used = 0
        mock_normalizer_cls.return_value = mock_normalizer

        result = cli_runner.invoke(app, ["normalize", "--snapshot", "test-snap", "--dry-run", "--no-ai"])

        assert result.exit_code == 0
        assert "DRY RUN" in result.stdout
        assert "No changes saved" in result.stdout

    @patch("src.cli.main.Config.load")
    @patch("src.storage.SnapshotStore")
    @patch("src.storage.Database")
    @patch("src.matching.ResourceNormalizer")
    @patch("src.matching.NormalizerConfig")
    def test_normalize_saves_changes(self, mock_norm_config_cls, mock_normalizer_cls, mock_db_cls, mock_snap_store_cls, mock_config_load, cli_runner):
        mock_config = MagicMock()
        mock_config.storage_path = None
        mock_config.log_level = "INFO"
        mock_config.aws_profile = None
        mock_config_load.return_value = mock_config

        resources = [
            _make_mock_resource("arn:aws:s3:::bucket-1", "bucket-1", "s3:bucket"),
        ]

        mock_snap_store = MagicMock()
        mock_snap_store.exists.return_value = True
        mock_snap_obj = MagicMock()
        mock_snap_obj.resources = resources
        mock_snap_store.load.return_value = mock_snap_obj
        mock_snap_store.get_id.return_value = 42
        mock_snap_store_cls.return_value = mock_snap_store

        mock_norm_config = MagicMock()
        mock_norm_config.is_ai_enabled = False
        mock_norm_config_cls.from_env.return_value = mock_norm_config

        mock_normalizer = MagicMock()
        mock_normalizer.normalize_resources.return_value = {
            "arn:aws:s3:::bucket-1": "bucket-1-normalized",
        }
        mock_normalizer.tokens_used = 0
        mock_normalizer_cls.return_value = mock_normalizer

        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        mock_db.transaction.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_db.transaction.return_value.__exit__ = MagicMock(return_value=False)
        mock_db_cls.return_value = mock_db

        result = cli_runner.invoke(app, ["normalize", "--snapshot", "test-snap", "--no-ai"])

        assert result.exit_code == 0
        assert "Updated" in result.stdout

    @patch("src.cli.main.Config.load")
    @patch("src.storage.SnapshotStore")
    @patch("src.storage.Database")
    @patch("src.matching.ResourceNormalizer")
    @patch("src.matching.NormalizerConfig")
    def test_normalize_snapshot_id_not_found(self, mock_norm_config_cls, mock_normalizer_cls, mock_db_cls, mock_snap_store_cls, mock_config_load, cli_runner):
        mock_config = MagicMock()
        mock_config.storage_path = None
        mock_config.log_level = "INFO"
        mock_config.aws_profile = None
        mock_config_load.return_value = mock_config

        resources = [_make_mock_resource()]

        mock_snap_store = MagicMock()
        mock_snap_store.exists.return_value = True
        mock_snap_obj = MagicMock()
        mock_snap_obj.resources = resources
        mock_snap_store.load.return_value = mock_snap_obj
        mock_snap_store.get_id.return_value = None
        mock_snap_store_cls.return_value = mock_snap_store

        mock_norm_config = MagicMock()
        mock_norm_config.is_ai_enabled = False
        mock_norm_config_cls.from_env.return_value = mock_norm_config

        mock_normalizer = MagicMock()
        mock_normalizer.normalize_resources.return_value = {"arn:aws:s3:::my-bucket": "my-bucket"}
        mock_normalizer.tokens_used = 0
        mock_normalizer_cls.return_value = mock_normalizer

        result = cli_runner.invoke(app, ["normalize", "--snapshot", "test-snap", "--no-ai"])

        assert result.exit_code == 1
        assert "Failed to get snapshot ID" in result.stdout

    @patch("src.cli.main.Config.load")
    @patch("src.storage.SnapshotStore")
    @patch("src.storage.Database")
    @patch("src.matching.NormalizerConfig")
    @patch("src.matching.ResourceNormalizer")
    def test_normalize_ai_fallback_when_no_api_key(self, mock_normalizer_cls, mock_norm_config_cls, mock_db_cls, mock_snap_store_cls, mock_config_load, cli_runner):
        mock_config = MagicMock()
        mock_config.storage_path = None
        mock_config.log_level = "INFO"
        mock_config.aws_profile = None
        mock_config_load.return_value = mock_config

        resources = [_make_mock_resource()]

        mock_snap_store = MagicMock()
        mock_snap_store.exists.return_value = True
        mock_snap_obj = MagicMock()
        mock_snap_obj.resources = resources
        mock_snap_store.load.return_value = mock_snap_obj
        mock_snap_store.get_id.return_value = 1
        mock_snap_store_cls.return_value = mock_snap_store

        mock_norm_config = MagicMock()
        mock_norm_config.is_ai_enabled = False
        mock_norm_config_cls.from_env.return_value = mock_norm_config

        mock_normalizer = MagicMock()
        mock_normalizer.normalize_resources.return_value = {"arn:aws:s3:::my-bucket": "my-bucket"}
        mock_normalizer.tokens_used = 0
        mock_normalizer_cls.return_value = mock_normalizer

        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        mock_db.transaction.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_db.transaction.return_value.__exit__ = MagicMock(return_value=False)
        mock_db_cls.return_value = mock_db

        result = cli_runner.invoke(app, ["normalize", "--snapshot", "test-snap"])

        assert result.exit_code == 0
        assert "OPENAI_API_KEY not set" in result.stdout or "rules-based" in result.stdout.lower() or "Updated" in result.stdout
