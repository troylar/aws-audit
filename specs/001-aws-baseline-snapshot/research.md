# Research: AWS Baseline Snapshot & Delta Tracking

**Feature**: 001-aws-baseline-snapshot
**Date**: 2025-10-26
**Phase**: 0 - Technology Research & Decisions

## Overview

This document captures research findings and technology decisions for implementing the AWS Baseline Snapshot tool. Each section addresses a specific technical question identified during planning.

---

## 1. AWS Resource Enumeration Patterns

### Decision

Use **boto3 client interface with concurrent resource collection** across service types, with pagination handled via built-in paginators.

### Rationale

- **Client vs. Resource Interface**: boto3 client interface provides more direct control over API calls, better error handling, and is universally supported across all AWS services. The resource interface is higher-level but not available for all services.
- **Concurrent Collection**: Use Python's `concurrent.futures.ThreadPoolExecutor` to query multiple service types simultaneously (e.g., IAM, Lambda, EC2 in parallel), significantly reducing total snapshot time.
- **Paginators**: boto3's built-in paginators (e.g., `client.get_paginator('list_functions')`) automatically handle pagination for large result sets, simplifying code and ensuring complete resource enumeration.

### Alternatives Considered

- **Sequential collection**: Simpler but too slow for meeting <5 minute goal for 500 resources
- **boto3 resource interface**: Not available for all services (e.g., Cost Explorer), would require mixed approaches
- **AWS Config API**: Could provide resource inventory but adds dependency on AWS Config being enabled, increases cost, and has eventual consistency issues

### Implementation Notes

```python
# Pattern for resource collection
import boto3
from concurrent.futures import ThreadPoolExecutor, as_completed

def collect_resources(regions, resource_types):
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = []
        for region in regions:
            for resource_type in resource_types:
                futures.append(
                    executor.submit(collect_service_resources, region, resource_type)
                )

        for future in as_completed(futures):
            yield future.result()

def collect_service_resources(region, resource_type):
    client = boto3.client(resource_type, region_name=region)
    paginator = client.get_paginator('list_...')
    for page in paginator.paginate():
        yield from page['Resources']
```

**Key Services to Support Initially**:
- IAM (global): Roles, Policies, Users, Groups
- Lambda: Functions, Layers
- EC2: Instances, Security Groups, VPCs, Subnets, EBS Volumes
- S3 (global): Buckets
- RDS: Instances, Snapshots
- CloudFormation: Stacks
- CloudWatch: Alarms, Log Groups
- SNS: Topics
- SQS: Queues
- DynamoDB: Tables

---

## 2. AWS Cost Explorer API Integration

### Decision

Use **AWS Cost Explorer GetCostAndUsage API with resource-level tagging** for cost attribution, combined with **local snapshot ARN matching** for baseline separation.

### Rationale

- **GetCostAndUsage API**: Provides cost data grouped by various dimensions including tags, services, and usage types. Can query costs over specific time periods with daily or monthly granularity.
- **Resource Tagging Strategy**: ARNs from snapshots can't directly map to Cost Explorer data. Instead, match costs by:
  1. Service type (e.g., all Lambda costs)
  2. Resource tags (if consistently applied)
  3. Time-based filtering (costs incurred after snapshot timestamp = likely non-baseline)
- **Data Lag Handling**: Cost Explorer typically has 24-48 hour data lag. Tool must clearly communicate when cost data is incomplete and provide estimated "as of" timestamps.

### Alternatives Considered

- **AWS Cost & Usage Reports (CUR)**: More detailed but requires S3 setup, Athena queries, adds complexity. Overkill for this use case.
- **CloudWatch billing metrics**: Real-time but less granular, no resource-level attribution
- **Third-party tools** (CloudHealth, Cloudability): Introduces external dependencies, cost, and auth complexity

### Implementation Notes

```python
import boto3
from datetime import datetime, timedelta

def get_costs(start_date, end_date, group_by='SERVICE'):
    client = boto3.client('ce')  # Cost Explorer

    response = client.get_cost_and_usage(
        TimePeriod={
            'Start': start_date.strftime('%Y-%m-%d'),
            'End': end_date.strftime('%Y-%m-%d')
        },
        Granularity='DAILY',
        Metrics=['UnblendedCost', 'UsageQuantity'],
        GroupBy=[
            {'Type': 'DIMENSION', 'Key': group_by}
        ]
    )

    return response['ResultsByTime']

def separate_baseline_costs(snapshot, costs):
    """
    Match costs to baseline resources by:
    1. Service type mapping
    2. Timeline (costs before snapshot = baseline)
    3. Tag-based grouping where available
    """
    baseline_services = {r.service for r in snapshot.resources}
    # Implementation details...
```

