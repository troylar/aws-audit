"""Tests for CLI lambda commands."""

import base64
import json
import os
import tempfile
import zipfile
from datetime import datetime, timezone
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from src.cli.main import app
from src.models.resource import Resource
from src.models.snapshot import Snapshot


@pytest.fixture
def cli_runner():
    """Create a Typer CLI runner."""
    return CliRunner()


@pytest.fixture
def sample_lambda_code():
    """Create a sample Lambda deployment package as base64."""
    # Create a zip file with sample Python code
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("handler.py", 'def lambda_handler(event, context):\n    return {"statusCode": 200}\n')
        zf.writestr("utils.py", "# Utility functions\ndef helper():\n    pass\n")
        zf.writestr("requirements.txt", "boto3>=1.28.0\n")
    zip_buffer.seek(0)
    return base64.b64encode(zip_buffer.read()).decode("utf-8")


@pytest.fixture
def sample_js_lambda_code():
    """Create a sample JavaScript Lambda deployment package."""
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("index.js", "exports.handler = async (event) => {\n    return { statusCode: 200 };\n};\n")
        zf.writestr("package.json", '{"name": "my-lambda", "version": "1.0.0"}\n')
    zip_buffer.seek(0)
    return base64.b64encode(zip_buffer.read()).decode("utf-8")


@pytest.fixture
def mock_snapshot_with_lambdas(sample_lambda_code, sample_js_lambda_code):
    """Create a mock snapshot with Lambda functions."""
    resources = [
        Resource(
            arn="arn:aws:lambda:us-east-1:123456789012:function:my-python-func",
            resource_type="AWS::Lambda::Function",
            name="my-python-func",
            region="us-east-1",
            config_hash="hash1",
            raw_config={
                "Runtime": "python3.11",
                "Handler": "handler.lambda_handler",
                "_code": {
                    "code_stored": True,
                    "code_base64": sample_lambda_code,
                    "code_sha256": "abc123def456",
                },
            },
        ),
        Resource(
            arn="arn:aws:lambda:us-east-1:123456789012:function:my-js-func",
            resource_type="AWS::Lambda::Function",
            name="my-js-func",
            region="us-east-1",
            config_hash="hash2",
            raw_config={
                "Runtime": "nodejs18.x",
                "Handler": "index.handler",
                "_code": {
                    "code_stored": True,
                    "code_base64": sample_js_lambda_code,
                    "code_sha256": "xyz789abc012",
                },
            },
        ),
        Resource(
            arn="arn:aws:lambda:us-east-1:123456789012:function:large-func",
            resource_type="AWS::Lambda::Function",
            name="large-func",
            region="us-east-1",
            config_hash="hash3",
            raw_config={
                "Runtime": "python3.11",
                "Handler": "handler.main",
                "_code": {
                    "code_stored": False,
                    "code_sha256": "largehash123456",
                },
            },
        ),
        Resource(
            arn="arn:aws:lambda:us-east-1:123456789012:function:s3-deployed",
            resource_type="AWS::Lambda::Function",
            name="s3-deployed",
            region="us-east-1",
            config_hash="hash4",
            raw_config={
                "Runtime": "python3.11",
                "Handler": "handler.lambda_handler",
                "_code": {
                    "code_stored": True,
                    "code_base64": sample_lambda_code,
                    "code_sha256": "s3hash789",
                    "s3_bucket": "my-code-bucket",
                    "s3_key": "deployments/code.zip",
                },
            },
        ),
        # Non-Lambda resource to ensure filtering works
        Resource(
            arn="arn:aws:s3:::my-bucket",
            resource_type="AWS::S3::Bucket",
            name="my-bucket",
            region="us-east-1",
            config_hash="hash5",
            raw_config={"BucketName": "my-bucket"},
        ),
    ]

    snapshot = Snapshot(
        name="test-snapshot",
        created_at=datetime.now(timezone.utc),
        account_id="123456789012",
        regions=["us-east-1"],
        resources=resources,
    )
    return snapshot


