# aws-baseline Development Guidelines

Auto-generated from all feature plans. Last updated: 2025-10-26

## Active Technologies
- Python 3.8+ (supports 3.8-3.13 per pyproject.toml) + boto3 (AWS SDK), typer (CLI), rich (terminal UI), pyyaml (storage), python-dateutil (timestamps) (002-inventory-management)
- Local filesystem YAML files (.snapshots/inventories.yaml, .snapshots/snapshots/*.yaml) (002-inventory-management)
- Python 3.8+ (project requires >=3.8, testing on 3.8-3.13) + Typer 0.9+, Rich 13.0+, PyYAML 6.0+, boto3 1.28+ (003-snapshot-resource-report)
- YAML files in ~/.snapshots (configurable via AWS_INVENTORY_STORAGE_PATH) (003-snapshot-resource-report)

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
- 003-snapshot-resource-report: Added Python 3.8+ (project requires >=3.8, testing on 3.8-3.13) + Typer 0.9+, Rich 13.0+, PyYAML 6.0+, boto3 1.28+
- 002-inventory-management: Added Python 3.8+ (supports 3.8-3.13 per pyproject.toml) + boto3 (AWS SDK), typer (CLI), rich (terminal UI), pyyaml (storage), python-dateutil (timestamps)

- 001-aws-baseline-snapshot: Added Python 3.8+ (supports 3.8-3.13 based on project standards)

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
