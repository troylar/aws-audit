# Tasks: AWS Baseline Snapshot & Delta Tracking

**Feature Branch**: `001-aws-baseline-snapshot`
**Input**: Design documents from `/specs/001-aws-baseline-snapshot/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/cli-commands.md

**Tests**: Not explicitly requested in specification - focusing on implementation tasks

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story. User stories are organized by priority (P1 → P2 → P3).

## Format: `- [ ] [ID] [P?] [Story?] Description with file path`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)
- All tasks include exact file paths

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic Python package structure

- [X] T001 Create project directory structure per plan.md (src/, tests/, .snapshots/)
- [X] T002 Initialize Python package with pyproject.toml (boto3, typer, rich, pyyaml, python-dateutil dependencies)
- [X] T003 [P] Create .gitignore file with Python and .snapshots/ entries
- [X] T004 [P] Create README.md with installation and quickstart instructions
- [X] T005 [P] Create requirements.txt from pyproject.toml dependencies

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### Core Models & Data Structures

- [X] T006 [P] Create Snapshot data model in src/models/snapshot.py (name, created_at, account_id, regions, resources, metadata, is_active, filters_applied fields per data-model.md)
- [X] T007 [P] Create Resource data model in src/models/resource.py (arn, type, name, region, tags, config_hash, created_at, raw_config fields)
- [X] T008 [P] Create DeltaReport data model in src/models/delta_report.py (generated_at, snapshot_name, added/deleted/modified resources)
- [X] T009 [P] Create CostReport data model in src/models/cost_report.py (baseline_costs, non_baseline_costs, period, data_completeness)
- [X] T010 [P] Create ResourceChange data model in src/models/resource_change.py (for delta tracking)

### AWS Client Infrastructure

- [X] T011 Create boto3 client wrapper with retry configuration in src/aws/client.py (exponential backoff, adaptive mode per research.md)
- [X] T012 [P] Create AWS credential validation in src/aws/credentials.py (validate credentials, check permissions)
- [X] T013 [P] Create rate limiter utility in src/aws/rate_limiter.py (token bucket algorithm for IAM/CloudFormation throttling)

### Storage Infrastructure

- [ ] T014 Create snapshot storage manager in src/snapshot/storage.py (YAML save/load, compression support per research.md)
- [ ] T015 Create snapshot index manager in src/snapshot/storage.py (manage active snapshot, list snapshots)

### Utilities

- [ ] T016 [P] Create logging configuration in src/utils/logging.py (structured logging with levels)
- [ ] T017 [P] Create progress indicators using rich in src/utils/progress.py (multi-task progress bars per research.md)
- [ ] T018 [P] Create export utilities in src/utils/export.py (JSON/CSV export for reports)
- [ ] T019 [P] Create configuration hash utility in src/utils/hash.py (SHA256 of normalized JSON per research.md)

### CLI Framework

- [ ] T020 Create main CLI entry point using Typer in src/cli.py (global options: --profile, --region, --verbose, --output)
- [ ] T021 Create CLI configuration loader in src/cli/config.py (load .aws-baseline.yaml and environment variables)

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Capture Baseline Snapshot (Priority: P1) 🎯 MVP

**Goal**: Enable cloud administrators to capture a complete point-in-time snapshot of AWS baseline resources, serving as the foundation for all delta tracking and cost analysis

**Independent Test**: Run snapshot create command on a test AWS account and verify all resources (IAM, Lambda, EC2, S3) are inventoried with complete metadata (ARN, tags, creation timestamp, configuration hash)

### Resource Collection Framework

- [ ] T022 [P] [US1] Create base resource collector interface in src/snapshot/resource_collectors/base.py (abstract collect method)
- [ ] T023 [P] [US1] Implement IAM resource collector in src/snapshot/resource_collectors/iam.py (roles, policies, users, groups)
- [ ] T024 [P] [US1] Implement Lambda resource collector in src/snapshot/resource_collectors/lambda_func.py (functions, layers)
- [ ] T025 [P] [US1] Implement EC2 resource collector in src/snapshot/resource_collectors/ec2.py (instances, security groups, VPCs, subnets, volumes)
- [ ] T026 [P] [US1] Implement S3 resource collector in src/snapshot/resource_collectors/s3.py (buckets with metadata)
- [ ] T027 [P] [US1] Implement RDS resource collector in src/snapshot/resource_collectors/rds.py (instances, snapshots)
- [ ] T028 [P] [US1] Implement CloudWatch resource collector in src/snapshot/resource_collectors/cloudwatch.py (alarms, log groups)
- [ ] T029 [P] [US1] Implement SNS resource collector in src/snapshot/resource_collectors/sns.py (topics)
- [ ] T030 [P] [US1] Implement SQS resource collector in src/snapshot/resource_collectors/sqs.py (queues)
- [ ] T031 [P] [US1] Implement DynamoDB resource collector in src/snapshot/resource_collectors/dynamodb.py (tables)

### Snapshot Capturer

- [ ] T032 [US1] Create resource capturer coordinator in src/snapshot/capturer.py (orchestrate collectors, handle multi-region, concurrent collection per research.md)
- [ ] T033 [US1] Add region enumeration to capturer (get enabled regions, handle global vs regional services)
- [ ] T034 [US1] Add API throttling handling to capturer (integrate rate limiter, retry on throttle)
- [ ] T035 [US1] Add progress tracking to capturer (integrate rich progress bars, per-region/service tracking)

### CLI Command: snapshot create

- [ ] T036 [US1] Implement snapshot create command in src/cli.py (NAME argument, --regions, --resource-types, --exclude-types, --set-active, --compress, --metadata, --parallel options per contracts/cli-commands.md)
- [ ] T037 [US1] Add validation to snapshot create (validate snapshot name format, check AWS credentials, validate regions)
- [ ] T038 [US1] Add snapshot summary output (resource counts by service, total execution time, file path)
- [ ] T039 [US1] Add error handling for snapshot create (partial failures, permission errors, clear error messages)

**Checkpoint**: User Story 1 complete - can capture baseline snapshot independently

---

## Phase 4: User Story 2 - View Resource Delta (Priority: P2)

**Goal**: Enable administrators to identify which resources have been added, modified, or removed since the baseline snapshot was taken for drift tracking

**Independent Test**: Create a baseline snapshot, manually add/remove test resources in AWS console, run delta command and verify accurate detection of new, deleted, and modified resources with proper grouping by type

### Delta Calculator

- [ ] T040 [P] [US2] Create delta calculator in src/delta/calculator.py (compare current state to baseline, identify added/deleted/modified resources)
- [ ] T041 [US2] Add change detection logic (use config_hash for modifications, ARN matching for additions/deletions)
- [ ] T042 [US2] Add filtering support to delta calculator (by resource type, by date range, by region)

### Delta Reporter

- [ ] T043 [P] [US2] Create delta report formatter in src/delta/reporter.py (group by type and change type, format output per contracts example)
- [ ] T044 [US2] Add detailed change summary for modified resources (compare baseline vs current hashes, summarize changes)
- [ ] T045 [US2] Add export functionality to delta reporter (JSON and CSV formats)

### CLI Command: delta

- [ ] T046 [US2] Implement delta command in src/cli.py (--snapshot, --resource-type, --change-type, --region, --since, --export, --show-details options per contracts/cli-commands.md)
- [ ] T047 [US2] Add table output formatting for delta (use rich tables, color coding for added/deleted/modified)
- [ ] T048 [US2] Add "no changes detected" handling (exit code 2, friendly message)
- [ ] T049 [US2] Add error handling for delta (no baseline found, API errors)

**Checkpoint**: User Stories 1 AND 2 complete - can capture snapshots and view deltas independently

---

## Phase 5: User Story 3 - Analyze Cost Delta (Priority: P2)

**Goal**: Enable finance/operations teams to understand cost breakdown between baseline "dial tone" resources and non-baseline resources for proper cost allocation and project chargeback

**Independent Test**: Capture a baseline, create test resources with costs, run cost analysis command and verify accurate separation of baseline vs non-baseline costs with percentage breakdown and data completeness indicators

### Cost Explorer Integration

- [ ] T050 [P] [US3] Create Cost Explorer client wrapper in src/cost/explorer.py (GetCostAndUsage API integration per research.md)
- [ ] T051 [US3] Add cost data retrieval with date ranges (daily/monthly granularity, handle data lag warnings)
- [ ] T052 [US3] Add cost data completeness checking (detect missing/incomplete data, calculate data lag days)

### Cost Analyzer

- [ ] T053 [US3] Create cost analyzer in src/cost/analyzer.py (separate baseline vs non-baseline costs based on resource ARNs)
- [ ] T054 [US3] Add service-level cost attribution (map Cost Explorer service costs to snapshot resources)
- [ ] T055 [US3] Add time-based cost filtering (costs before snapshot = baseline, after = non-baseline)
- [ ] T056 [US3] Add tag-based cost grouping (group non-baseline costs by Project/Team tags)

### Cost Reporter

- [ ] T057 [P] [US3] Create cost report formatter in src/cost/reporter.py (baseline vs non-baseline breakdown, percentage calculations per contracts example)
- [ ] T058 [US3] Add data completeness warnings to report (display "data available through" date, lag indicators)
- [ ] T059 [US3] Add export functionality to cost reporter (JSON and CSV formats for financial systems)

### CLI Command: cost

- [ ] T060 [US3] Implement cost command in src/cli.py (--snapshot, --start-date, --end-date, --granularity, --group-by, --export, --currency options per contracts/cli-commands.md)
- [ ] T061 [US3] Add table output formatting for cost (use rich tables, currency formatting, percentage columns)
- [ ] T062 [US3] Add cost estimation messaging ("Estimated monthly cost" per contracts output)
- [ ] T063 [US3] Add error handling for cost (Cost Explorer not enabled, insufficient permissions, data not available)

**Checkpoint**: User Stories 1, 2, AND 3 complete - can capture snapshots, view deltas, and analyze costs independently

---

## Phase 6: User Story 4 - Restore to Baseline (Priority: P3)

**Goal**: Enable administrators to remove all non-baseline resources to return environment to original state for cleanup after testing or project decommissioning

**Independent Test**: Create a baseline, add test resources, run restore in dry-run mode to verify deletion plan, then execute actual restore and confirm all non-baseline resources are removed without affecting baseline resources

### Dependency Management

- [ ] T064 [P] [US4] Create dependency rule definitions in src/restore/dependency.py (DEPENDENCY_RULES dict per research.md: EC2→SG, Lambda→IAM, etc.)
- [ ] T065 [US4] Create dependency graph builder in src/restore/dependency.py (build directed graph from resource types)
- [ ] T066 [US4] Implement topological sort in src/restore/dependency.py (Kahn's algorithm for safe deletion order)

### Resource Deletion

- [ ] T067 [P] [US4] Create resource deletion handlers in src/restore/executor.py (per-service deletion API calls with error handling)
- [ ] T068 [US4] Create restore executor in src/restore/executor.py (delete resources in dependency order, continue on error)
- [ ] T069 [US4] Add deletion progress tracking (integrate rich progress bars, show per-service deletion status)
- [ ] T070 [US4] Add failed deletion logging (capture errors, provide detailed failure summary)

### Dry-Run Support

- [ ] T071 [P] [US4] Create dry-run simulator in src/restore/dry_run.py (preview deletions without executing)
- [ ] T072 [US4] Add cost savings estimation to dry-run (calculate monthly cost of resources to be deleted)

### CLI Command: restore

- [ ] T073 [US4] Implement restore command in src/cli.py (--snapshot, --dry-run, --resource-type, --exclude, --exclude-tag, --region, --yes, --continue-on-error options per contracts/cli-commands.md)
- [ ] T074 [US4] Add confirmation prompt (require "DELETE" typing for actual restoration per contracts example)
- [ ] T075 [US4] Add restore summary output (table with attempted/succeeded/failed counts per resource type)
- [ ] T076 [US4] Add error handling for restore (no baseline, cannot delete resources, permission errors)
- [ ] T077 [US4] Add protection for active snapshot (prevent deletion if snapshot is currently active)

**Checkpoint**: User Stories 1-4 complete - full snapshot, delta, cost, and restore workflow functional

---

## Phase 7: User Story 5 - Create Historical Baseline (Priority: P2)

**Goal**: Enable administrators to create baseline snapshots representing resources as they existed at specific points in time, filtered by creation date and tags, for retroactive baseline establishment

**Independent Test**: Create resources at different times with different tags, create a historical baseline with --before-date and --filter-tags, verify only matching resources are included and filtering transparency is reported

### Resource Filtering

- [ ] T078 [P] [US5] Create ResourceFilter class in src/snapshot/filter.py (before_date, after_date, required_tags parameters)
- [ ] T079 [US5] Implement date filtering in ResourceFilter (match created_at timestamps, handle missing timestamps)
- [ ] T080 [US5] Implement tag filtering in ResourceFilter (AND logic for multiple tags per spec)
- [ ] T081 [US5] Add filtering statistics tracking (total collected, date matched, tag matched, final count)
- [ ] T082 [US5] Add creation timestamp extraction per service (handle service-specific field names: CreateDate, LaunchTime, CreationDate per research.md)

### Enhanced CLI Command: snapshot create

- [ ] T083 [US5] Add date filtering options to snapshot create (--before-date, --after-date, --between-dates per contracts/cli-commands.md)
- [ ] T084 [US5] Add tag filtering options to snapshot create (--filter-tags with Key=Value,Key2=Value2 format)
- [ ] T085 [US5] Add filter validation (date format YYYY-MM-DD, tag format Key=Value)
- [ ] T086 [US5] Add filtering summary output (show "X collected, Y matched filters, Z final" per contracts output example)
- [ ] T087 [US5] Store filters_applied in snapshot metadata (date_filters, tag_filters, total_resources_before_filter)

**Checkpoint**: User Story 5 complete - can create historical and filtered baselines

---

## Phase 8: User Story 6 - Manage Multiple Snapshots (Priority: P3)

**Goal**: Enable administrators to manage multiple baseline snapshots over time as the approved baseline configuration evolves with platform updates or organizational changes

**Independent Test**: Create multiple snapshots with different names, list them, switch active baseline between them, delete old snapshots, verify only one is active at a time

### Snapshot Management

- [ ] T088 [US6] Enhance snapshot storage to support multiple named snapshots (already designed in storage.py, ensure full implementation)
- [ ] T089 [US6] Add active snapshot tracking (active marker file, atomicity per data-model.md)
- [ ] T090 [US6] Add snapshot listing with sorting (by name, created, resources, size)

### CLI Commands: snapshot list, show, set-active, delete

- [ ] T091 [P] [US6] Implement snapshot list command in src/cli.py (--sort-by, --reverse options per contracts/cli-commands.md)
- [ ] T092 [P] [US6] Implement snapshot show command in src/cli.py (NAME argument, --resources, --group-by options)
- [ ] T093 [P] [US6] Implement snapshot set-active command in src/cli.py (NAME argument, switch active baseline)
- [ ] T094 [P] [US6] Implement snapshot delete command in src/cli.py (NAME argument, --yes option, prevent deletion of active)
- [ ] T095 [US6] Add rich table formatting for snapshot list (name, created, resources, active indicator, size)
- [ ] T096 [US6] Add detailed snapshot metadata display for show (service breakdown, region info, metadata fields)

**Checkpoint**: All user stories complete - full snapshot management lifecycle functional

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories and final release preparation

### Documentation

- [ ] T097 [P] Update README.md with complete feature documentation (installation, all commands, examples)
- [ ] T098 [P] Create CHANGELOG.md with v1.0.0 release notes
- [ ] T099 [P] Add docstrings to all public functions and classes
- [ ] T100 [P] Validate quickstart.md examples still work

### Error Handling & User Experience

- [ ] T101 [P] Standardize error messages across all commands (consistent format, helpful remediation guidance)
- [ ] T102 [P] Add permission error handling with required IAM policy suggestions
- [ ] T103 Add comprehensive logging throughout application (DEBUG level for troubleshooting)

### Output Formatting

- [ ] T104 [P] Add JSON output format support (--output json for all commands per contracts/cli-commands.md)
- [ ] T105 [P] Add YAML output format support (--output yaml for all commands)
- [ ] T106 Ensure colored output respects --no-color and NO_COLOR environment variable

### Configuration

- [ ] T107 [P] Implement .aws-baseline.yaml configuration file loading (snapshot_dir, regions, resource_types per contracts)
- [ ] T108 [P] Implement environment variable support (AWS_BASELINE_SNAPSHOT_DIR, AWS_BASELINE_LOG_LEVEL per contracts)

### Performance & Optimization

- [ ] T109 Code cleanup and refactoring (remove duplicated code, improve readability)
- [ ] T110 Performance testing with large resource counts (1000+ resources, verify <2min delta calculation)

### Packaging & Distribution

- [ ] T111 [P] Configure entry point in pyproject.toml (aws-baseline command)
- [ ] T112 [P] Add version command (--version showing tool, Python, boto3 versions per contracts)
- [ ] T113 [P] Add comprehensive help text for all commands (--help per contracts)
- [ ] T114 Test installation from package (pip install -e .)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phases 3-8)**: All depend on Foundational phase completion
  - Can proceed in parallel if multiple developers available
  - Or sequentially in priority order: US1 (P1) → US5 (P2) → US2 (P2) → US3 (P2) → US4 (P3) → US6 (P3)
- **Polish (Phase 9)**: Depends on desired user stories being complete

### User Story Dependencies

- **US1 - Capture Baseline Snapshot (P1)**: No dependencies on other stories - can start immediately after Foundational
- **US2 - View Resource Delta (P2)**: Depends on US1 (needs snapshot functionality) but independently testable
- **US3 - Analyze Cost Delta (P2)**: Depends on US1 (needs snapshot functionality) but independently testable
- **US4 - Restore to Baseline (P3)**: Depends on US1 and US2 (needs snapshot and delta) but independently testable
- **US5 - Create Historical Baseline (P2)**: Enhances US1 (adds filtering to snapshot create) - minimal dependencies
- **US6 - Manage Multiple Snapshots (P3)**: Enhances US1 (adds snapshot management commands) - minimal dependencies

### Within Each User Story

- Models/collectors can run in parallel (marked [P])
- Core implementation before integration
- CLI commands after core functionality is complete

### Parallel Opportunities

- **Phase 1**: T003, T004, T005 can run in parallel
- **Phase 2**: T006-T010 (models), T012-T013 (AWS utils), T016-T019 (utilities) can all run in parallel
- **Phase 3 (US1)**: T023-T031 (all resource collectors) can run in parallel
- **Phase 4 (US2)**: T040 and T043 can run in parallel
- **Phase 5 (US3)**: T050, T057 can run in parallel
- **Phase 6 (US4)**: T064, T067, T071 can run in parallel
- **Phase 7 (US5)**: T078 and T082 can start in parallel
- **Phase 8 (US6)**: T091-T094 (CLI commands) can run in parallel
- **Phase 9**: Most tasks can run in parallel (T097-T108, T112-T113)

**Once Foundational (Phase 2) completes**: US1, US5, US6 can start in parallel (different files). Then US2, US3 can start. Finally US4.

---

## Parallel Example: Phase 2 (Foundational)

```bash
# All data models can be created in parallel:
Task T006: "Create Snapshot data model in src/models/snapshot.py"
Task T007: "Create Resource data model in src/models/resource.py"
Task T008: "Create DeltaReport data model in src/models/delta_report.py"
Task T009: "Create CostReport data model in src/models/cost_report.py"
Task T010: "Create ResourceChange data model in src/models/resource_change.py"

