# Tasks: Multi-Account Inventory Management

**Input**: Design documents from `/specs/002-inventory-management/`
**Prerequisites**: plan.md, spec.md, data-model.md, research.md, quickstart.md

**Tests**: Not requested in specification - tests are OPTIONAL for this feature.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `src/`, `tests/` at repository root (per plan.md structure decision)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization - ensure .gitignore is properly configured

- [X] T001 [P] Verify .gitignore contains Python patterns (__pycache__/, *.pyc, .venv/, venv/, dist/, *.egg-info/, .DS_Store, *.swp, .vscode/, .idea/)

**Checkpoint**: Project structure ready for feature development

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core data models and storage infrastructure that ALL user stories depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T002 [US1] Create Inventory model dataclass in src/models/inventory.py with fields (name, account_id, include_tags, exclude_tags, snapshots, active_snapshot, description, created_at, last_updated), to_dict(), from_dict(), add_snapshot(), remove_snapshot(), and validate() methods per data-model.md lines 54-132
- [X] T003 [US1] Update Snapshot model in src/models/snapshot.py to add inventory_name field with default value "default" per data-model.md lines 136-171
- [X] T004 [US1] Create InventoryStorage service class in src/snapshot/inventory_storage.py with methods: __init__(storage_dir), load_all(), load_by_account(account_id), get_by_name(name, account_id), get_or_create_default(account_id), save(inventory), delete(name, account_id, delete_snapshots), exists(name, account_id), validate_unique(name, account_id), and _atomic_write() helper per data-model.md lines 257-306

**Checkpoint**: Foundation ready - all models and storage infrastructure in place. User story implementation can now begin.

---

## Phase 3: User Story 1 - Create Named Inventory with Filters (Priority: P1) 🎯 MVP

**Goal**: Enable users to create named inventories with optional tag filters, list all inventories, and view inventory details

**Independent Test**: Per spec.md line 16 - "Can be fully tested by creating an inventory with a name and optional tag filters, then verifying the inventory is stored and can be listed"

### Implementation for User Story 1

- [X] T005 [US1] Add inventory command group to CLI in src/cli/main.py using typer.Typer() with name="inventory" and help text
- [X] T006 [P] [US1] Implement `inventory create` command in src/cli/main.py with parameters: name (required), --description, --include-tags, --exclude-tags, --profile; validate name format (FR-010), auto-detect account ID (FR-002), check for duplicates (FR-006), create Inventory instance, save via InventoryStorage, display success message per quickstart.md lines 38-51
- [X] T007 [P] [US1] Implement `inventory list` command in src/cli/main.py with --profile parameter; load inventories for current account, display table with columns (Name, Snapshots count, Filters summary, Description), show account ID and total count per quickstart.md lines 114-125
- [X] T008 [P] [US1] Implement `inventory show <name>` command in src/cli/main.py with --profile parameter; load specific inventory, display detailed info (name, account, description, created/updated timestamps, filters with include/exclude tags, snapshots list with active marker) per quickstart.md lines 134-154
- [X] T009 [US1] Add helper function parse_tags(tag_string) in src/cli/main.py to convert "key1=val1,key2=val2" format to Dict[str, str] for CLI tag parsing
- [X] T010 [US1] Add error handling in inventory commands for: duplicate name (FR-006), invalid name format (FR-010), nonexistent inventory in show command, AWS credential errors per quickstart.md lines 158-171

**Checkpoint**: Users can create inventories with filters, list all inventories, and view details. This is the minimum viable product (MVP).

---

## Phase 4: User Story 2 - Take Filtered Snapshots within Inventory Context (Priority: P2)

**Goal**: Enable snapshots to be taken within inventory context, automatically applying inventory filters and using correct naming pattern

**Independent Test**: Per spec.md line 33 - "Can be tested by creating a snapshot with `--inventory baseline` option and verifying it applies the inventory's filters and is stored with the correct naming pattern"

**Dependencies**: Requires Phase 3 (US1) complete - inventories must exist before taking snapshots

### Implementation for User Story 2

