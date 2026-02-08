"""Tests for the CLI deprecation warning utility."""

import pytest
import typer
import typer.core

from src.cli.deprecation import (
    _is_provided,
    emit_deprecation_warning,
    handle_deprecated_option,
)
from src.cli.main import app


class TestEmitDeprecationWarning:
    """Tests for emit_deprecation_warning."""

    def test_writes_to_stderr(self, capsys):
        emit_deprecation_warning("--regions", "--region")
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "--regions is deprecated" in captured.err
        assert "--region" in captured.err

    def test_includes_version_info(self, capsys):
        emit_deprecation_warning("--old", "--new", since_version="1.4.0", remove_in="2.0.0")
        captured = capsys.readouterr()
        assert "v1.4.0" in captured.err
        assert "v2.0.0" in captured.err

    def test_custom_versions(self, capsys):
        emit_deprecation_warning("--old", "--new", since_version="1.5.0", remove_in="3.0.0")
        captured = capsys.readouterr()
        assert "v1.5.0" in captured.err
        assert "v3.0.0" in captured.err


class TestHandleDeprecatedOption:
    """Tests for handle_deprecated_option."""

    def test_returns_new_value_when_old_not_provided(self):
        result = handle_deprecated_option(
            old_value=None,
            new_value="us-east-1",
            old_name="--regions",
            new_name="--region",
        )
        assert result == "us-east-1"

    def test_returns_old_value_with_warning_when_old_used(self, capsys):
        result = handle_deprecated_option(
            old_value="us-west-2",
            new_value=None,
            old_name="--regions",
            new_name="--region",
        )
        assert result == "us-west-2"
        captured = capsys.readouterr()
        assert "--regions is deprecated" in captured.err

    def test_prefers_new_value_when_both_provided(self, capsys):
        result = handle_deprecated_option(
            old_value="old-val",
            new_value="new-val",
            old_name="--old",
            new_name="--new",
        )
        assert result == "new-val"
        captured = capsys.readouterr()
        assert "--old is deprecated" in captured.err

    def test_returns_default_when_neither_provided(self):
        result = handle_deprecated_option(
            old_value=None,
            new_value=None,
            old_name="--old",
            new_name="--new",
        )
        assert result is None

    def test_handles_bool_false_as_not_provided(self):
        result = handle_deprecated_option(
            old_value=False,
            new_value=False,
            old_name="--force",
            new_name="--yes",
        )
        assert result is False

    def test_handles_bool_true_as_provided(self, capsys):
        result = handle_deprecated_option(
            old_value=True,
            new_value=False,
            old_name="--force",
            new_name="--yes",
        )
        assert result is True
        captured = capsys.readouterr()
        assert "--force is deprecated" in captured.err

    def test_handles_empty_list_as_not_provided(self):
        result = handle_deprecated_option(
            old_value=[],
            new_value=["us-east-1"],
            old_name="--regions",
            new_name="--region",
        )
        assert result == ["us-east-1"]

    def test_handles_nonempty_list_as_provided(self, capsys):
        result = handle_deprecated_option(
            old_value=["us-west-2"],
            new_value=[],
            old_name="--regions",
            new_name="--region",
        )
        assert result == ["us-west-2"]
        captured = capsys.readouterr()
        assert "--regions is deprecated" in captured.err


class TestIsProvided:
    """Tests for _is_provided helper."""

    def test_none_is_not_provided(self):
        assert _is_provided(None) is False

    def test_false_is_not_provided(self):
        assert _is_provided(False) is False

    def test_true_is_provided(self):
        assert _is_provided(True) is True

    def test_empty_list_is_not_provided(self):
        assert _is_provided([]) is False

    def test_nonempty_list_is_provided(self):
        assert _is_provided(["a"]) is True

    def test_empty_string_is_not_provided(self):
        assert _is_provided("") is False

    def test_nonempty_string_is_provided(self):
        assert _is_provided("hello") is True

    def test_zero_is_provided(self):
        assert _is_provided(0) is True

    def test_integer_is_provided(self):
        assert _is_provided(42) is True


def _collect_commands():
    """Recursively collect all commands from the app."""
    commands = []
    try:
        click_app = typer.main.get_command(app)
    except Exception:
        return commands
    if hasattr(click_app, "commands"):
        for name, cmd in click_app.commands.items():
            if hasattr(cmd, "commands"):
                for sub_name, sub_cmd in cmd.commands.items():
                    commands.append((f"{name} {sub_name}", sub_cmd))
            else:
                commands.append((name, cmd))
    return commands


class TestDeprecationAliasesExist:
    """SC-006: Deprecated option names still exist as hidden parameters."""

    EXPECTED_ALIASES = {
        "inventory delete": {"--force": "--yes"},
        "cleanup execute": {"--confirm": "--yes"},
        "cleanup purge": {"--confirm": "--yes"},
    }

    def test_deprecated_aliases_are_hidden(self):
        """Verify deprecated aliases exist as hidden options on their commands."""
        commands = _collect_commands()
        cmd_dict = {path: cmd for path, cmd in commands}

        violations = []
        for cmd_path, aliases in self.EXPECTED_ALIASES.items():
            if cmd_path not in cmd_dict:
                violations.append(f"{cmd_path}: command not found")
                continue
            cmd = cmd_dict[cmd_path]
            for old_name, new_name in aliases.items():
                found = False
                for param in cmd.params:
                    if old_name in getattr(param, "opts", []):
                        found = True
                        if not getattr(param, "hidden", False):
                            violations.append(f"{cmd_path}: {old_name} exists but is not hidden")
                        break
                if not found:
                    violations.append(f"{cmd_path}: deprecated alias {old_name} not found")

        if violations:
            assert False, "Deprecation alias issues:\n  " + "\n  ".join(violations)

    def test_regions_alias_exists_where_region_used(self):
        """Verify --regions hidden alias exists on commands that have --region."""
        commands = _collect_commands()

        violations = []
        for cmd_path, cmd in commands:
            has_region = any("--region" in getattr(p, "opts", []) for p in cmd.params)
            if not has_region:
                continue
            has_regions = any("--regions" in getattr(p, "opts", []) for p in cmd.params)
            if has_regions:
                for param in cmd.params:
                    if "--regions" in getattr(param, "opts", []):
                        if not getattr(param, "hidden", False):
                            violations.append(f"{cmd_path}: --regions exists but is not hidden")

        if violations:
            assert False, "Regions alias issues:\n  " + "\n  ".join(violations)
