# Infrastructure Patterns

Patterns are reusable architecture blueprints that describe **what your infrastructure should look like**. They define the resource types, counts, configuration expectations, and compliance guardrails that make up a known-good architecture.

Use patterns to answer: *"Does this account match our standard three-tier web app?"* or *"Which of our reference architectures is closest to what's deployed here?"*

## Patterns vs Guardrails

Patterns and guardrails solve different problems and work best together.

| | Patterns | Guardrails |
|---|---|---|
| **Question answered** | "What should be deployed?" | "How should it be configured?" |
| **Scope** | Whole architecture (multiple resource types) | Individual resource settings |
| **Defines** | Resource composition, counts, relationships | Configuration rules, security policies |
| **Example** | "A web app needs 1 ALB, 2 Lambda functions, 1 DynamoDB table" | "All DynamoDB tables must have encryption enabled" |
| **Evaluation** | Similarity scoring (0-100%) | Pass/fail per resource |
| **Action on failure** | Report gaps, suggest changes | BLOCK, WARN, or AUTO-FIX |

**Think of it this way:** A pattern says *"you need an S3 bucket"*. A guardrail says *"that S3 bucket must be encrypted"*. Together they answer: *"you need an encrypted S3 bucket"*.

### How They Work Together

Patterns can reference guardrails by ID. When you compare a snapshot against a pattern, the comparison engine:

1. **Scores resource alignment** -- Are the right resource types present in the right quantities?
2. **Evaluates expect fields** -- Do the resources have the right configuration values?
3. **Runs referenced guardrails** -- Do the resources pass the pattern's compliance requirements?

```yaml
# Pattern that references guardrails
name: secure-data-lake
description: S3 data lake with encryption and access controls
version: 1
tags: [data-lake, s3, security]
owner: platform-team
resources:
  - type: s3:bucket
    count: 3
    description: Raw, processed, and curated data buckets
    expect:
      Versioning.Status: Enabled
  - type: kms:key
    count: 1
    description: Encryption key for all buckets

# These guardrails are evaluated during comparison
guardrails:
  - GR-ENC-001  # S3 bucket must have encryption at rest
  - GR-ENC-004  # DynamoDB table must have encryption
```

When you run `awsinv patterns compare --snapshot my-snapshot`, the report shows:

- **Pattern alignment:** 2/2 resource types found (score: 100%)
- **Expect violations:** Bucket `raw-data` has `Versioning.Status: Suspended` (expected: `Enabled`)
- **Guardrail violations:** Bucket `curated-data` missing encryption (GR-ENC-001)

### Example: Seeing the Difference

Consider a production web application. Here's how you'd define both the pattern (architecture) and guardrails (configuration rules):

**The pattern** defines what the architecture looks like:

```yaml
name: three-tier-web-app
description: Standard three-tier web application with ALB, compute, and database
version: 1
tags: [web, three-tier, production]
owner: platform-team
resources:
  - type: elasticloadbalancing:loadbalancer
    count: 1
    description: Application load balancer
    expect:
      Scheme: internet-facing
      Type: application

  - type: lambda:function
    count: 2
    description: API handler and background worker
    expect:
      Runtime: python3.11

  - type: dynamodb:table
    count: 1
    description: Application data store
    expect:
      BillingMode: PAY_PER_REQUEST
      SSEDescription.Status: ENABLED

  - type: s3:bucket
    count: 1
    description: Static asset storage

  - type: cloudfront:distribution
    count: 1
    description: CDN for static assets

guardrails:
  - GR-ENC-001   # S3 encryption
  - GR-ENC-004   # DynamoDB encryption
  - GR-NET-005   # Load balancer deletion protection
  - GR-TAG-001   # Required tags on all resources
```

**The guardrails** define how each resource must be configured:

```yaml
# GR-ENC-001: S3 bucket must have encryption at rest
# - Applies to: s3:bucket
# - Action: AUTO-FIX (adds encryption if missing)

# GR-ENC-004: DynamoDB table must have encryption
# - Applies to: dynamodb:table
# - Action: AUTO-FIX

# GR-NET-005: Load balancer must have deletion protection
# - Applies to: elasticloadbalancing:loadbalancer
# - Action: AUTO-FIX

# GR-TAG-001: All resources must have required tags
# - Applies to: * (all resources)
# - Action: AUTO-FIX
```

