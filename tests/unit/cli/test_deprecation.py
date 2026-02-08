"""Tests verifying old deprecated option names have been fully removed."""

import typer
import typer.core

from src.cli.main import app


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


class TestRemovedOptionNames:
    """Verify old option names have been fully removed from the CLI."""

    REMOVED_OPTIONS = {
        "--regions": "--region",
        "--resource-type": "--type",
        "--export": "--output",
        "--confirm": "--yes",
    }

    def test_no_removed_options_exist(self):
        """Verify none of the old deprecated option names exist on any command."""
        commands = _collect_commands()

        violations = []
        for cmd_path, cmd in commands:
            for param in cmd.params:
                opts = getattr(param, "opts", [])
                for opt in opts:
                    if opt in self.REMOVED_OPTIONS:
                        violations.append(f"{cmd_path}: {opt} should be removed (use {self.REMOVED_OPTIONS[opt]})")

        if violations:
            assert False, "Removed options still present:\n  " + "\n  ".join(violations)

    def test_no_force_on_destructive_commands(self):
        """Verify --force is removed from destructive commands (replaced by --yes)."""
        commands = _collect_commands()
        destructive = {"inventory delete", "cleanup execute", "cleanup purge"}

        violations = []
        for cmd_path, cmd in commands:
            if cmd_path not in destructive:
                continue
            has_force = any("--force" in getattr(p, "opts", []) for p in cmd.params)
            if has_force:
                violations.append(f"{cmd_path}: --force should be removed (use --yes)")

        if violations:
            assert False, "Force flag still present:\n  " + "\n  ".join(violations)
