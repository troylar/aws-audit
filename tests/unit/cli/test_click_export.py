"""Tests for the Click export module used by mkdocs-click."""

import click

from src.cli._click_export import cli


class TestClickExport:
    """Tests for the cli object exported for mkdocs-click."""

    def test_cli_is_click_group(self):
        """Test that cli is a Click BaseCommand (Group or MultiCommand)."""
        assert isinstance(cli, click.BaseCommand)

    def test_cli_is_group_with_subcommands(self):
        """Test that cli is a Click Group containing subcommands."""
        assert isinstance(cli, click.Group)
        assert len(cli.commands) > 0

    def test_cli_derived_from_typer_app(self):
        """Test that cli was derived from the Typer app in main."""
        import typer.main

        from src.cli.main import app

        expected = typer.main.get_command(app)
        assert type(cli) is type(expected)
        assert set(cli.commands.keys()) == set(expected.commands.keys())