- [X] T011 [US2] Update `snapshot create` command in src/cli/main.py to add --inventory parameter (Optional[str])
- [X] T012 [US2] Add filter conflict validation in snapshot command: if --inventory AND (--include-tags OR --exclude-tags), raise error with clear message per research.md lines 211-232
- [X] T013 [US2] Implement inventory context logic in snapshot command: if --inventory provided, load inventory and use its filters; else get_or_create_default() and use inline filters per research.md lines 142-181
- [X] T014 [US2] Update snapshot naming in snapshot command to use pattern: {account_id}-{inventory_name}-{timestamp}.yaml (FR-003)
- [X] T015 [US2] Update create_snapshot() call in src/snapshot/capturer.py to accept inventory_name parameter and pass to Snapshot model
- [X] T016 [US2] After snapshot creation, call inventory.add_snapshot(snapshot_filename, set_active=True) and inventory_storage.save(inventory) to register snapshot with inventory
- [X] T017 [US2] Add user feedback messages: "Using inventory: {name}" at start, "Added to inventory '{name}' and marked as active" at end per quickstart.md lines 189-196
- [X] T018 [US2] Add error handling for: nonexistent inventory (FR-014), zero resources after filtering per quickstart.md lines 288-301 and 310-325
- [X] T019 [US2] Update snapshot storage.py to handle both legacy and new naming patterns when loading snapshots (backward compatibility)

**Checkpoint**: Snapshots can be taken in inventory context with automatic filter application and correct naming. Default inventory auto-creation works.

---

## Phase 5: User Story 3 - Analyze Costs and Deltas within Inventory Context (Priority: P3)

**Goal**: Enable cost and delta analysis scoped to specific inventory, using only that inventory's snapshots

**Independent Test**: Per spec.md line 50 - "Can be tested by running `cost --inventory baseline` and `delta --inventory team-a-resources` commands"

**Dependencies**: Requires Phase 4 (US2) complete - snapshots must exist in inventories

### Implementation for User Story 3

- [X] T020 [P] [US3] Update `cost` command in src/cli/main.py to add --inventory parameter and modify snapshot loading logic to: if --inventory, get inventory and use active_snapshot; else get_or_create_default() and use its active_snapshot (FR-017)
- [X] T021 [P] [US3] Update `delta` command in src/cli/main.py to add --inventory parameter and modify baseline snapshot loading logic to: if --inventory, get inventory and use active_snapshot; else get_or_create_default() and use its active_snapshot (FR-018)
- [X] T022 [US3] Add validation in cost command: if inventory has no snapshots, display error "No snapshots exist in inventory '{name}'" with suggestion to take snapshot first per quickstart.md lines 416-427
- [X] T023 [US3] Add validation in cost command: if inventory has no active_snapshot, display error "No active snapshot in inventory '{name}'"
- [X] T024 [US3] Add validation in delta command: if inventory has no snapshots, display error with same logic as T022
- [X] T025 [US3] Add validation in delta command: if inventory has no active_snapshot, display error with same logic as T023
- [X] T026 [US3] Add user feedback in cost/delta commands: "Using inventory: {name}" or "Using 'default' inventory" at command start per quickstart.md lines 336, 370, 404

**Checkpoint**: Cost and delta analysis works with inventory scoping. Users can analyze different inventories independently.

---

## Phase 6: User Story 4 - Manage Inventory Lifecycle (Priority: P4)

**Goal**: Enable deletion of obsolete inventories with optional snapshot cleanup

**Independent Test**: Per spec.md line 67 - "Can be tested by deleting an inventory and verifying it removes the inventory metadata and optionally its snapshots"

**Dependencies**: Requires Phase 3 (US1) complete - inventories must exist to be deleted

### Implementation for User Story 4

- [X] T027 [US4] Implement `inventory delete <name>` command in src/cli/main.py with --profile parameter and --force flag (optional)
- [X] T028 [US4] Add confirmation prompt in delete command: display inventory details (name, snapshot count, active status), ask "Delete inventory '{name}'?" with Yes/No confirmation per quickstart.md lines 438-452
- [X] T029 [US4] Add active baseline warning in delete command: if inventory.active_snapshot is set, show warning "This is the active baseline snapshot! Deleting it will prevent cost/delta analysis..." per quickstart.md lines 472-489
- [X] T030 [US4] Add snapshot deletion prompt in delete command: after inventory deletion confirmed, ask "Delete snapshot files too? [y/N]" per quickstart.md lines 448, 485
- [X] T031 [US4] Implement inventory_storage.delete(name, account_id, delete_snapshots) method logic: remove inventory from inventories.yaml, if delete_snapshots=True then delete all snapshot files from .snapshots/snapshots/ directory, return count of deleted snapshots
- [X] T032 [US4] Add error handling in delete command: nonexistent inventory, last inventory check (cannot delete if it would leave account with zero inventories), file deletion errors
- [X] T033 [US4] Display completion messages: "✓ Inventory '{name}' deleted" and optionally "✓ {count} snapshot file(s) deleted" per quickstart.md lines 450-451, 487-488