**Accuracy Strategy**:
- For <1% error margin goal, combine multiple attribution methods:
  - Time-based: Costs before snapshot creation = baseline
  - Service-based: If all Lambda functions in baseline, all Lambda costs = baseline
  - Tag-based: If resources tagged consistently (e.g., `baseline:true`), use tag filtering
- Clearly document assumptions and data quality in cost reports

**Data Lag Communication**:
- Check cost data freshness before reporting
- Display "Costs as of [date]" prominently
- Warn when requesting costs for last 48 hours

---

## 3. AWS Resource Dependency Detection

### Decision

Use **manually maintained dependency rules** based on AWS resource type relationships, with **topological sort** for deletion ordering.

### Rationale

- **AWS Dependency Complexity**: No universal API for dependency detection across all resource types. CloudFormation has dependency graphs but only for CFN-managed resources.
- **Predictable Dependencies**: Most AWS dependencies follow predictable patterns:
  - EC2 instances → Security groups, Subnets
  - Lambda functions → IAM roles, VPC subnets
  - RDS instances → Security groups, Subnets
- **Topological Sort**: Classic algorithm for dependency-ordered processing ensures resources are deleted in safe order
- **95% Success Rate**: Manual rules cover common cases. For edge cases, provide clear error messages for manual cleanup.

### Alternatives Considered

- **CloudFormation resource scanning**: Only works for CFN-managed resources, not manually created ones
- **Trial-and-error deletion with retries**: Messy, generates many error logs, poor UX
- **AWS Resource Groups Tagging API**: Doesn't provide dependency information

### Implementation Notes

```python
# Dependency rules (extensible)
DEPENDENCY_RULES = {
    'ec2:instance': ['ec2:security-group', 'ec2:subnet', 'ec2:volume'],
    'lambda:function': ['iam:role', 'ec2:subnet'],  # If VPC-attached
    'rds:instance': ['ec2:security-group', 'ec2:subnet'],
    'ec2:security-group': ['ec2:vpc'],
    'ec2:subnet': ['ec2:vpc'],
}

def build_dependency_graph(resources):
    """Build directed graph of dependencies"""
    graph = {}
    for resource in resources:
        deps = DEPENDENCY_RULES.get(resource.type, [])
        graph[resource.arn] = [r.arn for r in resources
                               if r.type in deps]
    return graph

def topological_sort(graph):
    """Return deletion order (dependencies first)"""
    # Kahn's algorithm or DFS-based topological sort
    pass

def delete_in_order(resources):
    graph = build_dependency_graph(resources)
    deletion_order = topological_sort(graph)

    for resource_arn in deletion_order:
        try:
            delete_resource(resource_arn)
        except Exception as e:
            log_failed_deletion(resource_arn, e)
            # Continue with other deletions
```

**Dependency Coverage**:
- Start with top 10 resource types (covers 80%+ of common use cases)
- Extensible design allows adding new dependency rules
- Document which resource types support automated dependency handling

---

## 4. Configuration Hash for Change Detection

### Decision

Use **SHA256 hash of normalized JSON representation** of resource configuration, excluding volatile attributes (timestamps, state, IDs).

### Rationale

- **SHA256**: Standard cryptographic hash, collision-resistant, fast, widely supported
- **Normalized JSON**: Serialize resource configuration to JSON with sorted keys for deterministic hashing
- **Exclusion List**: Ignore attributes that change naturally:
  - Timestamps (LastModifiedDate, CreatedDate)
  - Runtime state (State, Status)
  - Ephemeral IDs (RequestId, VersionId)
  - Computed values (ARN if derived from name)
- **Stable Attributes**: Hash based on:
  - Resource configuration (policies, parameters)
  - Tags
  - Relationships (attached roles, security groups)

### Alternatives Considered

