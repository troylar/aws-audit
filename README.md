<div align="center">

# AWS Inventory Manager

### *Know Everything About Your AWS Environment*

[![CI](https://github.com/troylar/aws-inventory-manager/actions/workflows/test.yml/badge.svg)](https://github.com/troylar/aws-inventory-manager/actions/workflows/test.yml)
[![Coverage](https://codecov.io/gh/troylar/aws-inventory-manager/branch/main/graph/badge.svg)](https://codecov.io/gh/troylar/aws-inventory-manager)
[![PyPI version](https://img.shields.io/pypi/v/aws-inventory-manager.svg)](https://pypi.org/project/aws-inventory-manager/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Inventory Snapshots** | **Configuration Drift** | **Security Scanning** | **Cost Analysis** | **Resource Cleanup** | **IaC Generation**

[Documentation](https://troylar.github.io/aws-inventory-manager/) | [Quick Start](#quick-start) | [Features](#features) | [Contributing](#contributing)

</div>

---

## What It Does

One CLI that inventories **27 AWS services and 80+ resource types**, then lets you track drift, enforce compliance, generate Terraform and CDK, scan for security issues, manage Lambda code, query resources with SQL, and clean up what shouldn't be there. 60+ commands. Zero agents running in your account.

> **Note:** "Snapshot" in this tool means an *inventory snapshot* (a catalog of what exists), not an AWS EBS or RDS snapshot. No AWS snapshots are created.

| Problem | Solution |
|---------|----------|
| "What's actually running in our account?" | Snapshot 80+ resource types across all regions in one command |
| "What changed since last week?" | Field-level configuration drift detection between snapshots |
| "Are we following security best practices?" | 12+ CIS-aligned checks with severity filtering |
| "Someone spun up a bunch of test resources" | Delete everything created after a baseline snapshot |
| "I need Terraform for existing resources" | Generate Terraform or CDK from live inventory with guardrails |
| "What's in that Lambda function?" | Extract, view, and diff deployment packages across snapshots |
| "Are our guardrails being followed?" | YAML-based compliance policies with BLOCK/WARN/AUTO-FIX |
| "I need a resource explorer for the team" | Launch a web UI with `awsinv serve` |

---

## Quick Start

```bash
pip install aws-inventory-manager
```

Or with pipx: `pipx install aws-inventory-manager`

```bash
# 1. Capture current state
awsinv snapshot create my-baseline --regions us-east-1

# 2. View what was captured
awsinv snapshot report

# 3. Track changes
awsinv delta --snapshot my-baseline --show-diff

# 4. Find security issues
awsinv security scan --severity HIGH

# 5. Clean up (always preview first!)
awsinv cleanup preview my-baseline
awsinv cleanup execute my-baseline --confirm
```

> See the full [Getting Started tutorial](https://troylar.github.io/aws-inventory-manager/getting-started/first-snapshot/) for a complete walkthrough.

---

## Features

- **Inventory Snapshots** -- 27 AWS services, 80+ resource types, multi-region, Lambda code collection, SQLite storage ([guide](https://troylar.github.io/aws-inventory-manager/guides/snapshots/))
- **Change Tracking** -- Field-level drift detection with before/after diff ([guide](https://troylar.github.io/aws-inventory-manager/guides/change-tracking/))
- **Security Scanning** -- 12+ CIS-aligned checks across severity levels ([guide](https://troylar.github.io/aws-inventory-manager/guides/security-scanning/))
- **Cost Analysis** -- Per-inventory cost tracking, date ranges, service breakdown ([guide](https://troylar.github.io/aws-inventory-manager/guides/cost-analysis/))
- **Resource Cleanup** -- Baseline cleanup, purge mode, protection rules, 43 deletable types ([guide](https://troylar.github.io/aws-inventory-manager/guides/resource-cleanup/))
- **AWS Config Integration** -- Auto-detected, up to 5x faster collection ([guide](https://troylar.github.io/aws-inventory-manager/configuration/aws-config-integration/))
- **Query & Analysis** -- SQL queries, resource search, cross-snapshot history ([guide](https://troylar.github.io/aws-inventory-manager/guides/query-analysis/))
- **Creator Tracking** -- CloudTrail-based resource provenance ([guide](https://troylar.github.io/aws-inventory-manager/guides/creator-tracking/))
- **IaC Generation** -- Terraform, CDK TypeScript, CDK Python via AI ([guide](https://troylar.github.io/aws-inventory-manager/guides/iac-generation/))
- **Guardrails** -- Policy-based compliance checking, AI auto-fix, CI/CD ready ([guide](https://troylar.github.io/aws-inventory-manager/guardrails/))
- **Web UI** -- Resource Explorer with advanced filtering and export ([guide](https://troylar.github.io/aws-inventory-manager/guides/web-ui/))
- **Lambda Code** -- List, extract, view, diff, and fetch Lambda deployment code ([guide](https://troylar.github.io/aws-inventory-manager/guides/lambda-code/))

---

## Documentation

Full documentation is available at **[troylar.github.io/aws-inventory-manager](https://troylar.github.io/aws-inventory-manager/)**.

| Section | Description |
|---------|-------------|
| [Getting Started](https://troylar.github.io/aws-inventory-manager/getting-started/installation/) | Installation, first snapshot, common workflows |
| [Configuration](https://troylar.github.io/aws-inventory-manager/configuration/environment-variables/) | Environment variables, AWS Config, data storage, multi-account |
| [Guides](https://troylar.github.io/aws-inventory-manager/guides/snapshots/) | How-to guides for every feature |
| [Guardrails](https://troylar.github.io/aws-inventory-manager/guardrails/) | Policy-based compliance checking |
| [Reference](https://troylar.github.io/aws-inventory-manager/reference/cli/) | CLI reference, IAM permissions, supported resources, database schema |
| [Development](https://troylar.github.io/aws-inventory-manager/development/contributing/) | Contributing, testing, architecture |
| [FAQ](https://troylar.github.io/aws-inventory-manager/faq/) | Troubleshooting and frequently asked questions |

---

## Common Workflows

```bash
# Development environment reset
awsinv snapshot create morning-baseline --regions us-east-1
# ... work all day ...
awsinv cleanup execute morning-baseline --confirm

# Pre/post deployment comparison
awsinv snapshot create pre-deploy --regions us-east-1,us-west-2
# ... deploy ...
awsinv delta --snapshot pre-deploy --show-diff

# Sandbox account cleanup
awsinv cleanup purge --protect-tag "baseline=true" --preview
awsinv cleanup purge --protect-tag "baseline=true" --confirm
```

> See [Common Workflows](https://troylar.github.io/aws-inventory-manager/getting-started/common-workflows/) for more examples.

---

## Command Quick Reference

| Command Group | Description |
|--------------|-------------|
| `awsinv snapshot` | Create, list, export, enrich snapshots |
| `awsinv delta` | Track changes since a baseline |
| `awsinv security` | Run CIS-aligned security scans |
| `awsinv cost` | Cost analysis with date ranges |
| `awsinv cleanup` | Delete resources (preview/execute/purge) |
| `awsinv lambda` | Lambda code: list, extract, show, diff, fetch |
| `awsinv query` | SQL queries and resource search |
| `awsinv generate` | Generate Terraform/CDK from snapshots |
| `awsinv guardrails` | Compliance checking and policy management |
| `awsinv serve` | Launch web-based Resource Explorer |

> See the full [CLI Reference](https://troylar.github.io/aws-inventory-manager/reference/cli/) for all options.

---

## Supported Resources

27 AWS services, 80+ resource types. 43 support deletion via cleanup.

> See [Supported Resource Types](https://troylar.github.io/aws-inventory-manager/reference/supported-resources/) for the full list.

---

## Development

```bash
git clone https://github.com/troylar/aws-inventory-manager.git
cd aws-inventory-manager
pip install -e ".[dev]"

invoke test              # All tests with coverage
invoke test-unit         # Unit tests only (faster)
invoke quality           # Lint + typecheck
invoke quality --fix     # Auto-fix issues
invoke build             # Build distributable package
```

2400+ tests, 61% overall coverage.

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Run tests: `invoke test`
4. Run quality checks: `invoke quality`
5. Submit a pull request

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

## License

MIT License - see [LICENSE](LICENSE)

## Support

- **Issues:** [GitHub Issues](https://github.com/troylar/aws-inventory-manager/issues)
- **Discussions:** [GitHub Discussions](https://github.com/troylar/aws-inventory-manager/discussions)

---

<div align="center">

**Built for AWS practitioners who need visibility and control**

[![Star on GitHub](https://img.shields.io/github/stars/troylar/aws-inventory-manager?style=social)](https://github.com/troylar/aws-inventory-manager)

</div>
