# aws-baseline Development Guidelines

Auto-generated from all feature plans. Last updated: 2025-10-26

## Active Technologies
- Python 3.8+ (supports 3.8-3.13 per pyproject.toml) + boto3 (AWS SDK), typer (CLI), rich (terminal UI), pyyaml (storage), python-dateutil (timestamps) (002-inventory-management)
- Local filesystem YAML files (.snapshots/collections.yaml, .snapshots/snapshots/*.yaml) (002-inventory-management)
- Python 3.8+ (project requires >=3.8, testing on 3.8-3.13) + Typer 0.9+, Rich 13.0+, PyYAML 6.0+, boto3 1.28+ (003-snapshot-resource-report)
- YAML files in ~/.snapshots (configurable via AWS_INVENTORY_STORAGE_PATH) (003-snapshot-resource-report)
- Python 3.8+ (supports 3.8 through 3.13) + boto3>=1.28.0, typer>=0.9.0, rich>=13.0.0, pyyaml>=6.0, python-dateutil>=2.8.0 (001-quick-wins)
- Local YAML files in ~/.snapshots (existing infrastructure, extended for full config storage) (001-quick-wins)
- Python 3.8+ (supports 3.8 through 3.13 per project standards) + boto3>=1.28.0 (AWS SDK), typer>=0.9.0 (CLI), rich>=13.0.0 (terminal UI), pyyaml>=6.0 (audit logs) (004-resource-cleanup)
- Local YAML files in ~/.snapshots (existing infrastructure, add audit-logs/ subdirectory) (004-resource-cleanup)
- Python 3.8+ (tool), TypeScript/Python (generated output) + langgraph>=0.2.0, boto3>=1.28.0 (existing), plus generated code targets aws-cdk-lib v2 (001-cdk-generation)
- Local filesystem for generated CDK projects (same pattern as Terraform) (001-cdk-generation)
- Python 3.8+ (supports 3.8-3.13) + Typer 0.9+, Rich 13.0+ (001-cli-consistency-review)
- N/A (CLI interface changes only, no data model changes) (001-cli-consistency-review)
- Python 3.11+ (tested on 3.11, 3.12, 3.13, 3.14) + pytest>=7.0.0, pytest-cov>=4.0.0, pytest-mock>=3.12.0, typer (CLI under test), fastapi (web routes under test) (001-increase-coverage)
- N/A (testing effort, no storage changes) (001-increase-coverage)

- Python 3.8+ (supports 3.8-3.13 based on project standards) (001-aws-baseline-snapshot)

## Project Structure

```text
src/
tests/
```

## Commands

cd src [ONLY COMMANDS FOR ACTIVE TECHNOLOGIES][ONLY COMMANDS FOR ACTIVE TECHNOLOGIES] pytest [ONLY COMMANDS FOR ACTIVE TECHNOLOGIES][ONLY COMMANDS FOR ACTIVE TECHNOLOGIES] ruff check .

## Code Style

Python 3.8+ (supports 3.8-3.13 based on project standards): Follow standard conventions

## Recent Changes
- 001-increase-coverage: Added Python 3.11+ (tested on 3.11, 3.12, 3.13, 3.14) + pytest>=7.0.0, pytest-cov>=4.0.0, pytest-mock>=3.12.0, typer (CLI under test), fastapi (web routes under test)
- 001-cli-consistency-review: Added Python 3.8+ (supports 3.8-3.13) + Typer 0.9+, Rich 13.0+
- 001-cli-consistency-review: Added Python 3.8+ (supports 3.8-3.13) + Typer 0.9+, Rich 13.0+


<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
