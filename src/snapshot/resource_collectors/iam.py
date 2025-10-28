"""IAM resource collector."""

from typing import List

from ...models.resource import Resource
from ...utils.hash import compute_config_hash
from .base import BaseResourceCollector


class IAMCollector(BaseResourceCollector):
    """Collector for AWS IAM resources (roles, users, groups, policies)."""

    @property
    def service_name(self) -> str:
        return "iam"

    @property
    def is_global_service(self) -> bool:
        return True

    def collect(self) -> List[Resource]:
        """Collect IAM resources.

        Returns:
            List of IAM resources (roles, users, groups, policies)
        """
        resources = []
        account_id = self._get_account_id()

        # Collect roles
        resources.extend(self._collect_roles(account_id))

        # Collect users
        resources.extend(self._collect_users(account_id))

        # Collect groups
        resources.extend(self._collect_groups(account_id))

        # Collect policies (customer-managed only)
        resources.extend(self._collect_policies(account_id))

        self.logger.debug(f"Collected {len(resources)} IAM resources")
        return resources

    def _collect_roles(self, account_id: str) -> List[Resource]:
        """Collect IAM roles."""
        resources = []
        client = self._create_client()

        try:
            paginator = client.get_paginator("list_roles")
            for page in paginator.paginate():
                for role in page["Roles"]:
                    # Build ARN
                    arn = role["Arn"]

                    # Extract tags
                    tags = {}
                    try:
                        tag_response = client.list_role_tags(RoleName=role["RoleName"])
                        tags = {tag["Key"]: tag["Value"] for tag in tag_response.get("Tags", [])}
                    except Exception as e:
                        self.logger.debug(f"Could not get tags for role {role['RoleName']}: {e}")

                    # Create resource
                    resource = Resource(
                        arn=arn,
                        resource_type="AWS::IAM::Role",
                        name=role["RoleName"],
                        region="global",
                        tags=tags,
                        config_hash=compute_config_hash(role),
                        created_at=role.get("CreateDate"),
                        raw_config=role,
                    )
                    resources.append(resource)

        except Exception as e:
            self.logger.error(f"Error collecting IAM roles: {e}")

        return resources

    def _collect_users(self, account_id: str) -> List[Resource]:
        """Collect IAM users."""
        resources = []
        client = self._create_client()

        try:
            paginator = client.get_paginator("list_users")
            for page in paginator.paginate():
                for user in page["Users"]:
                    # Build ARN
                    arn = user["Arn"]

                    # Extract tags
                    tags = {}
                    try:
                        tag_response = client.list_user_tags(UserName=user["UserName"])
                        tags = {tag["Key"]: tag["Value"] for tag in tag_response.get("Tags", [])}
                    except Exception as e:
                        self.logger.debug(f"Could not get tags for user {user['UserName']}: {e}")

                    # Create resource
                    resource = Resource(
                        arn=arn,
                        resource_type="AWS::IAM::User",
                        name=user["UserName"],
                        region="global",
                        tags=tags,
                        config_hash=compute_config_hash(user),
                        created_at=user.get("CreateDate"),
                        raw_config=user,
                    )
                    resources.append(resource)

        except Exception as e:
            self.logger.error(f"Error collecting IAM users: {e}")

        return resources

    def _collect_groups(self, account_id: str) -> List[Resource]:
        """Collect IAM groups."""
        resources = []
        client = self._create_client()

        try:
            paginator = client.get_paginator("list_groups")
            for page in paginator.paginate():
                for group in page["Groups"]:
                    # Build ARN
                    arn = group["Arn"]

                    # Create resource (groups don't support tags)
                    resource = Resource(
                        arn=arn,
                        resource_type="AWS::IAM::Group",
                        name=group["GroupName"],
                        region="global",
                        tags={},
                        config_hash=compute_config_hash(group),
                        created_at=group.get("CreateDate"),
                        raw_config=group,
                    )
                    resources.append(resource)

        except Exception as e:
            self.logger.error(f"Error collecting IAM groups: {e}")

        return resources

    def _collect_policies(self, account_id: str) -> List[Resource]:
        """Collect customer-managed IAM policies."""
        resources = []
        client = self._create_client()

        try:
            paginator = client.get_paginator("list_policies")
            # Only get customer-managed policies (not AWS-managed)
            for page in paginator.paginate(Scope="Local"):
                for policy in page["Policies"]:
                    # Build ARN
                    arn = policy["Arn"]

                    # Extract tags
                    tags = {}
                    try:
                        tag_response = client.list_policy_tags(PolicyArn=arn)
                        tags = {tag["Key"]: tag["Value"] for tag in tag_response.get("Tags", [])}
                    except Exception as e:
                        self.logger.debug(f"Could not get tags for policy {policy['PolicyName']}: {e}")

                    # Create resource
                    resource = Resource(
                        arn=arn,
                        resource_type="AWS::IAM::Policy",
                        name=policy["PolicyName"],
                        region="global",
                        tags=tags,
                        config_hash=compute_config_hash(policy),
                        created_at=policy.get("CreateDate"),
                        raw_config=policy,
                    )
                    resources.append(resource)

        except Exception as e:
            self.logger.error(f"Error collecting IAM policies: {e}")

        return resources
