# Data Model: AWS Baseline Snapshot & Delta Tracking

**Feature**: 001-aws-baseline-snapshot
**Date**: 2025-10-26
**Phase**: 1 - Design

## Overview

This document defines the core data models for the AWS Baseline Snapshot tool. These models represent the domain entities and their relationships.

---

## Core Entities

### 1. Snapshot

Represents a point-in-time inventory of AWS resources, serving as the baseline reference for delta tracking and cost analysis.

**Fields**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Unique identifier for the snapshot (e.g., "baseline-2025-10-26") |
| `created_at` | datetime | Yes | ISO 8601 timestamp when snapshot was created |
| `account_id` | string | Yes | AWS account ID (12-digit string) |
| `regions` | list[string] | Yes | List of AWS regions included in snapshot (e.g., ["us-east-1", "us-west-2"]) |
| `resources` | list[Resource] | Yes | List of captured resources |
| `metadata` | dict | No | Optional metadata (creator, tags, notes) |
| `is_active` | boolean | Yes | Whether this is the currently active baseline (default: True for new snapshots) |
| `resource_count` | int | Yes | Total number of resources (derived field for quick display) |
| `service_counts` | dict[string, int] | Yes | Count by service type (e.g., {"iam": 45, "lambda": 12}) |
| `filters_applied` | dict | No | Filters used during snapshot creation (date_filters, tag_filters) |
| `total_resources_before_filter` | int | No | Count of resources before filters were applied (for filtering transparency) |

**Validation Rules**:
- `name` must be unique across all snapshots
- `name` must match pattern: `^[a-zA-Z0-9_-]+$` (alphanumeric, hyphens, underscores)
- `account_id` must be 12-digit string
- `regions` must contain at least one valid AWS region
- Only one snapshot can have `is_active = True` at a time

**Relationships**:
- Contains many `Resource` objects (one-to-many)
- Referenced by `DeltaReport` objects (one-to-many)

**State Transitions**:
- New snapshot: `is_active = True`, all other snapshots become `is_active = False`
- Set active: Target snapshot `is_active = True`, others become `False`
- Delete: Cannot delete if `is_active = True`

**Storage Format** (YAML):
```yaml
name: baseline-2025-10-26
created_at: 2025-10-26T10:30:00Z
account_id: "123456789012"
regions:
  - us-east-1
  - us-west-2
is_active: true
resource_count: 342
service_counts:
  iam: 45
  lambda: 12
  ec2: 180
  s3: 8
metadata:
  creator: admin@example.com
  purpose: Production baseline after Q4 2025 deployment
filters_applied:
  date_filters:
    before_date: null
    after_date: null
  tag_filters: []
total_resources_before_filter: 342
resources:
  - # Resource objects...
```

---

### 2. Resource

Represents a single AWS resource captured in a snapshot.

**Fields**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `arn` | string | Yes | Amazon Resource Name (unique identifier) |
| `type` | string | Yes | Resource type (format: "service:resource", e.g., "iam:role") |
| `name` | string | Yes | Human-readable resource name |
| `region` | string | Yes | AWS region (or "global" for IAM, S3, etc.) |
| `tags` | dict[string, string] | No | AWS resource tags (key-value pairs) |
| `config_hash` | string | Yes | SHA256 hash of normalized configuration (for change detection) |
| `created_at` | datetime | No | Resource creation timestamp (if available from AWS) |
| `raw_config` | dict | Yes | Full boto3 API response for the resource (stored for detailed inspection) |

**Validation Rules**:
- `arn` must be unique within a snapshot
- `arn` must match AWS ARN format: `^arn:aws:[a-z0-9-]+:[a-z0-9-]*:[0-9]+:.*$`
- `type` must be in supported resource types list
- `config_hash` must be 64-character hex string (SHA256 output)
- `region` must be valid AWS region or "global"

**Relationships**:
- Belongs to one `Snapshot` (many-to-one)
- May reference other `Resource` objects via `ResourceDependency` (many-to-many)

