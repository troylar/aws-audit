---
applyTo: "**/*.tf,**/*.tfvars"
---

# Terraform Best Practices

Guide AI assistants to write maintainable, scalable, secure Infrastructure as Code using Terraform. These practices reflect Terraform 1.7+ capabilities and industry standards.

## Commands

```bash
# Initialization and planning
terraform init                    # Initialize working directory
terraform fmt -recursive          # Format all .tf files
terraform validate                # Validate configuration
terraform plan -out=tfplan        # Create execution plan
terraform apply tfplan            # Apply saved plan

# Testing (Terraform 1.6+)
terraform test                    # Run native tests
terraform test -filter=test_name  # Run specific test

# State management
terraform state list              # List resources in state
terraform state show <resource>   # Show resource details
terraform import <addr> <id>      # Import existing resource

# Modules
terraform get                     # Download modules
terraform init -upgrade           # Upgrade module versions
```

## Boundaries

### Always Do

- Pin Terraform version (`required_version = ">= 1.7.0"`)
- Pin provider versions with constraints (`version = "~> 5.0"`)
- Use remote state with locking (S3+DynamoDB or Terraform Cloud)
- Enable encryption for all storage resources (S3, RDS, EBS)
- Use `for_each` over `count` for dynamic resources
- Add variable validation blocks
- Mark sensitive variables with `sensitive = true`
- Use provider `default_tags` block

### Ask First

- Before using `prevent_destroy = true` (user may want flexibility)
- Before adding lifecycle `ignore_changes` (may hide drift)
- Before using workspaces vs separate state files
- When choosing between modules vs inline resources
- Before using `terraform import` (may need state coordination)

### Never Do

- Never hardcode secrets (use Secrets Manager, SSM, or Vault)
- Never use `count` with resources that have unique identifiers
- Never commit `.terraform/` directory or state files
- Never use `*` in IAM policy actions or resources
- Never disable state locking
- Never use `terraform taint` (deprecated, use `-replace`)

## Good vs Bad Examples

### Variable Definitions

```hcl
# Bad: No validation, no description
variable "environment" {
  type = string
}

# Good: Validated with clear description
variable "environment" {
  description = "Deployment environment (dev, staging, production)"
  type        = string

  validation {
    condition     = contains(["dev", "staging", "production"], var.environment)
    error_message = "Environment must be dev, staging, or production."
  }
}
```

### Resource Iteration

```hcl
# Bad: Using count with potential reordering issues
resource "aws_subnet" "private" {
  count             = length(var.availability_zones)
  availability_zone = var.availability_zones[count.index]
}

# Good: Using for_each with stable keys
resource "aws_subnet" "private" {
  for_each          = toset(var.availability_zones)
  availability_zone = each.value

  tags = {
    Name = "${local.name_prefix}-private-${each.value}"
  }
}
```

### Security Group Rules

```hcl
# Bad: Inline rules, hard to manage
resource "aws_security_group" "app" {
  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# Good: Separate rule resources, reference security groups
resource "aws_security_group" "app" {
  name   = "${local.name_prefix}-app"
  vpc_id = aws_vpc.main.id
  tags   = local.common_tags
}

resource "aws_vpc_security_group_ingress_rule" "app_https" {
  security_group_id            = aws_security_group.app.id
  from_port                    = 443
  to_port                      = 443
  ip_protocol                  = "tcp"
  referenced_security_group_id = aws_security_group.alb.id
}
```

## Version Requirements

Always specify explicit version constraints:

```hcl
terraform {
  required_version = ">= 1.7.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = local.common_tags
  }
}
```

## Module Structure

Organize Terraform code into modules:

```
project/
├── environments/
│   ├── dev/
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   ├── outputs.tf
│   │   └── terraform.tfvars
│   └── production/
├── modules/
│   ├── networking/
│   ├── compute/
│   └── database/
└── tests/
    └── networking_test.tftest.hcl
```

## Variable Definitions

Define variables with validation and descriptions:

```hcl
variable "environment" {
  description = "Environment name (dev, staging, production)"
  type        = string

  validation {
    condition     = contains(["dev", "staging", "production"], var.environment)
    error_message = "Environment must be dev, staging, or production."
  }
}

variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string

  validation {
    condition     = can(cidrhost(var.vpc_cidr, 0))
    error_message = "Must be a valid CIDR block."
  }
}

variable "database_password" {
  description = "Master password for database"
  type        = string
  sensitive   = true
}
```

## Local Values

Use locals for computed values and to avoid repetition:

```hcl
locals {
  common_tags = merge(var.tags, {
    Environment = var.environment
    ManagedBy   = "Terraform"
    Project     = var.project_name
  })

  name_prefix = "${var.project_name}-${var.environment}"
}
```

## Resource Naming and Tagging

Use consistent naming and comprehensive tagging:

```hcl
resource "aws_s3_bucket" "data" {
  bucket = "${local.name_prefix}-data-${data.aws_caller_identity.current.account_id}"

  tags = merge(local.common_tags, {
    Name    = "${local.name_prefix}-data"
    Purpose = "Application data storage"
  })
}
```

