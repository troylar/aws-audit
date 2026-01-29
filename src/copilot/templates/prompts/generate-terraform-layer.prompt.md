---
model: gpt-4.1
optimizations:
  - layer-focused generation
  - api-to-terraform mapping
constraints:
  task-prompt-tokens: 3000
last-updated: 2026-01-29
---

# Generate Terraform for Layer

Generate Terraform HCL for resources in the specified layer from the AWS inventory YAML.

## Usage

Specify which layer to generate:
- `network` - VPC, Subnets, Route Tables, Gateways
- `security` - Security Groups, NACLs, IAM
- `data` - RDS, DynamoDB, ElastiCache, etc.
- `storage` - S3, EFS, EBS
- `compute` - EC2, Lambda, ECS, EKS
- `loadbalancing` - ALB, NLB, Target Groups
- `application` - API Gateway, CloudFront
- `messaging` - SNS, SQS, EventBridge
- `monitoring` - CloudWatch, CloudTrail
- `dns` - Route53

## Property Mapping Rules

### 1. Name Translation
```
AWS API (CamelCase)  →  Terraform (snake_case)
─────────────────────────────────────────────
InstanceType         →  instance_type
SubnetId             →  subnet_id
SecurityGroupIds     →  security_group_ids
VpcId                →  vpc_id
CidrBlock            →  cidr_block
AvailabilityZone     →  availability_zone
```

### 2. Computed Properties (OMIT these)
Never include in Terraform - these are read-only/auto-generated:
```
Arn, CreateTime, CreatedDate, LaunchTime, ModifyTime
State, Status, StatusReason
OwnerId, AccountId
PublicIp, PrivateIpAddress (when auto-assigned)
DnsName (for load balancers)
Endpoint (for databases)
*Id when it's the resource's own ID (e.g., VpcId on VPC, InstanceId on Instance)
```

### 3. Configurable Properties (KEEP these)
Include in Terraform - user specifies these:
```
InstanceType, VolumeSize, DesiredCapacity
CidrBlock, Port, Protocol
Name tags, other Tags
Timeouts, Retention periods
Encryption settings
```

### 4. Reference Transformation
Replace hardcoded IDs with Terraform references:
```hcl
# BAD - hardcoded
subnet_id = "subnet-abc123"

# GOOD - reference
subnet_id = aws_subnet.private_a.id
```

Create references using resource names derived from Name tags or logical names.

## Example Transformations

### EC2 Instance

**Raw API Response:**
```yaml
InstanceId: i-0abc123def456
InstanceType: t3.medium
SubnetId: subnet-xyz789
SecurityGroups:
  - GroupId: sg-111222
    GroupName: web-sg
VpcId: vpc-main123
State:
  Name: running
  Code: 16
PublicIpAddress: 54.123.45.67
PrivateIpAddress: 10.0.1.50
LaunchTime: "2024-01-15T10:30:00Z"
Tags:
  - Key: Name
    Value: web-server-1
  - Key: Environment
    Value: production
```

**Terraform Output:**
```hcl
resource "aws_instance" "web_server_1" {
  ami           = "ami-xxxxx"  # Note: AMI often not in raw response, may need lookup
  instance_type = "t3.medium"
  subnet_id     = aws_subnet.private_a.id

  vpc_security_group_ids = [
    aws_security_group.web_sg.id,
  ]

  tags = {
    Name        = "web-server-1"
    Environment = "production"
  }
}
```

### Security Group

**Raw API Response:**
```yaml
GroupId: sg-0abc123
GroupName: web-sg
Description: Web server security group
VpcId: vpc-main123
IpPermissions:
  - IpProtocol: tcp
    FromPort: 443
    ToPort: 443
    IpRanges:
      - CidrIp: 0.0.0.0/0
        Description: HTTPS from anywhere
  - IpProtocol: tcp
    FromPort: 80
    ToPort: 80
    IpRanges:
      - CidrIp: 0.0.0.0/0
IpPermissionsEgress:
  - IpProtocol: "-1"
    IpRanges:
      - CidrIp: 0.0.0.0/0
Tags:
  - Key: Name
    Value: web-sg
```

