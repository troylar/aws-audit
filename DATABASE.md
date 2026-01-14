# Database Schema & Power User Queries

## Database Schema

For power users who want to run direct SQL queries, the SQLite database (`inventory.db`) has the following structure:

**`snapshots`** — Metadata about each capture
| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Primary Key |
| `name` | TEXT | Unique snapshot name |
| `created_at` | TIMESTAMP | When the snapshot was taken |
| `account_id` | TEXT | AWS Account ID |
| `regions` | TEXT | Comma-separated list of regions scanned |
| `resource_count` | INTEGER | Total resources in snapshot |

**`resources`** — The actual inventory items
| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Primary Key |
| `snapshot_id` | INTEGER | Foreign Key to `snapshots` |
| `arn` | TEXT | Amazon Resource Name |
| `resource_type` | TEXT | e.g., `AWS::EC2::Instance` |
| `name` | TEXT | Resource name or ID |
| `region` | TEXT | AWS Region |
| `source` | TEXT | Collection method (`config` or `direct_api`) |
| `created_at` | TIMESTAMP | Detection/Creation timestamp |
| `config_hash` | TEXT | Hash of configuration for drift detection |

**`resource_tags`** — Key/value pairs for resources
| Column | Type | Description |
|--------|------|-------------|
| `resource_id` | INTEGER | Foreign Key to `resources` |
| `key` | TEXT | Tag key |
| `value` | TEXT | Tag value |

## Power User Queries

The `awsinv query sql` command opens up unlimited analysis possibilities. 

> **Tip:** Use the `--snapshot` flag (or `AWSINV_SNAPSHOT_ID` environment variable) to automatically filter your query to a specific snapshot. This saves you from writing complex `JOIN snapshots s ON ... WHERE s.name = ...` clauses!

### 1. Tagging Compliance
Find all EC2 instances that are missing the mandatory `Owner` tag:

```bash
# Set your target snapshot one time
export AWSINV_SNAPSHOT_ID="latest-prod"

# Now the query is simple and clean
awsinv query sql "
  SELECT r.name, r.region
  FROM resources r
  WHERE r.resource_type = 'AWS::EC2::Instance'
  AND NOT EXISTS (
    SELECT 1 FROM resource_tags t 
    WHERE t.resource_id = r.id 
    AND t.key = 'Owner'
  )
"
```

### 2. Cost Center Distribution
Count resources by Cost Center tag to verify allocation:

```bash
awsinv query sql "
  SELECT t.value as cost_center, COUNT(*) as resource_count
  FROM resource_tags t
  JOIN resources r ON t.resource_id = r.id
  WHERE t.key = 'CostCenter'
  GROUP BY t.value
  ORDER BY resource_count DESC
" --snapshot latest-prod
```

### 3. Multi-Region Sprawl
Identify which regions have the most resources, helping you spot unused regions:

```bash
awsinv query sql "
  SELECT region, COUNT(*) as count
  FROM resources
  GROUP BY region
  ORDER BY count DESC
" --snapshot latest-prod
```

### 4. High-Churn Resources
Find resources that have changed configuration frequently (by counting unique config hashes across snapshots):

```bash
awsinv query sql "
  SELECT arn, name, resource_type, COUNT(DISTINCT config_hash) as revisions
  FROM resources
  GROUP BY arn, name, resource_type
  HAVING revisions > 3
  ORDER BY revisions DESC
"
```

### 5. Audit "Direct API" vs "Config" Collection
Verify which resources are falling back to slow API calls instead of using AWS Config:

```bash
awsinv query sql "
  SELECT resource_type, source, COUNT(*) 
  FROM resources 
  GROUP BY resource_type, source
  ORDER BY source, resource_type
" --snapshot latest-prod
```

### 6. Zombie Resource Candidates
Find resources (excluding IAM) that were created over a year ago and might be forgotten:

```bash
awsinv query sql "
  SELECT resource_type, name, created_at, region
  FROM resources
  WHERE created_at < date('now', '-1 year')
  AND resource_type NOT LIKE 'AWS::IAM::%'
  ORDER BY created_at ASC
" --snapshot latest-prod
```

