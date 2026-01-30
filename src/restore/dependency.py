"""Dependency graph analysis for resource deletion ordering.

Builds dependency graph from resource metadata and computes deletion order
using Kahn's topological sort algorithm.
"""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Any, List

# Resource type deletion order (delete first → delete last)
# Lower tier = delete first, Higher tier = delete last
# Resources in the same tier can be deleted in any order
RESOURCE_TYPE_DELETION_ORDER = {
    # Tier 1: Application layer (depend on compute/infra)
    "AWS::ECS::Service": 1,
    "AWS::ECS::TaskDefinition": 1,
    "AWS::CodePipeline::Pipeline": 1,
    "AWS::CodeBuild::Project": 1,
    "AWS::StepFunctions::StateMachine": 1,
    "AWS::Events::Rule": 1,
    "AWS::ApiGateway::RestApi": 1,
    "AWS::Lambda::Function": 1,
    # Tier 2: Compute layer (depend on networking)
    "AWS::EC2::Instance": 2,
    "AWS::ECS::Cluster": 2,
    "AWS::EKS::Cluster": 2,
    "AWS::RDS::DBInstance": 2,
    "AWS::RDS::DBCluster": 2,
    "AWS::ElastiCache::CacheCluster": 2,
    "AWS::EFS::FileSystem": 2,
    "AWS::CloudFormation::Stack": 2,
    # Tier 3: Load balancers (depend on networking, target compute)
    "AWS::ElasticLoadBalancing::LoadBalancer": 3,
    "AWS::ElasticLoadBalancingV2::LoadBalancer": 3,
    "AWS::ElasticLoadBalancingV2::TargetGroup": 3,
    # Tier 4: Networking accessories (depend on VPC)
    "AWS::EC2::NatGateway": 4,
    "AWS::EC2::NetworkInterface": 4,
    "AWS::EC2::VPCEndpoint": 4,
    "AWS::EC2::EIP": 4,
    # Tier 5: Security groups (depend on VPC, used by compute)
    "AWS::EC2::SecurityGroup": 5,
    # Tier 6: Subnets and route tables (depend on VPC)
    "AWS::EC2::Subnet": 6,
    "AWS::EC2::RouteTable": 6,
    "AWS::EC2::NetworkAcl": 6,
    # Tier 7: Internet/NAT gateways attachment (depend on VPC)
    "AWS::EC2::InternetGateway": 7,
    # Tier 8: VPCs (root networking infrastructure)
    "AWS::EC2::VPC": 8,
    # Tier 9: Standalone resources (no VPC dependencies)
    "AWS::S3::Bucket": 9,
    "AWS::DynamoDB::Table": 9,
    "AWS::SNS::Topic": 9,
    "AWS::SQS::Queue": 9,
    "AWS::SecretsManager::Secret": 9,
    "AWS::SSM::Parameter": 9,
    "AWS::CloudWatch::Alarm": 9,
    "AWS::CloudWatch::LogGroup": 9,
    "AWS::Route53::HostedZone": 9,
    "AWS::Backup::BackupPlan": 9,
    "AWS::Backup::BackupVault": 9,
    "AWS::WAFv2::WebACL": 9,
    "AWS::WAFv2::RuleGroup": 9,
    "AWS::KMS::Key": 9,
    "AWS::EC2::Volume": 9,
    "AWS::EC2::KeyPair": 9,
    "AWS::Glue::Job": 9,
    "AWS::Glue::Database": 9,
    "AWS::Glue::Crawler": 9,
    # Tier 10: IAM (delete last - may be needed by other resources)
    "AWS::IAM::Role": 10,
    "AWS::IAM::User": 10,
    "AWS::IAM::Policy": 10,
    "AWS::IAM::InstanceProfile": 10,
}

# Default tier for unknown resource types (middle of the order)
DEFAULT_DELETION_TIER = 5


