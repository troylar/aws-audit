# Quickstart Guide: Multi-Account Inventory Management

**Feature**: 002-inventory-management
**Date**: 2025-10-28
**Audience**: Developers implementing and testing this feature

## Overview

This guide provides concrete test scenarios for the inventory management feature, mapping directly to the user stories in [spec.md](./spec.md). Use these scenarios to validate implementation during development.

---

## Prerequisites

```bash
# Ensure you have AWS credentials configured
aws configure

# Or use a profile
export AWS_PROFILE=your-profile

# Tool installed (from project root)
pip install -e .

# Verify installation
aws-baseline --help
```

---

## User Story 1: Create Named Inventory with Filters (P1)

### Scenario 1.1: Create Basic Inventory

**Test**: Create inventory without filters

```bash
# Create baseline inventory
aws-baseline inventory create baseline \
  --description "Production baseline resources"

# Expected output:
# ✓ Created inventory 'baseline' for account 123456789012
#
# Inventory Details:
#   Name: baseline
#   Account: 123456789012
#   Description: Production baseline resources
#   Filters: None
#   Snapshots: 0
```

**Validation**:
```bash
# Check inventory was created
cat .snapshots/inventories.yaml

# Should contain:
# inventories:
#   - name: baseline
#     account_id: "123456789012"
#     description: "Production baseline resources"
#     include_tags: {}
#     exclude_tags: {}
#     snapshots: []
#     active_snapshot: null
```

---

### Scenario 1.2: Create Inventory with Filters

**Test**: Create inventory with include/exclude tags

```bash
# Create filtered inventory
aws-baseline inventory create team-a-resources \
  --description "Team Alpha project resources" \
  --include-tags "team=alpha,env=prod" \
  --exclude-tags "managed-by=terraform"

# Expected output:
# ✓ Created inventory 'team-a-resources' for account 123456789012
#
# Inventory Details:
#   Name: team-a-resources
#   Account: 123456789012
#   Description: Team Alpha project resources
#   Filters:
#     Include Tags: team=alpha, env=prod (resources must have ALL)
#     Exclude Tags: managed-by=terraform (resources must NOT have ANY)
#   Snapshots: 0
```

**Validation**:
```bash
cat .snapshots/inventories.yaml | grep -A 10 "team-a-resources"

# Should show:
#   include_tags:
#     team: "alpha"
#     env: "prod"
#   exclude_tags:
#     managed-by: "terraform"
```

---

### Scenario 1.3: List Inventories

**Test**: View all inventories for current account

```bash
aws-baseline inventory list

# Expected output (table format):
# ┌────────────────────┬───────────────┬─────────────┬────────────────────────────────┐
# │ Name               │ Snapshots     │ Filters     │ Description                    │
# ├────────────────────┼───────────────┼─────────────┼────────────────────────────────┤
# │ baseline           │ 0             │ None        │ Production baseline resources  │
# │ team-a-resources   │ 0             │ Yes (2/1)   │ Team Alpha project resources   │
# └────────────────────┴───────────────┴─────────────┴────────────────────────────────┘
#
# Account: 123456789012 | Total Inventories: 2
```

---

### Scenario 1.4: Show Inventory Details

**Test**: View detailed information for specific inventory

```bash
aws-baseline inventory show team-a-resources

# Expected output:
# Inventory: team-a-resources
# Account: 123456789012
# Description: Team Alpha project resources
# Created: 2025-10-28 14:30:00 UTC
# Last Updated: 2025-10-28 14:30:00 UTC
#
# Filters:
#   Include Tags (must have ALL):
#     • team = alpha
#     • env = prod
#   Exclude Tags (must NOT have ANY):
#     • managed-by = terraform
#
# Snapshots: 0
# (No snapshots taken yet)
#
# Active Baseline: None
```

---

### Scenario 1.5: Error - Duplicate Inventory Name

**Test**: Attempt to create inventory with existing name

```bash
aws-baseline inventory create baseline \
  --description "This should fail"

# Expected output:
# ✗ Error: Inventory 'baseline' already exists for account 123456789012
#
# Use a different name or delete the existing inventory first:
#   aws-baseline inventory delete baseline
```

