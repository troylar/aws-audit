# Change Tracking

Track what changed in your AWS environment since a baseline snapshot.

## Basic Delta

```bash
# Compare current state to a snapshot
awsinv delta --snapshot my-baseline

# Show field-level diff
awsinv delta --snapshot my-baseline --show-diff
```

## What the Delta Shows

- **New resources** created since the snapshot
- **Deleted resources** that no longer exist
- **Modified resources** with field-level configuration changes

The `--show-diff` flag provides before/after values for each changed field, with color-coded terminal output.

## JSON Export for CI/CD

```bash
awsinv delta --snapshot my-baseline --export changes.json
```

This produces a structured JSON file suitable for CI/CD pipeline integration, containing arrays of added, removed, and modified resources.
