# Common Workflows

Real-world scenarios showing how teams use AWS Inventory Manager.

## Development Environment Reset

!!! warning
    Only use this in dedicated development/sandbox accounts. Never run cleanup commands in production without extensive testing and protection rules.

```bash
# Morning: Capture clean state
awsinv snapshot create morning-baseline --region us-east-1

# Evening: Clean up everything created during the day
awsinv cleanup preview morning-baseline   # Always preview first!
awsinv cleanup execute morning-baseline --yes
```

## Sandbox Account Cleanup

!!! warning
    Purge mode deletes ALL resources except protected ones. Triple-check your protection rules before executing.

```bash
# Tag your permanent infrastructure with "baseline=true"
# Then periodically purge everything else

awsinv cleanup purge --protect-tag "baseline=true" --preview
# Review the preview output carefully!
awsinv cleanup purge --protect-tag "baseline=true" --yes
```

## Pre/Post Deployment Comparison

```bash
# Before deploy
awsinv snapshot create pre-deploy-v2.3 --region us-east-1,us-west-2

# Deploy your changes...

# After deploy - see exactly what changed
awsinv delta --snapshot pre-deploy-v2.3 --show-diff
```

## Security Audit

```bash
# Weekly security scan
awsinv snapshot create weekly-audit --region us-east-1
awsinv security scan --output security-report-$(date +%Y%m%d).json
```

## Cost Attribution by Team

```bash
# Snapshot resources per team
awsinv snapshot create team-platform --include-tags "team=platform"
awsinv snapshot create team-data --include-tags "team=data"

# Compare costs
awsinv cost --snapshot team-platform
awsinv cost --snapshot team-data
```

## Automated Snapshots

The tool itself doesn't include scheduling, but you can add it:

```bash
# Cron example (daily at midnight)
0 0 * * * /usr/local/bin/awsinv snapshot create daily-$(date +\%Y\%m\%d) --region us-east-1
```

Or use AWS EventBridge + Lambda to trigger from within AWS.
