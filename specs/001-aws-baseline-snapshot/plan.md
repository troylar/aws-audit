# Implementation Plan: AWS Baseline Snapshot & Delta Tracking

**Branch**: `001-aws-baseline-snapshot` | **Date**: 2025-10-26 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-aws-baseline-snapshot/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Build a Python CLI tool that captures point-in-time snapshots of AWS cloud landing zone baseline resources, tracks resource deltas over time, separates baseline vs. non-baseline costs for chargeback, and provides restoration capabilities to return environments to baseline state. The tool will support multi-region AWS deployments with robust error handling, progress indication, and data export capabilities.

## Technical Context

**Language/Version**: Python 3.8+ (supports 3.8-3.13 based on project standards)
**Primary Dependencies**:
- boto3 (AWS SDK for Python) - AWS API interactions
- typer (CLI framework) - command-line interface
- rich (terminal UI) - progress bars, formatted output, tables
- pyyaml (configuration) - snapshot storage format
- python-dateutil - date/time handling for cost analysis

**Storage**: Local filesystem (JSON/YAML files for snapshots), no database required
**Testing**: pytest with coverage (unit tests, integration tests with mocked boto3)
**Target Platform**: Cross-platform CLI (Linux, macOS, Windows) - runs wherever Python 3.8+ and boto3 are available
**Project Type**: Single project - command-line tool with library modules
**Performance Goals**:
- Snapshot 100-500 resources in <5 minutes
- Delta calculation for 1000 resources in <2 minutes
- Cost report generation in <2 minutes
**Constraints**:
- AWS API rate limits (handled with exponential backoff)
- AWS Cost Explorer data lag (24-48 hours)
- Offline mode not possible (requires AWS API connectivity)
- Memory: handle large resource inventories (1000+ resources) efficiently
**Scale/Scope**:
- Target: 100-1000 AWS resources per snapshot
- Support for 10+ AWS service types initially (extensible)
- Multiple regions per snapshot
- Multiple snapshots per project

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Initial Check (Pre-Phase 0)**:
- Status: ✅ PASS
- No constitution violations detected
- Standard Python CLI project patterns

**Post-Design Check (After Phase 1)**:
- Status: ✅ PASS - Design confirmed alignment
- Architecture Review:
  - ✅ Single project structure maintained (src/ and tests/)
  - ✅ CLI-first design via typer framework (confirmed in contracts)
  - ✅ Library modules separable from CLI (snapshot, delta, cost, restore modules)
  - ✅ Test coverage planned with pytest (unit + integration)
  - ✅ Standard Python packaging (pyproject.toml, setup.py)
  - ✅ No architectural complexity concerns
- Data Model Review:
  - ✅ Simple, well-defined entities (Snapshot, Resource, DeltaReport, CostReport)
  - ✅ Local file storage (YAML) - no database complexity
  - ✅ Clear validation rules and relationships
- CLI Contracts Review:
  - ✅ Consistent command structure
  - ✅ Standard conventions (options, exit codes, output formats)
  - ✅ No unnecessary complexity in user interface

**Final Gate Result**: ✅ PASS - Design complete, ready for implementation

## Project Structure

### Documentation (this feature)

```text
specs/001-aws-baseline-snapshot/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
│   └── cli-commands.md  # CLI command specifications
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
aws-baseline/
├── src/
│   ├── __init__.py
│   ├── cli.py                    # Typer CLI entry point
│   ├── snapshot/
│   │   ├── __init__.py
│   │   ├── capturer.py           # Resource inventory capture
│   │   ├── storage.py            # Snapshot persistence
│   │   └── resource_collectors/  # Per-service resource collection
│   │       ├── __init__.py
│   │       ├── iam.py
│   │       ├── lambda_func.py
│   │       ├── ec2.py
│   │       ├── s3.py
│   │       └── base.py           # Base collector interface
│   ├── delta/
│   │   ├── __init__.py
│   │   ├── calculator.py         # Delta computation logic
│   │   └── reporter.py           # Delta report formatting
│   ├── cost/
│   │   ├── __init__.py
│   │   ├── explorer.py           # AWS Cost Explorer integration
│   │   ├── analyzer.py           # Cost separation logic
│   │   └── reporter.py           # Cost report formatting
│   ├── restore/
│   │   ├── __init__.py
│   │   ├── dependency.py         # Dependency graph builder
│   │   ├── executor.py           # Resource deletion execution
│   │   └── dry_run.py            # Dry-run simulation
│   ├── models/
│   │   ├── __init__.py
│   │   ├── snapshot.py           # Snapshot data model
│   │   ├── resource.py           # Resource data model
│   │   ├── delta_report.py       # Delta report model
│   │   └── cost_report.py        # Cost report model
│   ├── aws/
│   │   ├── __init__.py
│   │   ├── client.py             # Boto3 client wrapper with retry
│   │   └── credentials.py        # Credential validation
│   └── utils/
│       ├── __init__.py
│       ├── logging.py            # Logging configuration
│       ├── progress.py           # Progress indicators (rich)
│       └── export.py             # JSON/CSV export utilities
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py               # Pytest fixtures
│   ├── unit/
│   │   ├── __init__.py
│   │   ├── test_snapshot_capturer.py
│   │   ├── test_delta_calculator.py
│   │   ├── test_cost_analyzer.py
│   │   ├── test_restore_executor.py
│   │   └── test_models.py
│   └── integration/
│       ├── __init__.py
│       ├── test_snapshot_workflow.py
│       ├── test_delta_workflow.py
│       ├── test_cost_workflow.py
│       └── test_cli_commands.py
│
├── .snapshots/                   # Default snapshot storage directory
├── pyproject.toml                # Project metadata, dependencies
├── setup.py                      # Package setup (if needed for editable install)
├── README.md                     # User documentation
└── requirements.txt              # Runtime dependencies
```

