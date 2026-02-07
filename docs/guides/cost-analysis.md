# Cost Analysis

Track AWS spending with date ranges, service breakdowns, and tag-based attribution via AWS Cost Explorer.

## Basic Cost Analysis

```bash
# Cost for current period
awsinv cost

# With date range
awsinv cost --start-date 2026-01-01 --end-date 2026-01-31

# Service-level breakdown
awsinv cost --show-services
```

## Cost Attribution by Team

```bash
# Snapshot resources per team using tag filters
awsinv snapshot create team-platform --include-tags "team=platform"
awsinv snapshot create team-data --include-tags "team=data"

# Compare costs
awsinv cost --snapshot team-platform
awsinv cost --snapshot team-data
```

## Requirements

The `cost` command requires IAM permissions for AWS Cost Explorer:

```json
{
  "Effect": "Allow",
  "Action": [
    "ce:GetCostAndUsage",
    "ce:GetCostForecast"
  ],
  "Resource": "*"
}
```

See [IAM Permissions](../reference/iam-permissions.md) for the full policy.
