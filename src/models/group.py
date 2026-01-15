"""Resource Group model for baseline comparison across accounts."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class GroupMember:
    """A member of a resource group, identified by name and type.

    Attributes:
        resource_name: Resource name (extracted from ARN or logical ID)
        resource_type: Resource type (e.g., s3:bucket, lambda:function)
        original_arn: Original ARN from source snapshot (reference only)
        match_strategy: How to match this member - 'logical_id' uses CloudFormation
                       logical-id tag for stable matching, 'physical_name' uses name
    """

    resource_name: str
    resource_type: str
    original_arn: Optional[str] = None
    match_strategy: str = "physical_name"  # 'logical_id' or 'physical_name'

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "resource_name": self.resource_name,
            "resource_type": self.resource_type,
            "original_arn": self.original_arn,
            "match_strategy": self.match_strategy,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GroupMember":
        """Deserialize from dictionary."""
        return cls(
            resource_name=data["resource_name"],
            resource_type=data["resource_type"],
            original_arn=data.get("original_arn"),
            match_strategy=data.get("match_strategy", "physical_name"),
        )


@dataclass
class ResourceGroup:
    """A named group of resources for baseline comparison.

    Groups store resources by name + type to enable cross-account comparison
    where ARNs differ (due to account IDs) but resource names are identical.

    Attributes:
        name: Unique group name
        description: Human-readable description
        source_snapshot: Name of snapshot used to create the group
        members: List of group members
        resource_count: Number of resources in the group
        is_favorite: Whether the group is marked as favorite
        created_at: Group creation timestamp
        last_updated: Last modification timestamp
        id: Database ID (set after save)
    """

    name: str
    description: str = ""
    source_snapshot: Optional[str] = None
    members: List[GroupMember] = field(default_factory=list)
    resource_count: int = 0
    is_favorite: bool = False
    created_at: Optional[datetime] = field(default_factory=lambda: datetime.now(timezone.utc))
    last_updated: Optional[datetime] = field(default_factory=lambda: datetime.now(timezone.utc))
    id: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for storage.

        Returns:
            Dictionary representation suitable for storage
        """
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "source_snapshot": self.source_snapshot,
            "members": [m.to_dict() for m in self.members],
            "resource_count": self.resource_count,
            "is_favorite": self.is_favorite,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ResourceGroup":
        """Deserialize from dictionary.

        Args:
            data: Dictionary loaded from storage

        Returns:
            ResourceGroup instance
        """
        # Handle datetime fields
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)

        last_updated = data.get("last_updated")
        if isinstance(last_updated, str):
            last_updated = datetime.fromisoformat(last_updated)

        # Handle members
        members_data = data.get("members", [])
        members = [GroupMember.from_dict(m) for m in members_data]

        return cls(
            id=data.get("id"),
            name=data["name"],
            description=data.get("description", ""),
            source_snapshot=data.get("source_snapshot"),
            members=members,
            resource_count=data.get("resource_count", len(members)),
            is_favorite=data.get("is_favorite", False),
            created_at=created_at,
            last_updated=last_updated,
        )

    def add_member(
        self,
        resource_name: str,
        resource_type: str,
        original_arn: Optional[str] = None,
        match_strategy: str = "physical_name",
    ) -> bool:
        """Add a resource to the group.

        Args:
            resource_name: Resource name (or logical ID if match_strategy is 'logical_id')
            resource_type: Resource type
            original_arn: Optional original ARN
            match_strategy: 'logical_id' for CloudFormation logical IDs, 'physical_name' for names

        Returns:
            True if added, False if already exists
        """
        # Check if already exists
        for member in self.members:
            if member.resource_name == resource_name and member.resource_type == resource_type:
                return False

        self.members.append(GroupMember(resource_name, resource_type, original_arn, match_strategy))
        self.resource_count = len(self.members)
        self.last_updated = datetime.now(timezone.utc)
        return True

    def remove_member(self, resource_name: str, resource_type: str) -> bool:
        """Remove a resource from the group.

        Args:
            resource_name: Resource name
            resource_type: Resource type

        Returns:
            True if removed, False if not found
        """
        for i, member in enumerate(self.members):
            if member.resource_name == resource_name and member.resource_type == resource_type:
                del self.members[i]
                self.resource_count = len(self.members)
                self.last_updated = datetime.now(timezone.utc)
                return True
        return False

    def has_member(self, resource_name: str, resource_type: str) -> bool:
        """Check if a resource is in the group.

        Args:
            resource_name: Resource name
            resource_type: Resource type

        Returns:
            True if resource is in the group
        """
        for member in self.members:
            if member.resource_name == resource_name and member.resource_type == resource_type:
                return True
        return False


