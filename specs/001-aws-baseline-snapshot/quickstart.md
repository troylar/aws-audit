# Quickstart Guide: AWS Baseline Snapshot

**Feature**: 001-aws-audit-snapshot
**Date**: 2025-10-26
**Phase**: 1 - Design

## Overview

This quickstart guide will help you install, configure, and start using the AWS Baseline Snapshot tool to track your AWS infrastructure changes and costs.

**Time to complete**: 10-15 minutes

---

## Prerequisites

Before you begin, ensure you have:

- **Python 3.8 or higher** installed
  ```bash
  python --version  # Should show 3.8+
  ```

- **AWS Account** with a cloud landing zone deployed

- **AWS CLI configured** with credentials
  ```bash
  aws sts get-caller-identity  # Should show your AWS account info
  ```

- **IAM Permissions** - Your AWS credentials need read permissions for the resources you want to snapshot:
  - `ec2:Describe*`
  - `iam:List*`, `iam:Get*`
  - `lambda:List*`, `lambda:Get*`
  - `s3:ListAllMyBuckets`, `s3:GetBucketLocation`
  - `rds:Describe*`
  - `ce:GetCostAndUsage` (for cost analysis)
  - And similar read permissions for other services

  For restore operations, you also need delete permissions:
  - `ec2:Terminate*`, `ec2:Delete*`
  - `lambda:Delete*`
  - `iam:Delete*`
  - etc.

---

## Installation

### Option 1: Install from PyPI (When Published)

```bash
pip install aws-audit
```

### Option 2: Install from Source (Development)

```bash
# Clone the repository
git clone https://github.com/your-org/aws-audit.git
cd aws-audit

# Install in development mode
pip install -e .

# Verify installation
aws-audit --version
```

### Option 3: Using pipx (Isolated Installation)

```bash
pipx install aws-audit
```

---

## Quick Start in 5 Steps

### Step 1: Verify AWS Credentials

Ensure your AWS credentials are configured:

```bash
# Check current AWS identity
aws sts get-caller-identity

# If not configured, run:
aws configure
```

**Expected output**:
```
{
    "UserId": "AIDAI...",
    "Account": "123456789012",
    "Arn": "arn:aws:iam::123456789012:user/admin"
}
```

---

### Step 2: Create Your First Baseline Snapshot

After your cloud landing zone is deployed, create a baseline snapshot:

```bash
# Create snapshot with default name (auto-generated from timestamp)
aws-audit snapshot create

# Or create with a custom name
aws-audit snapshot create my-baseline
```

**What happens**:
- Tool scans all enabled AWS regions
- Collects resources from supported services (IAM, Lambda, EC2, S3, RDS, etc.)
- Stores snapshot in `.snapshots/` directory
- Sets snapshot as active baseline

**Expected output**:
```
Creating snapshot: baseline-2025-10-26

Collecting resources...
us-east-1  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% (10/10 services) 0:01:23
us-west-2  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% (10/10 services) 0:01:15

✓ Snapshot complete!

Summary:
Total resources: 456
Snapshot saved: .snapshots/baseline-2025-10-26.yaml
Active baseline: baseline-2025-10-26
Duration: 2m 38s
```

---

### Step 3: View Your Snapshot

Inspect the snapshot you just created:

```bash
# List all snapshots
aws-audit snapshot list

# View detailed information about a snapshot
aws-audit snapshot show baseline-2025-10-26
```

**Expected output**:
```
Snapshot: baseline-2025-10-26
Created: 2025-10-26 10:30:00 UTC
Account: 123456789012
Regions: us-east-1, us-west-2
Status: Active baseline
Total resources: 456

Resources by service:
┏━━━━━━━━━━━━━━┳━━━━━━━━━┓
┃ Service      ┃ Count   ┃
┡━━━━━━━━━━━━━━╇━━━━━━━━━┩
│ EC2          │ 245     │
│ CloudWatch   │ 98      │
│ IAM          │ 52      │
│ Lambda       │ 18      │
│ ...          │ ...     │
└──────────────┴─────────┘
```

---

### Step 4: Track Changes (Delta)

After some development work, see what resources have been added or changed:

```bash
# Show all changes since baseline
aws-audit delta
```

**Expected output**:
```
Delta Report
Baseline: baseline-2025-10-26 (created 2025-10-26 10:30)
Current:  2025-10-27 14:30

Summary:
  Added:     5 resources
  Deleted:   1 resource
  Modified:  2 resources
  Unchanged: 448 resources

Added Resources (5):
  Lambda Functions (3):
    ✓ new-experiment-function (us-east-1)
    ✓ data-processor (us-west-2)
    ✓ api-handler (us-east-1)

  EC2 Instances (2):
    ✓ i-0123456789abcdef0 (us-east-1)
    ✓ i-0123456789abcdef1 (us-east-1)

[... more details ...]
```

