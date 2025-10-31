<!--
Sync Impact Report - Version 1.0.0 (Initial Ratification)
============================================================
Version Change: [Template] → 1.0.0
Modified Principles: N/A (initial creation)
Added Sections: All (complete constitution from template)
Removed Sections: None

Template Updates Required:
- ✅ plan-template.md: Constitution Check section aligned with principles
- ✅ spec-template.md: User story priorities and testing requirements aligned
- ✅ tasks-template.md: Phase structure and testing discipline aligned

Follow-up TODOs: None
-->

# AWS Inventory Manager Constitution

## Core Principles

### I. CLI-First Design

All features MUST be accessible via the `awsinv` command-line interface. No functionality should require programmatic API usage or GUI interaction. The CLI is the primary interface for all operations.

**Requirements**:
- Every feature exposes complete functionality through CLI commands and options
- Text-based input/output protocol: arguments/stdin → stdout, errors → stderr
- Support both JSON (machine-readable) and Rich terminal output (human-readable)
- All commands follow consistent Typer-based patterns with clear help text

**Rationale**: Users interact with AWS infrastructure through terminals. A well-designed CLI provides automation capabilities, scripting support, and clear operational workflows.

### II. Local-First Storage

Resource snapshots and inventory metadata MUST be stored locally in user-accessible YAML files. No external databases or cloud storage dependencies for core functionality.

**Requirements**:
- Default storage location: `~/.snapshots` (configurable via environment or CLI parameter)
- All data stored as human-readable YAML files
- Storage path precedence: CLI parameter > Environment variable > Default
- File format must be versionable and inspectable without special tools

**Rationale**: Local storage ensures the tool works offline, provides full user control over data, enables version control integration, and eliminates cloud dependencies.

### III. Test-First Development (NON-NEGOTIABLE)

TDD is mandatory for all features. Tests MUST be written, reviewed, and verified to fail BEFORE implementation begins.

**Requirements**:
- Write unit tests for all business logic (pure functions, data models)
- Write integration tests for CLI commands and AWS interactions
- Tests must fail initially (Red), then pass after implementation (Green)
- Minimum 80% code coverage across all modules
- Use pytest with pytest-cov, pytest-mock for all testing

**Rationale**: TDD prevents regressions, ensures testable design, documents expected behavior, and provides confidence in refactoring. The Red-Green-Refactor cycle is strictly enforced.

### IV. Type Safety & Code Quality

All code MUST use strict type hints and pass mypy type checking. Code quality standards are enforced through automated tools.

**Requirements**:
- Full type hints for all function signatures (mypy strict mode: `disallow_untyped_defs=true`)
- Black formatting with 120-character line length
- Ruff linting with E, F, I, N, W rules enabled
- All quality checks pass before merge (enforced via invoke tasks)

**Rationale**: Type safety catches bugs at development time, improves code documentation, enables better IDE support, and makes refactoring safer. Consistent formatting reduces cognitive load.

### V. Python 3.8+ Compatibility

Code MUST support Python 3.8 through 3.13. No features or syntax exclusive to newer versions may be used without explicit compatibility handling.

**Requirements**:
- Minimum version: Python 3.8
- Tested versions: 3.8, 3.9, 3.10, 3.11, 3.12, 3.13
- Use type hints compatible with Python 3.8 (from `__future__ import annotations` if needed)
- All dependencies must support Python 3.8+

**Rationale**: Broad Python version support ensures the tool works in diverse environments (enterprise systems, CI/CD pipelines, legacy infrastructure).

### VI. AWS Resource Coverage & Accuracy

Resource snapshots MUST accurately represent AWS infrastructure state. All supported services must capture complete resource metadata.

**Requirements**:
- Each supported AWS service must capture all relevant resource types
- Resource data must include ARN, tags, region, creation date, and service-specific attributes
- Snapshot accuracy: 100% of resources matching filter criteria must be captured
- Delta calculations must accurately identify added, modified, and removed resources

**Rationale**: Users rely on snapshot accuracy for cost analysis, compliance auditing, and infrastructure management. Incomplete or inaccurate data undermines trust.

### VII. Performance & Scalability

