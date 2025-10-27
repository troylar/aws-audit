# CLI Command Contracts: AWS Baseline Snapshot

**Feature**: 001-aws-baseline-snapshot
**Date**: 2025-10-26
**Phase**: 1 - Design

## Overview

This document specifies the command-line interface for the AWS Baseline Snapshot tool. All commands follow the pattern: `aws-baseline <command> [subcommand] [options] [arguments]`

---

## Command Structure

```
aws-baseline
├── snapshot        # Snapshot management
│   ├── create
│   ├── list
│   ├── show
│   ├── set-active
│   └── delete
├── delta           # Resource delta tracking
├── cost            # Cost analysis
└── restore         # Restore to baseline
```

---

## Global Options

Available for all commands:

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--profile` | `-p` | string | default | AWS profile name from ~/.aws/config |
| `--region` | `-r` | string | All enabled | AWS region(s) for operations |
| `--verbose` | `-v` | flag | False | Enable verbose logging |
| `--quiet` | `-q` | flag | False | Suppress all output except errors |
| `--no-color` | | flag | False | Disable colored output |
| `--output` | `-o` | enum | table | Output format: table, json, yaml |
| `--help` | `-h` | flag | | Show help and exit |
| `--version` | | flag | | Show version and exit |

---

## 1. Snapshot Commands

### 1.1 `snapshot create`

Create a new baseline snapshot of current AWS resources.

**Syntax**:
```bash
aws-baseline snapshot create [OPTIONS] [NAME]
```

**Arguments**:

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `NAME` | string | No | Snapshot name (default: auto-generated from timestamp) |

**Options**:

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--regions` | | string | All enabled | Comma-separated list of regions (e.g., "us-east-1,us-west-2") |
| `--resource-types` | | string | All supported | Comma-separated list of resource types to include (e.g., "iam,lambda,ec2") |
| `--exclude-types` | | string | None | Comma-separated list of resource types to exclude |
| `--set-active` | | flag | True | Set this snapshot as active baseline |
| `--compress` | | flag | False | Compress snapshot with gzip |
| `--metadata` | `-m` | string | None | JSON string of metadata to attach |
| `--parallel` | | int | 10 | Number of parallel API calls |
| `--before-date` | | date | None | Include only resources created before this date (YYYY-MM-DD, UTC) |
| `--after-date` | | date | None | Include only resources created on or after this date (YYYY-MM-DD, UTC) |
| `--between-dates` | | string | None | Include only resources created between dates (YYYY-MM-DD,YYYY-MM-DD, UTC) |
| `--filter-tags` | | string | None | Include only resources with specified tags (format: "Key=Value" or "Key1=Value1,Key2=Value2" for multiple) |

**Output**:
- Progress bars showing collection by region/service
- Summary table of resources collected
- Snapshot file path
- Total execution time

**Exit Codes**:
- `0`: Success
- `1`: Partial failure (some services failed, see warnings)
- `2`: Complete failure (no resources collected)
- `3`: AWS credential/permission error

**Examples**:

```bash
# Create baseline snapshot with default name
aws-baseline snapshot create

# Create named snapshot for specific regions
aws-baseline snapshot create prod-baseline --regions us-east-1,us-west-2

# Create snapshot for specific resource types only
aws-baseline snapshot create iam-only --resource-types iam,lambda

# Create compressed snapshot without setting as active
aws-baseline snapshot create archive-2025 --compress --set-active=false

# Create with metadata
aws-baseline snapshot create --metadata '{"purpose":"Q4 baseline","created_by":"admin"}'

# Historical baseline: capture only resources created before deployment date
aws-baseline snapshot create pre-deployment-baseline --before-date 2025-10-15

# Capture resources created after a specific date (new resources)
aws-baseline snapshot create new-resources --after-date 2025-10-15

# Capture resources created in a specific time period
aws-baseline snapshot create october-resources --between-dates 2025-10-01,2025-10-31

# Create baseline from tagged resources only
aws-baseline snapshot create tagged-baseline --filter-tags Baseline=true

# Combine date and tag filters
aws-baseline snapshot create prod-baseline --before-date 2025-10-15 --filter-tags Environment=production

# Multiple tag filters (AND logic - resource must have ALL tags)
aws-baseline snapshot create terraform-baseline --filter-tags ManagedBy=terraform,Baseline=true

# Complex filtering: tagged production resources created before date
aws-baseline snapshot create prod-historical \
  --before-date 2025-10-01 \
  --filter-tags Environment=production,Team=platform \
  --regions us-east-1,us-west-2
```