**Storage Format** (YAML, within Snapshot):
```yaml
- arn: arn:aws:iam::123456789012:role/baseline-execution-role
  type: iam:role
  name: baseline-execution-role
  region: global
  tags:
    Environment: production
    ManagedBy: baseline
  config_hash: a1b2c3d4e5f6...
  created_at: 2025-10-01T00:00:00Z
  raw_config:
    RoleName: baseline-execution-role
    RoleId: AIDAI...
    AssumeRolePolicyDocument: {...}
    MaxSessionDuration: 3600
    # ... full boto3 response
```

---

### 3. DeltaReport

Represents the differences between current AWS state and a baseline snapshot.

**Fields**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `generated_at` | datetime | Yes | When this delta report was generated |
| `snapshot_name` | string | Yes | Name of baseline snapshot used for comparison |
| `snapshot_timestamp` | datetime | Yes | Timestamp of the baseline snapshot |
| `added_resources` | list[ResourceChange] | Yes | Resources created since baseline |
| `deleted_resources` | list[ResourceChange] | Yes | Baseline resources that no longer exist |
| `modified_resources` | list[ResourceChange] | Yes | Resources with configuration changes |
| `unchanged_count` | int | Yes | Count of resources unchanged since baseline |

**Validation Rules**:
- `snapshot_name` must reference an existing snapshot
- All change lists can be empty (no changes detected)

**Relationships**:
- References one `Snapshot` (many-to-one)

**Storage Format** (JSON, generated on-demand):
```json
{
  "generated_at": "2025-10-27T14:30:00Z",
  "snapshot_name": "baseline-2025-10-26",
  "snapshot_timestamp": "2025-10-26T10:30:00Z",
  "added_resources": [
    {
      "arn": "arn:aws:lambda:us-east-1:123456789012:function:new-function",
      "type": "lambda:function",
      "name": "new-function",
      "region": "us-east-1",
      "created_at": "2025-10-27T10:00:00Z",
      "tags": {"Project": "experiment"}
    }
  ],
  "deleted_resources": [
    {
      "arn": "arn:aws:iam::123456789012:role/old-role",
      "type": "iam:role",
      "name": "old-role",
      "region": "global",
      "last_seen_at": "2025-10-26T10:30:00Z"
    }
  ],
  "modified_resources": [
    {
      "arn": "arn:aws:iam::123456789012:role/updated-role",
      "type": "iam:role",
      "name": "updated-role",
      "region": "global",
      "baseline_hash": "abc123...",
      "current_hash": "def456...",
      "changes_summary": "Policy document updated"
    }
  ],
  "unchanged_count": 340
}
```

---

### 4. ResourceChange

Represents a single resource change (used within DeltaReport).

**Fields**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `arn` | string | Yes | Resource ARN |
| `type` | string | Yes | Resource type |
| `name` | string | Yes | Resource name |
| `region` | string | Yes | AWS region |
| `tags` | dict[string, string] | No | Current resource tags |
| `change_type` | enum | Yes | Type of change: "added", "deleted", "modified" |
| `created_at` | datetime | No | Creation timestamp (for added resources) |
| `last_seen_at` | datetime | No | Last seen timestamp (for deleted resources) |
| `baseline_hash` | string | No | Baseline config hash (for modified resources) |
| `current_hash` | string | No | Current config hash (for modified resources) |
| `changes_summary` | string | No | Human-readable summary of what changed |

**Validation Rules**:
- `change_type` must be one of: "added", "deleted", "modified"
- For "added": `created_at` should be present
- For "deleted": `last_seen_at` should be present
- For "modified": both `baseline_hash` and `current_hash` required

---

### 5. CostReport

Represents cost analysis for a time period, separating baseline vs. non-baseline costs.

**Fields**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `generated_at` | datetime | Yes | When this cost report was generated |
| `snapshot_name` | string | Yes | Baseline snapshot used for cost separation |
| `period_start` | date | Yes | Start of cost analysis period (YYYY-MM-DD) |
| `period_end` | date | Yes | End of cost analysis period (YYYY-MM-DD) |
| `baseline_costs` | list[CostItem] | Yes | Costs attributed to baseline resources |
| `non_baseline_costs` | list[CostItem] | Yes | Costs attributed to non-baseline resources |
| `baseline_total` | decimal | Yes | Total baseline costs (USD) |
| `non_baseline_total` | decimal | Yes | Total non-baseline costs (USD) |
| `total_costs` | decimal | Yes | Combined total costs (USD) |
| `cost_groupings` | dict[string, CostBreakdown] | No | Optional groupings by tag (e.g., by project) |
| `data_completeness` | dict | Yes | Indicators of data quality/freshness |