class TestLambdaListCommand:
    """Tests for awsinv lambda list command."""

    @patch("src.cli.main.SnapshotStorage")
    def test_list_lambdas_with_code(self, mock_storage_cls, cli_runner, mock_snapshot_with_lambdas):
        """Test listing Lambda functions with stored code."""
        mock_storage = MagicMock()
        mock_storage.load_snapshot.return_value = mock_snapshot_with_lambdas
        mock_storage_cls.return_value = mock_storage

        result = cli_runner.invoke(app, ["lambda", "list", "test-snapshot"])

        assert result.exit_code == 0
        assert "my-python-func" in result.stdout
        assert "my-js-func" in result.stdout
        assert "python3.11" in result.stdout
        assert "nodejs18.x" in result.stdout
        assert "✓" in result.stdout  # Code stored indicator
        assert "3/4 functions have code stored" in result.stdout

    @patch("src.cli.main.SnapshotStorage")
    def test_list_lambdas_show_all(self, mock_storage_cls, cli_runner, mock_snapshot_with_lambdas):
        """Test listing all Lambda functions including those without code."""
        mock_storage = MagicMock()
        mock_storage.load_snapshot.return_value = mock_snapshot_with_lambdas
        mock_storage_cls.return_value = mock_storage

        result = cli_runner.invoke(app, ["lambda", "list", "test-snapshot", "--all"])

        assert result.exit_code == 0
        assert "large-func" in result.stdout
        assert ">10MB" in result.stdout  # Large function indicator

    @patch("src.cli.main.SnapshotStorage")
    def test_list_lambdas_active_snapshot(self, mock_storage_cls, cli_runner, mock_snapshot_with_lambdas):
        """Test listing Lambda functions from active snapshot."""
        mock_storage = MagicMock()
        mock_storage.get_active_snapshot_name.return_value = "test-snapshot"
        mock_storage.load_snapshot.return_value = mock_snapshot_with_lambdas
        mock_storage_cls.return_value = mock_storage

        result = cli_runner.invoke(app, ["lambda", "list"])

        assert result.exit_code == 0
        assert "my-python-func" in result.stdout

    @patch("src.cli.main.SnapshotStorage")
    def test_list_lambdas_no_active_snapshot(self, mock_storage_cls, cli_runner):
        """Test error when no active snapshot and none specified."""
        mock_storage = MagicMock()
        mock_storage.get_active_snapshot_name.return_value = None
        mock_storage_cls.return_value = mock_storage

        result = cli_runner.invoke(app, ["lambda", "list"])

        assert result.exit_code == 1
        assert "No active snapshot" in result.stdout

    @patch("src.cli.main.SnapshotStorage")
    def test_list_lambdas_no_functions(self, mock_storage_cls, cli_runner):
        """Test listing when snapshot has no Lambda functions."""
        mock_storage = MagicMock()
        empty_snapshot = Snapshot(
            name="empty-snapshot",
            created_at=datetime.now(timezone.utc),
            account_id="123456789012",
            regions=["us-east-1"],
            resources=[
                Resource(
                    arn="arn:aws:s3:::my-bucket",
                    resource_type="AWS::S3::Bucket",
                    name="my-bucket",
                    region="us-east-1",
                    config_hash="hash1",
                )
            ],
        )
        mock_storage.load_snapshot.return_value = empty_snapshot
        mock_storage_cls.return_value = mock_storage

        result = cli_runner.invoke(app, ["lambda", "list", "empty-snapshot"])

        assert result.exit_code == 0
        assert "No Lambda functions found" in result.stdout

    @patch("src.cli.main.SnapshotStorage")
    def test_list_shows_s3_source(self, mock_storage_cls, cli_runner, mock_snapshot_with_lambdas):
        """Test that S3-deployed functions show S3 as source."""
        mock_storage = MagicMock()
        mock_storage.load_snapshot.return_value = mock_snapshot_with_lambdas
        mock_storage_cls.return_value = mock_storage

        result = cli_runner.invoke(app, ["lambda", "list", "test-snapshot"])

        assert result.exit_code == 0
        assert "S3" in result.stdout  # S3 source indicator