**Output Example (Unfiltered)**:
```
Creating snapshot: baseline-2025-10-26

Collecting resources...
us-east-1  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% (10/10 services) 0:01:23
us-west-2  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% (10/10 services) 0:01:15

✓ Snapshot complete!

Summary:
┏━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━┓
┃ Service       ┃ Region ┃ Resources┃ Status   ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━┩
│ IAM           │ global │ 45       │ ✓        │
│ Lambda        │ all    │ 18       │ ✓        │
│ EC2           │ all    │ 245      │ ✓        │
│ S3            │ global │ 12       │ ✓        │
│ RDS           │ all    │ 6        │ ✓        │
└───────────────┴────────┴──────────┴──────────┘

Total resources: 456
Snapshot saved: .snapshots/baseline-2025-10-26.yaml
Active baseline: baseline-2025-10-26
Duration: 2m 38s
```

**Output Example (With Date/Tag Filtering)**:
```
Creating snapshot: prod-historical
Filters: --before-date 2025-10-01 --filter-tags Environment=production

Collecting resources...
us-east-1  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% (10/10 services) 0:01:23
us-west-2  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% (10/10 services) 0:01:15

Applying filters...
  Resources collected: 456
  Date filter (before 2025-10-01): 342 matched
  Tag filter (Environment=production): 298 matched
  Final (both filters): 287 matched

✓ Snapshot complete!

Summary:
┏━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━┓
┃ Service       ┃ Region ┃ Resources┃ Status   ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━┩
│ IAM           │ global │ 45       │ ✓        │
│ Lambda        │ all    │ 18       │ ✓        │
│ EC2           │ all    │ 245      │ ✓        │
│ S3            │ global │ 12       │ ✓        │
│ RDS           │ all    │ 6        │ ✓        │
└───────────────┴────────┴──────────┴──────────┘

Total resources: 456
Snapshot saved: .snapshots/baseline-2025-10-26.yaml
Active baseline: baseline-2025-10-26
Duration: 2m 38s
```

---

### 1.2 `snapshot list`

List all available snapshots.

**Syntax**:
```bash
aws-baseline snapshot list [OPTIONS]
```

**Options**:

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--sort-by` | | enum | created | Sort by: name, created, resources, size |
| `--reverse` | | flag | False | Reverse sort order |

**Output**:
Table of snapshots with name, creation date, resource count, active status, size.

**Exit Codes**:
- `0`: Success
- `1`: No snapshots found

**Examples**:

```bash
# List all snapshots
aws-baseline snapshot list

# List sorted by resource count
aws-baseline snapshot list --sort-by resources --reverse
```

**Output Example**:
```
┏━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━┳━━━━━━━━┓
┃ Name                   ┃ Created            ┃ Resources┃ Active┃ Size   ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━╇━━━━━━━━┩
│ baseline-2025-10-26    │ 2025-10-26 10:30   │ 456      │ ✓     │ 8.2 MB │
│ baseline-2025-10-20    │ 2025-10-20 08:15   │ 442      │       │ 7.9 MB │
│ prod-baseline          │ 2025-10-15 12:00   │ 438      │       │ 7.8 MB │
└────────────────────────┴────────────────────┴──────────┴───────┴────────┘

Total snapshots: 3
```

---

### 1.3 `snapshot show`

Display detailed information about a snapshot.

**Syntax**:
```bash
aws-baseline snapshot show NAME [OPTIONS]
```

**Arguments**:

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `NAME` | string | Yes | Snapshot name to display |

**Options**:

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--resources` | | flag | False | Include full resource list |
| `--group-by` | | enum | service | Group resources by: service, region, type |

**Output**:
Detailed snapshot metadata, resource counts by service/region, optionally full resource list.

**Exit Codes**:
- `0`: Success
- `1`: Snapshot not found

