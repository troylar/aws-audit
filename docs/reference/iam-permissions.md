# IAM Permissions

The tool requires different permissions depending on which features you use. Combine the policies below based on your needs, or attach them as separate managed policies.

!!! tip
    Start with just "Snapshot Collection" permissions. Add others only when needed.

## Snapshot Collection (Read-Only)

For basic snapshot collection. The easiest approach is the `ReadOnlyAccess` AWS managed policy, but here's a minimal custom policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "SnapshotCollection",
      "Effect": "Allow",
      "Action": [
        "ec2:Describe*",
        "s3:GetBucket*",
        "s3:ListAllMyBuckets",
        "s3:ListBucket",
        "lambda:List*",
        "lambda:GetFunction*",
        "iam:List*",
        "iam:Get*",
        "rds:Describe*",
        "dynamodb:Describe*",
        "dynamodb:List*",
        "ecs:Describe*",
        "ecs:List*",
        "eks:Describe*",
        "eks:List*",
        "sns:List*",
        "sns:GetTopicAttributes",
        "sqs:List*",
        "sqs:GetQueueAttributes",
        "cloudwatch:Describe*",
        "cloudwatch:List*",
        "elasticloadbalancing:Describe*",
        "route53:List*",
        "route53:Get*",
        "secretsmanager:List*",
        "secretsmanager:DescribeSecret",
        "kms:List*",
        "kms:Describe*",
        "apigateway:GET",
        "events:List*",
        "events:Describe*",
        "states:List*",
        "states:Describe*",
        "codepipeline:List*",
        "codepipeline:Get*",
        "codebuild:List*",
        "codebuild:BatchGet*",
        "cloudformation:Describe*",
        "cloudformation:List*",
        "elasticache:Describe*",
        "ssm:DescribeParameters",
        "ssm:GetParameter*",
        "backup:List*",
        "backup:Describe*",
        "efs:Describe*",
        "wafv2:List*",
        "wafv2:Get*"
      ],
      "Resource": "*"
    }
  ]
}
```

## AWS Config Integration (Optional)

For faster collection via AWS Config:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ConfigRead",
      "Effect": "Allow",
      "Action": [
        "config:DescribeConfigurationRecorders",
        "config:DescribeConfigurationRecorderStatus",
        "config:GetDiscoveredResourceCounts",
        "config:ListDiscoveredResources",
        "config:BatchGetResourceConfig"
      ],
      "Resource": "*"
    }
  ]
}
```

For Config Aggregators (multi-account):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ConfigAggregator",
      "Effect": "Allow",
      "Action": [
        "config:DescribeConfigurationAggregators",
        "config:SelectAggregateResourceConfig"
      ],
      "Resource": "*"
    }
  ]
}
```

## CloudTrail (Creator Tracking)

For the `--track-creators` flag and `enrich-creators` command:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "CloudTrailLookup",
      "Effect": "Allow",
      "Action": [
        "cloudtrail:LookupEvents"
      ],
      "Resource": "*"
    }
  ]
}
```

## Cost Analysis

For the `awsinv cost` command:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "CostExplorer",
      "Effect": "Allow",
      "Action": [
        "ce:GetCostAndUsage",
        "ce:GetCostForecast"
      ],
      "Resource": "*"
    }
  ]
}
```

## Resource Cleanup

!!! danger
    These permissions allow resource deletion. Use with extreme caution.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ResourceCleanup",
      "Effect": "Allow",
      "Action": [
        "ec2:TerminateInstances",
        "ec2:DeleteVolume",
        "ec2:DeleteVpc",
        "ec2:DeleteSubnet",
        "ec2:DeleteSecurityGroup",
        "ec2:DeleteInternetGateway",
        "ec2:DeleteNatGateway",
        "ec2:DeleteRouteTable",
        "ec2:DeleteVpcEndpoints",
        "ec2:DetachInternetGateway",
        "ec2:DisassociateRouteTable",
        "ec2:ReleaseAddress",
        "ec2:DeleteKeyPair",
        "s3:DeleteBucket",
        "s3:DeleteObject",
        "s3:DeleteObjectVersion",
        "lambda:DeleteFunction",
        "iam:DeleteRole",
        "iam:DeleteRolePolicy",
        "iam:DetachRolePolicy",
        "iam:DeleteUser",
        "iam:DeleteUserPolicy",
        "iam:DetachUserPolicy",
        "iam:DeleteAccessKey",
        "iam:DeleteLoginProfile",
        "iam:DeactivateMFADevice",
        "iam:DeletePolicy",
        "rds:DeleteDBInstance",
        "rds:DeleteDBCluster",
        "dynamodb:DeleteTable",
        "ecs:DeleteCluster",
        "ecs:DeleteService",
        "ecs:DeregisterTaskDefinition",
        "eks:DeleteCluster",
        "sns:DeleteTopic",
        "sqs:DeleteQueue",
        "cloudwatch:DeleteAlarms",
        "elasticloadbalancing:DeleteLoadBalancer",
        "elasticloadbalancing:DeleteTargetGroup",
        "route53:DeleteHostedZone",
        "route53:ChangeResourceRecordSets",
        "secretsmanager:DeleteSecret",
        "kms:ScheduleKeyDeletion",
        "apigateway:DELETE",
        "events:DeleteRule",
        "events:RemoveTargets",
        "states:DeleteStateMachine",
        "codepipeline:DeletePipeline",
        "codebuild:DeleteProject",
        "cloudformation:DeleteStack",
        "elasticache:DeleteCacheCluster",
        "ssm:DeleteParameter",
        "backup:DeleteBackupPlan",
        "backup:DeleteBackupVault",
        "backup:DeleteRecoveryPoint",
        "efs:DeleteFileSystem",
        "efs:DeleteMountTarget",
        "wafv2:DeleteWebACL",
        "wafv2:DeleteRuleGroup",
        "wafv2:DisassociateWebACL"
      ],
      "Resource": "*"
    }
  ]
}
```

**Recommendation:** For production accounts, use separate IAM roles for read-only operations (snapshots) and cleanup operations. Never give cleanup permissions to everyday users.