**Checkpoint**: Inventory lifecycle management complete. Users can delete obsolete inventories with full control over snapshot retention.

---

## Phase 7: Migration Utility (Supporting Feature)

**Purpose**: Provide utility to migrate existing legacy snapshots to inventory structure

**Dependencies**: Requires Phase 2 (foundational) complete

### Implementation for Migration

- [X] T034 [P] Implement `inventory migrate` command in src/cli/main.py with --profile parameter
- [X] T035 Implement migration logic in migrate command: scan .snapshots/snapshots/ for all .yaml files, load each snapshot, check for inventory_name field, if missing assign to "default" inventory, create/update default inventory in inventories.yaml per research.md lines 86-98
- [X] T036 Add progress feedback in migrate command: "Scanning for legacy snapshots...", "Found {count} snapshot(s) without inventory assignment", "Created 'default' inventory", "Added {count} snapshots to 'default' inventory", "Migration complete!" per quickstart.md lines 517-530
- [X] T037 Add error handling in migrate command: corrupted snapshot files, permission errors, no legacy snapshots found

**Checkpoint**: Legacy snapshots can be migrated to inventory structure without data loss (SC-005).

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Final refinements for production readiness

### Refinements

- [X] T038 [P] Add __init__.py imports in src/models/ to expose Inventory class
- [X] T039 [P] Add __init__.py imports in src/snapshot/ to expose InventoryStorage class
- [X] T040 [P] Update src/cli/__init__.py to ensure inventory commands are registered
- [X] T041 [P] Add logging statements using logger.debug() in InventoryStorage methods (load, save, delete operations)
- [X] T042 [P] Add logging statements in inventory CLI commands for audit trail (create, delete operations)
- [X] T043 Ensure .snapshots/ directory is created if it doesn't exist in InventoryStorage.__init__()
- [X] T044 Ensure inventories.yaml is created with empty structure if it doesn't exist on first load_all()
- [X] T045 [P] Verify inventory name validation regex in Inventory.validate() matches FR-010 specification (alphanumeric, hyphens, underscores only)
- [X] T046 [P] Verify atomic write implementation in InventoryStorage._atomic_write() uses os.replace() per research.md lines 29-44
- [X] T047 Test end-to-end workflow from quickstart.md lines 547-580 (create baseline inventory → take snapshot → create team inventory → take filtered snapshot → list inventories → run cost analysis → run delta analysis → delete inventory)

**Checkpoint**: Feature complete and production-ready!

---

## Dependencies

### User Story Completion Order

```
Phase 1 (Setup) → Phase 2 (Foundational)
                     ↓
                  Phase 3: US1 (Create Inventory) ← MVP
                     ↓
                  Phase 4: US2 (Take Snapshots)
                     ↓
                  Phase 5: US3 (Cost/Delta Analysis)
                     ↓
                  Phase 6: US4 (Delete Inventory)
                     ↓
                  Phase 7: Migration Utility
                     ↓
                  Phase 8: Polish
```

**Critical Path**: Phase 1 → Phase 2 → Phase 3 (MVP) → Phase 4 → Phase 5 → Phase 6

**Parallel Opportunities**:
- Within Phase 2: T002, T003, T004 can be done in parallel (different files)
- Within Phase 3: T006, T007, T008 can be done in parallel after T005
- Within Phase 5: T020, T021 can be done in parallel
- Within Phase 8: Most polish tasks (T038-T046) can be done in parallel

**MVP Scope**: Phases 1-3 deliver the minimum viable product:
- Setup + Foundational infrastructure (T001-T004)
- Inventory CRUD operations (T005-T010)
- This enables users to create, list, and view inventories with filters

**Full Feature**: All phases (1-8) deliver complete functionality:
- MVP + Snapshot integration (Phase 4)
- + Cost/Delta analysis (Phase 5)
- + Inventory deletion (Phase 6)
- + Migration utility (Phase 7)
- + Production polish (Phase 8)

---

## Parallel Execution Examples

### Phase 2 (Foundational) - After T001

