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
    # Security (Layer 2)
    "ec2:security-group": LayerOrder.SECURITY,
    "ec2:network-acl": LayerOrder.SECURITY,
    "wafv2:web-acl": LayerOrder.SECURITY,
    "acm:certificate": LayerOrder.SECURITY,
    "secretsmanager:secret": LayerOrder.SECURITY,
    "kms:key": LayerOrder.SECURITY,
    # IAM (Layer 3)
    "iam:role": LayerOrder.IAM,
    "iam:policy": LayerOrder.IAM,
    "iam:instance-profile": LayerOrder.IAM,
    "iam:user": LayerOrder.IAM,
    "iam:group": LayerOrder.IAM,
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
    # Storage (Layer 5)
    "s3:bucket": LayerOrder.STORAGE,
    "efs:file-system": LayerOrder.STORAGE,
    "efs:mount-target": LayerOrder.STORAGE,
    "efs:access-point": LayerOrder.STORAGE,
    "fsx:file-system": LayerOrder.STORAGE,
    "backup:backup-vault": LayerOrder.STORAGE,
    "backup:backup-plan": LayerOrder.STORAGE,
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
    # Load Balancing (Layer 7)
    "elbv2:loadbalancer": LayerOrder.LOADBALANCING,
    "elbv2:target-group": LayerOrder.LOADBALANCING,
    "elbv2:listener": LayerOrder.LOADBALANCING,
    "elbv2:listener-rule": LayerOrder.LOADBALANCING,
    "elb:loadbalancer": LayerOrder.LOADBALANCING,
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
    # Messaging (Layer 9)
    "sqs:queue": LayerOrder.MESSAGING,
    "sns:topic": LayerOrder.MESSAGING,
    "sns:subscription": LayerOrder.MESSAGING,
    "events:rule": LayerOrder.MESSAGING,
    "events:event-bus": LayerOrder.MESSAGING,
    "kinesis:stream": LayerOrder.MESSAGING,
    "firehose:delivery-stream": LayerOrder.MESSAGING,
    "stepfunctions:state-machine": LayerOrder.MESSAGING,
    # Monitoring (Layer 10)
    "cloudwatch:alarm": LayerOrder.MONITORING,
    "cloudwatch:metric-alarm": LayerOrder.MONITORING,
    "cloudwatch:dashboard": LayerOrder.MONITORING,
    "logs:log-group": LayerOrder.MONITORING,
    "xray:group": LayerOrder.MONITORING,
    "xray:sampling-rule": LayerOrder.MONITORING,
    "cloudtrail:trail": LayerOrder.MONITORING,
    "config:config-rule": LayerOrder.MONITORING,
    # DNS (Layer 11)
    "route53:hosted-zone": LayerOrder.DNS,
    "route53:record-set": LayerOrder.DNS,
    "route53:health-check": LayerOrder.DNS,
    "cloudfront:distribution": LayerOrder.DNS,
    "acm:certificate-validation": LayerOrder.DNS,
}