**Examples**:

```bash
# Show snapshot summary
aws-baseline snapshot show baseline-2025-10-26

# Show with full resource list grouped by region
aws-baseline snapshot show baseline-2025-10-26 --resources --group-by region
```

**Output Example**:
```
Snapshot: baseline-2025-10-26
Created: 2025-10-26 10:30:00 UTC
Account: 123456789012
Regions: us-east-1, us-west-2, eu-west-1
Status: Active baseline
Total resources: 456

Resources by service:
┏━━━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━┓
┃ Service      ┃ Count   ┃ Percent  ┃
┡━━━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━┩
│ EC2          │ 245     │ 53.7%    │
│ CloudWatch   │ 98      │ 21.5%    │
│ IAM          │ 52      │ 11.4%    │
│ Lambda       │ 18      │ 3.9%     │
│ SNS          │ 15      │ 3.3%     │
│ S3           │ 12      │ 2.6%     │
│ SQS          │ 10      │ 2.2%     │
│ RDS          │ 6       │ 1.3%     │
└──────────────┴─────────┴──────────┘

Metadata:
  creator: admin@example.com
  purpose: Q4 2025 production baseline
  created_by_tool: aws-baseline-snapshot v1.0.0
```

---

### 1.4 `snapshot set-active`

Set a snapshot as the active baseline.

**Syntax**:
```bash
aws-baseline snapshot set-active NAME
```

**Arguments**:

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `NAME` | string | Yes | Snapshot name to set as active |

**Output**:
Confirmation message with previous and new active baseline.

**Exit Codes**:
- `0`: Success
- `1`: Snapshot not found

**Examples**:

```bash
aws-baseline snapshot set-active prod-baseline
```

**Output Example**:
```
✓ Active baseline changed
  Previous: baseline-2025-10-26
  Current:  prod-baseline
```

---

### 1.5 `snapshot delete`

Delete a snapshot.

**Syntax**:
```bash
aws-baseline snapshot delete NAME [OPTIONS]
```

**Arguments**:

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `NAME` | string | Yes | Snapshot name to delete |

**Options**:

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--yes` | `-y` | flag | False | Skip confirmation prompt |

**Output**:
Confirmation prompt (unless `--yes`), then deletion confirmation.

**Exit Codes**:
- `0`: Success
- `1`: Snapshot not found
- `2`: Cannot delete active snapshot (must set another active first)
- `3`: User cancelled deletion

**Examples**:

```bash
# Delete with confirmation
aws-baseline snapshot delete old-baseline

# Delete without confirmation
aws-baseline snapshot delete old-baseline --yes
```

**Output Example**:
```
⚠ Warning: This will permanently delete snapshot 'old-baseline' (442 resources)
Continue? [y/N]: y

✓ Snapshot deleted: old-baseline
```

---

## 2. Delta Command

### 2.1 `delta`

Show resource changes since baseline snapshot.

**Syntax**:
```bash
aws-baseline delta [OPTIONS]
```

**Options**:

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--snapshot` | `-s` | string | Active | Snapshot name to compare against |
| `--resource-type` | | string | All | Filter by resource type (e.g., "lambda") |
| `--change-type` | | enum | All | Filter by: added, deleted, modified, all |
| `--region` | `-r` | string | All | Filter by region |
| `--since` | | date | None | Show resources created since date (YYYY-MM-DD) |
| `--export` | `-e` | path | None | Export delta report to file (JSON/CSV based on extension) |
| `--show-details` | | flag | False | Show detailed configuration changes for modified resources |

**Output**:
Delta report with added/deleted/modified resources grouped by type.

**Exit Codes**:
- `0`: Success (changes detected)
- `1`: No baseline snapshot found
- `2`: No changes detected

**Examples**:

```bash
# Show all changes since active baseline
aws-baseline delta

# Show only added Lambda functions
aws-baseline delta --resource-type lambda --change-type added

# Show changes in us-east-1 only
aws-baseline delta --region us-east-1

# Export delta to JSON
aws-baseline delta --export delta-report.json

# Show detailed changes for modified resources
aws-baseline delta --change-type modified --show-details
```

