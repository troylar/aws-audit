# AWS Resource Deletion - Quick Reference Table

## Complete Service Matrix

| Service | Resource Type | Deletion Method | Key Prerequisite | Common Error | Delete Order |
|---------|---------------|-----------------|------------------|--------------|--------------|
| **EC2** | Instance | terminate_instances() | Disable termination protection | InvalidInstanceID.InUse | Tier 1 |
| EC2 | Volume | delete_volume() | Not in-use, detached | InvalidVolume.InUse | Tier 1 |
| EC2 | VPC | delete_vpc() | Empty of resources | DependencyViolation | Tier 4 |
| EC2 | Security Group | delete_security_group() | Not in-use | InvalidGroup.InUse | Tier 4 |
| EC2 | Subnet | delete_subnet() | Empty of ENIs | InvalidSubnetID.NotEmpty | Tier 4 |
| EC2 | Network Interface | delete_network_interface() | Detached | InvalidNetworkInterfaceID.InUse | Tier 1 |
| EC2 | Internet Gateway | detach_internet_gateway() + delete_internet_gateway() | Detached from VPC | InvalidInternetGatewayID.NotFound | Tier 4 |
| EC2 | Elastic IP | release_address() | Not associated | InvalidAllocationID.NotFound | Tier 1 |
| **S3** | Bucket | delete_bucket() | Completely empty | BucketNotEmpty | Tier 2 |
| S3 | Object | delete_object() | Must have Key | NoSuchKey | Tier 2 |
| S3 | Multiple Objects | delete_objects() | Batch up to 1000 | SlowDown | Tier 2 |
| **RDS** | DB Instance | delete_db_instance() | Disable DeletionProtection | InvalidDBInstanceState | Tier 2 |
| RDS | DB Cluster | delete_db_cluster() | Delete instances first | InvalidDBClusterStateFault | Tier 2 |
| RDS | DB Snapshot | delete_db_snapshot() | Manual snapshot only | DBSnapshotNotFound | Tier 2 |
| RDS | Parameter Group | delete_db_parameter_group() | Not in-use | InvalidDBParameterGroupState | Tier 5 |
| **Lambda** | Function | delete_function() | Delete event mappings | FunctionNotFound | Tier 1 |
| Lambda | Layer | delete_layer_version() | Version specified | LayerVersionNotFound | Tier 1 |
| Lambda | Event Source Mapping | delete_event_source_mapping() | UUID from list_event_source_mappings | ResourceNotFoundException | Tier 1 (pre-req) |
| Lambda | Alias | delete_alias() | Function name + alias | ResourceNotFoundException | Tier 1 (pre-req) |
| **IAM** | Role | delete_role() | Remove all policies | DeleteConflict | Tier 5 |
| IAM | User | delete_user() | Remove keys, MFA, profile | DeleteConflict | Tier 5 |
| IAM | Group | delete_group() | Remove users | DeleteConflict | Tier 5 |
| IAM | Policy | delete_policy() | Detach from all entities | InvalidInput | Tier 5 |
| IAM | Access Key | delete_access_key() | Specify user + key ID | NoSuchEntity | Tier 5 (pre-req) |
| IAM | MFA Device | deactivate_mfa_device() | Specify user + serial | InvalidInput | Tier 5 (pre-req) |
| **DynamoDB** | Table | delete_table() | Table in ACTIVE state | ResourceInUseException | Tier 2 |
| DynamoDB | Backup | delete_backup() | BackupArn specified | BackupNotFoundException | Tier 2 |
| DynamoDB | Global Table | delete_global_table() | Delete replicas first | ResourceInUseException | Tier 2 |
| **SQS** | Queue | delete_queue() | Queue URL | QueueDoesNotExist | Tier 3 |
| SQS | Message | delete_message() | ReceiptHandle required | ReceiptHandleIsInvalid | Tier 3 |
| SQS | Message Batch | delete_message_batch() | Batch up to 10 | BatchEntryIdsNotDistinct | Tier 3 |
| **SNS** | Topic | delete_topic() | Subscriptions auto-removed | NotFound | Tier 3 |
| SNS | Subscription | unsubscribe() | SubscriptionArn | InvalidParameter | Tier 3 |
| **ECS** | Cluster | delete_cluster() | Delete services first | ClusterContainsServicesFault | Tier 1 |
| ECS | Service | delete_service() | Scale to desiredCount=0 | ServiceNotEmptyFault | Tier 1 (pre-req) |
| ECS | Task Definition | deregister_task_definition() | Specify family:revision | ResourceNotFoundException | Tier 1 |
| **EKS** | Cluster | delete_cluster() | Delete node groups first | ResourceInUseException | Tier 1 |
| EKS | Node Group | delete_nodegroup() | Pods auto-drained | ResourceInUseException | Tier 1 (pre-req) |
| EKS | Addon | delete_addon() | Supported addon | InvalidParameterException | Tier 1 (pre-req) |
| **CloudFormation** | Stack | delete_stack() | In stable state | ValidationError | Tier 5 |
| CloudFormation | Stack Set | delete_stack_set() | Delete instances first | StackSetNotEmpty | Tier 5 |
| **ECR** | Repository | delete_repository() | Empty or force=True | RepositoryNotEmptyException | Tier 1 |
| ECR | Image | batch_delete_image() | Batch up to 100 | ImageNotFound | Tier 1 |
| **CloudWatch** | Log Group | delete_log_group() | Streams auto-removed | ResourceNotFoundException | Tier 5 |
| CloudWatch | Log Stream | delete_log_stream() | In same log group | ResourceNotFoundException | Tier 5 |
| CloudWatch | Alarm | delete_alarms() | Batch multiple | ResourceNotFoundException | Tier 5 |
| CloudWatch | Dashboard | delete_dashboards() | Batch multiple | ResourceNotFoundException | Tier 5 |
| **EventBridge** | Rule | delete_rule() | Remove targets first | ResourceNotFoundException | Tier 3 |
| EventBridge | Event Bus | delete_event_bus() | Custom bus only | ResourceNotFoundException | Tier 3 |
| **Route53** | Hosted Zone | delete_hosted_zone() | Delete non-NS/SOA records | HostedZoneNotEmpty | Tier 4 |
| Route53 | Record Set | change_resource_record_sets(Action=DELETE) | Specify all details | InvalidChangeBatch | Tier 4 |
| Route53 | Health Check | delete_health_check() | Not in-use | HealthCheckInUse | Tier 4 |
| **API Gateway** | REST API | delete_rest_api() | Stages auto-removed | NotFoundException | Tier 3 |
| API Gateway | HTTP/WebSocket API | delete_api() | Stages auto-removed | NotFoundException | Tier 3 |
| API Gateway | Stage | delete_stage() | Not in-use | BadRequestException | Tier 3 |
| **Secrets Manager** | Secret | delete_secret() | Recovery window default 30d | ResourceNotFoundException | Tier 5 |
| **KMS** | Key | schedule_key_deletion() | Min 7d, max 30d window | InvalidKeyId | Tier 5 |
| KMS | Alias | delete_alias() | Must exist | NotFoundException | Tier 5 |
| **VPC Endpoints** | Endpoint | delete_vpc_endpoints() | In available state | InvalidVpcEndpointId.NotFound | Tier 4 |
| **CodeBuild** | Project | delete_project() | Not in-use | ProjectNotFoundException | Tier 1 |
| **CodePipeline** | Pipeline | delete_pipeline() | Any state OK | PipelineNotFoundException | Tier 1 |
| **Step Functions** | State Machine | delete_state_machine() | Executions auto-stopped | InvalidArn | Tier 1 |
| **Backup** | Plan | delete_backup_plan() | No active backups | InvalidParameterException | Tier 2 |
| Backup | Vault | delete_backup_vault() | Must be empty | InvalidParameterException | Tier 2 |
| **WAF** | Web ACL | delete_web_acl() | Get lock token first | InvalidOperationException | Tier 4 |
| **EFS** | File System | delete_file_system() | Delete mount targets first | FileSystemInUse | Tier 2 |
| EFS | Mount Target | delete_mount_target() | In available state | InvalidMountTargetId.NotFound | Tier 2 (pre-req) |
| **ElastiCache** | Cluster | delete_cache_cluster() | Optional final snapshot | InvalidCacheClusterStateFault | Tier 2 |
| ElastiCache | Replication Group | delete_replication_group() | Optional final snapshot | InvalidReplicationGroupState | Tier 2 |
| **SSM** | Parameter | delete_parameter() | Parameter must exist | ParameterNotFound | Tier 5 |

