# Feature Specification: AWS Baseline Snapshot & Delta Tracking

**Feature Branch**: `001-aws-baseline-snapshot`
**Created**: 2025-10-26
**Status**: Draft
**Input**: User description: "Imagine an AWS environment where we have a cloud landing zone that pre-deploys several roles, lambdas, etc for cloud-custodian and other corporate baseline resources. I want a python cli that lets us take a 'snapshot' of the current baseline and from that we can do a delta both of resource and billing. The goal is to be able to restore back to baseline (remove newly created resources) and also see what the costs are for 'dial tone' (baseline resources) and the separate costs for non-baseline resources."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Capture Baseline Snapshot (Priority: P1)

A cloud administrator needs to establish a reference point of the cloud landing zone's baseline resources immediately after deployment. This snapshot will serve as the foundation for all future delta tracking and cost analysis.

**Why this priority**: Without a baseline snapshot, no other functionality can work. This is the fundamental building block that enables delta detection and cost separation.

**Independent Test**: Can be fully tested by running the snapshot command on a fresh landing zone deployment and verifying that all baseline resources (roles, lambdas, policies, etc.) are catalogued. Delivers immediate value by providing visibility into what resources exist in the baseline.

**Acceptance Scenarios**:

1. **Given** a freshly deployed AWS landing zone with baseline resources, **When** administrator runs the snapshot command, **Then** all existing AWS resources are inventoried and saved with metadata including resource type, ARN, tags, creation timestamp, and configuration
2. **Given** a baseline snapshot is being captured, **When** the snapshot process encounters an AWS API rate limit, **Then** the system gracefully handles throttling and completes the snapshot with all resources captured
3. **Given** an administrator wants to snapshot specific resource types only, **When** they specify resource filters (e.g., only IAM roles and Lambda functions), **Then** only those resource types are included in the snapshot
4. **Given** a baseline snapshot has been created, **When** administrator views the snapshot metadata, **Then** they can see the snapshot date, total resource count by type, AWS account ID, and region coverage

---

### User Story 2 - View Resource Delta (Priority: P2)

A cloud administrator or developer needs to identify which resources have been added, modified, or removed since the baseline snapshot was taken. This helps track drift from the approved baseline configuration.

**Why this priority**: This is the primary value proposition - seeing what's changed. However, it depends on having a baseline snapshot first, making it P2.

**Independent Test**: Can be tested by creating a baseline snapshot, adding/removing some resources, then running the delta command. Delivers value by showing developers exactly what they've created beyond the baseline.

**Acceptance Scenarios**:

1. **Given** a baseline snapshot exists, **When** administrator runs the delta command, **Then** the system displays new resources created since baseline, existing resources that were deleted, and existing resources that were modified with details of what changed
2. **Given** multiple resource changes have occurred, **When** viewing the delta report, **Then** resources are grouped by type (IAM, Lambda, S3, etc.) and change type (added/deleted/modified) for easy scanning
3. **Given** a delta report is generated, **When** viewing added resources, **Then** each resource shows its creation date, creator (if available from CloudTrail), and key configuration details
4. **Given** administrator needs to investigate specific changes, **When** they filter delta by resource type or date range, **Then** only matching changes are displayed
5. **Given** no changes have occurred since baseline, **When** delta command is run, **Then** system reports "No changes detected - environment matches baseline"

---

### User Story 3 - Analyze Cost Delta (Priority: P2)

A finance or operations team member needs to understand the cost breakdown between baseline "dial tone" resources and non-baseline resources to properly allocate cloud costs and track project spending.

**Why this priority**: Equal priority to resource delta as both are core value propositions. Cost tracking is independent of resource restoration, making it a separately valuable feature.

**Independent Test**: Can be tested by capturing a baseline, creating some resources, then running cost analysis. Delivers value by showing total baseline costs vs. incremental costs, helping with budgeting and chargeback.

**Acceptance Scenarios**:

1. **Given** a baseline snapshot exists and AWS Cost Explorer data is available, **When** administrator runs the cost delta command, **Then** the system displays total baseline resource costs ("dial tone"), total non-baseline resource costs, and combined total with percentage breakdown
2. **Given** cost analysis is requested for a specific time period, **When** specifying start and end dates, **Then** costs are calculated only for that period with daily or monthly breakdown
3. **Given** multiple projects or teams are using the same account, **When** non-baseline resources have project tags, **Then** non-baseline costs can be grouped by tag value for chargeback purposes
4. **Given** cost data is being retrieved, **When** AWS Cost Explorer API returns incomplete data, **Then** system warns the user about data gaps and shows estimated costs with clear indication of data quality
5. **Given** administrator wants to export cost data, **When** requesting cost report export, **Then** data is available in CSV or JSON format with resource-level cost details

