# Your First Snapshot

This tutorial walks you through creating your first inventory snapshot, viewing what was captured, and comparing changes over time.

## Key Concepts

| Term | Meaning |
|------|---------|
| **Snapshot** | A point-in-time inventory of your AWS resources (stored in local SQLite database). Not an EBS/RDS snapshot. |
| **Inventory** | A named collection of snapshots. Use inventories to organize snapshots by environment, team, or purpose. |
| **Cleanup** | Delete resources that were created *after* a snapshot, returning to that baseline state. |
| **Purge** | Delete all resources *except* those matching protection rules. Filter by creator or date range. |
| **Query** | Search and analyze resources across snapshots using SQL or built-in filters. |

## Step 1: Create a Snapshot

Capture the current state of your AWS resources:

```bash
awsinv snapshot create my-baseline --region us-east-1
```

This takes 30--60 seconds depending on resource count. The tool scans 27 AWS services and catalogs 80+ resource types.

!!! tip
    If you have [AWS Config](../configuration/aws-config-integration.md) enabled, collection can be up to 5x faster. The tool detects it automatically.

## Step 2: View What Was Captured

```bash
awsinv snapshot report
```

Output:

```
+------------------------------------------+
| Snapshot: my-baseline                    |
| Resources: 127                           |
| Regions: us-east-1                       |
+------------------------------------------+
| EC2 Instances:     12                    |
| S3 Buckets:        8                     |
| Lambda Functions:  23                    |
| IAM Roles:         45                    |
| ...                                      |
+------------------------------------------+
```

For a detailed view of all resources:

```bash
awsinv snapshot report --detailed
```

## Step 3: Track Changes

After making changes to your AWS environment, compare against your baseline:

```bash
awsinv delta --snapshot my-baseline --show-diff
```

This shows:

- New resources created since the snapshot
- Resources that were deleted
- Configuration changes (field-level diff)

## Step 4: Export Your Snapshot

Export data for external analysis:

```bash
# Export to JSON
awsinv snapshot export my-baseline -o inventory.json

# Export to CSV
awsinv snapshot export my-baseline -o inventory.csv

# Export to YAML
awsinv snapshot export my-baseline -o inventory.yaml
```

## Next Steps

- [Common Workflows](common-workflows.md) -- practical scenarios for daily use
- [Snapshots guide](../guides/snapshots.md) -- advanced snapshot features
- [Change Tracking](../guides/change-tracking.md) -- deep-dive into delta analysis
- [Security Scanning](../guides/security-scanning.md) -- find security issues