---

## Deletion Tier Summary

### Tier 1: Compute & Application Layer
**Delete First** - Can delete independently
- EC2 Instances, ENIs, Elastic IPs
- Lambda Functions, Layers, Event Mappings
- ECS Clusters, Services, Task Definitions
- EKS Clusters, Node Groups, Addons
- ECR Repositories, Images
- CodeBuild Projects, CodePipeline Pipelines
- Step Functions State Machines

### Tier 2: Data & Storage Layer
**Delete Second** - May need snapshots/backups
- S3 Buckets and Objects
- RDS Instances and Clusters
- DynamoDB Tables
- EFS File Systems
- ElastiCache Clusters
- Backup Plans and Vaults

### Tier 3: Messaging & Events
**Delete Third** - Auto-resolve dependencies
- SQS Queues and Messages
- SNS Topics and Subscriptions
- EventBridge Rules and Event Buses
- API Gateway APIs and Stages

### Tier 4: Networking
**Delete Fourth** - Reverse dependency order
- EC2 VPCs, Subnets, Security Groups
- EC2 Internet Gateways, Route Tables
- VPC Endpoints
- Route53 Hosted Zones and Records
- WAF Web ACLs

### Tier 5: Configuration & Metadata
**Delete Last** - Global impact, extra care needed
- IAM Roles, Users, Groups, Policies
- KMS Keys and Aliases
- CloudFormation Stacks
- CloudWatch Log Groups, Alarms, Dashboards
- Secrets Manager Secrets
- SSM Parameters

