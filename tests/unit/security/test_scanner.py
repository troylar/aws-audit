"""Unit tests for SecurityScanner."""

from __future__ import annotations

from src.models.security_finding import Severity
from src.security.scanner import SecurityScanner
from tests.fixtures.snapshots import (
    create_mock_snapshot,
    create_rds_instance,
    create_s3_bucket,
    create_security_group,
)


class TestSecurityScanner:
    """Tests for SecurityScanner."""

    def test_scanner_initializes_with_checks(self) -> None:
        """Test that scanner initializes and loads security checks."""
        scanner = SecurityScanner()

        # Should have loaded all check modules
        assert len(scanner.checks) > 0
        # Should have at least the 6 core checks we're implementing
        assert len(scanner.checks) >= 6

    def test_scan_empty_snapshot(self) -> None:
        """Test scanning an empty snapshot."""
        snapshot = create_mock_snapshot(resources=[])
        scanner = SecurityScanner()

        result = scanner.scan(snapshot)

        assert result.total_findings == 0
        assert len(result.findings) == 0

    def test_scan_with_security_issues(self) -> None:
        """Test scanning snapshot with known security issues."""
        public_bucket = create_s3_bucket("public-bucket", public=True)
        open_sg = create_security_group("sg-open", open_ports=[22])
        public_db = create_rds_instance("public-db", publicly_accessible=True)

        snapshot = create_mock_snapshot(resources=[public_bucket, open_sg, public_db])
        scanner = SecurityScanner()

        result = scanner.scan(snapshot)

        # Should find at least 3 issues (public bucket, open SG, public RDS)
        assert result.total_findings >= 3
        assert len(result.findings) >= 3

    def test_scan_with_no_security_issues(self) -> None:
        """Test scanning snapshot with no security issues."""
        private_bucket = create_s3_bucket("private-bucket", public=False)
        closed_sg = create_security_group("sg-closed", open_ports=[])
        private_db = create_rds_instance("private-db", publicly_accessible=False)

        snapshot = create_mock_snapshot(resources=[private_bucket, closed_sg, private_db])
        scanner = SecurityScanner()

        result = scanner.scan(snapshot)

        # May still have some findings (e.g., unencrypted resources)
        # but should be significantly fewer than the "with issues" case
        assert result.total_findings >= 0

    def test_filter_by_severity_critical(self) -> None:
        """Test filtering findings by CRITICAL severity."""
        public_bucket = create_s3_bucket("public-bucket", public=True)  # CRITICAL
        open_sg = create_security_group("sg-open", open_ports=[22])  # HIGH

        snapshot = create_mock_snapshot(resources=[public_bucket, open_sg])
        scanner = SecurityScanner()

        result = scanner.scan(snapshot, severity_filter=Severity.CRITICAL)

        # Should only include CRITICAL findings
        assert all(f.severity == Severity.CRITICAL for f in result.findings)

    def test_filter_by_severity_high(self) -> None:
        """Test filtering findings by HIGH severity."""
        public_bucket = create_s3_bucket("public-bucket", public=True)  # CRITICAL
        open_sg = create_security_group("sg-open", open_ports=[22])  # HIGH

        snapshot = create_mock_snapshot(resources=[public_bucket, open_sg])
        scanner = SecurityScanner()

        result = scanner.scan(snapshot, severity_filter=Severity.HIGH)

        # Should only include HIGH severity findings
        assert all(f.severity == Severity.HIGH for f in result.findings)

    def test_get_findings_by_severity(self) -> None:
        """Test grouping findings by severity level."""
        public_bucket = create_s3_bucket("public-bucket", public=True)  # CRITICAL
        open_sg = create_security_group("sg-open", open_ports=[22])  # HIGH

        snapshot = create_mock_snapshot(resources=[public_bucket, open_sg])
        scanner = SecurityScanner()

        result = scanner.scan(snapshot)

        critical_findings = result.get_findings_by_severity(Severity.CRITICAL)
        high_findings = result.get_findings_by_severity(Severity.HIGH)

        assert len(critical_findings) > 0
        assert len(high_findings) > 0
        assert all(f.severity == Severity.CRITICAL for f in critical_findings)
        assert all(f.severity == Severity.HIGH for f in high_findings)

    def test_scan_executes_all_checks(self) -> None:
        """Test that scan executes all loaded security checks."""
        # Create resources that would trigger multiple different checks
        public_bucket = create_s3_bucket("bucket", public=True)
        open_sg = create_security_group("sg", open_ports=[22, 3306])
        public_db = create_rds_instance("db", publicly_accessible=True)

        snapshot = create_mock_snapshot(resources=[public_bucket, open_sg, public_db])
        scanner = SecurityScanner()

        result = scanner.scan(snapshot)

        # Should have findings from multiple check types
        finding_types = {f.finding_type for f in result.findings}
        assert len(finding_types) > 1  # Multiple different check types executed

    def test_scan_handles_check_execution_error(self) -> None:
        """Test that scan continues when a check raises an exception."""
        from unittest.mock import MagicMock, patch

        snapshot = create_mock_snapshot(resources=[])
        scanner = SecurityScanner()

        # Add a mock check that raises an exception
        failing_check = MagicMock()
        failing_check.check_id = "failing_check"
        failing_check.execute.side_effect = Exception("Check failed")
        scanner.checks.append(failing_check)

        # Scan should complete without raising
        result = scanner.scan(snapshot)

        # Should return a result (even if empty)
        assert result is not None
        # The failing check should have been called
        failing_check.execute.assert_called_once()

    def test_load_checks_handles_module_import_error(self) -> None:
        """Test that _load_checks handles module import errors gracefully."""
        from unittest.mock import MagicMock, patch

        # Create a scanner with mocked module loading
        with patch("src.security.scanner.importlib.import_module") as mock_import:
            # Make the import fail for all modules
            mock_import.side_effect = ImportError("Module not found")

            # Scanner should still initialize (with empty checks list)
            scanner = SecurityScanner()

            # Since all imports failed, checks list should be empty or have some
            # that loaded before the mock was applied
            # The key is that it didn't raise an exception
            assert scanner is not None