# All AWS utilities can be created in parallel:
Task T012: "Create AWS credential validation in src/aws/credentials.py"
Task T013: "Create rate limiter utility in src/aws/rate_limiter.py"

# All utility modules can be created in parallel:
Task T016: "Create logging configuration in src/utils/logging.py"
Task T017: "Create progress indicators using rich in src/utils/progress.py"
Task T018: "Create export utilities in src/utils/export.py"
Task T019: "Create configuration hash utility in src/utils/hash.py"
```

---

## Parallel Example: User Story 1 (Resource Collectors)

```bash
# All resource collectors can be implemented in parallel:
Task T023: "Implement IAM resource collector in src/snapshot/resource_collectors/iam.py"
Task T024: "Implement Lambda resource collector in src/snapshot/resource_collectors/lambda_func.py"
Task T025: "Implement EC2 resource collector in src/snapshot/resource_collectors/ec2.py"
Task T026: "Implement S3 resource collector in src/snapshot/resource_collectors/s3.py"
Task T027: "Implement RDS resource collector in src/snapshot/resource_collectors/rds.py"
Task T028: "Implement CloudWatch resource collector in src/snapshot/resource_collectors/cloudwatch.py"
Task T029: "Implement SNS resource collector in src/snapshot/resource_collectors/sns.py"
Task T030: "Implement SQS resource collector in src/snapshot/resource_collectors/sqs.py"
Task T031: "Implement DynamoDB resource collector in src/snapshot/resource_collectors/dynamodb.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T005)
2. Complete Phase 2: Foundational (T006-T021) - CRITICAL
3. Complete Phase 3: User Story 1 (T022-T039)
4. **STOP and VALIDATE**: Test snapshot create command on test AWS account
5. Verify all resources captured with correct metadata
6. Deploy/demo MVP

