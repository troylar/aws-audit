# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2025-10-31

### Added
- **Snapshot Reporting**: Comprehensive resource reporting system with summary and detailed views
  - `awsinv snapshot report` command for generating reports from snapshots
  - Summary view with aggregated counts by service, region, and resource type
  - Detailed view showing all resources with ARN, tags, creation dates, and age calculations
  - Flexible filtering by resource type and region (supports exact match, prefix, and contains)
  - Multi-format export support (JSON, CSV, TXT)
  - Pagination for large datasets (configurable page size)
  - Automatic selection of most recent snapshot when inventory is specified
  - Rich terminal UI with visual progress bars and formatted tables

### Changed
- `--inventory` option now automatically uses the most recent snapshot from that inventory
- Improved error messages for snapshot selection with helpful suggestions
- Enhanced datetime handling for timezone-aware resource age calculations

### Fixed
- Fixed timezone mismatch error when calculating resource age in detailed view
- Fixed CSV export to properly handle JSON-encoded tags column

## [0.2.0] - 2025-10-26

### Added
- Command name changed from `aws-baseline` to `awsinv`
- Inventory-based resource organization
- Multi-inventory support per AWS account
- Tag-based filtering for snapshots
- Cost analysis per inventory
- Delta tracking improvements

### Changed
- Updated all documentation to use `awsinv` command
- Improved terminology throughout codebase

### Fixed
- UTC timezone handling for all CLI date inputs
- Date parsing consistency

## [0.1.0] - Initial Release

### Added
- Initial release with basic snapshot functionality
- AWS resource capture across 25 services
- Local YAML storage
- Basic delta tracking
- Cost analysis integration
