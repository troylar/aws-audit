"""Tests for CLI security commands."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from src.cli.main import app
from src.models.resource import Resource
from src.models.security_finding import SecurityFinding, Severity
from src.models.snapshot import Snapshot
from src.security.models import SecurityScanResult


@pytest.fixture
def cli_runner():
    """Create a Typer CLI runner."""
    return CliRunner()


@pytest.fixture
def sample_snapshot():
    """Create a sample snapshot for security scanning."""
    resources = [
        Resource(
            arn="arn:aws:s3:::public-bucket",
            resource_type="AWS::S3::Bucket",
            name="public-bucket",
            region="us-east-1",
            config_hash="a" * 64,
            raw_config={
                "BucketName": "public-bucket",
                "PublicAccessBlockConfiguration": {
                    "BlockPublicAcls": False,
                    "BlockPublicPolicy": False,
                },
            },
        ),
        Resource(
            arn="arn:aws:ec2:us-east-1:123456789012:security-group/sg-123",
            resource_type="AWS::EC2::SecurityGroup",
            name="open-sg",
            region="us-east-1",
            config_hash="b" * 64,
            raw_config={
                "GroupName": "open-sg",
                "IpPermissions": [
                    {
                        "IpProtocol": "tcp",
                        "FromPort": 22,
                        "ToPort": 22,
                        "IpRanges": [{"CidrIp": "0.0.0.0/0"}],
                    }
                ],
            },
        ),
    ]
    return Snapshot(
        name="security-test-snap",
        created_at=datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
        account_id="123456789012",
        regions=["us-east-1"],
        resources=resources,
    )


@pytest.fixture
def sample_findings():
    """Create sample security findings."""
    return [
        SecurityFinding(
            resource_arn="arn:aws:s3:::public-bucket",
            finding_type="public_s3_bucket",
            severity=Severity.CRITICAL,
            description="S3 bucket has public access enabled",
            remediation="Enable S3 Block Public Access settings",
            cis_control="2.1.5",
        ),
        SecurityFinding(
            resource_arn="arn:aws:ec2:us-east-1:123456789012:security-group/sg-123",
            finding_type="open_ssh_access",
            severity=Severity.HIGH,
            description="Security group allows SSH from 0.0.0.0/0",
            remediation="Restrict SSH access to specific IP ranges",
            cis_control="5.2",
        ),
        SecurityFinding(
            resource_arn="arn:aws:ec2:us-east-1:123456789012:instance/i-abc123",
            finding_type="imdsv1_enabled",
            severity=Severity.MEDIUM,
            description="EC2 instance has IMDSv1 enabled",
            remediation="Enable IMDSv2 and disable IMDSv1",
        ),
        SecurityFinding(
            resource_arn="arn:aws:iam::123456789012:user/old-user",
            finding_type="old_access_key",
            severity=Severity.LOW,
            description="IAM user access key is over 90 days old",
            remediation="Rotate access keys regularly",
        ),
    ]


@pytest.fixture
def scan_result_with_findings(sample_findings):
    """Create a scan result with findings."""
    result = SecurityScanResult(snapshot_name="security-test-snap")
    for finding in sample_findings:
        result.add_finding(finding)
    return result


@pytest.fixture
def scan_result_no_findings():
    """Create a scan result with no findings."""
    return SecurityScanResult(snapshot_name="clean-snap")


class TestSecurityScanCommand:
    """Tests for awsinv security scan command."""

    def test_security_scan_help_text(self, cli_runner):
        """Test that security scan command has help text."""
        result = cli_runner.invoke(app, ["security", "scan", "--help"])
        assert result.exit_code == 0
        assert "snapshot" in result.stdout.lower()

    @patch("src.security.scanner.SecurityScanner")
    @patch("src.cli.main.SnapshotStorage")
    def test_scan_with_valid_snapshot(
        self,
        mock_storage_cls,
        mock_scanner_cls,
        cli_runner,
        sample_snapshot,
        scan_result_with_findings,
    ):
        """Test security scan with a valid snapshot returns findings."""
        mock_storage = MagicMock()
        mock_storage.load_snapshot.return_value = sample_snapshot
        mock_storage_cls.return_value = mock_storage

        mock_scanner = MagicMock()
        mock_scanner.scan.return_value = scan_result_with_findings
        mock_scanner_cls.return_value = mock_scanner

        result = cli_runner.invoke(app, ["security", "scan", "--snapshot", "security-test-snap"])

        assert result.exit_code == 0
        assert "security issue" in result.stdout.lower() or "finding" in result.stdout.lower()

    @patch("src.security.scanner.SecurityScanner")
    @patch("src.cli.main.SnapshotStorage")
    def test_scan_no_findings(
        self,
        mock_storage_cls,
        mock_scanner_cls,
        cli_runner,
        sample_snapshot,
        scan_result_no_findings,
    ):
        """Test security scan with no findings shows success message."""
        mock_storage = MagicMock()
        mock_storage.load_snapshot.return_value = sample_snapshot
        mock_storage_cls.return_value = mock_storage

        mock_scanner = MagicMock()
        mock_scanner.scan.return_value = scan_result_no_findings
        mock_scanner_cls.return_value = mock_scanner

        result = cli_runner.invoke(app, ["security", "scan", "--snapshot", "clean-snap"])

        assert result.exit_code == 0
        assert "No security issues" in result.stdout

    @patch("src.security.scanner.SecurityScanner")
    @patch("src.cli.main.SnapshotStorage")
    def test_scan_with_severity_filter(
        self,
        mock_storage_cls,
        mock_scanner_cls,
        cli_runner,
        sample_snapshot,
    ):
        """Test security scan with --severity filter."""
        mock_storage = MagicMock()
        mock_storage.load_snapshot.return_value = sample_snapshot
        mock_storage_cls.return_value = mock_storage

        critical_only = SecurityScanResult(snapshot_name="security-test-snap")
        critical_only.add_finding(
            SecurityFinding(
                resource_arn="arn:aws:s3:::public-bucket",
                finding_type="public_s3_bucket",
                severity=Severity.CRITICAL,
                description="S3 bucket has public access enabled",
                remediation="Enable S3 Block Public Access settings",
            )
        )
        mock_scanner = MagicMock()
        mock_scanner.scan.return_value = critical_only
        mock_scanner_cls.return_value = mock_scanner

        result = cli_runner.invoke(
            app,
            ["security", "scan", "--snapshot", "security-test-snap", "--severity", "critical"],
        )

        assert result.exit_code == 0
        mock_scanner.scan.assert_called_once()
        call_kwargs = mock_scanner.scan.call_args
        assert call_kwargs[1]["severity_filter"] == Severity.CRITICAL

    def test_scan_with_invalid_severity(self, cli_runner):
        """Test security scan with invalid severity value."""
        with patch("src.cli.main.SnapshotStorage") as mock_storage_cls:
            mock_storage = MagicMock()
            mock_snapshot = MagicMock()
            mock_snapshot.name = "test-snap"
            mock_storage.load_snapshot.return_value = mock_snapshot
            mock_storage_cls.return_value = mock_storage

            result = cli_runner.invoke(
                app,
                ["security", "scan", "--snapshot", "test-snap", "--severity", "invalid"],
            )

            assert result.exit_code == 1
            assert "Invalid severity" in result.stdout

    @patch("src.cli.main.SnapshotStorage")
    def test_scan_with_nonexistent_snapshot(
        self,
        mock_storage_cls,
        cli_runner,
    ):
        """Test security scan with a snapshot that does not exist."""
        mock_storage = MagicMock()
        mock_storage.load_snapshot.side_effect = FileNotFoundError("Snapshot not found")
        mock_storage_cls.return_value = mock_storage

        result = cli_runner.invoke(app, ["security", "scan", "--snapshot", "nonexistent"])

        assert result.exit_code == 1
        assert "not found" in result.stdout.lower()

    def test_scan_missing_snapshot_and_collection(self, cli_runner):
        """Test security scan with neither --snapshot nor --collection."""
        result = cli_runner.invoke(app, ["security", "scan"])

        assert result.exit_code == 1
        assert "Must specify" in result.stdout or "snapshot" in result.stdout.lower()

    @patch("src.security.scanner.SecurityScanner")
    @patch("src.cli.main.SnapshotStorage")
    def test_scan_with_cis_only_flag(
        self,
        mock_storage_cls,
        mock_scanner_cls,
        cli_runner,
        sample_snapshot,
        scan_result_with_findings,
    ):
        """Test security scan with --cis-only flag filters to CIS-mapped findings."""
        mock_storage = MagicMock()
        mock_storage.load_snapshot.return_value = sample_snapshot
        mock_storage_cls.return_value = mock_storage

        mock_scanner = MagicMock()
        mock_scanner.scan.return_value = scan_result_with_findings
        mock_scanner_cls.return_value = mock_scanner

        result = cli_runner.invoke(
            app,
            ["security", "scan", "--snapshot", "security-test-snap", "--cis-only"],
        )

        assert result.exit_code == 0

    @patch("src.security.scanner.SecurityScanner")
    @patch("src.snapshot.collection_storage.CollectionStorage")
    @patch("src.cli.main.SnapshotStorage")
    @patch("src.cli.main.validate_credentials")
    def test_scan_with_collection(
        self,
        mock_validate,
        mock_storage_cls,
        mock_coll_storage_cls,
        mock_scanner_cls,
        cli_runner,
        sample_snapshot,
        scan_result_no_findings,
    ):
        """Test security scan using --collection to resolve active snapshot."""
        mock_validate.return_value = {
            "account_id": "123456789012",
            "arn": "arn:aws:iam::123456789012:user/test",
        }
        mock_storage = MagicMock()
        mock_storage.load_snapshot.return_value = sample_snapshot
        mock_storage_cls.return_value = mock_storage

        mock_collection = MagicMock()
        mock_collection.active_snapshot = "security-test-snap.yaml"
        mock_coll_storage = MagicMock()
        mock_coll_storage.get_by_name.return_value = mock_collection
        mock_coll_storage_cls.return_value = mock_coll_storage

        mock_scanner = MagicMock()
        mock_scanner.scan.return_value = scan_result_no_findings
        mock_scanner_cls.return_value = mock_scanner

        result = cli_runner.invoke(app, ["security", "scan", "--collection", "prod-baseline"])

        assert result.exit_code == 0

    @patch("src.snapshot.collection_storage.CollectionStorage")
    @patch("src.cli.main.SnapshotStorage")
    @patch("src.cli.main.validate_credentials")
    def test_scan_collection_no_active_snapshot(
        self,
        mock_validate,
        mock_storage_cls,
        mock_coll_storage_cls,
        cli_runner,
    ):
        """Test security scan when collection has no active snapshot."""
        mock_validate.return_value = {
            "account_id": "123456789012",
            "arn": "arn:aws:iam::123456789012:user/test",
        }
        mock_collection = MagicMock()
        mock_collection.active_snapshot = None
        mock_coll_storage = MagicMock()
        mock_coll_storage.get_by_name.return_value = mock_collection
        mock_coll_storage_cls.return_value = mock_coll_storage

        result = cli_runner.invoke(app, ["security", "scan", "--collection", "empty-coll"])

        assert result.exit_code == 1
        assert "no active snapshot" in result.stdout.lower()