---

## Error Code Reference

### Dependency Errors (Recursive Resolution Needed)
| Error Code | Service | Solution |
|-----------|---------|----------|
| InvalidGroup.InUse | EC2 | Find and delete ENI/instance using group |
| InvalidVolume.InUse | EC2 | Detach from instance first |
| BucketNotEmpty | S3 | Delete all objects and delete markers |
| DependencyViolation | EC2 | Delete VPC components in order |
| ClusterContainsServices | ECS | Delete all services first |
| ClusterContainsContainerInstances | ECS | Drain container instances |
| ResourceInUse | Multiple | Find dependent resource, delete it first |
| InvalidDBInstanceState | RDS | Wait for AVAILABLE state |
| HostedZoneNotEmpty | Route53 | Delete all non-NS/SOA records |

### Permission Errors (Check IAM)
| Error Code | Solution |
|-----------|----------|
| UnauthorizedOperation | Check IAM policy for required action |
| AccessDenied | Check resource policy (bucket, KMS key, etc.) |
| NotAuthorized | Check service role permissions |
| AuthFailure.ServiceLinked | Create missing service-linked role |

### State Errors (Wait & Retry)
| Error Code | Service | Solution |
|-----------|---------|----------|
| InvalidDBInstanceState | RDS | Wait for AVAILABLE state, retry |
| InvalidCacheClusterStateFault | ElastiCache | Wait for AVAILABLE state, retry |
| InvalidVpcEndpointState | VPC | Wait for AVAILABLE state, retry |
| ServiceUnavailable | Multiple | Exponential backoff, retry |

### Resource Not Found (Safe to Ignore)
| Error Code | Meaning |
|-----------|---------|
| ResourceNotFoundException | Resource doesn't exist or already deleted |
| NoSuchBucket | S3 bucket doesn't exist |
| DBInstanceNotFound | RDS instance doesn't exist |
| InvalidInstanceID.NotFound | EC2 instance doesn't exist |
| ClusterNotFound | ECS/EKS cluster doesn't exist |

### Rate Limiting (Backoff & Retry)
| Error Code | Solution |
|-----------|----------|
| ThrottlingException | Exponential backoff (1s, 2s, 4s, max 5 retries) |
| RequestThrottled | Exponential backoff |
| SlowDown | Exponential backoff |
| ProvisionedThroughputExceededException | Exponential backoff for DynamoDB |

---

## Pre-Deletion Validation Checklist

- [ ] Resource created after baseline timestamp
- [ ] Resource is not AWS-managed (AWS policy, service-linked role, default VPC)
- [ ] No protection flags enabled (RDS deletion protection, EC2 termination protection)
- [ ] No dependency conflicts (check for related resources)
- [ ] Snapshots/backups created if needed (RDS, ElastiCache, S3)
- [ ] Event mappings deleted before Lambda function
- [ ] Services scaled to 0 before ECS/EKS deletion
- [ ] VPC resources in dependency order
- [ ] IAM policies detached before entity deletion
- [ ] Dry-run completed and user confirmed

---

## Implementation Status

### ✅ Implemented (41 Resource Types)

**Core Compute & Applications:**
- EC2 Instances, Volumes, VPCs, Subnets, Security Groups, ENIs, Internet Gateways, Route Tables, Key Pairs, VPC Endpoints
- Lambda Functions
- ECS Clusters, Services, Task Definitions
- EKS Clusters

**Storage & Data:**
- S3 Buckets (with automatic emptying including versioned objects)
- RDS DB Instances and Clusters
- DynamoDB Tables
- EFS File Systems
- ElastiCache Clusters
- Backup Plans and Vaults (with recovery point cleanup)

**Messaging & Events:**
- SNS Topics
- SQS Queues
- EventBridge Rules (with target cleanup)

**Networking:**
- Route53 Hosted Zones (with record cleanup)
- API Gateway REST APIs
- Load Balancers (Classic and v2)

**Security & Identity:**
- IAM Roles (with policy detachment and instance profile cleanup)
- IAM Users (with full credential cleanup)
- IAM Policies
- KMS Keys (scheduled deletion)
- Secrets Manager Secrets
- WAF Web ACLs and Rule Groups (with disassociation and LockToken handling)

**Developer Tools:**
- CloudFormation Stacks
- CodeBuild Projects
- CodePipeline Pipelines
- Step Functions State Machines

**Monitoring:**
- CloudWatch Alarms
- SSM Parameters

---

## Key Implementation Tips

1. **Always check timestamps**: Verify creation_at is after baseline
2. **Build dependency graph**: Model resource relationships
3. **Implement retry logic**: Handle transient failures gracefully
4. **Use batch operations**: S3, SQS, DynamoDB support batching
5. **Create snapshots**: RDS, ElastiCache before deletion
6. **Log everything**: Audit trail for compliance
7. **Disable protections first**: RDS deletion protection, EC2 termination protection
8. **Test thoroughly**: Always dry-run first
9. **Handle async operations**: Use boto3 waiters
10. **Skip AWS-managed**: Never delete AWS-created resources
