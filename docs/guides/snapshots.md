# Snapshots

Snapshots are the foundation of AWS Inventory Manager. A snapshot captures a point-in-time inventory of your AWS resources.

## Creating Snapshots

```bash
# Basic snapshot
awsinv snapshot create my-baseline --region us-east-1

# Multi-region
awsinv snapshot create my-baseline --region us-east-1,us-west-2

# Filter by service
awsinv snapshot create my-baseline --region us-east-1 --type ec2,s3,lambda

# Filter by tag
awsinv snapshot create my-baseline --region us-east-1 --include-tags "env=prod"

# Assign to inventory group
awsinv snapshot create my-baseline --region us-east-1 --inventory prod-baseline

# Track who created each resource
awsinv snapshot create my-baseline --region us-east-1 --track-creators

# Collect Lambda deployment code
awsinv snapshot create my-baseline --region us-east-1 --lambda-code-max-size 50
```

## Listing Snapshots

```bash
awsinv snapshot list
```

## Viewing Snapshot Reports

```bash
# Summary
awsinv snapshot report --snapshot my-baseline

# Detailed (all resources)
awsinv snapshot report --snapshot my-baseline --detailed

# Export report
awsinv snapshot report --snapshot my-baseline --output report.json
```

## Enriching Snapshots

Add creator information to an existing snapshot:

```bash
awsinv snapshot enrich-creators my-baseline --days-back 90
```

## Exporting Snapshots

```bash
# Export to JSON
awsinv snapshot export my-baseline -o inventory.json

# Export to CSV
awsinv snapshot export my-baseline -o inventory.csv

# Export to YAML
awsinv snapshot export my-baseline -o inventory.yaml

# Filter exports
awsinv snapshot export my-baseline -o filtered.json \
  --type AWS::S3::Bucket \
  --region us-east-1 \
  --tag "env=prod"
```

## Managing Snapshots

```bash
# Rename a snapshot
awsinv snapshot rename old-name new-name

# Delete a snapshot
awsinv snapshot delete my-snapshot

# Set active snapshot
awsinv snapshot set-active my-baseline
```
