"""Tests for CLI group commands (create, list, show, delete, compare, add, remove, export)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from src.cli.main import app
from src.models.group import GroupMember, ResourceGroup


@pytest.fixture
def cli_runner():
    return CliRunner()


def _make_group(
    name: str = "baseline",
    description: str = "Test group",
    resource_count: int = 3,
    source_snapshot: str | None = "snap-1",
    members: list[GroupMember] | None = None,
    is_favorite: bool = False,
) -> ResourceGroup:
    if members is None:
        members = [
            GroupMember(resource_name="my-bucket", resource_type="s3:bucket", original_arn="arn:aws:s3:::my-bucket"),
            GroupMember(resource_name="my-func", resource_type="lambda:function", original_arn="arn:aws:lambda:us-east-1:123456789012:function:my-func"),
            GroupMember(resource_name="my-table", resource_type="dynamodb:table", original_arn="arn:aws:dynamodb:us-east-1:123456789012:table/my-table"),
        ]
    return ResourceGroup(
        name=name,
        description=description,
        source_snapshot=source_snapshot,
        members=members,
        resource_count=resource_count,
        is_favorite=is_favorite,
        created_at=datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc),
        last_updated=datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc),
    )


def _make_list_entry(
    name: str = "baseline",
    description: str = "Test group",
    resource_count: int = 3,
    source_snapshot: str | None = "snap-1",
    is_favorite: bool = False,
) -> dict:
    return {
        "name": name,
        "description": description,
        "resource_count": resource_count,
        "source_snapshot": source_snapshot,
        "is_favorite": is_favorite,
    }


# ---------------------------------------------------------------------------
# group create
# ---------------------------------------------------------------------------


class TestGroupCreate:
    @patch("src.storage.GroupStore")
    @patch("src.storage.Database")
    def test_create_empty_group(self, mock_db_cls, mock_store_cls, cli_runner):
        mock_store = MagicMock()
        mock_store.exists.return_value = False
        mock_store_cls.return_value = mock_store

        result = cli_runner.invoke(
            app,
            ["group", "create", "baseline", "--description", "Production baseline"],
        )

        assert result.exit_code == 0
        assert "baseline" in result.stdout
        mock_store.save.assert_called_once()

    @patch("src.storage.GroupStore")
    @patch("src.storage.Database")
    def test_create_group_from_snapshot(self, mock_db_cls, mock_store_cls, cli_runner):
        mock_store = MagicMock()
        mock_store.exists.return_value = False
        mock_store.create_from_snapshot.return_value = 5
        mock_store_cls.return_value = mock_store

        result = cli_runner.invoke(
            app,
            ["group", "create", "baseline", "--from-snapshot", "snap-2025"],
        )

        assert result.exit_code == 0
        assert "5 resources" in result.stdout
        mock_store.create_from_snapshot.assert_called_once()

    @patch("src.storage.GroupStore")
    @patch("src.storage.Database")
    def test_create_group_from_snapshot_with_filters(self, mock_db_cls, mock_store_cls, cli_runner):
        mock_store = MagicMock()
        mock_store.exists.return_value = False
        mock_store.create_from_snapshot.return_value = 2
        mock_store_cls.return_value = mock_store

        result = cli_runner.invoke(
            app,
            [
                "group", "create", "iam-baseline",
                "--from-snapshot", "snap-2025",
                "--type", "iam",
                "--region", "us-east-1",
            ],
        )

        assert result.exit_code == 0
        assert "2 resources" in result.stdout

    @patch("src.storage.GroupStore")
    @patch("src.storage.Database")
    def test_create_duplicate_group_fails(self, mock_db_cls, mock_store_cls, cli_runner):
        mock_store = MagicMock()
        mock_store.exists.return_value = True
        mock_store_cls.return_value = mock_store

        result = cli_runner.invoke(
            app,
            ["group", "create", "baseline"],
        )

        assert result.exit_code == 1
        assert "already exists" in result.stdout

    @patch("src.storage.GroupStore")
    @patch("src.storage.Database")
    def test_create_group_value_error(self, mock_db_cls, mock_store_cls, cli_runner):
        mock_store = MagicMock()
        mock_store.exists.return_value = False
        mock_store.save.side_effect = ValueError("Invalid group name")
        mock_store_cls.return_value = mock_store

        result = cli_runner.invoke(
            app,
            ["group", "create", "bad!name"],
        )

        assert result.exit_code == 1
        assert "Invalid group name" in result.stdout


# ---------------------------------------------------------------------------
# group list
# ---------------------------------------------------------------------------


class TestGroupList:
    @patch("src.storage.GroupStore")
    @patch("src.storage.Database")
    def test_list_groups_table(self, mock_db_cls, mock_store_cls, cli_runner):
        mock_store = MagicMock()
        mock_store.list_all.return_value = [
            _make_list_entry(name="baseline", resource_count=10),
            _make_list_entry(name="dev-resources", resource_count=3, is_favorite=True),
        ]
        mock_store_cls.return_value = mock_store

        result = cli_runner.invoke(app, ["group", "list"])

        assert result.exit_code == 0
        assert "baseline" in result.stdout
        assert "dev-resources" in result.stdout

    @patch("src.storage.GroupStore")
    @patch("src.storage.Database")
    def test_list_groups_json(self, mock_db_cls, mock_store_cls, cli_runner):
        mock_store = MagicMock()
        mock_store.list_all.return_value = [
            _make_list_entry(name="baseline"),
        ]
        mock_store_cls.return_value = mock_store

        result = cli_runner.invoke(app, ["group", "list", "--format", "json"])

        assert result.exit_code == 0
        assert "baseline" in result.stdout

    @patch("src.storage.GroupStore")
    @patch("src.storage.Database")
    def test_list_groups_empty(self, mock_db_cls, mock_store_cls, cli_runner):
        mock_store = MagicMock()
        mock_store.list_all.return_value = []
        mock_store_cls.return_value = mock_store

        result = cli_runner.invoke(app, ["group", "list"])

        assert result.exit_code == 0
        assert "No groups found" in result.stdout

    @patch("src.storage.GroupStore")
    @patch("src.storage.Database")
    def test_list_groups_error(self, mock_db_cls, mock_store_cls, cli_runner):
        mock_store = MagicMock()
        mock_store.list_all.side_effect = Exception("DB error")
        mock_store_cls.return_value = mock_store

        result = cli_runner.invoke(app, ["group", "list"])

        assert result.exit_code == 1
        assert "Error" in result.stdout


# ---------------------------------------------------------------------------
# group show
# ---------------------------------------------------------------------------


class TestGroupShow:
    @patch("src.storage.GroupStore")
    @patch("src.storage.Database")
    def test_show_group_with_members(self, mock_db_cls, mock_store_cls, cli_runner):
        mock_store = MagicMock()
        mock_store.load.return_value = _make_group()
        mock_store_cls.return_value = mock_store

        result = cli_runner.invoke(app, ["group", "show", "baseline"])

        assert result.exit_code == 0
        assert "baseline" in result.stdout
        assert "my-bucket" in result.stdout

    @patch("src.storage.GroupStore")
    @patch("src.storage.Database")
    def test_show_group_not_found(self, mock_db_cls, mock_store_cls, cli_runner):
        mock_store = MagicMock()
        mock_store.load.return_value = None
        mock_store_cls.return_value = mock_store

        result = cli_runner.invoke(app, ["group", "show", "missing"])

        assert result.exit_code == 1
        assert "not found" in result.stdout

    @patch("src.storage.GroupStore")
    @patch("src.storage.Database")
    def test_show_group_no_members(self, mock_db_cls, mock_store_cls, cli_runner):
        mock_store = MagicMock()
        group = _make_group(members=[], resource_count=0)
        mock_store.load.return_value = group
        mock_store_cls.return_value = mock_store

        result = cli_runner.invoke(app, ["group", "show", "empty-group"])

        assert result.exit_code == 0
        assert "no members" in result.stdout.lower()

    @patch("src.storage.GroupStore")
    @patch("src.storage.Database")
    def test_show_group_with_limit(self, mock_db_cls, mock_store_cls, cli_runner):
        mock_store = MagicMock()
        mock_store.load.return_value = _make_group()
        mock_store_cls.return_value = mock_store

        result = cli_runner.invoke(app, ["group", "show", "baseline", "--limit", "1"])

        assert result.exit_code == 0
        assert "baseline" in result.stdout


# ---------------------------------------------------------------------------
# group delete
# ---------------------------------------------------------------------------


class TestGroupDelete:
    @patch("src.storage.GroupStore")
    @patch("src.storage.Database")
    def test_delete_group_with_confirm(self, mock_db_cls, mock_store_cls, cli_runner):
        mock_store = MagicMock()
        mock_store.exists.return_value = True
        mock_store_cls.return_value = mock_store

        result = cli_runner.invoke(app, ["group", "delete", "baseline", "--yes"])

        assert result.exit_code == 0
        assert "Deleted" in result.stdout
        mock_store.delete.assert_called_once_with("baseline")

    @patch("src.storage.GroupStore")
    @patch("src.storage.Database")
    def test_delete_group_not_found(self, mock_db_cls, mock_store_cls, cli_runner):
        mock_store = MagicMock()
        mock_store.exists.return_value = False
        mock_store_cls.return_value = mock_store

        result = cli_runner.invoke(app, ["group", "delete", "missing", "--yes"])

        assert result.exit_code == 1
        assert "not found" in result.stdout

    @patch("src.storage.GroupStore")
    @patch("src.storage.Database")
    def test_delete_group_cancelled(self, mock_db_cls, mock_store_cls, cli_runner):
        mock_store = MagicMock()
        mock_store.exists.return_value = True
        mock_store_cls.return_value = mock_store

        result = cli_runner.invoke(app, ["group", "delete", "baseline"], input="n\n")

        assert result.exit_code == 0
        assert "Cancelled" in result.stdout
        mock_store.delete.assert_not_called()


# ---------------------------------------------------------------------------
# group compare
# ---------------------------------------------------------------------------


class TestGroupCompare:
    @patch("src.storage.GroupStore")
    @patch("src.storage.Database")
    def test_compare_summary(self, mock_db_cls, mock_store_cls, cli_runner):
        mock_store = MagicMock()
        mock_store.compare_snapshot.return_value = {
            "total_in_group": 10,
            "total_in_snapshot": 12,
            "matched": 8,
            "missing_from_snapshot": 2,
            "not_in_group": 4,
            "resources": {
                "missing": [{"name": "old-bucket", "resource_type": "s3:bucket"}],
                "extra": [{"name": "new-func", "resource_type": "lambda:function", "arn": "arn:aws:lambda:us-east-1:123:function:new-func"}],
            },
        }
        mock_store_cls.return_value = mock_store

        result = cli_runner.invoke(
            app,
            ["group", "compare", "baseline", "--snapshot", "snap-2025"],
        )

        assert result.exit_code == 0
        assert "Matched" in result.stdout or "8" in result.stdout

    @patch("src.storage.GroupStore")
    @patch("src.storage.Database")
    def test_compare_json_format(self, mock_db_cls, mock_store_cls, cli_runner):
        mock_store = MagicMock()
        mock_store.compare_snapshot.return_value = {
            "total_in_group": 5,
            "total_in_snapshot": 5,
            "matched": 5,
            "missing_from_snapshot": 0,
            "not_in_group": 0,
            "resources": {"missing": [], "extra": []},
        }
        mock_store_cls.return_value = mock_store

        result = cli_runner.invoke(
            app,
            ["group", "compare", "baseline", "--snapshot", "snap-2025", "--format", "json"],
        )

        assert result.exit_code == 0
        assert "total_in_group" in result.stdout

    @patch("src.storage.GroupStore")
    @patch("src.storage.Database")
    def test_compare_with_details(self, mock_db_cls, mock_store_cls, cli_runner):
        mock_store = MagicMock()
        mock_store.compare_snapshot.return_value = {
            "total_in_group": 5,
            "total_in_snapshot": 7,
            "matched": 3,
            "missing_from_snapshot": 2,
            "not_in_group": 4,
            "resources": {
                "missing": [
                    {"name": "bucket-a", "resource_type": "s3:bucket"},
                    {"name": "bucket-b", "resource_type": "s3:bucket"},
                ],
                "extra": [
                    {"name": "func-x", "resource_type": "lambda:function", "arn": "arn:aws:lambda:us-east-1:123:function:func-x"},
                ],
            },
        }
        mock_store_cls.return_value = mock_store

        result = cli_runner.invoke(
            app,
            ["group", "compare", "baseline", "--snapshot", "snap-2025", "--details"],
        )

        assert result.exit_code == 0
        assert "Missing" in result.stdout or "missing" in result.stdout.lower()

    @patch("src.storage.GroupStore")
    @patch("src.storage.Database")
    def test_compare_value_error(self, mock_db_cls, mock_store_cls, cli_runner):
        mock_store = MagicMock()
        mock_store.compare_snapshot.side_effect = ValueError("Group not found")
        mock_store_cls.return_value = mock_store

        result = cli_runner.invoke(
            app,
            ["group", "compare", "missing", "--snapshot", "snap-2025"],
        )

        assert result.exit_code == 1
        assert "Group not found" in result.stdout


# ---------------------------------------------------------------------------
# group add
# ---------------------------------------------------------------------------


class TestGroupAdd:
    @patch("src.storage.GroupStore")
    @patch("src.storage.Database")
    def test_add_resource(self, mock_db_cls, mock_store_cls, cli_runner):
        mock_store = MagicMock()
        mock_store.exists.return_value = True
        mock_store.add_members.return_value = 1
        mock_store_cls.return_value = mock_store

        result = cli_runner.invoke(
            app,
            ["group", "add", "baseline", "--resource", "my-bucket:s3:bucket"],
        )

        assert result.exit_code == 0
        assert "Added" in result.stdout

    @patch("src.storage.GroupStore")
    @patch("src.storage.Database")
    def test_add_resource_already_exists(self, mock_db_cls, mock_store_cls, cli_runner):
        mock_store = MagicMock()
        mock_store.exists.return_value = True
        mock_store.add_members.return_value = 0
        mock_store_cls.return_value = mock_store

        result = cli_runner.invoke(
            app,
            ["group", "add", "baseline", "--resource", "my-bucket:s3:bucket"],
        )

        assert result.exit_code == 0
        assert "already exists" in result.stdout.lower()

    @patch("src.storage.GroupStore")
    @patch("src.storage.Database")
    def test_add_resource_group_not_found(self, mock_db_cls, mock_store_cls, cli_runner):
        mock_store = MagicMock()
        mock_store.exists.return_value = False
        mock_store_cls.return_value = mock_store

        result = cli_runner.invoke(
            app,
            ["group", "add", "missing", "--resource", "my-bucket:s3:bucket"],
        )

        assert result.exit_code == 1
        assert "not found" in result.stdout

    @patch("src.storage.GroupStore")
    @patch("src.storage.Database")
    def test_add_resource_bad_format(self, mock_db_cls, mock_store_cls, cli_runner):
        mock_store = MagicMock()
        mock_store_cls.return_value = mock_store

        result = cli_runner.invoke(
            app,
            ["group", "add", "baseline", "--resource", "no-colon-here"],
        )

        assert result.exit_code == 1
        assert "name:type" in result.stdout


# ---------------------------------------------------------------------------
# group remove
# ---------------------------------------------------------------------------


class TestGroupRemove:
    @patch("src.storage.GroupStore")
    @patch("src.storage.Database")
    def test_remove_resource(self, mock_db_cls, mock_store_cls, cli_runner):
        mock_store = MagicMock()
        mock_store.exists.return_value = True
        mock_store.remove_member.return_value = True
        mock_store_cls.return_value = mock_store

        result = cli_runner.invoke(
            app,
            ["group", "remove", "baseline", "--resource", "my-bucket:s3:bucket"],
        )

        assert result.exit_code == 0
        assert "Removed" in result.stdout

    @patch("src.storage.GroupStore")
    @patch("src.storage.Database")
    def test_remove_resource_not_in_group(self, mock_db_cls, mock_store_cls, cli_runner):
        mock_store = MagicMock()
        mock_store.exists.return_value = True
        mock_store.remove_member.return_value = False
        mock_store_cls.return_value = mock_store

        result = cli_runner.invoke(
            app,
            ["group", "remove", "baseline", "--resource", "missing:s3:bucket"],
        )

        assert result.exit_code == 0
        assert "not found" in result.stdout.lower()

    @patch("src.storage.GroupStore")
    @patch("src.storage.Database")
    def test_remove_resource_group_not_found(self, mock_db_cls, mock_store_cls, cli_runner):
        mock_store = MagicMock()
        mock_store.exists.return_value = False
        mock_store_cls.return_value = mock_store

        result = cli_runner.invoke(
            app,
            ["group", "remove", "missing", "--resource", "my-bucket:s3:bucket"],
        )

        assert result.exit_code == 1
        assert "not found" in result.stdout

    @patch("src.storage.GroupStore")
    @patch("src.storage.Database")
    def test_remove_resource_bad_format(self, mock_db_cls, mock_store_cls, cli_runner):
        mock_store = MagicMock()
        mock_store_cls.return_value = mock_store

        result = cli_runner.invoke(
            app,
            ["group", "remove", "baseline", "--resource", "no-colon"],
        )

        assert result.exit_code == 1
        assert "name:type" in result.stdout


# ---------------------------------------------------------------------------
# group export
# ---------------------------------------------------------------------------


class TestGroupExport:
    @patch("src.storage.GroupStore")
    @patch("src.storage.Database")
    def test_export_yaml_stdout(self, mock_db_cls, mock_store_cls, cli_runner):
        mock_store = MagicMock()
        mock_store.load.return_value = _make_group()
        mock_store_cls.return_value = mock_store

        result = cli_runner.invoke(
            app,
            ["group", "export", "baseline"],
        )

        assert result.exit_code == 0
        assert "baseline" in result.stdout

    @patch("src.storage.GroupStore")
    @patch("src.storage.Database")
    def test_export_json_stdout(self, mock_db_cls, mock_store_cls, cli_runner):
        mock_store = MagicMock()
        mock_store.load.return_value = _make_group()
        mock_store_cls.return_value = mock_store

        result = cli_runner.invoke(
            app,
            ["group", "export", "baseline", "--format", "json"],
        )

        assert result.exit_code == 0
        assert "baseline" in result.stdout

    @patch("src.storage.GroupStore")
    @patch("src.storage.Database")
    def test_export_csv_stdout(self, mock_db_cls, mock_store_cls, cli_runner):
        mock_store = MagicMock()
        mock_store.load.return_value = _make_group()
        mock_store_cls.return_value = mock_store

        result = cli_runner.invoke(
            app,
            ["group", "export", "baseline", "--format", "csv"],
        )

        assert result.exit_code == 0
        assert "resource_name" in result.stdout
        assert "my-bucket" in result.stdout

    @patch("src.storage.GroupStore")
    @patch("src.storage.Database")
    def test_export_to_file(self, mock_db_cls, mock_store_cls, cli_runner, tmp_path):
        mock_store = MagicMock()
        mock_store.load.return_value = _make_group()
        mock_store_cls.return_value = mock_store

        output_file = str(tmp_path / "out.yaml")

        result = cli_runner.invoke(
            app,
            ["group", "export", "baseline", "--output", output_file],
        )

        assert result.exit_code == 0
        assert "Exported" in result.stdout

    @patch("src.storage.GroupStore")
    @patch("src.storage.Database")
    def test_export_group_not_found(self, mock_db_cls, mock_store_cls, cli_runner):
        mock_store = MagicMock()
        mock_store.load.return_value = None
        mock_store_cls.return_value = mock_store

        result = cli_runner.invoke(
            app,
            ["group", "export", "missing"],
        )

        assert result.exit_code == 1
        assert "not found" in result.stdout
