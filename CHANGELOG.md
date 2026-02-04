# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-02-04

### Added
- **Guardrails (Compliance Checking)**: Enforce security and compliance policies before IaC generation
  - Policy-based compliance checking with custom guardrail definitions (YAML)
  - Severity levels: CRITICAL, HIGH, MEDIUM, LOW, INFO
  - Actions: BLOCK (stop generation), AUTO-FIX (AI remediation), WARN (continue with warning)
  - 10+ condition operators: exists, not_exists, equals, contains, matches, in, greater_than, etc.
  - Environment-specific policy overrides (dev, staging, production)
  - AI-powered auto-fix using AWS Bedrock to automatically remediate violations
  - Standalone `awsinv guardrails check` command for CI/CD integration
  - `awsinv guardrails list` to view available guardrails
  - Integration with `awsinv generate` via `--guardrails` flag
  - JSON/YAML output formats for reports

### Changed
- IaC generation now supports guardrails flags: `--guardrails`, `--guardrails-policy`, `--guardrails-env`, `--guardrails-strict`, `--guardrails-auto-fix`

## [1.0.2] - 2026-02-04

### Fixed
- **CDK Progress Display**: Show format-specific UI during generation
  - Header shows "CDK TypeScript Generation" or "CDK Python Generation" instead of "Terraform"
  - Step names update: "Generate CDK", "NPM Build", "CDK Synth" for CDK formats
  - Fixed icon spacing inconsistencies in progress display

- **Coverage Detection**: Expanded resource type mappings from 27 to 102 types
  - Added IAM: instance-profile, user, group
  - Added ECS: cluster, service, task-definition
  - Added EKS: cluster, nodegroup, fargate-profile
  - Added Load Balancing: ALB, NLB, target-group, listener
  - Added API Gateway v1/v2: resource, method, stage, route, integration
  - Added Glue: database, table, crawler, job, trigger, workflow
  - Added Route53: hosted-zone, record-set, health-check
  - Added 60+ additional resource types for accurate coverage reporting

## [1.0.1] - 2026-02-04

### Fixed
- **CDK Template Files**: Fixed missing template files in PyPI package distribution
  - Template files (`.template`) are now properly included in the wheel
  - Fixes "No such file or directory: package.json.template" error

## [1.0.0] - 2026-02-04

### Added
- **CDK TypeScript Generation**: Generate complete AWS CDK TypeScript projects from inventory snapshots
  - `awsinv generate cdk-typescript my-snapshot` command
  - Full project structure: `bin/app.ts`, `lib/*.ts`, `package.json`, `tsconfig.json`, `cdk.json`
  - L2 construct generation with proper typing and exports
  - npm build and cdk synth validation

- **CDK Python Generation**: Generate complete AWS CDK Python projects from inventory snapshots
  - `awsinv generate cdk-python my-snapshot` command
  - Full project structure: `app.py`, `stacks/*.py`, `requirements.txt`, `setup.py`, `cdk.json`
  - Snake_case naming conventions and Python best practices
  - pip install and cdk synth validation

- **CDK Coverage Detection**: Compare inventory against CDK code
  - Detect CDK TypeScript constructs (`new ec2.Vpc`, `new s3.Bucket`, etc.)
  - Detect CDK Python constructs (`ec2.Vpc`, `s3.Bucket`, etc.)
  - Coverage percentage calculation for CDK projects

### Changed
- **Default AI Model**: Upgraded to Claude Opus 4 (`anthropic.claude-opus-4-20250514-v1:0`)
- **IaC Generation**: Now supports three output formats: `terraform`, `cdk-typescript`, `cdk-python`

## [0.25.0] - 2026-01-29

### Added
- **Skipped Status for Already-Deleted Resources**: Distinguish between actually deleted vs already gone
  - ⏭️ Skipped status for resources that were already deleted before purge
  - New column in summary table: ✅ Deleted | ⏭️ Skipped | ❌ Failed
  - Real-time display shows "(already gone)" for skipped resources
  - Clear visibility into what was actually deleted vs what was already missing

## [0.24.4] - 2026-01-22

