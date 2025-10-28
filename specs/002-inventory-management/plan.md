# Implementation Plan: Multi-Account Inventory Management

**Branch**: `002-inventory-management` | **Date**: 2025-10-28 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/002-inventory-management/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

This feature adds multi-account inventory management to organize AWS resource snapshots by account with named inventories, saved filter presets, and time-stamped snapshot tracking. The system enables users to create named inventories (e.g., "baseline", "team-a-resources") with immutable tag-based filters, automatically apply these filters during snapshot capture, and scope cost/delta analysis to specific inventory contexts. The implementation reuses existing snapshot, storage, filtering, and analysis infrastructure while adding a new Inventory model, InventoryStorage service, and CLI commands for inventory lifecycle management.

## Technical Context

**Language/Version**: Python 3.8+ (supports 3.8-3.13 per pyproject.toml)
**Primary Dependencies**: boto3 (AWS SDK), typer (CLI), rich (terminal UI), pyyaml (storage), python-dateutil (timestamps)
**Storage**: Local filesystem YAML files (.snapshots/inventories.yaml, .snapshots/snapshots/*.yaml)
**Testing**: pytest, pytest-cov (existing test infrastructure)
**Target Platform**: Linux/macOS/Windows CLI
**Project Type**: Single CLI application with modular architecture
**Performance Goals**: Handle 50 inventories per account, 100 snapshots per inventory without degradation (per SC-006)
**Constraints**: <2 minutes to create inventory + snapshot (SC-001), <10 seconds for inventory deletion (SC-007)
**Scale/Scope**: 3 new CLI commands (inventory create/list/show/delete), 2 new models (Inventory, InventoryStorage), updates to 3 existing commands (snapshot, cost, delta)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Note**: This project does not have a formal constitution file yet (template placeholder found). Applying standard Python CLI project principles:

| Principle | Status | Notes |
|-----------|--------|-------|
| Single Responsibility | ✅ PASS | Feature adds inventory organization without changing core snapshot/cost/delta logic |
| Reusability | ✅ PASS | Reuses existing models, storage patterns, and CLI framework |
| Testability | ✅ PASS | All components independently testable, no hard dependencies |
| Maintainability | ✅ PASS | Follows existing patterns (models/, cli/, snapshot/), consistent naming |
| Backward Compatibility | ✅ PASS | Default inventory auto-created, existing commands work unchanged |

**No violations - proceed to Phase 0.**

## Project Structure

### Documentation (this feature)

```text
specs/002-inventory-management/
├── spec.md              # Feature specification (complete)
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (next)
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── checklists/          # Quality validation
│   └── requirements.md  # Spec quality checklist (complete)
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
src/
├── models/
│   ├── inventory.py              # NEW: Inventory dataclass
│   ├── snapshot.py               # UPDATED: Add inventory_name field
│   ├── resource.py               # EXISTING: No changes
│   ├── cost_report.py            # EXISTING: No changes
│   └── delta_report.py           # EXISTING: No changes
├── snapshot/
│   ├── inventory_storage.py      # NEW: InventoryStorage service
│   ├── storage.py                # UPDATED: Inventory-aware snapshot naming/loading
│   ├── capturer.py               # UPDATED: Accept inventory parameter
│   ├── filter.py                 # EXISTING: Reused for inventory filters
│   └── resource_collectors/      # EXISTING: No changes
├── cli/
│   ├── main.py                   # UPDATED: Add inventory commands, update snapshot/cost/delta
│   ├── config.py                 # EXISTING: No changes
│   └── __init__.py               # EXISTING: No changes
├── cost/
│   ├── analyzer.py               # UPDATED: Accept inventory-scoped snapshots
│   ├── explorer.py               # EXISTING: No changes
│   └── reporter.py               # EXISTING: No changes
├── delta/
│   ├── calculator.py             # UPDATED: Accept inventory-scoped snapshots
│   └── reporter.py               # EXISTING: No changes
├── aws/
│   ├── credentials.py            # EXISTING: Reused for account ID detection
│   └── [other files]             # EXISTING: No changes
└── utils/
    └── [all files]               # EXISTING: No changes

tests/
├── unit/
│   ├── test_inventory_model.py           # NEW
│   ├── test_inventory_storage.py         # NEW
│   ├── test_snapshot_model_updated.py    # NEW (verify inventory_name)
│   └── [existing tests]                  # UPDATED as needed
├── integration/
│   ├── test_inventory_workflow.py        # NEW (create→snapshot→cost/delta)
│   ├── test_migration.py                 # NEW (migrate old snapshots)
│   └── [existing tests]                  # EXISTING
└── contract/
    └── [no new contracts needed]         # CLI-only changes

.snapshots/                               # Storage directory
├── inventories.yaml                      # NEW: Central inventory metadata
└── snapshots/
    ├── 123456-baseline-*.yaml            # NEW naming pattern
    ├── 123456-team-a-*.yaml              # NEW naming pattern
    └── [legacy snapshots]                # Existing, migrated via utility
```

**Structure Decision**: Single project structure maintained. All new code follows existing patterns:
- Models in `src/models/` (Inventory dataclass similar to Snapshot)
- Storage services in `src/snapshot/` (InventoryStorage similar to snapshot/storage.py)
- CLI commands in `src/cli/main.py` (typer app with inventory group)
- Tests mirror source structure in `tests/`

## Complexity Tracking

> **No violations identified - this section left empty per template instructions.**

## Phase 0: Research & Decisions

### Research Topics

1. **YAML File Concurrency Safety**
   - **Question**: How to handle concurrent reads/writes to inventories.yaml?
   - **Options**: File locking (fcntl), atomic writes (write temp + rename), optimistic locking (version field)
   - **Decision needed**: Per FR-022, system MUST handle concurrent access safely

2. **Snapshot Naming Migration Strategy**
   - **Question**: How to migrate existing snapshots to new naming pattern without breaking existing workflows?
   - **Options**: In-place rename, symlinks, metadata-only migration, parallel storage
   - **Decision needed**: Per FR-019, migration utility must convert 100% without data loss (SC-005)

3. **Default Inventory Auto-Creation**
   - **Question**: When/how to create default inventory automatically?
   - **Options**: On first snapshot command, on first inventory list, explicit init command, lazy on-demand
   - **Decision needed**: Per FR-005, must be automatic; affects UX for new users

4. **Inventory Filter Conflict Resolution**
   - **Question**: What happens if user provides both --inventory and --include-tags/--exclude-tags?
   - **Options**: Error (exclusive), merge (AND logic), override (CLI wins), ignore (inventory wins)
   - **Decision needed**: Edge case from spec.md line 83, affects user experience

### Deliverable

Create `research.md` documenting:
- Decision for each topic above
- Rationale (why chosen)
- Alternatives considered and rejected
- Code examples or pseudo-code for implementation approach

