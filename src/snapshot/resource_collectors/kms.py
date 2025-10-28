"""KMS resource collector."""

from typing import List

from ...models.resource import Resource
from ...utils.hash import compute_config_hash
from .base import BaseResourceCollector


class KMSCollector(BaseResourceCollector):
    """Collector for AWS KMS (Key Management Service) resources."""

    @property
    def service_name(self) -> str:
        return "kms"

    def collect(self) -> List[Resource]:
        """Collect KMS keys.

        Collects customer-managed KMS keys (not AWS-managed keys).

        Returns:
            List of KMS key resources
        """
        resources = []
        client = self._create_client()

        try:
            paginator = client.get_paginator("list_keys")
            for page in paginator.paginate():
                for key_item in page.get("Keys", []):
                    key_id = key_item["KeyId"]
                    key_arn = key_item["KeyArn"]

                    try:
                        # Get key metadata
                        key_metadata = client.describe_key(KeyId=key_id)["KeyMetadata"]

                        # Skip AWS-managed keys (we only want customer-managed keys)
                        if key_metadata.get("KeyManager") == "AWS":
                            continue

                        # Skip keys that are pending deletion
                        if key_metadata.get("KeyState") == "PendingDeletion":
                            self.logger.debug(f"Skipping key {key_id} - pending deletion")
                            continue

                        key_alias = None

                        # Get key aliases
                        try:
                            aliases_response = client.list_aliases(KeyId=key_id)
                            aliases = aliases_response.get("Aliases", [])
                            if aliases:
                                # Use first alias as the name
                                key_alias = aliases[0]["AliasName"]
                        except Exception as e:
                            self.logger.debug(f"Could not get aliases for key {key_id}: {e}")

                        # Get tags
                        tags = {}
                        try:
                            tag_response = client.list_resource_tags(KeyId=key_id)
                            for tag in tag_response.get("Tags", []):
                                tags[tag["TagKey"]] = tag["TagValue"]
                        except Exception as e:
                            self.logger.debug(f"Could not get tags for key {key_id}: {e}")

                        # Get key rotation status
                        rotation_enabled = False
                        try:
                            rotation_response = client.get_key_rotation_status(KeyId=key_id)
                            rotation_enabled = rotation_response.get("KeyRotationEnabled", False)
                        except Exception as e:
                            self.logger.debug(f"Could not get rotation status for key {key_id}: {e}")

                        # Build config for hash
                        config = {
                            **key_metadata,
                            "RotationEnabled": rotation_enabled,
                            "Aliases": [key_alias] if key_alias else [],
                        }

                        # Extract creation date
                        created_at = key_metadata.get("CreationDate")

                        # Use alias as name if available, otherwise use key ID
                        name = key_alias if key_alias else key_id

                        # Create resource
                        resource = Resource(
                            arn=key_arn,
                            resource_type="AWS::KMS::Key",
                            name=name,
                            region=self.region,
                            tags=tags,
                            config_hash=compute_config_hash(config),
                            created_at=created_at,
                            raw_config=config,
                        )
                        resources.append(resource)

                    except Exception as e:
                        self.logger.debug(f"Error processing key {key_id}: {e}")
                        continue

        except Exception as e:
            self.logger.error(f"Error collecting KMS keys in {self.region}: {e}")

        self.logger.debug(f"Collected {len(resources)} KMS keys in {self.region}")
        return resources
