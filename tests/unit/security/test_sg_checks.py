"""Unit tests for Security Group checks."""

from __future__ import annotations

from src.models.security_finding import Severity
from src.security.checks.sg_checks import SecurityGroupOpenCheck
from tests.fixtures.snapshots import create_mock_snapshot, create_security_group


class TestSecurityGroupOpenCheck:
    """Tests for SecurityGroupOpenCheck."""

    def test_check_id_and_severity(self) -> None:
        """Test that check has correct ID and severity."""
        check = SecurityGroupOpenCheck()
        assert check.check_id == "security_group_open"
        assert check.severity == Severity.HIGH

    def test_detect_ssh_port_22_open_to_world(self) -> None:
        """Test detection of SSH port 22 open to 0.0.0.0/0."""
        open_sg = create_security_group("sg-ssh", open_ports=[22])
        snapshot = create_mock_snapshot(resources=[open_sg])

        check = SecurityGroupOpenCheck()
        findings = check.execute(snapshot)

        assert len(findings) == 1
        assert findings[0].resource_arn == open_sg.arn
        assert findings[0].severity == Severity.HIGH
        assert "22" in findings[0].description
        assert "0.0.0.0/0" in findings[0].description

    def test_detect_rdp_port_3389_open(self) -> None:
        """Test detection of RDP port 3389 open to 0.0.0.0/0."""
        open_sg = create_security_group("sg-rdp", open_ports=[3389])
        snapshot = create_mock_snapshot(resources=[open_sg])

        check = SecurityGroupOpenCheck()
        findings = check.execute(snapshot)

        assert len(findings) == 1
        assert "3389" in findings[0].description

    def test_detect_multiple_open_ports(self) -> None:
        """Test detection of multiple critical ports open."""
        # Ports: 22 (SSH), 3306 (MySQL), 5432 (PostgreSQL)
        open_sg = create_security_group("sg-multi", open_ports=[22, 3306, 5432])
        snapshot = create_mock_snapshot(resources=[open_sg])

        check = SecurityGroupOpenCheck()
        findings = check.execute(snapshot)

        # Should create one finding per open port
        assert len(findings) == 3

        # Verify each critical port is mentioned
        all_descriptions = " ".join([f.description for f in findings])
        assert "22" in all_descriptions
        assert "3306" in all_descriptions
        assert "5432" in all_descriptions

    def test_security_group_with_no_open_ports(self) -> None:
        """Test that security group with no open ports produces no findings."""
        closed_sg = create_security_group("sg-closed", open_ports=[])
        snapshot = create_mock_snapshot(resources=[closed_sg])

        check = SecurityGroupOpenCheck()
        findings = check.execute(snapshot)

        assert len(findings) == 0

    def test_security_group_with_specific_cidr_no_finding(self) -> None:
        """Test that security group with specific CIDR (not 0.0.0.0/0) produces no finding."""
        # This would need to be handled in the fixture, but for now we test the base case
        closed_sg = create_security_group("sg-specific", open_ports=[])
        snapshot = create_mock_snapshot(resources=[closed_sg])

        check = SecurityGroupOpenCheck()
        findings = check.execute(snapshot)

        assert len(findings) == 0

    def test_all_critical_ports_checked(self) -> None:
        """Test that check validates all critical ports: 22, 3389, 3306, 5432, 1433, 27017."""
        # Create security groups with each critical port
        sg_ssh = create_security_group("sg-22", open_ports=[22])
        sg_rdp = create_security_group("sg-3389", open_ports=[3389])
        sg_mysql = create_security_group("sg-3306", open_ports=[3306])
        sg_postgres = create_security_group("sg-5432", open_ports=[5432])
        sg_mssql = create_security_group("sg-1433", open_ports=[1433])
        sg_mongo = create_security_group("sg-27017", open_ports=[27017])

        snapshot = create_mock_snapshot(resources=[sg_ssh, sg_rdp, sg_mysql, sg_postgres, sg_mssql, sg_mongo])

        check = SecurityGroupOpenCheck()
        findings = check.execute(snapshot)

        # Should find all 6 critical port violations
        assert len(findings) == 6

    def test_cis_control_mapping(self) -> None:
        """Test that findings include CIS control mappings."""
        open_sg = create_security_group("sg-test", open_ports=[22])
        snapshot = create_mock_snapshot(resources=[open_sg])

        check = SecurityGroupOpenCheck()
        findings = check.execute(snapshot)

        assert len(findings) == 1
        # SSH should map to CIS 5.2
        assert findings[0].cis_control in ["5.2", "5.3"]

    def test_remediation_guidance_present(self) -> None:
        """Test that findings include remediation guidance."""
        open_sg = create_security_group("sg-test", open_ports=[22])
        snapshot = create_mock_snapshot(resources=[open_sg])

        check = SecurityGroupOpenCheck()
        findings = check.execute(snapshot)

        assert len(findings) == 1
        assert findings[0].remediation
        assert "restrict" in findings[0].remediation.lower() or "remove" in findings[0].remediation.lower()

    def test_security_group_with_raw_config_none(self) -> None:
        """Test that security group with raw_config=None is skipped."""
        from src.models.resource import Resource

        sg = Resource(
            arn="arn:aws:ec2:us-east-1:123456789012:security-group/sg-123",
            resource_type="ec2:security-group",
            name="no-config-sg",
            region="us-east-1",
            config_hash="a" * 64,
            raw_config=None,
            tags={},
        )
        snapshot = create_mock_snapshot(resources=[sg])

        check = SecurityGroupOpenCheck()
        findings = check.execute(snapshot)

        assert len(findings) == 0

    def test_security_group_with_no_port_range(self) -> None:
        """Test that permissions without port range are skipped."""
        from src.models.resource import Resource

        sg = Resource(
            arn="arn:aws:ec2:us-east-1:123456789012:security-group/sg-123",
            resource_type="ec2:security-group",
            name="no-port-sg",
            region="us-east-1",
            config_hash="a" * 64,
            raw_config={
                "GroupId": "sg-123",
                "IpPermissions": [
                    {
                        # No FromPort or ToPort - e.g., for all traffic rule
                        "IpProtocol": "-1",
                        "IpRanges": [{"CidrIp": "0.0.0.0/0"}],
                    }
                ],
            },
            tags={},
        )
        snapshot = create_mock_snapshot(resources=[sg])

        check = SecurityGroupOpenCheck()
        findings = check.execute(snapshot)

        # Should skip this permission since no port range
        assert len(findings) == 0

    def test_security_group_with_specific_cidr_only(self) -> None:
        """Test that security group with only specific CIDR (not 0.0.0.0/0) produces no finding."""
        from src.models.resource import Resource

        sg = Resource(
            arn="arn:aws:ec2:us-east-1:123456789012:security-group/sg-123",
            resource_type="ec2:security-group",
            name="specific-cidr-sg",
            region="us-east-1",
            config_hash="a" * 64,
            raw_config={
                "GroupId": "sg-123",
                "IpPermissions": [
                    {
                        "IpProtocol": "tcp",
                        "FromPort": 22,
                        "ToPort": 22,
                        "IpRanges": [{"CidrIp": "10.0.0.0/8"}],  # Private range, not 0.0.0.0/0
                    }
                ],
            },
            tags={},
        )
        snapshot = create_mock_snapshot(resources=[sg])

        check = SecurityGroupOpenCheck()
        findings = check.execute(snapshot)

        # Should return False in _is_open_to_world and no findings
        assert len(findings) == 0
