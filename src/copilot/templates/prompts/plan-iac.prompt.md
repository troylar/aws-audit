---
model: gpt-4.1
optimizations:
  - inventory analysis
  - categorization
constraints:
  task-prompt-tokens: 2000
last-updated: 2026-01-29
---

# Plan IaC Generation from Inventory

Analyze the provided AWS inventory YAML and create a categorized checklist for IaC generation.

## Your Task

1. Parse the inventory YAML (contains raw AWS API responses)
2. Categorize each resource into a layer
3. Count resources per layer
4. Output a structured checklist

## Layer Definitions

| Order | Layer | Resource Types |
|-------|-------|----------------|
| 1 | network | VPC, Subnet, RouteTable, InternetGateway, NatGateway, VPCEndpoint, TransitGateway, VPCPeeringConnection |
| 2 | security | SecurityGroup, NetworkAcl, IAM (Role, Policy, User, Group), KMS Key |
| 3 | data | RDS, DynamoDB, ElastiCache, Redshift, OpenSearch, DocumentDB, Neptune, MemoryDB |
| 4 | storage | S3, EFS, FSx, EBS Volume, Backup |
| 5 | compute | EC2, Lambda, ECS, EKS, Batch, AutoScaling, LaunchTemplate |
| 6 | loadbalancing | ELB, ALB, NLB, TargetGroup, Listener |
| 7 | application | APIGateway, AppSync, CloudFront, Amplify, AppRunner |
| 8 | messaging | SNS, SQS, EventBridge, Kinesis, MSK, MQ |
| 9 | monitoring | CloudWatch (Alarms, LogGroups, Dashboards), CloudTrail, Config |
| 10 | dns | Route53 (HostedZone, RecordSet, HealthCheck) |
| 11 | other | Any resources not fitting above categories |

## Output Format

```markdown
# IaC Generation Plan

## Summary
- Total resources: X
- Layers with resources: Y

## Checklist

### 1. Network Layer (X resources)
- [ ] VPC (count)
- [ ] Subnet (count)
- [ ] RouteTable (count)
...

### 2. Security Layer (X resources)
- [ ] SecurityGroup (count)
- [ ] IAM::Role (count)
...

[Continue for all layers with resources]

## Recommended Order
1. Start with: network (foundation)
2. Then: security (required by compute/data)
3. Then: data, storage (may need security refs)
4. Then: compute (needs network, security)
5. Then: loadbalancing, application
6. Finally: messaging, monitoring, dns

## Notes
- [Any observations about the inventory]
- [Cross-region resources detected]
- [Potential dependency issues]
```

## Instructions

- Use the `type` field (e.g., `AWS::EC2::VPC`) to categorize
- Extract service name from type: `AWS::SERVICE::Resource`
- Group related resources together
- Note any unusual patterns or potential issues
- If a resource type is unknown, put in "other" layer
