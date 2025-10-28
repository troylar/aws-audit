# Data Model: Multi-Account Inventory Management

**Feature**: 002-inventory-management
**Date**: 2025-10-28
**Status**: Complete

## Overview

This document defines the data structures for the inventory management feature. All models are Python dataclasses using type hints (Python 3.8+). Storage format is YAML for human readability and consistency with existing snapshot storage.

---

## Core Entities

### Inventory

Represents a named organizational container for snapshots within an AWS account.

**Purpose**: Groups related snapshots by account and purpose (baseline, team resources, compliance scope, etc.) with optional immutable filters.

**Lifecycle**: Created by user → accumulates snapshots → optionally deleted

**File**: `src/models/inventory.py`

#### Fields

| Field | Type | Required | Description | Validation |
|-------|------|----------|-------------|------------|
| `name` | `str` | Yes | Unique identifier within account | Alphanumeric + hyphens + underscores, 1-50 chars |
| `account_id` | `str` | Yes | AWS account ID (12 digits) | Auto-detected from credentials |
| `description` | `str` | No | Human-readable description | Max 500 characters |
| `include_tags` | `Dict[str, str]` | No | Tag filters (resource MUST have ALL) | Empty dict if no filters |
| `exclude_tags` | `Dict[str, str]` | No | Tag filters (resource MUST NOT have ANY) | Empty dict if no filters |
| `snapshots` | `List[str]` | Yes | Snapshot filenames in this inventory | Empty list if no snapshots yet |
| `active_snapshot` | `Optional[str]` | No | Filename of active baseline snapshot | None if no snapshots |
| `created_at` | `datetime` | Yes | Inventory creation timestamp | Timezone-aware UTC |
| `last_updated` | `datetime` | Yes | Last modification timestamp | Timezone-aware UTC, auto-updated |

#### Relationships

- **1 Inventory → Many Snapshots**: `snapshots` list contains snapshot filenames
- **1 Inventory → 0 or 1 Active Snapshot**: `active_snapshot` references one snapshot in `snapshots` list
- **1 Account → Many Inventories**: Multiple inventories can exist for same account (different names)

#### Constraints

- **Unique name per account**: (name, account_id) must be unique across all inventories
- **Immutable filters**: Once created, `include_tags` and `exclude_tags` cannot be modified
- **Active snapshot validation**: If `active_snapshot` is set, it MUST exist in `snapshots` list
- **Snapshot filename format**: Can be legacy ("name.yaml") or new ("{account}-{inventory}-{timestamp}.yaml")

#### Python Dataclass

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