- **MD5**: Faster but not collision-resistant (security not critical here but SHA256 is standard)
- **Full resource comparison**: More accurate but slower, requires detailed schema knowledge per resource type
- **Attribute-by-attribute diff**: More granular but requires per-resource-type logic

### Implementation Notes

```python
import json
import hashlib

# Attributes to exclude from hashing (volatile data)
EXCLUDE_ATTRIBUTES = {
    'ResponseMetadata',
    'LastModifiedDate',
    'CreatedDate',
    'CreateDate',
    'State',
    'Status',
    'RequestId',
    'VersionId',
    'LastUpdateTime',
    'Arn',  # If derivable from name
}

def compute_config_hash(resource_data):
    """Compute stable hash of resource configuration"""
    # Deep copy and remove excluded attributes
    clean_data = remove_volatile_attributes(resource_data, EXCLUDE_ATTRIBUTES)

    # Normalize: sort keys for deterministic JSON
    normalized = json.dumps(clean_data, sort_keys=True, default=str)

    # Hash
    return hashlib.sha256(normalized.encode()).hexdigest()

def remove_volatile_attributes(data, exclude_set):
    """Recursively remove excluded attributes from nested dict/list"""
    if isinstance(data, dict):
        return {
            k: remove_volatile_attributes(v, exclude_set)
            for k, v in data.items()
            if k not in exclude_set
        }
    elif isinstance(data, list):
        return [remove_volatile_attributes(item, exclude_set) for item in data]
    else:
        return data

def detect_changes(baseline_snapshot, current_resources):
    """Identify modified resources by hash comparison"""
    baseline_hashes = {r.arn: r.config_hash for r in baseline_snapshot.resources}

    modified = []
    for resource in current_resources:
        current_hash = compute_config_hash(resource.raw_data)
        baseline_hash = baseline_hashes.get(resource.arn)

        if baseline_hash and baseline_hash != current_hash:
            modified.append({
                'arn': resource.arn,
                'type': resource.type,
                'baseline_hash': baseline_hash,
                'current_hash': current_hash
            })

    return modified
```

**Hash Storage**: Store hash in snapshot alongside each resource for efficient delta calculation.

---

## 5. AWS API Rate Limiting Strategies

### Decision

Use **boto3 standard retry with exponential backoff**, configured via `botocore.config.Config`, with **client-side rate limiting** for known throttle-prone APIs.

### Rationale

- **Built-in Retry**: boto3/botocore already implements exponential backoff for throttling errors (HTTP 429, ThrottlingException)
- **Configurable Retry**: Can customize max attempts and backoff multiplier via Config object
- **Service-Specific Limits**: Some APIs (IAM, CloudFormation) have lower rate limits; apply client-side rate limiting to avoid hitting limits
- **Graceful Degradation**: Tool continues operation even if some API calls are throttled, with progress indication so user understands delays

### Alternatives Considered

- **Manual retry logic**: Reinventing the wheel, boto3 already handles this well
- **No rate limiting**: Will fail on large environments or repeated runs
- **Third-party rate limiting** (ratelimit, pyrate-limiter): Adds dependency for minimal benefit

### Implementation Notes

```python
import boto3
from botocore.config import Config

# Aggressive retry configuration for batch operations
retry_config = Config(
    retries={
        'max_attempts': 10,
        'mode': 'adaptive'  # Adaptive retry mode (boto3 1.16+)
    },
    max_pool_connections=50
)

def create_boto_client(service_name, region_name='us-east-1'):
    """Create boto3 client with retry configuration"""
    return boto3.client(
        service_name,
        region_name=region_name,
        config=retry_config
    )

# Service-specific rate limits (calls per second)
RATE_LIMITS = {
    'iam': 5,           # IAM has strict rate limits (global service)
    'cloudformation': 2,
    'default': 10       # Conservative default
}

import time
from threading import Lock

class RateLimiter:
    """Simple token bucket rate limiter"""
    def __init__(self, rate):
        self.rate = rate
        self.tokens = rate
        self.last_update = time.time()
        self.lock = Lock()

    def acquire(self):
        with self.lock:
            now = time.time()
            elapsed = now - self.last_update
            self.tokens = min(self.rate, self.tokens + elapsed * self.rate)
            self.last_update = now

            if self.tokens >= 1:
                self.tokens -= 1
                return True
            else:
                sleep_time = (1 - self.tokens) / self.rate
                time.sleep(sleep_time)
                self.tokens = 0
                return True

# Usage
iam_limiter = RateLimiter(RATE_LIMITS['iam'])

def list_iam_roles(client):
    iam_limiter.acquire()  # Throttle client-side before API call
    return client.list_roles()
```

