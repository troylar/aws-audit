"""Unit tests for S3 security checks."""

from __future__ import annotations

from src.models.security_finding import Severity
from src.security.checks.s3_checks import S3PublicBucketCheck
from tests.fixtures.snapshots import create_mock_snapshot, create_s3_bucket


class TestS3PublicBucketCheck:
    """Tests for S3PublicBucketCheck."""

    def test_check_id_and_severity(self) -> None:
        """Test that check has correct ID and severity."""
        check = S3PublicBucketCheck()
        assert check.check_id == "s3_public_bucket"
        assert check.severity == Severity.CRITICAL

    def test_detect_public_bucket_via_block_config(self) -> None:
        """Test detection of publicly accessible bucket via PublicAccessBlockConfiguration."""
        public_bucket = create_s3_bucket("public-bucket", public=True)
        snapshot = create_mock_snapshot(resources=[public_bucket])

        check = S3PublicBucketCheck()
        findings = check.execute(snapshot)

        assert len(findings) == 1
        assert findings[0].resource_arn == public_bucket.arn
        assert findings[0].finding_type == "s3_public_bucket"
        assert findings[0].severity == Severity.CRITICAL
        assert "publicly accessible" in findings[0].description.lower()
        assert findings[0].cis_control == "2.1.5"

    def test_private_bucket_no_findings(self) -> None:
        """Test that private bucket with all blocks enabled produces no findings."""
        private_bucket = create_s3_bucket("private-bucket", public=False)
        snapshot = create_mock_snapshot(resources=[private_bucket])

        check = S3PublicBucketCheck()
        findings = check.execute(snapshot)

        assert len(findings) == 0

    def test_multiple_buckets_mixed_access(self) -> None:
        """Test scanning multiple buckets with mixed public/private access."""
        public_bucket1 = create_s3_bucket("public-1", public=True)
        private_bucket = create_s3_bucket("private-1", public=False)
        public_bucket2 = create_s3_bucket("public-2", public=True)

        snapshot = create_mock_snapshot(resources=[public_bucket1, private_bucket, public_bucket2])

        check = S3PublicBucketCheck()
        findings = check.execute(snapshot)

        assert len(findings) == 2
        finding_arns = [f.resource_arn for f in findings]
        assert public_bucket1.arn in finding_arns
        assert public_bucket2.arn in finding_arns
        assert private_bucket.arn not in finding_arns

    def test_empty_snapshot_no_findings(self) -> None:
        """Test that empty snapshot produces no findings."""
        snapshot = create_mock_snapshot(resources=[])

        check = S3PublicBucketCheck()
        findings = check.execute(snapshot)

        assert len(findings) == 0

    def test_snapshot_without_s3_resources(self) -> None:
        """Test snapshot with no S3 buckets produces no findings."""
        from tests.fixtures.snapshots import create_ec2_instance

        ec2_instance = create_ec2_instance()
        snapshot = create_mock_snapshot(resources=[ec2_instance])

        check = S3PublicBucketCheck()
        findings = check.execute(snapshot)

        assert len(findings) == 0

    def test_remediation_guidance_present(self) -> None:
        """Test that findings include remediation guidance."""
        public_bucket = create_s3_bucket("test-bucket", public=True)
        snapshot = create_mock_snapshot(resources=[public_bucket])

        check = S3PublicBucketCheck()
        findings = check.execute(snapshot)

        assert len(findings) == 1
        assert findings[0].remediation
        assert len(findings[0].remediation) > 0
        assert "block public access" in findings[0].remediation.lower()

    def test_bucket_with_raw_config_none(self) -> None:
        """Test that bucket with raw_config=None is skipped."""
        from src.models.resource import Resource

        bucket = Resource(
            arn="arn:aws:s3:::no-config-bucket",
            resource_type="s3:bucket",
            name="no-config-bucket",
            region="us-east-1",
            config_hash="a" * 64,
            raw_config=None,
            tags={},
        )
        snapshot = create_mock_snapshot(resources=[bucket])

        check = S3PublicBucketCheck()
        findings = check.execute(snapshot)

        assert len(findings) == 0