---

### User Story 4 - Restore to Baseline (Priority: P3)

A cloud administrator needs to remove all non-baseline resources to return the environment to its original state, typically for cleaning up after testing or when decommissioning a project.

**Why this priority**: This is a destructive operation that should only be performed with caution. While valuable for cleanup, it's less frequently used than viewing deltas and costs, making it P3.

**Independent Test**: Can be tested by creating a baseline, adding test resources, then running restore command in dry-run mode followed by actual execution. Delivers value by automating cleanup that would otherwise be manual and error-prone.

**Acceptance Scenarios**:

1. **Given** a baseline snapshot exists and non-baseline resources are present, **When** administrator runs restore command in dry-run mode, **Then** system displays all resources that would be deleted without actually deleting them, and prompts for confirmation
2. **Given** administrator confirms restoration, **When** restore operation executes, **Then** all non-baseline resources are deleted in proper dependency order (e.g., EC2 instances before security groups) and progress is displayed
3. **Given** restore operation is in progress, **When** a resource deletion fails due to dependencies or permissions, **Then** system logs the error, continues with other deletions, and provides a summary of failed deletions at the end
4. **Given** certain resources should be preserved, **When** administrator specifies exclusion tags or resource IDs, **Then** those resources are skipped during restoration even if not in baseline
5. **Given** restore operation completes, **When** administrator reviews the results, **Then** a detailed log shows all deleted resources, any errors encountered, and final environment state compared to baseline

---

### User Story 5 - Create Historical Baseline (Priority: P2)

A cloud administrator needs to create a baseline snapshot that represents resources as they existed at a specific point in time, filtered by creation date and tags. This enables retroactive baseline establishment and reconstruction of historical infrastructure states.

**Why this priority**: Critical for teams who need to establish baselines after infrastructure is already deployed, or who want to track different baseline "layers" (e.g., "all resources created before Q4 2025" or "all resources tagged as baseline infrastructure"). This is a core differentiator for the tool.

**Independent Test**: Can be tested by creating resources at different times with different tags, then creating a historical baseline using date/tag filters, and verifying only matching resources are included. Delivers value by enabling flexible baseline definitions without requiring prospective snapshot capture.

**Acceptance Scenarios**:

1. **Given** resources exist with various creation dates, **When** administrator creates a snapshot with `--before-date 2025-10-01`, **Then** only resources created before October 1, 2025 are included in the baseline snapshot
2. **Given** resources exist with various creation dates, **When** administrator creates a snapshot with `--after-date 2025-10-01`, **Then** only resources created on or after October 1, 2025 are included in the snapshot
3. **Given** resources exist with various creation dates, **When** administrator creates a snapshot with `--between-dates 2025-09-01,2025-10-01`, **Then** only resources created in September 2025 are included
4. **Given** resources have different tags, **When** administrator creates a snapshot with `--filter-tags Baseline=true`, **Then** only resources with that exact tag are included in the baseline
5. **Given** resources have various tags and creation dates, **When** administrator creates a snapshot with `--before-date 2025-10-01 --filter-tags Environment=production`, **Then** only resources matching both criteria (created before date AND tagged appropriately) are included
6. **Given** administrator needs to establish baseline for pre-existing infrastructure, **When** they create a snapshot with `--before-date <deployment-date>`, **Then** baseline captures the "as-deployed" state for future delta tracking
7. **Given** resources are tagged with baseline indicators, **When** administrator creates a snapshot with `--filter-tags ManagedBy=terraform,Baseline=true` (multiple tags), **Then** only resources with all specified tags are included

---

### User Story 6 - Manage Multiple Snapshots (Priority: P3)

A cloud administrator needs to manage multiple baseline snapshots over time as the approved baseline configuration evolves with new platform updates or organizational changes.

**Why this priority**: This is an operational enhancement for mature usage. Users can start with a single snapshot, making this nice-to-have rather than essential.

**Independent Test**: Can be tested by creating multiple snapshots with different names/dates, listing them, and switching between them as the active baseline. Delivers value by supporting baseline evolution over time.

**Acceptance Scenarios**:

1. **Given** a baseline snapshot exists, **When** administrator creates a new snapshot with a specific name, **Then** both snapshots are preserved and the new one becomes the default for delta operations
2. **Given** multiple snapshots exist, **When** administrator lists snapshots, **Then** all snapshots are shown with name, creation date, resource count, and indicator of which is currently active
3. **Given** an older snapshot needs to become the baseline reference, **When** administrator sets it as active, **Then** all subsequent delta and cost operations use that snapshot as the baseline
4. **Given** old snapshots are no longer needed, **When** administrator deletes a snapshot by name, **Then** the snapshot is removed and system prevents deletion of the currently active snapshot
5. **Given** snapshots contain sensitive resource data, **When** viewing snapshot details, **Then** sensitive values (secrets, keys) are masked while structural information remains visible

