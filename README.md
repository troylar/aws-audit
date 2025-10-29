<div align="center">

# 📦 AWS Inventory Manager

**Track, snapshot, and manage your AWS resources with cost analysis**

[![CI](https://github.com/troylar/aws-inventory-manager/actions/workflows/ci.yml/badge.svg)](https://github.com/troylar/aws-inventory-manager/actions/workflows/ci.yml)
[![Coverage](https://codecov.io/gh/troylar/aws-inventory-manager/branch/main/graph/badge.svg)](https://codecov.io/gh/troylar/aws-inventory-manager)
[![PyPI version](https://img.shields.io/pypi/v/aws-inventory-manager.svg)](https://pypi.org/project/aws-inventory-manager/)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Python CLI tool that captures point-in-time snapshots of AWS resources organized by inventory, tracks resource deltas over time, analyzes costs per inventory, and provides restoration capabilities.

</div>

---

## Features

- **📦 Inventory Management**: Organize snapshots into named inventories with optional tag-based filters
- **📸 Resource Snapshots**: Capture complete inventory of AWS resources across multiple regions
- **🔄 Delta Tracking**: Identify resources added, modified, or removed since a snapshot
- **💰 Cost Analysis**: Analyze costs for resources within a specific inventory
- **🔧 Resource Restoration**: Remove resources added since a snapshot to return to that state
- **🏷️ Filtered Snapshots**: Create snapshots filtered by tags for specific teams or environments
- **🔀 Multi-Account Support**: Manage inventories across multiple AWS accounts
- **📊 Snapshot Management**: Manage multiple snapshots per inventory with active snapshot tracking

## Quick Start

### Installation

```bash
# Install from PyPI
pip install aws-inventory-manager

# Or install from source
git clone https://github.com/troylar/aws-inventory-manager.git
cd aws-inventory-manager
pip install -e .
```

### Prerequisites

- Python 3.8 or higher
- AWS CLI configured with credentials
- IAM permissions for resource read/write operations

### Getting Started in 5 Minutes

Follow these steps for a complete walkthrough from setup to cost analysis:

**1. Create an inventory** (a named collection for organizing snapshots)
```bash
awsinv inventory create prod-baseline --description "Production baseline resources"
```

**2. Take your first snapshot** (capture current AWS resources)
```bash
awsinv snapshot create initial --regions us-east-1 --inventory prod-baseline
```
This captures all resources in `us-east-1` and stores them in the `prod-baseline` inventory.

**3. Make changes to your AWS environment** (optional)
- Deploy new resources, update configurations, etc.
- Then take another snapshot to track what changed

**4. Compare snapshots** (see what changed)
```bash
awsinv delta --snapshot initial --inventory prod-baseline
```
This shows all resources added, removed, or modified since the `initial` snapshot.

**5. Analyze costs**
```bash
# Costs since snapshot was created
awsinv cost --snapshot initial --inventory prod-baseline

# Costs for specific date range
awsinv cost --snapshot initial --inventory prod-baseline \
  --start-date 2025-01-01 --end-date 2025-01-31
```

**6. List your resources**
```bash
# List all inventories
awsinv inventory list

# List snapshots in your inventory
awsinv snapshot list --inventory prod-baseline

# Show snapshot details
awsinv snapshot show initial --inventory prod-baseline
```

**Advanced: Use AWS profiles and tag filtering**
```bash
# Use a specific AWS profile
awsinv --profile production snapshot create initial --regions us-east-1 --inventory prod-baseline

# Filter snapshot by tags (only include resources with specific tags)
awsinv snapshot create prod-only --regions us-east-1 \
  --include-tags Environment=production,Team=platform

# Exclude resources with certain tags
awsinv snapshot create non-dev --regions us-east-1 \
  --exclude-tags Environment=development
```

That's it! You're now tracking AWS resources, comparing changes, and analyzing costs.

### Configuration

The tool stores snapshots in `~/.snapshots` by default. You can customize this using:

**Environment Variable:**
```bash
export AWS_INVENTORY_STORAGE_PATH=/path/to/snapshots
```

**CLI Parameter** (highest priority):
```bash
awsinv --storage-path /custom/path inventory list
```

**Precedence:** CLI parameter > Environment variable > Default (`~/.snapshots`)

### Basic Usage

```bash
# Create a named inventory for organizing snapshots
awsinv inventory create infrastructure \
  --description "Core infrastructure resources"

# Create a filtered inventory for a specific team
awsinv inventory create team-alpha \
  --description "Team Alpha resources" \
  --include-tags "Team=Alpha"

# Take a snapshot (automatically uses 'default' inventory if none specified)
awsinv snapshot create

# Take a snapshot within a specific inventory
awsinv snapshot create --inventory infrastructure

# List all inventories
awsinv inventory list

# View what's changed since the snapshot
awsinv delta

# View delta for specific inventory
awsinv delta --inventory team-alpha

# Analyze costs for a specific inventory
awsinv cost --inventory infrastructure

# Analyze costs for team inventory
awsinv cost --inventory team-alpha

# List all snapshots
awsinv snapshot list

# Migrate legacy snapshots to inventory structure
awsinv inventory migrate
```

## Use Cases

### Multi-Account Resource Management
Organize snapshots by AWS account and purpose. Track costs per account.

```bash
# Create inventory for core infrastructure account
awsinv inventory create infrastructure \
  --description "Core infrastructure resources"

# Take snapshot
awsinv snapshot create --inventory infrastructure

# Analyze costs for this inventory
awsinv cost --inventory infrastructure
```

### Team-Based Resource Tracking
Create filtered inventories for different teams to track their resources and costs independently.

```bash
# Create team-specific inventories with tag filters
awsinv inventory create team-alpha \
  --include-tags "Team=Alpha" \
  --description "Team Alpha resources"

awsinv inventory create team-beta \
  --include-tags "Team=Beta" \
  --description "Team Beta resources"

# Take filtered snapshots for each team
awsinv snapshot create --inventory team-alpha
awsinv snapshot create --inventory team-beta

# Analyze costs per team
awsinv cost --inventory team-alpha
awsinv cost --inventory team-beta
```

### Environment Isolation
Separate production, staging, and development resources for independent tracking.

```bash
# Create environment-specific inventories
awsinv inventory create production \
  --include-tags "Environment=production"

awsinv inventory create staging \
  --include-tags "Environment=staging"

# Track changes for each environment
awsinv delta --inventory production
awsinv delta --inventory staging

# Analyze costs per environment
awsinv cost --inventory production
awsinv cost --inventory staging
```

## Documentation

For complete documentation including installation guide, command reference, usage examples, and best practices, run:

```bash
awsinv --help
awsinv quickstart
```

## Supported AWS Services

The tool captures resources from **25 AWS services**:

- **IAM**: Roles, Users, Groups, Customer-Managed Policies
- **Lambda**: Functions, Layers
- **S3**: Buckets (with versioning, encryption metadata)
- **EC2**: Instances, Volumes, VPCs, Security Groups, Subnets, VPC Endpoints (Interface & Gateway)
- **RDS**: DB Instances, DB Clusters (Aurora)
- **CloudWatch**: Alarms (Metric & Composite), Log Groups
- **SNS**: Topics
- **SQS**: Queues
- **DynamoDB**: Tables
- **ELB**: Load Balancers (Classic ELB, ALB, NLB, GWLB)
- **CloudFormation**: Stacks
- **API Gateway**: REST APIs, HTTP APIs, WebSocket APIs
- **EventBridge**: Event Buses, Event Rules
- **Secrets Manager**: Secrets (metadata only, values excluded)
- **KMS**: Customer-Managed Keys (with rotation status)
- **Systems Manager**: Parameter Store Parameters, SSM Documents
- **Route53**: Hosted Zones (public and private)
- **ECS**: Clusters, Services, Task Definitions
- **EKS**: Clusters, Node Groups, Fargate Profiles
- **Step Functions**: State Machines
- **WAF**: Web ACLs (Regional and CloudFront)
- **CodePipeline**: CI/CD Pipelines
- **CodeBuild**: Build Projects
- **Backup**: Backup Plans, Backup Vaults

## Architecture

- **Language**: Python 3.8+
- **CLI Framework**: Typer
- **AWS SDK**: boto3
- **Output**: Rich terminal UI
- **Storage**: Local YAML files

## Development

### Setup

```bash
# Install development dependencies
pip install -e ".[dev]"

# Verify installation
awsinv --help
```

### Testing

Use invoke for all development tasks:

```bash
# Run all tests with coverage
invoke test

# Run unit tests only
invoke test-unit

# Run integration tests only
invoke test-integration

# Run tests with verbose output
invoke test --verbose

# Generate HTML coverage report
invoke coverage-report
```

### Code Quality

```bash
# Run all quality checks (format, lint, typecheck)
invoke quality

# Auto-fix formatting and linting issues
invoke quality --fix

# Format code
invoke format

# Check formatting without changes
invoke format --check

# Lint code
invoke lint

# Auto-fix linting issues
invoke lint --fix

# Type check
invoke typecheck
```

### Build & Release

```bash
# Clean build artifacts
invoke clean

# Build package
invoke build

# Show version
invoke version

# Run all CI checks (quality + tests)
invoke ci
```

### Available Invoke Tasks

```bash
# List all available tasks
invoke --list
```

## Project Structure

```
aws-inventory-manager/
├── src/
│   ├── cli/                # CLI entry point and commands
│   ├── models/             # Data models (Snapshot, Inventory, Resource, etc.)
│   ├── snapshot/           # Snapshot capture and inventory storage
│   ├── delta/              # Delta calculation
│   ├── cost/               # Cost analysis
│   ├── aws/                # AWS client utilities
│   └── utils/              # Shared utilities
├── tests/
│   ├── unit/               # Unit tests
│   └── integration/        # Integration tests
└── ~/.snapshots/           # Default snapshot storage
    ├── inventories.yaml    # Inventory metadata
    └── snapshots/          # Individual snapshot files
```

## Command Reference

### Inventory Commands

```bash
# Create an inventory
awsinv inventory create <name> \
  [--description "Description"] \
  [--include-tags "Key1=Value1,Key2=Value2"] \
  [--exclude-tags "Key3=Value3"] \
  [--profile <aws-profile>]

# List all inventories for current account
awsinv inventory list [--profile <aws-profile>]

# Show detailed inventory information
awsinv inventory show <name> [--profile <aws-profile>]

# Delete an inventory
awsinv inventory delete <name> \
  [--force] \
  [--profile <aws-profile>]

# Migrate legacy snapshots to inventory structure
awsinv inventory migrate [--profile <aws-profile>]
```

### Snapshot Commands

```bash
# Create a snapshot
awsinv snapshot create [name] \
  [--inventory <inventory-name>] \
  [--regions <region1,region2>] \
  [--include-tags "Key=Value"] \
  [--exclude-tags "Key=Value"] \
  [--before-date YYYY-MM-DD] \
  [--after-date YYYY-MM-DD] \
  [--compress] \
  [--profile <aws-profile>]

# List all snapshots
awsinv snapshot list [--profile <aws-profile>]

# Show snapshot details
awsinv snapshot show <name> [--profile <aws-profile>]
```

### Analysis Commands

```bash
# View resource delta
awsinv delta \
  [--inventory <inventory-name>] \
  [--snapshot <snapshot-name>] \
  [--resource-type <type>] \
  [--region <region>] \
  [--show-details] \
  [--export <file.json|file.csv>] \
  [--profile <aws-profile>]

# Analyze costs for an inventory
awsinv cost \
  [--inventory <inventory-name>] \
  [--snapshot <snapshot-name>] \
  [--start-date YYYY-MM-DD] \
  [--end-date YYYY-MM-DD] \
  [--granularity DAILY|MONTHLY] \
  [--show-services] \
  [--export <file.json|file.csv>] \
  [--profile <aws-profile>]
```

## Contributing

Contributions are welcome! Please read the contributing guidelines before submitting pull requests.

## License

MIT License - see LICENSE file for details

## Support

- Report issues: https://github.com/troylar/aws-inventory-manager/issues
- Documentation: https://github.com/troylar/aws-inventory-manager#readme

---

**Version**: 0.1.0
**Status**: Alpha
**Python**: 3.8 - 3.13
