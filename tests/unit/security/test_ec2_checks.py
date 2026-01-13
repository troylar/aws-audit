"""Unit tests for EC2 security checks."""

from __future__ import annotations

from src.models.security_finding import Severity
from src.security.checks.ec2_checks import EC2IMDSv1Check
from tests.fixtures.snapshots import create_ec2_instance, create_mock_snapshot


class TestEC2IMDSv1Check:
    """Tests for EC2IMDSv1Check."""

    def test_check_id_and_severity(self) -> None:
        """Test that check has correct ID and severity."""
        check = EC2IMDSv1Check()
        assert check.check_id == "ec2_imdsv1_enabled"
        assert check.severity == Severity.MEDIUM

    def test_detect_imdsv1_enabled(self) -> None:
        """Test detection of EC2 instance with IMDSv1 enabled (HttpTokens=optional)."""
        imdsv1_instance = create_ec2_instance("i-imdsv1", imdsv2_required=False)
        snapshot = create_mock_snapshot(resources=[imdsv1_instance])

        check = EC2IMDSv1Check()
        findings = check.execute(snapshot)

        assert len(findings) == 1
        assert findings[0].resource_arn == imdsv1_instance.arn
        assert findings[0].severity == Severity.MEDIUM
        assert "imdsv1" in findings[0].description.lower() or "metadata" in findings[0].description.lower()

    def test_imdsv2_required_no_findings(self) -> None:
        """Test that EC2 instance with IMDSv2 required produces no findings."""
        imdsv2_instance = create_ec2_instance("i-imdsv2", imdsv2_required=True)
        snapshot = create_mock_snapshot(resources=[imdsv2_instance])

        check = EC2IMDSv1Check()
        findings = check.execute(snapshot)

        assert len(findings) == 0

    def test_multiple_instances_mixed_imds(self) -> None:
        """Test scanning multiple EC2 instances with mixed IMDS configurations."""
        imdsv1_instance1 = create_ec2_instance("i-old1", imdsv2_required=False)
        imdsv2_instance = create_ec2_instance("i-new", imdsv2_required=True)
        imdsv1_instance2 = create_ec2_instance("i-old2", imdsv2_required=False)

        snapshot = create_mock_snapshot(resources=[imdsv1_instance1, imdsv2_instance, imdsv1_instance2])

        check = EC2IMDSv1Check()
        findings = check.execute(snapshot)

        assert len(findings) == 2
        finding_arns = [f.resource_arn for f in findings]
        assert imdsv1_instance1.arn in finding_arns
        assert imdsv1_instance2.arn in finding_arns
        assert imdsv2_instance.arn not in finding_arns

    def test_remediation_guidance_present(self) -> None:
        """Test that findings include remediation guidance."""
        imdsv1_instance = create_ec2_instance("i-test", imdsv2_required=False)
        snapshot = create_mock_snapshot(resources=[imdsv1_instance])

        check = EC2IMDSv1Check()
        findings = check.execute(snapshot)

        assert len(findings) == 1
        assert findings[0].remediation
        assert "imdsv2" in findings[0].remediation.lower() or "httptokens" in findings[0].remediation.lower()

    def test_empty_snapshot_no_findings(self) -> None:
        """Test that empty snapshot produces no findings."""
        snapshot = create_mock_snapshot(resources=[])

        check = EC2IMDSv1Check()
        findings = check.execute(snapshot)

        assert len(findings) == 0

    def test_instance_with_raw_config_none(self) -> None:
        """Test that instance with raw_config=None is skipped."""
        from src.models.resource import Resource

        instance = Resource(
            arn="arn:aws:ec2:us-east-1:123456789012:instance/i-123",
            resource_type="ec2:instance",
            name="no-config-instance",
            region="us-east-1",
            config_hash="a" * 64,
            raw_config=None,
            tags={},
        )
        snapshot = create_mock_snapshot(resources=[instance])

        check = EC2IMDSv1Check()
        findings = check.execute(snapshot)

        assert len(findings) == 0