### Changed
- **Enhanced Deletion Summary**: Beautiful emoji-rich summary report after purge
  - Tier-specific emojis: 🚀 Apps, 💻 Compute, ⚖️ Load Balancers, 🛡️ Security, 🏠 VPCs, etc.
  - Status header with ✨ success / ⚠️ partial / ❌ failure indicators
  - Styled table with colored headers and alternating rows
  - Celebratory messaging on successful cleanup

## [0.24.3] - 2026-01-22

### Added
- **Deletion Summary Report**: `cleanup purge` now displays a final summary table after completion
  - Resources organized by deletion tier with success/failed/total counts
  - Failed resources listed with error details at the end
  - Clear visual breakdown of what was deleted across all dependency layers

## [0.24.2] - 2026-01-22

### Fixed
- **EntityNotFoundException**: Treat as success (Glue crawlers, jobs, etc. already deleted)

## [0.24.1] - 2026-01-22

### Fixed
- **RDS DBCluster**: Add `SkipFinalSnapshot` parameter for cluster deletion
- **RDS Not Found**: Treat `DBInstanceNotFound` and `DBClusterNotFoundFault` as success

## [0.24.0] - 2026-01-22

### Added
- **Real-Time Deletion Progress Display**: `cleanup purge` now shows a live dependency tree during deletion
  - Resources grouped by deletion tier with real-time status updates
  - Status icons: ✓ Done, ⋯ In Progress, ○ Pending, ✗ Failed
  - Detailed mode (< 50 resources) shows all resources with status
  - Compact mode (50+ resources) shows tier progress bars
  - Elapsed time tracking
- **Glue Resource Support**: Added deletion support for AWS Glue resources
  - `AWS::Glue::Job`, `AWS::Glue::Database`, `AWS::Glue::Crawler`

### Fixed
- **RDS Already Deleting**: Treat `InvalidDBInstanceState` (already being deleted) as success
- **SQS Queue Not Found**: Treat `NonExistentQueue` errors as success (already deleted)
- **RDS-Managed Secrets**: Skip secrets owned by RDS (cannot be deleted directly)
- **IAM Policy Versions**: Delete non-default policy versions before deleting policy

## [0.23.0] - 2026-01-22

### Added
- **Dependency-Ordered Deletion**: `cleanup purge` now deletes resources in correct dependency order
  - Resources sorted into 10 deletion tiers based on AWS dependency relationships
  - Applications (Lambda, ECS, API Gateway) deleted before compute (EC2, RDS)
  - Compute deleted before networking (security groups, subnets)
  - Networking deleted before VPCs
  - IAM resources deleted last (may be needed by other resources)
  - Preview shows resources grouped by deletion tier with tier descriptions

### Changed
- **Purge No Longer Requires Protect Tag**: Removed `--protect-tag` requirement from `cleanup purge`
  - Command now works without specifying a protect tag
  - Resources can still be protected with `--protect-tag` option if desired

## [0.22.1] - 2026-01-22

### Improved
- **Purge Preview**: Removed truncation from `cleanup purge --preview` output
  - Now shows all resources that would be deleted, excluded, or protected
  - Previously limited to 20 deleted, 10 excluded, and 10 protected resources

## [0.22.0] - 2026-01-22

### Added
- **Snapshot Creators Command**: New `awsinv snapshot creators` command to list resource creators
  - Shows summary of who created resources in a snapshot (requires creator tracking)
  - Aggregates resources by creator with counts by resource type
  - Displays creator type (AssumedRole, IAMUser, Root, Service)
  - `--detailed` flag shows individual resources for each creator
  - Export to JSON or CSV with `--export` option
  - Examples:
    - `awsinv snapshot creators my-snapshot` - Show creators summary
    - `awsinv snapshot creators --detailed` - Show detailed resources per creator
    - `awsinv snapshot creators --export creators.json` - Export to JSON
    - `awsinv snapshot creators --export creators.csv` - Export to CSV

## [0.21.2] - 2026-01-22

### Improved
- **Better Deletion Error Details**: Improved error reporting for `cleanup purge` and `cleanup execute`
  - Failed deletions now show detailed error messages including resource type, name, region, ARN, and specific error
  - Error messages from AWS are now captured and displayed instead of generic "Deletion failed"
  - Failed resources listed individually before the summary panel

