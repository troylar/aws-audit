"""Resource type mapping between AWS Config and collectors.

AWS Config supports ~80+ resource types. This module maps which types
can be collected via Config vs which must use direct API calls.
"""

from __future__ import annotations

from typing import Set

# Resource types supported by AWS Config
# Reference: https://docs.aws.amazon.com/config/latest/developerguide/resource-config-reference.html
CONFIG_SUPPORTED_TYPES: Set[str] = {
    # EC2
    "AWS::EC2::CustomerGateway",
    "AWS::EC2::EIP",
    "AWS::EC2::Host",
    "AWS::EC2::Instance",
    "AWS::EC2::InternetGateway",
    "AWS::EC2::NetworkAcl",
    "AWS::EC2::NetworkInterface",
    "AWS::EC2::RouteTable",
    "AWS::EC2::SecurityGroup",
    "AWS::EC2::Subnet",
    "AWS::EC2::Volume",
    "AWS::EC2::VPC",
    "AWS::EC2::VPNConnection",
    "AWS::EC2::VPNGateway",
    "AWS::EC2::NatGateway",
    "AWS::EC2::EgressOnlyInternetGateway",
    "AWS::EC2::FlowLog",
    "AWS::EC2::TransitGateway",
    "AWS::EC2::TransitGatewayAttachment",
    "AWS::EC2::TransitGatewayRouteTable",
    "AWS::EC2::LaunchTemplate",
    # IAM
    "AWS::IAM::User",
    "AWS::IAM::Group",
    "AWS::IAM::Role",
    "AWS::IAM::Policy",
    # S3
    "AWS::S3::Bucket",
    "AWS::S3::AccountPublicAccessBlock",
    # Lambda
    "AWS::Lambda::Function",
    "AWS::Lambda::Alias",
    # RDS
    "AWS::RDS::DBInstance",
    "AWS::RDS::DBCluster",
    "AWS::RDS::DBClusterSnapshot",
    "AWS::RDS::DBSecurityGroup",
    "AWS::RDS::DBSnapshot",
    "AWS::RDS::DBSubnetGroup",
    "AWS::RDS::EventSubscription",
    # DynamoDB
    "AWS::DynamoDB::Table",
    # CloudWatch
    "AWS::Logs::LogGroup",
    "AWS::CloudWatch::Alarm",
    # SNS
    "AWS::SNS::Topic",
    # SQS
    "AWS::SQS::Queue",
    # ELB
    "AWS::ElasticLoadBalancing::LoadBalancer",
    "AWS::ElasticLoadBalancingV2::LoadBalancer",
    "AWS::ElasticLoadBalancingV2::TargetGroup",
    # ECS
    "AWS::ECS::Cluster",
    "AWS::ECS::Service",
    "AWS::ECS::TaskDefinition",
    # EKS
    "AWS::EKS::Cluster",
    "AWS::EKS::FargateProfile",
    "AWS::EKS::Nodegroup",
    # KMS
    "AWS::KMS::Key",
    # Secrets Manager
    "AWS::SecretsManager::Secret",
    # API Gateway
    "AWS::ApiGateway::RestApi",
    "AWS::ApiGateway::Stage",
    "AWS::ApiGatewayV2::Api",
    "AWS::ApiGatewayV2::Stage",
    # CloudFormation
    "AWS::CloudFormation::Stack",
    # Auto Scaling
    "AWS::AutoScaling::AutoScalingGroup",
    "AWS::AutoScaling::LaunchConfiguration",
    "AWS::AutoScaling::ScalingPolicy",
    # CloudTrail
    "AWS::CloudTrail::Trail",
    # CodeBuild
    "AWS::CodeBuild::Project",
    # CodePipeline
    "AWS::CodePipeline::Pipeline",
    # Config
    "AWS::Config::ConfigurationRecorder",
    "AWS::Config::ConformancePackCompliance",
    "AWS::Config::ResourceCompliance",
    # Elasticsearch/OpenSearch
    "AWS::Elasticsearch::Domain",
    "AWS::OpenSearch::Domain",
    # ElastiCache
    "AWS::ElastiCache::CacheCluster",
    "AWS::ElastiCache::ReplicationGroup",
    # EFS
    "AWS::EFS::FileSystem",
    "AWS::EFS::AccessPoint",
    # EventBridge
    "AWS::Events::Rule",
    "AWS::Events::EventBus",
    # Kinesis
    "AWS::Kinesis::Stream",
    "AWS::KinesisFirehose::DeliveryStream",
    # Redshift
    "AWS::Redshift::Cluster",
    "AWS::Redshift::ClusterParameterGroup",
    "AWS::Redshift::ClusterSecurityGroup",
    "AWS::Redshift::ClusterSubnetGroup",
    # SSM
    "AWS::SSM::ManagedInstanceInventory",
    "AWS::SSM::PatchCompliance",
    "AWS::SSM::AssociationCompliance",
    "AWS::SSM::FileData",
    # Step Functions
    "AWS::StepFunctions::StateMachine",
    "AWS::StepFunctions::Activity",
    # VPC
    "AWS::EC2::VPCEndpoint",
    "AWS::EC2::VPCEndpointService",
    "AWS::EC2::VPCPeeringConnection",
    # ACM
    "AWS::ACM::Certificate",
    # Backup
    "AWS::Backup::BackupPlan",
    "AWS::Backup::BackupSelection",
    "AWS::Backup::BackupVault",
    "AWS::Backup::RecoveryPoint",
    # Network Firewall
    "AWS::NetworkFirewall::Firewall",
    "AWS::NetworkFirewall::FirewallPolicy",
    "AWS::NetworkFirewall::RuleGroup",
    # WAF
    "AWS::WAF::RateBasedRule",
    "AWS::WAF::Rule",
    "AWS::WAF::RuleGroup",
    "AWS::WAF::WebACL",
    "AWS::WAFv2::WebACL",
    "AWS::WAFv2::RuleGroup",
    "AWS::WAFv2::IPSet",
    "AWS::WAFv2::RegexPatternSet",
    "AWS::WAFv2::ManagedRuleSet",
    # Shield
    "AWS::Shield::Protection",
    "AWS::ShieldRegional::Protection",
    # Systems Manager
    "AWS::SSM::Parameter",
    # Route53 (limited support)
    "AWS::Route53::HostedZone",
    # Glue
    "AWS::Glue::Job",
    "AWS::Glue::Classifier",
    "AWS::Glue::Crawler",
    "AWS::Glue::Database",
    "AWS::Glue::Table",
    # Athena
    "AWS::Athena::WorkGroup",
    "AWS::Athena::DataCatalog",
    # EMR
    "AWS::EMR::Cluster",
    "AWS::EMR::SecurityConfiguration",
    # SageMaker
    "AWS::SageMaker::CodeRepository",
    "AWS::SageMaker::Model",
    "AWS::SageMaker::NotebookInstance",
    "AWS::SageMaker::Workteam",
}