**MVP Delivers**: Ability to capture complete baseline snapshots - the foundation for all other features

### Incremental Delivery (Recommended)

1. **Iteration 1**: Setup + Foundational + US1 (Capture Baseline) → Test → Deploy
   - Users can start creating baseline snapshots
2. **Iteration 2**: + US5 (Historical Baseline) → Test → Deploy
   - Users can create date/tag-filtered baselines
3. **Iteration 3**: + US2 (View Delta) → Test → Deploy
   - Users can track resource changes
4. **Iteration 4**: + US3 (Cost Analysis) → Test → Deploy
   - Users can analyze cost breakdown
5. **Iteration 5**: + US6 (Snapshot Management) → Test → Deploy
   - Users can manage multiple snapshots
6. **Iteration 6**: + US4 (Restore) + Polish → Test → Deploy
   - Full feature set complete

### Parallel Team Strategy

With multiple developers:

1. **Together**: Complete Phase 1 (Setup) and Phase 2 (Foundational)
2. **After Foundational complete**:
   - Developer A: US1 (Snapshot Capture - P1) - highest priority
   - Developer B: US5 (Historical Baseline - P2) - enhances US1
   - Developer C: US6 (Snapshot Management - P3) - enhances US1
3. **After US1 complete**:
   - Developer D: US2 (Delta - P2) - depends on US1
   - Developer E: US3 (Cost - P2) - depends on US1