class TestLambdaExtractCommand:
    """Tests for awsinv lambda extract command."""

    @patch("src.cli.main.SnapshotStorage")
    def test_extract_single_function(self, mock_storage_cls, cli_runner, mock_snapshot_with_lambdas):
        """Test extracting a single Lambda function's code."""
        mock_storage = MagicMock()
        mock_storage.get_active_snapshot_name.return_value = "test-snapshot"
        mock_storage.load_snapshot.return_value = mock_snapshot_with_lambdas
        mock_storage_cls.return_value = mock_storage

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = os.path.join(tmpdir, "lambda_code")

            result = cli_runner.invoke(app, ["lambda", "extract", "my-python-func", "--output", output_dir])

            assert result.exit_code == 0
            assert "my-python-func" in result.stdout
            assert "3 files" in result.stdout  # handler.py, utils.py, requirements.txt

            # Verify files were extracted
            func_dir = os.path.join(output_dir, "my-python-func")
            assert os.path.exists(func_dir)
            assert os.path.exists(os.path.join(func_dir, "handler.py"))
            assert os.path.exists(os.path.join(func_dir, "utils.py"))

    @patch("src.cli.main.SnapshotStorage")
    def test_extract_all_functions(self, mock_storage_cls, cli_runner, mock_snapshot_with_lambdas):
        """Test extracting all Lambda functions' code."""
        mock_storage = MagicMock()
        mock_storage.get_active_snapshot_name.return_value = "test-snapshot"
        mock_storage.load_snapshot.return_value = mock_snapshot_with_lambdas
        mock_storage_cls.return_value = mock_storage

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = os.path.join(tmpdir, "all_code")

            result = cli_runner.invoke(app, ["lambda", "extract", "all", "--output", output_dir])

            assert result.exit_code == 0
            assert "Extracting 3 Lambda function" in result.stdout  # 3 with stored code

            # Verify directories created
            assert os.path.exists(os.path.join(output_dir, "my-python-func"))
            assert os.path.exists(os.path.join(output_dir, "my-js-func"))
            assert os.path.exists(os.path.join(output_dir, "s3-deployed"))

    @patch("src.cli.main.SnapshotStorage")
    def test_extract_flatten_option(self, mock_storage_cls, cli_runner, mock_snapshot_with_lambdas):
        """Test extracting with flatten option (no subdirectories)."""
        mock_storage = MagicMock()
        mock_storage.get_active_snapshot_name.return_value = "test-snapshot"
        mock_storage.load_snapshot.return_value = mock_snapshot_with_lambdas
        mock_storage_cls.return_value = mock_storage

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = os.path.join(tmpdir, "flat_code")

            result = cli_runner.invoke(
                app, ["lambda", "extract", "my-python-func", "--output", output_dir, "--flatten"]
            )

            assert result.exit_code == 0
            # Files should be directly in output_dir, not in subdirectory
            assert os.path.exists(os.path.join(output_dir, "handler.py"))
            assert not os.path.exists(os.path.join(output_dir, "my-python-func"))

    @patch("src.cli.main.SnapshotStorage")
    def test_extract_function_not_found(self, mock_storage_cls, cli_runner, mock_snapshot_with_lambdas):
        """Test error when function not found."""
        mock_storage = MagicMock()
        mock_storage.get_active_snapshot_name.return_value = "test-snapshot"
        mock_storage.load_snapshot.return_value = mock_snapshot_with_lambdas
        mock_storage_cls.return_value = mock_storage

        result = cli_runner.invoke(app, ["lambda", "extract", "nonexistent-func"])

        assert result.exit_code == 1
        assert "not found" in result.stdout
        assert "Available:" in result.stdout

    @patch("src.cli.main.SnapshotStorage")
    def test_extract_large_function_warning(self, mock_storage_cls, cli_runner, mock_snapshot_with_lambdas):
        """Test warning when trying to extract function without stored code."""
        mock_storage = MagicMock()
        mock_storage.get_active_snapshot_name.return_value = "test-snapshot"
        mock_storage.load_snapshot.return_value = mock_snapshot_with_lambdas
        mock_storage_cls.return_value = mock_storage

        with tempfile.TemporaryDirectory() as tmpdir:
            result = cli_runner.invoke(app, ["lambda", "extract", "large-func", "--output", tmpdir])

            assert "No code stored" in result.stdout or ">10MB" in result.stdout

    @patch("src.cli.main.SnapshotStorage")
    def test_extract_with_snapshot_option(self, mock_storage_cls, cli_runner, mock_snapshot_with_lambdas):
        """Test extracting with explicit snapshot option."""
        mock_storage = MagicMock()
        mock_storage.load_snapshot.return_value = mock_snapshot_with_lambdas
        mock_storage_cls.return_value = mock_storage

        with tempfile.TemporaryDirectory() as tmpdir:
            result = cli_runner.invoke(
                app,
                ["lambda", "extract", "my-python-func", "--snapshot", "test-snapshot", "--output", tmpdir],
            )

            assert result.exit_code == 0
            mock_storage.load_snapshot.assert_called_once_with("test-snapshot")