---

## User Story 2: Take Filtered Snapshots within Inventory Context (P2)

### Scenario 2.1: Take Snapshot in Inventory

**Test**: Create snapshot with inventory filters

```bash
# Take snapshot in baseline inventory
aws-baseline snapshot create \
  --name "baseline-oct-28" \
  --inventory baseline \
  --regions us-east-1,us-west-2

# Expected output:
# 🔍 Using inventory: baseline (no filters)
# 📦 Collecting AWS resources from 2 region(s)...
# [progress indicators...]
# ✓ Successfully collected 1,234 resources
#
# 💾 Saving snapshot as: 123456-baseline-20251028-143000.yaml
# ✓ Snapshot saved successfully
# ✓ Added to inventory 'baseline' and marked as active
```

**Validation**:
```bash
# Check snapshot file was created
ls .snapshots/snapshots/123456-baseline-*.yaml

# Check inventory was updated
aws-baseline inventory show baseline

# Should show:
# Snapshots: 1
#   • 123456-baseline-20251028-143000.yaml (active)
```

---

### Scenario 2.2: Take Filtered Snapshot

**Test**: Snapshot automatically applies inventory filters

```bash
aws-baseline snapshot create \
  --name "team-a-oct-28" \
  --inventory team-a-resources \
  --regions us-east-1

# Expected output:
# 🔍 Using inventory: team-a-resources
# 📋 Filters: team=alpha, env=prod (exclude: managed-by=terraform)
# 📦 Collecting AWS resources from 1 region(s)...
# [progress...]
# ✓ Successfully collected 567 resources
# 🔍 Applying filters...
# ✓ Filtered to 234 resources (333 excluded)
#
# 💾 Saving snapshot as: 123456-team-a-resources-20251028-150000.yaml
# ✓ Snapshot saved successfully
# ✓ Added to inventory 'team-a-resources' and marked as active
```

**Validation**:
```bash
# Verify snapshot contains only filtered resources
aws-baseline snapshot show 123456-team-a-resources-20251028-150000.yaml

# Should show 234 resources, all with team=alpha and env=prod tags
```

---

### Scenario 2.3: Default Inventory Auto-Creation

**Test**: Snapshot without --inventory creates default inventory

```bash
# First time using tool (no inventories exist)
aws-baseline snapshot create \
  --name "first-snapshot" \
  --regions us-east-1

# Expected output:
# 🔍 No inventory specified, using 'default' inventory
# ℹ️  Created default inventory for account 123456789012
# 📦 Collecting AWS resources from 1 region(s)...
# [progress...]
# ✓ Successfully collected 1,234 resources
#
# 💾 Saving snapshot as: 123456-default-20251028-160000.yaml
# ✓ Snapshot saved successfully
# ✓ Added to inventory 'default' and marked as active
```

**Validation**:
```bash
# Check default inventory was created
aws-baseline inventory list

# Should show 'default' inventory
aws-baseline inventory show default

# Should show 1 snapshot
```

---

### Scenario 2.4: Error - Nonexistent Inventory

**Test**: Attempt snapshot with nonexistent inventory

```bash
aws-baseline snapshot create \
  --name "test" \
  --inventory nonexistent \
  --regions us-east-1

# Expected output:
# ✗ Error: Inventory 'nonexistent' not found for account 123456789012
#
# Create the inventory first:
#   aws-baseline inventory create nonexistent [--include-tags ...] [--exclude-tags ...]
#
# Or list existing inventories:
#   aws-baseline inventory list
```

---

### Scenario 2.5: Error - Filter Conflict

**Test**: Attempt to override inventory filters

```bash
aws-baseline snapshot create \
  --name "test" \
  --inventory baseline \
  --include-tags "team=bravo" \
  --regions us-east-1

# Expected output:
# ✗ Error: Cannot specify both --inventory and --include-tags/--exclude-tags
#
# Inventories have immutable filters defined at creation time.
#
# Choose one:
#   1. Use inventory filters: aws-baseline snapshot --inventory baseline
#   2. Use inline filters:    aws-baseline snapshot --include-tags 'env=prod'
#   3. Create new inventory:  aws-baseline inventory create <name> --include-tags 'env=prod'
```

