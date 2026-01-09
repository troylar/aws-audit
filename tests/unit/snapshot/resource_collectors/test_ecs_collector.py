"""Unit tests for ECS resource collector."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.snapshot.resource_collectors.ecs import ECSCollector


class TestECSCollector:
    """Tests for ECSCollector."""

    @pytest.fixture
    def collector(self):
        """Create an ECSCollector instance for testing."""
        mock_session = MagicMock()
        mock_session.profile_name = "default"
        return ECSCollector(session=mock_session, region="us-east-1")

    def test_service_name(self, collector):
        """Test service name property."""
        assert collector.service_name == "ecs"

    def test_is_global_service(self, collector):
        """Test that ECS is not a global service."""
        assert collector.is_global_service is False

    def test_collect_clusters(self, collector):
        """Test collecting ECS clusters."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [
            {"clusterArns": ["arn:aws:ecs:us-east-1:123456789012:cluster/my-cluster"]}
        ]
        mock_client.describe_clusters.return_value = {
            "clusters": [
                {
                    "clusterName": "my-cluster",
                    "clusterArn": "arn:aws:ecs:us-east-1:123456789012:cluster/my-cluster",
                    "status": "ACTIVE",
                    "tags": [
                        {"key": "Environment", "value": "production"},
                    ],
                }
            ]
        }

        with patch.object(collector, "_create_client", return_value=mock_client):
            resources = collector._collect_clusters()

        assert len(resources) == 1
        resource = resources[0]
        assert resource.name == "my-cluster"
        assert resource.resource_type == "AWS::ECS::Cluster"
        assert resource.region == "us-east-1"
        assert resource.tags == {"Environment": "production"}

    def test_collect_clusters_empty(self, collector):
        """Test collecting when no clusters exist."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [{"clusterArns": []}]

        with patch.object(collector, "_create_client", return_value=mock_client):
            resources = collector._collect_clusters()

        assert len(resources) == 0

    def test_collect_clusters_error_handling(self, collector):
        """Test that cluster collection handles errors gracefully."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.side_effect = Exception("API Error")

        with patch.object(collector, "_create_client", return_value=mock_client):
            resources = collector._collect_clusters()

        assert resources == []

    def test_collect_services(self, collector):
        """Test collecting ECS services."""
        mock_client = MagicMock()

        # Setup paginator for list_clusters
        cluster_paginator = MagicMock()
        cluster_paginator.paginate.return_value = [
            {"clusterArns": ["arn:aws:ecs:us-east-1:123456789012:cluster/my-cluster"]}
        ]

        # Setup paginator for list_services
        service_paginator = MagicMock()
        service_paginator.paginate.return_value = [
            {"serviceArns": ["arn:aws:ecs:us-east-1:123456789012:service/my-cluster/web-service"]}
        ]

        def get_paginator(operation):
            if operation == "list_clusters":
                return cluster_paginator
            elif operation == "list_services":
                return service_paginator
            return MagicMock()

        mock_client.get_paginator.side_effect = get_paginator
        mock_client.describe_services.return_value = {
            "services": [
                {
                    "serviceName": "web-service",
                    "serviceArn": "arn:aws:ecs:us-east-1:123456789012:service/my-cluster/web-service",
                    "status": "ACTIVE",
                    "createdAt": datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
                    "tags": [{"key": "Team", "value": "backend"}],
                }
            ]
        }

        with patch.object(collector, "_create_client", return_value=mock_client):
            resources = collector._collect_services()

        assert len(resources) == 1
        resource = resources[0]
        assert resource.name == "web-service"
        assert resource.resource_type == "AWS::ECS::Service"
        assert resource.tags == {"Team": "backend"}
        assert resource.created_at == datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)

    def test_collect_services_no_clusters(self, collector):
        """Test collecting services when no clusters exist."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [{"clusterArns": []}]

        with patch.object(collector, "_create_client", return_value=mock_client):
            resources = collector._collect_services()

        assert len(resources) == 0

    def test_collect_services_error_handling(self, collector):
        """Test that service collection handles errors gracefully."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.side_effect = Exception("API Error")

        with patch.object(collector, "_create_client", return_value=mock_client):
            resources = collector._collect_services()

        assert resources == []

    def test_collect_task_definitions(self, collector):
        """Test collecting ECS task definitions."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [
            {"taskDefinitionArns": ["arn:aws:ecs:us-east-1:123456789012:task-definition/web-task:1"]}
        ]
        mock_client.describe_task_definition.return_value = {
            "taskDefinition": {
                "family": "web-task",
                "revision": 1,
                "taskDefinitionArn": "arn:aws:ecs:us-east-1:123456789012:task-definition/web-task:1",
            },
            "tags": [{"key": "Application", "value": "web"}],
        }

        with patch.object(collector, "_create_client", return_value=mock_client):
            resources = collector._collect_task_definitions()

        assert len(resources) == 1
        resource = resources[0]
        assert resource.name == "web-task:1"
        assert resource.resource_type == "AWS::ECS::TaskDefinition"
        assert resource.tags == {"Application": "web"}
        assert resource.created_at is None  # Task definitions don't have creation timestamp

    def test_collect_task_definitions_empty(self, collector):
        """Test collecting when no task definitions exist."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [{"taskDefinitionArns": []}]

        with patch.object(collector, "_create_client", return_value=mock_client):
            resources = collector._collect_task_definitions()

        assert len(resources) == 0

    def test_collect_task_definitions_error_handling(self, collector):
        """Test that task definition collection handles errors gracefully."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.side_effect = Exception("API Error")

        with patch.object(collector, "_create_client", return_value=mock_client):
            resources = collector._collect_task_definitions()

        assert resources == []

    def test_collect_all_resources(self, collector):
        """Test the main collect() method calls all sub-collectors."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [{"clusterArns": [], "taskDefinitionArns": []}]

        with patch.object(collector, "_create_client", return_value=mock_client):
            resources = collector.collect()

        # Should have called get_paginator multiple times
        assert mock_client.get_paginator.call_count >= 2

    def test_collect_multiple_clusters(self, collector):
        """Test collecting multiple ECS clusters."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [
            {
                "clusterArns": [
                    "arn:aws:ecs:us-east-1:123456789012:cluster/cluster-1",
                    "arn:aws:ecs:us-east-1:123456789012:cluster/cluster-2",
                ]
            }
        ]
        mock_client.describe_clusters.return_value = {
            "clusters": [
                {
                    "clusterName": "cluster-1",
                    "clusterArn": "arn:aws:ecs:us-east-1:123456789012:cluster/cluster-1",
                    "tags": [],
                },
                {
                    "clusterName": "cluster-2",
                    "clusterArn": "arn:aws:ecs:us-east-1:123456789012:cluster/cluster-2",
                    "tags": [],
                },
            ]
        }

        with patch.object(collector, "_create_client", return_value=mock_client):
            resources = collector._collect_clusters()

        assert len(resources) == 2
        assert {r.name for r in resources} == {"cluster-1", "cluster-2"}
