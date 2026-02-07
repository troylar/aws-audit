# Supported Resource Types

AWS Inventory Manager supports 80+ resource types across 27 AWS services. 43 of these support deletion via the cleanup command.

## Compute

| Service | Resource Types |
|---------|---------------|
| EC2 | Instances, Volumes, VPCs, Subnets, Security Groups, ENIs, Internet Gateways, NAT Gateways, Route Tables, Key Pairs, Elastic IPs, VPC Endpoints |
| Lambda | Functions (with deployment code), Layers (with code), Event Source Mappings |
| ECS | Clusters, Services, Task Definitions |
| EKS | Clusters, Node Groups, Fargate Profiles |

## Storage

| Service | Resource Types |
|---------|---------------|
| S3 | Buckets (with policies, encryption, versioning config) |
| EBS | Volumes, Snapshots |
| EFS | File Systems, Mount Targets |

## Database

| Service | Resource Types |
|---------|---------------|
| RDS | DB Instances, DB Clusters, DB Subnet Groups |
| DynamoDB | Tables |
| ElastiCache | Clusters, Replication Groups |

## Networking

| Service | Resource Types |
|---------|---------------|
| ELB | Application Load Balancers, Network Load Balancers, Classic Load Balancers, Target Groups |
| Route53 | Hosted Zones, Record Sets |
| API Gateway | REST APIs, HTTP APIs, Stages |

## Security & Identity

| Service | Resource Types |
|---------|---------------|
| IAM | Users, Roles, Groups, Policies, Instance Profiles |
| KMS | Keys, Aliases |
| Secrets Manager | Secrets |
| WAF | WebACLs, Rule Groups, IP Sets |

## Management & Monitoring

| Service | Resource Types |
|---------|---------------|
| CloudWatch | Alarms, Log Groups, Dashboards |
| CloudFormation | Stacks |
| EventBridge | Rules, Event Buses |
| SSM | Parameters |

## Developer Tools

| Service | Resource Types |
|---------|---------------|
| CodePipeline | Pipelines |
| CodeBuild | Projects |
| Step Functions | State Machines |

## Messaging

| Service | Resource Types |
|---------|---------------|
| SNS | Topics, Subscriptions |
| SQS | Queues |

## Backup

| Service | Resource Types |
|---------|---------------|
| AWS Backup | Backup Plans, Backup Vaults |