**The comparison report** then tells you:
- *Architecture:* "You have 4 of 5 resource types (missing CloudFront distribution)" -- **pattern**
- *Configuration:* "Your DynamoDB table uses PROVISIONED billing, expected PAY_PER_REQUEST" -- **expect field**
- *Compliance:* "Your S3 bucket is missing encryption" -- **guardrail**

---

## Quick Start

### 1. Create a Pattern

Write a YAML file describing your architecture:

```yaml
# serverless-api.yaml
name: serverless-api
description: API Gateway + Lambda + DynamoDB serverless API
version: 1
tags: [serverless, api]
owner: backend-team
resources:
  - type: apigateway:restapi
    count: 1
    description: REST API endpoint
  - type: lambda:function
    count: 3
    description: CRUD handler functions
    expect:
      Runtime: python3.11
      Timeout: ">= 30"
  - type: dynamodb:table
    count: 1
    description: Application data store
    expect:
      BillingMode: PAY_PER_REQUEST
```

Add it to the library:

```bash
awsinv patterns add serverless-api.yaml
```

### 2. Compare Against a Snapshot

```bash
awsinv patterns compare --snapshot prod-account
```

Output:

```
Pattern Comparison: prod-account
================================

  serverless-api v1 (score: 0.67)
  --------------------------------
  Aligned:
    lambda:function       5 found (3 expected)
    dynamodb:table        1 found (1 expected)
  Missing:
    apigateway:restapi    1 expected
  Expect Violations:
    lambda:function 'order-processor': Runtime = python3.9 (expected python3.11)
    lambda:function 'data-sync': Timeout = 15 (expected >= 30)

  Unaccounted Resources:
    s3:bucket              3
    ec2:security-group     2
```

### 3. Generate IaC from a Pattern

Turn any pattern into Terraform or CDK:

```bash
# Terraform
awsinv patterns generate-iac serverless-api --format terraform --output-dir ./infra

# CDK TypeScript
awsinv patterns generate-iac serverless-api --format cdk-typescript --output-dir ./cdk-app

# With guardrails applied during generation
awsinv patterns generate-iac serverless-api --format terraform --guardrails
```

### 4. Run Compliance Across Accounts

Check how well multiple accounts follow your patterns:

```bash
awsinv patterns compliance \
  --snapshot prod-us-east \
  --snapshot prod-us-west \
  --snapshot staging \
  --pattern three-tier-web-app
```

---

## Pattern YAML Reference

### Full Schema

```yaml
name: string              # Required - Pattern name (unique in library)
description: string       # Required - What this architecture is for
version: integer          # Required - Version number (1, 2, 3...)
tags: [string, ...]       # Optional - Categorization tags
owner: string             # Optional - Team or person responsible

resources:                # Required - At least one resource
  - type: string          # Required - Resource type (e.g., "s3:bucket")
    count: integer        # Optional - Expected count (default: 1)
    description: string   # Optional - What this resource is for
    expect:               # Optional - Expected configuration values
      ConfigKey: "value"  # Exact match
      Nested.Key: "value" # Dotted path for nested fields
      NumericKey: ">= 30" # Operator comparison

guardrails: [string, ...] # Optional - Guardrail IDs to evaluate
source_snapshot: string    # Optional - Snapshot this pattern was derived from
source_account: string     # Optional - AWS account ID
```

### Resource Types

Resource types use the format `service:resource-type`, matching the AWS resource types in your inventory snapshots:

| Service | Types |
|---------|-------|
| **S3** | `s3:bucket` |
| **EC2** | `ec2:instance`, `ec2:security-group`, `ec2:volume`, `ec2:vpc`, `ec2:subnet` |
| **Lambda** | `lambda:function` |
| **DynamoDB** | `dynamodb:table` |
| **RDS** | `rds:db`, `rds:cluster` |
| **ELB** | `elasticloadbalancing:loadbalancer`, `elasticloadbalancing:targetgroup` |
| **API Gateway** | `apigateway:restapi` |
| **CloudFront** | `cloudfront:distribution` |
| **KMS** | `kms:key` |
| **SNS/SQS** | `sns:topic`, `sqs:queue` |
| **ECS** | `ecs:cluster`, `ecs:service`, `ecs:task-definition` |