**Throttling Communication**:
- Log throttling events at INFO level (not ERROR)
- Update progress indicator to show "Throttled, retrying..."
- Track retry metrics for post-operation reporting

---

## 6. Snapshot Storage Format

### Decision

Use **YAML for snapshots** with **optional gzip compression** for large snapshots.

### Rationale

- **YAML vs JSON**:
  - YAML: More human-readable, comments supported, cleaner diffs in version control
  - JSON: More ubiquitous, slightly faster parsing
  - **Decision**: YAML for human-readability and diff-friendliness, critical for debugging and version control
- **Compression**: Optional gzip compression for snapshots >1MB to save disk space
  - 1000 resources ≈ 5-10MB uncompressed → ~1-2MB gzipped
  - Not enabled by default (human-readability priority)
- **Diff-Friendly**: YAML with consistent field ordering enables meaningful `git diff` on snapshots

### Alternatives Considered

- **JSON**: More standard but less readable
- **SQLite database**: More queryable but less portable, not diff-friendly
- **Binary format** (pickle, msgpack): Fast but not human-readable, poor for debugging

### Implementation Notes

```python
import yaml
import gzip
from pathlib import Path

class SnapshotStorage:
    def __init__(self, storage_dir='.snapshots'):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(exist_ok=True)

    def save_snapshot(self, snapshot, compress=False):
        """Save snapshot to YAML file, optionally compressed"""
        filename = f"{snapshot.name}.yaml"
        if compress:
            filename += ".gz"

        filepath = self.storage_dir / filename

        # Convert snapshot to dict
        snapshot_dict = snapshot.to_dict()

        # Serialize to YAML
        yaml_str = yaml.dump(
            snapshot_dict,
            default_flow_style=False,  # Block style (more readable)
            sort_keys=False,            # Preserve insertion order
            allow_unicode=True
        )

        if compress:
            with gzip.open(filepath, 'wt', encoding='utf-8') as f:
                f.write(yaml_str)
        else:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(yaml_str)

        return filepath

    def load_snapshot(self, snapshot_name):
        """Load snapshot from YAML file (auto-detects compression)"""
        # Try compressed first
        filepath_gz = self.storage_dir / f"{snapshot_name}.yaml.gz"
        if filepath_gz.exists():
            with gzip.open(filepath_gz, 'rt', encoding='utf-8') as f:
                return yaml.safe_load(f)

        # Try uncompressed
        filepath = self.storage_dir / f"{snapshot_name}.yaml"
        with open(filepath, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
```

**Snapshot File Structure**:
```yaml
name: baseline-2025-10-26
created_at: 2025-10-26T10:30:00Z
account_id: "123456789012"
regions:
  - us-east-1
  - us-west-2
resource_count: 342
resources:
  - arn: arn:aws:iam::123456789012:role/baseline-role
    type: iam:role
    name: baseline-role
    region: global
    tags:
      Environment: production
    config_hash: a1b2c3d4...
    created_at: 2025-10-01T00:00:00Z
    raw_config:
      # Full boto3 response...
```

---

## 7. Multi-Region Resource Tracking

### Decision

Use **parallel region queries** with `ThreadPoolExecutor`, **caching enabled regions** list, and **regional resource type filtering**.

### Rationale

- **Parallel Queries**: Query multiple regions simultaneously to minimize total time
  - 3 regions × 10 services = 30 API calls
  - Sequential: ~5 minutes, Parallel: ~1-2 minutes
- **Enabled Regions Only**: Not all regions are enabled in all accounts (e.g., Asia Pacific regions require opt-in). Query `ec2:DescribeRegions` to get enabled regions.
- **Regional vs Global Resources**: Some resources are global (IAM, S3 buckets, CloudFront) and should only be queried once, not per-region
- **Region Specification**: Allow users to specify regions via CLI flag (e.g., `--regions us-east-1,us-west-2`) or default to all enabled regions

### Alternatives Considered

