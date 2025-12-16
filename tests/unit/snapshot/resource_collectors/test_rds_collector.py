"""Unit tests for RDS resource collector."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.snapshot.resource_collectors.rds import RDSCollector


class TestRDSCollector:
    """Tests for RDSCollector."""

    @pytest.fixture
    def collector(self):
        """Create an RDSCollector instance for testing."""
        mock_session = MagicMock()
        mock_session.profile_name = "default"
        return RDSCollector(session=mock_session, region="us-east-1")

    def test_service_name(self, collector):
        """Test service name property."""
        assert collector.service_name == "rds"

    def test_is_global_service(self, collector):
        """Test that RDS is not a global service."""
        assert collector.is_global_service is False

    def test_collect_db_instances(self, collector):
        """Test collecting RDS DB instances."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [
            {
                "DBInstances": [
                    {
                        "DBInstanceIdentifier": "my-database",
                        "DBInstanceArn": "arn:aws:rds:us-east-1:123456789012:db:my-database",
                        "DBInstanceClass": "db.t3.micro",
                        "Engine": "mysql",
                        "InstanceCreateTime": datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
                    }
                ]
            }
        ]
        mock_client.list_tags_for_resource.return_value = {
            "TagList": [
                {"Key": "Environment", "Value": "production"},
                {"Key": "Team", "Value": "backend"},
            ]
        }

        with patch.object(collector, "_create_client", return_value=mock_client):
            resources = collector._collect_db_instances("123456789012")

        assert len(resources) == 1
        resource = resources[0]
        assert resource.name == "my-database"
        assert resource.resource_type == "AWS::RDS::DBInstance"
        assert resource.region == "us-east-1"
        assert resource.tags == {"Environment": "production", "Team": "backend"}
        assert resource.created_at == datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        assert "my-database" in resource.arn

    def test_collect_db_instances_tag_error(self, collector):
        """Test collecting DB instances when tag retrieval fails."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [
            {
                "DBInstances": [
                    {
                        "DBInstanceIdentifier": "no-tags-db",
                        "DBInstanceArn": "arn:aws:rds:us-east-1:123456789012:db:no-tags-db",
                        "InstanceCreateTime": datetime.now(timezone.utc),
                    }
                ]
            }
        ]
        mock_client.list_tags_for_resource.side_effect = Exception("Access Denied")

        with patch.object(collector, "_create_client", return_value=mock_client):
            resources = collector._collect_db_instances("123456789012")

        assert len(resources) == 1
        assert resources[0].tags == {}

    def test_collect_db_clusters(self, collector):
        """Test collecting RDS DB clusters (Aurora)."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [
            {
                "DBClusters": [
                    {
                        "DBClusterIdentifier": "aurora-cluster",
                        "DBClusterArn": "arn:aws:rds:us-east-1:123456789012:cluster:aurora-cluster",
                        "Engine": "aurora-mysql",
                        "ClusterCreateTime": datetime(2024, 2, 1, 8, 0, 0, tzinfo=timezone.utc),
                    }
                ]
            }
        ]
        mock_client.list_tags_for_resource.return_value = {
            "TagList": [{"Key": "Application", "Value": "web-app"}]
        }

        with patch.object(collector, "_create_client", return_value=mock_client):
            resources = collector._collect_db_clusters("123456789012")

        assert len(resources) == 1
        resource = resources[0]
        assert resource.name == "aurora-cluster"
        assert resource.resource_type == "AWS::RDS::DBCluster"
        assert resource.region == "us-east-1"
        assert resource.tags == {"Application": "web-app"}
        assert resource.created_at == datetime(2024, 2, 1, 8, 0, 0, tzinfo=timezone.utc)

    def test_collect_db_clusters_tag_error(self, collector):
        """Test collecting DB clusters when tag retrieval fails."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [
            {
                "DBClusters": [
                    {
                        "DBClusterIdentifier": "no-tags-cluster",
                        "DBClusterArn": "arn:aws:rds:us-east-1:123456789012:cluster:no-tags-cluster",
                        "ClusterCreateTime": datetime.now(timezone.utc),
                    }
                ]
            }
        ]
        mock_client.list_tags_for_resource.side_effect = Exception("Access Denied")

        with patch.object(collector, "_create_client", return_value=mock_client):
            resources = collector._collect_db_clusters("123456789012")

        assert len(resources) == 1
        assert resources[0].tags == {}

    def test_collect_all_resources(self, collector):
        """Test the main collect() method calls all sub-collectors."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [{"DBInstances": []}, {"DBClusters": []}]

        with patch.object(collector, "_create_client", return_value=mock_client):
            with patch.object(collector, "_get_account_id", return_value="123456789012"):
                resources = collector.collect()

        # Should call get_paginator for db_instances and db_clusters
        assert mock_client.get_paginator.call_count == 2

    def test_collect_db_instances_error_handling(self, collector):
        """Test that DB instance collection handles errors gracefully."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.side_effect = Exception("API Error")

        with patch.object(collector, "_create_client", return_value=mock_client):
            resources = collector._collect_db_instances("123456789012")

        assert resources == []

    def test_collect_db_clusters_error_handling(self, collector):
        """Test that DB cluster collection handles errors gracefully."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.side_effect = Exception("API Error")

        with patch.object(collector, "_create_client", return_value=mock_client):
            resources = collector._collect_db_clusters("123456789012")

        assert resources == []

    def test_collect_multiple_db_instances(self, collector):
        """Test collecting multiple RDS DB instances."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [
            {
                "DBInstances": [
                    {
                        "DBInstanceIdentifier": "db-1",
                        "DBInstanceArn": "arn:aws:rds:us-east-1:123456789012:db:db-1",
                        "InstanceCreateTime": datetime.now(timezone.utc),
                    },
                    {
                        "DBInstanceIdentifier": "db-2",
                        "DBInstanceArn": "arn:aws:rds:us-east-1:123456789012:db:db-2",
                        "InstanceCreateTime": datetime.now(timezone.utc),
                    },
                ]
            }
        ]
        mock_client.list_tags_for_resource.return_value = {"TagList": []}

        with patch.object(collector, "_create_client", return_value=mock_client):
            resources = collector._collect_db_instances("123456789012")

        assert len(resources) == 2
        assert {r.name for r in resources} == {"db-1", "db-2"}

    def test_collect_empty_results(self, collector):
        """Test collecting when no RDS resources exist."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [{"DBInstances": []}]

        with patch.object(collector, "_create_client", return_value=mock_client):
            resources = collector._collect_db_instances("123456789012")

        assert len(resources) == 0