def extract_resource_name(arn: str, resource_type: str) -> str:
    """Extract resource name from ARN based on resource type.

    ARN formats vary by service:
    - S3: arn:aws:s3:::bucket-name
    - Lambda: arn:aws:lambda:region:account:function:name
    - IAM: arn:aws:iam::account:role/role-name
    - EC2: arn:aws:ec2:region:account:instance/i-xxxx

    Args:
        arn: AWS ARN string
        resource_type: Resource type (e.g., s3:bucket, iam:role)

    Returns:
        Extracted resource name
    """
    parts = arn.split(":")

    # Handle different ARN formats based on service
    if resource_type.startswith("s3:"):
        # S3: arn:aws:s3:::bucket-name
        return parts[-1]

    elif resource_type.startswith("lambda:"):
        # Lambda: arn:aws:lambda:region:account:function:name
        return parts[-1]

    elif resource_type.startswith("iam:"):
        # IAM: arn:aws:iam::account:role/role-name
        # or arn:aws:iam::account:user/user-name
        # or arn:aws:iam::account:policy/policy-name
        resource_part = parts[-1]
        if "/" in resource_part:
            return resource_part.split("/")[-1]
        return resource_part

    elif resource_type.startswith("dynamodb:"):
        # DynamoDB: arn:aws:dynamodb:region:account:table/table-name
        resource_part = parts[-1]
        if "/" in resource_part:
            return resource_part.split("/")[-1]
        return resource_part

    elif resource_type.startswith("sns:"):
        # SNS: arn:aws:sns:region:account:topic-name
        return parts[-1]

    elif resource_type.startswith("sqs:"):
        # SQS: arn:aws:sqs:region:account:queue-name
        return parts[-1]

    elif resource_type.startswith("ec2:"):
        # EC2: arn:aws:ec2:region:account:instance/i-xxxx
        # or arn:aws:ec2:region:account:vpc/vpc-xxxx
        resource_part = parts[-1]
        if "/" in resource_part:
            return resource_part.split("/")[-1]
        return resource_part

    elif resource_type.startswith("rds:"):
        # RDS: arn:aws:rds:region:account:db:db-instance-name
        # or arn:aws:rds:region:account:cluster:cluster-name
        return parts[-1]

    elif resource_type.startswith("secretsmanager:"):
        # Secrets Manager: arn:aws:secretsmanager:region:account:secret:name-suffix
        return parts[-1].split("-")[0] if "-" in parts[-1] else parts[-1]

    elif resource_type.startswith("kms:"):
        # KMS: arn:aws:kms:region:account:key/key-id
        # or arn:aws:kms:region:account:alias/alias-name
        resource_part = parts[-1]
        if "/" in resource_part:
            return resource_part.split("/")[-1]
        return resource_part

    elif resource_type.startswith("ecs:"):
        # ECS: arn:aws:ecs:region:account:cluster/cluster-name
        # or arn:aws:ecs:region:account:service/cluster-name/service-name
        resource_part = parts[-1]
        if "/" in resource_part:
            return resource_part.split("/")[-1]
        return resource_part

    elif resource_type.startswith("eks:"):
        # EKS: arn:aws:eks:region:account:cluster/cluster-name
        resource_part = parts[-1]
        if "/" in resource_part:
            return resource_part.split("/")[-1]
        return resource_part

    elif resource_type.startswith("cloudwatch:"):
        # CloudWatch: arn:aws:cloudwatch:region:account:alarm:alarm-name
        return parts[-1]

    elif resource_type.startswith("logs:"):
        # CloudWatch Logs: arn:aws:logs:region:account:log-group:group-name
        return parts[-1]

    elif resource_type.startswith("events:"):
        # EventBridge: arn:aws:events:region:account:rule/rule-name
        resource_part = parts[-1]
        if "/" in resource_part:
            return resource_part.split("/")[-1]
        return resource_part

    elif resource_type.startswith("apigateway:"):
        # API Gateway: arn:aws:apigateway:region::/restapis/api-id
        resource_part = parts[-1]
        if "/" in resource_part:
            return resource_part.split("/")[-1]
        return resource_part

    elif resource_type.startswith("elasticache:"):
        # ElastiCache: arn:aws:elasticache:region:account:cluster:cluster-id
        return parts[-1]

    elif resource_type.startswith("ssm:"):
        # SSM Parameter: arn:aws:ssm:region:account:parameter/param-name
        resource_part = parts[-1]
        if "/" in resource_part:
            # Handle hierarchical parameter names like /env/app/key
            return resource_part.replace("parameter/", "").replace("parameter", "")
        return resource_part

    # Default: take last segment after / or :
    resource_part = parts[-1]
    if "/" in resource_part:
        return resource_part.split("/")[-1]
    return resource_part