**Validation Rules**:
- `period_end` must be >= `period_start`
- `total_costs` must equal `baseline_total + non_baseline_total`
- All cost amounts must be non-negative

**Relationships**:
- References one `Snapshot` (many-to-one)

**Storage Format** (JSON):
```json
{
  "generated_at": "2025-10-27T14:30:00Z",
  "snapshot_name": "baseline-2025-10-26",
  "period_start": "2025-10-01",
  "period_end": "2025-10-31",
  "baseline_costs": [
    {
      "service": "Lambda",
      "amount": 125.50,
      "currency": "USD",
      "resource_count": 12
    },
    {
      "service": "EC2",
      "amount": 450.75,
      "currency": "USD",
      "resource_count": 8
    }
  ],
  "non_baseline_costs": [
    {
      "service": "Lambda",
      "amount": 45.30,
      "currency": "USD",
      "resource_count": 3
    },
    {
      "service": "RDS",
      "amount": 280.00,
      "currency": "USD",
      "resource_count": 2
    }
  ],
  "baseline_total": 576.25,
  "non_baseline_total": 325.30,
  "total_costs": 901.55,
  "cost_groupings": {
    "by_project": {
      "Project-A": 280.00,
      "Project-B": 45.30
    }
  },
  "data_completeness": {
    "data_available_through": "2025-10-25",
    "data_lag_days": 2,
    "completeness_percentage": 93,
    "warnings": ["Cost data for last 2 days is incomplete"]
  }
}
```

---

### 6. CostItem

Represents cost for a specific service or resource (used within CostReport).

**Fields**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `service` | string | Yes | AWS service name (e.g., "Lambda", "EC2") |
| `amount` | decimal | Yes | Cost amount |
| `currency` | string | Yes | Currency code (typically "USD") |
| `resource_count` | int | No | Number of resources contributing to this cost |
| `usage_type` | string | No | AWS usage type (for detailed analysis) |

---

### 7. CostBreakdown

Represents cost breakdown by a dimension (e.g., by tag value).

**Fields**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `dimension` | string | Yes | Dimension name (e.g., "Project", "Environment") |
| `breakdowns` | dict[string, decimal] | Yes | Cost by dimension value (e.g., {"Project-A": 280.00}) |

---

### 8. ResourceDependency

Represents a dependency relationship between two resources (used for restore ordering).

**Fields**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `resource_arn` | string | Yes | ARN of dependent resource |
| `depends_on_arn` | string | Yes | ARN of resource it depends on |
| `dependency_type` | string | Yes | Type of dependency (e.g., "ec2-instance-to-sg") |

**Validation Rules**:
- Both ARNs must exist in the resource inventory
- No circular dependencies allowed (validated during graph construction)

**Usage**:
- Not persisted in snapshot storage
- Computed dynamically during restore operations based on resource types
- Used to build dependency graph for topological sort

---

## Entity Relationships Diagram

```
┌─────────────┐
│  Snapshot   │
│             │
│ - name      │
│ - created_at│───────┐
│ - resources │       │ references
│             │       │
└─────────────┘       │
       │              │
       │ contains     │
       │              ▼
       ▼         ┌──────────────┐
┌─────────────┐  │ DeltaReport  │
│  Resource   │  │              │
│             │  │ - added      │
│ - arn       │  │ - deleted    │
│ - type      │  │ - modified   │
│ - config    │  │              │
└─────────────┘  └──────────────┘
       │
       │ referenced by
       │
       ▼
┌──────────────────┐
│ ResourceDependency│
│                  │
│ - resource_arn   │
│ - depends_on_arn │
└──────────────────┘

                    ┌─────────────┐
                    │ CostReport  │
                    │             │
                    │ - baseline_ │
                    │   costs     │
                    │ - non_base_ │
                    │   costs     │
                    └─────────────┘
                         │
                         │ contains
                         ▼
                    ┌─────────────┐
                    │  CostItem   │
                    │             │
                    │ - service   │
                    │ - amount    │
                    └─────────────┘
```