4. **After US1, US2 complete**:
   - Developer F: US4 (Restore - P3) - depends on US1, US2
5. **All**: Phase 9 (Polish) together

---

## Task Summary

- **Total Tasks**: 114
- **Phase 1 (Setup)**: 5 tasks
- **Phase 2 (Foundational)**: 16 tasks (BLOCKING)
- **Phase 3 (US1 - Capture Baseline)**: 18 tasks
- **Phase 4 (US2 - View Delta)**: 10 tasks
- **Phase 5 (US3 - Cost Analysis)**: 14 tasks
- **Phase 6 (US4 - Restore)**: 14 tasks
- **Phase 7 (US5 - Historical Baseline)**: 10 tasks
- **Phase 8 (US6 - Snapshot Management)**: 9 tasks
- **Phase 9 (Polish)**: 18 tasks

**Parallelizable Tasks**: 55 tasks marked with [P] (48%)

**Estimated MVP Effort** (Phase 1 + 2 + 3): 39 tasks for basic snapshot capture functionality

---

## Notes

- [P] tasks can run in parallel (different files, no inter-task dependencies)
- [Story] label maps task to specific user story for traceability
- Each user story should be independently testable
- Commit frequently (after each task or logical group)
- Stop at any checkpoint to validate story independently
- Foundational phase (Phase 2) must be 100% complete before starting any user story
- User stories can be implemented in priority order or in parallel (if team capacity allows)