class TestLambdaShowCommand:
    """Tests for awsinv lambda show command."""

    @patch("src.cli.main.SnapshotStorage")
    def test_show_list_files(self, mock_storage_cls, cli_runner, mock_snapshot_with_lambdas):
        """Test listing files in Lambda package."""
        mock_storage = MagicMock()
        mock_storage.get_active_snapshot_name.return_value = "test-snapshot"
        mock_storage.load_snapshot.return_value = mock_snapshot_with_lambdas
        mock_storage_cls.return_value = mock_storage

        result = cli_runner.invoke(app, ["lambda", "show", "my-python-func", "--list"])

        assert result.exit_code == 0
        assert "handler.py" in result.stdout
        assert "utils.py" in result.stdout
        assert "requirements.txt" in result.stdout
        assert "3 files" in result.stdout

    @patch("src.cli.main.SnapshotStorage")
    def test_show_auto_detect_handler(self, mock_storage_cls, cli_runner, mock_snapshot_with_lambdas):
        """Test auto-detecting and showing handler file."""
        mock_storage = MagicMock()
        mock_storage.get_active_snapshot_name.return_value = "test-snapshot"
        mock_storage.load_snapshot.return_value = mock_snapshot_with_lambdas
        mock_storage_cls.return_value = mock_storage

        result = cli_runner.invoke(app, ["lambda", "show", "my-python-func"])

        assert result.exit_code == 0
        assert "handler.py" in result.stdout
        assert "lambda_handler" in result.stdout
        assert "def" in result.stdout

    @patch("src.cli.main.SnapshotStorage")
    def test_show_specific_file(self, mock_storage_cls, cli_runner, mock_snapshot_with_lambdas):
        """Test showing a specific file from package."""
        mock_storage = MagicMock()
        mock_storage.get_active_snapshot_name.return_value = "test-snapshot"
        mock_storage.load_snapshot.return_value = mock_snapshot_with_lambdas
        mock_storage_cls.return_value = mock_storage

        result = cli_runner.invoke(app, ["lambda", "show", "my-python-func", "--file", "utils.py"])

        assert result.exit_code == 0
        assert "utils.py" in result.stdout
        assert "helper" in result.stdout

    @patch("src.cli.main.SnapshotStorage")
    def test_show_js_function(self, mock_storage_cls, cli_runner, mock_snapshot_with_lambdas):
        """Test showing JavaScript Lambda code."""
        mock_storage = MagicMock()
        mock_storage.get_active_snapshot_name.return_value = "test-snapshot"
        mock_storage.load_snapshot.return_value = mock_snapshot_with_lambdas
        mock_storage_cls.return_value = mock_storage

        result = cli_runner.invoke(app, ["lambda", "show", "my-js-func"])

        assert result.exit_code == 0
        assert "index.js" in result.stdout
        assert "exports.handler" in result.stdout

    @patch("src.cli.main.SnapshotStorage")
    def test_show_function_not_found(self, mock_storage_cls, cli_runner, mock_snapshot_with_lambdas):
        """Test error when function not found."""
        mock_storage = MagicMock()
        mock_storage.get_active_snapshot_name.return_value = "test-snapshot"
        mock_storage.load_snapshot.return_value = mock_snapshot_with_lambdas
        mock_storage_cls.return_value = mock_storage

        result = cli_runner.invoke(app, ["lambda", "show", "nonexistent-func"])

        assert result.exit_code == 1
        assert "not found" in result.stdout

    @patch("src.cli.main.SnapshotStorage")
    def test_show_file_not_found(self, mock_storage_cls, cli_runner, mock_snapshot_with_lambdas):
        """Test error when file not found in package."""
        mock_storage = MagicMock()
        mock_storage.get_active_snapshot_name.return_value = "test-snapshot"
        mock_storage.load_snapshot.return_value = mock_snapshot_with_lambdas
        mock_storage_cls.return_value = mock_storage

        result = cli_runner.invoke(app, ["lambda", "show", "my-python-func", "--file", "nonexistent.py"])

        assert result.exit_code == 1
        assert "not found" in result.stdout
        assert "Available:" in result.stdout

    @patch("src.cli.main.SnapshotStorage")
    def test_show_large_function_no_code(self, mock_storage_cls, cli_runner, mock_snapshot_with_lambdas):
        """Test error when function has no stored code."""
        mock_storage = MagicMock()
        mock_storage.get_active_snapshot_name.return_value = "test-snapshot"
        mock_storage.load_snapshot.return_value = mock_snapshot_with_lambdas
        mock_storage_cls.return_value = mock_storage

        result = cli_runner.invoke(app, ["lambda", "show", "large-func"])

        assert result.exit_code == 1
        assert "No code stored" in result.stdout
        assert "SHA256" in result.stdout  # Should still show hash


