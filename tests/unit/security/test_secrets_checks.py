"""Unit tests for Secrets Manager security checks."""

from __future__ import annotations

from src.models.security_finding import Severity
from src.security.checks.secrets_checks import SecretsRotationCheck
from tests.fixtures.snapshots import create_mock_snapshot, create_secrets_manager_secret


class TestSecretsRotationCheck:
    """Tests for SecretsRotationCheck."""

    def test_check_id_and_severity(self) -> None:
        """Test that check has correct ID and severity."""
        check = SecretsRotationCheck()
        assert check.check_id == "secrets_rotation_age"
        assert check.severity == Severity.MEDIUM

    def test_detect_secret_not_rotated_90_days(self) -> None:
        """Test detection of secret not rotated in 90+ days."""
        old_secret = create_secrets_manager_secret("old-secret", last_rotated_days_ago=120)
        snapshot = create_mock_snapshot(resources=[old_secret])

        check = SecretsRotationCheck()
        findings = check.execute(snapshot)

        assert len(findings) == 1
        assert findings[0].resource_arn == old_secret.arn
        assert findings[0].severity == Severity.MEDIUM
        assert "90" in findings[0].description or "120" in findings[0].description

    def test_recently_rotated_secret_no_findings(self) -> None:
        """Test that recently rotated secret produces no findings."""
        recent_secret = create_secrets_manager_secret("recent-secret", last_rotated_days_ago=30)
        snapshot = create_mock_snapshot(resources=[recent_secret])

        check = SecretsRotationCheck()
        findings = check.execute(snapshot)

        assert len(findings) == 0

    def test_secret_exactly_90_days_no_findings(self) -> None:
        """Test that secret rotated exactly 90 days ago produces no findings (boundary)."""
        secret_90 = create_secrets_manager_secret("secret-90", last_rotated_days_ago=90)
        snapshot = create_mock_snapshot(resources=[secret_90])

        check = SecretsRotationCheck()
        findings = check.execute(snapshot)

        assert len(findings) == 0

    def test_secret_91_days_creates_finding(self) -> None:
        """Test that secret rotated 91 days ago creates a finding (just over threshold)."""
        secret_91 = create_secrets_manager_secret("secret-91", last_rotated_days_ago=91)
        snapshot = create_mock_snapshot(resources=[secret_91])

        check = SecretsRotationCheck()
        findings = check.execute(snapshot)

        assert len(findings) == 1

    def test_multiple_secrets_mixed_rotation_age(self) -> None:
        """Test scanning multiple secrets with mixed rotation ages."""
        old_secret1 = create_secrets_manager_secret("old-1", last_rotated_days_ago=150)
        recent_secret = create_secrets_manager_secret("recent", last_rotated_days_ago=20)
        old_secret2 = create_secrets_manager_secret("old-2", last_rotated_days_ago=200)

        snapshot = create_mock_snapshot(resources=[old_secret1, recent_secret, old_secret2])

        check = SecretsRotationCheck()
        findings = check.execute(snapshot)

        assert len(findings) == 2
        finding_arns = [f.resource_arn for f in findings]
        assert old_secret1.arn in finding_arns
        assert old_secret2.arn in finding_arns
        assert recent_secret.arn not in finding_arns

    def test_remediation_guidance_present(self) -> None:
        """Test that findings include remediation guidance."""
        old_secret = create_secrets_manager_secret("test-secret", last_rotated_days_ago=100)
        snapshot = create_mock_snapshot(resources=[old_secret])

        check = SecretsRotationCheck()
        findings = check.execute(snapshot)

        assert len(findings) == 1
        assert findings[0].remediation
        assert "rotate" in findings[0].remediation.lower()

    def test_empty_snapshot_no_findings(self) -> None:
        """Test that empty snapshot produces no findings."""
        snapshot = create_mock_snapshot(resources=[])

        check = SecretsRotationCheck()
        findings = check.execute(snapshot)

        assert len(findings) == 0

    def test_secret_with_raw_config_none(self) -> None:
        """Test that secret with raw_config=None is skipped."""
        from src.models.resource import Resource

        # Create secret with raw_config=None
        secret = Resource(
            arn="arn:aws:secretsmanager:us-east-1:123456789012:secret:no-config",
            resource_type="secretsmanager:secret",
            name="no-config",
            region="us-east-1",
            config_hash="a" * 64,
            raw_config=None,  # No config
            tags={},
        )
        snapshot = create_mock_snapshot(resources=[secret])

        check = SecretsRotationCheck()
        findings = check.execute(snapshot)

        # Should be skipped, no findings
        assert len(findings) == 0

    def test_secret_without_last_rotated_date(self) -> None:
        """Test that secret without LastRotatedDate is skipped."""
        from src.models.resource import Resource

        # Create secret without LastRotatedDate
        secret = Resource(
            arn="arn:aws:secretsmanager:us-east-1:123456789012:secret:no-rotation",
            resource_type="secretsmanager:secret",
            name="no-rotation",
            region="us-east-1",
            config_hash="a" * 64,
            raw_config={
                "Name": "no-rotation",
                "RotationEnabled": False,
                # No LastRotatedDate field
            },
            tags={},
        )
        snapshot = create_mock_snapshot(resources=[secret])

        check = SecretsRotationCheck()
        findings = check.execute(snapshot)

        # Should be skipped, no findings
        assert len(findings) == 0

    def test_secret_with_datetime_object(self) -> None:
        """Test handling secret with datetime object instead of string."""
        from datetime import datetime, timedelta, timezone

        from src.models.resource import Resource

        # Create date 120 days ago as datetime object (not string)
        last_rotated = datetime.now(timezone.utc) - timedelta(days=120)

        secret = Resource(
            arn="arn:aws:secretsmanager:us-east-1:123456789012:secret:datetime-secret",
            resource_type="secretsmanager:secret",
            name="datetime-secret",
            region="us-east-1",
            config_hash="a" * 64,
            raw_config={
                "Name": "datetime-secret",
                "LastRotatedDate": last_rotated,  # datetime object, not string
                "RotationEnabled": True,
            },
            tags={},
        )
        snapshot = create_mock_snapshot(resources=[secret])

        check = SecretsRotationCheck()
        findings = check.execute(snapshot)

        # Should find the secret that hasn't been rotated
        assert len(findings) == 1
        assert "120" in findings[0].description

    def test_secret_with_naive_datetime_object(self) -> None:
        """Test handling secret with naive datetime object (no timezone)."""
        from datetime import datetime, timedelta

        from src.models.resource import Resource

        # Create date 120 days ago as naive datetime (no tzinfo)
        last_rotated = datetime.now() - timedelta(days=120)

        secret = Resource(
            arn="arn:aws:secretsmanager:us-east-1:123456789012:secret:naive-secret",
            resource_type="secretsmanager:secret",
            name="naive-secret",
            region="us-east-1",
            config_hash="a" * 64,
            raw_config={
                "Name": "naive-secret",
                "LastRotatedDate": last_rotated,  # naive datetime (no timezone)
                "RotationEnabled": True,
            },
            tags={},
        )
        snapshot = create_mock_snapshot(resources=[secret])

        check = SecretsRotationCheck()
        findings = check.execute(snapshot)

        # Should find the secret after adding UTC timezone
        assert len(findings) == 1
