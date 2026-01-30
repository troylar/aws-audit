# aws-baseline Development Guidelines

Auto-generated from all feature plans. Last updated: 2025-10-26

## Active Technologies
- Python 3.8+ (supports 3.8-3.13 per pyproject.toml) + boto3 (AWS SDK), typer (CLI), rich (terminal UI), pyyaml (storage), python-dateutil (timestamps) (002-inventory-management)
- Local filesystem YAML files (.snapshots/inventories.yaml, .snapshots/snapshots/*.yaml) (002-inventory-management)
- Python 3.8+ (project requires >=3.8, testing on 3.8-3.13) + Typer 0.9+, Rich 13.0+, PyYAML 6.0+, boto3 1.28+ (003-snapshot-resource-report)
- YAML files in ~/.snapshots (configurable via AWS_INVENTORY_STORAGE_PATH) (003-snapshot-resource-report)
- Python 3.8+ (supports 3.8 through 3.13) + boto3>=1.28.0, typer>=0.9.0, rich>=13.0.0, pyyaml>=6.0, python-dateutil>=2.8.0 (001-quick-wins)
- Local YAML files in ~/.snapshots (existing infrastructure, extended for full config storage) (001-quick-wins)
- Python 3.8+ (supports 3.8 through 3.13 per project standards) + boto3>=1.28.0 (AWS SDK), typer>=0.9.0 (CLI), rich>=13.0.0 (terminal UI), pyyaml>=6.0 (audit logs) (004-resource-cleanup)
- Local YAML files in ~/.snapshots (existing infrastructure, add audit-logs/ subdirectory) (004-resource-cleanup)

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
- 001-langgraph-iac-agent: Added [if applicable, e.g., PostgreSQL, CoreData, files or N/A]
- 004-resource-cleanup: Added Python 3.8+ (supports 3.8 through 3.13 per project standards) + boto3>=1.28.0 (AWS SDK), typer>=0.9.0 (CLI), rich>=13.0.0 (terminal UI), pyyaml>=6.0 (audit logs)
- 001-quick-wins: Added Python 3.8+ (supports 3.8 through 3.13) + boto3>=1.28.0, typer>=0.9.0, rich>=13.0.0, pyyaml>=6.0, python-dateutil>=2.8.0


<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