### 7. Tag Taxonomy Audit
Find inconsistent tag values (e.g., 'prod', 'production', 'Prod') to clean up your tagging strategy:

```bash
awsinv query sql "
  SELECT DISTINCT value as raw_tag_value, COUNT(*) as count 
  FROM resource_tags 
  WHERE key = 'Environment'
  GROUP BY value
  ORDER BY value
" --snapshot latest-prod
```

### 8. Infrastructure Growth Trends
Analyze how your total resource count is growing over time by querying the snapshots metadata:

```bash
awsinv query sql "
  SELECT date(created_at) as capture_date, resource_count, name
  FROM snapshots
  ORDER BY created_at ASC
"
```

### 9. Unencrypted EBS Volumes
Find volumes that are not encrypted at rest (Cost/Security):

```bash
awsinv query sql "
  SELECT name, region, created_at
  FROM resources
  WHERE resource_type = 'AWS::EC2::Volume'
  AND raw_config LIKE '%\"Encrypted\": false%'
" --snapshot latest-prod
```

### 10. Stopped EC2 Instances
Find instances that are currently stopped and not running (Cost):

```bash
awsinv query sql "
  SELECT name, region, created_at
  FROM resources
  WHERE resource_type = 'AWS::EC2::Instance'
  AND raw_config LIKE '%\"Name\": \"stopped\"%'
" --snapshot latest-prod
```

### 11. Available (Unattached) Volumes
Identify EBS volumes that exist but are not attached to any instance (Cost):

```bash
awsinv query sql "
  SELECT name, region, created_at
  FROM resources
  WHERE resource_type = 'AWS::EC2::Volume'
  AND raw_config LIKE '%\"State\": \"available\"%'
" --snapshot latest-prod
```

### 12. Default VPCs
Identify default VPCs which often shouldn't be used for production resources (Security):

```bash
awsinv query sql "
  SELECT name, region
  FROM resources
  WHERE resource_type = 'AWS::EC2::VPC'
  AND raw_config LIKE '%\"IsDefault\": true%'
" --snapshot latest-prod
```

### 13. Lambda Function Runtimes
Aggregate Lambda functions by runtime to identify deprecated versions (Ops):

```bash
# Requires SQLite with JSON1 extension, or use text matching
awsinv query sql "
  SELECT json_extract(raw_config, '$.Runtime') as runtime, COUNT(*) as count
  FROM resources
  WHERE resource_type = 'AWS::Lambda::Function'
  GROUP BY runtime
  ORDER BY count DESC
" --snapshot latest-prod
```

### 14. Untagged Resources
Find resources that have absolutely no tags (Compliance):

```bash
awsinv query sql "
  SELECT r.name, r.resource_type
  FROM resources r
  LEFT JOIN resource_tags t ON r.id = t.resource_id
  WHERE t.id IS NULL
  AND r.resource_type != 'AWS::EC2::Volume'
" --snapshot latest-prod
```

### 15. Empty Tag Values
Find tags that have keys but empty values (Quality):

```bash
awsinv query sql "
  SELECT r.name, r.resource_type, t.key
  FROM resources r
  JOIN resource_tags t ON r.id = t.resource_id
  WHERE t.value = ''
" --snapshot latest-prod
```

### 16. Security Groups Allowing All Traffic
Find Security Groups with `0.0.0.0/0` in their ingress rules (Security):

```bash
awsinv query sql "
  SELECT name, region
  FROM resources
  WHERE resource_type = 'AWS::EC2::SecurityGroup'
  AND raw_config LIKE '%0.0.0.0/0%'
" --snapshot latest-prod
```

### 17. Oldest Active Resources
List the top 15 oldest resources in the account (Ops/Cleanup):

```bash
awsinv query sql "
  SELECT name, resource_type, date(created_at) as created
  FROM resources
  WHERE created_at IS NOT NULL
  ORDER BY created_at ASC
  LIMIT 15
" --snapshot latest-prod
```

### 18. Resources by Service
Aggregate count of resources by AWS Service (Inventory):