**Terraform Output:**
```hcl
resource "aws_security_group" "web_sg" {
  name        = "web-sg"
  description = "Web server security group"
  vpc_id      = aws_vpc.main.id

  tags = {
    Name = "web-sg"
  }
}

resource "aws_vpc_security_group_ingress_rule" "web_sg_https" {
  security_group_id = aws_security_group.web_sg.id
  description       = "HTTPS from anywhere"
  from_port         = 443
  to_port           = 443
  ip_protocol       = "tcp"
  cidr_ipv4         = "0.0.0.0/0"
}

resource "aws_vpc_security_group_ingress_rule" "web_sg_http" {
  security_group_id = aws_security_group.web_sg.id
  from_port         = 80
  to_port           = 80
  ip_protocol       = "tcp"
  cidr_ipv4         = "0.0.0.0/0"
}

resource "aws_vpc_security_group_egress_rule" "web_sg_all" {
  security_group_id = aws_security_group.web_sg.id
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"
}
```

### RDS Instance

**Raw API Response:**
```yaml
DBInstanceIdentifier: mydb-production
DBInstanceClass: db.t3.medium
Engine: postgres
EngineVersion: "15.4"
MasterUsername: admin
DBName: myapp
AllocatedStorage: 100
StorageType: gp3
MultiAZ: true
PubliclyAccessible: false
VpcSecurityGroups:
  - VpcSecurityGroupId: sg-db123
DBSubnetGroup:
  DBSubnetGroupName: mydb-subnet-group
Endpoint:
  Address: mydb-production.abc123.us-east-1.rds.amazonaws.com
  Port: 5432
DBInstanceStatus: available
```

**Terraform Output:**
```hcl
resource "aws_db_instance" "mydb_production" {
  identifier     = "mydb-production"
  instance_class = "db.t3.medium"
  engine         = "postgres"
  engine_version = "15.4"

  db_name  = "myapp"
  username = "admin"
  password = var.mydb_production_password  # Never hardcode!

  allocated_storage = 100
  storage_type      = "gp3"

  multi_az               = true
  publicly_accessible    = false
  db_subnet_group_name   = aws_db_subnet_group.mydb_subnet_group.name
  vpc_security_group_ids = [aws_security_group.db.id]

  skip_final_snapshot = false
  final_snapshot_identifier = "mydb-production-final"

  tags = {
    Name = "mydb-production"
  }
}
```

### S3 Bucket

**Raw API Response:**
```yaml
Name: mycompany-data-bucket
CreationDate: "2023-06-15T08:00:00Z"
Versioning:
  Status: Enabled
ServerSideEncryptionConfiguration:
  Rules:
    - ApplyServerSideEncryptionByDefault:
        SSEAlgorithm: aws:kms
        KMSMasterKeyID: arn:aws:kms:us-east-1:123456789:key/abc-123
BucketPolicy: {...}
Tags:
  - Key: Environment
    Value: production
```

**Terraform Output:**
```hcl
resource "aws_s3_bucket" "data" {
  bucket = "mycompany-data-bucket"

  tags = {
    Environment = "production"
  }
}

resource "aws_s3_bucket_versioning" "data" {
  bucket = aws_s3_bucket.data.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "data" {
  bucket = aws_s3_bucket.data.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.main.arn
    }
  }
}
```

## Output Structure

For the specified layer, generate:

```
terraform/
├── {layer}.tf           # Main resources
├── {layer}_variables.tf # Variables for this layer
└── {layer}_outputs.tf   # Outputs for cross-layer references
```

## Cross-Layer References

When referencing resources from other layers:
```hcl
# If VPC was generated in network layer
variable "vpc_id" {
  description = "VPC ID from network layer"
  type        = string
}

# Use the variable
resource "aws_instance" "web" {
  subnet_id = var.subnet_id  # Passed from network layer
}
```

## Important Rules

1. **Generate for ALL resources** in the specified layer from the inventory
2. **Create meaningful resource names** from Name tags or logical identifiers
3. **Use variables** for sensitive values (passwords, keys)
4. **Add `lifecycle { prevent_destroy = true }`** for stateful resources (RDS, S3 with data)
5. **Output IDs** that other layers will need (vpc_id, subnet_ids, security_group_ids)
6. **Preserve all Tags** from the inventory
7. **Skip computed values** - only include what Terraform needs to create the resource
