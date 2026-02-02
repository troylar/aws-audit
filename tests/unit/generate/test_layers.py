"""Unit tests for layer ordering and resource type mappings."""

from __future__ import annotations

import pytest

from src.generate.layers import RESOURCE_TYPE_TO_LAYER, LayerOrder, LayerStatus


class TestLayerStatus:
    """Tests for LayerStatus enum."""

    def test_status_values_exist(self) -> None:
        """Test that all expected status values exist."""
        assert LayerStatus.PENDING.value == "pending"
        assert LayerStatus.IN_PROGRESS.value == "in_progress"
        assert LayerStatus.GENERATING.value == "generating"
        assert LayerStatus.VALIDATING.value == "validating"
        assert LayerStatus.COMPLETED.value == "completed"
        assert LayerStatus.FAILED.value == "failed"

    def test_status_count(self) -> None:
        """Test that there are exactly 6 status values."""
        assert len(LayerStatus) == 6


class TestLayerOrder:
    """Tests for LayerOrder enum ordering."""

    def test_network_is_first(self) -> None:
        """Test that NETWORK layer has lowest order value."""
        assert LayerOrder.NETWORK == 1
        for layer in LayerOrder:
            assert layer >= LayerOrder.NETWORK

    def test_dns_is_last(self) -> None:
        """Test that DNS layer has highest order value."""
        assert LayerOrder.DNS == 11
        for layer in LayerOrder:
            assert layer <= LayerOrder.DNS

    def test_layer_order_values(self) -> None:
        """Test all layer order values are assigned correctly."""
        assert LayerOrder.NETWORK == 1
        assert LayerOrder.SECURITY == 2
        assert LayerOrder.IAM == 3
        assert LayerOrder.DATA == 4
        assert LayerOrder.STORAGE == 5
        assert LayerOrder.COMPUTE == 6
        assert LayerOrder.LOADBALANCING == 7
        assert LayerOrder.APPLICATION == 8
        assert LayerOrder.MESSAGING == 9
        assert LayerOrder.MONITORING == 10
        assert LayerOrder.DNS == 11

    def test_layer_ordering_comparison(self) -> None:
        """Test that layers can be compared for ordering."""
        assert LayerOrder.NETWORK < LayerOrder.SECURITY
        assert LayerOrder.SECURITY < LayerOrder.IAM
        assert LayerOrder.IAM < LayerOrder.DATA
        assert LayerOrder.DATA < LayerOrder.STORAGE
        assert LayerOrder.STORAGE < LayerOrder.COMPUTE
        assert LayerOrder.COMPUTE < LayerOrder.LOADBALANCING
        assert LayerOrder.LOADBALANCING < LayerOrder.APPLICATION
        assert LayerOrder.APPLICATION < LayerOrder.MESSAGING
        assert LayerOrder.MESSAGING < LayerOrder.MONITORING
        assert LayerOrder.MONITORING < LayerOrder.DNS

    def test_layer_ordering_full_chain(self) -> None:
        """Test complete ordering chain from NETWORK to DNS."""
        expected_order = [
            LayerOrder.NETWORK,
            LayerOrder.SECURITY,
            LayerOrder.IAM,
            LayerOrder.DATA,
            LayerOrder.STORAGE,
            LayerOrder.COMPUTE,
            LayerOrder.LOADBALANCING,
            LayerOrder.APPLICATION,
            LayerOrder.MESSAGING,
            LayerOrder.MONITORING,
            LayerOrder.DNS,
        ]
        sorted_layers = sorted(LayerOrder)
        assert sorted_layers == expected_order

    def test_layer_count(self) -> None:
        """Test that there are exactly 11 layers."""
        assert len(LayerOrder) == 11

    def test_layer_is_int_enum(self) -> None:
        """Test that layers can be used as integers."""
        assert int(LayerOrder.NETWORK) == 1
        assert int(LayerOrder.DNS) == 11
        assert LayerOrder.COMPUTE + 1 == 7