CLI commands MUST perform efficiently even with large resource inventories (10,000+ resources).

**Requirements**:
- Summary generation: <3 seconds for 10,000 resources
- Filtering operations: <2 seconds for any filter combination
- Memory-efficient processing: Use generators/streaming for large datasets
- Pagination for detailed views (default: 100 resources per page, configurable)

**Rationale**: Users managing large AWS environments need responsive tools. Inefficient operations create friction and limit adoption.

## Development Standards

### Code Organization

**Module Structure**:
- `src/cli/`: CLI entry points and command definitions (Typer)
- `src/models/`: Data models (dataclasses with type hints)
- `src/snapshot/`: Snapshot capture and storage logic
- `src/delta/`: Delta calculation algorithms
- `src/cost/`: Cost analysis integration
- `src/aws/`: AWS client utilities and service integrations
- `src/utils/`: Shared utilities (export, pagination, formatting)

**Testing Structure**:
- `tests/unit/`: Fast, isolated tests for business logic
- `tests/integration/`: End-to-end CLI and AWS integration tests

### Dependencies

**Core Dependencies** (locked minimum versions):
- `boto3>=1.28.0`: AWS SDK for Python
- `typer>=0.9.0`: CLI framework
- `rich>=13.0.0`: Terminal UI and formatting
- `pyyaml>=6.0`: YAML serialization
- `python-dateutil>=2.8.0`: Date/time handling

**Development Dependencies**:
- `pytest>=7.0.0`, `pytest-cov>=4.0.0`, `pytest-mock>=3.12.0`: Testing framework
- `black>=23.0.0`: Code formatting
- `ruff>=0.1.0`: Linting
- `mypy>=1.0.0`: Type checking
- `invoke>=2.0.0`: Task automation

### Error Handling

**User-Facing Errors**:
- All error messages MUST clearly identify the issue and suggest corrective action
- Use Rich console formatting for readable error output
- Exit codes: 0 (success), 1 (user error/validation), 2 (system error/AWS failure)

**Internal Errors**:
- AWS API errors MUST be caught and translated to user-friendly messages
- File I/O errors MUST provide context (path, operation, permission issues)
- Validation errors MUST specify which parameter/value is invalid

## Quality Gates

### Pre-Commit Requirements

All code MUST pass these checks before commit:

```bash
invoke quality      # Run all quality checks (format, lint, typecheck)
invoke test         # Run all tests with coverage
```

### Pre-Merge Requirements

All pull requests MUST:
1. Pass all quality checks (`invoke quality`)
2. Pass all tests with ≥80% coverage (`invoke test`)
3. Include tests for new functionality (TDD: tests written first)
4. Update documentation (README, command help text, examples)
5. Follow commit message format: `type(scope): description (#issue)`

### Feature Completion Checklist

Before marking a feature complete:
- [ ] All user stories independently testable
- [ ] Unit tests written and passing (≥80% coverage)
- [ ] Integration tests written and passing
- [ ] CLI help text updated
- [ ] README examples added
- [ ] Error messages clear and actionable
- [ ] Performance targets met (if applicable)
- [ ] Type checking passes (mypy strict)
- [ ] Code formatted (black) and linted (ruff)

## Governance

### Constitution Authority

This constitution is the authoritative governance document for the AWS Inventory Manager project. When conflicts arise between this constitution and other practices, the constitution takes precedence.

### Amendment Process

Constitution amendments require:
1. Documented rationale for the change
2. Impact analysis on existing code and workflows
3. Version increment following semantic versioning:
   - **MAJOR**: Breaking changes (principle removal/redefinition)
   - **MINOR**: New principles or materially expanded guidance
   - **PATCH**: Clarifications, wording improvements, typo fixes
4. Update to all dependent templates and documentation
5. Sync impact report documenting all changes

### Compliance Verification

All pull requests and code reviews MUST verify compliance with constitutional principles. Violations must be justified with:
- Clear business need
- Technical impossibility of compliance
- Documented exception with remediation plan
- Approval from project maintainer

### Version Information

**Version**: 1.0.0
**Ratified**: 2025-10-31
**Last Amended**: 2025-10-31
