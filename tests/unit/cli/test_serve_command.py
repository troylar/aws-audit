"""Tests for CLI serve command (web UI)."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from src.cli.main import app

runner = CliRunner()


def _make_uvicorn_mock() -> MagicMock:
    mock = MagicMock()
    mock.__name__ = "uvicorn"
    mock.__spec__ = None
    mock.__path__ = []
    mock.__file__ = None
    mock.__loader__ = None
    mock.__package__ = "uvicorn"
    return mock


def _make_config_mock(storage_path: str = "/tmp/snapshots") -> MagicMock:
    mock_cfg = MagicMock()
    mock_cfg.storage_path = storage_path
    mock_cfg.log_level = "INFO"
    mock_cfg.aws_profile = None
    mock_cfg.regions = []
    mock_cfg.resource_types = []
    return mock_cfg


class TestServeCommand:
    """Tests for awsinv serve."""

    def test_serve_with_defaults(self):
        mock_uvicorn = _make_uvicorn_mock()
        mock_app_instance = MagicMock()
        mock_cfg = _make_config_mock()

        with (
            patch.dict(sys.modules, {"uvicorn": mock_uvicorn}),
            patch("src.web.app.create_app", return_value=mock_app_instance),
            patch("src.cli.config.Config.load", return_value=mock_cfg),
        ):
            result = runner.invoke(app, ["serve", "--no-open"])

        assert result.exit_code == 0, f"stdout: {result.stdout}\nexception: {result.exception}"
        mock_uvicorn.run.assert_called_once_with(
            mock_app_instance,
            host="127.0.0.1",
            port=8080,
            reload=False,
            log_level="info",
        )

    def test_serve_with_custom_host_and_port(self):
        mock_uvicorn = _make_uvicorn_mock()
        mock_app_instance = MagicMock()
        mock_cfg = _make_config_mock()

        with (
            patch.dict(sys.modules, {"uvicorn": mock_uvicorn}),
            patch("src.web.app.create_app", return_value=mock_app_instance),
            patch("src.cli.config.Config.load", return_value=mock_cfg),
        ):
            result = runner.invoke(
                app, ["serve", "--host", "0.0.0.0", "--port", "9090", "--no-open"]
            )

        assert result.exit_code == 0, f"stdout: {result.stdout}\nexception: {result.exception}"
        mock_uvicorn.run.assert_called_once_with(
            mock_app_instance,
            host="0.0.0.0",
            port=9090,
            reload=False,
            log_level="info",
        )

    def test_serve_with_reload_flag(self):
        mock_uvicorn = _make_uvicorn_mock()
        mock_app_instance = MagicMock()
        mock_cfg = _make_config_mock()

        with (
            patch.dict(sys.modules, {"uvicorn": mock_uvicorn}),
            patch("src.web.app.create_app", return_value=mock_app_instance),
            patch("src.cli.config.Config.load", return_value=mock_cfg),
        ):
            result = runner.invoke(app, ["serve", "--reload", "--no-open"])

        assert result.exit_code == 0, f"stdout: {result.stdout}\nexception: {result.exception}"
        mock_uvicorn.run.assert_called_once_with(
            mock_app_instance,
            host="127.0.0.1",
            port=8080,
            reload=True,
            log_level="info",
        )

    def test_serve_help(self):
        result = runner.invoke(app, ["serve", "--help"])

        assert result.exit_code == 0
        assert "--host" in result.stdout
        assert "--port" in result.stdout
        assert "--reload" in result.stdout
