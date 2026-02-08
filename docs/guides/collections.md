# Collections

A collection is a named grouping of snapshots organized by account, environment, or purpose. Collections let you manage multiple baselines independently -- for example, keeping separate snapshot histories for production and staging environments, or for different AWS accounts. Collections were previously called "inventories" and have been renamed to avoid confusion with the general concept of an inventory snapshot.

## Creating Collections

```bash
# Basic collection
awsinv collection create prod-baseline

# With a description
awsinv collection create prod-baseline --description "Production account baseline"

# Tied to a specific AWS account
awsinv collection create prod-baseline --account-id 123456789012
```

## Listing Collections

```bash
awsinv collection list
```

This displays all collections with their name, description, account ID (if set), snapshot count, and active snapshot.

## Showing Collection Details

```bash
awsinv collection show prod-baseline
```

Displays the collection metadata, the list of associated snapshots, and which snapshot is currently active.

## Assigning Snapshots to Collections

When creating a snapshot, use `--collection` to assign it to an existing collection:

```bash
awsinv snapshot create my-snapshot --collection prod-baseline
```

The snapshot is recorded under the collection and automatically set as the active snapshot unless overridden.

## Active Snapshot

Each collection tracks a single "active" snapshot that serves as the current baseline. When you run a delta comparison against a collection, the active snapshot is used as the reference point.

```bash
# Set a specific snapshot as active
awsinv snapshot set-active my-snapshot

# Compare current state against the collection's active snapshot
awsinv delta --snapshot my-snapshot
```

The active snapshot is updated automatically when a new snapshot is created within the collection, keeping the baseline current without manual intervention.

## Deleting Collections

```bash
awsinv collection delete old-collection --yes
```

The `--yes` flag skips the confirmation prompt. Deleting a collection does not delete the snapshots themselves -- they remain available and can be reassigned to another collection.

## Use Cases

**Multi-team** -- Create a separate collection per team so each team manages its own baseline independently.

```bash
awsinv collection create platform-team --description "Platform engineering baseline"
awsinv collection create data-team --description "Data pipeline resources"
```

**Multi-environment** -- Maintain distinct baselines for each environment to track drift separately.

```bash
awsinv collection create dev-baseline --description "Development environment"
awsinv collection create staging-baseline --description "Staging environment"
awsinv collection create prod-baseline --description "Production environment"
```

**Multi-account** -- Use one collection per AWS account to isolate snapshots by account boundary.

```bash
awsinv collection create acct-dev --account-id 111111111111 --description "Dev account"
awsinv collection create acct-staging --account-id 222222222222 --description "Staging account"
awsinv collection create acct-prod --account-id 333333333333 --description "Prod account"
```