```bash
# Extract service name from resource type (e.g., AWS::EC2::Instance -> AWS::EC2)
awsinv query sql "
  SELECT 
    substr(resource_type, 1, instr(substr(resource_type, 6), '::') + 5) as service,
    COUNT(*) as count
  FROM resources
  GROUP BY service
  ORDER BY count DESC
" --snapshot latest-prod
```

### 19. Identify "Launch Wizard" Security Groups
Find security groups created via console wizards, often needing cleanup (Quality):

```bash
awsinv query sql "
  SELECT name, region
  FROM resources
  WHERE resource_type = 'AWS::EC2::SecurityGroup'
  AND (name LIKE 'launch-wizard-%' OR name LIKE 'default')
" --snapshot latest-prod
```

### 20. IAM Users with Console Access
Find users who have a Login Profile (password) enabled (Security):

```bash
# Note: IAM collector must capture LoginProfile presence in raw_config
awsinv query sql "
  SELECT name
  FROM resources
  WHERE resource_type = 'AWS::IAM::User'
  AND raw_config LIKE '%LoginProfile%'
" --snapshot latest-prod
```

### 21. Bucket Versioning Status
Check which S3 buckets have versioning disabled (Resilience):

```bash
awsinv query sql "
  SELECT name, region
  FROM resources
  WHERE resource_type = 'AWS::S3::Bucket'
  AND (raw_config LIKE '%\"Versioning\": \"Disabled\"%' OR raw_config NOT LIKE '%\"Versioning\"%')
" --snapshot latest-prod
```

### 22. T-Series Instances
Audit usage of burstable performance instances (Cost):

```bash
awsinv query sql "
  SELECT name, region, json_extract(raw_config, '$.InstanceType') as type
  FROM resources
  WHERE resource_type = 'AWS::EC2::Instance'
  AND raw_config LIKE '%\"InstanceType\": \"t%\"%'
" --snapshot latest-prod
```

### 23. Resources Created in Last 24 Hours
Identify brand new resources for immediate review (Ops):

```bash
awsinv query sql "
  SELECT name, resource_type, created_at
  FROM resources
  WHERE created_at > datetime('now', '-1 day')
" --snapshot latest-prod
```

### 24. Most Used Tag Keys
Which tag keys are used most frequently across the environment (Taxonomy):

```bash
awsinv query sql "
  SELECT key, COUNT(*) as frequency
  FROM resource_tags
  GROUP BY key
  ORDER BY frequency DESC
  LIMIT 10
" --snapshot latest-prod
```

### 25. Orphaned Elastic IPs
Find EIPs that are not associated with any instance or interface (Cost):

```bash
awsinv query sql "
  SELECT name, region
  FROM resources
  WHERE resource_type = 'AWS::EC2::EIP'
  AND (raw_config LIKE '%\"AssociationId\": null%' OR raw_config NOT LIKE '%\"AssociationId\"%')
" --snapshot latest-prod
```

### 26. Classic Load Balancers
Identify legacy CLBs for migration to ALB/NLB (Modernization):

```bash
awsinv query sql "
  SELECT name, region
  FROM resources
  WHERE resource_type = 'AWS::ElasticLoadBalancing::LoadBalancer'
  AND raw_config LIKE '%\"Scheme\": \"internet-facing\"%' 
  -- Note: collector distinction for ELBv1 vs v2 depends on raw_config content
" --snapshot latest-prod
```

### 27. Key Pairs Used
List EC2 Key Pairs in use (Security):

```bash
awsinv query sql "
  SELECT name, region
  FROM resources
  WHERE resource_type = 'AWS::EC2::KeyPair'
" --snapshot latest-prod
```

### 28. VPCs without Subnets
Find VPCs that might be empty/unused (Network):

```bash
awsinv query sql "
  SELECT v.name, v.region
  FROM resources v
  WHERE v.resource_type = 'AWS::EC2::VPC'
  AND NOT EXISTS (
    SELECT 1 FROM resources s
    WHERE s.resource_type = 'AWS::EC2::Subnet'
    AND json_extract(s.raw_config, '$.VpcId') = v.name
  )
" --snapshot latest-prod
```