- **Sequential region processing**: Too slow for multi-region deployments
- **All regions always**: Wastes time on disabled regions
- **Single region only**: Doesn't meet multi-region requirement from spec

### Implementation Notes

```python
import boto3
from concurrent.futures import ThreadPoolExecutor, as_completed

# Global services (query once, not per-region)
GLOBAL_SERVICES = {'iam', 's3', 'cloudfront', 'route53'}

# Regional services
REGIONAL_SERVICES = {'ec2', 'lambda', 'rds', 'ecs', 'eks', ...}

def get_enabled_regions():
    """Get list of enabled regions for the account"""
    ec2 = boto3.client('ec2', region_name='us-east-1')
    response = ec2.describe_regions(AllRegions=False)  # Only enabled regions
    return [r['RegionName'] for r in response['Regions']]

def collect_multi_region_resources(regions=None, services=None):
    """Collect resources across multiple regions in parallel"""
    if regions is None:
        regions = get_enabled_regions()

    if services is None:
        services = REGIONAL_SERVICES.union(GLOBAL_SERVICES)

    all_resources = []

    # Collect global resources once
    global_services = services.intersection(GLOBAL_SERVICES)
    for service in global_services:
        all_resources.extend(collect_service_resources('us-east-1', service))

    # Collect regional resources in parallel
    regional_services = services.intersection(REGIONAL_SERVICES)
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = []
        for region in regions:
            for service in regional_services:
                future = executor.submit(
                    collect_service_resources, region, service
                )
                futures.append(future)

        for future in as_completed(futures):
            try:
                resources = future.result()
                all_resources.extend(resources)
            except Exception as e:
                # Log but don't fail entire snapshot
                logging.warning(f"Failed to collect resources: {e}")

    return all_resources
```

**Performance Optimization**:
- Max 10 concurrent API calls to avoid overwhelming AWS or hitting service quotas
- Progress indicator shows per-region and per-service progress
- Cache enabled regions list for 24 hours to avoid repeated API calls

---

## 8. Progress Indication for Long Operations

### Decision

Use **rich library Progress widget** with **multi-task progress tracking** for concurrent operations.

### Rationale

- **Rich Library**: Modern, feature-rich terminal UI library with excellent progress bar support
- **Multi-Task Progress**: Can display progress for multiple concurrent operations (e.g., each region/service pair gets its own progress bar)
- **Indeterminate Progress**: For operations where total count is unknown (e.g., paginating through resources), use spinner or indeterminate progress bar
- **Time Estimates**: rich automatically calculates ETA based on current progress rate
- **Clean Output**: Progress bars can be hidden after completion, leaving clean summary

### Alternatives Considered

- **tqdm**: Popular but less feature-rich than rich for CLI applications
- **Custom progress implementation**: Unnecessary when rich provides excellent solution
- **No progress indication**: Poor UX for long-running operations

### Implementation Notes

```python
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
    TimeRemainingColumn
)

def snapshot_with_progress(regions, services):
    """Create snapshot with rich progress indication"""

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
    ) as progress:

        # Create overall task
        overall = progress.add_task(
            "[cyan]Creating snapshot...",
            total=len(regions) * len(services)
        )

        # Create task per region
        region_tasks = {}
        for region in regions:
            task_id = progress.add_task(
                f"[green]{region}",
                total=len(services)
            )
            region_tasks[region] = task_id

        # Collect resources
        for region in regions:
            for service in services:
                # Collect resources for this region/service
                resources = collect_service_resources(region, service)

                # Update progress
                progress.update(region_tasks[region], advance=1)
                progress.update(overall, advance=1)

        progress.update(overall, description="[green]✓ Snapshot complete!")

# Indeterminate progress for unknown-length operations
def paginate_with_spinner(client, paginator_name):
    """Paginate through results with spinner"""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
    ) as progress:
        task = progress.add_task(
            description="Fetching resources...",
            total=None  # Indeterminate
        )

        paginator = client.get_paginator(paginator_name)
        results = []

        for page in paginator.paginate():
            results.extend(page.get('Items', []))
            progress.update(task, description=f"Fetched {len(results)} resources...")

        progress.update(task, description=f"[green]✓ Fetched {len(results)} resources")

        return results
```

**Progress Display Examples**:

```
Creating snapshot...  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 0:00:00
us-east-1            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 10/10 0:00:15
us-west-2            ━━━━━━━━━━━━━━━━━━━━━━━╸─────────────── 7/10  0:00:23
```

---

## 9. Resource Filtering by Date and Tags

### Decision

Implement **post-collection filtering** with in-memory filtering after resource collection, supporting date ranges (before/after/between) and AWS tag matching with AND logic for multiple tags.

### Rationale

- **Post-Collection Approach**: Collect all resources first, then filter in-memory. This is simpler than filtering during collection and allows transparent reporting of "X resources collected, Y matched filters".
- **Creation Timestamp Availability**: Most AWS resources have creation timestamps in their API responses (CreatedDate, CreateTime, LaunchTime, etc.), but field names vary by service.
- **Tag Availability**: All taggable resources return tags in Describe/List API calls (Tags field with Key/Value pairs).
- **Performance**: Filtering 1000 resources in-memory is negligible (<10ms). Network I/O dominates, not filtering logic.
- **AND Logic for Multiple Tags**: Resource must have ALL specified tags to match (more restrictive, prevents unexpected inclusions).

### Alternatives Considered

- **API-level filtering** (using AWS API filters): Not consistently supported across all services, would require service-specific filter logic
- **OR logic for tags**: Less predictable results, harder for users to reason about what's included
- **Pre-collection filtering**: Would require knowing resource timestamps before fetching full resource details, not feasible with most AWS APIs

### Implementation Notes

```python
from datetime import datetime
from typing import List, Dict, Optional

class ResourceFilter:
    """Filter collected resources by date and tags"""

    def __init__(
        self,
        before_date: Optional[datetime] = None,
        after_date: Optional[datetime] = None,
        required_tags: Optional[Dict[str, str]] = None
    ):
        self.before_date = before_date
        self.after_date = after_date
        self.required_tags = required_tags or {}

    def matches(self, resource: Resource) -> bool:
        """Check if resource matches all filter criteria"""

        # Date filtering
        if self.before_date or self.after_date:
            if not resource.created_at:
                # Resource doesn't have creation timestamp
                return False

            if self.before_date and resource.created_at >= self.before_date:
                return False

            if self.after_date and resource.created_at < self.after_date:
                return False

        # Tag filtering (AND logic - must have ALL required tags)
        if self.required_tags:
            resource_tags = resource.tags or {}
            for key, value in self.required_tags.items():
                if resource_tags.get(key) != value:
                    return False

        return True

    def apply(self, resources: List[Resource]) -> tuple[List[Resource], Dict]:
        """Apply filter and return (filtered_resources, stats)"""
        total = len(resources)

        # Track filtering stats
        stats = {
            'total_collected': total,
            'date_filtered_count': 0,
            'tag_filtered_count': 0,
            'final_count': 0,
            'no_timestamp_count': 0
        }

        # Apply filters
        filtered = []
        for resource in resources:
            if self.matches(resource):
                filtered.append(resource)
            elif (self.before_date or self.after_date) and not resource.created_at:
                stats['no_timestamp_count'] += 1

        # Calculate intermediate stats
        if self.before_date or self.after_date:
            date_filtered = [r for r in resources if self._matches_date(r)]
            stats['date_filtered_count'] = len(date_filtered)

        if self.required_tags:
            tag_filtered = [r for r in resources if self._matches_tags(r)]
            stats['tag_filtered_count'] = len(tag_filtered)

        stats['final_count'] = len(filtered)

        return filtered, stats

    def _matches_date(self, resource: Resource) -> bool:
        """Check only date criteria"""
        if not resource.created_at:
            return False
        if self.before_date and resource.created_at >= self.before_date:
            return False
        if self.after_date and resource.created_at < self.after_date:
            return False
        return True

    def _matches_tags(self, resource: Resource) -> bool:
        """Check only tag criteria"""
        resource_tags = resource.tags or {}
        for key, value in self.required_tags.items():
            if resource_tags.get(key) != value:
                return False
        return True


# CLI usage
def create_snapshot_with_filters(
    name: str,
    before_date: Optional[str] = None,
    after_date: Optional[str] = None,
    between_dates: Optional[str] = None,
    filter_tags: Optional[str] = None
):
    # Parse dates
    parsed_before = parse_date(before_date) if before_date else None
    parsed_after = parse_date(after_date) if after_date else None

    if between_dates:
        start, end = between_dates.split(',')
        parsed_after = parse_date(start)
        parsed_before = parse_date(end)

    # Parse tags (format: "Key1=Value1,Key2=Value2")
    required_tags = {}
    if filter_tags:
        for tag_pair in filter_tags.split(','):
            key, value = tag_pair.split('=', 1)
            required_tags[key.strip()] = value.strip()

    # Collect all resources
    all_resources = collect_resources(regions, resource_types)

    # Apply filters
    resource_filter = ResourceFilter(
        before_date=parsed_before,
        after_date=parsed_after,
        required_tags=required_tags
    )

    filtered_resources, stats = resource_filter.apply(all_resources)

    # Display filtering results
    print(f"Resources collected: {stats['total_collected']}")
    if parsed_before or parsed_after:
        print(f"Date filter matched: {stats['date_filtered_count']}")
    if required_tags:
        print(f"Tag filter matched: {stats['tag_filtered_count']}")
    print(f"Final count (all filters): {stats['final_count']}")

    if stats['no_timestamp_count'] > 0:
        print(f"⚠ Warning: {stats['no_timestamp_count']} resources excluded (no creation timestamp)")

    # Create snapshot with filtered resources
    snapshot = Snapshot(
        name=name,
        resources=filtered_resources,
        filters_applied={
            'date_filters': {
                'before_date': before_date,
                'after_date': after_date,
            },
            'tag_filters': list(required_tags.items())
        },
        total_resources_before_filter=stats['total_collected']
    )

    return snapshot


def parse_date(date_str: str) -> datetime:
    """Parse YYYY-MM-DD date string to UTC datetime"""
    try:
        return datetime.strptime(date_str, '%Y-%m-%d').replace(tzinfo=timezone.utc)
    except ValueError:
        raise ValueError(f"Invalid date format: {date_str}. Use YYYY-MM-DD")
```

