"""Unit tests for EKS resource collector."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.snapshot.resource_collectors.eks import EKSCollector


class TestEKSCollector:
    """Tests for EKSCollector."""

    @pytest.fixture
    def collector(self):
        """Create an EKSCollector instance for testing."""
        mock_session = MagicMock()
        mock_session.profile_name = "default"
        return EKSCollector(session=mock_session, region="us-east-1")

    def test_service_name(self, collector):
        """Test service name property."""
        assert collector.service_name == "eks"

    def test_is_global_service(self, collector):
        """Test that EKS is not a global service."""
        assert collector.is_global_service is False

    def test_collect_clusters(self, collector):
        """Test collecting EKS clusters."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [{"clusters": ["my-cluster"]}]
        mock_client.describe_cluster.return_value = {
            "cluster": {
                "name": "my-cluster",
                "arn": "arn:aws:eks:us-east-1:123456789012:cluster/my-cluster",
                "status": "ACTIVE",
                "createdAt": datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
                "tags": {"Environment": "production", "Team": "platform"},
            }
        }

        with patch.object(collector, "_create_client", return_value=mock_client):
            resources, cluster_names = collector._collect_clusters()

        assert len(resources) == 1
        assert cluster_names == ["my-cluster"]
        resource = resources[0]
        assert resource.name == "my-cluster"
        assert resource.resource_type == "AWS::EKS::Cluster"
        assert resource.region == "us-east-1"
        assert resource.tags == {"Environment": "production", "Team": "platform"}
        assert resource.created_at == datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)

    def test_collect_clusters_empty(self, collector):
        """Test collecting when no clusters exist."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [{"clusters": []}]

        with patch.object(collector, "_create_client", return_value=mock_client):
            resources, cluster_names = collector._collect_clusters()

        assert len(resources) == 0
        assert cluster_names == []

    def test_collect_clusters_error_handling(self, collector):
        """Test that cluster collection handles errors gracefully."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.side_effect = Exception("API Error")

        with patch.object(collector, "_create_client", return_value=mock_client):
            resources, cluster_names = collector._collect_clusters()

        assert resources == []
        assert cluster_names == []

    def test_collect_node_groups(self, collector):
        """Test collecting EKS node groups."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [{"nodegroups": ["my-nodegroup"]}]
        mock_client.describe_nodegroup.return_value = {
            "nodegroup": {
                "nodegroupName": "my-nodegroup",
                "nodegroupArn": "arn:aws:eks:us-east-1:123456789012:nodegroup/my-cluster/my-nodegroup/abc123",
                "clusterName": "my-cluster",
                "status": "ACTIVE",
                "createdAt": datetime(2024, 2, 1, 8, 0, 0, tzinfo=timezone.utc),
                "tags": {"NodeType": "general"},
            }
        }

        with patch.object(collector, "_create_client", return_value=mock_client):
            resources = collector._collect_node_groups(["my-cluster"])

        assert len(resources) == 1
        resource = resources[0]
        assert resource.name == "my-cluster/my-nodegroup"
        assert resource.resource_type == "AWS::EKS::Nodegroup"
        assert resource.tags == {"NodeType": "general"}
        assert resource.created_at == datetime(2024, 2, 1, 8, 0, 0, tzinfo=timezone.utc)

    def test_collect_node_groups_empty(self, collector):
        """Test collecting when no node groups exist."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [{"nodegroups": []}]

        with patch.object(collector, "_create_client", return_value=mock_client):
            resources = collector._collect_node_groups(["my-cluster"])

        assert len(resources) == 0

    def test_collect_node_groups_no_clusters(self, collector):
        """Test collecting node groups when no clusters provided."""
        mock_client = MagicMock()

        with patch.object(collector, "_create_client", return_value=mock_client):
            resources = collector._collect_node_groups([])

        assert len(resources) == 0
        # Should not call paginator if no clusters
        mock_client.get_paginator.assert_not_called()

    def test_collect_node_groups_error_handling(self, collector):
        """Test that node group collection handles errors gracefully."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.side_effect = Exception("API Error")

        with patch.object(collector, "_create_client", return_value=mock_client):
            resources = collector._collect_node_groups(["my-cluster"])

        assert resources == []

    def test_collect_fargate_profiles(self, collector):
        """Test collecting EKS Fargate profiles."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [{"fargateProfileNames": ["my-fargate-profile"]}]
        mock_client.describe_fargate_profile.return_value = {
            "fargateProfile": {
                "fargateProfileName": "my-fargate-profile",
                "fargateProfileArn": (
                    "arn:aws:eks:us-east-1:123456789012:fargateprofile/my-cluster/my-fargate-profile/abc123"
                ),
                "clusterName": "my-cluster",
                "status": "ACTIVE",
                "createdAt": datetime(2024, 3, 1, 12, 0, 0, tzinfo=timezone.utc),
                "tags": {"WorkloadType": "serverless"},
            }
        }

        with patch.object(collector, "_create_client", return_value=mock_client):
            resources = collector._collect_fargate_profiles(["my-cluster"])

        assert len(resources) == 1
        resource = resources[0]
        assert resource.name == "my-cluster/my-fargate-profile"
        assert resource.resource_type == "AWS::EKS::FargateProfile"
        assert resource.tags == {"WorkloadType": "serverless"}
        assert resource.created_at == datetime(2024, 3, 1, 12, 0, 0, tzinfo=timezone.utc)

    def test_collect_fargate_profiles_empty(self, collector):
        """Test collecting when no Fargate profiles exist."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [{"fargateProfileNames": []}]

        with patch.object(collector, "_create_client", return_value=mock_client):
            resources = collector._collect_fargate_profiles(["my-cluster"])

        assert len(resources) == 0

    def test_collect_fargate_profiles_error_handling(self, collector):
        """Test that Fargate profile collection handles errors gracefully."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.side_effect = Exception("API Error")

        with patch.object(collector, "_create_client", return_value=mock_client):
            resources = collector._collect_fargate_profiles(["my-cluster"])

        assert resources == []

    def test_collect_all_resources(self, collector):
        """Test the main collect() method calls all sub-collectors."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [{"clusters": [], "nodegroups": [], "fargateProfileNames": []}]

        with patch.object(collector, "_create_client", return_value=mock_client):
            collector.collect()

        # Should have called get_paginator at least once for clusters
        assert mock_client.get_paginator.call_count >= 1

    def test_collect_multiple_clusters(self, collector):
        """Test collecting multiple EKS clusters."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [{"clusters": ["cluster-1", "cluster-2"]}]

        def describe_cluster_side_effect(name):
            return {
                "cluster": {
                    "name": name,
                    "arn": f"arn:aws:eks:us-east-1:123456789012:cluster/{name}",
                    "createdAt": datetime.now(timezone.utc),
                    "tags": {},
                }
            }

        mock_client.describe_cluster.side_effect = describe_cluster_side_effect

        with patch.object(collector, "_create_client", return_value=mock_client):
            resources, cluster_names = collector._collect_clusters()

        assert len(resources) == 2
        assert set(cluster_names) == {"cluster-1", "cluster-2"}
        assert {r.name for r in resources} == {"cluster-1", "cluster-2"}

    def test_collect_multiple_node_groups(self, collector):
        """Test collecting multiple node groups across clusters."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [{"nodegroups": ["ng-1", "ng-2"]}]

        call_count = [0]

        def describe_nodegroup_side_effect(clusterName, nodegroupName):
            call_count[0] += 1
            return {
                "nodegroup": {
                    "nodegroupName": nodegroupName,
                    "nodegroupArn": f"arn:aws:eks:us-east-1:123456789012:nodegroup/{clusterName}/{nodegroupName}/abc",
                    "createdAt": datetime.now(timezone.utc),
                    "tags": {},
                }
            }

        mock_client.describe_nodegroup.side_effect = describe_nodegroup_side_effect

        with patch.object(collector, "_create_client", return_value=mock_client):
            resources = collector._collect_node_groups(["my-cluster"])

        assert len(resources) == 2
        assert {r.name for r in resources} == {"my-cluster/ng-1", "my-cluster/ng-2"}

    def test_collect_clusters_describe_error(self, collector):
        """Test that cluster collection continues when describe_cluster fails for one cluster."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [{"clusters": ["good-cluster", "bad-cluster"]}]

        def describe_cluster_side_effect(name):
            if name == "bad-cluster":
                raise Exception("Describe failed")
            return {
                "cluster": {
                    "name": name,
                    "arn": f"arn:aws:eks:us-east-1:123456789012:cluster/{name}",
                    "createdAt": datetime.now(timezone.utc),
                    "tags": {},
                }
            }

        mock_client.describe_cluster.side_effect = describe_cluster_side_effect

        with patch.object(collector, "_create_client", return_value=mock_client):
            resources, cluster_names = collector._collect_clusters()

        # Should get both cluster names but only one resource
        assert len(cluster_names) == 2
        assert len(resources) == 1
        assert resources[0].name == "good-cluster"

    def test_collect_node_groups_describe_error(self, collector):
        """Test that node group collection continues when describe_nodegroup fails."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [{"nodegroups": ["good-ng", "bad-ng"]}]

        def describe_nodegroup_side_effect(clusterName, nodegroupName):
            if nodegroupName == "bad-ng":
                raise Exception("Describe failed")
            return {
                "nodegroup": {
                    "nodegroupName": nodegroupName,
                    "nodegroupArn": f"arn:aws:eks:us-east-1:123456789012:nodegroup/{clusterName}/{nodegroupName}/abc",
                    "createdAt": datetime.now(timezone.utc),
                    "tags": {},
                }
            }

        mock_client.describe_nodegroup.side_effect = describe_nodegroup_side_effect

        with patch.object(collector, "_create_client", return_value=mock_client):
            resources = collector._collect_node_groups(["my-cluster"])

        # Should only get the good node group
        assert len(resources) == 1
        assert resources[0].name == "my-cluster/good-ng"

    def test_collect_fargate_profiles_describe_error(self, collector):
        """Test that Fargate profile collection continues when describe fails."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [{"fargateProfileNames": ["good-profile", "bad-profile"]}]

        def describe_fargate_side_effect(clusterName, fargateProfileName):
            if fargateProfileName == "bad-profile":
                raise Exception("Describe failed")
            return {
                "fargateProfile": {
                    "fargateProfileName": fargateProfileName,
                    "fargateProfileArn": (
                        f"arn:aws:eks:us-east-1:123456789012:fargateprofile/{clusterName}/{fargateProfileName}/abc"
                    ),
                    "createdAt": datetime.now(timezone.utc),
                    "tags": {},
                }
            }

        mock_client.describe_fargate_profile.side_effect = describe_fargate_side_effect

        with patch.object(collector, "_create_client", return_value=mock_client):
            resources = collector._collect_fargate_profiles(["my-cluster"])

        # Should only get the good profile
        assert len(resources) == 1
        assert resources[0].name == "my-cluster/good-profile"

    def test_collect_fargate_profiles_no_clusters(self, collector):
        """Test collecting Fargate profiles when no clusters provided."""
        mock_client = MagicMock()

        with patch.object(collector, "_create_client", return_value=mock_client):
            resources = collector._collect_fargate_profiles([])

        assert len(resources) == 0
        # Should not call paginator if no clusters
        mock_client.get_paginator.assert_not_called()
