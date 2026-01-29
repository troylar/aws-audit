---
model: gpt-4.1
optimizations:
  - token-efficient
  - cdk-typescript best practices
constraints:
  task-prompt-tokens: 2000
last-updated: 2026-01-29
---

# Generate CDK TypeScript from Inventory

Generate AWS CDK TypeScript code from the provided AWS inventory YAML.

## Output Structure

```
cdk/
├── bin/
│   └── app.ts           # CDK app entry point
├── lib/
│   ├── network-stack.ts # VPC, subnets
│   ├── compute-stack.ts # EC2, Lambda, ECS
│   ├── data-stack.ts    # RDS, DynamoDB
│   ├── storage-stack.ts # S3, EFS
│   └── shared/
│       └── props.ts     # Shared interfaces
├── cdk.json
└── package.json
```

## Rules

### L2 Constructs

1. Use L2 constructs where available (prefer over L1/CfnResource)
2. L2 constructs have sensible defaults and type safety

```typescript
// Good: L2 construct
const bucket = new s3.Bucket(this, 'MyBucket', {
  encryption: s3.BucketEncryption.S3_MANAGED,
  versioned: true,
});

// Avoid: L1 construct unless necessary
const cfnBucket = new s3.CfnBucket(this, 'CfnBucket', {...});
```

### Stack Organization

1. Group related resources into logical stacks
2. Keep stacks under 500 resources for deployment performance
3. Use nested stacks for complex applications

```typescript
export class NetworkStack extends cdk.Stack {
  public readonly vpc: ec2.Vpc;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);
    this.vpc = new ec2.Vpc(this, 'MainVpc', {...});
  }
}
```

### Props Interfaces

1. Define props interfaces for stack inputs
2. Export outputs as public readonly properties

```typescript
export interface ComputeStackProps extends cdk.StackProps {
  vpc: ec2.IVpc;
  environment: string;
}
```

### Cross-Stack References

1. Use exported outputs for cross-stack references
2. Pass resources via props, not by import

```typescript
// In app.ts
const network = new NetworkStack(app, 'Network');
const compute = new ComputeStack(app, 'Compute', {
  vpc: network.vpc,
});
```

### CDK Aspects for Tagging

1. Use Aspects for consistent tagging across stacks

```typescript
cdk.Tags.of(app).add('Environment', environment);
cdk.Tags.of(app).add('ManagedBy', 'cdk');
```

### Environment-Agnostic Patterns

1. Avoid hardcoding account/region
2. Use environment-aware constructs

```typescript
new cdk.Stack(this, 'MyStack', {
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION,
  },
});
```

### Sensitive Values

1. Use Secrets Manager or SSM for secrets
2. Never hardcode credentials

```typescript
const secret = secretsmanager.Secret.fromSecretNameV2(
  this, 'DbSecret', 'prod/db/password'
);
```

## Validation

After generation, run:

```bash
npm install
cdk synth
cdk diff
```

## Large Inventories (50+ resources)

Process by stack in order:

1. **Network**: VPC, subnets, route tables
2. **Security**: Security groups, IAM roles
3. **Compute**: EC2, Lambda, ECS
4. **Data**: RDS, DynamoDB, ElastiCache
5. **Storage**: S3, EFS

Request: "Generate NetworkStack from this inventory" or "Continue with ComputeStack."
