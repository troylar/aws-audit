# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
