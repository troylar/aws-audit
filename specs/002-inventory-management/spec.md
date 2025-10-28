# Feature Specification: Multi-Account Inventory Management

**Feature Branch**: `002-inventory-management`
**Created**: 2025-10-28
**Status**: Draft
**Input**: User description: "Multi-account inventory management system to organize AWS resource snapshots by account with named inventories, saved filter presets, and time-stamped snapshot tracking"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Create Named Inventory with Filters (Priority: P1)

As a cloud administrator managing multiple AWS environments, I need to create named inventories for different purposes (baseline resources, team-specific resources, compliance-scoped resources) so that I can organize snapshots and track costs separately for each concern.

**Why this priority**: This is the foundational capability that enables all other functionality. Without the ability to create and organize inventories, users cannot benefit from any other feature. This delivers immediate value by allowing users to segment their AWS resources by purpose or team.

**Independent Test**: Can be fully tested by creating an inventory with a name and optional tag filters, then verifying the inventory is stored and can be listed. Delivers the value of organized resource tracking even before taking any snapshots.

**Acceptance Scenarios**:

1. **Given** I am authenticated with an AWS account, **When** I create an inventory named "baseline" with no filters, **Then** the system creates the inventory, auto-detects my account ID from AWS credentials, and confirms creation
2. **Given** I am authenticated with an AWS account, **When** I create an inventory named "team-a-resources" with include-tags filter "team=alpha,env=prod", **Then** the system creates the inventory with immutable filters and stores them for all future snapshots
3. **Given** I have multiple inventories in the same account, **When** I list all inventories, **Then** I see all inventories for my account with their names, descriptions, filter settings, and snapshot counts
4. **Given** I want to view inventory details, **When** I show a specific inventory, **Then** I see full details including all snapshots taken within that inventory with timestamps

---

### User Story 2 - Take Filtered Snapshots within Inventory Context (Priority: P2)

As a cloud administrator, I need to take snapshots within a specific inventory context so that the snapshot automatically applies the inventory's saved filters and is stored in the correct organizational structure.

**Why this priority**: This builds on P1 by making inventories useful for actual snapshot operations. Without this, inventories would just be metadata containers with no practical value. This enables the core workflow of filtered, organized snapshot collection.

**Independent Test**: Can be tested by creating a snapshot with `--inventory baseline` option and verifying it applies the inventory's filters and is stored with the correct naming pattern `{account}-{inventory}-{timestamp}.yaml`.

**Acceptance Scenarios**:

1. **Given** I have an inventory named "baseline" with no filters, **When** I create a snapshot with `--inventory baseline`, **Then** the system captures all resources and stores the snapshot as `123456-baseline-2025-10-28-143000.yaml`
2. **Given** I have an inventory named "team-a-resources" with include-tags "team=alpha", **When** I create a snapshot with `--inventory team-a-resources`, **Then** the system only captures resources matching the filter and stores with correct naming
3. **Given** I do not specify an inventory, **When** I create a snapshot, **Then** the system uses the "default" inventory automatically
4. **Given** I specify a non-existent inventory, **When** I create a snapshot, **Then** the system returns an error message prompting me to create the inventory first

---

### User Story 3 - Analyze Costs and Deltas within Inventory Context (Priority: P3)

As a cloud administrator, I need to run cost and delta analysis within a specific inventory context so that I only see changes and costs relevant to that inventory's filtered resources.

**Why this priority**: This builds on P1 and P2 by enabling analysis operations on inventory-scoped data. Users can now answer questions like "What are my baseline costs?" or "What changed in team-a's resources?" This completes the core workflow loop.

**Independent Test**: Can be tested by running `cost --inventory baseline` and `delta --inventory team-a-resources` commands and verifying they use only snapshots from the specified inventory.

**Acceptance Scenarios**:

1. **Given** I have a "baseline" inventory with multiple snapshots, **When** I run cost analysis with `--inventory baseline`, **Then** the system uses the most recent baseline snapshot and shows costs only for baseline resources
2. **Given** I have a "team-a-resources" inventory with filtered snapshots, **When** I run delta analysis with `--inventory team-a-resources`, **Then** the system compares current state to the inventory's baseline using only filtered resources
3. **Given** I do not specify an inventory for cost/delta commands, **When** I run the command, **Then** the system uses the "default" inventory automatically
4. **Given** I specify an inventory with no snapshots, **When** I run cost or delta analysis, **Then** the system returns an error indicating no snapshots exist in that inventory

---

### User Story 4 - Manage Inventory Lifecycle (Priority: P4)

As a cloud administrator, I need to delete obsolete inventories and manage per-inventory snapshot retention so that I can keep my storage organized and remove outdated organizational structures when they're no longer needed.

**Why this priority**: This is a maintenance/cleanup capability that becomes important over time but isn't needed for initial adoption. Users can create and use inventories for months before needing deletion capabilities.

**Independent Test**: Can be tested by deleting an inventory and verifying it removes the inventory metadata and optionally its snapshots based on user choice.

**Acceptance Scenarios**:

