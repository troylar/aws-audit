<div align="center">

# 📦 AWS Inventory Manager

### *Snapshot, Track, Secure, and Restore Your AWS Environment*

[![CI](https://github.com/troylar/aws-inventory-manager/actions/workflows/ci.yml/badge.svg)](https://github.com/troylar/aws-inventory-manager/actions/workflows/ci.yml)
[![Coverage](https://codecov.io/gh/troylar/aws-inventory-manager/branch/main/graph/badge.svg)](https://codecov.io/gh/troylar/aws-inventory-manager)
[![PyPI version](https://img.shields.io/pypi/v/aws-inventory-manager.svg)](https://pypi.org/project/aws-inventory-manager/)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Snapshots** • **Configuration Drift** • **Security Scanning** • **Cost Analysis** • **Resource Cleanup** • **27 AWS Services**

[Quick Start](#-quick-start) • [Features](#-features) • [Documentation](#-documentation)

</div>

---

## 🎯 What It Does

AWS Inventory Manager gives you complete visibility and control over your AWS resources:

```bash
# Capture your environment
awsinv snapshot create my-snapshot --regions us-east-1,us-west-2

# Track what changed
awsinv delta --show-diff

# Find security issues
awsinv security scan --severity HIGH

# Restore to any snapshot (NEW!)
awsinv restore preview my-snapshot  # See what would be deleted
awsinv restore execute my-snapshot --confirm  # Clean up new resources
```

### Why You Need This

- **"What changed?"** → Field-level configuration drift detection
- **"Are we secure?"** → Automated CIS Benchmark security scanning
- **"Can we restore?"** → Delete resources created after any snapshot
- **"How much does this cost?"** → Per-inventory cost tracking
- **"Who owns what?"** → Tag-based filtering and team isolation

---

## ✨ Features

<table>
<tr>
<td width="33%" valign="top">

### 📸 Snapshot
- 27 AWS services
- Multi-region support
- Tag-based filtering
- Point-in-time capture
- Export to JSON/CSV

</td>
<td width="33%" valign="top">

### 🔍 Track Changes
- Field-level drift detection
- Before/after comparison
- Color-coded output
- Configuration + security changes
- JSON export

</td>
<td width="33%" valign="top">

### 🔒 Security
- 12+ CIS-aligned checks
- Severity levels (CRITICAL→LOW)
- Find public buckets, open ports
- IAM credential age
- Remediation guidance

</td>
</tr>
<tr>
<td width="33%" valign="top">

### 💰 Cost Analysis
- Per-inventory tracking
- Date range analysis
- Service-level breakdown
- Multi-account support
- Team attribution

</td>
<td width="33%" valign="top">

### 🧹 Restore (NEW)
- Preview mode (dry-run)
- Dependency-aware deletion
- Multi-layer protection rules
- Comprehensive audit logs
- Supports 41 resource types

</td>
<td width="33%" valign="top">

### 📊 Reporting
- Summary & detailed views
- Resource type filtering
- Multiple export formats
- Beautiful terminal UI
- Pagination support

</td>
</tr>
</table>

---

## 🚀 Quick Start

### Installation

```bash
pip install aws-inventory-manager
```

### 60-Second Demo

```bash
# 1. Create a snapshot
awsinv snapshot create my-snapshot --regions us-east-1

# 2. See what you have
awsinv snapshot report

# 3. Make some changes in AWS console...

# 4. Track what changed
awsinv delta --snapshot my-snapshot --show-diff

# 5. Scan for security issues
awsinv security scan

# 6. Restore to snapshot (removes new resources)
awsinv restore preview my-snapshot      # Safe preview
awsinv restore execute my-snapshot --confirm  # Actual cleanup
```

---

## 📖 Documentation

### Core Workflows

<details>
<summary><b>1. Snapshot Your Environment</b></summary>

```bash
# Basic snapshot
awsinv snapshot create prod-snapshot --regions us-east-1,us-west-2

# With tag filtering
awsinv snapshot create team-alpha \
  --include-tags "Team=Alpha" \
  --regions us-east-1

# Generate report
awsinv snapshot report --detailed
awsinv snapshot report --export report.json
```

**What gets captured:** EC2, S3, RDS, Lambda, VPCs, IAM, KMS, and [24 more services](#-supported-services)

</details>

<details>
<summary><b>2. Track Configuration Changes</b></summary>

```bash
# See what changed since snapshot
awsinv delta --snapshot my-snapshot

# Show field-level changes
awsinv delta --snapshot my-snapshot --show-diff
```

**Example output:**
```
Configuration Changes:
  Instance i-abc123:
    InstanceType: t2.micro → t2.small
    Tags.Environment: dev → prod

Security Changes:
  Bucket my-bucket:
    PublicAccessBlockConfiguration.BlockPublicAcls: true → false ⚠️
```

</details>

<details>
<summary><b>3. Scan for Security Issues</b></summary>

```bash
# Scan all security checks
awsinv security scan

# Filter by severity
awsinv security scan --severity CRITICAL

# Export findings
awsinv security scan --export findings.json
```

**Checks include:**
- Public S3 buckets (CRITICAL)
- Open SSH/RDP ports (HIGH)
- Unencrypted databases (HIGH)
- Old IAM keys (MEDIUM)
- IMDSv1 on EC2 (MEDIUM)

</details>

<details>
<summary><b>4. Restore to Snapshot (NEW)</b></summary>

```bash
# Preview what would be deleted (safe, no changes)
awsinv restore preview prod-baseline

# Shows:
# - Resources created after the snapshot
# - Which are protected
# - Deletion order (respects dependencies)

# Execute cleanup (requires --confirm)
awsinv restore execute prod-baseline --confirm

# Filter by type or region
awsinv restore preview my-snapshot --type AWS::EC2::Instance --region us-east-1
```

**Works with any snapshot** - use whatever naming convention fits your workflow.

**Safety features:**
- Preview mode (dry-run)
- Multiple confirmations required
- Tag-based protection rules
- Type/age/cost-based protection
- Dependency-aware deletion order
- Comprehensive audit logging

**Protection rules example:**
```bash
# Protected resources are automatically skipped:
# - Resources with Protection=true tag
# - Critical resource types (e.g., production databases)
# - Resources younger than threshold
# - High-cost resources (configurable)
```

</details>

<details>
<summary><b>5. Analyze Costs</b></summary>

```bash
# Current costs
awsinv cost

# Date range
awsinv cost --start-date 2025-01-01 --end-date 2025-01-31

# By service
awsinv cost --show-services
```

</details>

---

### Command Reference

```bash
# SNAPSHOTS
awsinv snapshot create [name] [--regions <regions>]
awsinv snapshot list
awsinv snapshot report [--detailed] [--export <file>]

# ANALYSIS
awsinv delta [--snapshot <name>] [--show-diff]
awsinv security scan [--severity <level>] [--export <file>]
awsinv cost [--start-date <date>] [--show-services]

# RESTORE (NEW)
awsinv restore preview <snapshot>  # Safe preview mode
awsinv restore execute <snapshot> --confirm  # Delete new resources
  [--type <resource-type>]   # Filter by type
  [--region <region>]        # Filter by region
  [--profile <aws-profile>]  # AWS profile

# GLOBAL OPTIONS
--profile <aws-profile>    # AWS CLI profile
--storage-path <path>      # Custom storage location
--help                     # Show help
```

---

## 📊 Supported Services

**27 AWS Services:** EC2, Lambda, ECS, EKS, S3, EBS, EFS, RDS, DynamoDB, ElastiCache, VPC, Security Groups, Load Balancers, Route53, IAM, KMS, Secrets Manager, CodePipeline, CodeBuild, CloudFormation, Step Functions, CloudWatch, EventBridge, SNS, SQS, WAF, Backup

**Restore supports 41 resource types** with intelligent dependency resolution.

---

## 📅 Date-Based Filtering Support

When using `--before-date` or `--after-date` filters, note that not all AWS resources expose creation timestamps via their APIs.

<details>
<summary><b>Resources WITH creation date support</b></summary>

| Service | Resource Type | Creation Date Field |
|---------|---------------|---------------------|
| EC2 | Instances | LaunchTime |
| EC2 | Volumes | CreateTime |
| S3 | Buckets | CreationDate |
| RDS | DB Instances | InstanceCreateTime |
| RDS | DB Clusters | ClusterCreateTime |
| DynamoDB | Tables | CreationDateTime |
| IAM | Roles, Users, Groups, Policies | CreateDate |
| ELB | Load Balancers | CreatedTime |
| CloudFormation | Stacks | CreationTime |
| KMS | Keys | CreationDate |
| EFS | File Systems | CreationTime |
| EKS | Clusters, Node Groups, Fargate Profiles | createdAt |
| ECS | Clusters, Services, Task Definitions | createdAt |
| Lambda | Functions | LastModified |
| Lambda | Layers | CreatedDate |
| API Gateway | REST APIs, HTTP APIs | createdDate |
| Step Functions | State Machines | creationDate |
| CodeBuild | Projects | created |
| CodePipeline | Pipelines | created |
| Secrets Manager | Secrets | CreatedDate |
| Route53 | Hosted Zones | (via metadata) |
| SQS | Queues | CreatedTimestamp |

</details>

<details>
<summary><b>Resources WITHOUT creation date support</b></summary>

| Service | Resource Type | Note |
|---------|---------------|------|
| EC2 | VPCs | AWS API doesn't provide creation timestamp |
| EC2 | Security Groups | AWS API doesn't provide creation timestamp |
| EC2 | Subnets | AWS API doesn't provide creation timestamp |
| SNS | Topics | AWS API doesn't provide creation timestamp |
| CloudWatch | Log Groups | Not easily exposed via API |

**Behavior:** Resources without creation dates are **included by default** when date filters are applied. This ensures you don't accidentally miss resources due to API limitations.

</details>

---

## 🎯 Use Cases

### Baseline State Management
```bash
# Capture your production baseline
awsinv snapshot create prod-baseline

# Later, restore to baseline state
awsinv restore execute prod-baseline --confirm
# Removes all resources created after the baseline
```

### Ephemeral Environment Cleanup
```bash
# Create snapshot before temporary resources
awsinv snapshot create clean-state

# After testing, restore to snapshot
awsinv restore execute clean-state --confirm
```

### Configuration Drift Detection
```bash
# Before deployment
awsinv snapshot create pre-deploy

# After deployment - see exactly what changed
awsinv delta --snapshot pre-deploy --show-diff
```

### Multi-Team Cost Attribution
```bash
# Track costs per team
awsinv snapshot create team-frontend --include-tags "Team=Frontend"
awsinv cost --snapshot team-frontend
```

### Security Compliance Audits
```bash
# CIS compliance reporting
awsinv security scan --cis-only --export audit.csv
```

---

## 🛠️ Development

<details>
<summary><b>Setup & Testing</b></summary>

```bash
# Setup
git clone https://github.com/troylar/aws-inventory-manager.git
cd aws-inventory-manager
pip install -e ".[dev]"

# Run tests
invoke test              # All tests with coverage
invoke test-unit         # Unit tests only
invoke quality           # Format, lint, typecheck
invoke quality --fix     # Auto-fix issues

# Build
invoke build            # Build package
invoke ci               # Run all CI checks
```

**Test Coverage:** 600+ tests across the codebase with 52% overall coverage. Restore module has 98.5% coverage (153 tests).

</details>

---

## 🏗️ Architecture

```
┌────────────────────────────────────────────────┐
│         AWS Inventory Manager (CLI)            │
├────────────────────────────────────────────────┤
│ Commands                                       │
│  ├─ snapshot    (Capture resources)            │
│  ├─ delta       (Track changes)                │
│  ├─ security    (Scan misconfigurations)       │
│  ├─ cost        (Analyze spending)             │
│  └─ restore     (Cleanup resources) ✨ NEW     │
├────────────────────────────────────────────────┤
│ Core Engine                                    │
│  ├─ 27 Resource Collectors (boto3)             │
│  ├─ Configuration Differ (field-level)         │
│  ├─ Security Scanner (CIS aligned)             │
│  ├─ Cost Analyzer (AWS Cost Explorer)          │
│  └─ Resource Cleanup (dependency-aware) ✨ NEW │
├────────────────────────────────────────────────┤
│ Storage Layer (YAML)                           │
│  ├─ ~/.snapshots/snapshots/*.yaml              │
│  └─ ~/.snapshots/audit-logs/**/*.yaml ✨ NEW   │
└────────────────────────────────────────────────┘
```

**Tech Stack:** Python 3.8+ • Typer • Rich • boto3 • YAML • pytest

---

## 🤝 Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Run tests: `invoke test`
4. Run quality checks: `invoke quality`
5. Submit a pull request

See [CONTRIBUTING.md](CONTRIBUTING.md) for details.

---

## 📜 License

MIT License - see [LICENSE](LICENSE)

---

## 🆘 Support

- **Issues:** [GitHub Issues](https://github.com/troylar/aws-inventory-manager/issues)
- **Discussions:** [GitHub Discussions](https://github.com/troylar/aws-inventory-manager/discussions)

---

<div align="center">

**Made with ❤️ for AWS practitioners**

[![Star on GitHub](https://img.shields.io/github/stars/troylar/aws-inventory-manager?style=social)](https://github.com/troylar/aws-inventory-manager)

**Version** 0.6.0 • **Python** 3.8 - 3.13 • **Status** Production/Stable

[⬆ Back to Top](#-aws-inventory-manager)

</div>
