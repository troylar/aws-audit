<div align="center">

# AWS Inventory Manager

### *Snapshot, Track, Secure, and Clean Up Your AWS Environment*

[![CI](https://github.com/troylar/aws-inventory-manager/actions/workflows/ci.yml/badge.svg)](https://github.com/troylar/aws-inventory-manager/actions/workflows/ci.yml)
[![Coverage](https://codecov.io/gh/troylar/aws-inventory-manager/branch/main/graph/badge.svg)](https://codecov.io/gh/troylar/aws-inventory-manager)
[![PyPI version](https://img.shields.io/pypi/v/aws-inventory-manager.svg)](https://pypi.org/project/aws-inventory-manager/)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Inventory Snapshots** • **Configuration Drift** • **Security Scanning** • **Cost Analysis** • **Resource Cleanup** • **IaC Generation**

[Quick Start](#quick-start) • [Features](#features) • [AWS Config](#aws-config-integration) • [Documentation](#documentation)

</div>

---

## What It Does

AWS Inventory Manager captures a **point-in-time inventory** of your AWS resources, then helps you track changes, find security issues, and clean up unwanted resources.

> **Note:** "Snapshot" in this tool means an *inventory snapshot* (a catalog of what exists), not an AWS EBS or RDS snapshot. No AWS snapshots are created.

```bash
# Capture your current resource inventory
awsinv snapshot create my-baseline --regions us-east-1,us-west-2

# Track what changed since the baseline
awsinv delta --snapshot my-baseline --show-diff

# Find security issues
awsinv security scan --severity HIGH

# Remove resources created after the baseline
awsinv cleanup preview my-baseline      # See what would be deleted
awsinv cleanup execute my-baseline --confirm  # Execute cleanup
```

### Why You Need This

| Problem | Solution |
|---------|----------|
| "What changed in our account?" | Field-level configuration drift detection |
| "Are we following security best practices?" | Automated CIS Benchmark scanning |
| "Someone spun up a bunch of test resources" | Delete everything created after a baseline snapshot |
| "How much is each team spending?" | Per-inventory cost tracking with tag filtering |
| "I need to clean up a sandbox account" | Purge all resources except those with specific tags |

---

## Key Concepts

Before diving in, here's the terminology:

| Term | Meaning |
|------|---------|
| **Snapshot** | A point-in-time inventory of your AWS resources (stored in local SQLite database). Not an EBS/RDS snapshot. |
| **Inventory** | A named collection of snapshots. Use inventories to organize snapshots by environment, team, or purpose. |
| **Cleanup** | Delete resources that were created *after* a snapshot, returning to that baseline state. |
| **Purge** | Delete all resources *except* those matching protection rules. Filter by creator or date range. |
| **Query** | Search and analyze resources across snapshots using SQL or built-in filters. |

---

## Features

<table>
<tr>
<td width="33%" valign="top">

### Inventory Snapshots
- 27 AWS services, 80+ resource types
- Multi-region collection
- Tag-based filtering
- **Lambda code collection** (deployment packages)
- Lambda CLI: list, extract, show, diff
- Export to JSON/CSV/YAML
- SQLite storage with SQL queries

</td>
<td width="33%" valign="top">

### Change Tracking
- Field-level drift detection
- Before/after comparison
- Configuration + security changes
- Color-coded terminal output
- JSON export for CI/CD

</td>
<td width="33%" valign="top">

### Security Scanning
- 12+ CIS-aligned checks
- CRITICAL/HIGH/MEDIUM/LOW severity
- Public S3 buckets, open ports
- IAM credential age
- Remediation guidance

</td>
</tr>
<tr>
<td width="33%" valign="top">

### Cost Analysis
- Per-inventory cost tracking
- Date range filtering
- Service-level breakdown
- Tag-based attribution
- AWS Cost Explorer integration

</td>
<td width="33%" valign="top">

### Resource Cleanup
- **Cleanup**: Return to a snapshot baseline
- **Purge**: Delete all except protected
- **Exclusion filters**: Wildcard name/tag patterns
- Preview mode (dry-run)
- Dependency-aware deletion
- 43 deletable resource types*

<sub>*Deletion requires service-specific logic; collection supports 80+ types, deletion supports 43.</sub>

</td>
<td width="33%" valign="top">

### AWS Config Integration
- Automatic detection
- Up to 5x faster collection
- Hybrid fallback to direct API
- Per-resource source tracking
- Multi-account via Aggregators

</td>
</tr>
<tr>
<td width="33%" valign="top">

### Query & Analysis
- Raw SQL queries on resources
- Search by type, region, tags
- Tag coverage analysis
- Cross-snapshot history
- Export to JSON/CSV

</td>
<td width="33%" valign="top">

### Resource Provenance
- CloudTrail creator tracking
- `--track-creators` flag
- Enrich existing snapshots
- **List creators by snapshot**
- Web UI creator columns
- Identity type detection

</td>
<td width="33%" valign="top">

### IaC Generation (New!)
- Generate Terraform from snapshots
- AI-powered code generation
- Layer-based chunking (network → compute → etc.)
- Automatic ID → reference mapping
- `terraform validate` integration
- OpenAI-compatible API support

</td>
</tr>
</table>

---

## Prerequisites

Before installing, ensure you have:

- **Python 3.8+** (3.8, 3.9, 3.10, 3.11, 3.12, or 3.13)
- **AWS CLI configured** with credentials (`aws configure` or environment variables)
- **Sufficient IAM permissions** (see [IAM Permissions](#iam-permissions) below)

To verify your setup:
```bash
python3 --version            # Should be 3.8+ (use 'python' on some systems)
aws sts get-caller-identity  # Should return your account info
```

---

## Quick Start

### Installation

```bash
pip install aws-inventory-manager
```

Or with pipx for isolated installation:
```bash
pipx install aws-inventory-manager
```

### Your First Snapshot

```bash
# 1. Capture current state (takes 30-60 seconds depending on resource count)
awsinv snapshot create my-baseline --regions us-east-1

# 2. View what was captured
awsinv snapshot report

# Output:
# ┌─────────────────────────────────────────┐
# │ Snapshot: my-baseline                   │
# │ Resources: 127                          │
# │ Regions: us-east-1                      │
# ├─────────────────────────────────────────┤
# │ EC2 Instances:     12                   │
# │ S3 Buckets:        8                    │
# │ Lambda Functions:  23                   │
# │ IAM Roles:         45                   │
# │ ...                                     │
# └─────────────────────────────────────────┘
```

### Common Workflows

```bash
# Track changes since baseline
awsinv delta --snapshot my-baseline --show-diff

# Find security issues
awsinv security scan

# Clean up resources created after baseline
awsinv cleanup preview my-baseline      # Always preview first!
awsinv cleanup execute my-baseline --confirm

# Clean up a sandbox (keep only tagged resources)
awsinv cleanup purge --protect-tag "keep=true" --preview
awsinv cleanup purge --protect-tag "keep=true" --confirm
```

---
## Environment Variables

You can configure most CLI options via environment variables, which is useful for CI/CD pipelines or setting personal defaults.

| Variable | Description | Equivalent Flag |
|----------|-------------|-----------------|
| `AWSINV_SNAPSHOT_ID` | Default snapshot name for queries | `--snapshot` |
| `AWSINV_INVENTORY_ID` | Default inventory name | `--inventory` |
| `AWSINV_REGION` | Comma-separated regions (e.g., `us-east-1,us-west-2`) | `--regions` |
| `AWSINV_PROFILE` | AWS CLI profile to use | `--profile` |
| `AWSINV_STORAGE_PATH` | Custom path for SQLite DB and logs | `--storage-path` |
| `AWSINV_AI_ENDPOINT` | AI API endpoint for IaC generation | `--endpoint` |
| `AWSINV_AI_API_KEY` | AI API key for IaC generation | `--api-key` |
| `AWSINV_AI_MODEL` | AI model name (default: gpt-4) | `--model` |

Example:
```bash
export AWSINV_INVENTORY_ID="prod-baseline"
export AWSINV_REGION="us-east-1"

# These commands will now use the exported values automatically
awsinv snapshot create daily-snap
awsinv delta --snapshot previous-snap
```

---

## AWS Config Integration

When [AWS Config](https://aws.amazon.com/config/) is enabled, the tool automatically uses it for faster resource collection.

### Why Use AWS Config?

| Method | 500 Resources | 2000 Resources |
|--------|---------------|----------------|
| Direct API calls | ~45 seconds | ~3 minutes |
| AWS Config | ~8 seconds | ~20 seconds |

AWS Config maintains an indexed inventory of your resources. Instead of calling 27 different AWS service APIs, we query Config's pre-built index.

### How It Works

```
For each region:
  1. Check if AWS Config is enabled and recording
  2. For each resource type:
     ├─ Config supports it? → Query Config API (fast)
     └─ Config doesn't support it? → Call service API directly (Route53, WAF, etc.)
  3. Merge results into unified snapshot
```

**No configuration required.** The tool detects Config availability automatically and falls back gracefully.

### Usage

```bash
# Default behavior: Use Config when available (recommended)
awsinv snapshot create my-snapshot --regions us-east-1

# Force direct API only (skip Config, useful for debugging)
awsinv snapshot create my-snapshot --regions us-east-1 --no-config

# Multi-account via Config Aggregator
awsinv snapshot create org-snapshot --config-aggregator my-org-aggregator
```

### Source Tracking

Each resource records how it was collected:

```yaml
resources:
  - arn: "arn:aws:s3:::my-bucket"
    type: "AWS::S3::Bucket"
    name: "my-bucket"
    source: "config"        # Collected via AWS Config

  - arn: "arn:aws:route53:::hostedzone/Z123"
    type: "AWS::Route53::HostedZone"
    name: "example.com"
    source: "direct_api"    # Config doesn't support Route53
```

### Requirements

To benefit from Config integration:

1. **AWS Config enabled** in target region(s)
2. **Configuration Recorder** actively recording
3. **Resource types being recorded** (either "all supported types" or specific types)

If these aren't met, the tool falls back to direct API calls automatically.

---

## Data Storage

### Where Snapshots Are Stored

By default, all data is stored locally in a SQLite database:

```
~/.snapshots/
├── inventory.db              # SQLite database (snapshots, resources, tags)
└── audit-logs/
    └── cleanup/              # Cleanup operation audit logs
        └── 2026-01-15_cleanup.yaml
```

The SQLite database provides:
- **Fast queries**: Search across all snapshots with SQL
- **Tag analysis**: Normalized tags table for efficient filtering
- **Cross-snapshot history**: Track resources across multiple snapshots

### Changing Storage Location

```bash
# Via environment variable
export AWS_INVENTORY_STORAGE_PATH=/path/to/storage
awsinv snapshot create my-snapshot

# Via CLI flag
awsinv snapshot create my-snapshot --storage-path /path/to/storage
```

### Team Sharing

The SQLite database is a single portable file. To share across a team:

- Store `inventory.db` in a shared filesystem
- Sync via S3 or other cloud storage
- Use separate databases per environment/team

### Database Schema & Power User Queries

For advanced usage, including the full SQLite schema and complex analytical SQL queries, please see [DATABASE.md](DATABASE.md).

---

## Multi-Account Support

### Option 1: AWS Config Aggregator (Recommended)

If you have a [Config Aggregator](https://docs.aws.amazon.com/config/latest/developerguide/aggregate-data.html) set up (common with AWS Organizations):

```bash
# Query all accounts via the aggregator
awsinv snapshot create org-wide --config-aggregator my-aggregator
```

**Prerequisites:**
- Config Aggregator already configured in your management account
  - See [Setting Up an Aggregator Using the Console](https://docs.aws.amazon.com/config/latest/developerguide/setup-aggregator-console.html)
- Appropriate IAM permissions to query the aggregator (see [IAM Permissions](#iam-permissions))

### Option 2: Profile Switching

```bash
# Snapshot each account separately
awsinv snapshot create account-dev --profile dev-account
awsinv snapshot create account-prod --profile prod-account
```

### Option 3: Cross-Account Roles

Configure your AWS CLI with cross-account role assumption, then use profiles as above.

---

## IAM Permissions

The tool requires different permissions depending on which features you use. Combine the policies below based on which features you need, or attach them as separate managed policies.

> **Tip:** Start with just "Snapshot Collection" permissions. Add others only when needed.

### Snapshot Collection (Read-Only)

For basic snapshot collection, you need read access to the services you want to inventory. The easiest approach is to use the `ReadOnlyAccess` AWS managed policy, but here's a minimal custom policy:

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

### AWS Config Integration (Optional)

If you want to use AWS Config for faster collection:

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

### CloudTrail (Creator Tracking)

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

### Cost Analysis

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

### Resource Cleanup

⚠️ **Warning:** These permissions allow resource deletion. Use with extreme caution.

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

---

## Documentation

### Resource Provenance (Creator Tracking)

Track who created each resource in your AWS account using CloudTrail:

```bash
# Track creators during snapshot creation
awsinv snapshot create my-snapshot --regions us-east-1 --track-creators

# Enrich an existing snapshot with creator information
awsinv snapshot enrich-creators my-snapshot --days-back 90
```

This adds three tags to each resource:
- `_created_by`: The IAM role/user ARN that created the resource
- `_created_by_type`: The identity type (AssumedRole, IAMUser, Root, AWSService)
- `_created_at`: When the resource was created (from CloudTrail)

**Use Cases:**
- Identify resources created by automation vs. manual creation
- Track resources created by specific CI/CD pipelines
- Find resources created by former team members
- Audit resource creation by identity type

**List Creators:**
View a summary of all resource creators for a snapshot:

```bash
# Show creators summary for active snapshot
awsinv snapshot creators

# Show creators for specific snapshot
awsinv snapshot creators my-snapshot

# Show detailed resources for each creator
awsinv snapshot creators --detailed

# Export to JSON or CSV
awsinv snapshot creators --export creators.json
awsinv snapshot creators --export creators.csv
```

**Output includes:**
- Unique creators count
- Resources with/without creator info
- Table with creator name, type, resource count, and top resource types
- With `--detailed`: individual resources grouped by type for each creator

**Web UI Support:**
The Resource Explorer includes three creator columns (enable via column selector):
- "Created By" - Shows the creator ARN (truncated for readability)
- "Creator Type" - Color-coded badge (AssumedRole=blue, IAMUser=green, Root=red, AWSService=orange)
- "Creation Time" - When the resource was created

> **Note:** CloudTrail has a 90-day lookup window. Resources created more than 90 days ago won't have creator information. The `--days-back` option lets you customize the lookup period (default: 90).

---

### Lambda Code Management

Work with Lambda function deployment code stored in snapshots:

```bash
# List all Lambda functions with code info
awsinv lambda list [--snapshot my-snapshot]

# Extract Lambda code to disk
awsinv lambda extract my-function                    # Single function
awsinv lambda extract --all --output ./lambda-code  # All functions

# View code with syntax highlighting
awsinv lambda show my-function
awsinv lambda show my-function --handler           # Just the handler file

# Compare code between snapshots
awsinv lambda diff my-function --snapshot1 snap-before --snapshot2 snap-after

# Fetch code for existing snapshots (without recreating)
awsinv lambda fetch my-snapshot                    # Fetch missing code
awsinv lambda fetch my-snapshot --function my-func # Specific function only
awsinv lambda fetch my-snapshot --force            # Re-fetch all code
awsinv lambda fetch my-snapshot --max-size 50      # Store inline up to 50MB
```

**Code Storage Options:**

When creating snapshots, control how Lambda code is stored:

```bash
# Default: Store code inline up to 10MB, hash-only for larger
awsinv snapshot create my-snap --regions us-east-1

# Store code inline up to 50MB
awsinv snapshot create my-snap --regions us-east-1 --lambda-code-max-size 50

# Store all code externally (none inline)
awsinv snapshot create my-snap --regions us-east-1 --lambda-code-max-size 0

# Store all code inline regardless of size
awsinv snapshot create my-snap --regions us-east-1 --lambda-code-max-size -1
```

Large packages are stored to `~/.snapshots/lambda-code/<snapshot>/` and automatically loaded when needed.

---

### IaC Generation (Terraform)

Generate Terraform code from your inventory snapshots using AI:

```bash
# Set up AI credentials (OpenAI example)
export AWSINV_AI_ENDPOINT="https://api.openai.com/v1"
export AWSINV_AI_API_KEY="sk-..."
export AWSINV_AI_MODEL="gpt-4"

# Generate Terraform from a snapshot
awsinv generate terraform my-snapshot

# Specify output directory
awsinv generate terraform my-snapshot --output ./infrastructure

# Dry run (show what would be generated)
awsinv generate terraform my-snapshot --dry-run

# Use different model/endpoint
awsinv generate terraform my-snapshot \
  --endpoint "http://localhost:11434/v1" \
  --model "llama3"
```

**How It Works:**

```mermaid
flowchart TD
    subgraph Input
        START([🚀 START<br/>snapshot_name])
    end

    subgraph Preparation ["📋 Preparation Phase"]
        PARSE[/"📦 parse_inventory<br/>Load snapshot & resources"/]
        MAP[/"🗺️ build_resource_map<br/>vpc-123 → aws_vpc.main"/]
        CAT[/"📊 categorize_layers<br/>Group by layer order"/]
        LAMBDA[/"λ extract_lambda<br/>Save code to files"/]
    end

    subgraph Generation ["🧠 Generation Loop"]
        GEN[/"🤖 generate_layer<br/>Call AI → Write .tf"/]
        CHECK{{"❓ More layers?"}}
    end

    subgraph Validation ["✅ Validation Phase"]
        VALIDATE[/"✅ validate_terraform<br/>terraform init & validate"/]
    end

    subgraph Output
        DONE([🏁 END<br/>GenerationResult])
    end

    START --> PARSE
    PARSE --> MAP
    MAP --> CAT
    CAT --> LAMBDA
    LAMBDA --> GEN
    GEN --> CHECK
    CHECK -->|"Yes"| GEN
    CHECK -->|"No"| VALIDATE
    VALIDATE --> DONE

    style START fill:#22c55e,stroke:#16a34a,color:#fff
    style DONE fill:#22c55e,stroke:#16a34a,color:#fff
    style GEN fill:#3b82f6,stroke:#2563eb,color:#fff
    style CHECK fill:#f59e0b,stroke:#d97706,color:#fff
    style VALIDATE fill:#8b5cf6,stroke:#7c3aed,color:#fff
```

**Layer Order** (generated in dependency sequence):

| Order | Layer | Resources |
|-------|-------|-----------|
| 1 | 🌐 Network | VPCs, Subnets, Route Tables, Gateways |
| 2 | 🛡️ Security | Security Groups, NACLs, WAF, KMS |
| 3 | 🔑 IAM | Roles, Policies, Instance Profiles |
| 4 | 💾 Data | RDS, DynamoDB, ElastiCache |
| 5 | 📁 Storage | S3, EFS |
| 6 | 💻 Compute | EC2, Lambda, ECS, EKS |
| 7 | ⚖️ LoadBalancing | ALB, NLB, Target Groups |
| 8 | 📱 Application | API Gateway, AppRunner |
| 9 | 📨 Messaging | SQS, SNS, EventBridge |
| 10 | 📊 Monitoring | CloudWatch, CloudTrail |
| 11 | 🌍 DNS | Route53, CloudFront |

**Output Structure:**
```
./terraform/
├── main.tf              # Provider configuration
├── variables.tf         # Input variables
├── outputs.tf           # Output values
├── layer_01_network.tf  # VPCs, subnets, gateways
├── layer_02_security.tf # Security groups, ACLs
├── layer_03_iam.tf      # Roles, policies
├── layer_04_data.tf     # RDS, DynamoDB
├── layer_05_storage.tf  # S3, EFS
├── layer_06_compute.tf  # EC2, Lambda, ECS
└── ...
```

**Supported AI Providers:**
- OpenAI (GPT-4, GPT-4 Turbo)
- Azure OpenAI
- Ollama (local models)
- LM Studio
- Any OpenAI-compatible API

> **Note:** IaC generation requires the `langgraph` optional dependency: `pip install aws-inventory-manager[generate]`

---

### Resource Cleanup

The `cleanup` command has two modes:

**Execute Mode** - Delete resources created *after* a baseline snapshot:
```bash
# Preview what would be deleted
awsinv cleanup preview my-baseline

# Execute (requires confirmation)
awsinv cleanup execute my-baseline --confirm
```

**Purge Mode** - Delete *all* resources except those matching protection rules:
```bash
# Preview what would be deleted (everything except keep=true tagged resources)
awsinv cleanup purge --protect-tag "keep=true" --preview

# Execute
awsinv cleanup purge --protect-tag "keep=true" --confirm
```

**Purge by Creator/Date** - Delete resources created by specific users or within date ranges:
```bash
# First, enrich a snapshot with creator information from CloudTrail
awsinv snapshot enrich-creators my-snapshot

# Preview resources created by a specific user
awsinv cleanup purge --from-snapshot my-snapshot --created-by "john.doe" --preview

# Preview resources created by a specific role
awsinv cleanup purge --from-snapshot my-snapshot --created-by "AWSReservedSSO_Developer" --preview

# Delete resources created after a specific date
awsinv cleanup purge --from-snapshot my-snapshot --created-after "2025-01-01" --confirm

# Delete resources created within a date range
awsinv cleanup purge --from-snapshot my-snapshot --created-after "2025-01-01" --created-before "2025-01-15" --confirm

# Combine creator and date filters
awsinv cleanup purge --from-snapshot my-snapshot --created-by "john" --created-after "2025-01-10" --preview
```

**Exclusion Filters** - Protect specific resources by name or tag pattern (supports wildcards):
```bash
# Exclude resources by name pattern (wildcards: * and ?)
awsinv cleanup purge --protect-tag "env=dev" --exclude-name "*-prod-*" --preview
awsinv cleanup purge --protect-tag "env=dev" -x "critical-*" -x "important-*" --preview

# Exclude resources by tag pattern
awsinv cleanup purge --protect-tag "env=dev" --exclude-tag "protected=yes" --preview
awsinv cleanup purge --protect-tag "env=dev" --exclude-tag "Name=*production*" --preview

# Exclude by tag key only (any value matches)
awsinv cleanup purge --protect-tag "env=dev" --exclude-tag "do-not-delete=*" --preview

# Combine name and tag exclusions (OR logic - excluded if ANY match)
awsinv cleanup purge --protect-tag "env=dev" \
  --exclude-name "*-prod-*" \
  --exclude-name "*-staging-*" \
  --exclude-tag "critical=true" \
  --preview
```

> **Note:** Exclusion filters use `*` (any characters) and `?` (single character) wildcards. Matching is case-insensitive.

> **Note:** Creator/date filters require `--from-snapshot` with an enriched snapshot. The `--created-by` option does substring matching on the creator ARN.

> **Note:** `cleanup execute` compares to a snapshot and deletes newer resources. `cleanup purge` ignores snapshots and deletes everything except protected resources.

### Protection Rules

Prevent accidental deletion of important resources:

```bash
# Protect by tag (OR logic - any match protects)
awsinv cleanup preview my-snapshot --protect-tag "env=prod" --protect-tag "keep=true"

# Filter to specific resource type (only delete this type)
awsinv cleanup preview my-snapshot --type AWS::EC2::Instance

# Use a config file for complex rules
awsinv cleanup preview my-snapshot --config .awsinv-cleanup.yaml
```

Example `.awsinv-cleanup.yaml`:
```yaml
# Protection Rules Configuration
# Resources matching ANY rule are protected from deletion

protection:
  # Tag-based protection (OR logic - any matching tag protects)
  tags:
    - key: env
      value: prod         # Protect production resources
    - key: keep
      value: "true"       # Protect explicitly marked resources
    - key: Owner
      value: "*"          # Protect anything with an Owner tag (any value)

  # Type-based protection
  types:
    - AWS::IAM::Role      # Never delete IAM roles
    - AWS::IAM::User      # Never delete IAM users
    - AWS::S3::Bucket     # Never delete S3 buckets

  # Age-based protection
  age_days_minimum: 7     # Keep resources older than 7 days
```

**Config file schema:**
| Field | Type | Description |
|-------|------|-------------|
| `protection.tags[]` | Array | Tag key/value pairs. `value: "*"` matches any value. |
| `protection.types[]` | Array | Full resource type names (e.g., `AWS::EC2::Instance`) |
| `protection.age_days_minimum` | Integer | Protect resources older than N days |

### Safety Features

- **Preview mode**: Always see what would happen before execution
- **Confirmation required**: `--confirm` flag mandatory for destructive operations
- **Dependency ordering**: Deletes in correct order (instances before VPCs, etc.)
- **Audit logging**: Every deletion logged to `~/.snapshots/audit-logs/`

### Deletion Behavior Notes

Some resources have special deletion behavior:

| Resource | Behavior |
|----------|----------|
| **KMS Keys** | Scheduled for deletion (minimum 7-day wait, not immediate) |
| **S3 Buckets** | Automatically emptied before deletion (including versioned objects) |
| **IAM Roles** | Attached policies detached, instance profiles removed first |
| **Route53 Zones** | All records deleted except NS/SOA before zone deletion |

---

## Supported Resource Types

<details>
<summary><b>Full list of 80+ supported resource types</b></summary>

### Compute
| Service | Resource Types |
|---------|---------------|
| EC2 | Instances, Volumes, VPCs, Subnets, Security Groups, ENIs, Internet Gateways, NAT Gateways, Route Tables, Key Pairs, Elastic IPs, VPC Endpoints |
| Lambda | Functions (with deployment code), Layers (with code), Event Source Mappings |
| ECS | Clusters, Services, Task Definitions |
| EKS | Clusters, Node Groups, Fargate Profiles |

### Storage
| Service | Resource Types |
|---------|---------------|
| S3 | Buckets (with policies, encryption, versioning config) |
| EBS | Volumes, Snapshots |
| EFS | File Systems, Mount Targets |

### Database
| Service | Resource Types |
|---------|---------------|
| RDS | DB Instances, DB Clusters, DB Subnet Groups |
| DynamoDB | Tables |
| ElastiCache | Clusters, Replication Groups |

### Networking
| Service | Resource Types |
|---------|---------------|
| ELB | Application Load Balancers, Network Load Balancers, Classic Load Balancers, Target Groups |
| Route53 | Hosted Zones, Record Sets |
| API Gateway | REST APIs, HTTP APIs, Stages |

### Security & Identity
| Service | Resource Types |
|---------|---------------|
| IAM | Users, Roles, Groups, Policies, Instance Profiles |
| KMS | Keys, Aliases |
| Secrets Manager | Secrets |
| WAF | WebACLs, Rule Groups, IP Sets |

### Management & Monitoring
| Service | Resource Types |
|---------|---------------|
| CloudWatch | Alarms, Log Groups, Dashboards |
| CloudFormation | Stacks |
| EventBridge | Rules, Event Buses |
| SSM | Parameters |

### Developer Tools
| Service | Resource Types |
|---------|---------------|
| CodePipeline | Pipelines |
| CodeBuild | Projects |
| Step Functions | State Machines |

### Messaging
| Service | Resource Types |
|---------|---------------|
| SNS | Topics, Subscriptions |
| SQS | Queues |

### Backup
| Service | Resource Types |
|---------|---------------|
| AWS Backup | Backup Plans, Backup Vaults |

</details>

---

## Command Reference

```bash
# ─────────────────────────────────────────────────────────────
# SNAPSHOTS
# ─────────────────────────────────────────────────────────────
awsinv snapshot create <name> --regions <region1,region2>
    [--use-config/--no-config]        # AWS Config usage (default: disabled)
    [--config-aggregator <name>]      # Config Aggregator for multi-account
    [--resource-types <svc1,svc2>]    # Filter services (e.g., ec2,s3,lambda)
    [--include-tags <key=value>]      # Only include tagged resources
    [--inventory <name>]              # Assign to inventory group
    [--track-creators]                # Tag resources with CloudTrail creator info
    [--created-by-role <role>]        # Only include resources created by role
    [--lambda-code-max-size <MB>]     # Max Lambda code size to store inline (default: 10)

awsinv snapshot list                  # List all snapshots
awsinv snapshot report                # Summary of current/specified snapshot
    [--snapshot <name>]
    [--detailed]                      # Show all resources
    [--export <file.json|csv>]

awsinv snapshot enrich-creators <name>  # Add creator info to existing snapshot
    [--days-back <days>]              # CloudTrail lookup period (default: 90)

awsinv snapshot creators              # List resource creators for a snapshot
    [<snapshot-name>]                 # Specific snapshot (default: active)
    [--detailed]                      # Show individual resources per creator
    [--export <file.json|csv>]        # Export to JSON or CSV

# ─────────────────────────────────────────────────────────────
# ANALYSIS
# ─────────────────────────────────────────────────────────────
awsinv delta                          # Changes since active snapshot
    [--snapshot <name>]               # Compare to specific snapshot
    [--show-diff]                     # Show field-level changes

awsinv security scan                  # Run security checks
    [--severity <CRITICAL|HIGH|MEDIUM|LOW>]
    [--export <file.json>]

awsinv cost                           # Cost analysis
    [--start-date YYYY-MM-DD]
    [--end-date YYYY-MM-DD]
    [--show-services]

# ─────────────────────────────────────────────────────────────
# RESOURCE CLEANUP
# ─────────────────────────────────────────────────────────────
# Cleanup: Delete resources created AFTER a snapshot
awsinv cleanup preview <snapshot>     # Dry-run (safe)
awsinv cleanup execute <snapshot> --confirm

# Purge: Delete ALL resources EXCEPT protected ones
awsinv cleanup purge --protect-tag <key=value> --preview
awsinv cleanup purge --protect-tag <key=value> --confirm

# Purge exclusion filters (wildcards: * and ?):
    [--exclude-name <pattern>]        # Exclude by name pattern (repeatable)
    [-x <pattern>]                    # Short form of --exclude-name
    [--exclude-tag <key=value>]       # Exclude by tag pattern (repeatable)

# Common options for both:
    [--type <AWS::Service::Type>]     # Filter by resource type
    [--region <region>]               # Filter by region
    [--protect-tag <key=value>]       # Protect matching resources (repeatable)
    [--config <path>]                 # Protection rules file
    [-y, --yes]                       # Skip interactive prompts

# ─────────────────────────────────────────────────────────────
# LAMBDA CODE
# ─────────────────────────────────────────────────────────────
awsinv lambda list                    # List Lambda functions with code info
    [--snapshot <name>]               # Specific snapshot (default: active)

awsinv lambda extract <function>      # Extract code to disk
    [--snapshot <name>]
    [--output <dir>]                  # Output directory
    [--all]                           # Extract all functions

awsinv lambda show <function>         # View code with syntax highlighting
    [--snapshot <name>]
    [--handler]                       # Show only handler file

awsinv lambda diff <function>         # Compare code between snapshots
    --snapshot1 <name>
    --snapshot2 <name>

awsinv lambda fetch <snapshot>        # Fetch code for existing snapshot
    [--function <name>]               # Specific function only
    [--max-size <MB>]                 # Max inline size (default: 50)
    [--force]                         # Re-fetch even if code exists
    [--profile <name>]                # AWS profile

# ─────────────────────────────────────────────────────────────
# QUERY & ANALYSIS
# ─────────────────────────────────────────────────────────────
awsinv query sql "<SQL>"              # Run raw SQL query
    [--format table|json|csv]

awsinv query resources                # Search resources
    [--type <AWS::Service::Type>]     # Filter by type
    [--region <region>]               # Filter by region
    [--tag <Key=Value>]               # Filter by tag
    [--snapshot <name>]               # Limit to snapshot
    [--limit <n>]                     # Max results

awsinv query history <arn>            # Resource history across snapshots

awsinv query stats                    # Resource statistics
    [--snapshot <name>]               # Specific snapshot
    [--group-by type|region|service]  # Grouping

awsinv query diff <snap1> <snap2>     # Compare two snapshots
    [--type <AWS::Service::Type>]

# Example queries:
awsinv query sql "SELECT resource_type, COUNT(*) FROM resources GROUP BY resource_type"
awsinv query resources --type "AWS::S3::Bucket" --tag "Environment=prod"
awsinv query stats --group-by region

# ─────────────────────────────────────────────────────────────
# IAC GENERATION
# ─────────────────────────────────────────────────────────────
awsinv generate terraform <snapshot>  # Generate Terraform from snapshot
    [--output <dir>]                  # Output directory (default: ./terraform)
    [--endpoint <url>]                # AI API endpoint
    [--api-key <key>]                 # AI API key
    [--model <name>]                  # AI model (default: gpt-4)
    [--dry-run]                       # Show what would be generated
    [--verbose]                       # Show detailed progress

# ─────────────────────────────────────────────────────────────
# GLOBAL OPTIONS
# ─────────────────────────────────────────────────────────────
--profile <aws-profile>               # AWS CLI profile to use
--storage-path <path>                 # Custom storage location
--help                                # Show help for any command
```

---

## Use Cases

### Development Environment Reset

> ⚠️ **Warning:** Only use this in dedicated development/sandbox accounts. Never run cleanup commands in production without extensive testing and protection rules.

```bash
# Morning: Capture clean state
awsinv snapshot create morning-baseline --regions us-east-1

# Evening: Clean up everything created during the day
awsinv cleanup preview morning-baseline   # Always preview first!
awsinv cleanup execute morning-baseline --confirm
```

### Sandbox Account Cleanup

> ⚠️ **Warning:** Purge mode deletes ALL resources except protected ones. Triple-check your protection rules before executing.

```bash
# Tag your permanent infrastructure with "baseline=true"
# Then periodically purge everything else

awsinv cleanup purge --protect-tag "baseline=true" --preview
# Review the preview output carefully!
awsinv cleanup purge --protect-tag "baseline=true" --confirm
```

### Pre/Post Deployment Comparison
```bash
# Before deploy
awsinv snapshot create pre-deploy-v2.3 --regions us-east-1,us-west-2

# Deploy your changes...

# After deploy - see exactly what changed
awsinv delta --snapshot pre-deploy-v2.3 --show-diff
```

### Security Audit
```bash
# Weekly security scan
awsinv snapshot create weekly-audit --regions us-east-1
awsinv security scan --export security-report-$(date +%Y%m%d).json
```

### Cost Attribution by Team
```bash
# Snapshot resources per team
awsinv snapshot create team-platform --include-tags "team=platform"
awsinv snapshot create team-data --include-tags "team=data"

# Compare costs
awsinv cost --snapshot team-platform
awsinv cost --snapshot team-data
```

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                   AWS Inventory Manager                       │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  CLI Commands                                                 │
│  ┌─────────┐ ┌───────┐ ┌──────────┐ ┌──────┐ ┌─────────┐     │
│  │snapshot │ │ delta │ │ security │ │ cost │ │ cleanup │     │
│  └────┬────┘ └───┬───┘ └────┬─────┘ └──┬───┘ └────┬────┘     │
│       │          │          │          │          │           │
│  ┌────┴──────────┴──────────┴──────────┴──────────┴────┐     │
│  │                     generate                         │     │
│  │        (AI-powered Terraform/CDK generation)        │     │
│  └──────────────────────────────────────────────────────┘     │
│                                                               │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  Collection Layer                                             │
│  ┌────────────────────────┐  ┌────────────────────────────┐  │
│  │     AWS Config API     │  │     Direct Service APIs    │  │
│  │  (auto-detected, fast) │  │  (fallback, 27 collectors) │  │
│  └────────────────────────┘  └────────────────────────────┘  │
│                                                               │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  Analysis & Generation Engines                                │
│  • Configuration Differ (field-level change detection)       │
│  • Security Scanner (CIS Benchmark checks)                   │
│  • Cost Analyzer (AWS Cost Explorer)                         │
│  • Dependency Resolver (deletion ordering)                   │
│  • IaC Generator (LangGraph + OpenAI-compatible APIs)        │
│                                                               │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  Storage: ~/.snapshots/                                       │
│  • inventory.db         (SQLite: snapshots, resources, tags) │
│  • audit-logs/**/*.yaml (cleanup operation logs)             │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

---

## Development

```bash
# Clone and install
git clone https://github.com/troylar/aws-inventory-manager.git
cd aws-inventory-manager
pip install -e ".[dev]"

# Run tests
invoke test              # All tests with coverage
invoke test-unit         # Unit tests only (faster)

# Code quality
invoke quality           # Lint + typecheck
invoke quality --fix     # Auto-fix issues

# Build
invoke build             # Build distributable package
```

**Test Coverage:** 2080+ tests, 61% overall coverage. Cleanup module: 98%+ coverage.

---

## Troubleshooting

### Common Issues

#### "AccessDenied" or "UnauthorizedOperation" errors

**Problem:** The tool returns permission errors during snapshot collection.

**Solution:** Ensure your IAM user/role has the required permissions. See [IAM Permissions](#iam-permissions) for the minimum required policies.

```bash
# Verify your current identity
aws sts get-caller-identity

# Test if you have basic access
aws ec2 describe-instances --region us-east-1
```

#### Snapshot takes a long time

**Problem:** Creating a snapshot takes several minutes.

**Solutions:**
1. **Enable AWS Config** for faster collection (up to 5x faster). The tool detects it automatically.
2. **Limit regions:** Only scan regions you use with `--regions us-east-1,us-west-2`
3. **Limit resource types:** Filter to specific services with `--resource-types ec2,s3,lambda`

```bash
# Faster: Only scan what you need
awsinv snapshot create quick-snap --regions us-east-1 --resource-types ec2,lambda
```

#### "No resources found" in snapshot

**Problem:** Snapshot completes but shows 0 resources.

**Possible causes:**
1. **Wrong region:** You may be scanning a region with no resources. Check with `aws ec2 describe-instances --region <region>`
2. **Tag filtering:** If you used `--include-tags`, ensure resources have those tags
3. **Permission issues:** Some describe APIs may silently return empty results instead of errors

#### Config Aggregator not working

**Problem:** `--config-aggregator` flag doesn't return cross-account resources.

**Solutions:**
1. Verify the aggregator exists: `aws configservice describe-configuration-aggregators`
2. Ensure you have `config:SelectAggregateResourceConfig` permission
3. Check that source accounts are properly linked in the aggregator
4. Run from the aggregator's account/region (typically management account)

#### Cleanup preview shows unexpected resources

**Problem:** The cleanup preview shows resources you didn't expect to be deleted.

**Explanation:** Cleanup deletes resources that exist now but didn't exist in the snapshot. This includes:
- Resources created after the snapshot
- Resources in regions not included in the original snapshot
- AWS-managed resources that get auto-created

**Solutions:**
1. Use `--protect-tag` to protect resources by tag
2. Use `--type` to limit to specific resource types
3. Create a more comprehensive baseline snapshot

#### Rate limiting / API throttling

**Problem:** Errors like "Rate exceeded" or "Throttling" during snapshot.

**Explanation:** The tool includes built-in retry logic with exponential backoff for AWS API rate limits. Most throttling is handled automatically.

**If you still see issues:**
1. Use `--no-config` to skip Config detection (reduces API calls)
2. Limit regions with `--regions`
3. Limit resource types with `--resource-types`
4. For very large accounts, consider running during off-peak hours

#### Large accounts (50k+ resources)

**Problem:** Scanning accounts with tens of thousands of resources.

**Considerations:**
- **Memory:** Snapshot data is held in memory during collection; very large accounts may need 2-4GB RAM
- **Database size:** SQLite database grows with resources but handles large datasets efficiently
- **Time:** Direct API collection may take 10-15 minutes; AWS Config reduces this significantly
- **Recommendation:** Use AWS Config + limit to specific regions/types for large accounts

### Frequently Asked Questions

#### Q: Does this create actual AWS snapshots (EBS, RDS)?

**No.** "Snapshot" in this tool means an *inventory snapshot* — a catalog of what resources exist. It does not create EBS snapshots, RDS snapshots, or any AWS resources. All data is stored locally in a SQLite database.

#### Q: Is my AWS data sent anywhere?

**No.** All data stays local. The tool only makes read API calls to AWS (and delete calls if you use cleanup). All data is stored in a SQLite database at `~/.snapshots/inventory.db` on your local machine.

#### Q: Can I use this with AWS Organizations?

**Yes.** Use one of these approaches:
1. **Config Aggregator:** Query all accounts from your management account with `--config-aggregator`
2. **Profile switching:** Create snapshots per account using `--profile`
3. **Cross-account roles:** Configure role assumption in AWS CLI profiles

#### Q: What happens if AWS Config is only partially enabled?

The tool handles partial Config coverage gracefully:
- **Region has Config:** Uses Config for supported types, direct API for others
- **Region lacks Config:** Falls back to direct API for all types
- **Type not recorded:** Falls back to direct API for that specific type

You can see which method was used per resource via the `source` field in snapshots.

#### Q: How do I undo a cleanup operation?

**You can't.** Deleted resources are permanently deleted. Always:
1. Use `cleanup preview` first
2. Review the output carefully
3. Consider creating a fresh snapshot before cleanup
4. Use `--protect-tag` to safeguard important resources

#### Q: Can I schedule automatic snapshots?

The tool itself doesn't include scheduling, but you can easily add it:

```bash
# Cron example (daily at midnight)
0 0 * * * /usr/local/bin/awsinv snapshot create daily-$(date +\%Y\%m\%d) --regions us-east-1

# Or use AWS EventBridge + Lambda to trigger from within AWS
```

#### Q: Where should I run this tool?

The tool works anywhere with Python and AWS credentials:

| Environment | Pros | Cons |
|-------------|------|------|
| **Local laptop** | Easy setup, interactive preview | Credentials on laptop, network latency |
| **EC2 with instance role** | No credential management, low latency | Snapshots stored on instance (back up!) |
| **CI/CD pipeline** | Automated, auditable | Credential setup, snapshot storage strategy needed |
| **CloudShell** | Zero setup, in-browser | Session timeouts, ephemeral storage |

For team use, consider storing snapshots in a shared location (see [Data Storage](#data-storage)).

#### Q: Why does cleanup delete my VPC?

When you run cleanup execute against a baseline, the tool deletes resources created after that baseline. If the VPC was created after your snapshot, it will be marked for deletion.

**Best practice:** Always include networking infrastructure in your baseline snapshot, or protect it with tags:

```bash
awsinv cleanup execute my-baseline --protect-tag "layer=network" --confirm
```

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Run tests: `invoke test`
4. Run quality checks: `invoke quality`
5. Submit a pull request

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

---

## License

MIT License - see [LICENSE](LICENSE)

---

## Support

- **Issues:** [GitHub Issues](https://github.com/troylar/aws-inventory-manager/issues)
- **Discussions:** [GitHub Discussions](https://github.com/troylar/aws-inventory-manager/discussions)

---

<div align="center">

**Built for AWS practitioners who need visibility and control**

[![Star on GitHub](https://img.shields.io/github/stars/troylar/aws-inventory-manager?style=social)](https://github.com/troylar/aws-inventory-manager)

Version 0.22.0 • Python 3.8 - 3.13

</div>