1. **Given** I have an inventory I no longer need, **When** I delete the inventory with confirmation, **Then** the system removes the inventory metadata and prompts about snapshot cleanup
2. **Given** I am deleting an inventory with existing snapshots, **When** I confirm deletion and choose to keep snapshots, **Then** the system removes inventory metadata but leaves snapshot files intact
3. **Given** I am deleting an inventory with existing snapshots, **When** I confirm deletion and choose to delete snapshots, **Then** the system removes both inventory metadata and all associated snapshot files
4. **Given** I try to delete an inventory marked as "active baseline", **When** I attempt deletion, **Then** the system warns me and requires explicit confirmation since this impacts delta/cost commands

---

### Edge Cases

- What happens when a user tries to create an inventory with the same name as an existing one in the same account?
- What happens if AWS credentials change mid-operation (account ID detection)?
- How does the system handle snapshot creation when inventory filters result in zero resources?
- What happens when a user specifies `--inventory` for a snapshot but also provides conflicting `--include-tags` or `--exclude-tags` options?
- How does the system handle very old inventories created before this feature existed during migration?
- What happens if the inventories.yaml file becomes corrupted?
- How does the system behave when multiple CLI instances try to create snapshots simultaneously in the same inventory?
- What happens when a user deletes an inventory but references it in subsequent cost/delta commands?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST store inventories in a central `inventories.yaml` file within the `.snapshots/` directory
- **FR-002**: System MUST auto-detect AWS account ID from the current AWS profile/credentials when creating an inventory
- **FR-003**: System MUST organize snapshots by naming pattern `{account_id}-{inventory_name}-{timestamp}.yaml` in the `.snapshots/snapshots/` directory
- **FR-004**: System MUST treat inventory filters (include-tags, exclude-tags) as immutable once an inventory is created
- **FR-005**: System MUST create a "default" inventory automatically if referenced before it exists
- **FR-006**: System MUST prevent duplicate inventory names within the same AWS account
- **FR-007**: System MUST track which snapshot is marked as "active" (baseline) for each inventory
- **FR-008**: System MUST allow users to create inventories with optional descriptions
- **FR-009**: System MUST allow users to create inventories with optional tag-based filters (include-tags and/or exclude-tags)
- **FR-010**: System MUST validate that inventory names contain only alphanumeric characters, hyphens, and underscores
- **FR-011**: System MUST support listing all inventories for the current AWS account
- **FR-012**: System MUST support showing detailed information for a specific inventory including all snapshots
- **FR-013**: System MUST support deleting inventories with confirmation prompts
- **FR-014**: System MUST allow users to specify which inventory to use when creating snapshots via `--inventory` option
- **FR-015**: System MUST apply inventory filters automatically when creating snapshots within that inventory context
- **FR-016**: System MUST use "default" inventory when no `--inventory` option is provided for snapshot, cost, or delta commands
- **FR-017**: System MUST support cost analysis scoped to a specific inventory via `--inventory` option
- **FR-018**: System MUST support delta analysis scoped to a specific inventory via `--inventory` option
- **FR-019**: System MUST provide migration utility to convert existing snapshots to the new inventory structure
- **FR-020**: System MUST implement per-inventory snapshot retention policies (configurable, not automatic)
- **FR-021**: System MUST prevent deletion of active baseline snapshots without explicit confirmation
- **FR-022**: System MUST handle concurrent access to inventories.yaml safely (file locking or transaction-safe writes)

### Key Entities

- **Inventory**: Represents a named organizational container for snapshots within an AWS account. Contains name, account_id, description, immutable filters (include_tags, exclude_tags), list of snapshot references, active_snapshot reference, creation timestamp, and last_updated timestamp.
- **Snapshot**: Represents a point-in-time capture of AWS resources. Now includes inventory_name to indicate which inventory it belongs to. Maintains existing attributes (name, created_at, account_id, regions, resources, metadata, is_active, service_counts, filters_applied).
- **InventoryStorage**: Service component that manages reading/writing inventories.yaml file and provides inventory CRUD operations with proper error handling and validation.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can create a new inventory and take a filtered snapshot in under 2 minutes
- **SC-002**: System correctly segregates snapshots by account and inventory name in storage, preventing cross-contamination
- **SC-003**: Users can view all inventories for their account and see snapshot counts without opening individual files
- **SC-004**: Cost and delta commands correctly use only snapshots from the specified inventory context
- **SC-005**: Migration utility successfully converts 100% of existing snapshots to the new structure without data loss
- **SC-006**: System handles at least 50 inventories per account and 100 snapshots per inventory without performance degradation
- **SC-007**: Inventory deletion completes in under 10 seconds regardless of snapshot count

## Assumptions

- Users manage one AWS account at a time per CLI session (no simultaneous multi-account operations)
- Inventory names are relatively short (under 50 characters recommended for file path compatibility)
- Filter complexity is limited to tag-based include/exclude rules (no complex query languages)
- Account ID detection via STS GetCallerIdentity is sufficient for all authentication methods
- Concurrent CLI usage is rare (file locking/transactions nice-to-have, not critical for MVP)
- Snapshot files follow existing YAML format and storage location conventions
- Users can manually edit inventories.yaml if needed (human-readable format)
- Inventory retention policies are manual (users run cleanup commands explicitly)
- No automatic reporting or scheduled snapshot creation in this phase

## Dependencies

- Existing snapshot capture and storage infrastructure
- Existing cost analysis and delta detection functionality
- AWS STS API for account ID detection
- YAML file format for inventory metadata storage
- Existing Resource, Snapshot, and ResourceFilter models

## Open Questions

None - design has been clarified through user discussion.
