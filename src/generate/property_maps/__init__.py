"""AWS to Terraform property mapping utilities."""

from typing import Any, Dict, Optional

# Registry of property maps by resource type prefix
_PROPERTY_MAPS: Dict[str, Any] = {}


def register_property_map(resource_prefix: str, property_map: Any) -> None:
    """Register a property map for a resource type prefix."""
    _PROPERTY_MAPS[resource_prefix] = property_map


def get_property_map(resource_type: str) -> Optional[Any]:
    """Get property map for a resource type.

    Args:
        resource_type: AWS resource type (e.g., "ec2:instance", "lambda:function")

    Returns:
        Property map module or None if not found
    """
    # Try exact match first
    if resource_type in _PROPERTY_MAPS:
        return _PROPERTY_MAPS[resource_type]

    # Try prefix match (e.g., "ec2" for "ec2:instance")
    prefix = resource_type.split(":")[0] if ":" in resource_type else resource_type
    return _PROPERTY_MAPS.get(prefix)


# Register property maps
from . import (
    apigateway,
    backup,
    cloudformation,
    cloudwatch,
    codebuild,
    codepipeline,
    dynamodb,
    ec2,
    ecs,
    efs,
    eks,
    elasticache,
    elb,
    eventbridge,
    glue,
    iam,
    kms,
    lambda_,
    rds,
    route53,
    s3,
    secretsmanager,
    sns,
    sqs,
    ssm,
    stepfunctions,
    vpc,
    vpcendpoints,
    waf,
)

register_property_map("apigateway", apigateway)
register_property_map("backup", backup)
register_property_map("cloudformation", cloudformation)
register_property_map("cloudwatch", cloudwatch)
register_property_map("codebuild", codebuild)
register_property_map("codepipeline", codepipeline)
register_property_map("dynamodb", dynamodb)
register_property_map("ec2", ec2)
register_property_map("ecs", ecs)
register_property_map("efs", efs)
register_property_map("eks", eks)
register_property_map("elasticache", elasticache)
register_property_map("elb", elb)
register_property_map("eventbridge", eventbridge)
register_property_map("glue", glue)
register_property_map("iam", iam)
register_property_map("kms", kms)
register_property_map("lambda", lambda_)
register_property_map("rds", rds)
register_property_map("route53", route53)
register_property_map("s3", s3)
register_property_map("secretsmanager", secretsmanager)
register_property_map("sns", sns)
register_property_map("sqs", sqs)
register_property_map("ssm", ssm)
register_property_map("stepfunctions", stepfunctions)
register_property_map("vpc", vpc)
register_property_map("vpcendpoints", vpcendpoints)
register_property_map("waf", waf)


__all__ = ["register_property_map", "get_property_map"]
