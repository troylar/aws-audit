# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.17.6] - 2026-01-18

### Changed
- **Compact Layout**: Significantly reduced header section height to maximize table space
  - Filters collapsed by default
  - Saved Views and Filters combined into single compact row
  - Reduced padding throughout header sections
  - Main content padding reduced from p-6/p-8 to p-4

## [0.17.5] - 2026-01-18

### Fixed
- **Table Header Alignment**: Fixed headers getting out of sync during horizontal scrolling
  - Changed layout mode to `fitData` for proper horizontal scroll behavior
  - Fixed header overflow settings to stay aligned with body

## [0.17.4] - 2026-01-18

### Added
- **Collapsible Filters**: Filter section can now be collapsed/expanded with a click
  - Shows "Active" badge when filters are applied
  - Shows condition count when using advanced filters
  - Retains filter state when collapsed

### Fixed
- **Single-Page App Layout**: Resources page now fits within browser viewport
  - No more vertical/horizontal page blowout
  - Table fills remaining space and scrolls within its container
  - Fixed header, filters, and footer stay in place while table scrolls
- **Proper Flexbox Layout**: All page sections use proper flex-shrink-0 to maintain size
  - Header, views bar, filters, and selection toolbar don't shrink
  - Table card expands to fill available space

## [0.17.3] - 2026-01-17

### Added
- **Creator Filter Fields**: Added creator columns to advanced filter fields
  - Filter by Created By, Creator Type, and Creation Time in Advanced Filter mode
  - Tag field filtering now properly evaluates for `isTagField` columns

### Fixed
- **Horizontal Scrolling**: Fixed table extending past page width when many columns are enabled
  - Changed Tabulator layout from `fitColumns` to `fitDataStretch` for proper horizontal scrolling
  - Card container now has `overflow-x: auto` for scrollable tables
- **Sticky First Column**: Name column is now frozen/sticky when scrolling horizontally
  - Select checkbox column also stays frozen for better usability

## [0.17.2] - 2026-01-16

### Performance
- **10x Faster CloudTrail Queries**: Parallel queries by event name instead of scanning all events
  - Uses 10 concurrent workers to query different event types simultaneously
  - Filters at the API level with `LookupAttributes` instead of client-side filtering

### Added
- **Progress Bar for CloudTrail Queries**: Visual feedback during `enrich-creators` command
  - Shows which event types are being queried
  - Displays count of events found per type

### Fixed
- **Web UI Creator Columns Not Showing Data**: Fixed issue where enabling creator columns didn't trigger tag fetching
  - Now correctly detects `isTagField` columns in addition to `tag:` prefix columns

## [0.17.1] - 2026-01-16

### Added
- **Web UI Creator Columns**: New columns in Resource Explorer for creator information
  - "Created By" column shows the IAM role/user ARN (truncated for readability)
  - "Creator Type" column with color-coded badges (AssumedRole=blue, IAMUser=green, Root=red, AWSService=orange)
  - "Creation Time" column showing when the resource was created according to CloudTrail

### Documentation
- Added Resource Provenance section to README with usage examples
- Added CloudTrail IAM permissions documentation
- Updated Command Reference with `--track-creators`, `--created-by-role`, and `enrich-creators`
- Updated CHANGELOG with versions 0.12.0 through 0.17.0

## [0.17.0] - 2026-01-16

### Added
- **Resource Creator Tracking**: Query CloudTrail to discover who created each resource
  - `--track-creators` flag on `snapshot create` - Tags ALL resources with creator info from CloudTrail
  - `snapshot enrich-creators <snapshot>` - Enrich an existing snapshot with creator information
  - Adds `_created_by`, `_created_by_type`, and `_created_at` tags to each resource
  - Supports all identity types: AssumedRole, IAMUser, Root, AWSService
  - 90-day CloudTrail lookup window
  - `--days-back` option for `enrich-creators` to customize the lookup period