```bash
# These can run in parallel (different files):
T002: Create Inventory model (src/models/inventory.py)
T003: Update Snapshot model (src/models/snapshot.py)
T004: Create InventoryStorage (src/snapshot/inventory_storage.py)
```

### Phase 3 (US1) - After T005

```bash
# These can run in parallel (independent commands):
T006: Implement inventory create command
T007: Implement inventory list command
T008: Implement inventory show command
```

### Phase 5 (US3) - All Tasks

```bash
# These can run in parallel (independent commands):
T020: Update cost command with --inventory
T021: Update delta command with --inventory
# (Note: validation tasks T022-T026 depend on their respective command tasks)
```

### Phase 8 (Polish)

```bash
# These can run in parallel (different files/concerns):
T038: Update models __init__.py
T039: Update snapshot __init__.py
T040: Update cli __init__.py
T041: Add logging to InventoryStorage
T042: Add logging to CLI commands
T045: Verify validation regex
T046: Verify atomic write
```

---

## Implementation Strategy

### MVP First (Recommended)

1. **Week 1**: Complete Phases 1-3 (Setup → Foundational → US1)
   - Deliverable: Users can create and manage inventories with filters
   - Value: Immediate organizational capability

2. **Week 2**: Complete Phase 4 (US2)
   - Deliverable: Snapshots integrate with inventories
   - Value: Core workflow enabled

3. **Week 3**: Complete Phases 5-6 (US3 + US4)
   - Deliverable: Analysis and lifecycle management
   - Value: Complete feature set

4. **Week 4**: Complete Phases 7-8 (Migration + Polish)
   - Deliverable: Migration support and production readiness
   - Value: Enterprise-ready solution

### Incremental Delivery

Each phase delivers standalone value:
- **Phase 3**: Inventory management UI/commands
- **Phase 4**: Filtered snapshot collection
- **Phase 5**: Inventory-scoped analysis
- **Phase 6**: Cleanup capabilities
- **Phase 7**: Legacy support

---

## Task Summary

**Total Tasks**: 47
**MVP Tasks**: 10 (T001-T010)
**Parallelizable Tasks**: 18 (marked with [P])

**Tasks by Phase**:
- Phase 1 (Setup): 1 task
- Phase 2 (Foundational): 3 tasks
- Phase 3 (US1): 6 tasks
- Phase 4 (US2): 9 tasks
- Phase 5 (US3): 7 tasks
- Phase 6 (US4): 7 tasks
- Phase 7 (Migration): 4 tasks
- Phase 8 (Polish): 10 tasks

**Tasks by User Story**:
- US1 (Create Inventory): 9 tasks (T002-T010)
- US2 (Take Snapshots): 9 tasks (T011-T019)
- US3 (Cost/Delta Analysis): 7 tasks (T020-T026)
- US4 (Delete Inventory): 7 tasks (T027-T033)
- Setup/Infrastructure: 1 task (T001)
- Migration: 4 tasks (T034-T037)
- Polish: 10 tasks (T038-T047)

**Estimated Effort**:
- MVP (Phases 1-3): ~2-3 days
- Full Feature (All Phases): ~1-2 weeks
- Per-task average: ~2-3 hours

---

## Success Criteria Mapping

| Success Criterion | Related Tasks | Validation Method |
|-------------------|---------------|-------------------|
| SC-001: Create inventory + snapshot in <2 minutes | T002-T019 | Time execution of workflow |
| SC-002: Correct snapshot segregation by account/inventory | T014, T019 | Verify naming pattern and storage |
| SC-003: View inventories with snapshot counts | T007 | Test inventory list command |
| SC-004: Cost/delta use correct inventory snapshots | T020-T026 | Verify analysis uses active_snapshot |
| SC-005: Migration converts 100% without data loss | T034-T037 | Run migration on test snapshots |
| SC-006: Handle 50 inventories, 100 snapshots per inventory | T004 | Performance test with scale |
| SC-007: Inventory deletion in <10 seconds | T027-T033 | Time delete operation |

---

## Format Validation

✅ All tasks follow required format: `- [ ] [ID] [P?] [Story?] Description with file path`
✅ All tasks have sequential IDs (T001-T047)
✅ Parallelizable tasks marked with [P] (18 tasks)
✅ User story tasks labeled with [US#] (32 tasks across US1-US4)
✅ File paths included in all implementation tasks
✅ Setup/Foundational/Polish tasks have NO story labels (15 tasks)

Ready for implementation!