def get_deletion_tier(resource_type: str) -> int:
    """Get the deletion tier for a resource type.

    Args:
        resource_type: AWS resource type (e.g., "AWS::EC2::Instance")

    Returns:
        Deletion tier number (lower = delete first)
    """
    return RESOURCE_TYPE_DELETION_ORDER.get(resource_type, DEFAULT_DELETION_TIER)


def sort_resources_for_deletion(resources: List[Any]) -> List[Any]:
    """Sort resources by deletion order (dependencies first).

    Resources are sorted by their deletion tier, with lower tiers deleted first.
    Within the same tier, resources are sorted by type then name for consistency.

    Args:
        resources: List of resource objects with resource_type attribute

    Returns:
        Sorted list of resources in safe deletion order
    """
    return sorted(
        resources,
        key=lambda r: (
            get_deletion_tier(r.resource_type),
            r.resource_type,
            getattr(r, "name", "") or getattr(r, "arn", ""),
        ),
    )


class DependencyResolver:
    """Dependency resolver for resource deletion ordering.

    Builds dependency graph from resource metadata and computes safe deletion
    order using Kahn's topological sort algorithm. Detects circular dependencies
    and assigns resources to deletion tiers.

    Attributes:
        graph: Dependency graph where graph[child] = [parent1, parent2, ...]
               Children must be deleted before parents
    """

    # Dependency field mappings for common AWS resource types
    DEPENDENCY_FIELDS = {
        "AWS::EC2::Instance": ["VpcId", "SubnetId", "SecurityGroupIds"],
        "AWS::EC2::Subnet": ["VpcId"],
        "AWS::EC2::SecurityGroup": ["VpcId"],
        "AWS::EC2::VPC": [],  # VPCs have no dependencies
        "AWS::RDS::DBInstance": ["DBSubnetGroupName", "VpcSecurityGroupIds"],
        "AWS::Lambda::Function": ["VpcConfig.SubnetIds", "Role"],
        "AWS::ECS::Service": ["Cluster", "LoadBalancers.TargetGroupArn"],
    }

    def __init__(self) -> None:
        """Initialize dependency resolver with empty graph."""
        self.graph: dict[str, list[str]] = {}

    def add_dependency(self, parent: str, child: str) -> None:
        """Add dependency: child must be deleted before parent.

        Args:
            parent: Resource ID that depends on child
            child: Resource ID that parent depends on
        """
        if child not in self.graph:
            self.graph[child] = []

        if parent not in self.graph[child]:
            self.graph[child].append(parent)

        # Ensure parent exists in graph even if it has no dependencies
        if parent not in self.graph:
            self.graph[parent] = []

    def build_graph_from_resources(self, resources: list[dict]) -> None:
        """Build dependency graph from resource metadata.

        Automatically detects dependencies based on resource type and metadata
        fields (VpcId, SubnetId, etc.).

        Args:
            resources: List of resource dictionaries with metadata
        """
        # Build resource ID index
        resource_index = {r["resource_id"]: r for r in resources}

        for resource in resources:
            resource_id = resource["resource_id"]
            resource_type = resource.get("resource_type", "")
            metadata = resource.get("metadata", {})

            # Get dependency fields for this resource type
            dep_fields = self.DEPENDENCY_FIELDS.get(resource_type, [])

            for field in dep_fields:
                # Handle nested fields (e.g., "VpcConfig.SubnetIds")
                field_value = self._get_nested_field(metadata, field)

                if field_value:
                    # Handle list values (e.g., SecurityGroupIds)
                    if isinstance(field_value, list):
                        for dep_id in field_value:
                            if dep_id in resource_index:
                                # resource_id depends on dep_id (parent)
                                # resource_id must be deleted before dep_id
                                self.add_dependency(parent=dep_id, child=resource_id)
                    else:
                        if field_value in resource_index:
                            # resource_id depends on field_value (parent)
                            # resource_id must be deleted before field_value
                            self.add_dependency(parent=field_value, child=resource_id)

    def compute_deletion_order(self, resources: list[str]) -> list[str]:
        """Compute deletion order using Kahn's topological sort algorithm.

        Args:
            resources: List of resource IDs to order

        Returns:
            List of resource IDs in deletion order (children before parents)

        Raises:
            ValueError: If circular dependency detected
        """
        if self.has_cycle():
            raise ValueError("Circular dependency detected - cannot compute deletion order")

        # Build in-degree map (number of dependencies each resource has)
        in_degree = {resource: 0 for resource in resources}

        for resource in resources:
            if resource in self.graph:
                # Count how many parents depend on this resource
                for parent in self.graph[resource]:
                    if parent in in_degree:
                        in_degree[parent] += 1

        # Start with resources that have no dependencies (in-degree = 0)
        queue = deque([resource for resource, degree in in_degree.items() if degree == 0])
        result = []

        while queue:
            # Remove resource with no dependencies
            current = queue.popleft()
            result.append(current)

            # Reduce in-degree for all parents of this resource
            if current in self.graph:
                for parent in self.graph[current]:
                    if parent in in_degree:
                        in_degree[parent] -= 1

                        # If parent now has no dependencies, add to queue
                        if in_degree[parent] == 0:
                            queue.append(parent)

        # If result doesn't contain all resources, there's a cycle
        if len(result) != len(resources):
            raise ValueError("Circular dependency detected - some resources not reachable")

        return result

    def has_cycle(self) -> bool:
        """Detect if dependency graph contains cycles.

        Returns:
            True if circular dependency exists, False otherwise
        """
        # Use DFS with color marking (white, gray, black)
        white = 0  # Unvisited
        gray = 1  # Visiting
        black = 2  # Visited

        color = {node: white for node in self.graph}

        def dfs(node: str) -> bool:
            """DFS visit that returns True if cycle found."""
            if color.get(node, white) == gray:
                # Back edge found - cycle exists
                return True

            if color.get(node, white) == black:
                # Already visited
                return False

            # Mark as visiting
            color[node] = gray

            # Visit all parents
            for parent in self.graph.get(node, []):
                if dfs(parent):
                    return True

            # Mark as visited
            color[node] = black
            return False

        # Check all nodes
        for node in self.graph:
            if color[node] == white:
                if dfs(node):
                    return True

        return False

    def get_deletion_tiers(self, resources: list[str]) -> dict[int, list[str]]:
        """Assign resources to deletion tiers based on dependency depth.

        Tier 1: Resources with no dependencies (delete first)
        Tier 2: Resources depending only on tier 1
        Tier 3: Resources depending on tier 2, etc.

        Args:
            resources: List of resource IDs

        Returns:
            Dictionary mapping tier number to list of resource IDs
        """
        # Build tier assignment based on dependency depth
        tiers: dict[int, list[str]] = defaultdict(list)
        resource_tier: dict[str, int] = {}

        # Build in-degree map
        in_degree = {resource: 0 for resource in resources}
        for resource in resources:
            if resource in self.graph:
                for parent in self.graph[resource]:
                    if parent in in_degree:
                        in_degree[parent] += 1

        # Start with tier 1 (resources with no dependencies)
        queue = deque([(resource, 1) for resource, degree in in_degree.items() if degree == 0])

        while queue:
            current, tier = queue.popleft()
            tiers[tier].append(current)
            resource_tier[current] = tier

            # Process children (resources that depend on current)
            if current in self.graph:
                for parent in self.graph[current]:
                    if parent in in_degree:
                        in_degree[parent] -= 1

                        if in_degree[parent] == 0:
                            # Parent goes in next tier
                            queue.append((parent, tier + 1))

        return dict(tiers)

    def _get_nested_field(self, metadata: dict, field_path: str) -> Any:
        """Get nested field value from metadata.

        Args:
            metadata: Resource metadata dictionary
            field_path: Field path (e.g., "VpcConfig.SubnetIds")

        Returns:
            Field value if found, None otherwise
        """
        parts = field_path.split(".")
        value: Any = metadata

        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
                if value is None:
                    return None
            else:
                return None

        return value