**Output Example**:
```
Delta Report
Baseline: baseline-2025-10-26 (created 2025-10-26 10:30)
Current:  2025-10-27 14:30

Summary:
  Added:     8 resources
  Deleted:   2 resources
  Modified:  3 resources
  Unchanged: 443 resources

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Added Resources (8):

Lambda Functions (3):
  ✓ new-experiment-function (us-east-1)
    Created: 2025-10-27 10:00
    Tags: Project=experiment

  ✓ data-processor (us-west-2)
    Created: 2025-10-27 12:30
    Tags: Project=analytics

  ✓ api-handler (us-east-1)
    Created: 2025-10-27 13:15

EC2 Instances (5):
  ✓ i-0123456789abcdef0 (us-east-1)
    Created: 2025-10-27 08:00
    Type: t3.medium
    Tags: Environment=dev, Project=test

  [... 4 more instances ...]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Deleted Resources (2):

IAM Roles (2):
  ✗ old-lambda-role (global)
    Last seen: 2025-10-26 10:30

  ✗ deprecated-service-role (global)
    Last seen: 2025-10-26 10:30

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Modified Resources (3):

IAM Policies (3):
  ⟳ baseline-execution-policy (global)
    Changes: Policy document updated (permissions added)

  ⟳ lambda-invoke-policy (global)
    Changes: Attached to 2 additional roles

  ⟳ s3-access-policy (global)
    Changes: Resource ARN list modified

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## 3. Cost Command

### 3.1 `cost`

Analyze costs separating baseline vs. non-baseline resources.

**Syntax**:
```bash
aws-baseline cost [OPTIONS]
```

**Options**:

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--snapshot` | `-s` | string | Active | Snapshot name to use as baseline |
| `--start-date` | | date | 30 days ago | Start of cost analysis period (YYYY-MM-DD) |
| `--end-date` | | date | Today | End of cost analysis period (YYYY-MM-DD) |
| `--granularity` | `-g` | enum | daily | Granularity: daily, monthly |
| `--group-by` | | string | None | Group non-baseline costs by tag (e.g., "Project") |
| `--export` | `-e` | path | None | Export cost report to file (JSON/CSV based on extension) |
| `--currency` | | string | USD | Currency code |

**Output**:
Cost report with baseline vs. non-baseline breakdown, totals, and optional groupings.

**Exit Codes**:
- `0`: Success
- `1`: No baseline snapshot found
- `2`: Cost data not available (Cost Explorer not enabled or insufficient permissions)
- `3`: Requested period outside available data range

**Examples**:

```bash
# Show cost breakdown for last 30 days
aws-baseline cost

# Show October 2025 costs
aws-baseline cost --start-date 2025-10-01 --end-date 2025-10-31

# Group non-baseline costs by Project tag
aws-baseline cost --group-by Project

# Export to CSV for financial systems
aws-baseline cost --export october-costs.csv --start-date 2025-10-01 --end-date 2025-10-31

# Monthly granularity for trend analysis
aws-baseline cost --granularity monthly --start-date 2025-01-01 --end-date 2025-12-31
```

**Output Example**:
```
Cost Report
Baseline: baseline-2025-10-26 (created 2025-10-26 10:30)
Period:   2025-10-01 to 2025-10-31
Currency: USD

⚠ Data completeness: 93% (Cost data available through 2025-10-29)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Cost Summary:
┏━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━┓
┃ Category          ┃ Cost      ┃ Percent  ┃
┡━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━┩
│ Baseline          │ $576.25   │ 63.9%    │
│ Non-Baseline      │ $325.30   │ 36.1%    │
│ ─────────────────  │ ───────── │ ──────── │
│ Total             │ $901.55   │ 100%     │
└───────────────────┴───────────┴──────────┘

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Baseline Costs (Dial Tone):
┏━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━━┓
┃ Service      ┃ Cost     ┃ Resources     ┃
┡━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━━┩
│ EC2          │ $450.75  │ 8 instances   │
│ Lambda       │ $125.50  │ 12 functions  │
│ CloudWatch   │ $48.20   │ 98 alarms     │
│ S3           │ $32.10   │ 12 buckets    │
│ RDS          │ $18.50   │ 6 instances   │
│ SNS          │ $8.90    │ 15 topics     │
│ Other        │ $17.80   │ Various       │
└──────────────┴──────────┴───────────────┘

Non-Baseline Costs:
┏━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━━┓
┃ Service      ┃ Cost     ┃ Resources     ┃
┡━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━━┩
│ RDS          │ $280.00  │ 2 instances   │
│ Lambda       │ $45.30   │ 3 functions   │
│ EC2          │ $32.50   │ 5 instances   │
│ S3           │ $12.80   │ 2 buckets     │
│ Other        │ $9.20    │ Various       │
└──────────────┴──────────┴───────────────┘

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Estimated monthly cost (baseline): $576.25/month
Estimated monthly cost (non-baseline): $325.30/month
```

