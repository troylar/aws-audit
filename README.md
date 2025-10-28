# AWS Audit - Resource Snapshot & Delta Tracking

A Python CLI tool that captures point-in-time snapshots of AWS resources organized by inventory, tracks resource deltas over time, analyzes costs per inventory, and provides restoration capabilities.

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
# Install from PyPI (when published)
pip install aws-audit

# Or install from source
git clone https://github.com/your-org/aws-audit.git
cd aws-audit
pip install -e .
```

### Prerequisites

- Python 3.8 or higher
- AWS CLI configured with credentials
- IAM permissions for resource read/write operations

### Basic Usage

```bash
# Create a named inventory for organizing snapshots
aws-audit inventory create infrastructure \
  --description "Core infrastructure resources"

# Create a filtered inventory for a specific team
aws-audit inventory create team-alpha \
  --description "Team Alpha resources" \
  --include-tags "Team=Alpha"

# Take a snapshot (automatically uses 'default' inventory if none specified)
aws-audit snapshot create

# Take a snapshot within a specific inventory
aws-audit snapshot create --inventory infrastructure

# List all inventories
aws-audit inventory list

# View what's changed since the snapshot
aws-audit delta

# View delta for specific inventory
aws-audit delta --inventory team-alpha

# Analyze costs for a specific inventory
aws-audit cost --inventory infrastructure

# Analyze costs for team inventory
aws-audit cost --inventory team-alpha

# List all snapshots
aws-audit snapshot list

# Migrate legacy snapshots to inventory structure
aws-audit inventory migrate

# Restore to snapshot (removes resources added since snapshot)
aws-audit restore --dry-run  # Preview first
aws-audit restore            # Actual restoration
```

## Use Cases

### Multi-Account Resource Management
Organize snapshots by AWS account and purpose. Track costs per account.

```bash
# Create inventory for core infrastructure account
aws-audit inventory create infrastructure \
  --description "Core infrastructure resources"

# Take snapshot
aws-audit snapshot create --inventory infrastructure

# Analyze costs for this inventory
aws-audit cost --inventory infrastructure
```

### Team-Based Resource Tracking
Create filtered inventories for different teams to track their resources and costs independently.

```bash
# Create team-specific inventories with tag filters
aws-audit inventory create team-alpha \
  --include-tags "Team=Alpha" \
  --description "Team Alpha resources"

aws-audit inventory create team-beta \
  --include-tags "Team=Beta" \
  --description "Team Beta resources"

# Take filtered snapshots for each team
aws-audit snapshot create --inventory team-alpha
aws-audit snapshot create --inventory team-beta

# Analyze costs per team
aws-audit cost --inventory team-alpha
aws-audit cost --inventory team-beta
```

### Environment Isolation
Separate production, staging, and development resources for independent tracking.

```bash
# Create environment-specific inventories
aws-audit inventory create production \
  --include-tags "Environment=production"

aws-audit inventory create staging \
  --include-tags "Environment=staging"

# Track changes for each environment
aws-audit delta --inventory production
aws-audit delta --inventory staging

# Analyze costs per environment
aws-audit cost --inventory production
aws-audit cost --inventory staging
```

## Documentation

For complete documentation including:
- Installation guide
- Command reference
- Usage examples
- Configuration options
- Best practices

See the documentation:
- [Feature 001: AWS Resource Snapshot](specs/001-aws-baseline-snapshot/quickstart.md)
- [Feature 002: Inventory Management](specs/002-inventory-management/quickstart.md)

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
aws-audit --help
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
aws-audit/
├── src/
│   ├── cli/                # CLI entry point and commands
│   ├── models/             # Data models (Snapshot, Inventory, Resource, etc.)
│   ├── snapshot/           # Snapshot capture and inventory storage
│   ├── delta/              # Delta calculation
│   ├── cost/               # Cost analysis
│   ├── restore/            # Resource restoration
│   ├── aws/                # AWS client utilities
│   └── utils/              # Shared utilities
├── tests/
│   ├── unit/               # Unit tests
│   └── integration/        # Integration tests
├── .snapshots/             # Default snapshot storage
│   ├── inventories.yaml    # Inventory metadata
│   └── snapshots/          # Individual snapshot files
└── specs/                  # Feature specifications
    ├── 001-aws-audit-snapshot/
    └── 002-inventory-management/
```

## Command Reference

### Inventory Commands

```bash
# Create an inventory
aws-audit inventory create <name> \
  [--description "Description"] \
  [--include-tags "Key1=Value1,Key2=Value2"] \
  [--exclude-tags "Key3=Value3"] \
  [--profile <aws-profile>]

# List all inventories for current account
aws-audit inventory list [--profile <aws-profile>]

# Show detailed inventory information
aws-audit inventory show <name> [--profile <aws-profile>]

# Delete an inventory
aws-audit inventory delete <name> \
  [--force] \
  [--profile <aws-profile>]

# Migrate legacy snapshots to inventory structure
aws-audit inventory migrate [--profile <aws-profile>]
```

### Snapshot Commands

```bash
# Create a snapshot
aws-audit snapshot create [name] \
  [--inventory <inventory-name>] \
  [--regions <region1,region2>] \
  [--include-tags "Key=Value"] \
  [--exclude-tags "Key=Value"] \
  [--before-date YYYY-MM-DD] \
  [--after-date YYYY-MM-DD] \
  [--compress] \
  [--profile <aws-profile>]

# List all snapshots
aws-audit snapshot list [--profile <aws-profile>]

# Show snapshot details
aws-audit snapshot show <name> [--profile <aws-profile>]
```

### Analysis Commands

```bash
# View resource delta
aws-audit delta \
  [--inventory <inventory-name>] \
  [--snapshot <snapshot-name>] \
  [--resource-type <type>] \
  [--region <region>] \
  [--show-details] \
  [--export <file.json|file.csv>] \
  [--profile <aws-profile>]

# Analyze costs for an inventory
aws-audit cost \
  [--inventory <inventory-name>] \
  [--snapshot <snapshot-name>] \
  [--start-date YYYY-MM-DD] \
  [--end-date YYYY-MM-DD] \
  [--granularity DAILY|MONTHLY] \
  [--show-services] \
  [--export <file.json|file.csv>] \
  [--profile <aws-profile>]

# Restore to a snapshot state
aws-audit restore \
  [--snapshot <snapshot-name>] \
  [--dry-run] \
  [--profile <aws-profile>]
```

## Contributing

Contributions are welcome! Please read the contributing guidelines before submitting pull requests.

## License

MIT License - see LICENSE file for details

## Support

- Report issues: https://github.com/your-org/aws-audit/issues
- Documentation: https://github.com/your-org/aws-audit#readme

---

**Version**: 1.0.0
**Status**: Beta
**Python**: 3.8 - 3.13