**Filtering examples**:
```bash
# Show only added Lambda functions
aws-audit delta --resource-type lambda --change-type added

# Show changes in specific region
aws-audit delta --region us-east-1

# Export delta report to JSON
aws-audit delta --export delta-report.json
```

---

### Step 5: Analyze Costs

See cost breakdown for resources in your inventory:

```bash
# Show costs for the default inventory (last 30 days)
aws-audit cost

# Show costs for a specific inventory
aws-audit cost --inventory infrastructure

# Show costs for specific month
aws-audit cost --inventory infrastructure --start-date 2025-10-01 --end-date 2025-10-31
```

**Expected output**:
```
Cost Report
Inventory: infrastructure
Snapshot: 123456789012-infrastructure-2025-10-26
Period:   2025-10-01 to 2025-10-31
Currency: USD

Total Cost: $576.25

Service Breakdown:
┏━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━┓
┃ Service           ┃ Cost      ┃ Percent  ┃
┡━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━┩
│ EC2               │ $285.50   │ 49.5%    │
│ RDS               │ $180.25   │ 31.3%    │
│ Lambda            │ $110.50   │ 19.2%    │
└───────────────────┴───────────┴──────────┘
```

**Advanced cost analysis**:
```bash
# Analyze costs for different inventories (teams, environments)
aws-audit cost --inventory team-alpha
aws-audit cost --inventory team-beta
aws-audit cost --inventory production

# Export to CSV for finance team
aws-audit cost --inventory infrastructure --export october-costs.csv --start-date 2025-10-01 --end-date 2025-10-31
```

---

## Common Workflows

### Workflow 1: Testing & Cleanup

When testing new features, use the tool to clean up afterward:

```bash
# 1. Capture baseline before testing
aws-audit snapshot create pre-test-baseline

# 2. Do your testing (create EC2 instances, Lambda functions, etc.)

# 3. Check what was created
aws-audit delta

# 4. Preview cleanup (dry-run)
aws-audit restore --dry-run

# 5. Clean up test resources
aws-audit restore
```

---

### Workflow 2: Monthly Cost Reporting

Generate monthly cost reports for finance:

```bash
# Generate October cost report
aws-audit cost \
  --start-date 2025-10-01 \
  --end-date 2025-10-31 \
  --group-by Project \
  --export october-2025-cost-report.csv

# Email or upload the CSV to your finance system
```

---

### Workflow 3: Multi-Environment Management

Manage different baselines for different environments:

```bash
# Create production baseline
aws-audit snapshot create prod-baseline --regions us-east-1,us-west-2

# Create staging baseline (different account, use --profile)
aws-audit --profile staging snapshot create staging-baseline

# Compare staging to its baseline
aws-audit --profile staging delta

# Switch active baseline
aws-audit snapshot set-active prod-baseline
```

---

### Workflow 4: Tracking Drift from Approved Configuration

Monitor drift from approved infrastructure:

```bash
# Daily: Check for drift
aws-audit delta

# If unauthorized changes detected, investigate
aws-audit delta --change-type modified --show-details

# Option 1: Restore to baseline (destructive!)
aws-audit restore --dry-run  # Preview first
aws-audit restore            # Actual restoration

# Option 2: Create new baseline if changes are approved
aws-audit snapshot create updated-baseline
```

---

## Advanced Configuration

### Configuration File

Create `.aws-audit.yaml` in your project directory or `~/.aws-audit.yaml` for global settings:

```yaml
# Default snapshot directory
snapshot_dir: /path/to/snapshots

# Default regions to include
regions:
  - us-east-1
  - us-west-2

# Resource types to include/exclude
resource_types:
  include:
    - iam
    - lambda
    - ec2
    - s3
    - rds
  exclude:
    - cloudformation  # Skip CloudFormation resources

# AWS profile
aws_profile: production

# Performance tuning
parallel_workers: 10
auto_compress_mb: 10

# Cost settings
cost:
  currency: USD
  default_period_days: 30
```

---

### Environment Variables

Customize behavior with environment variables:

```bash
# Snapshot storage location
export AWS_BASELINE_SNAPSHOT_DIR=/custom/snapshot/location

# Default AWS region
export AWS_REGION=us-east-1

# Log level
export AWS_BASELINE_LOG_LEVEL=DEBUG

# Disable colored output (for CI/CD)
export NO_COLOR=1
```

---

### Scripting & Automation

Use the tool in scripts with JSON output:

