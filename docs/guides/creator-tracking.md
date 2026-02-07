# Creator Tracking

Track who created each resource in your AWS account using CloudTrail.

## Tracking During Snapshot Creation

```bash
awsinv snapshot create my-snapshot --regions us-east-1 --track-creators
```

## Enriching Existing Snapshots

```bash
awsinv snapshot enrich-creators my-snapshot --days-back 90
```

This adds three tags to each resource:

- `_created_by`: The IAM role/user ARN that created the resource
- `_created_by_type`: The identity type (AssumedRole, IAMUser, Root, AWSService)
- `_created_at`: When the resource was created (from CloudTrail)

!!! note
    CloudTrail has a 90-day lookup window. Resources created more than 90 days ago won't have creator information. The `--days-back` option lets you customize the lookup period (default: 90).

## Listing Creators

View a summary of all resource creators for a snapshot:

```bash
# Show creators summary for active snapshot
awsinv snapshot creators

# Show creators for specific snapshot
awsinv snapshot creators my-snapshot

# Show detailed resources for each creator
awsinv snapshot creators --detailed

# Export to JSON or CSV
awsinv snapshot creators --export creators.json
awsinv snapshot creators --export creators.csv
```

Output includes:

- Unique creators count
- Resources with/without creator info
- Table with creator name, type, resource count, and top resource types
- With `--detailed`: individual resources grouped by type for each creator

## Use Cases

- Identify resources created by automation vs. manual creation
- Track resources created by specific CI/CD pipelines
- Find resources created by former team members
- Audit resource creation by identity type

## Web UI Support

The Resource Explorer includes three creator columns (enable via column selector):

- **Created By** -- Shows the creator ARN (truncated for readability)
- **Creator Type** -- Color-coded badge (AssumedRole=blue, IAMUser=green, Root=red, AWSService=orange)
- **Creation Time** -- When the resource was created

## IAM Permissions

Creator tracking requires CloudTrail access:

```json
{
  "Effect": "Allow",
  "Action": ["cloudtrail:LookupEvents"],
  "Resource": "*"
}
```
