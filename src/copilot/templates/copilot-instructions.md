---
model: gpt-4.1
optimizations:
  - token-efficient (4k context pressure)
  - terse rules over prose
  - batch guidance for large inputs
  - explicit chunking instructions
constraints:
  base-instructions-tokens: 4000
  task-prompt-tokens: 2000
  batch-threshold-resources: 50
last-updated: 2026-01-29
---

# AWS Inventory Manager - Copilot Instructions

Context for generating Infrastructure as Code from AWS inventory YAML snapshots.

## Commands

```bash
# Snapshot management
awsinv snapshot create <name>           # Create new snapshot
awsinv snapshot list                    # List all snapshots
awsinv snapshot show <name>             # Show snapshot details
awsinv snapshot diff <name1> <name2>    # Compare two snapshots

# Resource inventory
awsinv inventory list                   # List discovered resources
awsinv inventory export --format yaml   # Export to YAML

# IaC generation (use prompts)
# /generate-terraform - Generate Terraform from snapshot
# /generate-cdk-typescript - Generate CDK TypeScript
# /generate-cdk-python - Generate CDK Python
```

## Boundaries

### Always Do

- Use the YAML schema defined below when parsing snapshot files
- Follow AWS Well-Architected best practices for generated IaC
- Include resource tags from the snapshot in generated code
- Use variables for environment-specific values (regions, account IDs)
- Generate separate files for logical groupings (networking, compute, etc.)

### Ask First

- Before generating IaC for 50+ resources (may need batching)
- Before choosing between Terraform and CDK if not specified
- When snapshot contains resources with missing or incomplete configurations
- When generating cross-account or cross-region references

### Never Do

- Never hardcode AWS credentials or secrets in generated code
- Never use overly permissive IAM policies (avoid `*` wildcards)
- Never generate resources without encryption configuration
- Never ignore existing tags from the snapshot

## Inventory YAML Schema

| Field | Type | Description |
|-------|------|-------------|
| arn | string | AWS Resource ARN |
| type | string | AWS::Service::Resource format |
| name | string | Resource name or ID |
| region | string | AWS region (e.g., us-east-1) |
| tags | object | Key-value tag pairs |
| raw_config | object | Service-specific configuration |

### Example Resource

```yaml
- arn: arn:aws:ec2:us-east-1:123456789012:instance/i-abc123
  type: AWS::EC2::Instance
  name: web-server-1
  region: us-east-1
  tags:
    Environment: production
    Team: platform
  raw_config:
    InstanceType: t3.medium
    SubnetId: subnet-abc123
    SecurityGroups: [sg-abc123]
```

## Good vs Bad Examples

### IAM Policy Generation

```hcl
# Bad: Overly permissive
resource "aws_iam_policy" "app" {
  policy = jsonencode({
    Statement = [{
      Effect   = "Allow"
      Action   = "*"
      Resource = "*"
    }]
  })
}

# Good: Least privilege from snapshot
resource "aws_iam_policy" "app" {
  policy = jsonencode({
    Statement = [{
      Effect   = "Allow"
      Action   = ["s3:GetObject", "s3:PutObject"]
      Resource = "arn:aws:s3:::${var.bucket_name}/*"
    }]
  })
}
```

### Resource Tagging

```hcl
# Bad: Ignores snapshot tags
resource "aws_instance" "web" {
  ami           = var.ami_id
  instance_type = "t3.medium"
}

# Good: Preserves snapshot tags
resource "aws_instance" "web" {
  ami           = var.ami_id
  instance_type = "t3.medium"

  tags = {
    Name        = "web-server-1"
    Environment = "production"  # From snapshot
    Team        = "platform"    # From snapshot
  }
}
```

### Secrets Handling

```hcl
# Bad: Hardcoded secrets
resource "aws_db_instance" "main" {
  password = "supersecret123"
}

# Good: Reference secrets manager
resource "aws_db_instance" "main" {
  password = data.aws_secretsmanager_secret_version.db.secret_string
}
```

## AWS Best Practices

### Security (SEC)

- Never hardcode secrets; use SSM Parameter Store, Secrets Manager, or env vars
- Enable encryption at rest (KMS) for S3, RDS, EBS, DynamoDB
- Enable encryption in transit (TLS/SSL) for all endpoints
- Use least-privilege IAM policies; avoid wildcards (*)
- Enable VPC flow logs for network visibility
- Use security groups with minimal ingress rules
- Enable CloudTrail for audit logging

### Reliability (REL)

- Use Multi-AZ deployments for RDS, ElastiCache
- Configure auto-scaling for EC2, ECS, Lambda
- Set appropriate timeouts and retries
- Use health checks for load balancers
- Enable automated backups with retention policies
- Use Route53 health checks for DNS failover

### Cost Optimization (COST)

- Right-size instances based on utilization
- Use Reserved Instances or Savings Plans for steady-state
- Enable S3 lifecycle policies for storage tiers
- Use spot instances for fault-tolerant workloads
- Tag resources for cost allocation
- Delete unused resources (EIPs, snapshots, volumes)

## Resource-Specific Guidance

### EC2

- Use launch templates over launch configurations
- Prefer instance metadata v2 (IMDSv2)
- Use EBS-optimized instances
- Consider Graviton (arm64) for cost savings

### RDS

- Use parameter groups for configuration
- Enable Performance Insights
- Use IAM authentication where possible
- Configure appropriate backup windows

### Lambda

- Set appropriate memory (affects CPU allocation)
- Use provisioned concurrency for latency-sensitive
- Configure dead letter queues
- Use layers for shared dependencies

### S3

- Enable versioning for critical buckets
- Use bucket policies over ACLs
- Enable server access logging
- Configure appropriate lifecycle rules

### VPC

- Use /16 CIDR for VPCs, /24 for subnets
- Reserve IP ranges for future expansion
- Use NAT Gateways per AZ for HA
- Use VPC endpoints for AWS services

## Custom Instructions

If `copilot-custom.md` exists in this directory, follow org-specific standards
defined there for naming conventions, tagging policies, and security requirements.
Custom instructions take precedence over these defaults.
