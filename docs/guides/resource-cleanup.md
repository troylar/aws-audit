# Resource Cleanup

The `cleanup` command has two modes for removing AWS resources.

## Execute Mode

Delete resources created *after* a baseline snapshot:

```bash
# Preview what would be deleted
awsinv cleanup preview my-baseline

# Execute (requires confirmation)
awsinv cleanup execute my-baseline --confirm
```

## Purge Mode

Delete *all* resources except those matching protection rules:

```bash
# Preview what would be deleted (everything except keep=true tagged resources)
awsinv cleanup purge --protect-tag "keep=true" --preview

# Execute
awsinv cleanup purge --protect-tag "keep=true" --confirm
```

## Purge by Creator/Date

Delete resources created by specific users or within date ranges:

```bash
# First, enrich a snapshot with creator information from CloudTrail
awsinv snapshot enrich-creators my-snapshot

# Preview resources created by a specific user
awsinv cleanup purge --from-snapshot my-snapshot --created-by "john.doe" --preview

# Preview resources created by a specific role
awsinv cleanup purge --from-snapshot my-snapshot --created-by "AWSReservedSSO_Developer" --preview

# Delete resources created after a specific date
awsinv cleanup purge --from-snapshot my-snapshot --created-after "2025-01-01" --confirm

# Delete resources created within a date range
awsinv cleanup purge --from-snapshot my-snapshot \
  --created-after "2025-01-01" --created-before "2025-01-15" --confirm

# Combine creator and date filters
awsinv cleanup purge --from-snapshot my-snapshot \
  --created-by "john" --created-after "2025-01-10" --preview
```

!!! note
    Creator/date filters require `--from-snapshot` with an enriched snapshot. The `--created-by` option does substring matching on the creator ARN.

## Exclusion Filters

Protect specific resources by name or tag pattern (supports wildcards):

```bash
# Exclude resources by name pattern (wildcards: * and ?)
awsinv cleanup purge --protect-tag "env=dev" --exclude-name "*-prod-*" --preview
awsinv cleanup purge --protect-tag "env=dev" -x "critical-*" -x "important-*" --preview

# Exclude resources by tag pattern
awsinv cleanup purge --protect-tag "env=dev" --exclude-tag "protected=yes" --preview
awsinv cleanup purge --protect-tag "env=dev" --exclude-tag "Name=*production*" --preview

# Exclude by tag key only (any value matches)
awsinv cleanup purge --protect-tag "env=dev" --exclude-tag "do-not-delete=*" --preview

# Combine name and tag exclusions (OR logic - excluded if ANY match)
awsinv cleanup purge --protect-tag "env=dev" \
  --exclude-name "*-prod-*" \
  --exclude-name "*-staging-*" \
  --exclude-tag "critical=true" \
  --preview
```

!!! note
    Exclusion filters use `*` (any characters) and `?` (single character) wildcards. Matching is case-insensitive.

## Protection Rules

Prevent accidental deletion of important resources:

```bash
# Protect by tag (OR logic - any match protects)
awsinv cleanup preview my-snapshot --protect-tag "env=prod" --protect-tag "keep=true"

# Filter to specific resource type (only delete this type)
awsinv cleanup preview my-snapshot --type AWS::EC2::Instance

# Use a config file for complex rules
awsinv cleanup preview my-snapshot --config .awsinv-cleanup.yaml
```

### Config File Example

`.awsinv-cleanup.yaml`:

```yaml
protection:
  # Tag-based protection (OR logic - any matching tag protects)
  tags:
    - key: env
      value: prod         # Protect production resources
    - key: keep
      value: "true"       # Protect explicitly marked resources
    - key: Owner
      value: "*"          # Protect anything with an Owner tag (any value)

  # Type-based protection
  types:
    - AWS::IAM::Role      # Never delete IAM roles
    - AWS::IAM::User      # Never delete IAM users
    - AWS::S3::Bucket     # Never delete S3 buckets

  # Age-based protection
  age_days_minimum: 7     # Keep resources older than 7 days
```

### Config File Schema

| Field | Type | Description |
|-------|------|-------------|
| `protection.tags[]` | Array | Tag key/value pairs. `value: "*"` matches any value. |
| `protection.types[]` | Array | Full resource type names (e.g., `AWS::EC2::Instance`) |
| `protection.age_days_minimum` | Integer | Protect resources older than N days |

## Safety Features

- **Preview mode**: Always see what would happen before execution
- **Confirmation required**: `--confirm` flag mandatory for destructive operations
- **Dependency ordering**: Deletes in correct order (instances before VPCs, etc.)
- **Audit logging**: Every deletion logged to `~/.snapshots/audit-logs/`

## Deletion Behavior Notes

Some resources have special deletion behavior:

| Resource | Behavior |
|----------|----------|
| **KMS Keys** | Scheduled for deletion (minimum 7-day wait, not immediate) |
| **S3 Buckets** | Automatically emptied before deletion (including versioned objects) |
| **IAM Roles** | Attached policies detached, instance profiles removed first |
| **Route53 Zones** | All records deleted except NS/SOA before zone deletion |

!!! note
    `cleanup execute` compares to a snapshot and deletes newer resources. `cleanup purge` ignores snapshots and deletes everything except protected resources.
