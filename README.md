# AWS Baseline Snapshot & Delta Tracking

A Python CLI tool that captures point-in-time snapshots of AWS cloud landing zone baseline resources, tracks resource deltas over time, separates baseline vs. non-baseline costs for chargeback, and provides restoration capabilities to return environments to baseline state.

## Features

- **📸 Baseline Snapshots**: Capture complete inventory of AWS resources across multiple regions
- **🔄 Delta Tracking**: Identify resources added, modified, or removed since baseline
- **💰 Cost Analysis**: Separate baseline "dial tone" costs from project costs
- **🔧 Baseline Restoration**: Remove non-baseline resources to return to clean state
- **🏷️ Historical Baselines**: Create baselines filtered by date and tags
- **📦 Snapshot Management**: Manage multiple snapshots with active baseline tracking

## Quick Start

### Installation

```bash
# Install from PyPI (when published)
pip install aws-baseline-snapshot

# Or install from source
git clone https://github.com/your-org/aws-baseline.git
cd aws-baseline
pip install -e .
```

### Prerequisites

- Python 3.8 or higher
- AWS CLI configured with credentials
- IAM permissions for resource read/write operations

### Basic Usage

```bash
# Create your first baseline snapshot
aws-baseline snapshot create my-baseline

# View what's changed since baseline
aws-baseline delta

# Analyze cost breakdown
aws-baseline cost

# List all snapshots
aws-baseline snapshot list

# Restore to baseline (removes non-baseline resources)
aws-baseline restore --dry-run  # Preview first
aws-baseline restore            # Actual restoration
```

## Documentation

For complete documentation including:
- Installation guide
- Command reference
- Usage examples
- Configuration options
- Best practices

See the [Quickstart Guide](specs/001-aws-baseline-snapshot/quickstart.md)

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

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black src/ tests/

# Lint
ruff check src/ tests/

# Type check
mypy src/
```

## Project Structure

```
aws-baseline/
├── src/
│   ├── cli.py              # CLI entry point
│   ├── models/             # Data models
│   ├── snapshot/           # Snapshot capture
│   ├── delta/              # Delta calculation
│   ├── cost/               # Cost analysis
│   ├── restore/            # Resource restoration
│   ├── aws/                # AWS client utilities
│   └── utils/              # Shared utilities
├── tests/
│   ├── unit/               # Unit tests
│   └── integration/        # Integration tests
├── .snapshots/             # Default snapshot storage
└── specs/                  # Feature specifications
```

## Contributing

Contributions are welcome! Please read the contributing guidelines before submitting pull requests.

## License

MIT License - see LICENSE file for details

## Support

- Report issues: https://github.com/your-org/aws-baseline/issues
- Documentation: https://github.com/your-org/aws-baseline#readme

---

**Version**: 1.0.0
**Status**: Beta
**Python**: 3.8 - 3.13
