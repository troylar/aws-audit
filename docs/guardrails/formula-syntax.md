# Formula Syntax Reference

Formulas are expressions used in guardrail conditions. They are evaluated against resource configurations to determine compliance.

## Basic Syntax

Formulas use a simple expression language powered by [simpleeval](https://github.com/danthedeckie/simpleeval).

### Check if attribute exists

```yaml
condition: "Encryption exists"
condition: "PublicAccessBlock exists"
condition: "Tags exists"
```

### Check if attribute is missing

```yaml
condition: "PublicIp not exists"
condition: "Encryption not exists"
```

### Compare values

```yaml
condition: "get('InstanceType') == 't3.micro'"
condition: "get('Engine') in ['mysql', 'postgres']"
condition: "get('AllocatedStorage') >= 100"
```

## Functions

### get(path)

Retrieve a value from the resource configuration. Returns `None` if not found.

```yaml
# Simple attribute
condition: "get('InstanceType') == 't3.large'"

# Nested attribute (dot notation)
condition: "get('Encryption.SSEAlgorithm') == 'aws:kms'"

# Default value if missing
condition: "get('MultiAZ', False) == True"
```

### exists(attribute)

Check if an attribute exists and is not None.

```yaml
condition: "exists('Encryption')"
condition: "exists('Tags.Environment')"
```

### env(key)

Get a value from policy context or OS environment variables.

```yaml
# From policy context
condition: "get('VpcId') == env('ACCOUNT_VPC')"

# From OS environment
condition: "get('Region') == env('AWS_REGION')"

# With default value
condition: "get('KmsKeyId') == env('KMS_KEY', 'alias/default')"
```

## Operators

### Comparison

| Operator | Description | Example |
|----------|-------------|---------|
| `==` | Equal | `get('Engine') == 'mysql'` |
| `!=` | Not equal | `get('Status') != 'stopped'` |
| `>` | Greater than | `get('Size') > 100` |
| `>=` | Greater or equal | `get('IOPS') >= 3000` |
| `<` | Less than | `get('Age') < 30` |
| `<=` | Less or equal | `get('Replicas') <= 5` |

### Logical

| Operator | Description | Example |
|----------|-------------|---------|
| `and` | Both true | `Encryption exists and get('Encryption.SSEAlgorithm') == 'aws:kms'` |
| `or` | Either true | `get('MultiAZ') == True or get('Engine') == 'aurora'` |
| `not` | Negation | `not get('PubliclyAccessible')` |

### Membership

| Operator | Description | Example |
|----------|-------------|---------|
| `in` | Value in list | `get('InstanceType') in ['t3.micro', 't3.small']` |
| `not in` | Value not in list | `get('Engine') not in ['mysql5.6', 'postgres9.6']` |

## Shorthand Syntax

For common patterns, use the simplified syntax:

| Shorthand | Equivalent |
|-----------|------------|
| `Attribute exists` | `exists(get('Attribute'))` |
| `Attribute not exists` | `not exists(get('Attribute'))` |

```yaml
# These are equivalent:
condition: "Encryption exists"
condition: "exists(get('Encryption'))"
```

**Note:** The shorthand only works for simple attribute names. For nested paths with `get()`, use the function form:

```yaml
# CORRECT - use exists() function with get()
condition: "exists(get('VpcConfig.VpcId'))"

# INCORRECT - shorthand doesn't work after get()
condition: "get('VpcConfig.VpcId') exists"  # Syntax error!
```

## Complex Examples

### Multiple conditions

```yaml
condition: "Encryption exists and get('Encryption.SSEAlgorithm') == 'aws:kms'"
```

### Nested attribute checks

```yaml
condition: "get('PublicAccessBlock.BlockPublicAcls') == True and get('PublicAccessBlock.BlockPublicPolicy') == True"
```

### Environment-specific rules

```yaml
condition: "get('VpcId') == env('ACCOUNT_VPC') or env('ALLOW_DEFAULT_VPC') == 'true'"
```

### Tag validation

```yaml
condition: "Tags exists and get('Tags.Environment') in ['dev', 'staging', 'prod']"
```

### Size constraints

```yaml
condition: "get('AllocatedStorage') >= 100 and get('AllocatedStorage') <= 1000"
```

## Common Patterns

### Require encryption

```yaml
condition: "Encryption exists"
```

### Block public access

```yaml
condition: "PublicIp not exists"
condition: "get('PubliclyAccessible') == False"
```

### Require specific VPC

```yaml
condition: "get('VpcId') == env('REQUIRED_VPC')"
```

### Require tags

```yaml
condition: "Tags exists and get('Tags.Owner') exists and get('Tags.Environment') exists"
```

### Instance type restrictions

```yaml
condition: "get('InstanceType') in env('ALLOWED_INSTANCE_TYPES')"
```

## Validation Errors

When a formula is invalid, you'll see errors like:

| Error | Cause | Fix |
|-------|-------|-----|
| `Unknown function 'foo'` | Using undefined function | Use `get`, `exists`, or `env` |
| `Syntax error at position X` | Invalid expression syntax | Check quotes and parentheses |
| `Name 'x' is not defined` | Unquoted string | Use quotes: `'x'` |

Run `awsinv guardrails validate --policy your-policy.yaml` to check for formula errors.