---

### Edge Cases

- What happens when AWS API calls fail during snapshot due to permission issues? System should log which resource types failed and continue with accessible resources, producing a partial snapshot with clear warnings.
- How does system handle resources that exist in multiple regions? Snapshot should capture resources from all specified regions, with delta and cost operations accounting for multi-region deployments.
- What happens when a resource in the baseline was manually deleted? Delta should show it as "baseline resource deleted" as opposed to "new resource added".
- How does system handle resources created during snapshot execution? Use snapshot start timestamp as cutoff - resources created during snapshot are considered post-baseline.
- What happens when cost data isn't available yet for recent resources (AWS Cost Explorer lag)? Clearly indicate in cost report which resources don't have cost data yet and when data is expected.
- How does system handle resources without proper tagging? All resources are tracked; tagging only enhances cost grouping functionality.
- What happens when restore operation is interrupted? System should be idempotent - re-running restore should continue from where it left off, not fail on already-deleted resources.
- How does system handle resources that can't be deleted via API? Log them as manual deletion required, provide resource details for manual cleanup.
- What happens when baseline snapshot is corrupted or missing? All operations should fail gracefully with clear error message directing user to create a new baseline.
- How does system differentiate between baseline resources that were modified vs. new resources? Track resource identifiers (ARNs) - same ARN = modification, new ARN = new resource.
- What happens when resources don't have creation timestamps? Include them in snapshot with null creation date, exclude them from date-filtered snapshots with warning logged.
- How does system handle resources with tags that don't match filter? They are excluded from snapshot; summary shows how many resources were filtered out.
- What happens when date filters result in zero resources? Create empty snapshot with clear warning that no resources matched criteria.
- How does system handle timezone differences in date filtering? All dates interpreted as UTC; user documentation should specify UTC timezone requirement.
- What happens when combining multiple tag filters? Use AND logic (resource must have ALL specified tags to be included).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST capture complete inventory of AWS resources across specified regions including IAM roles, policies, Lambda functions, EC2 instances, S3 buckets, VPCs, security groups, and other common resource types
- **FR-002**: System MUST store baseline snapshots with sufficient detail to identify each resource uniquely (ARN, resource ID) and detect configuration changes (resource tags, policy documents, configuration parameters)
- **FR-003**: System MUST calculate delta between current AWS state and baseline snapshot, identifying added resources, deleted resources, and modified resources
- **FR-004**: System MUST integrate with AWS Cost Explorer or similar billing APIs to retrieve cost data for resources
- **FR-005**: System MUST separate costs into baseline resource costs and non-baseline resource costs based on resource inventory comparison
- **FR-006**: System MUST provide cost breakdown over configurable time periods (daily, weekly, monthly)
- **FR-007**: System MUST support deletion of non-baseline resources with dependency-aware ordering to avoid deletion failures
- **FR-008**: System MUST implement dry-run mode for destructive operations showing what would be changed without making changes
- **FR-009**: System MUST require explicit confirmation before executing destructive operations
- **FR-010**: System MUST handle AWS API rate limiting gracefully with automatic retry and backoff
- **FR-011**: System MUST log all operations with sufficient detail for audit and troubleshooting purposes
- **FR-012**: System MUST persist snapshots to local storage in a readable format (JSON or YAML)
- **FR-013**: System MUST support multiple named snapshots with ability to set one as the active baseline
- **FR-014**: System MUST provide progress indicators for long-running operations (snapshot, delta calculation, restore)
- **FR-015**: System MUST support filtering operations by resource type, tags, or date ranges
- **FR-016**: System MUST use AWS credentials from standard AWS credential chain (environment variables, AWS config files, IAM roles)
- **FR-017**: System MUST validate AWS credentials and required permissions before executing operations
- **FR-018**: System MUST export delta reports and cost reports in machine-readable formats (JSON, CSV)
- **FR-019**: System MUST handle multi-region AWS deployments, allowing users to specify which regions to include in operations
- **FR-020**: System MUST provide clear error messages when operations fail, including remediation guidance where possible
- **FR-021**: System MUST support filtering resources by creation date during snapshot capture (before date, after date, between dates)
- **FR-022**: System MUST support filtering resources by AWS tags during snapshot capture (single tag, multiple tags with AND logic)
- **FR-023**: System MUST combine date and tag filters when both are specified (resources must match all criteria)
- **FR-024**: System MUST retrieve resource creation timestamps from AWS APIs where available, with graceful handling when timestamps are unavailable
- **FR-025**: System MUST validate date filter formats and provide clear errors for invalid date specifications
- **FR-026**: System MUST validate tag filter formats (key=value pairs) and provide clear errors for malformed tag specifications