**Creation Timestamp Field Names by Service**:
- IAM: `CreateDate`
- Lambda: `LastModified` (use as proxy for creation if CodeSha256 indicates first version)
- EC2 Instances: `LaunchTime`
- S3 Buckets: `CreationDate`
- RDS: `InstanceCreateTime`
- CloudWatch Logs: `creationTime`
- CloudFormation: `CreationTime`
- DynamoDB: `CreationDateTime`

**Services Without Reliable Creation Timestamps**:
- IAM Policies (have CreateDate but may not reflect true creation for AWS-managed)
- Some CloudWatch metrics

**Handling Missing Timestamps**:
- Log warning for each service type where timestamps are unavailable
- Include resources with missing timestamps in unfiltered snapshots
- Exclude resources with missing timestamps from date-filtered snapshots
- Report count of excluded resources in summary

**Filter Combination Logic**:
```
if date_filters AND tag_filters:
    include_resource = matches_date(resource) AND matches_tags(resource)
elif date_filters:
    include_resource = matches_date(resource)
elif tag_filters:
    include_resource = matches_tags(resource)
else:
    include_resource = True  # No filters
```

---

## Summary of Key Decisions

| Area | Decision | Key Benefit |
|------|----------|-------------|
| Resource Enumeration | boto3 client + concurrent collection | Performance: meets <5 min goal |
| Cost Attribution | Cost Explorer API + ARN matching | Accuracy: <1% error margin achievable |
| Dependency Detection | Manual rules + topological sort | Reliability: 95% success rate for common resources |
| Change Detection | SHA256 hash of normalized config | Efficiency: fast delta calculation |
| Rate Limiting | boto3 adaptive retry + client-side throttling | Resilience: handles API limits gracefully |
| Storage Format | YAML with optional gzip | Human-readability + version control friendly |
| Multi-Region | Parallel queries with region filtering | Performance: supports multi-region efficiently |
| Progress Indication | rich library with multi-task tracking | UX: clear progress for long operations |
| Resource Filtering | Post-collection in-memory filtering | Flexibility: historical baselines + transparent reporting |

---

## Next Steps

1. ✅ Research complete - all technical questions resolved
2. → Proceed to Phase 1: Data Model design
3. → Proceed to Phase 1: CLI contracts specification
4. → Proceed to Phase 1: Quickstart guide creation

**Research Status**: Complete - Ready for Phase 1 design.