---

## 4. Restore Command

### 4.1 `restore`

Remove non-baseline resources to return to baseline state.

**Syntax**:
```bash
aws-baseline restore [OPTIONS]
```

**Options**:

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--snapshot` | `-s` | string | Active | Snapshot name to use as baseline |
| `--dry-run` | | flag | False | Show what would be deleted without deleting |
| `--resource-type` | | string | All | Restrict deletion to specific resource types |
| `--exclude` | | string | None | Comma-separated list of resource ARNs to preserve |
| `--exclude-tag` | | string | None | Preserve resources with tag (e.g., "Protect=true") |
| `--region` | `-r` | string | All | Restrict to specific region(s) |
| `--yes` | `-y` | flag | False | Skip confirmation prompt |
| `--continue-on-error` | | flag | True | Continue deleting other resources if one fails |

**Output**:
List of resources to be deleted, confirmation prompt, progress during deletion, summary of results.

**Exit Codes**:
- `0`: Success (all resources deleted or dry-run completed)
- `1`: Partial failure (some resources couldn't be deleted)
- `2`: Complete failure (no resources deleted)
- `3`: User cancelled operation
- `4`: No baseline snapshot found

**Examples**:

```bash
# Dry-run to see what would be deleted
aws-baseline restore --dry-run

# Delete only Lambda functions added since baseline
aws-baseline restore --resource-type lambda

# Restore but preserve resources tagged with Protect=true
aws-baseline restore --exclude-tag Protect=true

# Restore without confirmation (careful!)
aws-baseline restore --yes

# Restore specific region only
aws-baseline restore --region us-east-1
```

**Output Example (Dry-Run)**:
```
Restore to Baseline (DRY RUN)
Baseline: baseline-2025-10-26 (created 2025-10-26 10:30)

⚠ This operation will DELETE the following resources:

Lambda Functions (3):
  ✗ new-experiment-function (us-east-1)
  ✗ data-processor (us-west-2)
  ✗ api-handler (us-east-1)

EC2 Instances (5):
  ✗ i-0123456789abcdef0 (us-east-1)
  ✗ i-0123456789abcdef1 (us-east-1)
  ✗ i-0123456789abcdef2 (us-west-2)
  ✗ i-0123456789abcdef3 (us-west-2)
  ✗ i-0123456789abcdef4 (us-west-2)

RDS Instances (2):
  ✗ project-a-db (us-east-1)
  ✗ analytics-db (us-west-2)

S3 Buckets (2):
  ✗ experiment-data-bucket
  ✗ temp-storage-bucket

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Total resources to delete: 12
Estimated cost savings: $325.30/month

ℹ This is a DRY RUN - no resources will be deleted.
  Run without --dry-run to perform actual deletion.
```

**Output Example (Actual Restore)**:
```
Restore to Baseline
Baseline: baseline-2025-10-26 (created 2025-10-26 10:30)

⚠ WARNING: This will PERMANENTLY DELETE 12 resources!
  Review the list carefully. This operation cannot be undone.

[... resource list ...]

Continue with deletion? Type 'DELETE' to confirm: DELETE

Deleting resources (dependency-ordered)...

Lambda Functions  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% (3/3)   ✓
EC2 Instances     ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% (5/5)   ✓
RDS Instances     ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% (2/2)   ✓
S3 Buckets        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% (2/2)   ✓

