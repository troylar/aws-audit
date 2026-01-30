"""Build resource map node for LangGraph workflow."""

from typing import Any, Dict

from ...models.generation import ResourceMap, TrackedResource
from ..state import GenerationState


def build_resource_map(state: GenerationState) -> Dict[str, Any]:
    """Build AWS ID to Terraform reference mapping.

    For each resource, creates mappings like:
    - vpc-abc123 → aws_vpc.my_vpc.id
    - subnet-def456 → aws_subnet.public_1.id
    - i-789xyz → aws_instance.web_server.id

    Args:
        state: Current state with inventory list

    Returns:
        Dict with resource_map: ResourceMap
    """
    inventory = state.get("inventory", [])
    resource_map = ResourceMap()

    for resource_dict in inventory:
        resource = TrackedResource.from_inventory(resource_dict)

        tf_type = _get_terraform_type(resource.resource_type)
        if not tf_type:
            continue

        tf_name = resource.get_terraform_name()
        tf_ref = f"{tf_type}.{tf_name}"

        aws_id = _extract_aws_id(resource)
        if aws_id:
            resource_map.add(aws_id, tf_ref, resource.resource_type)

        if resource.arn:
            resource_map.add(resource.arn, tf_ref, resource.resource_type)

    return {"resource_map": resource_map}


def _get_terraform_type(resource_type: str) -> str:
    """Map AWS resource type to Terraform resource type."""
    type_map = {
        "ec2:instance": "aws_instance",
        "ec2:security-group": "aws_security_group",
        "ec2:volume": "aws_ebs_volume",
        "ec2:snapshot": "aws_ebs_snapshot",
        "ec2:ami": "aws_ami",
        "ec2:key-pair": "aws_key_pair",
        "vpc:vpc": "aws_vpc",
        "vpc:subnet": "aws_subnet",
        "vpc:route-table": "aws_route_table",
        "vpc:internet-gateway": "aws_internet_gateway",
        "vpc:nat-gateway": "aws_nat_gateway",
        "vpc:network-acl": "aws_network_acl",
        "lambda:function": "aws_lambda_function",
        "lambda:layer": "aws_lambda_layer_version",
        "rds:instance": "aws_db_instance",
        "rds:cluster": "aws_rds_cluster",
        "rds:subnet-group": "aws_db_subnet_group",
        "s3:bucket": "aws_s3_bucket",
        "iam:role": "aws_iam_role",
        "iam:policy": "aws_iam_policy",
        "iam:user": "aws_iam_user",
        "iam:group": "aws_iam_group",
        "ecs:cluster": "aws_ecs_cluster",
        "ecs:service": "aws_ecs_service",
        "ecs:task-definition": "aws_ecs_task_definition",
        "eks:cluster": "aws_eks_cluster",
        "eks:node-group": "aws_eks_node_group",
        "sqs:queue": "aws_sqs_queue",
        "sns:topic": "aws_sns_topic",
        "dynamodb:table": "aws_dynamodb_table",
        "elb:load-balancer": "aws_lb",
        "elb:target-group": "aws_lb_target_group",
        "route53:hosted-zone": "aws_route53_zone",
        "route53:record": "aws_route53_record",
        "cloudwatch:alarm": "aws_cloudwatch_metric_alarm",
        "cloudwatch:log-group": "aws_cloudwatch_log_group",
        "apigateway:rest-api": "aws_api_gateway_rest_api",
        "kms:key": "aws_kms_key",
        "secretsmanager:secret": "aws_secretsmanager_secret",
    }
    return type_map.get(resource_type, "")


def _extract_aws_id(resource: TrackedResource) -> str:
    """Extract the AWS resource ID from resource data."""
    raw = resource.raw_config
    resource_type = resource.resource_type

    id_field_map = {
        "vpc:vpc": "VpcId",
        "vpc:subnet": "SubnetId",
        "vpc:route-table": "RouteTableId",
        "vpc:internet-gateway": "InternetGatewayId",
        "vpc:nat-gateway": "NatGatewayId",
        "vpc:network-acl": "NetworkAclId",
        "ec2:instance": "InstanceId",
        "ec2:security-group": ["SecurityGroupId", "GroupId"],
        "ec2:volume": "VolumeId",
        "ec2:snapshot": "SnapshotId",
        "ec2:ami": "ImageId",
        "ec2:key-pair": "KeyPairId",
        "lambda:function": "FunctionName",
        "rds:instance": "DBInstanceIdentifier",
        "rds:cluster": "DBClusterIdentifier",
        "rds:subnet-group": "DBSubnetGroupName",
        "s3:bucket": ["BucketName", "Name"],
        "iam:role": "RoleName",
        "iam:policy": "PolicyName",
        "iam:user": "UserName",
        "iam:group": "GroupName",
        "ecs:cluster": "ClusterArn",
        "ecs:service": "ServiceArn",
        "ecs:task-definition": "TaskDefinitionArn",
        "eks:cluster": "ClusterName",
        "eks:node-group": "NodegroupName",
        "sqs:queue": "QueueUrl",
        "sns:topic": "TopicArn",
        "dynamodb:table": "TableName",
        "elb:load-balancer": "LoadBalancerArn",
        "elb:target-group": "TargetGroupArn",
        "route53:hosted-zone": "HostedZoneId",
        "cloudwatch:alarm": ["AlarmArn", "AlarmName"],
        "cloudwatch:log-group": "LogGroupName",
        "apigateway:rest-api": "Id",
        "kms:key": "KeyId",
        "secretsmanager:secret": "ARN",
    }

    if resource_type in id_field_map:
        fields = id_field_map[resource_type]
        if isinstance(fields, str):
            fields = [fields]
        for field in fields:
            if field in raw:
                return raw[field]

    for field in ["id", "Id", "ID"]:
        if field in raw:
            return raw[field]

    if "ARN" in raw:
        return raw["ARN"]

    return resource.name
