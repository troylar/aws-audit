# Guardrails

Guardrails are policy rules that validate and auto-fix AWS resources during IaC code generation. They ensure generated code meets your organization's security, compliance, and operational standards.

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
    awsinv generate terraform my-snapshot --guardrails --guardrails-policy policy.yaml
    ```

4. Preview changes with dry-run:

    ```bash
    awsinv generate terraform my-snapshot --guardrails --guardrails-policy policy.yaml --dry-run
    ```

## How It Works

1. **Parse** -- Load your AWS inventory from snapshot or file
2. **Evaluate** -- Check each resource against applicable guardrails
3. **Auto-fix** -- Apply fixes for AUTO-FIX guardrails
4. **Detect conflicts** -- Verify fixes don't violate other guardrails
5. **Generate** -- Create IaC code with fixes applied
6. **Validate** -- Run `terraform validate` / `cdk synth` on output

## Actions

| Action | Behavior |
|--------|----------|
| `BLOCK` | Stop generation if condition fails |
| `AUTO-FIX` | Automatically apply fix and continue |
| `WARN` | Log warning and continue |

## Severity Levels

| Severity | Use Case |
|----------|----------|
| `CRITICAL` | Security vulnerabilities, compliance violations |
| `HIGH` | Best practice violations, missing encryption |
| `MEDIUM` | Suboptimal configurations |
| `LOW` | Minor improvements |
| `INFO` | Informational notices |

## Integrated with IaC Generation

```bash
# Generate with guardrails enabled (uses built-in guardrails)
awsinv generate terraform my-snapshot --guardrails

# Use a custom policy file
awsinv generate terraform my-snapshot --guardrails --guardrails-policy ./policy.yaml

# Strict mode: block on any violation (not just CRITICAL/HIGH)
awsinv generate terraform my-snapshot --guardrails --guardrails-strict

# Environment-specific overrides
awsinv generate terraform my-snapshot --guardrails --guardrails-env production

# Save guardrails report to file
awsinv generate terraform my-snapshot --guardrails --guardrails-report report.json

# Disable AI auto-fix (default: enabled)
awsinv generate terraform my-snapshot --guardrails --no-guardrails-auto-fix
```

## Standalone Commands

```bash
# Check a snapshot without generating IaC
awsinv guardrails check my-snapshot

# Use custom policy and strict mode
awsinv guardrails check my-snapshot --policy ./policy.yaml --strict

# Output as JSON for CI/CD pipelines
awsinv guardrails check my-snapshot --format json

# List available guardrails
awsinv guardrails list
awsinv guardrails list --severity CRITICAL
awsinv guardrails list --category ENC

# Validate a policy file
awsinv guardrails validate ./policy.yaml --verbose

# Generate guardrails from natural language (requires Bedrock)
awsinv guardrails create "S3 buckets must have encryption"
awsinv guardrails generate "production security baseline" --count 10
```

## Custom Policy File Example

```yaml
name: acme-security-policy
version: "1.0"
description: ACME Corp security standards

context:
  APPROVED_VPC: "vpc-12345678"
  REQUIRED_KMS_KEY: "alias/enterprise-key"

context_overrides:
  production:
    APPROVED_VPC: "vpc-prod-abcd"

guardrails:
  - id: ACME-ENC-001
    short_description: S3 buckets must have encryption enabled
    severity: CRITICAL
    action: AUTO-FIX
    applies_to: ["s3:bucket"]
    condition: "Encryption exists"
    auto_fix:
      Encryption:
        SSEAlgorithm: "aws:kms"

  - id: ACME-NET-001
    short_description: EC2 must use approved VPC
    severity: HIGH
    action: BLOCK
    applies_to: ["ec2:instance"]
    condition: "get('VpcId') == env('APPROVED_VPC')"

  - id: ACME-TAG-001
    short_description: Resources must have Owner tag
    severity: HIGH
    action: WARN
    applies_to: ["*"]
    condition: "Tags exists and exists(get('Tags.Owner'))"

  - id: ACME-SEC-001
    short_description: No secrets in Lambda environment
    severity: CRITICAL
    action: BLOCK
    applies_to: ["lambda:function"]
    ai_fail_if: "Lambda environment variables contain hardcoded secrets"
    ai_context: "Check for AWS keys, database passwords, API tokens"

overrides:
  development:
    - guardrail_id: ACME-ENC-001
      severity: MEDIUM
      action: WARN
  production:
    - guardrail_id: ACME-TAG-001
      action: BLOCK
```

## AI Auto-Fix

When a guardrail has `action: AUTO-FIX`, the tool automatically applies the fix configuration:

```yaml
- id: GR-ENC-001
  action: AUTO-FIX
  condition: "Encryption exists"
  auto_fix:
    Encryption:
      SSEAlgorithm: "aws:kms"
      KMSMasterKeyID: "alias/my-key"
```

For AI-powered fixes (complex scenarios), add `ai_context`:

```yaml
- id: GR-SEC-001
  action: AUTO-FIX
  ai_fail_if: "Security group allows SSH from 0.0.0.0/0"
  ai_context: |
    WHY: Open SSH access is a security risk.
    HOW TO FIX: Restrict to specific CIDR blocks or remove the rule.
```

## Conflict Detection

When auto-fixes are applied, the system detects if a fix violates another guardrail:

```
Conflict detected:
  Original: GR-ENC-001 (add encryption)
  Conflicts with: GR-KMS-001 (must use specific KMS key)
```

## Further Reading

- [Policy Reference](policy-reference.md) -- Complete schema for policy files
- [Formula Syntax](formula-syntax.md) -- Expression language for conditions
- [CI/CD Integration](ci-cd-integration.md) -- Using guardrails in pipelines
- Example Policies -- Ready-to-use policy templates in `docs/guardrails/examples/`