# Resource types that should ALWAYS use direct API collectors
# (even if technically supported by Config, the direct API is better)
DIRECT_API_ONLY_TYPES: Set[str] = {
    # Route53 has better data via direct API
    "AWS::Route53::HostedZone",
    # WAF has complex regional/CloudFront distinction
    "AWS::WAFv2::WebACL::Regional",
    "AWS::WAFv2::WebACL::CloudFront",
}

# Mapping from collector service_name to AWS Config resource types
COLLECTOR_TO_CONFIG_TYPES: dict[str, list[str]] = {
    "ec2": [
        "AWS::EC2::Instance",
        "AWS::EC2::Volume",
        "AWS::EC2::VPC",
        "AWS::EC2::SecurityGroup",
        "AWS::EC2::Subnet",
        "AWS::EC2::NatGateway",
        "AWS::EC2::InternetGateway",
        "AWS::EC2::RouteTable",
        "AWS::EC2::NetworkAcl",
        "AWS::EC2::NetworkInterface",
        "AWS::EC2::EIP",
    ],
    "iam": [
        "AWS::IAM::Role",
        "AWS::IAM::User",
        "AWS::IAM::Group",
        "AWS::IAM::Policy",
    ],
    "s3": [
        "AWS::S3::Bucket",
    ],
    "lambda": [
        "AWS::Lambda::Function",
    ],
    "rds": [
        "AWS::RDS::DBInstance",
        "AWS::RDS::DBCluster",
    ],
    "dynamodb": [
        "AWS::DynamoDB::Table",
    ],
    "cloudwatch": [
        "AWS::Logs::LogGroup",
        "AWS::CloudWatch::Alarm",
    ],
    "sns": [
        "AWS::SNS::Topic",
    ],
    "sqs": [
        "AWS::SQS::Queue",
    ],
    "elb": [
        "AWS::ElasticLoadBalancing::LoadBalancer",
        "AWS::ElasticLoadBalancingV2::LoadBalancer",
        "AWS::ElasticLoadBalancingV2::TargetGroup",
    ],
    "ecs": [
        "AWS::ECS::Cluster",
        "AWS::ECS::Service",
        "AWS::ECS::TaskDefinition",
    ],
    "eks": [
        "AWS::EKS::Cluster",
        "AWS::EKS::Nodegroup",
        "AWS::EKS::FargateProfile",
    ],
    "kms": [
        "AWS::KMS::Key",
    ],
    "secretsmanager": [
        "AWS::SecretsManager::Secret",
    ],
    "apigateway": [
        "AWS::ApiGateway::RestApi",
        "AWS::ApiGateway::Stage",
        "AWS::ApiGatewayV2::Api",
    ],
    "cloudformation": [
        "AWS::CloudFormation::Stack",
    ],
    "codebuild": [
        "AWS::CodeBuild::Project",
    ],
    "codepipeline": [
        "AWS::CodePipeline::Pipeline",
    ],
    "elasticache": [
        "AWS::ElastiCache::CacheCluster",
        "AWS::ElastiCache::ReplicationGroup",
    ],
    "efs": [
        "AWS::EFS::FileSystem",
        "AWS::EFS::AccessPoint",
    ],
    "eventbridge": [
        "AWS::Events::Rule",
        "AWS::Events::EventBus",
    ],
    "stepfunctions": [
        "AWS::StepFunctions::StateMachine",
    ],
    "backup": [
        "AWS::Backup::BackupPlan",
        "AWS::Backup::BackupVault",
    ],
    "ssm": [
        "AWS::SSM::Parameter",
    ],
    "vpcendpoints": [
        "AWS::EC2::VPCEndpoint",
    ],
    "waf": [
        "AWS::WAFv2::WebACL",
        "AWS::WAFv2::RuleGroup",
        "AWS::WAFv2::IPSet",
    ],
    "route53": [
        "AWS::Route53::HostedZone",
    ],
}


def is_config_supported_type(resource_type: str) -> bool:
    """Check if a resource type is supported by AWS Config.

    Args:
        resource_type: AWS resource type (e.g., "AWS::EC2::Instance")

    Returns:
        True if the type can be collected via AWS Config
    """
    if resource_type in DIRECT_API_ONLY_TYPES:
        return False
    return resource_type in CONFIG_SUPPORTED_TYPES


def get_config_types_for_service(service_name: str) -> list[str]:
    """Get AWS Config resource types for a collector service.

    Args:
        service_name: Collector service name (e.g., "ec2", "s3")

    Returns:
        List of AWS Config resource types for this service
    """
    return COLLECTOR_TO_CONFIG_TYPES.get(service_name, [])
