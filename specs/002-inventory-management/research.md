# Research & Technical Decisions: Multi-Account Inventory Management

**Feature**: 002-inventory-management
**Date**: 2025-10-28
**Status**: Complete

## Overview

This document captures technical research and decisions made during the planning phase for the inventory management feature. Each decision resolves a "NEEDS CLARIFICATION" item from the implementation plan's Technical Context section.

---

## Decision 1: YAML File Concurrency Safety

### Question
How should the system handle concurrent reads/writes to inventories.yaml when multiple CLI instances might access it simultaneously?

### Decision
**Use atomic writes with temp file + rename pattern**. Do NOT implement file locking.

### Rationale

1. **User assumption from spec**: "Concurrent CLI usage is rare (file locking/transactions nice-to-have, not critical for MVP)" - Spec line 140
2. **Atomic writes are sufficient**: Python's `os.replace()` is atomic on all platforms (POSIX + Windows), providing crash safety
3. **File locking complexity**: fcntl (Unix-only), msvcrt (Windows-only), requires platform-specific code and testing
4. **Race condition acceptable**: If two CLI instances create inventories simultaneously, last write wins - user will see one of them and can recreate if needed
5. **Read safety**: YAML parser handles incomplete reads gracefully (will fail, not corrupt)

### Implementation Approach

```python
# InventoryStorage.save() method
def save(self, inventories: List[Inventory]) -> None:
    """Save inventories using atomic write pattern."""
    data = [inv.to_dict() for inv in inventories]

    # Write to temp file
    temp_path = self.inventory_file.with_suffix('.tmp')
    with open(temp_path, 'w') as f:
        yaml.safe_dump({'inventories': data}, f)

    # Atomic rename (replaces existing file)
    os.replace(temp_path, self.inventory_file)
```

### Alternatives Considered

| Alternative | Rejected Because |
|-------------|------------------|
| fcntl file locking | Platform-specific (Unix only), adds complexity for rare edge case |
| Optimistic locking (version field) | Requires retry logic, confusing error messages for users |
| SQLite database | Overkill for simple YAML storage, adds dependency |

---

## Decision 2: Snapshot Naming Migration Strategy

### Question
How should existing snapshots (named without account-inventory prefix) be migrated to the new `{account}-{inventory}-{timestamp}.yaml` naming pattern?

### Decision
**Metadata-only migration**: Do NOT rename files. Store mapping in inventories.yaml.

### Rationale

1. **Zero data loss**: No file operations = no risk of corruption or deletion
2. **Backward compatibility**: Existing tools/scripts referencing old snapshot names continue to work
3. **100% success rate**: Per SC-005, must convert 100% without loss - metadata approach guarantees this
4. **Simple rollback**: Remove inventories.yaml to revert to legacy behavior
5. **User clarification**: "I'm thinking of calling them inventories or inventory snapshots" - user wants conceptual organization, not file system restructuring

### Implementation Approach

```python
# Inventory model includes legacy snapshot references
@dataclass
class Inventory:
    name: str
    account_id: str
    snapshots: List[str]  # Can include both formats:
                          # - New: "123456-baseline-20251028-143000.yaml"
                          # - Legacy: "baseline-snapshot.yaml"
    # ... other fields

# Migration utility
def migrate_legacy_snapshots():
    """Add existing snapshots to default inventory."""
    legacy_files = glob.glob('.snapshots/snapshots/*.yaml')

    # Create default inventory if doesn't exist
    inventory = get_or_create_default_inventory()

    # Add legacy snapshots to inventory
    for file in legacy_files:
        if not matches_new_pattern(file):
            inventory.snapshots.append(os.basename(file))

    save_inventory(inventory)
```

### Storage Format (inventories.yaml)

```yaml
inventories:
  - name: default
    account_id: "123456789012"
    description: "Auto-migrated legacy snapshots"
    filters: {}
    snapshots:
      - "baseline-snapshot.yaml"  # Legacy format
      - "123456-default-20251028-143000.yaml"  # New format
    active_snapshot: "baseline-snapshot.yaml"
    created_at: "2025-10-28T14:30:00Z"
```

### Alternatives Considered

| Alternative | Rejected Because |
|-------------|------------------|
| In-place rename | Risk of data loss if rename fails mid-operation |
| Symlinks | Platform-specific (Windows shortcuts ≠ symlinks), confusing |
| Copy + rename | Doubles storage usage, slow for large snapshots |

---

## Decision 3: Default Inventory Auto-Creation

### Question
When and how should the system automatically create the "default" inventory if it doesn't exist?

### Decision
**Lazy creation on first use**: Create default inventory when any command needs it (snapshot/cost/delta without --inventory flag).

### Rationale

1. **Spec requirement**: FR-005 states "System MUST create a 'default' inventory automatically if referenced before it exists"
2. **Zero configuration**: Users don't need to run init command before using the tool
3. **Minimal surprise**: Inventory only appears when actually needed, not on first app launch
4. **Account ID available**: Commands that need default inventory already authenticate with AWS, so account ID is available
5. **Consistent UX**: Same behavior across all commands (snapshot, cost, delta)

### Implementation Approach