@dataclass
class Inventory:
    """Named container for organizing snapshots by account and purpose."""

    name: str
    account_id: str
    include_tags: Dict[str, str] = field(default_factory=dict)
    exclude_tags: Dict[str, str] = field(default_factory=dict)
    snapshots: List[str] = field(default_factory=list)
    active_snapshot: Optional[str] = None
    description: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for YAML storage."""
        return {
            'name': self.name,
            'account_id': self.account_id,
            'description': self.description,
            'include_tags': self.include_tags,
            'exclude_tags': self.exclude_tags,
            'snapshots': self.snapshots,
            'active_snapshot': self.active_snapshot,
            'created_at': self.created_at.isoformat(),
            'last_updated': self.last_updated.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Inventory':
        """Deserialize from dictionary (YAML load)."""
        return cls(
            name=data['name'],
            account_id=data['account_id'],
            description=data.get('description', ''),
            include_tags=data.get('include_tags', {}),
            exclude_tags=data.get('exclude_tags', {}),
            snapshots=data.get('snapshots', []),
            active_snapshot=data.get('active_snapshot'),
            created_at=datetime.fromisoformat(data['created_at']),
            last_updated=datetime.fromisoformat(data['last_updated']),
        )

    def add_snapshot(self, snapshot_filename: str, set_active: bool = False) -> None:
        """Add snapshot to inventory, optionally marking as active."""
        if snapshot_filename not in self.snapshots:
            self.snapshots.append(snapshot_filename)
        if set_active:
            self.active_snapshot = snapshot_filename
        self.last_updated = datetime.now(timezone.utc)

    def remove_snapshot(self, snapshot_filename: str) -> None:
        """Remove snapshot from inventory, clearing active if it was active."""
        if snapshot_filename in self.snapshots:
            self.snapshots.remove(snapshot_filename)
        if self.active_snapshot == snapshot_filename:
            self.active_snapshot = None
        self.last_updated = datetime.now(timezone.utc)

    def validate(self) -> List[str]:
        """Validate inventory data, return list of errors."""
        errors = []

        if not self.name or not re.match(r'^[a-zA-Z0-9_-]+$', self.name):
            errors.append("Name must contain only alphanumeric, hyphens, underscores")
        if len(self.name) > 50:
            errors.append("Name must be 50 characters or less")
        if not self.account_id or not re.match(r'^\d{12}$', self.account_id):
            errors.append("Account ID must be 12 digits")
        if self.active_snapshot and self.active_snapshot not in self.snapshots:
            errors.append("Active snapshot must exist in snapshots list")

        return errors
```

---

### Snapshot (Updated)

**Existing model** in `src/models/snapshot.py` - adding one new field for inventory tracking.

#### New Field

| Field | Type | Required | Description | Default |
|-------|------|----------|-------------|---------|
| `inventory_name` | `str` | Yes | Name of inventory this snapshot belongs to | "default" |

#### Migration

Existing snapshots without `inventory_name` field will default to "default" inventory during loading.

#### Python Update

```python
@dataclass
class Snapshot:
    """Existing fields..."""
    name: str
    created_at: datetime
    account_id: str
    regions: List[str]
    resources: List[Resource]
    metadata: Dict[str, Any]
    is_active: bool
    service_counts: Dict[str, int]
    filters_applied: Optional[Dict[str, Any]]
    total_resources_before_filter: Optional[int]

    # NEW FIELD
    inventory_name: str = "default"  # Defaults to "default" for backward compatibility

    # ... existing methods ...
```

---

## Storage Format

### inventories.yaml

Central registry of all inventories across all accounts.

**Location**: `.snapshots/inventories.yaml`

**Structure**:

```yaml
inventories:
  - name: default
    account_id: "123456789012"
    description: "Auto-created default inventory"
    include_tags: {}
    exclude_tags: {}
    snapshots:
      - "legacy-snapshot.yaml"
      - "123456-default-20251028-143000.yaml"
    active_snapshot: "123456-default-20251028-143000.yaml"
    created_at: "2025-10-28T14:30:00+00:00"
    last_updated: "2025-10-28T15:45:00+00:00"

  - name: baseline
    account_id: "123456789012"
    description: "Production baseline resources"
    include_tags: {}
    exclude_tags: {}
    snapshots:
      - "123456-baseline-20251028-150000.yaml"
    active_snapshot: "123456-baseline-20251028-150000.yaml"
    created_at: "2025-10-28T15:00:00+00:00"
    last_updated: "2025-10-28T15:00:00+00:00"

  - name: team-a-resources
    account_id: "123456789012"
    description: "Team Alpha project resources"
    include_tags:
      team: "alpha"
      env: "prod"
    exclude_tags:
      managed-by: "terraform"
    snapshots:
      - "123456-team-a-resources-20251028-160000.yaml"
    active_snapshot: "123456-team-a-resources-20251028-160000.yaml"
    created_at: "2025-10-28T16:00:00+00:00"
    last_updated: "2025-10-28T16:00:00+00:00"

  - name: baseline
    account_id: "987654321098"
    description: "Different account, same inventory name is OK"
    include_tags: {}
    exclude_tags: {}
    snapshots: []
    active_snapshot: null
    created_at: "2025-10-28T17:00:00+00:00"
    last_updated: "2025-10-28T17:00:00+00:00"
```

**Key Points**:
- Multiple accounts can coexist in same file
- Same inventory name allowed across different accounts
- Empty `snapshots: []` is valid (newly created inventory)
- `active_snapshot: null` is valid (no baseline set yet)
- Legacy snapshot filenames are valid entries

---

## Service Layer

### InventoryStorage

Service class for CRUD operations on inventories.

**Purpose**: Encapsulate all inventory persistence logic, provide transactional safety.

**File**: `src/snapshot/inventory_storage.py`

#### Methods

```python
class InventoryStorage:
    """Manage inventory storage and retrieval."""

    def __init__(self, storage_dir: Path = Path('.snapshots')):
        """Initialize with storage directory."""
        self.storage_dir = storage_dir
        self.inventory_file = storage_dir / 'inventories.yaml'

    def load_all(self) -> List[Inventory]:
        """Load all inventories from inventories.yaml."""

    def load_by_account(self, account_id: str) -> List[Inventory]:
        """Load inventories for specific account."""

    def get_by_name(self, name: str, account_id: str) -> Inventory:
        """Get specific inventory by name and account (raises if not found)."""

    def get_or_create_default(self, account_id: str) -> Inventory:
        """Get default inventory, creating if it doesn't exist."""

    def save(self, inventory: Inventory) -> None:
        """Save/update single inventory (atomic write)."""

    def delete(self, name: str, account_id: str, delete_snapshots: bool = False) -> int:
        """Delete inventory, optionally deleting its snapshot files. Returns snapshot count."""

    def exists(self, name: str, account_id: str) -> bool:
        """Check if inventory exists."""

    def validate_unique(self, name: str, account_id: str) -> bool:
        """Validate that (name, account_id) combination is unique."""