## [0.21.1] - 2026-01-22

### Added
- **SSL Verification Option**: New `--no-ssl-verify` option for `lambda fetch` command
  - Allows downloading Lambda code when SSL certificate verification fails
  - Useful for corporate proxies or environments with self-signed certificates
  - Example: `awsinv lambda fetch my-snapshot --no-ssl-verify`

## [0.21.0] - 2026-01-22

### Added
- **Purge Exclusion Filters**: New options to exclude specific resources from deletion in `cleanup purge`
  - `--exclude-name` / `-x`: Exclude resources by name pattern (supports `*` and `?` wildcards)
  - `--exclude-tag`: Exclude resources by tag pattern (format: `key=value`, supports wildcards)
  - Both options can be repeated multiple times (OR logic - excluded if ANY match)
  - Examples:
    - `--exclude-name "*-prod-*"` - Exclude all resources with "-prod-" in their name
    - `--exclude-name "critical-*" -x "important-*"` - Exclude multiple name patterns
    - `--exclude-tag "protected=yes"` - Exclude resources with specific tag
    - `--exclude-tag "Name=*production*"` - Exclude resources where Name tag contains "production"

## [0.20.0] - 2026-01-22

### Added
- **Lambda Fetch Command**: New `awsinv lambda fetch` command to download Lambda code for existing snapshots
  - Fetches code from AWS for Lambda functions that don't have stored code
  - Handles versioned functions by parsing qualifier from ARN
  - Stores code inline or externally based on `--max-size` option
  - Use `--force` to re-fetch code even for functions that already have it
  - Filter by function name with `--function` option
  - Example: `awsinv lambda fetch my-snapshot --max-size 50`

## [0.19.0] - 2026-01-21

### Added
- **Lambda Code Size Configuration**: New `--lambda-code-max-size` option for `snapshot create`
  - Set maximum Lambda code size (in MB) to store inline in snapshots
  - Larger packages automatically stored to external files in `~/.snapshots/lambda-code/`
  - Use `-1` for unlimited inline storage, `0` for external-only storage
  - Example: `awsinv snapshot create my-snap --lambda-code-max-size 50`
- **External Lambda Code Storage**: Large Lambda deployment packages now stored to disk
  - Packages larger than inline limit saved to `~/.snapshots/lambda-code/<snapshot>/`
  - Lambda CLI commands automatically read from external files when needed
  - Shows "File" as source type in `lambda list` output

## [0.18.1] - 2026-01-21

### Added
- **Lambda CLI Unit Tests**: Comprehensive test coverage for lambda commands (29 tests)
  - Tests for list, extract, show, and diff commands
  - Edge case tests for missing code, empty configs, unnamed functions

### Fixed
- **Lambda CLI**: Fixed `get_active_snapshot` method call (was using wrong method name)

## [0.18.0] - 2026-01-21

### Added
- **Lambda Code CLI Commands**: New `awsinv lambda` command group for working with Lambda code
  - `awsinv lambda list` - List all Lambda functions with code info (size, hash, storage status)
  - `awsinv lambda extract` - Extract code to disk (single function or all at once)
  - `awsinv lambda show` - View code with syntax highlighting directly in terminal
  - `awsinv lambda diff` - Compare code between two snapshots with unified diff output
  - Auto-detects handler files and programming language for syntax highlighting
  - Supports Python, JavaScript, TypeScript, Go, Ruby, Java, and more

## [0.17.19] - 2026-01-21

### Fixed
- **Enrich Creators Filter**: Fixed issue where 0 creation events were found
  - Now falls back to querying all event types if no matches found
  - Added warning message when filter produces no matches

## [0.17.18] - 2026-01-21

### Improved
- **Enrich Creators Performance**: Significantly sped up `snapshot enrich-creators` command
  - Parallelized CloudTrail queries across regions (was serial before)
  - Increased thread pool workers from 10 to 20 for event type queries
  - Smart filtering: Only queries event types matching resource types in your snapshot
  - Example: If your snapshot only has Lambdas and S3 buckets, skips 40+ irrelevant event queries
  - Combined optimizations can reduce query time by 50-80% depending on snapshot contents

