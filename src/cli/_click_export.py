"""Expose the Typer app as a Click group for mkdocs-click."""

import typer.main

from src.cli.main import app

cli = typer.main.get_command(app)
