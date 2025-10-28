"""AWS Backup resource collector."""

from typing import List

from ...models.resource import Resource
from ...utils.hash import compute_config_hash
from .base import BaseResourceCollector


class BackupCollector(BaseResourceCollector):
    """Collector for AWS Backup resources."""

    @property
    def service_name(self) -> str:
        return "backup"

    def collect(self) -> List[Resource]:
        """Collect AWS Backup resources.

        Collects:
        - Backup Plans
        - Backup Vaults

        Returns:
            List of AWS Backup resources
        """
        resources = []

        # Collect Backup Plans
        resources.extend(self._collect_backup_plans())

        # Collect Backup Vaults
        resources.extend(self._collect_backup_vaults())

        self.logger.debug(f"Collected {len(resources)} AWS Backup resources in {self.region}")
        return resources

    def _collect_backup_plans(self) -> List[Resource]:
        """Collect Backup Plans.

        Returns:
            List of Backup Plan resources
        """
        resources = []
        client = self._create_client()

        try:
            paginator = client.get_paginator("list_backup_plans")
            for page in paginator.paginate():
                for plan_summary in page.get("BackupPlansList", []):
                    plan_id = plan_summary["BackupPlanId"]
                    plan_name = plan_summary["BackupPlanName"]
                    plan_arn = plan_summary["BackupPlanArn"]

                    try:
                        # Get detailed plan info
                        plan_response = client.get_backup_plan(BackupPlanId=plan_id)
                        plan = plan_response.get("BackupPlan", {})

                        # Get tags
                        tags = {}
                        try:
                            tag_response = client.list_tags(ResourceArn=plan_arn)
                            tags = tag_response.get("Tags", {})
                        except Exception as e:
                            self.logger.debug(f"Could not get tags for backup plan {plan_name}: {e}")

                        # Extract creation date
                        created_at = plan_summary.get("CreationDate")

                        # Create resource
                        resource = Resource(
                            arn=plan_arn,
                            resource_type="AWS::Backup::BackupPlan",
                            name=plan_name,
                            region=self.region,
                            tags=tags,
                            config_hash=compute_config_hash(plan),
                            created_at=created_at,
                            raw_config=plan,
                        )
                        resources.append(resource)

                    except Exception as e:
                        self.logger.debug(f"Error processing backup plan {plan_name}: {e}")
                        continue

        except Exception as e:
            self.logger.error(f"Error collecting Backup Plans in {self.region}: {e}")

        return resources

    def _collect_backup_vaults(self) -> List[Resource]:
        """Collect Backup Vaults.

        Returns:
            List of Backup Vault resources
        """
        resources = []
        client = self._create_client()

        try:
            paginator = client.get_paginator("list_backup_vaults")
            for page in paginator.paginate():
                for vault in page.get("BackupVaultList", []):
                    vault_name = vault["BackupVaultName"]
                    vault_arn = vault["BackupVaultArn"]

                    # Get tags
                    tags = {}
                    try:
                        tag_response = client.list_tags(ResourceArn=vault_arn)
                        tags = tag_response.get("Tags", {})
                    except Exception as e:
                        self.logger.debug(f"Could not get tags for backup vault {vault_name}: {e}")

                    # Extract creation date
                    created_at = vault.get("CreationDate")

                    # Create resource
                    resource = Resource(
                        arn=vault_arn,
                        resource_type="AWS::Backup::BackupVault",
                        name=vault_name,
                        region=self.region,
                        tags=tags,
                        config_hash=compute_config_hash(vault),
                        created_at=created_at,
                        raw_config=vault,
                    )
                    resources.append(resource)

        except Exception as e:
            self.logger.error(f"Error collecting Backup Vaults in {self.region}: {e}")

        return resources