```python
# inventory_storage.py
class InventoryStorage:
    def get_or_create_default(self, account_id: str) -> Inventory:
        """Get default inventory, creating if it doesn't exist."""
        try:
            return self.get_by_name("default", account_id)
        except InventoryNotFoundError:
            # Auto-create default inventory
            default = Inventory(
                name="default",
                account_id=account_id,
                description="Auto-created default inventory",
                filters={},
                snapshots=[],
                active_snapshot=None,
                created_at=datetime.now(timezone.utc),
                last_updated=datetime.now(timezone.utc),
            )
            self.save(default)
            logger.info(f"Created default inventory for account {account_id}")
            return default

# cli/main.py - snapshot command
@app.command()
def snapshot(
    inventory: Optional[str] = typer.Option(None, "--inventory"),
    # ... other options
):
    account_id = get_account_id(profile)

    if inventory:
        inv = inventory_storage.get_by_name(inventory, account_id)  # Error if not found
    else:
        inv = inventory_storage.get_or_create_default(account_id)  # Auto-create

    # ... proceed with snapshot using inv.filters
```

### Alternatives Considered

| Alternative | Rejected Because |
|-------------|------------------|
| Create on first `inventory list` | User might list before taking snapshot, sees nothing, confusion |
| Explicit `inventory init` command | Extra step, violates FR-005 "automatic" requirement |
| Create on CLI startup | Creates inventory even if user never uses snapshot/cost/delta |

---

## Decision 4: Inventory Filter Conflict Resolution

### Question
What should happen if a user specifies `--inventory baseline` (which has filters) AND also provides `--include-tags` or `--exclude-tags` on the snapshot command?

### Decision
**Error with clear message**: Reject command, require user to choose inventory OR inline filters, not both.

### Rationale

1. **Spec requirement**: FR-004 states filters are "immutable once an inventory is created"
2. **Principle of least surprise**: Merging filters could produce unexpected results
3. **Clear intent**: User should explicitly choose: use inventory (with its filters) OR create ad-hoc snapshot (with inline filters)
4. **Encourages proper usage**: User should create a new inventory if they want a different filter combination
5. **Edge case from spec**: Line 83 explicitly calls out this scenario as an edge case to handle

### Implementation Approach

```python
# cli/main.py - snapshot command
@app.command()
def snapshot(
    inventory: Optional[str] = typer.Option(None, "--inventory"),
    include_tags: Optional[str] = typer.Option(None, "--include-tags"),
    exclude_tags: Optional[str] = typer.Option(None, "--exclude-tags"),
    # ... other options
):
    # Validate filter conflict
    if inventory and (include_tags or exclude_tags):
        console.print(
            "[red]✗ Error: Cannot specify both --inventory and --include-tags/--exclude-tags[/red]\n"
            "\n"
            "Inventories have immutable filters defined at creation time.\n"
            "\n"
            "Choose one:\n"
            "  1. Use inventory filters: aws-baseline snapshot --inventory baseline\n"
            "  2. Use inline filters:    aws-baseline snapshot --include-tags 'env=prod'\n"
            "  3. Create new inventory:  aws-baseline inventory create <name> --include-tags 'env=prod'\n"
        )
        raise typer.Exit(code=1)

    # Proceed with inventory OR inline filters
    if inventory:
        inv = inventory_storage.get_by_name(inventory, account_id)
        resource_filter = ResourceFilter(
            include_tags=inv.include_tags,
            exclude_tags=inv.exclude_tags,
        )
    else:
        inv = inventory_storage.get_or_create_default(account_id)
        # Use inline filters if provided, otherwise no filters
        resource_filter = ResourceFilter(
            include_tags=parse_tags(include_tags) if include_tags else {},
            exclude_tags=parse_tags(exclude_tags) if exclude_tags else {},
        )
```

### Error Message Example

```
$ aws-baseline snapshot --inventory baseline --include-tags "team=alpha"

✗ Error: Cannot specify both --inventory and --include-tags/--exclude-tags

Inventories have immutable filters defined at creation time.

Choose one:
  1. Use inventory filters: aws-baseline snapshot --inventory baseline
  2. Use inline filters:    aws-baseline snapshot --include-tags 'env=prod'
  3. Create new inventory:  aws-baseline inventory create <name> --include-tags 'env=prod'
```

### Alternatives Considered

| Alternative | Rejected Because |
|-------------|------------------|
| Merge filters (AND logic) | Violates immutability principle, complex precedence rules |
| Override (CLI wins) | Defeats purpose of saved inventory filters |
| Ignore (inventory wins) | Silently ignoring CLI flags is confusing |
| Warn and continue | User might not see warning, produces unexpected results |

---

## Additional Design Decisions

### Snapshot File Naming for Default Inventory

**Decision**: Default inventory snapshots still use new naming pattern: `{account}-default-{timestamp}.yaml`

**Rationale**: Consistency. All snapshots follow same pattern regardless of inventory name. Makes storage code simpler.

### Inventory Name Validation

**Decision**: Alphanumeric + hyphens + underscores only, 1-50 characters.

**Rationale**: Per FR-010, ensures cross-platform filename compatibility. Prevents special characters that could cause path issues.

### Active Snapshot Tracking

**Decision**: One active snapshot per inventory (not global).

**Rationale**: User wants per-inventory baselines (confirmed in design discussion). Each inventory tracks its own active snapshot for delta/cost analysis.

---

## Summary

All technical clarifications resolved:

1. ✅ **Concurrency**: Atomic writes (no locking)
2. ✅ **Migration**: Metadata-only (no file renames)
3. ✅ **Default inventory**: Lazy creation on first use
4. ✅ **Filter conflicts**: Error with clear guidance

**Ready for Phase 1**: Data model design, contracts (N/A for CLI), and quickstart scenarios.