### Expect Fields

Expect fields validate specific configuration values on matching resources. They use dotted paths for nested fields and support operator comparisons for numeric values.

**Exact match:**
```yaml
expect:
  Runtime: python3.11
  BillingMode: PAY_PER_REQUEST
```

**Nested fields (dotted path):**
```yaml
expect:
  SSEDescription.Status: ENABLED
  Versioning.Status: Enabled
  VpcConfig.VpcId: vpc-12345678
```

**Operator comparisons:**
```yaml
expect:
  Timeout: ">= 30"           # Greater than or equal
  MemorySize: "<= 1024"      # Less than or equal
  ProvisionedThroughput.ReadCapacityUnits: "> 0"  # Greater than
  MaxRetries: "!= 0"         # Not equal
```

### When to Use Expect vs Guardrails

| Use Case | Use Expect | Use Guardrail |
|----------|-----------|---------------|
| Check a specific config value | `Runtime: python3.11` | -- |
| Enforce encryption across all S3 buckets | -- | `GR-ENC-001` |
| Verify a Lambda timeout is reasonable | `Timeout: ">= 30"` | -- |
| Block open SSH access on all security groups | -- | `GR-NET-001` |
| Check that a DynamoDB table uses on-demand billing | `BillingMode: PAY_PER_REQUEST` | -- |
| Ensure all resources have required tags | -- | `GR-TAG-001` |

**Rule of thumb:** Use expect fields for pattern-specific configuration checks ("this particular Lambda must use Python 3.11"). Use guardrails for organization-wide policies ("all S3 buckets must be encrypted").

---

## AI Pattern Generation

Generate patterns using AWS Bedrock (requires Bedrock access).

### From a Description

```bash
# Simple
awsinv patterns generate "serverless REST API with DynamoDB backend"

# With specific instructions
awsinv patterns generate "data processing pipeline" \
  --instructions "Use SQS for queueing, Lambda for processing, S3 for storage"

# Save to file
awsinv patterns generate "microservices platform on ECS" \
  --output ecs-platform.yaml
```

### From an Existing Snapshot

Analyze what's already deployed and turn it into a reusable pattern:

```bash
# Generate from a snapshot
awsinv patterns generate --from-snapshot prod-account

# With guardrails included
awsinv patterns generate --from-snapshot prod-account \
  --guardrails GR-ENC-001,GR-NET-001,GR-TAG-001

# Add instructions for how to interpret the snapshot
awsinv patterns generate --from-snapshot prod-account \
  --instructions "Focus on the web application tier, ignore monitoring resources"
```

---

## Library Management

### Listing Patterns

```bash
# List all patterns
awsinv patterns list

# Filter by tag
awsinv patterns list --tag serverless

# Filter by resource type
awsinv patterns list --type lambda:function

# Search by name or description
awsinv patterns list --search "web app"

# JSON output
awsinv patterns list --json
```

### Viewing Pattern Details

```bash
# Show latest version
awsinv patterns show three-tier-web-app

# Show specific version
awsinv patterns show three-tier-web-app --version 2

# JSON output
awsinv patterns show three-tier-web-app --json
```

### Versioning

Patterns are versioned. Add a new version by incrementing the `version` field in your YAML and adding it:

```bash
# v1 already in library
awsinv patterns add three-tier-web-app-v2.yaml  # version: 2 in the file

# Compare always uses the latest version by default
awsinv patterns compare --snapshot prod

# Or target a specific version
awsinv patterns show three-tier-web-app --version 1
```

### Exporting and Deleting

```bash
# Export a pattern to share with another team
awsinv patterns export three-tier-web-app --output shared-pattern.yaml
awsinv patterns export three-tier-web-app --output shared-pattern.json --format json

# Delete a specific version
awsinv patterns delete three-tier-web-app --version 1

# Delete all versions
awsinv patterns delete three-tier-web-app
```

---

## Comparison Engine

### How Scoring Works

The comparison engine calculates a similarity score between a pattern and a snapshot:

```
score = (number of matched resource types) / (total resource types in pattern)
```