---

## User Story 3: Analyze Costs and Deltas within Inventory Context (P3)

### Scenario 3.1: Cost Analysis with Inventory

**Test**: Run cost analysis scoped to inventory

```bash
aws-baseline cost --inventory baseline

# Expected output:
# 🔍 Checking for resource changes since baseline...
# ✓ No resource changes detected - all costs are from baseline resources
#
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#                     Cost Analysis Report
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Baseline: 123456-baseline-20251028-143000.yaml
# Period: 2025-10-28 to 2025-10-28
# Generated: 2025-10-28 16:30:00 UTC
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#
# Baseline Costs
# ┌──────────────────┐
# │    Total Cost    │
# ├──────────────────┤
# │    $1,234.56     │
# └──────────────────┘
#
# Top Services:
#   EC2             $567.89    (46.0%)
#   S3              $234.56    (19.0%)
#   Lambda          $123.45    (10.0%)
```

---

### Scenario 3.2: Delta Analysis with Inventory

**Test**: Run delta analysis scoped to inventory

```bash
aws-baseline delta --inventory team-a-resources

# Expected output:
# 🔍 Comparing current state to baseline: 123456-team-a-resources-20251028-150000.yaml
#
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#                  Delta Report: team-a-resources
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Baseline: 123456-team-a-resources-20251028-150000.yaml (234 resources)
# Current: 240 resources (filtered: team=alpha, env=prod)
# Generated: 2025-10-28 17:00:00 UTC
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#
# Summary:
#   + 8 added
#   - 2 removed
#   ~ 5 modified
#
# Added Resources (8):
#   + AWS::Lambda::Function - team-a-processor-v2 (us-east-1)
#   [... more ...]
```

---

### Scenario 3.3: Default Inventory Usage

**Test**: Cost/delta commands without --inventory use default

```bash
# Run cost without --inventory flag
aws-baseline cost

# Expected output:
# 🔍 Using 'default' inventory
# 🔍 Checking for resource changes since baseline...
# [... cost analysis for default inventory ...]
```

---

### Scenario 3.4: Error - No Snapshots in Inventory

**Test**: Attempt analysis on empty inventory

```bash
# Create empty inventory
aws-baseline inventory create empty-inv

# Try to run cost analysis
aws-baseline cost --inventory empty-inv

# Expected output:
# ✗ Error: No snapshots exist in inventory 'empty-inv'
#
# Take a snapshot first:
#   aws-baseline snapshot create --inventory empty-inv --regions us-east-1
```

---

## User Story 4: Manage Inventory Lifecycle (P4)

### Scenario 4.1: Delete Inventory (Keep Snapshots)

**Test**: Delete inventory but keep snapshot files

```bash
aws-baseline inventory delete team-a-resources

# Expected output (interactive prompt):
# ⚠️  Delete inventory 'team-a-resources'?
#
# This will remove the inventory metadata.
#
# This inventory contains 1 snapshot(s):
#   • 123456-team-a-resources-20251028-150000.yaml
#
# Delete snapshot files too? [y/N]: n
#
# ✓ Inventory 'team-a-resources' deleted
# ✓ Snapshot files preserved in .snapshots/snapshots/
```

**Validation**:
```bash
# Inventory gone
aws-baseline inventory list
# Should not show team-a-resources

# Files still exist
ls .snapshots/snapshots/123456-team-a-resources-*.yaml
# Should still list files
```

---

### Scenario 4.2: Delete Inventory (Delete Snapshots)

**Test**: Delete inventory and all its snapshots

```bash
aws-baseline inventory delete baseline

# Expected output:
# ⚠️  Delete inventory 'baseline'?
#
# This will remove the inventory metadata.
#
# This inventory contains 1 snapshot(s):
#   • 123456-baseline-20251028-143000.yaml (ACTIVE baseline)
#
# ⚠️  This is the active baseline snapshot!
# Deleting it will prevent cost/delta analysis until you take a new snapshot.
#
# Delete snapshot files too? [y/N]: y
#
# ✓ Inventory 'baseline' deleted
# ✓ 1 snapshot file(s) deleted from .snapshots/snapshots/
```

