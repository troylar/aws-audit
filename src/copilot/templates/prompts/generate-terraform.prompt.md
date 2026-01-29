---
model: gpt-4.1
optimizations:
  - token-efficient
  - terraform-specific best practices
constraints:
  task-prompt-tokens: 2000
last-updated: 2026-01-29
---

# Generate Terraform from Inventory

Generate Terraform HCL code from the provided AWS inventory YAML.

## Output Structure

Generate separate files per resource type:

```
terraform/
├── providers.tf      # AWS provider config
├── variables.tf      # Input variables
├── outputs.tf        # Output values
├── locals.tf         # Local values
├── ec2.tf           # EC2 instances, AMIs
├── vpc.tf           # VPCs, subnets, route tables
├── security.tf      # Security groups, NACLs
├── rds.tf           # RDS instances, clusters
├── lambda.tf        # Lambda functions
├── iam.tf           # IAM roles, policies
├── s3.tf            # S3 buckets
└── ...              # Other resource types
```

## Rules

### Variables & Locals

1. Use variables for all configurable values
2. Use locals for repeated expressions and computed values
3. Provide sensible defaults where appropriate
4. Group related variables together

```hcl
variable "environment" {
  type        = string
  description = "Environment name"
}

locals {
  common_tags = {
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}
```

### Resource Naming

1. Use descriptive resource names: `aws_instance.web_server`
2. Use snake_case for resource names
3. Reference other resources by name, not hardcoded IDs

### Lifecycle & Data Sources

1. Use `lifecycle { prevent_destroy = true }` for stateful resources
2. Use data sources for existing resources not in inventory
3. Use `depends_on` only when implicit dependencies insufficient

### Multi-Region

1. Use provider aliases for multi-region deployments
2. Pass provider explicitly to modules

```hcl
provider "aws" {
  alias  = "us_west_2"
  region = "us-west-2"
}
```

### Tagging Strategy

1. Apply consistent tags via locals
2. Merge resource-specific tags with common tags

```hcl
tags = merge(local.common_tags, {
  Name = "web-server"
})
```

### Sensitive Values

1. Replace secrets with variable references
2. Mark sensitive variables: `sensitive = true`
3. Use SSM or Secrets Manager data sources

```hcl
variable "db_password" {
  type      = string
  sensitive = true
}
```

## Validation

After generation, run:

```bash
terraform fmt -recursive
terraform validate
terraform plan
```

## Important: Generate ALL Resource Types

**Generate Terraform for EVERY resource in the inventory**, regardless of service type. Do not skip any resources. The inventory may contain any AWS service - generate appropriate Terraform resources for all of them.

Map the `type` field (e.g., `AWS::EC2::Instance`, `AWS::Lambda::Function`, `AWS::RDS::DBInstance`) to the corresponding Terraform resource type (e.g., `aws_instance`, `aws_lambda_function`, `aws_db_instance`).

## Large Inventories (50+ resources)

Only batch if the user explicitly requests it. Otherwise, generate all resources in a single pass.