- **Web UI Creator Columns**: New columns in Resource Explorer for creator information
  - "Created By" column shows the IAM role/user ARN (truncated for readability)
  - "Creator Type" column with color-coded badges (AssumedRole=blue, IAMUser=green, Root=red, AWSService=orange)
  - "Creation Time" column showing when the resource was created according to CloudTrail
  - All three columns available in column selector (disabled by default)

### IAM Permissions
New permissions required for creator tracking:
```json
{
  "Effect": "Allow",
  "Action": ["cloudtrail:LookupEvents"],
  "Resource": "*"
}
```

## [0.16.0] - 2026-01-15

### Added
- **`--created-by-role` Flag**: Filter snapshot resources by CloudTrail creator role
  - `awsinv snapshot create my-snap --created-by-role MyRole` - Only include resources created by specific role
  - Queries CloudTrail to find resources created by the specified role
  - Supports both full ARN and role name
  - Useful for tracking resources created by automation, CI/CD pipelines, or specific users

## [0.15.0] - 2026-01-15

### Changed
- **AWS Config Disabled by Default**: Direct API collection is now the default
  - Use `--use-config` to explicitly enable AWS Config collection
  - This change improves reliability for accounts without Config enabled
  - Config collection is still recommended for large accounts (faster)

### Added
- **Glue Collector**: New collector for AWS Glue resources
  - Glue Databases
  - Glue Tables
  - Glue Jobs
  - Glue Crawlers

## [0.14.0] - 2026-01-14

### Added
- **Intelligent Resource Name Normalization**: Better matching of resources across snapshots
  - Automatically strips CloudFormation suffixes (e.g., `-ABC123DEF`)
  - Strips Bedrock/Kendra random suffixes (e.g., `_jnwn1`)
  - Removes embedded account IDs and regions from names
  - Priority: CloudFormation logical-id tag > Name tag > Pattern extraction
  - New `normalized_name` and `normalization_method` columns in database

- **Matching Module**: New `src/matching/` module for name normalization
  - `ResourceNormalizer` class with pattern detection
  - Confidence scoring for normalization quality
  - Preserves extracted patterns for debugging

### Changed
- Group membership now uses normalized names for more stable matching
- `create_from_snapshot` uses intelligent match strategy selection

## [0.13.0] - 2026-01-14

### Fixed
- Fixed PyPI version mismatch (pyproject.toml had incorrect version)

## [0.12.0] - 2026-01-14

### Added
- **Resource Groups**: Organize resources into named groups for tracking
  - `group create <name> --snapshot <snap>` - Create group from snapshot resources
  - `group list` - List all groups
  - `group show <name>` - Show group members
  - `group delete <name>` - Delete a group
  - Match strategies: `logical_id`, `normalized`, `physical_name`

## [0.11.0] - 2026-01-14

### Added
- **Resizable Table Columns**: Drag column borders to resize columns in Resource Explorer
  - Visual resize handles appear on hover
  - Min/max width constraints (80-600px)
  - Smooth drag feedback with cursor changes

- **Multi-Select Type & Region Filters**: Select multiple types and regions in Simple filter mode
  - Checkbox dropdown menus with "X selected" display
  - Clear button to deselect all
  - Client-side filtering for multi-select combinations

- **Column Widths in Saved Views**: Save and restore column widths along with visibility
  - Views now preserve custom column sizing
  - Load a view to restore exact table layout

- **Enhanced Table Styling**:
  - Avatar icons with first letter for Name column
  - Color-coded Type badges (S3=green, EC2=orange, Lambda=amber, IAM=red, etc.)
  - Region badges with globe icon
  - Copy-to-clipboard button for ARN column
  - Sticky headers with gradient background
  - Alternating row colors with hover effects
  - Custom scrollbar styling

### Changed
- Type and Region filters changed from single-select to multi-select dropdowns
- Table uses fixed layout with explicit column widths for better performance

## [0.10.3] - 2026-01-14

