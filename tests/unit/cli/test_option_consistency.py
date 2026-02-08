"""Automated audit tests for CLI option consistency.

These tests programmatically inspect all Typer commands and verify:
- SC-001: Each short flag has exactly one semantic meaning
- SC-002: Standard option names are consistent across commands
- SC-003: All destructive commands use --yes / -y
- SC-005: Naming convention document exists
- SC-007: AWS terminology clarification in help text
"""

import os
from collections import defaultdict
from typing import Dict, List, Set, Tuple

import typer
import typer.core

from src.cli.main import app


def _collect_commands(typer_app: typer.Typer, prefix: str = "") -> List[Tuple[str, typer.core.TyperCommand]]:
    """Recursively collect all commands from a Typer app."""
    commands = []

    # Get the Click group underlying the Typer app
    try:
        click_app = typer.main.get_command(typer_app)
    except Exception:
        return commands

    if hasattr(click_app, "commands"):
        for name, cmd in click_app.commands.items():
            full_name = f"{prefix} {name}".strip() if prefix else name
            if hasattr(cmd, "commands"):
                # It's a group — recurse
                for sub_name, sub_cmd in cmd.commands.items():
                    sub_full = f"{full_name} {sub_name}"
                    commands.append((sub_full, sub_cmd))
            else:
                commands.append((full_name, cmd))

    # Also get top-level commands (non-group commands registered on app)
    if hasattr(click_app, "params"):
        pass  # Global callback params, not a command

    return commands


def _collect_short_flags(commands: List[Tuple[str, typer.core.TyperCommand]]) -> Dict[str, List[Tuple[str, str]]]:
    """Collect all short flag -> (command_path, long_name) mappings.

    Returns a dict like: {"-f": [("query sql", "--format"), ("snapshot export", "--format")]}
    """
    flag_map: Dict[str, List[Tuple[str, str]]] = defaultdict(list)

    for cmd_path, cmd in commands:
        for param in cmd.params:
            if hasattr(param, "opts"):
                short_flags = [o for o in param.opts if o.startswith("-") and not o.startswith("--")]
                long_names = [o for o in param.opts if o.startswith("--")]
                for sf in short_flags:
                    long_name = long_names[0] if long_names else param.name
                    flag_map[sf].append((cmd_path, long_name))

    return flag_map


# Canonical short flag meanings from contracts/short-flag-map.yaml
CANONICAL_FLAG_MEANINGS = {
    "-a": "--all",
    "-c": "--category",
    "-d": "--description",
    "-e": "--env",
    "-f": "--format",
    "-g": "--group-by",
    "-i": "--inventory",
    "-l": "--limit",
    "-m": "--model-id",
    "-n": "--count",
    "-o": "--output",
    "-p": "--profile",
    "-q": "--quiet",
    "-r": "--region",
    "-s": "--snapshot",
    "-t": "--type",
    "-v": "--verbose",
    "-x": "--exclude-name",
    "-y": "--yes",
}

# Destructive commands that must use --yes / -y
DESTRUCTIVE_COMMANDS = {
    "snapshot delete",
    "inventory delete",
    "group delete",
    "cleanup restore",
    "cleanup execute",
    "cleanup purge",
}


class TestShortFlagConsistency:
    """SC-001: Each short flag has exactly one semantic meaning."""

    def test_no_short_flag_has_multiple_meanings(self):
        """Verify no single-letter flag maps to more than one long-form option."""
        commands = _collect_commands(app)
        flag_map = _collect_short_flags(commands)

        violations = []
        for flag, usages in flag_map.items():
            if flag in ("-h", "--help"):
                continue
            # Collect unique long names for this flag
            unique_meanings = set()
            for cmd_path, long_name in usages:
                unique_meanings.add(long_name)

            if len(unique_meanings) > 1:
                details = [(cmd, ln) for cmd, ln in usages]
                violations.append((flag, details))

        if violations:
            msg_parts = ["Short flag collision(s) found:"]
            for flag, details in violations:
                msg_parts.append(f"\n  {flag}:")
                for cmd, ln in details:
                    msg_parts.append(f"    {cmd}: {ln}")
            assert False, "\n".join(msg_parts)

    def test_short_flags_match_canonical_meanings(self):
        """Verify each short flag, where used, maps to its canonical meaning."""
        commands = _collect_commands(app)
        flag_map = _collect_short_flags(commands)

        violations = []
        for flag, usages in flag_map.items():
            if flag not in CANONICAL_FLAG_MEANINGS:
                continue
            expected = CANONICAL_FLAG_MEANINGS[flag]
            for cmd_path, long_name in usages:
                if long_name != expected:
                    violations.append(f"{flag} on '{cmd_path}': expected {expected}, got {long_name}")

        if violations:
            assert False, "Short flag meaning mismatches:\n  " + "\n  ".join(violations)


class TestConfirmationConsistency:
    """SC-003: All destructive commands use --yes / -y."""

    def test_destructive_commands_use_yes_flag(self):
        """Verify all destructive commands have a --yes option."""
        commands = _collect_commands(app)
        cmd_dict = {path: cmd for path, cmd in commands}

        missing = []
        for cmd_path in DESTRUCTIVE_COMMANDS:
            if cmd_path not in cmd_dict:
                continue
            cmd = cmd_dict[cmd_path]
            has_yes = any(
                "--yes" in getattr(p, "opts", [])
                for p in cmd.params
            )
            if not has_yes:
                # Check for --force or --confirm as alternatives (should be deprecated)
                has_alt = any(
                    "--force" in getattr(p, "opts", []) or "--confirm" in getattr(p, "opts", [])
                    for p in cmd.params
                )
                if has_alt:
                    missing.append(f"{cmd_path}: uses --force/--confirm instead of --yes")
                else:
                    missing.append(f"{cmd_path}: no confirmation flag found")

        if missing:
            assert False, "Destructive commands not using --yes:\n  " + "\n  ".join(missing)


