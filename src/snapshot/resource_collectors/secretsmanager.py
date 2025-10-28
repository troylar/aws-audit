"""Secrets Manager resource collector."""

from typing import List

from ...models.resource import Resource
from ...utils.hash import compute_config_hash
from .base import BaseResourceCollector


class SecretsManagerCollector(BaseResourceCollector):
    """Collector for AWS Secrets Manager resources."""

    @property
    def service_name(self) -> str:
        return "secretsmanager"

    def collect(self) -> List[Resource]:
        """Collect Secrets Manager secrets.

        Returns:
            List of Secrets Manager secret resources
        """
        resources = []
        client = self._create_client()

        try:
            paginator = client.get_paginator("list_secrets")
            for page in paginator.paginate():
                for secret in page.get("SecretList", []):
                    secret_name = secret["Name"]
                    secret_arn = secret["ARN"]

                    # Get full secret details (but not the actual secret value)
                    try:
                        secret_details = client.describe_secret(SecretId=secret_arn)
                        # Use detailed info for config hash
                        config_data = secret_details
                    except Exception as e:
                        self.logger.debug(f"Could not get details for secret {secret_name}: {e}")
                        config_data = secret

                    # Extract tags
                    tags = {}
                    for tag in secret.get("Tags", []):
                        tags[tag["Key"]] = tag["Value"]

                    # Extract creation date
                    created_at = secret.get("CreatedDate")

                    # Create resource (without secret value for security)
                    # Remove sensitive fields if present
                    safe_config = {k: v for k, v in config_data.items() if k not in ["SecretString", "SecretBinary"]}

                    resource = Resource(
                        arn=secret_arn,
                        resource_type="AWS::SecretsManager::Secret",
                        name=secret_name,
                        region=self.region,
                        tags=tags,
                        config_hash=compute_config_hash(safe_config),
                        created_at=created_at,
                        raw_config=safe_config,
                    )
                    resources.append(resource)

        except Exception as e:
            self.logger.error(f"Error collecting Secrets Manager secrets in {self.region}: {e}")

        self.logger.debug(f"Collected {len(resources)} Secrets Manager secrets in {self.region}")
        return resources
