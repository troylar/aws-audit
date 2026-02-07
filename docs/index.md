# AWS Inventory Manager

**Snapshot, Track, Secure, and Clean Up Your AWS Environment**

[![CI](https://github.com/troylar/aws-inventory-manager/actions/workflows/ci.yml/badge.svg)](https://github.com/troylar/aws-inventory-manager/actions/workflows/ci.yml)
[![Coverage](https://codecov.io/gh/troylar/aws-inventory-manager/branch/main/graph/badge.svg)](https://codecov.io/gh/troylar/aws-inventory-manager)
[![PyPI version](https://img.shields.io/pypi/v/aws-inventory-manager.svg)](https://pypi.org/project/aws-inventory-manager/)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

AWS Inventory Manager captures a **point-in-time inventory** of your AWS resources, then helps you track changes, find security issues, and clean up unwanted resources.

!!! note
    "Snapshot" in this tool means an *inventory snapshot* (a catalog of what exists), not an AWS EBS or RDS snapshot. No AWS snapshots are created.

```bash
# Capture your current resource inventory
awsinv snapshot create my-baseline --regions us-east-1,us-west-2

# Track what changed since the baseline
awsinv delta --snapshot my-baseline --show-diff

# Find security issues
awsinv security scan --severity HIGH

# Remove resources created after the baseline
awsinv cleanup preview my-baseline      # See what would be deleted
awsinv cleanup execute my-baseline --confirm  # Execute cleanup
```

---

## Features

<div class="grid cards" markdown>

-   :material-camera:{ .lg .middle } **Inventory Snapshots**

    ---

    27 AWS services, 80+ resource types. Multi-region collection, tag-based filtering, Lambda code collection, export to JSON/CSV/YAML, SQLite storage with SQL queries.

    [:octicons-arrow-right-24: Snapshots guide](guides/snapshots.md)

-   :material-swap-horizontal:{ .lg .middle } **Change Tracking**

    ---

    Field-level drift detection with before/after comparison. Configuration and security change tracking with color-coded terminal output and JSON export for CI/CD.

    [:octicons-arrow-right-24: Change tracking guide](guides/change-tracking.md)

-   :material-shield-check:{ .lg .middle } **Security Scanning**

    ---

    12+ CIS-aligned checks across severity levels. Detect public S3 buckets, open ports, IAM credential age issues. Includes remediation guidance.

    [:octicons-arrow-right-24: Security scanning guide](guides/security-scanning.md)

-   :material-currency-usd:{ .lg .middle } **Cost Analysis**

    ---

    Per-inventory cost tracking with date range filtering, service-level breakdown, tag-based attribution, and AWS Cost Explorer integration.

    [:octicons-arrow-right-24: Cost analysis guide](guides/cost-analysis.md)

-   :material-delete-sweep:{ .lg .middle } **Resource Cleanup**

    ---

    Return to a snapshot baseline or purge all except protected resources. Exclusion filters, preview mode, dependency-aware deletion. 43 deletable resource types.

    [:octicons-arrow-right-24: Resource cleanup guide](guides/resource-cleanup.md)

-   :material-cloud-sync:{ .lg .middle } **AWS Config Integration**

    ---

    Automatic detection, up to 5x faster collection, hybrid fallback to direct API, per-resource source tracking, multi-account via Aggregators.

    [:octicons-arrow-right-24: AWS Config setup](configuration/aws-config-integration.md)

-   :material-database-search:{ .lg .middle } **Query & Analysis**

    ---

    Raw SQL queries on resources, search by type/region/tags, tag coverage analysis, cross-snapshot history, export to JSON/CSV.

    [:octicons-arrow-right-24: Query guide](guides/query-analysis.md)

-   :material-account-search:{ .lg .middle } **Resource Provenance**

    ---

    CloudTrail creator tracking, `--track-creators` flag, enrich existing snapshots, list creators by snapshot, Web UI creator columns.

    [:octicons-arrow-right-24: Creator tracking guide](guides/creator-tracking.md)

-   :material-code-braces:{ .lg .middle } **IaC Generation**

    ---

    Generate Terraform, CDK TypeScript, or CDK Python. AI-powered code generation with layer-based chunking and automatic validation.

    [:octicons-arrow-right-24: IaC generation guide](guides/iac-generation.md)

-   :material-shield-lock:{ .lg .middle } **Guardrails**

    ---

    Policy-based compliance checking with custom YAML guardrails. Severity levels, BLOCK/AUTO-FIX/WARN actions, AI-powered auto-fix, CI/CD integration.

    [:octicons-arrow-right-24: Guardrails overview](guardrails/index.md)

</div>

---

## Why You Need This

| Problem | Solution |
|---------|----------|
| "What changed in our account?" | Field-level configuration drift detection |
| "Are we following security best practices?" | Automated CIS Benchmark scanning |
| "Someone spun up a bunch of test resources" | Delete everything created after a baseline snapshot |
| "How much is each team spending?" | Per-inventory cost tracking with tag filtering |
| "I need to clean up a sandbox account" | Purge all resources except those with specific tags |

---

## Quick Start

```bash
pip install aws-inventory-manager
awsinv snapshot create my-baseline --regions us-east-1
awsinv snapshot report
```

[:octicons-arrow-right-24: Full installation guide](getting-started/installation.md) | [:octicons-arrow-right-24: First snapshot tutorial](getting-started/first-snapshot.md)