class TestOptionNameConsistency:
    """SC-002: Standard option names are consistent across commands."""

    # Canonical option names and their expected properties
    CANONICAL_OPTIONS = {
        "--snapshot": {"short": "-s", "envvar": "AWSINV_SNAPSHOT_ID"},
        "--region": {"short": "-r", "envvar": "AWSINV_REGION"},
        "--profile": {"short": "-p", "envvar": "AWSINV_PROFILE"},
        "--inventory": {"short": "-i", "envvar": "AWSINV_INVENTORY_ID"},
        "--format": {"short": "-f"},
        "--output": {"short": "-o"},
        "--type": {"short": "-t"},
        "--yes": {"short": "-y"},
        "--verbose": {"short": "-v"},
        "--quiet": {"short": "-q"},
        "--limit": {"short": "-l"},
    }

    # Deprecated names that should NOT appear as primary (non-hidden) options
    # Format: old_name -> (canonical_name, set of command paths where deprecation applies, or None for all)
    DEPRECATED_NAMES = {
        "--regions": ("--region", None),
        "--resource-type": ("--type", None),
        "--export": ("--output", None),
        "--force": ("--yes", {"inventory delete", "cleanup execute", "cleanup purge"}),
        "--confirm": ("--yes", None),
    }

    def test_no_deprecated_names_as_primary_options(self):
        """Verify deprecated option names are hidden, not primary."""
        commands = _collect_commands(app)

        violations = []
        for cmd_path, cmd in commands:
            for param in cmd.params:
                opts = getattr(param, "opts", [])
                is_hidden = getattr(param, "hidden", False)
                for opt in opts:
                    if opt in self.DEPRECATED_NAMES and not is_hidden:
                        canonical, scoped_cmds = self.DEPRECATED_NAMES[opt]
                        if scoped_cmds is not None and cmd_path not in scoped_cmds:
                            continue
                        violations.append(
                            f"{cmd_path}: {opt} should be hidden (deprecated in favor of {canonical})"
                        )

        if violations:
            assert False, "Deprecated option names still visible:\n  " + "\n  ".join(violations)


class TestEnvvarConsistency:
    """FR-010: Environment variable support is consistent."""

    ENVVAR_MAP = {
        "--snapshot": ["AWSINV_SNAPSHOT_ID"],
        "--region": ["AWSINV_REGION", "AWS_REGION"],
        "--profile": ["AWSINV_PROFILE", "AWS_PROFILE"],
        "--inventory": ["AWSINV_INVENTORY_ID"],
        "--storage-path": ["AWSINV_STORAGE_PATH", "AWS_INVENTORY_STORAGE_PATH"],
    }

    def test_options_with_required_envvars(self):
        """Verify every command with --snapshot, --region, --inventory, --profile has envvar."""
        commands = _collect_commands(app)

        violations = []
        for cmd_path, cmd in commands:
            for param in cmd.params:
                opts = getattr(param, "opts", [])
                is_hidden = getattr(param, "hidden", False)
                if is_hidden:
                    continue
                for opt in opts:
                    if opt in self.ENVVAR_MAP:
                        envvar = getattr(param, "envvar", None)
                        expected = self.ENVVAR_MAP[opt]
                        if envvar is None:
                            violations.append(f"{cmd_path}: {opt} missing envvar (expected {expected[0]})")
                        else:
                            envvar_list = envvar if isinstance(envvar, (list, tuple)) else [envvar]
                            if envvar_list[0] != expected[0]:
                                violations.append(
                                    f"{cmd_path}: {opt} has envvar {envvar_list[0]}, expected {expected[0]}"
                                )

        if violations:
            assert False, "Environment variable inconsistencies:\n  " + "\n  ".join(violations)


class TestConventionDocExists:
    """SC-005: Naming convention document exists."""

    def test_cli_conventions_doc_exists(self):
        """Verify docs/cli-conventions.md exists."""
        doc_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "docs", "cli-conventions.md")
        assert os.path.exists(doc_path), "docs/cli-conventions.md not found"


class TestTerminologyClarity:
    """SC-007: AWS terminology clarification in help text."""

    # Groups that use AWS-conflicting terms and need disambiguation
    TERMINOLOGY_CHECKS = {
        "snapshot": "not EBS/RDS snapshot",
        "inventory": "not AWS SSM Inventory",
        "security": "not AWS Security Hub",
        "guardrails": "not AWS Control Tower",
        "group": "not IAM or Security Group",
    }

    def test_group_help_includes_disambiguation(self):
        """Verify command groups with AWS-conflicting names include clarification."""
        try:
            click_app = typer.main.get_command(app)
        except Exception:
            pytest.skip("Could not resolve Typer app")

        violations = []
        for group_name, expected_text in self.TERMINOLOGY_CHECKS.items():
            if group_name in click_app.commands:
                group = click_app.commands[group_name]
                help_text = getattr(group, "help", "") or ""
                if expected_text.lower() not in help_text.lower():
                    violations.append(
                        f"'{group_name}' group help missing disambiguation: expected '{expected_text}'"
                    )

        if violations:
            assert False, "Missing AWS terminology clarification:\n  " + "\n  ".join(violations)