class TestResourceTypeToLayer:
    """Tests for RESOURCE_TYPE_TO_LAYER mapping."""

    def test_vpc_maps_to_network(self) -> None:
        """Test that VPC resources map to NETWORK layer."""
        assert RESOURCE_TYPE_TO_LAYER["ec2:vpc"] == LayerOrder.NETWORK
        assert RESOURCE_TYPE_TO_LAYER["ec2:subnet"] == LayerOrder.NETWORK
        assert RESOURCE_TYPE_TO_LAYER["ec2:internet-gateway"] == LayerOrder.NETWORK
        assert RESOURCE_TYPE_TO_LAYER["ec2:nat-gateway"] == LayerOrder.NETWORK
        assert RESOURCE_TYPE_TO_LAYER["ec2:route-table"] == LayerOrder.NETWORK

    def test_security_resources_map_to_security(self) -> None:
        """Test that security resources map to SECURITY layer."""
        assert RESOURCE_TYPE_TO_LAYER["ec2:security-group"] == LayerOrder.SECURITY
        assert RESOURCE_TYPE_TO_LAYER["ec2:network-acl"] == LayerOrder.SECURITY
        assert RESOURCE_TYPE_TO_LAYER["wafv2:web-acl"] == LayerOrder.SECURITY
        assert RESOURCE_TYPE_TO_LAYER["acm:certificate"] == LayerOrder.SECURITY
        assert RESOURCE_TYPE_TO_LAYER["secretsmanager:secret"] == LayerOrder.SECURITY
        assert RESOURCE_TYPE_TO_LAYER["kms:key"] == LayerOrder.SECURITY

    def test_iam_resources_map_to_iam(self) -> None:
        """Test that IAM resources map to IAM layer."""
        assert RESOURCE_TYPE_TO_LAYER["iam:role"] == LayerOrder.IAM
        assert RESOURCE_TYPE_TO_LAYER["iam:policy"] == LayerOrder.IAM
        assert RESOURCE_TYPE_TO_LAYER["iam:instance-profile"] == LayerOrder.IAM
        assert RESOURCE_TYPE_TO_LAYER["iam:user"] == LayerOrder.IAM
        assert RESOURCE_TYPE_TO_LAYER["iam:group"] == LayerOrder.IAM

    def test_data_resources_map_to_data(self) -> None:
        """Test that data resources map to DATA layer."""
        assert RESOURCE_TYPE_TO_LAYER["rds:db-instance"] == LayerOrder.DATA
        assert RESOURCE_TYPE_TO_LAYER["rds:db-cluster"] == LayerOrder.DATA
        assert RESOURCE_TYPE_TO_LAYER["dynamodb:table"] == LayerOrder.DATA
        assert RESOURCE_TYPE_TO_LAYER["elasticache:cluster"] == LayerOrder.DATA
        assert RESOURCE_TYPE_TO_LAYER["redshift:cluster"] == LayerOrder.DATA

    def test_storage_resources_map_to_storage(self) -> None:
        """Test that storage resources map to STORAGE layer."""
        assert RESOURCE_TYPE_TO_LAYER["s3:bucket"] == LayerOrder.STORAGE
        assert RESOURCE_TYPE_TO_LAYER["efs:file-system"] == LayerOrder.STORAGE
        assert RESOURCE_TYPE_TO_LAYER["efs:mount-target"] == LayerOrder.STORAGE
        assert RESOURCE_TYPE_TO_LAYER["backup:backup-vault"] == LayerOrder.STORAGE

    def test_compute_resources_map_to_compute(self) -> None:
        """Test that compute resources map to COMPUTE layer."""
        assert RESOURCE_TYPE_TO_LAYER["ec2:instance"] == LayerOrder.COMPUTE
        assert RESOURCE_TYPE_TO_LAYER["lambda:function"] == LayerOrder.COMPUTE
        assert RESOURCE_TYPE_TO_LAYER["ecs:cluster"] == LayerOrder.COMPUTE
        assert RESOURCE_TYPE_TO_LAYER["eks:cluster"] == LayerOrder.COMPUTE
        assert RESOURCE_TYPE_TO_LAYER["batch:compute-environment"] == LayerOrder.COMPUTE

    def test_loadbalancing_resources_map_to_loadbalancing(self) -> None:
        """Test that load balancing resources map to LOADBALANCING layer."""
        assert RESOURCE_TYPE_TO_LAYER["elbv2:loadbalancer"] == LayerOrder.LOADBALANCING
        assert RESOURCE_TYPE_TO_LAYER["elbv2:target-group"] == LayerOrder.LOADBALANCING
        assert RESOURCE_TYPE_TO_LAYER["elbv2:listener"] == LayerOrder.LOADBALANCING
        assert RESOURCE_TYPE_TO_LAYER["elb:loadbalancer"] == LayerOrder.LOADBALANCING

    def test_application_resources_map_to_application(self) -> None:
        """Test that application resources map to APPLICATION layer."""
        assert RESOURCE_TYPE_TO_LAYER["apigateway:rest-api"] == LayerOrder.APPLICATION
        assert RESOURCE_TYPE_TO_LAYER["apigatewayv2:api"] == LayerOrder.APPLICATION
        assert RESOURCE_TYPE_TO_LAYER["apprunner:service"] == LayerOrder.APPLICATION
        assert RESOURCE_TYPE_TO_LAYER["cognito:user-pool"] == LayerOrder.APPLICATION

    def test_messaging_resources_map_to_messaging(self) -> None:
        """Test that messaging resources map to MESSAGING layer."""
        assert RESOURCE_TYPE_TO_LAYER["sqs:queue"] == LayerOrder.MESSAGING
        assert RESOURCE_TYPE_TO_LAYER["sns:topic"] == LayerOrder.MESSAGING
        assert RESOURCE_TYPE_TO_LAYER["events:rule"] == LayerOrder.MESSAGING
        assert RESOURCE_TYPE_TO_LAYER["kinesis:stream"] == LayerOrder.MESSAGING
        assert RESOURCE_TYPE_TO_LAYER["stepfunctions:state-machine"] == LayerOrder.MESSAGING

    def test_monitoring_resources_map_to_monitoring(self) -> None:
        """Test that monitoring resources map to MONITORING layer."""
        assert RESOURCE_TYPE_TO_LAYER["cloudwatch:alarm"] == LayerOrder.MONITORING
        assert RESOURCE_TYPE_TO_LAYER["cloudwatch:dashboard"] == LayerOrder.MONITORING
        assert RESOURCE_TYPE_TO_LAYER["logs:log-group"] == LayerOrder.MONITORING
        assert RESOURCE_TYPE_TO_LAYER["cloudtrail:trail"] == LayerOrder.MONITORING

    def test_dns_resources_map_to_dns(self) -> None:
        """Test that DNS resources map to DNS layer."""
        assert RESOURCE_TYPE_TO_LAYER["route53:hosted-zone"] == LayerOrder.DNS
        assert RESOURCE_TYPE_TO_LAYER["route53:record-set"] == LayerOrder.DNS
        assert RESOURCE_TYPE_TO_LAYER["route53:health-check"] == LayerOrder.DNS
        assert RESOURCE_TYPE_TO_LAYER["cloudfront:distribution"] == LayerOrder.DNS

    def test_unknown_resource_type_returns_none(self) -> None:
        """Test that unknown resource types return None via dict.get()."""
        unknown_types = [
            "nonexistent:resource",
            "fake:type",
            "random:service",
            "",
        ]
        for resource_type in unknown_types:
            assert RESOURCE_TYPE_TO_LAYER.get(resource_type) is None

    def test_unknown_resource_type_raises_key_error(self) -> None:
        """Test that unknown resource types raise KeyError via direct access."""
        with pytest.raises(KeyError):
            _ = RESOURCE_TYPE_TO_LAYER["nonexistent:resource"]

    def test_mapping_has_expected_resource_count(self) -> None:
        """Test that the mapping contains a reasonable number of resource types."""
        # Should have mappings for multiple services
        assert len(RESOURCE_TYPE_TO_LAYER) >= 50

    def test_all_mappings_are_valid_layer_orders(self) -> None:
        """Test that all mapped values are valid LayerOrder enum members."""
        for resource_type, layer in RESOURCE_TYPE_TO_LAYER.items():
            assert isinstance(layer, LayerOrder), f"{resource_type} maps to invalid layer: {layer}"

    def test_resource_types_follow_naming_convention(self) -> None:
        """Test that all resource type keys follow valid conventions.

        Supports two formats:
        - service:type (e.g., ec2:vpc)
        - AWS::Service::Type (e.g., AWS::EC2::VPC)
        """
        for resource_type in RESOURCE_TYPE_TO_LAYER.keys():
            assert ":" in resource_type, f"Resource type missing colon: {resource_type}"

            if resource_type.startswith("AWS::"):
                # CloudFormation format: AWS::Service::Type
                parts = resource_type.split("::")
                assert len(parts) >= 3, f"AWS format should have at least 3 parts: {resource_type}"
            else:
                # Internal format: service:type
                parts = resource_type.split(":")
                assert len(parts) == 2, f"Resource type has wrong format: {resource_type}"
                service, rtype = parts
                assert len(service) > 0, f"Empty service in: {resource_type}"
                assert len(rtype) > 0, f"Empty type in: {resource_type}"