- **1.0 (100%):** Every resource type in the pattern exists in the snapshot
- **0.5 (50%):** Half of the pattern's resource types are present
- **0.0 (0%):** None of the pattern's resource types are found

Count mismatches do not affect the score. A pattern expecting 3 Lambda functions still gets a match if the snapshot has 1 or 10 -- the count difference is reported separately.

### Threshold

By default, only patterns scoring 0.25 (25%) or higher are shown. Adjust with `--threshold`:

```bash
# Show all patterns, even weak matches
awsinv patterns compare --snapshot my-snapshot --threshold 0.0

# Only show strong matches
awsinv patterns compare --snapshot my-snapshot --threshold 0.75
```

### AI Guidance

By default, the comparison engine generates AI-powered guidance using Bedrock for the top match. This adds remediation suggestions based on the gaps found. Disable it if you don't have Bedrock access or want faster results:

```bash
# Skip AI guidance (deterministic only, no Bedrock needed)
awsinv patterns compare --snapshot my-snapshot --no-guidance
```

### Targeting a Single Pattern

Compare against a specific pattern file instead of the full library:

```bash
awsinv patterns compare --snapshot my-snapshot --pattern ./my-pattern.yaml
```

### Exporting Results

```bash
# JSON export
awsinv patterns compare --snapshot my-snapshot --output report.json --format json

# YAML export
awsinv patterns compare --snapshot my-snapshot --output report.yaml --format yaml
```

---

## Compliance Reporting

Run pattern comparisons across multiple snapshots to see adoption trends:

```bash
awsinv patterns compliance \
  --snapshot account-a \
  --snapshot account-b \
  --snapshot account-c
```

Output:

```
Compliance Report
=================
Snapshots analyzed: 3

  account-a: 2 matches (top: three-tier-web-app, score: 0.85)
  account-b: 1 match  (top: serverless-api, score: 0.67)
  account-c: 0 matches

Pattern Adoption:
  three-tier-web-app  2 accounts
  serverless-api      1 account

No Matches: account-c
```

### Export Compliance Data

```bash
# JSON for dashboards
awsinv patterns compliance \
  --snapshot account-a \
  --snapshot account-b \
  --output compliance.json --format json

# YAML for documentation
awsinv patterns compliance \
  --snapshot account-a \
  --snapshot account-b \
  --output compliance.yaml --format yaml
```

---

## Generating IaC from Patterns

Convert any pattern into deployable infrastructure code. This uses the same IaC generation engine as `awsinv generate` but starts from a pattern definition instead of a live snapshot.

```bash
# Terraform (default)
awsinv patterns generate-iac serverless-api

# CDK TypeScript
awsinv patterns generate-iac serverless-api --format cdk-typescript

# CDK Python
awsinv patterns generate-iac serverless-api --format cdk-python

# Custom output directory
awsinv patterns generate-iac serverless-api --output-dir ./my-infra

# With guardrails applied during generation
awsinv patterns generate-iac serverless-api --guardrails

# With custom guardrails policy
awsinv patterns generate-iac serverless-api --guardrails --guardrails-policy ./policy.yaml

# Load from YAML file instead of library
awsinv patterns generate-iac ./path/to/pattern.yaml --format terraform
```

---

## Real-World Examples

### Example 1: Event-Driven Data Pipeline

```yaml
name: event-driven-pipeline
description: S3 ingestion, SQS queuing, Lambda processing, DynamoDB storage
version: 1
tags: [data, event-driven, serverless]
owner: data-engineering

resources:
  - type: s3:bucket
    count: 2
    description: Ingestion bucket and processed output bucket
    expect:
      Versioning.Status: Enabled

  - type: sqs:queue
    count: 2
    description: Processing queue and dead-letter queue
    expect:
      VisibilityTimeout: ">= 300"

  - type: lambda:function
    count: 2
    description: S3 event processor and DLQ handler
    expect:
      Runtime: python3.11
      Timeout: ">= 60"
      MemorySize: ">= 256"

  - type: dynamodb:table
    count: 1
    description: Processed records store
    expect:
      BillingMode: PAY_PER_REQUEST
      SSEDescription.Status: ENABLED

guardrails:
  - GR-ENC-001   # S3 encryption
  - GR-ENC-004   # DynamoDB encryption
  - GR-TAG-001   # Required tags
```

