"""Unit tests for the generate CLI command."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from src.cli.main import app

runner = CliRunner()


def _make_generation_result(
    success: bool = True,
    output_dir: str = "./terraform",
    generated_files: list | None = None,
    errors: list | None = None,
    guardrails_blocked: bool = False,
    guardrails_report: dict | None = None,
) -> MagicMock:
    result = MagicMock()
    result.success = success
    result.output_dir = output_dir
    result.generated_files = generated_files or ["main.tf"]
    result.layers = []
    result.errors = errors or []
    result.validation_errors = []
    result.guardrails_blocked = guardrails_blocked
    result.guardrails_report = guardrails_report
    return result


def _make_mock_snapshot(name: str = "test-snapshot") -> MagicMock:
    snapshot = MagicMock()
    snapshot.name = name
    snapshot.resources = [
        {
            "resource_type": "AWS::EC2::Instance",
            "name": "test-instance",
            "arn": "arn:aws:ec2:us-east-1:123456789012:instance/i-abc123",
            "config": {"InstanceType": "t3.micro"},
        }
    ]
    snapshot.resource_count = len(snapshot.resources)
    return snapshot


class TestGenerateTerraform:
    """Tests for `awsinv generate terraform` command."""

    @patch("src.cli.generation_progress.GenerationProgressDisplay")
    @patch("src.generate.terraform_generator.generate_terraform")
    def test_generate_terraform_success(
        self,
        mock_generate: MagicMock,
        mock_progress_cls: MagicMock,
    ) -> None:
        """Generate terraform with valid snapshot name produces success."""
        mock_generate.return_value = _make_generation_result()
        mock_progress = MagicMock()
        mock_progress_cls.return_value = mock_progress

        result = runner.invoke(
            app,
            ["generate", "terraform", "my-snapshot", "--output", "/tmp/tf-out"],
        )

        assert result.exit_code == 0
        mock_generate.assert_called_once()
        call_kwargs = mock_generate.call_args
        assert call_kwargs.kwargs["snapshot_name"] == "my-snapshot"
        assert call_kwargs.kwargs["output_dir"] == "/tmp/tf-out"

    def test_generate_requires_snapshot_or_from_file(self) -> None:
        """Generate command fails when neither snapshot nor --from-file given."""
        result = runner.invoke(app, ["generate", "terraform"])

        assert result.exit_code != 0
        assert "snapshot" in result.stdout.lower() or "from-file" in result.stdout.lower()

    def test_generate_unknown_format_fails(self) -> None:
        """Generate command rejects unknown format values."""
        result = runner.invoke(app, ["generate", "pulumi", "my-snapshot"])

        assert result.exit_code != 0
        assert "unknown format" in result.stdout.lower() or "pulumi" in result.stdout.lower()

    @patch("src.cli.generation_progress.GenerationProgressDisplay")
    @patch("src.generate.terraform_generator.generate_terraform")
    def test_generate_terraform_failure_exits_nonzero(
        self,
        mock_generate: MagicMock,
        mock_progress_cls: MagicMock,
    ) -> None:
        """Generate command exits with code 1 when generation fails."""
        mock_generate.return_value = _make_generation_result(
            success=False,
            errors=["Bedrock invocation failed"],
        )
        mock_progress_cls.return_value = MagicMock()

        result = runner.invoke(
            app,
            ["generate", "terraform", "my-snapshot", "--output", "/tmp/tf-out"],
        )

        assert result.exit_code == 1
        assert "error" in result.stdout.lower()


class TestGenerateDryRun:
    """Tests for `awsinv generate --dry-run`."""

    @patch("src.snapshot.storage.SnapshotStorage")
    def test_dry_run_with_snapshot(
        self,
        mock_storage_cls: MagicMock,
    ) -> None:
        """Dry run loads snapshot and displays summary without generating."""
        mock_storage = MagicMock()
        mock_snapshot = _make_mock_snapshot()
        mock_storage.load_snapshot.return_value = mock_snapshot
        mock_storage_cls.return_value = mock_storage

        result = runner.invoke(
            app,
            [
                "generate",
                "terraform",
                "my-snapshot",
                "--dry-run",
                "--no-best-practices",
            ],
        )

        assert result.exit_code == 0
        assert "dry run" in result.stdout.lower()
        mock_storage.load_snapshot.assert_called_once_with("my-snapshot")

    @patch("src.snapshot.storage.SnapshotStorage")
    def test_dry_run_nonexistent_snapshot(
        self,
        mock_storage_cls: MagicMock,
    ) -> None:
        """Dry run with nonexistent snapshot prints error and exits 1."""
        mock_storage = MagicMock()
        mock_storage.load_snapshot.return_value = None
        mock_storage_cls.return_value = mock_storage

        result = runner.invoke(
            app,
            [
                "generate",
                "terraform",
                "nonexistent",
                "--dry-run",
                "--no-best-practices",
            ],
        )

        assert result.exit_code != 0
        assert "not found" in result.stdout.lower()


class TestGenerateCdk:
    """Tests for CDK format generation."""

    @patch("src.cli.generation_progress.GenerationProgressDisplay")
    @patch("src.generate.cdk_generator.generate_cdk")
    def test_generate_cdk_typescript(
        self,
        mock_generate_cdk: MagicMock,
        mock_progress_cls: MagicMock,
    ) -> None:
        """Generate cdk-typescript calls generate_cdk with correct format."""
        mock_generate_cdk.return_value = _make_generation_result(output_dir="./cdk-out")
        mock_progress_cls.return_value = MagicMock()

        result = runner.invoke(
            app,
            ["generate", "cdk-typescript", "my-snapshot", "--output", "./cdk-out"],
        )

        assert result.exit_code == 0
        mock_generate_cdk.assert_called_once()
        call_kwargs = mock_generate_cdk.call_args
        assert call_kwargs.kwargs["snapshot_name"] == "my-snapshot"
        assert call_kwargs.kwargs["output_format"] == "cdk-typescript"

    @patch("src.cli.generation_progress.GenerationProgressDisplay")
    @patch("src.generate.cdk_generator.generate_cdk")
    def test_generate_cdk_python(
        self,
        mock_generate_cdk: MagicMock,
        mock_progress_cls: MagicMock,
    ) -> None:
        """Generate cdk-python calls generate_cdk with correct format."""
        mock_generate_cdk.return_value = _make_generation_result(output_dir="./cdk-py")
        mock_progress_cls.return_value = MagicMock()

        result = runner.invoke(
            app,
            ["generate", "cdk-python", "my-snapshot", "--output", "./cdk-py"],
        )

        assert result.exit_code == 0
        mock_generate_cdk.assert_called_once()
        call_kwargs = mock_generate_cdk.call_args
        assert call_kwargs.kwargs["output_format"] == "cdk-python"


class TestGenerateOptions:
    """Tests for generate command options."""

    @patch("src.cli.generation_progress.GenerationProgressDisplay")
    @patch("src.generate.terraform_generator.generate_terraform")
    def test_model_id_and_region_passed(
        self,
        mock_generate: MagicMock,
        mock_progress_cls: MagicMock,
    ) -> None:
        """--model-id and --region are forwarded to the generator."""
        mock_generate.return_value = _make_generation_result()
        mock_progress_cls.return_value = MagicMock()

        result = runner.invoke(
            app,
            [
                "generate",
                "terraform",
                "my-snapshot",
                "--model-id",
                "anthropic.claude-3-sonnet",
                "--region",
                "us-west-2",
            ],
        )

        assert result.exit_code == 0
        call_kwargs = mock_generate.call_args.kwargs
        assert call_kwargs["model_id"] == "anthropic.claude-3-sonnet"
        assert call_kwargs["region"] == "us-west-2"

    @patch("src.cli.generation_progress.GenerationProgressDisplay")
    @patch("src.generate.terraform_generator.generate_terraform")
    def test_no_best_practices_flag(
        self,
        mock_generate: MagicMock,
        mock_progress_cls: MagicMock,
    ) -> None:
        """--no-best-practices disables best-practice guardrails."""
        mock_generate.return_value = _make_generation_result()
        mock_progress_cls.return_value = MagicMock()

        result = runner.invoke(
            app,
            [
                "generate",
                "terraform",
                "my-snapshot",
                "--no-best-practices",
            ],
        )

        assert result.exit_code == 0
        call_kwargs = mock_generate.call_args.kwargs
        assert call_kwargs["best_practices_enabled"] is False

    @patch("src.cli.generation_progress.GenerationProgressDisplay")
    @patch("src.generate.terraform_generator.generate_terraform")
    def test_guardrails_flags_passed(
        self,
        mock_generate: MagicMock,
        mock_progress_cls: MagicMock,
    ) -> None:
        """--guardrails and related flags are forwarded to the generator."""
        mock_generate.return_value = _make_generation_result()
        mock_progress_cls.return_value = MagicMock()

        result = runner.invoke(
            app,
            [
                "generate",
                "terraform",
                "my-snapshot",
                "--guardrails",
                "--guardrails-strict",
                "--guardrails-env",
                "production",
            ],
        )

        assert result.exit_code == 0
        call_kwargs = mock_generate.call_args.kwargs
        assert call_kwargs["guardrails_enabled"] is True
        assert call_kwargs["guardrails_strict"] is True
        assert call_kwargs["guardrails_environment"] == "production"

    @patch("src.cli.generation_progress.GenerationProgressDisplay")
    @patch("src.generate.terraform_generator.generate_terraform")
    def test_from_file_option(
        self,
        mock_generate: MagicMock,
        mock_progress_cls: MagicMock,
    ) -> None:
        """--from-file passes input_file to the generator instead of snapshot_name."""
        mock_generate.return_value = _make_generation_result()
        mock_progress_cls.return_value = MagicMock()

        result = runner.invoke(
            app,
            [
                "generate",
                "terraform",
                "--from-file",
                "/tmp/inventory.json",
            ],
        )

        assert result.exit_code == 0
        call_kwargs = mock_generate.call_args.kwargs
        assert call_kwargs["input_file"] == "/tmp/inventory.json"
        assert call_kwargs["snapshot_name"] is None