**Validation**:
```bash
# Inventory gone
aws-baseline inventory list

# Files deleted
ls .snapshots/snapshots/123456-baseline-*.yaml
# Should show "No such file or directory"
```

---

## Migration Scenario

### Scenario: Migrate Legacy Snapshots

**Setup**: Existing snapshots without inventory structure

```bash
# Assume legacy snapshots exist:
ls .snapshots/snapshots/
# legacy-snapshot-1.yaml
# legacy-snapshot-2.yaml
# my-baseline.yaml

# Run migration
aws-baseline inventory migrate

# Expected output:
# 🔍 Scanning for legacy snapshots...
# Found 3 snapshot(s) without inventory assignment
#
# ✓ Created 'default' inventory for account 123456789012
# ✓ Added 3 snapshots to 'default' inventory:
#   • legacy-snapshot-1.yaml
#   • legacy-snapshot-2.yaml
#   • my-baseline.yaml
#
# ✓ Migration complete!
```

**Validation**:
```bash
# Check default inventory
aws-baseline inventory show default

# Should list all 3 legacy snapshots
```

---

## Integration Test Workflow

Complete end-to-end workflow combining all user stories:

```bash
# 1. Create baseline inventory (US1)
aws-baseline inventory create baseline \
  --description "Production baseline"

# 2. Take baseline snapshot (US2)
aws-baseline snapshot create \
  --inventory baseline \
  --regions us-east-1

# 3. Create team inventory with filters (US1)
aws-baseline inventory create team-alpha \
  --include-tags "team=alpha" \
  --description "Team Alpha resources"

# 4. Take filtered snapshot (US2)
aws-baseline snapshot create \
  --inventory team-alpha \
  --regions us-east-1

# 5. List all inventories (US1)
aws-baseline inventory list

# 6. Run cost analysis on baseline (US3)
aws-baseline cost --inventory baseline

# 7. Run delta analysis on team inventory (US3)
aws-baseline delta --inventory team-alpha

# 8. Delete team inventory (US4)
aws-baseline inventory delete team-alpha

# Validation: baseline inventory still exists
aws-baseline inventory list
```

---

## Testing Checklist

**User Story 1 (P1) - Create Inventory**:
- [ ] Create inventory without filters
- [ ] Create inventory with include-tags
- [ ] Create inventory with exclude-tags
- [ ] Create inventory with both include and exclude tags
- [ ] List inventories shows all for account
- [ ] Show inventory displays full details
- [ ] Error on duplicate inventory name
- [ ] Error on invalid inventory name (special characters)

**User Story 2 (P2) - Take Snapshots**:
- [ ] Snapshot with --inventory applies inventory filters
- [ ] Snapshot without --inventory creates/uses default
- [ ] Snapshot file named correctly ({account}-{inventory}-{timestamp}.yaml)
- [ ] Snapshot added to inventory.snapshots list
- [ ] Active snapshot set correctly
- [ ] Error on nonexistent inventory
- [ ] Error on conflicting filters (--inventory + --include-tags)

**User Story 3 (P3) - Cost/Delta Analysis**:
- [ ] Cost command with --inventory uses correct snapshot
- [ ] Delta command with --inventory uses correct snapshot
- [ ] Cost/delta without --inventory uses default
- [ ] Error on inventory with no snapshots
- [ ] Error on inventory with no active snapshot

**User Story 4 (P4) - Inventory Lifecycle**:
- [ ] Delete inventory keeps snapshots by default
- [ ] Delete inventory can delete snapshots
- [ ] Warning shown when deleting active baseline
- [ ] Confirmation prompt works correctly
- [ ] Cannot delete if it would leave account with zero inventories

**Migration**:
- [ ] Legacy snapshots detected correctly
- [ ] Default inventory created automatically
- [ ] All legacy snapshots added to default
- [ ] No data loss during migration

---

## Summary

This quickstart provides:
- ✅ 15+ concrete test scenarios
- ✅ Expected outputs for validation
- ✅ Error cases covered
- ✅ Integration workflow example
- ✅ Complete testing checklist

Use these scenarios during development to validate each user story independently.
