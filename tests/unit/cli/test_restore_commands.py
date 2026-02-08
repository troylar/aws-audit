"""Tests for CLI restore commands.

The main app does not currently register a 'restore' subcommand.
These tests verify the app imports correctly and that no restore
command is accidentally exposed.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from src.cli.main import app

runner = CliRunner()


class TestRestoreCommands:
    """Minimal tests since there is no restore subcommand in the app."""

    def test_app_imports_and_help_works(self):
        result = runner.invoke(app, ["--help"])

        assert result.exit_code == 0
        assert "awsinv" in result.stdout.lower() or "AWS Inventory" in result.stdout

    def test_restore_command_not_registered(self):
        result = runner.invoke(app, ["restore", "--help"])

        assert result.exit_code != 0 or "No such command" in result.stdout or "Error" in result.stdout

    def test_cleanup_is_registered(self):
        result = runner.invoke(app, ["cleanup", "--help"])

        assert result.exit_code == 0
        assert "preview" in result.stdout
        assert "execute" in result.stdout
        assert "purge" in result.stdout
