# FAQ & Troubleshooting

## Common Issues

### "AccessDenied" or "UnauthorizedOperation" errors

**Problem:** The tool returns permission errors during snapshot collection.

**Solution:** Ensure your IAM user/role has the required permissions. See [IAM Permissions](reference/iam-permissions.md) for the minimum required policies.

```bash
# Verify your current identity
aws sts get-caller-identity

# Test if you have basic access
aws ec2 describe-instances --region us-east-1
```

### Snapshot takes a long time

**Problem:** Creating a snapshot takes several minutes.

**Solutions:**

1. **Enable AWS Config** for faster collection (up to 5x faster). The tool detects it automatically.
2. **Limit regions:** Only scan regions you use with `--region us-east-1,us-west-2`
3. **Limit resource types:** Filter to specific services with `--type ec2,s3,lambda`

```bash
# Faster: Only scan what you need
awsinv snapshot create quick-snap --region us-east-1 --type ec2,lambda
```

### "No resources found" in snapshot

**Problem:** Snapshot completes but shows 0 resources.

**Possible causes:**

1. **Wrong region:** You may be scanning a region with no resources
2. **Tag filtering:** If you used `--include-tags`, ensure resources have those tags
3. **Permission issues:** Some describe APIs may silently return empty results instead of errors

### Config Aggregator not working

**Problem:** `--config-aggregator` flag doesn't return cross-account resources.

**Solutions:**

1. Verify the aggregator exists: `aws configservice describe-configuration-aggregators`
2. Ensure you have `config:SelectAggregateResourceConfig` permission
3. Check that source accounts are properly linked in the aggregator
4. Run from the aggregator's account/region (typically management account)

### Cleanup preview shows unexpected resources

**Problem:** The cleanup preview shows resources you didn't expect to be deleted.

**Explanation:** Cleanup deletes resources that exist now but didn't exist in the snapshot. This includes resources created after the snapshot, resources in regions not included in the original snapshot, and AWS-managed resources that get auto-created.

**Solutions:**

1. Use `--protect-tag` to protect resources by tag
2. Use `--type` to limit to specific resource types
3. Create a more comprehensive baseline snapshot

### Rate limiting / API throttling

**Problem:** Errors like "Rate exceeded" or "Throttling" during snapshot.

The tool includes built-in retry logic with exponential backoff. If you still see issues:

1. Use `--no-config` to skip Config detection (reduces API calls)
2. Limit regions with `--region`
3. Limit resource types with `--type`
4. For very large accounts, consider running during off-peak hours

### Large accounts (50k+ resources)

**Considerations:**

- **Memory:** Snapshot data is held in memory during collection; very large accounts may need 2--4GB RAM
- **Database size:** SQLite database grows with resources but handles large datasets efficiently
- **Time:** Direct API collection may take 10--15 minutes; AWS Config reduces this significantly
- **Recommendation:** Use AWS Config + limit to specific regions/types for large accounts

---

## Frequently Asked Questions

### Does this create actual AWS snapshots (EBS, RDS)?

**No.** "Snapshot" in this tool means an *inventory snapshot* -- a catalog of what resources exist. It does not create EBS snapshots, RDS snapshots, or any AWS resources. All data is stored locally in a SQLite database.

### Is my AWS data sent anywhere?

**No.** All data stays local. The tool only makes read API calls to AWS (and delete calls if you use cleanup). All data is stored in a SQLite database at `~/.snapshots/inventory.db` on your local machine.

### Can I use this with AWS Organizations?

**Yes.** Use one of these approaches:

1. **Config Aggregator:** Query all accounts from your management account with `--config-aggregator`
2. **Profile switching:** Create snapshots per account using `--profile`
3. **Cross-account roles:** Configure role assumption in AWS CLI profiles

See [Multi-Account Support](configuration/multi-account.md) for details.

### What happens if AWS Config is only partially enabled?

The tool handles partial Config coverage gracefully:

- **Region has Config:** Uses Config for supported types, direct API for others
- **Region lacks Config:** Falls back to direct API for all types
- **Type not recorded:** Falls back to direct API for that specific type

You can see which method was used per resource via the `source` field in snapshots.

### How do I undo a cleanup operation?

**You can't.** Deleted resources are permanently deleted. Always:

1. Use `cleanup preview` first
2. Review the output carefully
3. Consider creating a fresh snapshot before cleanup
4. Use `--protect-tag` to safeguard important resources

### Can I schedule automatic snapshots?

The tool doesn't include scheduling, but you can add it:

```bash
# Cron example (daily at midnight)
0 0 * * * /usr/local/bin/awsinv snapshot create daily-$(date +\%Y\%m\%d) --region us-east-1
```

Or use AWS EventBridge + Lambda to trigger from within AWS.

### Where should I run this tool?

| Environment | Pros | Cons |
|-------------|------|------|
| **Local laptop** | Easy setup, interactive preview | Credentials on laptop, network latency |
| **EC2 with instance role** | No credential management, low latency | Snapshots stored on instance (back up!) |
| **CI/CD pipeline** | Automated, auditable | Credential setup, snapshot storage strategy needed |
| **CloudShell** | Zero setup, in-browser | Session timeouts, ephemeral storage |

For team use, consider storing snapshots in a shared location (see [Data Storage](configuration/data-storage.md)).

### Why does cleanup delete my VPC?

When you run cleanup execute against a baseline, the tool deletes resources created after that baseline. If the VPC was created after your snapshot, it will be marked for deletion.

**Best practice:** Always include networking infrastructure in your baseline snapshot, or protect it with tags:

```bash
awsinv cleanup execute my-baseline --protect-tag "layer=network" --yes
```
