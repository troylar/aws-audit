"""Layer definitions for IaC generation ordering."""

from enum import Enum, IntEnum
from typing import Dict


class LayerStatus(Enum):
    """Status of a layer during generation."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    GENERATING = "generating"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"


class LayerOrder(IntEnum):
    """Layer generation order (lower = earlier)."""

    NETWORK = 1  # VPC, Subnets, Route Tables
    SECURITY = 2  # Security Groups, NACLs
    IAM = 3  # Roles, Policies
    DATA = 4  # RDS, DynamoDB, ElastiCache
    STORAGE = 5  # S3, EFS, EBS
    COMPUTE = 6  # EC2, ECS, EKS, Lambda
    LOADBALANCING = 7  # ALB, NLB, Target Groups
    APPLICATION = 8  # API Gateway, AppRunner
    MESSAGING = 9  # SQS, SNS, EventBridge
    MONITORING = 10  # CloudWatch, X-Ray
    DNS = 11  # Route53


RESOURCE_TYPE_TO_LAYER: Dict[str, LayerOrder] = {
    # Network (Layer 1)
    "ec2:vpc": LayerOrder.NETWORK,
    "ec2:subnet": LayerOrder.NETWORK,
    "ec2:internet-gateway": LayerOrder.NETWORK,
    "ec2:nat-gateway": LayerOrder.NETWORK,
    "ec2:route-table": LayerOrder.NETWORK,
    "ec2:vpc-endpoint": LayerOrder.NETWORK,
    "ec2:elastic-ip": LayerOrder.NETWORK,
    "ec2:transit-gateway": LayerOrder.NETWORK,
    "ec2:transit-gateway-attachment": LayerOrder.NETWORK,
    "ec2:vpc-peering-connection": LayerOrder.NETWORK,
    # Network (AWS CloudFormation format)
    "AWS::EC2::VPC": LayerOrder.NETWORK,
    "AWS::EC2::Subnet": LayerOrder.NETWORK,
    "AWS::EC2::InternetGateway": LayerOrder.NETWORK,
    "AWS::EC2::NatGateway": LayerOrder.NETWORK,
    "AWS::EC2::RouteTable": LayerOrder.NETWORK,
    "AWS::EC2::VPCEndpoint": LayerOrder.NETWORK,
    "AWS::EC2::VPCEndpoint::Gateway": LayerOrder.NETWORK,
    "AWS::EC2::VPCEndpoint::Interface": LayerOrder.NETWORK,
    "AWS::EC2::EIP": LayerOrder.NETWORK,
    "AWS::EC2::TransitGateway": LayerOrder.NETWORK,
    "AWS::EC2::VPCPeeringConnection": LayerOrder.NETWORK,
    # Security (Layer 2)
    "ec2:security-group": LayerOrder.SECURITY,
    "ec2:network-acl": LayerOrder.SECURITY,
    "wafv2:web-acl": LayerOrder.SECURITY,
    "acm:certificate": LayerOrder.SECURITY,
    "secretsmanager:secret": LayerOrder.SECURITY,
    "kms:key": LayerOrder.SECURITY,
    # Security (AWS CloudFormation format)
    "AWS::EC2::SecurityGroup": LayerOrder.SECURITY,
    "AWS::EC2::NetworkAcl": LayerOrder.SECURITY,
    "AWS::WAFv2::WebACL": LayerOrder.SECURITY,
    "AWS::ACM::Certificate": LayerOrder.SECURITY,
    "AWS::SecretsManager::Secret": LayerOrder.SECURITY,
    "AWS::KMS::Key": LayerOrder.SECURITY,
    # IAM (Layer 3)
    "iam:role": LayerOrder.IAM,
    "iam:policy": LayerOrder.IAM,
    "iam:instance-profile": LayerOrder.IAM,
    "iam:user": LayerOrder.IAM,
    "iam:group": LayerOrder.IAM,
    # IAM (AWS CloudFormation format)
    "AWS::IAM::Role": LayerOrder.IAM,
    "AWS::IAM::Policy": LayerOrder.IAM,
    "AWS::IAM::InstanceProfile": LayerOrder.IAM,
    "AWS::IAM::User": LayerOrder.IAM,
    "AWS::IAM::Group": LayerOrder.IAM,
    # Data (Layer 4)
    "rds:db-instance": LayerOrder.DATA,
    "rds:db-cluster": LayerOrder.DATA,
    "rds:db-subnet-group": LayerOrder.DATA,
    "rds:db-parameter-group": LayerOrder.DATA,
    "rds:db-cluster-parameter-group": LayerOrder.DATA,
    "dynamodb:table": LayerOrder.DATA,
    "elasticache:cluster": LayerOrder.DATA,
    "elasticache:replication-group": LayerOrder.DATA,
    "elasticache:subnet-group": LayerOrder.DATA,
    "redshift:cluster": LayerOrder.DATA,
    "elasticsearch:domain": LayerOrder.DATA,
    "opensearch:domain": LayerOrder.DATA,
    "glue:database": LayerOrder.DATA,
    "glue:table": LayerOrder.DATA,
    "glue:crawler": LayerOrder.DATA,
    "glue:job": LayerOrder.DATA,
    "glue:trigger": LayerOrder.DATA,
    "glue:connection": LayerOrder.DATA,
    "glue:classifier": LayerOrder.DATA,
    "glue:workflow": LayerOrder.DATA,
    # Data (AWS CloudFormation format)
    "AWS::RDS::DBInstance": LayerOrder.DATA,
    "AWS::RDS::DBCluster": LayerOrder.DATA,
    "AWS::RDS::DBSubnetGroup": LayerOrder.DATA,
    "AWS::RDS::DBParameterGroup": LayerOrder.DATA,
    "AWS::RDS::DBClusterParameterGroup": LayerOrder.DATA,
    "AWS::DynamoDB::Table": LayerOrder.DATA,
    "AWS::ElastiCache::CacheCluster": LayerOrder.DATA,
    "AWS::ElastiCache::ReplicationGroup": LayerOrder.DATA,
    "AWS::ElastiCache::SubnetGroup": LayerOrder.DATA,
    "AWS::Redshift::Cluster": LayerOrder.DATA,
    "AWS::Elasticsearch::Domain": LayerOrder.DATA,
    "AWS::OpenSearchService::Domain": LayerOrder.DATA,
    "AWS::Glue::Database": LayerOrder.DATA,
    "AWS::Glue::Table": LayerOrder.DATA,
    "AWS::Glue::Crawler": LayerOrder.DATA,
    "AWS::Glue::Job": LayerOrder.DATA,
    "AWS::Glue::Trigger": LayerOrder.DATA,
    "AWS::Glue::Connection": LayerOrder.DATA,
    "AWS::Glue::Classifier": LayerOrder.DATA,
    "AWS::Glue::Workflow": LayerOrder.DATA,
    # Storage (Layer 5)
    "s3:bucket": LayerOrder.STORAGE,
    "efs:file-system": LayerOrder.STORAGE,
    "efs:mount-target": LayerOrder.STORAGE,
    "efs:access-point": LayerOrder.STORAGE,
    "fsx:file-system": LayerOrder.STORAGE,
    "backup:backup-vault": LayerOrder.STORAGE,
    "backup:backup-plan": LayerOrder.STORAGE,
    # Storage (AWS CloudFormation format)
    "AWS::S3::Bucket": LayerOrder.STORAGE,
    "AWS::EFS::FileSystem": LayerOrder.STORAGE,
    "AWS::EFS::MountTarget": LayerOrder.STORAGE,
    "AWS::EFS::AccessPoint": LayerOrder.STORAGE,
    "AWS::FSx::FileSystem": LayerOrder.STORAGE,
    "AWS::Backup::BackupVault": LayerOrder.STORAGE,
    "AWS::Backup::BackupPlan": LayerOrder.STORAGE,
    # Compute (Layer 6)
    "ec2:instance": LayerOrder.COMPUTE,
    "ec2:launch-template": LayerOrder.COMPUTE,
    "ec2:auto-scaling-group": LayerOrder.COMPUTE,
    "lambda:function": LayerOrder.COMPUTE,
    "lambda:layer": LayerOrder.COMPUTE,
    "lambda:event-source-mapping": LayerOrder.COMPUTE,
    "ecs:cluster": LayerOrder.COMPUTE,
    "ecs:service": LayerOrder.COMPUTE,
    "ecs:task-definition": LayerOrder.COMPUTE,
    "eks:cluster": LayerOrder.COMPUTE,
    "eks:nodegroup": LayerOrder.COMPUTE,
    "eks:fargate-profile": LayerOrder.COMPUTE,
    "batch:compute-environment": LayerOrder.COMPUTE,
    "batch:job-queue": LayerOrder.COMPUTE,
    "batch:job-definition": LayerOrder.COMPUTE,
    # Compute (AWS CloudFormation format)
    "AWS::EC2::Instance": LayerOrder.COMPUTE,
    "AWS::EC2::LaunchTemplate": LayerOrder.COMPUTE,
    "AWS::AutoScaling::AutoScalingGroup": LayerOrder.COMPUTE,
    "AWS::EC2::Volume": LayerOrder.COMPUTE,
    "AWS::Lambda::Function": LayerOrder.COMPUTE,
    "AWS::Lambda::LayerVersion": LayerOrder.COMPUTE,
    "AWS::Lambda::EventSourceMapping": LayerOrder.COMPUTE,
    "AWS::ECS::Cluster": LayerOrder.COMPUTE,
    "AWS::ECS::Service": LayerOrder.COMPUTE,
    "AWS::ECS::TaskDefinition": LayerOrder.COMPUTE,
    "AWS::EKS::Cluster": LayerOrder.COMPUTE,
    "AWS::EKS::Nodegroup": LayerOrder.COMPUTE,
    "AWS::EKS::FargateProfile": LayerOrder.COMPUTE,
    "AWS::Batch::ComputeEnvironment": LayerOrder.COMPUTE,
    "AWS::Batch::JobQueue": LayerOrder.COMPUTE,
    "AWS::Batch::JobDefinition": LayerOrder.COMPUTE,
    # Load Balancing (Layer 7)
    "elbv2:loadbalancer": LayerOrder.LOADBALANCING,
    "elbv2:target-group": LayerOrder.LOADBALANCING,
    "elbv2:listener": LayerOrder.LOADBALANCING,
    "elbv2:listener-rule": LayerOrder.LOADBALANCING,
    "elb:loadbalancer": LayerOrder.LOADBALANCING,
    # Load Balancing (AWS CloudFormation format)
    "AWS::ElasticLoadBalancingV2::LoadBalancer": LayerOrder.LOADBALANCING,
    "AWS::ElasticLoadBalancingV2::LoadBalancer::Application": LayerOrder.LOADBALANCING,
    "AWS::ElasticLoadBalancingV2::LoadBalancer::Network": LayerOrder.LOADBALANCING,
    "AWS::ElasticLoadBalancingV2::TargetGroup": LayerOrder.LOADBALANCING,
    "AWS::ElasticLoadBalancingV2::Listener": LayerOrder.LOADBALANCING,
    "AWS::ElasticLoadBalancingV2::ListenerRule": LayerOrder.LOADBALANCING,
    "AWS::ElasticLoadBalancing::LoadBalancer": LayerOrder.LOADBALANCING,
    # Application (Layer 8)
    "apigateway:rest-api": LayerOrder.APPLICATION,
    "apigateway:resource": LayerOrder.APPLICATION,
    "apigateway:method": LayerOrder.APPLICATION,
    "apigateway:stage": LayerOrder.APPLICATION,
    "apigateway:deployment": LayerOrder.APPLICATION,
    "apigatewayv2:api": LayerOrder.APPLICATION,
    "apigatewayv2:stage": LayerOrder.APPLICATION,
    "apigatewayv2:route": LayerOrder.APPLICATION,
    "apigatewayv2:integration": LayerOrder.APPLICATION,
    "apprunner:service": LayerOrder.APPLICATION,
    "appsync:graphql-api": LayerOrder.APPLICATION,
    "cognito:user-pool": LayerOrder.APPLICATION,
    "cognito:identity-pool": LayerOrder.APPLICATION,
    # Application (AWS CloudFormation format)
    "AWS::ApiGateway::RestApi": LayerOrder.APPLICATION,
    "AWS::ApiGateway::Resource": LayerOrder.APPLICATION,
    "AWS::ApiGateway::Method": LayerOrder.APPLICATION,
    "AWS::ApiGateway::Stage": LayerOrder.APPLICATION,
    "AWS::ApiGateway::Deployment": LayerOrder.APPLICATION,
    "AWS::ApiGatewayV2::Api": LayerOrder.APPLICATION,
    "AWS::ApiGatewayV2::Stage": LayerOrder.APPLICATION,
    "AWS::ApiGatewayV2::Route": LayerOrder.APPLICATION,
    "AWS::ApiGatewayV2::Integration": LayerOrder.APPLICATION,
    "AWS::AppRunner::Service": LayerOrder.APPLICATION,
    "AWS::AppSync::GraphQLApi": LayerOrder.APPLICATION,
    "AWS::Cognito::UserPool": LayerOrder.APPLICATION,
    "AWS::Cognito::IdentityPool": LayerOrder.APPLICATION,
    # Messaging (Layer 9)
    "sqs:queue": LayerOrder.MESSAGING,
    "sns:topic": LayerOrder.MESSAGING,
    "sns:subscription": LayerOrder.MESSAGING,
    "events:rule": LayerOrder.MESSAGING,
    "events:event-bus": LayerOrder.MESSAGING,
    "kinesis:stream": LayerOrder.MESSAGING,
    "firehose:delivery-stream": LayerOrder.MESSAGING,
    "stepfunctions:state-machine": LayerOrder.MESSAGING,
    # Messaging (AWS CloudFormation format)
    "AWS::SQS::Queue": LayerOrder.MESSAGING,
    "AWS::SNS::Topic": LayerOrder.MESSAGING,
    "AWS::SNS::Subscription": LayerOrder.MESSAGING,
    "AWS::Events::Rule": LayerOrder.MESSAGING,
    "AWS::Events::EventBus": LayerOrder.MESSAGING,
    "AWS::Kinesis::Stream": LayerOrder.MESSAGING,
    "AWS::KinesisFirehose::DeliveryStream": LayerOrder.MESSAGING,
    "AWS::StepFunctions::StateMachine": LayerOrder.MESSAGING,
    # Monitoring (Layer 10)
    "cloudwatch:alarm": LayerOrder.MONITORING,
    "cloudwatch:metric-alarm": LayerOrder.MONITORING,
    "cloudwatch:dashboard": LayerOrder.MONITORING,
    "logs:log-group": LayerOrder.MONITORING,
    "xray:group": LayerOrder.MONITORING,
    "xray:sampling-rule": LayerOrder.MONITORING,
    "cloudtrail:trail": LayerOrder.MONITORING,
    "config:config-rule": LayerOrder.MONITORING,
    # Monitoring (AWS CloudFormation format)
    "AWS::CloudWatch::Alarm": LayerOrder.MONITORING,
    "AWS::CloudWatch::Dashboard": LayerOrder.MONITORING,
    "AWS::Logs::LogGroup": LayerOrder.MONITORING,
    "AWS::XRay::Group": LayerOrder.MONITORING,
    "AWS::XRay::SamplingRule": LayerOrder.MONITORING,
    "AWS::CloudTrail::Trail": LayerOrder.MONITORING,
    "AWS::Config::ConfigRule": LayerOrder.MONITORING,
    "AWS::SSM::Parameter": LayerOrder.MONITORING,
    # DNS (Layer 11)
    "route53:hosted-zone": LayerOrder.DNS,
    "route53:record-set": LayerOrder.DNS,
    "route53:health-check": LayerOrder.DNS,
    "cloudfront:distribution": LayerOrder.DNS,
    "acm:certificate-validation": LayerOrder.DNS,
    # DNS (AWS CloudFormation format)
    "AWS::Route53::HostedZone": LayerOrder.DNS,
    "AWS::Route53::RecordSet": LayerOrder.DNS,
    "AWS::Route53::HealthCheck": LayerOrder.DNS,
    "AWS::CloudFront::Distribution": LayerOrder.DNS,
}