## Remote State Management

Always use remote state with locking:

```hcl
terraform {
  backend "s3" {
    bucket         = "mycompany-terraform-state"
    key            = "environments/production/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "terraform-state-lock"
  }
}
```

## Dynamic Blocks

Use dynamic blocks for variable configurations:

```hcl
resource "aws_security_group" "main" {
  name   = "${local.name_prefix}-sg"
  vpc_id = aws_vpc.main.id

  dynamic "ingress" {
    for_each = var.ingress_rules
    content {
      from_port   = ingress.value.from_port
      to_port     = ingress.value.to_port
      protocol    = ingress.value.protocol
      cidr_blocks = ingress.value.cidr_blocks
    }
  }

  tags = local.common_tags
}
```

## For Expressions

Use for_each for multiple resources:

```hcl
resource "aws_subnet" "private" {
  for_each = toset(var.availability_zones)

  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 4, index(var.availability_zones, each.value))
  availability_zone = each.value

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-private-${each.value}"
    Type = "private"
  })
}
```

## Lifecycle Management

Use lifecycle blocks to prevent resource disruption:

```hcl
resource "aws_db_instance" "main" {
  identifier     = "${local.name_prefix}-db"
  engine         = "postgres"
  instance_class = var.db_instance_class

  lifecycle {
    prevent_destroy = true
    ignore_changes  = [password, snapshot_identifier]
  }
}
```

## Security Best Practices

### Secrets Management

```hcl
resource "random_password" "db_password" {
  length  = 32
  special = true
}

resource "aws_secretsmanager_secret" "db_password" {
  name = "${local.name_prefix}-db-password"
}

resource "aws_secretsmanager_secret_version" "db_password" {
  secret_id     = aws_secretsmanager_secret.db_password.id
  secret_string = random_password.db_password.result
}
```

### Encryption

```hcl
resource "aws_kms_key" "main" {
  description         = "KMS key for encryption"
  enable_key_rotation = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "data" {
  bucket = aws_s3_bucket.data.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.main.arn
    }
  }
}
```

### IAM Least Privilege

```hcl
data "aws_iam_policy_document" "app_permissions" {
  statement {
    sid     = "S3Access"
    actions = ["s3:GetObject", "s3:PutObject"]
    resources = ["${aws_s3_bucket.data.arn}/*"]
  }
}
```

### Security Groups

Define rules separately for better management:

```hcl
resource "aws_vpc_security_group_ingress_rule" "app_https" {
  security_group_id            = aws_security_group.app.id
  from_port                    = 443
  to_port                      = 443
  ip_protocol                  = "tcp"
  referenced_security_group_id = aws_security_group.alb.id
}
```

## Testing

### Native Terraform Tests (1.6+)

```hcl
# tests/networking_test.tftest.hcl
run "validate_vpc_cidr" {
  command = plan

  assert {
    condition     = aws_vpc.main.cidr_block == "10.0.0.0/16"
    error_message = "VPC CIDR block did not match"
  }
}

run "apply_and_verify" {
  command = apply

  assert {
    condition     = output.vpc_id != ""
    error_message = "VPC ID output is empty"
  }
}
```

## Workflow

```bash
terraform init
terraform fmt -recursive
terraform validate
terraform plan -out=tfplan
terraform apply tfplan
```

## Import Blocks (Terraform 1.5+)

```hcl
import {
  to = aws_instance.example
  id = "i-1234567890abcdef0"
}
```

## Moved Blocks

Handle resource refactoring:

```hcl
moved {
  from = aws_instance.old_name
  to   = module.compute.aws_instance.new_name
}
```

## Cost Optimization

### S3 Lifecycle Policies

```hcl
resource "aws_s3_bucket_lifecycle_configuration" "data" {
  bucket = aws_s3_bucket.data.id

  rule {
    id     = "archive-old-data"
    status = "Enabled"

    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 90
      storage_class = "GLACIER_IR"
    }
  }
}
```

### Spot Instances

```hcl
resource "aws_autoscaling_group" "spot" {
  mixed_instances_policy {
    instances_distribution {
      on_demand_base_capacity                  = 1
      on_demand_percentage_above_base_capacity = 20
      spot_allocation_strategy                 = "price-capacity-optimized"
    }

    launch_template {
      launch_template_specification {
        launch_template_id = aws_launch_template.app.id
      }

      override {
        instance_type = "t3.medium"
      }
      override {
        instance_type = "t3a.medium"
      }
    }
  }
}
```

## Key Points

- Pin Terraform and provider versions explicitly
- Use provider default_tags for consistent tagging
- Organize code into reusable modules
- Use remote state with locking (S3/DynamoDB or Terraform Cloud)
- Validate variables with multiple conditions
- Use `optional()` for flexible object types
- Use `for_each` over `count` when possible
- Use lifecycle rules to prevent accidental deletion
- Never hardcode secrets - use Secrets Manager or SSM
- Enable encryption by default (KMS)
- Use OIDC for CI/CD authentication
- Write native Terraform tests
- Use TFLint and security scanners in CI/CD
