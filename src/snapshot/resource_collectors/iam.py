"""IAM resource collector."""

from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List

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

        self._report_progress("roles")
        resources.extend(self._collect_roles(account_id))

        self._report_progress("users")
        resources.extend(self._collect_users(account_id))

        self._report_progress("groups")
        resources.extend(self._collect_groups(account_id))

        self._report_progress("policies")
        resources.extend(self._collect_policies(account_id))

        self.logger.debug(f"Collected {len(resources)} IAM resources")
        return resources

    def _collect_roles(self, account_id: str) -> List[Resource]:
        """Collect IAM roles."""
        client = self._create_client()

        try:
            # First collect all role metadata
            roles = []
            paginator = client.get_paginator("list_roles")
            for page in paginator.paginate():
                roles.extend(page["Roles"])

            if not roles:
                return []

            # Fetch tags in parallel
            def _enrich_role(role: Dict) -> Resource:
                tags = {}
                try:
                    tag_response = client.list_role_tags(RoleName=role["RoleName"])
                    tags = {tag["Key"]: tag["Value"] for tag in tag_response.get("Tags", [])}
                except Exception as e:
                    self.logger.debug(f"Could not get tags for role {role['RoleName']}: {e}")

                return Resource(
                    arn=role["Arn"],
                    resource_type="AWS::IAM::Role",
                    name=role["RoleName"],
                    region="global",
                    tags=tags,
                    config_hash=compute_config_hash(role),
                    created_at=role.get("CreateDate"),
                    raw_config=role,
                )

            resources: List[Resource] = []
            with ThreadPoolExecutor(max_workers=min(10, len(roles))) as executor:
                for resource in executor.map(_enrich_role, roles):
                    resources.append(resource)

            return resources

        except Exception as e:
            self.logger.error(f"Error collecting IAM roles: {e}")
            return []

    def _collect_users(self, account_id: str) -> List[Resource]:
        """Collect IAM users."""
        client = self._create_client()

        try:
            users = []
            paginator = client.get_paginator("list_users")
            for page in paginator.paginate():
                users.extend(page["Users"])

            if not users:
                return []

            def _enrich_user(user: Dict) -> Resource:
                tags = {}
                try:
                    tag_response = client.list_user_tags(UserName=user["UserName"])
                    tags = {tag["Key"]: tag["Value"] for tag in tag_response.get("Tags", [])}
                except Exception as e:
                    self.logger.debug(f"Could not get tags for user {user['UserName']}: {e}")

                return Resource(
                    arn=user["Arn"],
                    resource_type="AWS::IAM::User",
                    name=user["UserName"],
                    region="global",
                    tags=tags,
                    config_hash=compute_config_hash(user),
                    created_at=user.get("CreateDate"),
                    raw_config=user,
                )

            resources: List[Resource] = []
            with ThreadPoolExecutor(max_workers=min(10, len(users))) as executor:
                for resource in executor.map(_enrich_user, users):
                    resources.append(resource)

            return resources

        except Exception as e:
            self.logger.error(f"Error collecting IAM users: {e}")
            return []

    def _collect_groups(self, account_id: str) -> List[Resource]:
        """Collect IAM groups."""
        resources = []
        client = self._create_client()

        try:
            paginator = client.get_paginator("list_groups")
            for page in paginator.paginate():
                for group in page["Groups"]:
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
        client = self._create_client()

        try:
            policies = []
            paginator = client.get_paginator("list_policies")
            for page in paginator.paginate(Scope="Local"):
                policies.extend(page["Policies"])

            if not policies:
                return []

            def _enrich_policy(policy: Dict) -> Resource:
                arn = policy["Arn"]

                tags = {}
                try:
                    tag_response = client.list_policy_tags(PolicyArn=arn)
                    tags = {tag["Key"]: tag["Value"] for tag in tag_response.get("Tags", [])}
                except Exception as e:
                    self.logger.debug(f"Could not get tags for policy {policy['PolicyName']}: {e}")

                policy_document = None
                default_version_id = policy.get("DefaultVersionId")
                if default_version_id:
                    try:
                        version_response = client.get_policy_version(PolicyArn=arn, VersionId=default_version_id)
                        policy_document = version_response.get("PolicyVersion", {}).get("Document")
                    except Exception as e:
                        self.logger.debug(f"Could not get policy document for {policy['PolicyName']}: {e}")

                policy_config = dict(policy)
                if policy_document:
                    policy_config["PolicyDocument"] = policy_document

                return Resource(
                    arn=arn,
                    resource_type="AWS::IAM::Policy",
                    name=policy["PolicyName"],
                    region="global",
                    tags=tags,
                    config_hash=compute_config_hash(policy_config),
                    created_at=policy.get("CreateDate"),
                    raw_config=policy_config,
                )

            resources: List[Resource] = []
            with ThreadPoolExecutor(max_workers=min(10, len(policies))) as executor:
                for resource in executor.map(_enrich_policy, policies):
                    resources.append(resource)

            return resources

        except Exception as e:
            self.logger.error(f"Error collecting IAM policies: {e}")
            return []