```bash
#!/bin/bash
# Daily drift check script

# Get delta in JSON format
DELTA=$(aws-audit delta --output json)

# Count changes
ADDED=$(echo "$DELTA" | jq '.added_resources | length')
DELETED=$(echo "$DELTA" | jq '.deleted_resources | length')
MODIFIED=$(echo "$DELTA" | jq '.modified_resources | length')

TOTAL_CHANGES=$((ADDED + DELETED + MODIFIED))

if [ "$TOTAL_CHANGES" -gt 0 ]; then
  echo "⚠ Drift detected: $TOTAL_CHANGES changes"
  # Send alert (email, Slack, PagerDuty, etc.)
  aws-audit delta --export "drift-$(date +%Y-%m-%d).json"
else
  echo "✓ No drift detected"
fi
```

---

## Troubleshooting

### Issue: "AWS credentials not found"

**Solution**: Configure AWS credentials:
```bash
aws configure
# or
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
```

---

### Issue: "Permission denied" errors during snapshot

**Solution**: Your IAM user/role needs read permissions. Required policies:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ec2:Describe*",
        "iam:List*",
        "iam:Get*",
        "lambda:List*",
        "lambda:Get*",
        "s3:ListAllMyBuckets",
        "rds:Describe*",
        "ce:GetCostAndUsage"
      ],
      "Resource": "*"
    }
  ]
}
```

---

### Issue: Snapshot taking too long

**Solutions**:
- Reduce number of regions: `--regions us-east-1`
- Limit resource types: `--resource-types iam,lambda,ec2`
- Increase parallelism: `--parallel 20`

---

### Issue: Cost data not available

**Possible causes**:
1. AWS Cost Explorer not enabled (enable in AWS Console)
2. Cost Explorer data lag (wait 24-48 hours after resource creation)
3. Missing IAM permission: `ce:GetCostAndUsage`

**Check**:
```bash
aws ce get-cost-and-usage \
  --time-period Start=2025-10-01,End=2025-10-31 \
  --granularity DAILY \
  --metrics UnblendedCost
```

---

### Issue: "Cannot delete active snapshot"

**Solution**: Set a different snapshot as active first:
```bash
aws-audit snapshot set-active other-snapshot
aws-audit snapshot delete old-snapshot
```

---

## Best Practices

### 1. Baseline Timing
- Create baseline immediately after landing zone deployment
- Update baseline when approved infrastructure changes are deployed
- Keep historical baselines for audit trails

### 2. Naming Conventions
```bash
# Include date and environment
aws-audit snapshot create prod-baseline-2025-10-26

# Include purpose
aws-audit snapshot create post-security-audit-baseline
```

### 3. Regular Checks
```bash
# Daily drift check (cron job)
0 9 * * * cd /path/to/project && aws-audit delta --quiet || echo "Drift detected"

# Weekly cost report (cron job)
0 9 * * 1 cd /path/to/project && aws-audit cost --export weekly-cost-$(date +%Y-%m-%d).csv
```

### 4. Multi-Region Strategy
```bash
# If using multiple regions, be explicit
aws-audit snapshot create --regions us-east-1,us-west-2,eu-west-1

# Or configure in .aws-audit.yaml
```

### 5. Cost Attribution via Inventories
- Create separate inventories per team/project using tag filters
- Use `--inventory` to analyze costs independently per team/environment

### 6. Safe Restoration
```bash
# ALWAYS dry-run first
aws-audit restore --dry-run

# Review output carefully
# Only then run actual restore
aws-audit restore
```

---

## What's Next?

Now that you're up and running, explore these advanced topics:

1. **Automated Drift Detection**: Set up CI/CD integration to check for drift on every deployment
2. **Cost Alerting**: Create scripts to alert when inventory costs exceed thresholds
3. **Multi-Account Management**: Use AWS Organizations with separate baselines per account
4. **Compliance Reporting**: Combine with AWS Config for comprehensive compliance tracking
5. **Baseline Evolution**: Establish processes for updating baselines as infrastructure evolves

---

## Getting Help

- **Documentation**: See full documentation in the repository
- **Issues**: Report issues at https://github.com/your-org/aws-audit/issues
- **Examples**: Check `examples/` directory for more use cases

---

## Summary of Commands

Quick reference of most-used commands:

```bash
# Snapshot management
aws-audit snapshot create [NAME]
aws-audit snapshot list
aws-audit snapshot show NAME
aws-audit snapshot set-active NAME

# Tracking changes
aws-audit delta
aws-audit delta --export report.json

# Cost analysis
aws-audit cost
aws-audit cost --group-by Project --export costs.csv

# Restoration
aws-audit restore --dry-run
aws-audit restore
```

---

**Congratulations!** You've completed the quickstart guide. You're now ready to track your AWS infrastructure changes and costs effectively.
