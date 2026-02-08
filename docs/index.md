# AWS Inventory Manager

**Know Your AWS Environment. Generate Its Infrastructure as Code.**

[![CI](https://github.com/troylar/aws-inventory-manager/actions/workflows/test.yml/badge.svg)](https://github.com/troylar/aws-inventory-manager/actions/workflows/test.yml)
[![Coverage](https://codecov.io/gh/troylar/aws-inventory-manager/branch/main/graph/badge.svg)](https://codecov.io/gh/troylar/aws-inventory-manager)
[![PyPI version](https://img.shields.io/pypi/v/aws-inventory-manager.svg)](https://pypi.org/project/aws-inventory-manager/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

One CLI that inventories **27 AWS services and 80+ resource types**, then generates
production-ready **Terraform, CDK TypeScript, and CDK Python** from what it finds.
Also: drift detection, security scanning, compliance guardrails, resource cleanup,
Lambda code management, SQL queries, and more. 60+ commands. Zero agents running
in your account.

!!! note
    "Snapshot" in this tool means an *inventory snapshot* (a catalog of what exists), not an AWS EBS or RDS snapshot. No AWS snapshots are created.

=== "Collection"

    ```bash
    awsinv collection create prod-baseline --description "Production account"
    awsinv collection create staging --description "Staging environment"
    awsinv collection list
    awsinv collection show prod-baseline
    ```

=== "Snapshot"

    ```bash
    awsinv snapshot create my-baseline --collection prod-baseline --region us-east-1,us-west-2
    awsinv snapshot report --detailed
    awsinv snapshot export my-baseline -o inventory.yaml --type s3 --tag env=prod
    ```

=== "Generate IaC"

    ```bash
    awsinv generate --snapshot my-baseline --output terraform/
    awsinv generate --snapshot my-baseline --output cdk/ --format cdk-typescript
    awsinv guardrails check --policy security.yaml --strict
    ```

=== "Drift & Security"

    ```bash
    awsinv delta --snapshot my-baseline --show-diff
    awsinv security scan --severity HIGH --output report.json
    ```

=== "Cleanup"

    ```bash
    awsinv cleanup preview my-baseline        # See what would be deleted
    awsinv cleanup execute my-baseline --yes
    awsinv cleanup purge --exclude-tag env=prod --yes
    ```

=== "Explore"

    ```bash
    awsinv query resources --type ec2 --region us-east-1
    awsinv query sql "SELECT resource_type, COUNT(*) FROM resources GROUP BY 1"
    awsinv lambda show my-function --file handler.py
    awsinv serve  # Launch web UI
    ```

---

## Features

<div class="grid cards" markdown>

-   :material-folder-multiple:{ .lg .middle } **Collections**

    ---

    Named containers for organizing snapshots by account, environment, or team. Each collection tracks an active baseline snapshot and supports tag-based filtering.

    [:octicons-arrow-right-24: Collections guide](guides/collections.md)

-   :material-camera:{ .lg .middle } **Inventory Snapshots**

    ---

    Capture everything across 27 services and 80+ resource types. Multi-region, tag filtering, Lambda code collection, creator tracking, YAML/JSON/CSV export.

    [:octicons-arrow-right-24: Snapshots guide](guides/snapshots.md)

-   :material-code-braces:{ .lg .middle } **IaC Generation**

    ---

    Generate Terraform, CDK TypeScript, or CDK Python from live resources. AI-powered, layer-based chunking, automatic validation, guardrails integration.

    [:octicons-arrow-right-24: IaC generation guide](guides/iac-generation.md)

-   :material-shield-lock:{ .lg .middle } **Guardrails & Compliance**

    ---

    Custom YAML policy rules with BLOCK, AUTO-FIX, and WARN actions. AI-powered auto-fix, severity levels, environment overrides, CI/CD exit codes.

    [:octicons-arrow-right-24: Guardrails overview](guardrails/index.md)

-   :material-swap-horizontal:{ .lg .middle } **Change Tracking**

    ---

    Field-level drift detection between any two snapshots. Before/after comparison, color-coded terminal output, JSON export for CI/CD pipelines.

    [:octicons-arrow-right-24: Change tracking guide](guides/change-tracking.md)

-   :material-shield-check:{ .lg .middle } **Security Scanning**

    ---

    12+ CIS-aligned checks: public S3 buckets, open security groups, stale IAM credentials, unencrypted RDS, IMDSv1. Severity filtering and remediation guidance.

    [:octicons-arrow-right-24: Security scanning guide](guides/security-scanning.md)

-   :material-delete-sweep:{ .lg .middle } **Resource Cleanup**

    ---

    Return to a snapshot baseline or purge everything except protected resources. Tag-based exclusions, preview mode, dependency-aware deletion across 43 resource types.

    [:octicons-arrow-right-24: Resource cleanup guide](guides/resource-cleanup.md)

-   :material-lambda:{ .lg .middle } **Lambda Code Management**

    ---

    List, extract, view, and diff Lambda deployment packages across snapshots. Syntax-highlighted code viewer, cross-snapshot comparison, selective fetching.

    [:octicons-arrow-right-24: Lambda code guide](guides/lambda-code.md)

-   :material-currency-usd:{ .lg .middle } **Cost Analysis**

    ---

    Per-collection cost tracking via AWS Cost Explorer. Date range filtering, service-level breakdown, tag-based attribution, forecast data.

    [:octicons-arrow-right-24: Cost analysis guide](guides/cost-analysis.md)

-   :material-database-search:{ .lg .middle } **Query & Analysis**

    ---

    Raw SQL against the resource database, search by type/region/tags/ARN, cross-snapshot history, tag coverage stats, diff between any two snapshots.

    [:octicons-arrow-right-24: Query guide](guides/query-analysis.md)

-   :material-web:{ .lg .middle } **Web UI**

    ---

    Browser-based resource explorer with filtering, sorting, and creator columns. Launch with `awsinv serve` -- no infrastructure required.

    [:octicons-arrow-right-24: Web UI guide](guides/web-ui.md)

-   :material-account-search:{ .lg .middle } **Resource Provenance**

    ---

    Track who created each resource via CloudTrail. Enrich existing snapshots, list creators per snapshot, attribute resources to IAM identities.

    [:octicons-arrow-right-24: Creator tracking guide](guides/creator-tracking.md)

-   :material-cloud-sync:{ .lg .middle } **AWS Config Integration**

    ---

    Automatic detection, up to 5x faster collection, hybrid fallback to direct API, per-resource source tracking, multi-account via Config Aggregators.

    [:octicons-arrow-right-24: AWS Config setup](configuration/aws-config-integration.md)

-   :material-group:{ .lg .middle } **Resource Groups**

    ---

    Define baseline resource groups from snapshots, then compare future snapshots against the baseline. Track coverage, detect extra resources, export definitions.

    [:octicons-arrow-right-24: Query guide](guides/query-analysis.md)

-   :material-github:{ .lg .middle } **GitHub Copilot Integration**

    ---

    Install IaC generation prompts and instructions for Copilot. Pre-built prompt templates for Terraform, CDK TypeScript, and CDK Python generation.

    [:octicons-arrow-right-24: IaC generation guide](guides/iac-generation.md)

</div>

---

## Why You Need This

| Problem | Solution |
|---------|----------|
| "What's actually running in our account?" | Snapshot 80+ resource types across all regions in one command |
| "I need Terraform for existing resources" | Generate Terraform or CDK from live inventory with guardrails |
| "Our generated IaC must meet security standards" | Built-in guardrails auto-fix encryption, tagging, and network policies |
| "What changed since last week?" | Field-level configuration drift detection between snapshots |
| "Are we following security best practices?" | 12+ CIS-aligned checks with severity filtering |
| "Someone spun up a bunch of test resources" | Delete everything created after a baseline snapshot |
| "I need to clean up a sandbox account" | Purge all resources except those matching tag filters |
| "How much is each team spending?" | Per-collection cost tracking with tag-based attribution |
| "What's in that Lambda function?" | Extract, view, and diff deployment packages across snapshots |
| "Are our guardrails being followed?" | YAML-based compliance policies with BLOCK/WARN/AUTO-FIX |
| "I need a resource explorer for the team" | Launch a web UI with `awsinv serve` |

---

## Quick Start

```bash
pip install aws-inventory-manager
awsinv collection create my-project --description "My AWS project"
awsinv snapshot create my-baseline --collection my-project --region us-east-1
awsinv snapshot report --detailed
```

**Turn your inventory into IaC:**

```bash
pip install aws-inventory-manager[generate]
awsinv generate terraform my-baseline --output ./terraform
```

[:octicons-arrow-right-24: Full installation guide](getting-started/installation.md) | [:octicons-arrow-right-24: First snapshot tutorial](getting-started/first-snapshot.md)