### Added
- **Dynamic Tag Columns**: Individual tag keys now appear as separate columns in the Resource Explorer
  - Enable columns like `tag:Environment`, `tag:Name`, `tag:Owner` etc.
  - Column modal groups base fields and tag columns separately
  - Tag columns show values as styled badges with truncation

- **Filter Value Dropdowns**: Advanced filter mode now shows dropdown menus with existing values
  - Select from available types, regions, snapshots, and tag values
  - Values are loaded globally from the entire inventory (not snapshot-specific)
  - Async loading with spinner indicator

- **CSV Export Enhancement**: Export now supports individual tag columns (tag:KEY format)

### Fixed
- Fixed table horizontal overflow when many columns are enabled
  - Added horizontal scrolling with proper column width constraints
  - Improved cell truncation and max-width for better readability

### Changed
- Filter values (types, regions, tags) are now global across all snapshots for consistency
- Saved filters remain global across snapshots as designed

## [0.10.2] - 2026-01-14

### Fixed
- Fixed tags column showing "no tags" when enabled (data wasn't being re-fetched)

## [0.10.1] - 2026-01-14

### Fixed
- Fixed web UI templates not being included in package distribution

## [0.10.0] - 2026-01-14

### Added
- **Web-Based Inventory Browser**: New `awsinv serve` command launches a beautiful web UI
  - Install with: `pip install aws-inventory-manager[web]`
  - Launch with: `awsinv serve` (opens browser automatically)
  - **Dashboard**: KPI cards and charts showing resource distribution by type/region
  - **Snapshot Browser**: View, compare, and manage snapshots
  - **Resource Explorer**: Search, filter, and browse all resources
  - **Diff Viewer**: Side-by-side snapshot comparison with added/removed/modified resources
  - **SQL Query Editor**: Run custom SQL queries with syntax highlighting
  - **Cleanup UI**: Preview and execute cleanup operations with audit logs

- **Advanced Filter Builder**: Build complex filters with boolean logic
  - AND/OR conditions with multiple filter rules
  - 10 operators: equals, not equals, contains, doesn't contain, starts with, doesn't start with, ends with, doesn't end with, is empty, is not empty
  - Filter by any field including tags

- **Saved Views**: Save and restore complete view configurations
  - Column visibility and order
  - Sort settings
  - Filter configurations (simple or advanced)
  - Quick-apply via chip buttons

- **Saved Filters**: Save frequently used filter combinations
  - Simple filters (type, region, snapshot, search)
  - Advanced filters with multiple conditions
  - Visual distinction between simple (blue) and advanced (green) filters

- **Export Capabilities**:
  - **CSV Export**: Export filtered resources with selected columns
  - **YAML Export**: Full resource export including tags and raw AWS configuration

- **Tags Column**: Display resource tags directly in the table
  - Shows up to 5 tags as compact badges
  - Full tag key/value on hover
  - Include in CSV/YAML exports

### Changed
- **BREAKING**: Renamed `restore` command to `cleanup` for clarity
  - `awsinv restore preview` → `awsinv cleanup preview`
  - `awsinv restore execute` → `awsinv cleanup execute`
  - `awsinv restore purge` → `awsinv cleanup purge`
  - Config file renamed: `.awsinv-restore.yaml` → `.awsinv-cleanup.yaml`
  - The term "restore" was misleading as the command deletes resources

### New Dependencies (optional)
- `fastapi>=0.109.0` - Modern async web framework
- `uvicorn>=0.27.0` - ASGI server
- `jinja2>=3.1.0` - Template engine
- `python-multipart>=0.0.6` - Form parsing

### Migration
- Update any scripts using `awsinv restore` to use `awsinv cleanup`
- Rename any `.awsinv-restore.yaml` files to `.awsinv-cleanup.yaml`

## [0.8.1] - 2026-01-14

### Added
- **Environment Variables**: Configure CLI options via environment variables for CI/CD and personal defaults
  - `AWSINV_PROFILE` / `AWS_PROFILE` - AWS CLI profile to use
  - `AWSINV_SNAPSHOT_ID` - Default snapshot name for queries
  - `AWSINV_INVENTORY_ID` - Default inventory name
  - `AWSINV_REGION` / `AWS_REGION` - Comma-separated regions
  - `AWSINV_STORAGE_PATH` / `AWS_INVENTORY_STORAGE_PATH` - Custom storage path

- **Query SQL Snapshot Filter**: New `--snapshot` flag for `query sql` command
  - Automatically injects WHERE clause to filter by snapshot
  - Works with `AWSINV_SNAPSHOT_ID` environment variable
  - Simplifies queries by removing need for manual JOIN/WHERE clauses

- **DATABASE.md**: New documentation with full schema and 33 power user SQL queries
  - Tagging compliance and taxonomy queries
  - Cost optimization queries (stopped instances, unattached volumes)
  - Security queries (unencrypted volumes, open security groups)
  - CloudFormation-managed vs manual resource analysis
  - User vs system tag analysis

### Testing
- 19 new unit tests for query commands and environment variables
- Total test count: 1551 tests passing
- Coverage: 79%

## [0.8.0] - 2026-01-13

### Added
- **SQLite Storage Backend**: Migrated from YAML files to SQLite for better query capabilities
  - All snapshots, resources, and tags stored in `~/.snapshots/inventory.db`
  - Normalized tags table for efficient tag-based queries
  - Optimized indexes for fast lookups by ARN, type, region, and tags
  - Performance tuning with WAL mode, memory-mapped I/O, and connection pooling

- **Query Commands**: New `awsinv query` command group for searching and analyzing resources
  - `query sql "<SQL>"` - Run raw SQL queries against the resource database
  - `query resources` - Search resources with filters (type, region, tag, snapshot)
  - `query history <arn>` - Track a resource across all snapshots
  - `query stats` - View resource statistics grouped by type, region, or service
  - `query diff <snap1> <snap2>` - Compare resources between two snapshots

### Changed
- Storage format changed from YAML files to SQLite database
- Snapshot data now stored in `inventory.db` instead of individual YAML files
- Improved startup time with lazy imports in CLI module

### New Modules
- `src/storage/database.py` - SQLite connection management with performance tuning
- `src/storage/schema.py` - Database schema definitions and indexes
- `src/storage/snapshot_store.py` - Snapshot CRUD operations
- `src/storage/resource_store.py` - Resource queries and search
- `src/storage/inventory_store.py` - Inventory management
- `src/storage/audit_store.py` - Audit log storage

### Testing
- 82 new unit tests for storage layer
- Total test count: 1491 tests passing

### Breaking Changes
- **Storage format changed**: Snapshots now stored in SQLite instead of YAML
- New installations will create `~/.snapshots/inventory.db`
- Existing YAML snapshots are not automatically migrated

## [0.7.2] - 2026-01-13

### Fixed
- Fixed "'str' has no attribute 'tzinfo'" error when creating snapshots with string dates
- Improved date handling in resource filter to automatically parse ISO format string dates
- Made age calculation in report model robust to string dates

## [0.7.1] - 2026-01-13

### Added
- **`awsinv config check` command**: Check AWS Config availability before creating snapshots
  - Shows Config status per region (enabled/disabled, recorder name, recording mode)
  - `--verbose` flag shows which services will use Config vs Direct API
  - Helps users understand collection method before running snapshots
- **`--verbose` flag for `snapshot create`**: Shows collection method breakdown after completion
  - Displays which resource types were collected via Config vs Direct API
  - Shows reasons for fallback (Config not enabled, type not recorded)
  - Default output shows brief summary; `--verbose` shows detailed table

### Changed
- Snapshot completion output now includes collection method summary
- Improved user visibility into hybrid Config/Direct API collection

## [0.7.0] - 2026-01-13

### Added
- **AWS Config Integration**: Hybrid collection system that automatically uses AWS Config when available
  - `--use-config/--no-config` flag to enable/disable Config-based collection (default: enabled)
  - `--config-aggregator <name>` flag for multi-account collection via Config Aggregators
  - Automatic detection of AWS Config availability per region
  - Seamless fallback to direct API collectors when Config is unavailable
  - Support for 80+ resource types via AWS Config
  - Per-resource `source` field tracking (`config` or `direct_api`)

### New Modules
- `src/config_service/detector.py` - AWS Config availability detection
- `src/config_service/collector.py` - Config-based resource collection
- `src/config_service/resource_type_mapping.py` - Resource type support mapping

### Changed
- Resource model now includes `source` field for collection transparency
- Architecture updated to show hybrid collection layer
- Snapshot metadata includes `collection_sources` and `config_enabled_regions`

### Testing
- 33 new unit tests for config_service module (85-91% coverage)
- 7 new tests for Resource model source field

## [0.6.0] - 2026-01-09

### Added
- **Resource Cleanup/Restore**: Complete resource deletion system for restoring AWS accounts to baseline state
  - `awsinv restore preview <snapshot>` - Safe dry-run showing resources to be deleted
  - `awsinv restore execute <snapshot> --confirm` - Execute cleanup with confirmation
  - **43 resource types supported** with intelligent dependency resolution
  - Prerequisite cleanup for complex resources:
    - S3 buckets: Automatic emptying (versioned objects, delete markers, object lock detection)
    - IAM roles: Policy detachment, instance profile removal
    - IAM users: Full credential cleanup (access keys, MFA, certs, policies, groups)
    - EventBridge rules: Target removal before deletion
    - Route53 hosted zones: Record cleanup (skips NS/SOA)
    - Backup vaults: Recovery point deletion
    - WAF WebACLs/RuleGroups: Resource disassociation, LockToken handling
  - Protection rules: Tag-based, type-based, age-based, cost-based resource protection
  - Comprehensive audit logging with YAML storage
  - Topological sort for dependency-aware deletion ordering

### New Resource Deleters
- EC2: Instances, Volumes, VPCs, Subnets, Security Groups, ENIs, Internet Gateways, Route Tables, Key Pairs, VPC Endpoints
- S3: Buckets (with automatic emptying)
- Lambda: Functions
- RDS: DB Instances, DB Clusters
- DynamoDB: Tables
- IAM: Roles, Users, Policies (with full cleanup)
- ECS: Clusters, Services, Task Definitions
- EKS: Clusters
- SNS: Topics
- SQS: Queues
- CloudWatch: Alarms
- API Gateway: REST APIs
- KMS: Keys (scheduled deletion)
- Secrets Manager: Secrets
- ELB: Load Balancers (Classic and v2)
- EFS: File Systems
- ElastiCache: Cache Clusters
- SSM: Parameters
- Step Functions: State Machines
- EventBridge: Rules (with target cleanup)
- CodeBuild: Projects
- CodePipeline: Pipelines
- CloudFormation: Stacks
- Route53: Hosted Zones (with record cleanup)
- Backup: Plans, Vaults (with recovery point cleanup)
- WAF: WebACLs, RuleGroups (with disassociation)

### Testing
- 50+ unit tests for restore module with 98.5% coverage
- Additional collector tests for EC2, ECS, EKS, IAM, Lambda, RDS, S3, SQS

## [0.5.0] - 2026-01-08

### Added
- Initial resource cleanup framework
- Dependency resolution system using Kahn's topological sort
- Safety checker with configurable protection rules
- Audit logging infrastructure

## [0.4.0] - 2025-11-15

### Added
- Date-based filtering support (`--before-date`, `--after-date`)
- Documentation of resources with/without creation date support
- Security scanning with CIS Benchmark alignment
- 12+ security checks across services

### Changed
- Improved snapshot naming flexibility
- Enhanced CLI help text and examples

### Fixed
- Lambda LastModified timestamp parsing
- SQS CreatedTimestamp handling

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
