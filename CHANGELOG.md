# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