### Key Entities *(include if feature involves data)*

- **Baseline Snapshot**: Represents a point-in-time inventory of AWS resources. Contains snapshot name, creation timestamp, AWS account ID, region list, and complete resource inventory. Each snapshot is immutable after creation.

- **Resource Record**: Represents a single AWS resource within a snapshot. Contains resource type (IAM role, Lambda, etc.), unique identifier (ARN), resource name, tags, creation timestamp, configuration hash for change detection, and region.

- **Delta Report**: Represents the differences between current AWS state and a baseline snapshot. Contains list of added resources (with creation dates), deleted resources (with baseline references), modified resources (with change details), and generation timestamp.

- **Cost Report**: Represents cost analysis for a time period. Contains baseline resource costs (itemized and total), non-baseline resource costs (itemized and total), time period covered, cost groupings (by tag or project), and data completeness indicators.

- **Resource Dependency**: Represents relationships between resources for deletion ordering. Contains dependent resource identifier, dependency resource identifier, and dependency type (e.g., EC2 instance depends on security group).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Administrators can capture a complete baseline snapshot of a typical landing zone (100-500 resources) in under 5 minutes
- **SC-002**: Delta calculation comparing current state to baseline completes in under 2 minutes for environments with up to 1000 resources
- **SC-003**: Cost reports accurately separate baseline vs. non-baseline costs with less than 1% margin of error compared to manual AWS Cost Explorer analysis
- **SC-004**: Restore operations successfully remove 95% of non-baseline resources without manual intervention, with clear reporting of any failures
- **SC-005**: Users can identify all resources created in the last 7 days within 30 seconds using delta filtering
- **SC-006**: Cost allocation for project chargeback can be completed in under 5 minutes (compared to hours of manual cost analysis)
- **SC-007**: System handles AWS API throttling without user intervention and completes operations successfully despite rate limits
- **SC-008**: Zero baseline resources are accidentally deleted during restore operations when following documented procedures
- **SC-009**: Finance teams can generate monthly baseline vs. project cost reports in under 2 minutes
- **SC-010**: All operations provide clear progress indication so users can estimate completion time for long-running tasks

## Assumptions

- AWS credentials used will have broad read permissions across resource types (for snapshot and delta) and delete permissions (for restore operations)
- AWS Cost Explorer is enabled in the AWS account (may require 24-48 hours of data before costs are available)
- Cloud landing zone follows standard AWS best practices with consistent resource tagging for organizational tracking
- Snapshot storage location has sufficient disk space (estimated 1-10 MB per 100 resources depending on resource configuration complexity)
- Users have basic familiarity with AWS resource types and AWS CLI authentication patterns
- Internet connectivity to AWS APIs is reliable during operation execution
- Baseline resources are relatively stable (not changing daily) making snapshot approach viable
- Cost data lag from AWS Cost Explorer (typically 24-48 hours) is acceptable for cost reporting use cases
- Resources tracked are standard AWS resource types accessible via boto3 or AWS CLI
- Single AWS account per baseline (cross-account scenarios would require separate snapshots per account)

## Dependencies

- AWS SDK for Python (boto3) for AWS API interactions
- AWS Cost Explorer API access for cost data retrieval
- AWS credentials with appropriate IAM permissions for resource read/write operations
- Sufficient IAM permissions to enumerate resources across service APIs (ec2:Describe*, iam:List*, lambda:List*, s3:List*, etc.)
- For restore operations: IAM permissions to delete resources (ec2:Terminate*, iam:Delete*, lambda:Delete*, etc.)
- Local file system access for storing snapshot data
- AWS CloudTrail (optional) for enhanced resource metadata like creator information
- Python 3.8+ runtime environment for CLI execution

## Out of Scope

- Real-time monitoring or alerting of resource changes (this is a snapshot-based, on-demand tool)
- Automated scheduled snapshots (users run snapshot command manually when baseline changes)
- Cross-account baseline tracking (each AWS account requires separate baseline snapshot)
- Resource compliance checking or policy enforcement (focus is inventory and cost, not compliance)
- Modification or rollback of changed resources (only restoration via deletion, not configuration rollback)
- Cost optimization recommendations (purely reporting, not advisory)
- Integration with third-party cloud management platforms
- GUI or web interface (CLI only)
- Historical trending of costs over time beyond simple time period comparisons
- Budget alerts or cost threshold notifications
- Resource provisioning or infrastructure as code generation
- Backup or disaster recovery functionality
- Support for non-AWS cloud providers
