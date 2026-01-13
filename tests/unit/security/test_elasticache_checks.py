"""Unit tests for ElastiCache security checks."""

from __future__ import annotations

from src.models.security_finding import Severity
from src.security.checks.elasticache_checks import ElastiCacheEncryptionCheck
from tests.fixtures.snapshots import create_elasticache_cluster, create_mock_snapshot


class TestElastiCacheEncryptionCheck:
    """Tests for ElastiCacheEncryptionCheck."""

    def test_check_id_and_severity(self) -> None:
        """Test that check has correct ID and severity."""
        check = ElastiCacheEncryptionCheck()
        assert check.check_id == "elasticache_unencrypted"
        assert check.severity == Severity.MEDIUM

    def test_detect_unencrypted_at_rest(self) -> None:
        """Test detection of cluster without encryption at rest."""
        unencrypted_cluster = create_elasticache_cluster(
            "redis-001", engine="redis", encryption_at_rest=False, encryption_in_transit=True
        )
        snapshot = create_mock_snapshot(resources=[unencrypted_cluster])

        check = ElastiCacheEncryptionCheck()
        findings = check.execute(snapshot)

        assert len(findings) >= 1
        # Should have at least one finding for missing at-rest encryption
        at_rest_findings = [f for f in findings if "at rest" in f.description.lower()]
        assert len(at_rest_findings) == 1
        assert at_rest_findings[0].resource_arn == unencrypted_cluster.arn
        assert at_rest_findings[0].severity == Severity.MEDIUM

    def test_detect_unencrypted_in_transit(self) -> None:
        """Test detection of cluster without encryption in transit."""
        unencrypted_cluster = create_elasticache_cluster(
            "redis-002", engine="redis", encryption_at_rest=True, encryption_in_transit=False
        )
        snapshot = create_mock_snapshot(resources=[unencrypted_cluster])

        check = ElastiCacheEncryptionCheck()
        findings = check.execute(snapshot)

        assert len(findings) >= 1
        # Should have at least one finding for missing in-transit encryption
        in_transit_findings = [f for f in findings if "in transit" in f.description.lower()]
        assert len(in_transit_findings) == 1
        assert in_transit_findings[0].resource_arn == unencrypted_cluster.arn

    def test_detect_fully_unencrypted(self) -> None:
        """Test detection of cluster with no encryption at all."""
        unencrypted_cluster = create_elasticache_cluster(
            "redis-003", engine="redis", encryption_at_rest=False, encryption_in_transit=False
        )
        snapshot = create_mock_snapshot(resources=[unencrypted_cluster])

        check = ElastiCacheEncryptionCheck()
        findings = check.execute(snapshot)

        # Should flag both at-rest and in-transit
        assert len(findings) == 2
        assert all(f.severity == Severity.MEDIUM for f in findings)

    def test_encrypted_cluster_no_findings(self) -> None:
        """Test that fully encrypted cluster produces no findings."""
        encrypted_cluster = create_elasticache_cluster(
            "redis-secure", engine="redis", encryption_at_rest=True, encryption_in_transit=True
        )
        snapshot = create_mock_snapshot(resources=[encrypted_cluster])

        check = ElastiCacheEncryptionCheck()
        findings = check.execute(snapshot)

        assert len(findings) == 0

    def test_memcached_in_transit_only(self) -> None:
        """Test that Memcached (which doesn't support at-rest) only checks in-transit."""
        # Memcached doesn't support encryption at rest, so we shouldn't flag it
        memcached_cluster = create_elasticache_cluster(
            "memcached-001", engine="memcached", encryption_at_rest=False, encryption_in_transit=False
        )
        snapshot = create_mock_snapshot(resources=[memcached_cluster])

        check = ElastiCacheEncryptionCheck()
        findings = check.execute(snapshot)

        # Should only flag in-transit encryption for memcached
        assert len(findings) == 1
        assert "in transit" in findings[0].description.lower()
        assert "at rest" not in findings[0].description.lower()

    def test_multiple_clusters_mixed_encryption(self) -> None:
        """Test scanning multiple clusters with mixed encryption settings."""
        cluster1 = create_elasticache_cluster(
            "redis-001", engine="redis", encryption_at_rest=True, encryption_in_transit=True
        )
        cluster2 = create_elasticache_cluster(
            "redis-002", engine="redis", encryption_at_rest=False, encryption_in_transit=True
        )
        cluster3 = create_elasticache_cluster(
            "redis-003", engine="redis", encryption_at_rest=True, encryption_in_transit=False
        )

        snapshot = create_mock_snapshot(resources=[cluster1, cluster2, cluster3])

        check = ElastiCacheEncryptionCheck()
        findings = check.execute(snapshot)

        # cluster1 is fully encrypted: 0 findings
        # cluster2 missing at-rest: 1 finding
        # cluster3 missing in-transit: 1 finding
        assert len(findings) == 2

        finding_arns = [f.resource_arn for f in findings]
        assert cluster1.arn not in finding_arns  # Fully encrypted
        assert cluster2.arn in finding_arns  # Missing at-rest
        assert cluster3.arn in finding_arns  # Missing in-transit

    def test_remediation_guidance_present(self) -> None:
        """Test that findings include remediation guidance."""
        unencrypted_cluster = create_elasticache_cluster(
            "redis-bad", engine="redis", encryption_at_rest=False, encryption_in_transit=False
        )
        snapshot = create_mock_snapshot(resources=[unencrypted_cluster])

        check = ElastiCacheEncryptionCheck()
        findings = check.execute(snapshot)

        assert len(findings) == 2
        for finding in findings:
            assert finding.remediation
            assert len(finding.remediation) > 0

    def test_empty_snapshot_no_findings(self) -> None:
        """Test that empty snapshot produces no findings."""
        snapshot = create_mock_snapshot(resources=[])

        check = ElastiCacheEncryptionCheck()
        findings = check.execute(snapshot)

        assert len(findings) == 0

    def test_non_elasticache_resources_ignored(self) -> None:
        """Test that non-ElastiCache resources are ignored."""
        from tests.fixtures.snapshots import create_rds_instance, create_s3_bucket

        s3_bucket = create_s3_bucket("test-bucket")
        rds_instance = create_rds_instance("test-db")
        snapshot = create_mock_snapshot(resources=[s3_bucket, rds_instance])

        check = ElastiCacheEncryptionCheck()
        findings = check.execute(snapshot)

        assert len(findings) == 0

    def test_cluster_with_raw_config_none(self) -> None:
        """Test that cluster with raw_config=None is skipped."""
        from src.models.resource import Resource

        cluster = Resource(
            arn="arn:aws:elasticache:us-east-1:123456789012:cluster:no-config",
            resource_type="elasticache:cluster",
            name="no-config",
            region="us-east-1",
            config_hash="a" * 64,
            raw_config=None,
            tags={},
        )
        snapshot = create_mock_snapshot(resources=[cluster])

        check = ElastiCacheEncryptionCheck()
        findings = check.execute(snapshot)

        assert len(findings) == 0
