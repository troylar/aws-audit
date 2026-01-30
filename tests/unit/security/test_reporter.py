"""Unit tests for SecurityReporter."""

from __future__ import annotations

import json
from pathlib import Path

from src.models.security_finding import SecurityFinding, Severity
from src.security.reporter import SecurityReporter


class TestSecurityReporter:
    """Tests for SecurityReporter."""

    def test_reporter_initializes(self) -> None:
        """Test that reporter initializes."""
        reporter = SecurityReporter()
        assert reporter is not None

    def test_format_findings_for_terminal(self) -> None:
        """Test formatting findings for terminal output with Rich."""
        finding = SecurityFinding(
            resource_arn="arn:aws:s3:::test-bucket",
            finding_type="s3_public_bucket",
            severity=Severity.CRITICAL,
            description="S3 bucket is publicly accessible",
            remediation="Enable block public access settings",
            cis_control="2.1.5",
        )

        reporter = SecurityReporter()
        output = reporter.format_terminal([finding])

        # Should return a string representation
        assert output is not None
        assert isinstance(output, str)
        # Should include key information
        assert "CRITICAL" in output or "critical" in output
        assert "s3" in output.lower()

    def test_export_to_json(self, tmp_path: Path) -> None:
        """Test exporting findings to JSON format."""
        finding1 = SecurityFinding(
            resource_arn="arn:aws:s3:::bucket1",
            finding_type="s3_public_bucket",
            severity=Severity.CRITICAL,
            description="Bucket is public",
            remediation="Fix it",
            cis_control="2.1.5",
        )

        finding2 = SecurityFinding(
            resource_arn="arn:aws:s3:::bucket2",
            finding_type="s3_public_bucket",
            severity=Severity.HIGH,
            description="Another issue",
            remediation="Fix this too",
        )

        findings = [finding1, finding2]
        reporter = SecurityReporter()

        output_file = tmp_path / "findings.json"
        reporter.export_json(findings, str(output_file))

        # Verify file was created
        assert output_file.exists()

        # Verify JSON structure
        with open(output_file, "r") as f:
            data = json.load(f)

        assert "findings" in data
        assert len(data["findings"]) == 2
        assert data["findings"][0]["resource_arn"] == "arn:aws:s3:::bucket1"
        assert data["findings"][0]["severity"] == "critical"

    def test_export_to_csv(self, tmp_path: Path) -> None:
        """Test exporting findings to CSV format."""
        finding = SecurityFinding(
            resource_arn="arn:aws:s3:::test-bucket",
            finding_type="s3_public_bucket",
            severity=Severity.CRITICAL,
            description="Test finding",
            remediation="Fix it",
            cis_control="2.1.5",
        )

        findings = [finding]
        reporter = SecurityReporter()

        output_file = tmp_path / "findings.csv"
        reporter.export_csv(findings, str(output_file))

        # Verify file was created
        assert output_file.exists()

        # Verify CSV content
        with open(output_file, "r") as f:
            content = f.read()

        # Should have header row
        assert "resource_arn" in content or "Resource" in content
        assert "severity" in content or "Severity" in content
        # Should have data
        assert "arn:aws:s3:::test-bucket" in content
        assert "critical" in content.lower()

    def test_group_findings_by_severity(self) -> None:
        """Test grouping findings by severity for display."""
        critical_finding = SecurityFinding(
            resource_arn="arn:aws:s3:::bucket",
            finding_type="s3_public_bucket",
            severity=Severity.CRITICAL,
            description="Critical issue",
            remediation="Fix",
        )

        high_finding = SecurityFinding(
            resource_arn="arn:aws:ec2:us-east-1:123:sg/sg-1",
            finding_type="security_group_open",
            severity=Severity.HIGH,
            description="High issue",
            remediation="Fix",
        )

        medium_finding = SecurityFinding(
            resource_arn="arn:aws:ec2:us-east-1:123:instance/i-1",
            finding_type="ec2_imdsv1",
            severity=Severity.MEDIUM,
            description="Medium issue",
            remediation="Fix",
        )

        findings = [critical_finding, high_finding, medium_finding]
        reporter = SecurityReporter()

        grouped = reporter.group_by_severity(findings)

        assert Severity.CRITICAL in grouped
        assert Severity.HIGH in grouped
        assert Severity.MEDIUM in grouped
        assert len(grouped[Severity.CRITICAL]) == 1
        assert len(grouped[Severity.HIGH]) == 1
        assert len(grouped[Severity.MEDIUM]) == 1

    def test_generate_summary_stats(self) -> None:
        """Test generating summary statistics for findings."""
        findings = [
            SecurityFinding(
                resource_arn=f"arn:aws:s3:::bucket{i}",
                finding_type="s3_public_bucket",
                severity=Severity.CRITICAL,
                description="Test",
                remediation="Fix",
            )
            for i in range(3)
        ]

        findings.extend(
            [
                SecurityFinding(
                    resource_arn=f"arn:aws:ec2:us-east-1:123:sg/sg-{i}",
                    finding_type="security_group_open",
                    severity=Severity.HIGH,
                    description="Test",
                    remediation="Fix",
                )
                for i in range(2)
            ]
        )

        reporter = SecurityReporter()
        summary = reporter.generate_summary(findings)

        assert summary["total_findings"] == 5
        assert summary["critical_count"] == 3
        assert summary["high_count"] == 2
        assert summary["medium_count"] == 0
        assert summary["low_count"] == 0

    def test_format_empty_findings_list(self) -> None:
        """Test formatting empty findings list."""
        reporter = SecurityReporter()
        output = reporter.format_terminal([])

        assert output is not None
        # Should indicate no findings
        assert "no" in output.lower() or "0" in output

    def test_export_empty_findings_to_json(self, tmp_path: Path) -> None:
        """Test exporting empty findings list to JSON."""
        reporter = SecurityReporter()
        output_file = tmp_path / "empty.json"

        reporter.export_json([], str(output_file))

        assert output_file.exists()

        with open(output_file, "r") as f:
            data = json.load(f)

        assert "findings" in data
        assert len(data["findings"]) == 0

    def test_format_terminal_with_all_severities(self) -> None:
        """Test formatting findings with all severity levels."""
        findings = [
            SecurityFinding(
                resource_arn="arn:aws:s3:::critical-bucket",
                finding_type="s3_public_bucket",
                severity=Severity.CRITICAL,
                description="Critical issue",
                remediation="Fix critical",
            ),
            SecurityFinding(
                resource_arn="arn:aws:ec2:us-east-1:123:sg/sg-high",
                finding_type="security_group_open",
                severity=Severity.HIGH,
                description="High issue",
                remediation="Fix high",
            ),
            SecurityFinding(
                resource_arn="arn:aws:ec2:us-east-1:123:instance/i-medium",
                finding_type="ec2_imdsv1",
                severity=Severity.MEDIUM,
                description="Medium issue",
                remediation="Fix medium",
            ),
            SecurityFinding(
                resource_arn="arn:aws:s3:::low-bucket",
                finding_type="minor_issue",
                severity=Severity.LOW,
                description="Low issue",
                remediation="Fix low",
            ),
        ]

        reporter = SecurityReporter()
        output = reporter.format_terminal(findings)

        # Should contain all severity levels
        assert "CRITICAL" in output or "critical" in output.lower()
        assert "HIGH" in output or "high" in output.lower()
        assert "MEDIUM" in output or "medium" in output.lower()
        assert "LOW" in output or "low" in output.lower()

    def test_format_terminal_with_long_description(self) -> None:
        """Test that long descriptions are truncated in terminal output."""
        long_description = (
            "This is a very long description that exceeds sixty characters "
            "and should be truncated when displayed in the terminal table output."
        )

        finding = SecurityFinding(
            resource_arn="arn:aws:s3:::test-bucket",
            finding_type="test_finding",
            severity=Severity.HIGH,
            description=long_description,
            remediation="Fix it",
        )

        reporter = SecurityReporter()
        output = reporter.format_terminal([finding])

        # Output should contain truncated version (not the full description)
        assert output is not None
        # The full description should not appear
        assert long_description not in output
        # Should contain "..." indicating truncation
        assert "..." in output

    def test_format_terminal_resource_with_slash_in_arn(self) -> None:
        """Test resource display for ARN with slash."""
        finding = SecurityFinding(
            resource_arn="arn:aws:ec2:us-east-1:123456789012:instance/i-12345678",
            finding_type="test_finding",
            severity=Severity.MEDIUM,
            description="Test finding",
            remediation="Fix it",
        )

        reporter = SecurityReporter()
        output = reporter.format_terminal([finding])

        # Should extract resource ID from ARN
        assert "i-12345678" in output

    def test_format_terminal_resource_with_colon_in_arn(self) -> None:
        """Test resource display for ARN without slash (uses colon)."""
        finding = SecurityFinding(
            resource_arn="arn:aws:s3:::my-bucket-name",
            finding_type="test_finding",
            severity=Severity.LOW,
            description="Test finding",
            remediation="Fix it",
        )

        reporter = SecurityReporter()
        output = reporter.format_terminal([finding])

        # Should extract resource ID from ARN (last part after colon)
        assert "my-bucket-name" in output