## [0.17.16] - 2026-01-21

### Added
- **Lambda Code Collection**: Enhanced Lambda collector to download and store actual deployment code
  - Downloads Lambda function deployment packages from presigned URLs
  - Stores code as base64 for packages under 10MB, hash-only for larger
  - Captures S3 bucket/key if code was deployed from S3
  - Includes code SHA256 hash for change detection
  - Also collects Lambda layer code with same approach
  - Code stored in `raw_config._code` field

## [0.17.15] - 2026-01-21

### Added
- **Cleanup Purge Creator/Date Filters**: New options to filter resources for deletion by creator and creation date
  - `--from-snapshot`: Load resources from an enriched snapshot (required for creator filters)
  - `--created-by`: Filter by creator name/ARN (substring match)
  - `--created-after`: Filter by creation date (resources created after this date)
  - `--created-before`: Filter by creation date (resources created before this date)
  - Requires running `awsinv snapshot enrich-creators <snapshot>` first to populate creator info
  - Example: `awsinv cleanup purge --from-snapshot my-snapshot --created-by "john.doe" --preview`

## [0.17.14] - 2026-01-18

### Fixed
- **Save Filters/Views**: Fixed saved filters and views not persisting to database
  - Database class was missing `commit()` method
  - API routes were using wrong attribute name (`_conn` vs `_connection`)
  - Saved filters and views now persist correctly and appear in selection

## [0.17.13] - 2026-01-18

### Fixed
- **YAML Export Advanced Filters**: Fixed YAML export not respecting advanced filters (Created By, tag filters, etc.)
  - Export now uses filtered table data via `getData("active")` to respect ALL filters
  - Added POST endpoint to fetch full data by ARNs for filtered resources
  - Works with Tabulator filters, advanced query builder, and all client-side filters

## [0.17.12] - 2026-01-18

### Fixed
- **YAML Export Filters**: Fixed YAML export not respecting UI filters
  - Fixed wrong Alpine.js property names (selectedTypes vs selectedType, etc.)
  - Added support for multiple types/regions via comma-separated values
  - API now properly filters by type, region, snapshot, and search query
  - Console logging added for debugging export issues

## [0.17.11] - 2026-01-18

### Changed
- **YAML Export**: Now exports ALL resource properties including full AWS configuration
  - Uses server-side API endpoint for complete data
  - Includes `config` object with full raw_config from AWS
  - Includes all metadata fields and tags
  - Respects current filter state (snapshot, type, region, search)

## [0.17.10] - 2026-01-18

### Fixed
- **Loading Indicator**: Fixed HTMX loading indicator blocking button clicks when hidden
  - Added `pointer-events: none` when indicator is invisible
  - CSV/YAML export buttons now always clickable

## [0.17.9] - 2026-01-18

### Fixed
- **Column Sorting**: Fixed sorting for creator and tag columns
  - Created By, Creator Type, and Creation Time columns now sort correctly
  - Dynamic tag columns (tag:*) now sort correctly
  - All columns properly read values from nested tags object
- **Advanced Filter**: Fixed issue requiring double-click to search with creator field filters
  - Creator fields (_created_by, _created_by_type, _created_at) now properly detected as tag conditions
  - Tags are automatically included in API request when filtering by creator fields

### Changed
- **Compact Column Modal**: Converted column customization from cards to compact checklist
  - 3-column grid layout for more efficient space usage
  - Smaller checkboxes and text
  - Freeze button inline with each item
  - Reduced visual clutter while maintaining functionality

## [0.17.8] - 2026-01-18

### Changed
- **Compact Data-Dense UI**: Optimized for viewing large datasets
  - Smaller fonts throughout (0.75rem table cells, 0.625rem headers)
  - Narrower default column widths
  - Text truncation with ellipsis on all cells
  - Smaller buttons and icons
  - Still zoomable with browser Ctrl-+ / Ctrl--

## [0.17.7] - 2026-01-18

### Fixed
- **CSV/YAML Export**: Now exports the currently filtered/visible table data
  - Respects all active filters (simple, advanced, views)
  - Exports columns in current visible order
  - Client-side export for instant download

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