**Structure Decision**: Single project structure is appropriate for a CLI tool. The source code is organized by functional domain (snapshot, delta, cost, restore) with shared models and utilities. This structure supports:
- Independent testing of each module
- Clear separation of concerns
- Extensibility (adding new resource collectors)
- CLI as thin orchestration layer over library modules

## Complexity Tracking

No violations detected - this section is not applicable.

## Phase 0: Research & Technology Decisions

### Research Areas

1. **AWS Resource Enumeration Patterns**
   - **Question**: What's the most efficient way to enumerate AWS resources across multiple service APIs?
   - **Need**: Must capture 100-500 resources in <5 minutes across 10+ service types
   - **Research Focus**: boto3 resource vs. client interfaces, pagination best practices, parallel API calls

2. **AWS Cost Explorer API Integration**
   - **Question**: How to accurately map costs to specific resources and handle data lag?
   - **Need**: Separate baseline vs. non-baseline costs with <1% error margin
   - **Research Focus**: Cost Explorer API capabilities, resource-level cost attribution, handling incomplete data

3. **AWS Resource Dependency Detection**
   - **Question**: How to determine deletion order to avoid dependency failures?
   - **Need**: 95% successful deletion rate for restore operations
   - **Research Focus**: boto3 resource dependency patterns, AWS CloudFormation dependency graphs, common dependency chains

4. **Configuration Hash for Change Detection**
   - **Question**: How to detect resource configuration changes efficiently?
   - **Need**: Identify modified resources in delta calculation
   - **Research Focus**: Normalization strategies, which resource attributes to hash, handling dynamic values (timestamps, etc.)

5. **AWS API Rate Limiting Strategies**
   - **Question**: How to handle API throttling gracefully during large-scale operations?
   - **Need**: Complete operations despite rate limits without user intervention
   - **Research Focus**: boto3 retry configuration, exponential backoff patterns, AWS API throttling limits per service

6. **Snapshot Storage Format**
   - **Question**: JSON vs. YAML for snapshot persistence? Compression needed?
   - **Need**: Human-readable, version-controllable, efficient storage
   - **Research Focus**: Size estimates for 1000 resources, diff-friendly formats, compression trade-offs

7. **Multi-Region Resource Tracking**
   - **Question**: How to efficiently query resources across multiple regions?
   - **Need**: Support multi-region deployments without excessive API calls
   - **Research Focus**: boto3 region enumeration, parallel region queries, region-specific resource types

8. **Progress Indication for Long Operations**
   - **Question**: How to provide accurate progress estimates for variable-length operations?
   - **Need**: Users can estimate completion time for long-running tasks
   - **Research Focus**: rich library progress bars, async progress updates, estimating total work before completion

9. **Resource Filtering by Date and Tags**
   - **Question**: How to efficiently filter resources by creation date and AWS tags after collection?
   - **Need**: Enable historical baseline creation and tag-based baseline definitions
   - **Research Focus**: Timestamp availability across AWS services, tag extraction patterns, filter performance for large resource sets

### Research Outputs

Research findings will be documented in `research.md` with:
- Decision: Technology/pattern chosen
- Rationale: Why it best meets requirements
- Alternatives considered: What else was evaluated
- Implementation notes: Key details for Phase 1

## Phase 1: Design Artifacts

### Data Model (`data-model.md`)

Will document entity schemas for:
- **Snapshot**: name, timestamp, account_id, regions, resources, metadata
- **Resource**: arn, type, name, tags, config_hash, region, created_at
- **DeltaReport**: added, deleted, modified, timestamp, snapshot_ref
- **CostReport**: baseline_costs, non_baseline_costs, period, groupings, completeness
- **ResourceDependency**: resource_id, depends_on, dependency_type

### CLI Contracts (`contracts/cli-commands.md`)

Will document command specifications:
- `aws-baseline snapshot create [--name] [--regions] [--resource-types]`
- `aws-baseline snapshot list`
- `aws-baseline snapshot show <name>`
- `aws-baseline snapshot set-active <name>`
- `aws-baseline snapshot delete <name>`
- `aws-baseline delta [--resource-type] [--format json|table]`
- `aws-baseline cost [--start-date] [--end-date] [--group-by] [--format json|csv]`
- `aws-baseline restore [--dry-run] [--exclude] [--yes]`

Each command will specify:
- Arguments and options
- Output format
- Exit codes
- Examples

### Quickstart Guide (`quickstart.md`)

Will provide:
- Installation instructions (pip install, prerequisites)
- AWS credential setup
- First snapshot creation
- Basic delta/cost workflows
- Common use cases

## Phase 2: Task Breakdown (Not Generated by This Command)

Task breakdown will be generated by `/speckit.tasks` command after this plan is complete. The task list will be organized by priority (P1 snapshot, P2 delta/cost, P3 restore/management) and include:
- Development tasks per module
- Test implementation tasks
- Integration tasks
- Documentation tasks

## Next Steps

1. ✅ Complete this plan document
2. → Execute Phase 0: Research (automated by this command)
3. → Execute Phase 1: Generate data model, contracts, quickstart (automated by this command)
4. → Update agent context (automated by this command)
5. → Re-evaluate constitution check post-design
6. User runs `/speckit.tasks` to generate task breakdown
7. User runs `/speckit.implement` to execute tasks

---

**Plan Status**: Initial plan complete, proceeding to Phase 0 research.