### Example 2: Container Platform

```yaml
name: ecs-fargate-platform
description: ECS Fargate cluster with ALB, auto-scaling, and centralized logging
version: 1
tags: [containers, ecs, fargate, production]
owner: platform-team

resources:
  - type: ecs:cluster
    count: 1
    description: Fargate cluster

  - type: ecs:service
    count: 3
    description: Frontend, API, and worker services

  - type: ecs:task-definition
    count: 3
    description: Task definitions for each service

  - type: elasticloadbalancing:loadbalancer
    count: 1
    description: Application load balancer
    expect:
      Type: application
      Scheme: internet-facing

  - type: elasticloadbalancing:targetgroup
    count: 3
    description: Target groups for each service

  - type: ec2:security-group
    count: 2
    description: ALB security group and service security group

  - type: cloudwatch:log-group
    count: 3
    description: Log groups for each service

  - type: iam:role
    count: 2
    description: Task execution role and task role

guardrails:
  - GR-NET-001   # No open SSH
  - GR-NET-003   # No open all-ports
  - GR-NET-005   # ALB deletion protection
  - GR-TAG-001   # Required tags
  - GR-LOG-001   # CloudTrail enabled
```

### Example 3: Multi-Region DR Setup

```yaml
name: multi-region-dr
description: Primary and failover regions with Route53 health checks
version: 1
tags: [disaster-recovery, multi-region, production]
owner: reliability-team

resources:
  - type: rds:cluster
    count: 2
    description: Primary and replica Aurora clusters
    expect:
      Engine: aurora-postgresql
      StorageEncrypted: "True"
      DeletionProtection: "True"

  - type: s3:bucket
    count: 2
    description: Primary and replica buckets with cross-region replication
    expect:
      Versioning.Status: Enabled

  - type: route53:hostedzone
    count: 1
    description: DNS zone for failover routing

  - type: cloudfront:distribution
    count: 1
    description: CDN with multi-origin failover

  - type: kms:key
    count: 2
    description: Encryption keys in each region

guardrails:
  - GR-ENC-001   # S3 encryption
  - GR-ENC-002   # RDS encryption
  - GR-TAG-001   # Required tags
```

---

## Configuration

### Library Location

Patterns are stored as YAML files in a library directory. The location is resolved in this order:

1. `--library` CLI option (per-command override)
2. `AWS_INVENTORY_PATTERNS_PATH` environment variable
3. `.patterns/` directory relative to the storage root (default)

```bash
# Use a custom library location
awsinv patterns list --library /shared/patterns

# Or set via environment variable
export AWS_INVENTORY_PATTERNS_PATH=/shared/patterns
awsinv patterns list
```

### Storage Format

Each pattern is saved as `{name}-v{version}.yaml` in the library directory:

```
.patterns/
  serverless-api-v1.yaml
  serverless-api-v2.yaml
  three-tier-web-app-v1.yaml
  ecs-fargate-platform-v1.yaml
```

---

## CLI Command Reference

| Command | Description |
|---------|-------------|
| `patterns add <file>` | Add a pattern YAML file to the library |
| `patterns generate <description>` | Generate a pattern using AI (Bedrock) |
| `patterns list` | List all patterns (with filtering options) |
| `patterns show <name>` | Show detailed pattern information |
| `patterns compare --snapshot <name>` | Compare a snapshot against the pattern library |
| `patterns generate-iac <name>` | Generate Terraform/CDK from a pattern |
| `patterns compliance --snapshot <name>` | Compliance report across multiple snapshots |
| `patterns delete <name>` | Delete a pattern from the library |
| `patterns export <name>` | Export a pattern to a file |

## Further Reading

- [Guardrails Overview](../guardrails/index.md) -- Policy-based compliance rules that patterns can reference
- [Policy Reference](../guardrails/policy-reference.md) -- Complete guardrail schema
- [IaC Generation](../guides/iac-generation.md) -- Generate Terraform/CDK from snapshots or patterns
- [CI/CD Integration](../guardrails/ci-cd-integration.md) -- Using guardrails in pipelines
