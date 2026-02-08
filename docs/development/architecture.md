# Architecture

## System Overview

```
+--------------------------------------------------------------+
|                   AWS Inventory Manager                       |
+--------------------------------------------------------------+
|                                                               |
|  CLI Commands                                                 |
|  +---------+ +-------+ +----------+ +------+ +---------+     |
|  |snapshot | | delta | | security | | cost | | cleanup |     |
|  +----+----+ +---+---+ +----+-----+ +--+---+ +----+----+     |
|       |          |          |          |          |           |
|  +----+----------+----------+----------+----------+----+     |
|  |                     generate                         |     |
|  |        (AI-powered Terraform/CDK generation)        |     |
|  +------------------------------------------------------+     |
|                                                               |
+--------------------------------------------------------------+
|                                                               |
|  Collection Layer                                             |
|  +------------------------+  +----------------------------+  |
|  |     AWS Config API     |  |     Direct Service APIs    |  |
|  |  (auto-detected, fast) |  |  (fallback, 27 collectors) |  |
|  +------------------------+  +----------------------------+  |
|                                                               |
+--------------------------------------------------------------+
|                                                               |
|  Analysis & Generation Engines                                |
|  - Configuration Differ (field-level change detection)       |
|  - Security Scanner (CIS Benchmark checks)                   |
|  - Cost Analyzer (AWS Cost Explorer)                         |
|  - Dependency Resolver (deletion ordering)                   |
|  - IaC Generator (LangGraph + AWS Bedrock)                   |
|                                                               |
+--------------------------------------------------------------+
|                                                               |
|  Storage: ~/.snapshots/                                       |
|  - inventory.db         (SQLite: snapshots, resources, tags) |
|  - audit-logs/**/*.yaml (cleanup operation logs)             |
|                                                               |
+--------------------------------------------------------------+
```

## Module Descriptions

| Module | Description |
|--------|-------------|
| `src/cli/` | Typer CLI commands and option parsing |
| `src/collectors/` | 27 AWS service collectors (EC2, S3, Lambda, etc.) |
| `src/config_service/` | AWS Config integration (detection, collection, mapping) |
| `src/storage/` | SQLite database layer (schema, CRUD, queries) |
| `src/models/` | Data models (Resource, Snapshot, Collection) |
| `src/delta/` | Configuration drift detection |
| `src/security/` | CIS Benchmark security scanner |
| `src/cost/` | AWS Cost Explorer integration |
| `src/cleanup/` | Resource deletion (43 deleters, dependency resolution) |
| `src/generate/` | IaC generation (Terraform, CDK) via LangGraph + Bedrock |
| `src/guardrails/` | Compliance policy evaluation and auto-fix |
| `src/cloudtrail/` | Creator tracking via CloudTrail |
| `src/matching/` | Resource name normalization |
| `src/web/` | FastAPI-based Resource Explorer web UI |
