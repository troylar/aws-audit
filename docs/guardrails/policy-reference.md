# Policy File Reference

Complete schema reference for guardrails policy files.

## Top-Level Structure

```yaml
name: string              # Required - Policy name
version: string           # Required - Policy version (e.g., "1.0")
description: string       # Optional - Policy description
context: object           # Optional - Variables available in formulas
context_overrides: object # Optional - Per-environment variable overrides
guardrails: list          # List of guardrail definitions
overrides: object         # Optional - Per-environment guardrail overrides
```

## Guardrail Definition

```yaml
guardrails:
  - id: string                # Required - Unique ID (format: PREFIX-CATEGORY-NNN)
    short_description: string # Required - Brief description (max 100 chars)
    severity: string          # Required - CRITICAL, HIGH, MEDIUM, LOW, or INFO
    action: string            # Required - BLOCK, AUTO-FIX, or WARN
    applies_to: list          # Required - Resource type patterns

    # Condition (formula string) - mutually exclusive with AI rules
    condition: string         # Formula expression (see formula-syntax.md)

    # OR AI Rules - mutually exclusive with condition
    ai_fail_if: string        # AI evaluates this, fails if true
    ai_warn_if: string        # AI evaluates this, warns if true
    ai_notify_if: string      # AI evaluates this, notifies if true

    # Optional
    long_description: string  # Detailed explanation
    auto_fix: object          # Configuration to apply when fixing
    ai_context: string        # Context for AI when evaluating or fixing
```

## ID Format

Guardrail IDs must match the pattern `PREFIX-CATEGORY-NNN`:

```
GR-ENC-001    # Built-in encryption guardrail
GR-NET-002    # Built-in network guardrail
ACME-SEC-001  # Custom organization guardrail
AWS-CIS-001   # CIS benchmark guardrail
```

## applies_to Patterns

The `applies_to` field accepts resource type patterns:

```yaml
applies_to: ["s3:bucket"]           # Exact match
applies_to: ["s3:*"]                # All S3 resources
applies_to: ["ec2:instance", "rds:instance"]  # Multiple types
applies_to: ["*:*"]                 # All resources (use sparingly)
```

## Context Variables

Define variables that can be referenced in formulas using `env()`:

```yaml
context:
  ACCOUNT_VPC: "vpc-12345678"
  REQUIRED_TAGS:
    - Environment
    - Owner
  KMS_KEY_ARN: "arn:aws:kms:us-east-1:123456789:key/abc"

context_overrides:
  production:
    ACCOUNT_VPC: "vpc-prod-abcd"
    KMS_KEY_ARN: "arn:aws:kms:us-east-1:123456789:key/prod-key"
  staging:
    ACCOUNT_VPC: "vpc-staging-efgh"
```

Use in formulas:

```yaml
condition: "get('VpcId') == env('ACCOUNT_VPC')"
```

## Overrides

Override guardrail settings per environment:

```yaml
overrides:
  development:
    - guardrail_id: GR-ENC-001
      action: WARN              # Downgrade to warning in dev
  production:
    - guardrail_id: GR-LOG-001
      severity: CRITICAL        # Elevate severity in prod
```

## Auto-Fix Configuration

The `auto_fix` field specifies configuration to merge into the resource:

```yaml
auto_fix:
  Encryption:
    SSEAlgorithm: "aws:kms"
    KMSMasterKeyID: "alias/my-key"
```

For nested structures:

```yaml
auto_fix:
  PublicAccessBlock:
    BlockPublicAcls: true
    BlockPublicPolicy: true
    IgnorePublicAcls: true
    RestrictPublicBuckets: true
```

## AI Rules

For complex conditions that require AI evaluation:

```yaml
guardrails:
  - id: GR-SEC-001
    short_description: No hardcoded secrets
    severity: CRITICAL
    action: BLOCK
    applies_to: ["lambda:function", "ecs:task-definition"]
    ai_fail_if: "Resource configuration contains hardcoded credentials or secrets"
    ai_context: |
      Check for:
      - AWS access keys or secret keys
      - Database passwords
      - API tokens
      - Private keys
```

Note: `condition` and AI rules (`ai_fail_if`, `ai_warn_if`, `ai_notify_if`) are mutually exclusive.

## Complete Example

```yaml
name: enterprise-security-policy
version: "2.0"
description: Security guardrails for enterprise AWS accounts

context:
  ACCOUNT_VPC: "vpc-default"
  REQUIRED_KMS_KEY: "alias/enterprise-key"

context_overrides:
  production:
    ACCOUNT_VPC: "vpc-prod-12345"
    REQUIRED_KMS_KEY: "alias/production-key"

guardrails:
  - id: GR-ENC-001
    short_description: S3 encryption required
    severity: HIGH
    action: AUTO-FIX
    applies_to: ["s3:bucket"]
    condition: "Encryption exists"
    auto_fix:
      Encryption:
        SSEAlgorithm: "aws:kms"
    long_description: |
      All S3 buckets must have server-side encryption enabled.
      KMS encryption is preferred for sensitive data.

  - id: GR-NET-001
    short_description: EC2 must use approved VPC
    severity: HIGH
    action: BLOCK
    applies_to: ["ec2:instance"]
    condition: "get('VpcId') == env('ACCOUNT_VPC')"

  - id: GR-SEC-001
    short_description: No secrets in Lambda environment
    severity: CRITICAL
    action: BLOCK
    applies_to: ["lambda:function"]
    ai_fail_if: "Lambda environment variables contain secrets or credentials"
    ai_context: "Check for AWS keys, database passwords, API tokens"

overrides:
  development:
    - guardrail_id: GR-NET-001
      action: WARN
```
