# Query & Analysis

Search and analyze resources across snapshots using SQL or built-in filters.

## Raw SQL Queries

```bash
# Run any SQL query against the resource database
awsinv query sql "SELECT resource_type, COUNT(*) FROM resources GROUP BY resource_type"

# Output formats
awsinv query sql "SELECT * FROM resources LIMIT 10" --format table
awsinv query sql "SELECT * FROM resources LIMIT 10" --format json
awsinv query sql "SELECT * FROM resources LIMIT 10" --format csv
```

!!! tip
    Use the `--snapshot` flag or `AWSINV_SNAPSHOT_ID` environment variable to automatically filter queries to a specific snapshot.

## Search Resources

```bash
# Filter by type
awsinv query resources --type "AWS::S3::Bucket"

# Filter by region
awsinv query resources --region us-east-1

# Filter by tag
awsinv query resources --tag "Environment=prod"

# Combine filters
awsinv query resources --type "AWS::EC2::Instance" --region us-east-1 --tag "team=platform"

# Limit results
awsinv query resources --limit 20
```

## Resource History

Track a single resource across all snapshots:

```bash
awsinv query history "arn:aws:s3:::my-bucket"
```

## Statistics

```bash
# Group by type
awsinv query stats --group-by type

# Group by region
awsinv query stats --group-by region

# Group by service
awsinv query stats --group-by service

# For a specific snapshot
awsinv query stats --snapshot my-baseline --group-by type
```

## Snapshot Diff

Compare resources between two snapshots:

```bash
awsinv query diff snap-before snap-after

# Filter to specific type
awsinv query diff snap-before snap-after --type "AWS::EC2::Instance"
```

## Example Queries

For 33 power-user SQL queries covering tagging compliance, cost optimization, security auditing, and more, see the [Database Reference](../reference/database.md).
