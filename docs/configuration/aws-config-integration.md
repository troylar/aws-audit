# AWS Config Integration

When [AWS Config](https://aws.amazon.com/config/) is enabled, the tool automatically uses it for faster resource collection.

## Why Use AWS Config?

| Method | 500 Resources | 2000 Resources |
|--------|---------------|----------------|
| Direct API calls | ~45 seconds | ~3 minutes |
| AWS Config | ~8 seconds | ~20 seconds |

AWS Config maintains an indexed inventory of your resources. Instead of calling 27 different AWS service APIs, we query Config's pre-built index.

## How It Works

```
For each region:
  1. Check if AWS Config is enabled and recording
  2. For each resource type:
     +-- Config supports it? -> Query Config API (fast)
     +-- Config doesn't support it? -> Call service API directly (Route53, WAF, etc.)
  3. Merge results into unified snapshot
```

**No configuration required.** The tool detects Config availability automatically and falls back gracefully.

## Usage

```bash
# Default behavior: Use Config when available (recommended)
awsinv snapshot create my-snapshot --regions us-east-1

# Force direct API only (skip Config, useful for debugging)
awsinv snapshot create my-snapshot --regions us-east-1 --no-config

# Multi-account via Config Aggregator
awsinv snapshot create org-snapshot --config-aggregator my-org-aggregator
```

## Source Tracking

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

## Requirements

To benefit from Config integration:

1. **AWS Config enabled** in target region(s)
2. **Configuration Recorder** actively recording
3. **Resource types being recorded** (either "all supported types" or specific types)

If these aren't met, the tool falls back to direct API calls automatically.

## Verifying Config Status

```bash
awsinv config check --regions us-east-1
awsinv config check --regions us-east-1 --verbose  # Shows per-type breakdown
```
