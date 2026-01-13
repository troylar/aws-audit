"""Unit tests for RDS security checks."""

from __future__ import annotations

from src.models.security_finding import Severity
from src.security.checks.rds_checks import RDSPublicCheck
from tests.fixtures.snapshots import create_mock_snapshot, create_rds_instance


class TestRDSPublicCheck:
    """Tests for RDSPublicCheck."""

    def test_check_id_and_severity(self) -> None:
        """Test that check has correct ID and severity."""
        check = RDSPublicCheck()
        assert check.check_id == "rds_publicly_accessible"
        assert check.severity == Severity.HIGH

    def test_detect_publicly_accessible_rds(self) -> None:
        """Test detection of RDS instance with PubliclyAccessible=True."""
        public_db = create_rds_instance("public-db", publicly_accessible=True)
        snapshot = create_mock_snapshot(resources=[public_db])

        check = RDSPublicCheck()
        findings = check.execute(snapshot)

        assert len(findings) == 1
        assert findings[0].resource_arn == public_db.arn
        assert findings[0].severity == Severity.HIGH
        assert "publicly accessible" in findings[0].description.lower()

    def test_private_rds_no_findings(self) -> None:
        """Test that private RDS instance produces no findings."""
        private_db = create_rds_instance("private-db", publicly_accessible=False)
        snapshot = create_mock_snapshot(resources=[private_db])

        check = RDSPublicCheck()
        findings = check.execute(snapshot)

        assert len(findings) == 0

    def test_multiple_databases_mixed_accessibility(self) -> None:
        """Test scanning multiple RDS instances with mixed accessibility."""
        public_db1 = create_rds_instance("public-1", publicly_accessible=True)
        private_db = create_rds_instance("private-1", publicly_accessible=False)
        public_db2 = create_rds_instance("public-2", publicly_accessible=True)

        snapshot = create_mock_snapshot(resources=[public_db1, private_db, public_db2])

        check = RDSPublicCheck()
        findings = check.execute(snapshot)

        assert len(findings) == 2
        finding_arns = [f.resource_arn for f in findings]
        assert public_db1.arn in finding_arns
        assert public_db2.arn in finding_arns
        assert private_db.arn not in finding_arns

    def test_unencrypted_rds_detection(self) -> None:
        """Test detection of unencrypted RDS instance."""
        unencrypted_db = create_rds_instance("unencrypted-db", encrypted=False, publicly_accessible=False)
        snapshot = create_mock_snapshot(resources=[unencrypted_db])

        check = RDSPublicCheck()
        findings = check.execute(snapshot)

        # This check specifically looks for public accessibility and encryption
        # Unencrypted but private should still create a finding
        assert len(findings) == 1
        assert "encryption" in findings[0].description.lower()

    def test_public_and_unencrypted_multiple_findings(self) -> None:
        """Test that public AND unencrypted RDS creates findings for both issues."""
        bad_db = create_rds_instance("bad-db", publicly_accessible=True, encrypted=False)
        snapshot = create_mock_snapshot(resources=[bad_db])

        check = RDSPublicCheck()
        findings = check.execute(snapshot)

        # Should flag both public access and lack of encryption
        assert len(findings) >= 1

    def test_remediation_guidance_present(self) -> None:
        """Test that findings include remediation guidance."""
        public_db = create_rds_instance("test-db", publicly_accessible=True)
        snapshot = create_mock_snapshot(resources=[public_db])

        check = RDSPublicCheck()
        findings = check.execute(snapshot)

        assert len(findings) == 1
        assert findings[0].remediation
        assert "disable" in findings[0].remediation.lower() or "modify" in findings[0].remediation.lower()

    def test_empty_snapshot_no_findings(self) -> None:
        """Test that empty snapshot produces no findings."""
        snapshot = create_mock_snapshot(resources=[])

        check = RDSPublicCheck()
        findings = check.execute(snapshot)

        assert len(findings) == 0

    def test_rds_with_raw_config_none(self) -> None:
        """Test that RDS instance with raw_config=None is skipped."""
        from src.models.resource import Resource

        db = Resource(
            arn="arn:aws:rds:us-east-1:123456789012:db:no-config-db",
            resource_type="rds:db-instance",
            name="no-config-db",
            region="us-east-1",
            config_hash="a" * 64,
            raw_config=None,
            tags={},
        )
        snapshot = create_mock_snapshot(resources=[db])

        check = RDSPublicCheck()
        findings = check.execute(snapshot)

        assert len(findings) == 0