---

## Data Constraints Summary

### Uniqueness Constraints
- `Snapshot.name` must be unique across all snapshots
- `Resource.arn` must be unique within a snapshot (but can repeat across snapshots)
- Only one `Snapshot` can have `is_active = True` at a time

### Foreign Key Constraints
- `DeltaReport.snapshot_name` → `Snapshot.name`
- `CostReport.snapshot_name` → `Snapshot.name`
- `ResourceDependency.resource_arn` → `Resource.arn`
- `ResourceDependency.depends_on_arn` → `Resource.arn`

### Business Rules
- Cannot delete active snapshot (must set another as active first)
- Delta and cost reports reference immutable snapshots (snapshots never modified after creation)
- Cost reports require snapshot timestamp to be at least 48 hours old (Cost Explorer data lag)

---

## Storage Strategies

### Snapshot Storage
- **Format**: YAML files in `.snapshots/` directory
- **Naming**: `{snapshot_name}.yaml` or `{snapshot_name}.yaml.gz` (compressed)
- **Indexing**: `snapshots.yaml` index file listing all snapshots with metadata

### Delta Reports
- **Format**: JSON (generated on-demand, not persisted by default)
- **Export**: Can be exported to JSON or CSV for external analysis

### Cost Reports
- **Format**: JSON (generated on-demand, not persisted by default)
- **Export**: Can be exported to JSON or CSV for financial systems

### Active Snapshot Tracking
- **Format**: `.snapshots/active` file containing name of active snapshot
- **Atomicity**: Updated atomically during snapshot activation

---

## Example: Complete Snapshot

```yaml
name: baseline-prod-2025-10-26
created_at: 2025-10-26T10:30:00Z
account_id: "123456789012"
regions:
  - us-east-1
  - us-west-2
  - eu-west-1
is_active: true
resource_count: 456
service_counts:
  iam: 52
  lambda: 18
  ec2: 245
  s3: 12
  rds: 6
  cloudwatch: 98
  sns: 15
  sqs: 10
metadata:
  creator: admin@example.com
  purpose: Q4 2025 production baseline
  created_by_tool: aws-baseline-snapshot v1.0.0
resources:
  - arn: arn:aws:iam::123456789012:role/baseline-execution-role
    type: iam:role
    name: baseline-execution-role
    region: global
    tags:
      Environment: production
      ManagedBy: terraform
    config_hash: 1a2b3c4d5e6f7890abcdef1234567890abcdef1234567890abcdef1234567890
    created_at: 2025-10-01T00:00:00Z
    raw_config:
      Path: /
      RoleName: baseline-execution-role
      RoleId: AIDAI23456789EXAMPLE
      Arn: arn:aws:iam::123456789012:role/baseline-execution-role
      CreateDate: 2025-10-01T00:00:00Z
      AssumeRolePolicyDocument:
        Version: "2012-10-17"
        Statement:
          - Effect: Allow
            Principal:
              Service: lambda.amazonaws.com
            Action: sts:AssumeRole
      MaxSessionDuration: 3600
      Tags:
        - Key: Environment
          Value: production
        - Key: ManagedBy
          Value: terraform

  - arn: arn:aws:lambda:us-east-1:123456789012:function:baseline-processor
    type: lambda:function
    name: baseline-processor
    region: us-east-1
    tags:
      Environment: production
      Component: baseline
    config_hash: 9876543210fedcba9876543210fedcba9876543210fedcba9876543210fedcba
    created_at: 2025-10-05T12:00:00Z
    raw_config:
      FunctionName: baseline-processor
      FunctionArn: arn:aws:lambda:us-east-1:123456789012:function:baseline-processor
      Runtime: python3.11
      Role: arn:aws:iam::123456789012:role/baseline-execution-role
      Handler: main.handler
      CodeSize: 1024000
      Timeout: 300
      MemorySize: 512
      # ... additional Lambda config
```

---

## Next Steps

1. ✅ Data model design complete
2. → Implement Python dataclasses/models based on this schema
3. → Create serialization/deserialization logic (YAML ↔ Python objects)
4. → Build validation logic for constraints
5. → Proceed to CLI contracts design
