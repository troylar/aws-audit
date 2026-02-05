# Guardrails for IaC Generation

Guardrails are policy rules that validate and auto-fix AWS resources during IaC code generation. They ensure generated Terraform code meets your organization's security, compliance, and operational standards.

## Quick Start

1. Create a policy file (`policy.yaml`):

```yaml
name: my-security-policy
version: "1.0"
guardrails:
  - id: GR-ENC-001
    short_description: S3 bucket encryption required
    severity: HIGH
    action: AUTO-FIX
    applies_to: ["s3:bucket"]
    condition: "Encryption exists"
    auto_fix:
      Encryption:
        SSEAlgorithm: "aws:kms"
```

2. Validate the policy:

```bash
awsinv guardrails validate --policy policy.yaml
```

3. Generate Terraform with guardrails:

```bash
awsinv generate terraform \
  --from-file inventory.yaml \
  --policy policy.yaml \
  --output-dir ./terraform
```

4. Preview changes with dry-run:

```bash
awsinv generate terraform \
  --from-file inventory.yaml \
  --policy policy.yaml \
  --dry-run
```

## How It Works

1. **Parse** - Load your AWS inventory from snapshot or file
2. **Evaluate** - Check each resource against applicable guardrails
3. **Auto-fix** - Apply fixes for AUTO-FIX guardrails
4. **Detect conflicts** - Verify fixes don't violate other guardrails
5. **Generate** - Create Terraform code with fixes applied
6. **Validate** - Run `terraform validate` on output

## Documentation

- [Policy Reference](./policy-reference.md) - Complete schema for policy files
- [Formula Syntax](./formula-syntax.md) - Expression language for conditions
- [Example Policies](./examples/) - Ready-to-use policy templates

## Actions

| Action | Behavior |
|--------|----------|
| `BLOCK` | Stop generation if condition fails |
| `AUTO-FIX` | Automatically apply fix and continue |
| `WARN` | Log warning and continue |

## Severities

| Severity | Use Case |
|----------|----------|
| `CRITICAL` | Security vulnerabilities, compliance violations |
| `HIGH` | Best practice violations, missing encryption |
| `MEDIUM` | Suboptimal configurations |
| `LOW` | Minor improvements |
| `INFO` | Informational notices |