class TestLambdaDiffCommand:
    """Tests for awsinv lambda diff command."""

    @patch("src.cli.main.SnapshotStorage")
    def test_diff_no_changes(self, mock_storage_cls, cli_runner, sample_lambda_code):
        """Test diff when code hasn't changed."""
        mock_storage = MagicMock()

        # Same code in both snapshots
        resource = Resource(
            arn="arn:aws:lambda:us-east-1:123456789012:function:my-func",
            resource_type="AWS::Lambda::Function",
            name="my-func",
            region="us-east-1",
            config_hash="hash1",
            raw_config={
                "Runtime": "python3.11",
                "Handler": "handler.lambda_handler",
                "_code": {
                    "code_stored": True,
                    "code_base64": sample_lambda_code,
                    "code_sha256": "samehash123",
                },
            },
        )

        snapshot1 = Snapshot(
            name="snap1",
            created_at=datetime.now(timezone.utc),
            account_id="123456789012",
            regions=["us-east-1"],
            resources=[resource],
        )
        snapshot2 = Snapshot(
            name="snap2",
            created_at=datetime.now(timezone.utc),
            account_id="123456789012",
            regions=["us-east-1"],
            resources=[resource],
        )

        mock_storage.load_snapshot.side_effect = lambda name: snapshot1 if name == "snap1" else snapshot2
        mock_storage_cls.return_value = mock_storage

        result = cli_runner.invoke(app, ["lambda", "diff", "my-func", "snap1", "snap2"])

        assert result.exit_code == 0
        assert "No changes" in result.stdout

    @patch("src.cli.main.SnapshotStorage")
    def test_diff_code_changed(self, mock_storage_cls, cli_runner, sample_lambda_code):
        """Test diff when code has changed."""
        mock_storage = MagicMock()

        # Create different code for snapshot 2
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(
                "handler.py",
                'def lambda_handler(event, context):\n    # Updated code\n    return {"statusCode": 201}\n',
            )
        zip_buffer.seek(0)
        new_code = base64.b64encode(zip_buffer.read()).decode("utf-8")

        resource1 = Resource(
            arn="arn:aws:lambda:us-east-1:123456789012:function:my-func",
            resource_type="AWS::Lambda::Function",
            name="my-func",
            region="us-east-1",
            config_hash="hash1",
            raw_config={
                "Runtime": "python3.11",
                "Handler": "handler.lambda_handler",
                "_code": {
                    "code_stored": True,
                    "code_base64": sample_lambda_code,
                    "code_sha256": "oldhash123",
                },
            },
        )

        resource2 = Resource(
            arn="arn:aws:lambda:us-east-1:123456789012:function:my-func",
            resource_type="AWS::Lambda::Function",
            name="my-func",
            region="us-east-1",
            config_hash="hash2",
            raw_config={
                "Runtime": "python3.11",
                "Handler": "handler.lambda_handler",
                "_code": {
                    "code_stored": True,
                    "code_base64": new_code,
                    "code_sha256": "newhash456",
                },
            },
        )

        snapshot1 = Snapshot(
            name="snap1",
            created_at=datetime.now(timezone.utc),
            account_id="123456789012",
            regions=["us-east-1"],
            resources=[resource1],
        )
        snapshot2 = Snapshot(
            name="snap2",
            created_at=datetime.now(timezone.utc),
            account_id="123456789012",
            regions=["us-east-1"],
            resources=[resource2],
        )

        mock_storage.load_snapshot.side_effect = lambda name: snapshot1 if name == "snap1" else snapshot2
        mock_storage_cls.return_value = mock_storage

        result = cli_runner.invoke(app, ["lambda", "diff", "my-func", "snap1", "snap2"])

        assert result.exit_code == 0
        assert "Code changed" in result.stdout
        assert "handler.py" in result.stdout

    @patch("src.cli.main.SnapshotStorage")
    def test_diff_files_added_removed(self, mock_storage_cls, cli_runner):
        """Test diff when files are added or removed."""
        mock_storage = MagicMock()

        # Snapshot 1: only handler.py
        zip1 = BytesIO()
        with zipfile.ZipFile(zip1, "w") as zf:
            zf.writestr("handler.py", "def main(): pass")
        zip1.seek(0)
        code1 = base64.b64encode(zip1.read()).decode("utf-8")

        # Snapshot 2: handler.py + utils.py
        zip2 = BytesIO()
        with zipfile.ZipFile(zip2, "w") as zf:
            zf.writestr("handler.py", "def main(): pass")
            zf.writestr("utils.py", "def helper(): pass")
        zip2.seek(0)
        code2 = base64.b64encode(zip2.read()).decode("utf-8")

        resource1 = Resource(
            arn="arn:aws:lambda:us-east-1:123456789012:function:my-func",
            resource_type="AWS::Lambda::Function",
            name="my-func",
            region="us-east-1",
            config_hash="confighash1",
            raw_config={
                "Handler": "handler.main",
                "_code": {"code_stored": True, "code_base64": code1, "code_sha256": "hash1"},
            },
        )

        resource2 = Resource(
            arn="arn:aws:lambda:us-east-1:123456789012:function:my-func",
            resource_type="AWS::Lambda::Function",
            name="my-func",
            region="us-east-1",
            config_hash="confighash2",
            raw_config={
                "Handler": "handler.main",
                "_code": {"code_stored": True, "code_base64": code2, "code_sha256": "hash2"},
            },
        )

        snapshot1 = Snapshot(
            name="snap1",
            created_at=datetime.now(timezone.utc),
            account_id="123456789012",
            regions=["us-east-1"],
            resources=[resource1],
        )
        snapshot2 = Snapshot(
            name="snap2",
            created_at=datetime.now(timezone.utc),
            account_id="123456789012",
            regions=["us-east-1"],
            resources=[resource2],
        )

        mock_storage.load_snapshot.side_effect = lambda name: snapshot1 if name == "snap1" else snapshot2
        mock_storage_cls.return_value = mock_storage

        result = cli_runner.invoke(app, ["lambda", "diff", "my-func", "snap1", "snap2"])

        assert result.exit_code == 0
        assert "Added files" in result.stdout
        assert "utils.py" in result.stdout

    @patch("src.cli.main.SnapshotStorage")
    def test_diff_snapshot_not_found(self, mock_storage_cls, cli_runner):
        """Test error when snapshot not found."""
        mock_storage = MagicMock()
        mock_storage.load_snapshot.return_value = None
        mock_storage_cls.return_value = mock_storage

        result = cli_runner.invoke(app, ["lambda", "diff", "my-func", "snap1", "snap2"])

        assert result.exit_code == 1
        assert "not found" in result.stdout

    @patch("src.cli.main.SnapshotStorage")
    def test_diff_function_not_found(self, mock_storage_cls, cli_runner):
        """Test error when function not found in snapshot."""
        mock_storage = MagicMock()

        # Empty snapshots (no Lambda functions)
        snapshot = Snapshot(
            name="snap",
            created_at=datetime.now(timezone.utc),
            account_id="123456789012",
            regions=["us-east-1"],
            resources=[],
        )
        mock_storage.load_snapshot.return_value = snapshot
        mock_storage_cls.return_value = mock_storage

        result = cli_runner.invoke(app, ["lambda", "diff", "my-func", "snap1", "snap2"])

        assert result.exit_code == 1
        assert "not found" in result.stdout

    @patch("src.cli.main.SnapshotStorage")
    def test_diff_specific_file(self, mock_storage_cls, cli_runner, sample_lambda_code):
        """Test diffing a specific file."""
        mock_storage = MagicMock()

        # Create modified code
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            zf.writestr("handler.py", "def lambda_handler(event, context):\n    return {'new': 'code'}\n")
            zf.writestr("utils.py", "# Modified utils\n")
            zf.writestr("requirements.txt", "boto3>=1.28.0\n")
        zip_buffer.seek(0)
        new_code = base64.b64encode(zip_buffer.read()).decode("utf-8")

        resource1 = Resource(
            arn="arn:aws:lambda:us-east-1:123456789012:function:my-func",
            resource_type="AWS::Lambda::Function",
            name="my-func",
            region="us-east-1",
            config_hash="confighash1",
            raw_config={
                "Handler": "handler.lambda_handler",
                "_code": {"code_stored": True, "code_base64": sample_lambda_code, "code_sha256": "hash1"},
            },
        )

        resource2 = Resource(
            arn="arn:aws:lambda:us-east-1:123456789012:function:my-func",
            resource_type="AWS::Lambda::Function",
            name="my-func",
            region="us-east-1",
            config_hash="confighash2",
            raw_config={
                "Handler": "handler.lambda_handler",
                "_code": {"code_stored": True, "code_base64": new_code, "code_sha256": "hash2"},
            },
        )

        snapshot1 = Snapshot(
            name="snap1",
            created_at=datetime.now(timezone.utc),
            account_id="123456789012",
            regions=["us-east-1"],
            resources=[resource1],
        )
        snapshot2 = Snapshot(
            name="snap2",
            created_at=datetime.now(timezone.utc),
            account_id="123456789012",
            regions=["us-east-1"],
            resources=[resource2],
        )

        mock_storage.load_snapshot.side_effect = lambda name: snapshot1 if name == "snap1" else snapshot2
        mock_storage_cls.return_value = mock_storage

        result = cli_runner.invoke(app, ["lambda", "diff", "my-func", "snap1", "snap2", "--file", "utils.py"])

        assert result.exit_code == 0
        assert "utils.py" in result.stdout

    @patch("src.cli.main.SnapshotStorage")
    def test_diff_no_stored_code(self, mock_storage_cls, cli_runner):
        """Test diff when code not stored in one or both snapshots."""
        mock_storage = MagicMock()

        resource = Resource(
            arn="arn:aws:lambda:us-east-1:123456789012:function:my-func",
            resource_type="AWS::Lambda::Function",
            name="my-func",
            region="us-east-1",
            config_hash="hash1",
            raw_config={
                "Handler": "handler.main",
                "_code": {"code_stored": False, "code_sha256": "hash1"},  # No code stored
            },
        )

        snapshot = Snapshot(
            name="snap",
            created_at=datetime.now(timezone.utc),
            account_id="123456789012",
            regions=["us-east-1"],
            resources=[resource],
        )
        mock_storage.load_snapshot.return_value = snapshot
        mock_storage_cls.return_value = mock_storage

        result = cli_runner.invoke(app, ["lambda", "diff", "my-func", "snap1", "snap2"])

        # Should handle gracefully - same hash means no changes, even without stored code
        assert result.exit_code == 0
        assert "No changes" in result.stdout or "SHA256" in result.stdout