```

#### Atomic Write Implementation

Per Research Decision #1, uses temp file + rename for atomic writes:

```python
def _atomic_write(self, inventories: List[Inventory]) -> None:
    """Write inventories using atomic rename."""
    data = {'inventories': [inv.to_dict() for inv in inventories]}

    # Write to temp file
    temp_path = self.inventory_file.with_suffix('.tmp')
    with open(temp_path, 'w') as f:
        yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)

    # Atomic rename
    os.replace(temp_path, self.inventory_file)
```

---

## Queries and Operations

### Common Access Patterns

1. **List inventories for current account**
   ```python
   inventories = storage.load_by_account(account_id)
   ```

2. **Get inventory for snapshot operation**
   ```python
   if inventory_name:
       inv = storage.get_by_name(inventory_name, account_id)
   else:
       inv = storage.get_or_create_default(account_id)
   ```

3. **Add snapshot to inventory**
   ```python
   inventory.add_snapshot(snapshot_filename, set_active=True)
   storage.save(inventory)
   ```

4. **Find inventory by snapshot filename**
   ```python
   for inv in storage.load_by_account(account_id):
       if snapshot_filename in inv.snapshots:
           return inv
   ```

5. **Get active snapshot for cost/delta analysis**
   ```python
   inventory = storage.get_by_name(inventory_name, account_id)
   if inventory.active_snapshot:
       snapshot = load_snapshot(inventory.active_snapshot)
   ```

---

## Validation Rules

### Inventory Creation

- Name: 1-50 characters, alphanumeric + hyphens + underscores only
- Account ID: Auto-detected, must be 12 digits
- Unique (name, account_id) combination
- Include/exclude tags: Valid key=value format
- Description: Max 500 characters (soft limit, not enforced)

### Snapshot Addition

- Snapshot file must exist in .snapshots/snapshots/
- Snapshot filename added to inventory.snapshots list
- If set_active=True, also set inventory.active_snapshot
- Update inventory.last_updated timestamp

### Inventory Deletion

- If active_snapshot is set, warn user before deletion
- If delete_snapshots=True, delete all files in inventory.snapshots list
- If delete_snapshots=False, leave files but remove inventory metadata
- Cannot delete if it's the last inventory for an account (keep at least default)

---

## Migration Path

### Legacy Snapshot Handling

Existing snapshots without `inventory_name` field:

1. On first load: Add `inventory_name = "default"` to Snapshot dataclass
2. Migration utility creates "default" inventory if it doesn't exist
3. Legacy snapshot files added to default inventory's `snapshots` list
4. No file renaming required (metadata-only migration per Research Decision #2)

### Migration Command

```bash
aws-baseline inventory migrate
```

**Actions**:
1. Scan `.snapshots/snapshots/` for all YAML files
2. Load each snapshot, check for `inventory_name` field
3. If missing: assign to "default" inventory
4. Create/update inventories.yaml with default inventory
5. Report: X snapshots migrated to default inventory

---

## Examples

### Create Baseline Inventory

```python
from src.models.inventory import Inventory
from src.snapshot.inventory_storage import InventoryStorage
from datetime import datetime, timezone

storage = InventoryStorage()
account_id = "123456789012"

baseline = Inventory(
    name="baseline",
    account_id=account_id,
    description="Production baseline resources",
    include_tags={},
    exclude_tags={},
    created_at=datetime.now(timezone.utc),
    last_updated=datetime.now(timezone.utc),
)

storage.save(baseline)
```

### Take Snapshot in Inventory Context

```python
# Get inventory (or default)
inventory = storage.get_by_name("baseline", account_id)

# Create snapshot with inventory filters
snapshot = create_snapshot(
    name=f"{account_id}-{inventory.name}-{timestamp}",
    regions=regions,
    account_id=account_id,
    inventory_name=inventory.name,
    resource_filter=ResourceFilter(
        include_tags=inventory.include_tags,
        exclude_tags=inventory.exclude_tags,
    ),
)

# Add to inventory
inventory.add_snapshot(snapshot.name, set_active=True)
storage.save(inventory)
```

### Cost Analysis with Inventory

```python
# Get inventory
inventory = storage.get_by_name("baseline", account_id)

# Load active snapshot
if not inventory.active_snapshot:
    raise ValueError("No active snapshot in inventory")

snapshot = load_snapshot(inventory.active_snapshot)

# Run cost analysis
report = analyzer.analyze(baseline_snapshot=snapshot, ...)
reporter.display(report)
```

---

## Summary

**New Models**: 1 (Inventory)
**Updated Models**: 1 (Snapshot + inventory_name field)
**Storage Files**: 1 (inventories.yaml)
**Service Classes**: 1 (InventoryStorage)

All data structures follow existing patterns (dataclasses, YAML storage, type hints). No breaking changes to existing snapshot format.
