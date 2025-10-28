# aws-baseline Development Guidelines

Auto-generated from all feature plans. Last updated: 2025-10-26

## Active Technologies
- Python 3.8+ (supports 3.8-3.13 per pyproject.toml) + boto3 (AWS SDK), typer (CLI), rich (terminal UI), pyyaml (storage), python-dateutil (timestamps) (002-inventory-management)
- Local filesystem YAML files (.snapshots/inventories.yaml, .snapshots/snapshots/*.yaml) (002-inventory-management)

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
- 002-inventory-management: Added Python 3.8+ (supports 3.8-3.13 per pyproject.toml) + boto3 (AWS SDK), typer (CLI), rich (terminal UI), pyyaml (storage), python-dateutil (timestamps)

- 001-aws-baseline-snapshot: Added Python 3.8+ (supports 3.8-3.13 based on project standards)

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