Restoration Summary:
┏━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━┓
┃ Resource Type┃ Attempted┃ Succeeded┃ Failed   ┃
┡━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━┩
│ Lambda       │ 3        │ 3        │ 0        │
│ EC2          │ 5        │ 5        │ 0        │
│ RDS          │ 2        │ 2        │ 0        │
│ S3           │ 2        │ 2        │ 0        │
│ ────────────  │ ──────── │ ──────── │ ──────── │
│ Total        │ 12       │ 12       │ 0        │
└──────────────┴──────────┴──────────┴──────────┘

✓ Restoration complete!
  Duration: 3m 45s
  Environment now matches baseline: baseline-2025-10-26
```

---

## 5. Version & Help

### 5.1 `--version`

Display tool version information.

**Syntax**:
```bash
aws-baseline --version
```

**Output Example**:
```
aws-baseline-snapshot version 1.0.0
Python 3.11.5
boto3 1.28.85
```

---

### 5.2 `--help`

Display help for any command.

**Syntax**:
```bash
aws-baseline [command] [subcommand] --help
```

**Examples**:
```bash
aws-baseline --help
aws-baseline snapshot --help
aws-baseline snapshot create --help
aws-baseline delta --help
```

---

## Exit Code Summary

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | General error (snapshot not found, no changes, etc.) |
| `2` | Operation failed (can't create snapshot, can't delete resources, etc.) |
| `3` | User cancelled operation or permission error |
| `4` | Configuration error (no baseline, AWS Config issues) |

---

## Error Handling

All commands follow consistent error handling:

1. **AWS Credential Errors**: Clear message directing to `aws configure` or profile setup
2. **Permission Errors**: List required IAM permissions for the operation
3. **Rate Limiting**: Automatically retried, progress indicator shows throttling status
4. **Partial Failures**: Operation continues, warnings logged, summary shows failures
5. **Invalid Arguments**: Clear error message with examples of correct usage

**Error Example**:
```
✗ Error: AWS credentials not found

Please configure AWS credentials using one of these methods:
  1. Run: aws configure
  2. Set environment variables: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
  3. Use --profile option with a configured profile

For more info: https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-files.html
```

---

## Output Formats

### Table Format (Default)
- Human-readable tables using rich library
- Colored output for status indicators
- Progress bars for long operations

### JSON Format
- Machine-readable JSON output
- Suitable for scripting and automation
- Disabled progress bars/colors

### YAML Format
- Human-readable YAML output
- Useful for configuration management
- Disabled progress bars/colors

**Example JSON Output**:
```bash
aws-baseline delta --output json
```

```json
{
  "generated_at": "2025-10-27T14:30:00Z",
  "snapshot_name": "baseline-2025-10-26",
  "snapshot_timestamp": "2025-10-26T10:30:00Z",
  "added_resources": [...],
  "deleted_resources": [...],
  "modified_resources": [...],
  "unchanged_count": 443
}
```

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `AWS_PROFILE` | AWS profile name | default |
| `AWS_REGION` | Default AWS region | None (all enabled regions) |
| `AWS_BASELINE_SNAPSHOT_DIR` | Snapshot storage directory | ./.snapshots |
| `AWS_BASELINE_LOG_LEVEL` | Log level (DEBUG, INFO, WARN, ERROR) | INFO |
| `NO_COLOR` | Disable colored output (any value) | Not set |

---

## Configuration File

Optional configuration file: `.aws-baseline.yaml` (in current directory or `~/.aws-baseline.yaml`)

```yaml
# Default snapshot directory
snapshot_dir: /path/to/snapshots

# Default regions to include
regions:
  - us-east-1
  - us-west-2

# Default resource types to include/exclude
resource_types:
  include:
    - iam
    - lambda
    - ec2
    - s3
  exclude:
    - cloudformation

# AWS profile to use
aws_profile: production

# Parallel API calls
parallel_workers: 10

# Auto-compress snapshots over this size
auto_compress_mb: 10

# Cost Explorer settings
cost:
  currency: USD
  default_period_days: 30
```

---

## Next Steps

1. ✅ CLI contracts complete
2. → Implement CLI using Typer framework
3. → Add command validators and error handling
4. → Create comprehensive help text
5. → Proceed to quickstart guide creation
