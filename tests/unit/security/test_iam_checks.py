"""Unit tests for IAM security checks."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.models.resource import Resource
from src.models.security_finding import Severity
from src.security.checks.iam_checks import IAMCredentialAgeCheck
from tests.fixtures.snapshots import create_iam_user, create_mock_snapshot


class TestIAMCredentialAgeCheck:
    """Tests for IAMCredentialAgeCheck."""

    def test_check_id_and_severity(self) -> None:
        """Test that check has correct ID and severity."""
        check = IAMCredentialAgeCheck()
        assert check.check_id == "iam_credential_age"
        assert check.severity == Severity.MEDIUM

    def test_detect_credentials_older_than_90_days(self) -> None:
        """Test detection of IAM credentials older than 90 days."""
        old_user = create_iam_user("old-user", access_key_age_days=120)
        snapshot = create_mock_snapshot(resources=[old_user])

        check = IAMCredentialAgeCheck()
        findings = check.execute(snapshot)

        assert len(findings) == 1
        assert findings[0].resource_arn == old_user.arn
        assert findings[0].severity == Severity.MEDIUM
        assert "90" in findings[0].description or "120" in findings[0].description

    def test_credentials_less_than_90_days_no_findings(self) -> None:
        """Test that credentials less than 90 days old produce no findings."""
        recent_user = create_iam_user("recent-user", access_key_age_days=30)
        snapshot = create_mock_snapshot(resources=[recent_user])

        check = IAMCredentialAgeCheck()
        findings = check.execute(snapshot)

        assert len(findings) == 0

    def test_credentials_exactly_90_days_no_findings(self) -> None:
        """Test that credentials exactly 90 days old produce no findings (boundary)."""
        user_90_days = create_iam_user("user-90", access_key_age_days=90)
        snapshot = create_mock_snapshot(resources=[user_90_days])

        check = IAMCredentialAgeCheck()
        findings = check.execute(snapshot)

        # 90 days is the threshold - should not trigger
        assert len(findings) == 0

    def test_credentials_91_days_creates_finding(self) -> None:
        """Test that credentials 91 days old create a finding (just over threshold)."""
        user_91_days = create_iam_user("user-91", access_key_age_days=91)
        snapshot = create_mock_snapshot(resources=[user_91_days])

        check = IAMCredentialAgeCheck()
        findings = check.execute(snapshot)

        assert len(findings) == 1

    def test_multiple_users_mixed_credential_age(self) -> None:
        """Test scanning multiple IAM users with mixed credential ages."""
        old_user1 = create_iam_user("old-1", access_key_age_days=150)
        recent_user = create_iam_user("recent", access_key_age_days=30)
        old_user2 = create_iam_user("old-2", access_key_age_days=200)

        snapshot = create_mock_snapshot(resources=[old_user1, recent_user, old_user2])

        check = IAMCredentialAgeCheck()
        findings = check.execute(snapshot)

        assert len(findings) == 2
        finding_arns = [f.resource_arn for f in findings]
        assert old_user1.arn in finding_arns
        assert old_user2.arn in finding_arns
        assert recent_user.arn not in finding_arns

    def test_cis_control_mapping(self) -> None:
        """Test that findings include CIS control mappings."""
        old_user = create_iam_user("test-user", access_key_age_days=100)
        snapshot = create_mock_snapshot(resources=[old_user])

        check = IAMCredentialAgeCheck()
        findings = check.execute(snapshot)

        assert len(findings) == 1
        # Should map to CIS 1.3 or 1.4
        assert findings[0].cis_control in ["1.3", "1.4"]

    def test_remediation_guidance_present(self) -> None:
        """Test that findings include remediation guidance."""
        old_user = create_iam_user("test-user", access_key_age_days=100)
        snapshot = create_mock_snapshot(resources=[old_user])

        check = IAMCredentialAgeCheck()
        findings = check.execute(snapshot)

        assert len(findings) == 1
        assert findings[0].remediation
        assert "rotate" in findings[0].remediation.lower() or "replace" in findings[0].remediation.lower()

    def test_empty_snapshot_no_findings(self) -> None:
        """Test that empty snapshot produces no findings."""
        snapshot = create_mock_snapshot(resources=[])

        check = IAMCredentialAgeCheck()
        findings = check.execute(snapshot)

        assert len(findings) == 0

    def test_user_with_raw_config_none(self) -> None:
        """Test that user with raw_config=None is skipped."""
        # Create user with raw_config=None
        user = Resource(
            arn="arn:aws:iam::123456789012:user/no-config-user",
            resource_type="iam:user",
            name="no-config-user",
            region="global",
            config_hash="a" * 64,
            raw_config=None,  # No config
            tags={},
        )
        snapshot = create_mock_snapshot(resources=[user])

        check = IAMCredentialAgeCheck()
        findings = check.execute(snapshot)

        # Should be skipped, no findings
        assert len(findings) == 0

    def test_access_key_without_create_date(self) -> None:
        """Test that access key without CreateDate is skipped."""
        # Create user with access key that has no CreateDate
        user = Resource(
            arn="arn:aws:iam::123456789012:user/no-date-user",
            resource_type="iam:user",
            name="no-date-user",
            region="global",
            config_hash="a" * 64,
            raw_config={
                "UserName": "no-date-user",
                "AccessKeys": [
                    {"AccessKeyId": "AKIAXXXXXXXXXXXXXXXX", "Status": "Active"}
                    # No CreateDate field
                ],
            },
            tags={},
        )
        snapshot = create_mock_snapshot(resources=[user])

        check = IAMCredentialAgeCheck()
        findings = check.execute(snapshot)

        # Should be skipped, no findings
        assert len(findings) == 0

    def test_access_key_with_datetime_object(self) -> None:
        """Test handling access key with datetime object instead of string."""
        # Create date 120 days ago as datetime object (not string)
        key_created = datetime.now(timezone.utc) - timedelta(days=120)

        user = Resource(
            arn="arn:aws:iam::123456789012:user/datetime-user",
            resource_type="iam:user",
            name="datetime-user",
            region="global",
            config_hash="a" * 64,
            raw_config={
                "UserName": "datetime-user",
                "AccessKeys": [
                    {
                        "AccessKeyId": "AKIAXXXXXXXXXXXXXXXX",
                        "CreateDate": key_created,  # datetime object, not string
                        "Status": "Active",
                    }
                ],
            },
            tags={},
        )
        snapshot = create_mock_snapshot(resources=[user])

        check = IAMCredentialAgeCheck()
        findings = check.execute(snapshot)

        # Should find the old key
        assert len(findings) == 1
        assert "120" in findings[0].description

    def test_access_key_with_naive_datetime_object(self) -> None:
        """Test handling access key with naive datetime object (no timezone)."""
        # Create date 120 days ago as naive datetime (no tzinfo)
        key_created = datetime.now() - timedelta(days=120)

        user = Resource(
            arn="arn:aws:iam::123456789012:user/naive-datetime-user",
            resource_type="iam:user",
            name="naive-datetime-user",
            region="global",
            config_hash="a" * 64,
            raw_config={
                "UserName": "naive-datetime-user",
                "AccessKeys": [
                    {
                        "AccessKeyId": "AKIAXXXXXXXXXXXXXXXX",
                        "CreateDate": key_created,  # naive datetime (no timezone)
                        "Status": "Active",
                    }
                ],
            },
            tags={},
        )
        snapshot = create_mock_snapshot(resources=[user])

        check = IAMCredentialAgeCheck()
        findings = check.execute(snapshot)

        # Should find the old key after adding UTC timezone
        assert len(findings) == 1