class TestLambdaEdgeCases:
    """Edge case tests for lambda commands."""

    @patch("src.cli.main.SnapshotStorage")
    def test_lambda_with_no_raw_config(self, mock_storage_cls, cli_runner):
        """Test handling Lambda with no raw_config."""
        mock_storage = MagicMock()

        resource = Resource(
            arn="arn:aws:lambda:us-east-1:123456789012:function:broken-func",
            resource_type="AWS::Lambda::Function",
            name="broken-func",
            region="us-east-1",
            config_hash="hash1",
            raw_config=None,
        )

        snapshot = Snapshot(
            name="snap",
            created_at=datetime.now(timezone.utc),
            account_id="123456789012",
            regions=["us-east-1"],
            resources=[resource],
        )
        mock_storage.load_snapshot.return_value = snapshot
        mock_storage_cls.return_value = mock_storage

        result = cli_runner.invoke(app, ["lambda", "list", "snap", "--all"])

        # Should not crash
        assert result.exit_code == 0

    @patch("src.cli.main.SnapshotStorage")
    def test_lambda_with_empty_code_section(self, mock_storage_cls, cli_runner):
        """Test handling Lambda with empty _code section."""
        mock_storage = MagicMock()

        resource = Resource(
            arn="arn:aws:lambda:us-east-1:123456789012:function:empty-code-func",
            resource_type="AWS::Lambda::Function",
            name="empty-code-func",
            region="us-east-1",
            config_hash="hash1",
            raw_config={"Runtime": "python3.11", "_code": {}},
        )

        snapshot = Snapshot(
            name="snap",
            created_at=datetime.now(timezone.utc),
            account_id="123456789012",
            regions=["us-east-1"],
            resources=[resource],
        )
        mock_storage.load_snapshot.return_value = snapshot
        mock_storage_cls.return_value = mock_storage

        result = cli_runner.invoke(app, ["lambda", "list", "snap", "--all"])

        # Should not crash
        assert result.exit_code == 0

    @patch("src.cli.main.SnapshotStorage")
    def test_lambda_unnamed_function(self, mock_storage_cls, cli_runner, sample_lambda_code):
        """Test handling Lambda with no name."""
        mock_storage = MagicMock()

        resource = Resource(
            arn="arn:aws:lambda:us-east-1:123456789012:function:unnamed",
            resource_type="AWS::Lambda::Function",
            name=None,  # No name
            region="us-east-1",
            config_hash="hash1",
            raw_config={
                "Runtime": "python3.11",
                "_code": {"code_stored": True, "code_base64": sample_lambda_code, "code_sha256": "hash"},
            },
        )

        snapshot = Snapshot(
            name="snap",
            created_at=datetime.now(timezone.utc),
            account_id="123456789012",
            regions=["us-east-1"],
            resources=[resource],
        )
        mock_storage.load_snapshot.return_value = snapshot
        mock_storage_cls.return_value = mock_storage

        result = cli_runner.invoke(app, ["lambda", "list", "snap"])

        # Should handle gracefully
        assert result.exit_code == 0
        assert "unnamed" in result.stdout.lower()
