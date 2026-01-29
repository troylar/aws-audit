---
model: gpt-4.1
optimizations:
  - token-efficient
  - cdk-python best practices
constraints:
  task-prompt-tokens: 2000
last-updated: 2026-01-29
---

# Generate CDK Python from Inventory

Generate AWS CDK Python code from the provided AWS inventory YAML.

## Output Structure

```
cdk/
├── app.py               # CDK app entry point
├── stacks/
│   ├── __init__.py
│   ├── network_stack.py # VPC, subnets
│   ├── compute_stack.py # EC2, Lambda, ECS
│   ├── data_stack.py    # RDS, DynamoDB
│   └── storage_stack.py # S3, EFS
├── cdk.json
└── requirements.txt
```

## Rules

### L2 Constructs

1. Use L2 constructs where available (prefer over L1/CfnResource)
2. L2 constructs have sensible defaults and type safety

```python
# Good: L2 construct
bucket = s3.Bucket(
    self, "MyBucket",
    encryption=s3.BucketEncryption.S3_MANAGED,
    versioned=True,
)

# Avoid: L1 construct unless necessary
cfn_bucket = s3.CfnBucket(self, "CfnBucket", ...)
```

### Type Hints

1. Use type hints throughout
2. Import types for better IDE support

```python
from aws_cdk import Stack
from constructs import Construct
from aws_cdk import aws_ec2 as ec2

class NetworkStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        self.vpc: ec2.Vpc = ec2.Vpc(self, "MainVpc", ...)
```

### Stack Organization

1. Group related resources into logical stacks
2. Keep stacks under 500 resources
3. Use nested stacks for complex applications

```python
class NetworkStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)
        self.vpc = ec2.Vpc(self, "MainVpc", ...)
```

### Props via Kwargs/Dataclasses

1. Use kwargs or dataclasses for stack inputs
2. Export outputs as instance attributes

```python
from dataclasses import dataclass

@dataclass
class ComputeStackProps:
    vpc: ec2.IVpc
    environment: str
```

### Cross-Stack References

1. Use exported outputs for cross-stack references
2. Pass resources via constructor, not by import

```python
# In app.py
network = NetworkStack(app, "Network")
compute = ComputeStack(app, "Compute", vpc=network.vpc)
```

### CDK Aspects for Tagging

1. Use Tags for consistent tagging across stacks

```python
Tags.of(app).add("Environment", environment)
Tags.of(app).add("ManagedBy", "cdk")
```

### Environment-Agnostic Patterns

1. Avoid hardcoding account/region
2. Use environment-aware constructs

```python
import os

Stack(
    self, "MyStack",
    env=Environment(
        account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
        region=os.environ.get("CDK_DEFAULT_REGION"),
    ),
)
```

### Sensitive Values

1. Use Secrets Manager or SSM for secrets
2. Never hardcode credentials

```python
secret = secretsmanager.Secret.from_secret_name_v2(
    self, "DbSecret", "prod/db/password"
)
```

## Validation

After generation, run:

```bash
pip install -r requirements.txt
cdk synth
cdk diff
```

## Important: Generate ALL Resource Types

**Generate CDK constructs for EVERY resource in the inventory**, regardless of service type. Do not skip any resources. The inventory may contain any AWS service - generate appropriate CDK constructs for all of them.

Map the `type` field (e.g., `AWS::EC2::Instance`, `AWS::Lambda::Function`, `AWS::RDS::DBInstance`) to the corresponding CDK L2 construct (e.g., `ec2.Instance`, `lambda_.Function`, `rds.DatabaseInstance`). Use L1 constructs only when no L2 exists.

Organize resources into logical stacks by service category (network, compute, data, etc.).

## Large Inventories (50+ resources)

Only batch if the user explicitly requests it. Otherwise, generate all resources in a single pass.
