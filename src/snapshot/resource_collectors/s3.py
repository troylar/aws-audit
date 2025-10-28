"""S3 resource collector."""

from typing import List

from ...models.resource import Resource
from ...utils.hash import compute_config_hash
from .base import BaseResourceCollector


class S3Collector(BaseResourceCollector):
    """Collector for AWS S3 buckets.

    Note: S3 is a global service but buckets are accessed via regional endpoints.
    We only collect once (in us-east-1) to avoid duplicates.
    """

    @property
    def service_name(self) -> str:
        return "s3"

    @property
    def is_global_service(self) -> bool:
        # S3 is global, so only collect once
        return True

    def collect(self) -> List[Resource]:
        """Collect S3 buckets.

        Returns:
            List of S3 bucket resources
        """
        resources = []
        client = self._create_client()

        try:
            # List all buckets
            response = client.list_buckets()

            for bucket in response.get("Buckets", []):
                bucket_name = bucket["Name"]
                creation_date = bucket.get("CreationDate")

                # Get bucket location to determine region
                try:
                    location_response = client.get_bucket_location(Bucket=bucket_name)
                    location = location_response.get("LocationConstraint")
                    # None means us-east-1
                    bucket_region = location if location else "us-east-1"
                except Exception as e:
                    self.logger.debug(f"Could not get location for bucket {bucket_name}: {e}")
                    bucket_region = "unknown"

                # Get bucket tags
                tags = {}
                try:
                    tag_response = client.get_bucket_tagging(Bucket=bucket_name)
                    tags = {tag["Key"]: tag["Value"] for tag in tag_response.get("TagSet", [])}
                except client.exceptions.NoSuchTagSet:
                    # Bucket has no tags
                    pass
                except Exception as e:
                    self.logger.debug(f"Could not get tags for bucket {bucket_name}: {e}")

                # Get additional bucket configuration for config hash
                bucket_config = {
                    "Name": bucket_name,
                    "CreationDate": creation_date,
                    "Region": bucket_region,
                }

                # Try to get versioning, encryption, etc.
                try:
                    versioning = client.get_bucket_versioning(Bucket=bucket_name)
                    bucket_config["Versioning"] = versioning.get("Status", "Disabled")
                except Exception:
                    pass

                try:
                    encryption = client.get_bucket_encryption(Bucket=bucket_name)
                    bucket_config["Encryption"] = encryption.get("ServerSideEncryptionConfiguration")
                except Exception:
                    # No encryption configured
                    pass

                # Build ARN
                arn = f"arn:aws:s3:::{bucket_name}"

                # Create resource
                resource = Resource(
                    arn=arn,
                    resource_type="AWS::S3::Bucket",
                    name=bucket_name,
                    region=bucket_region,
                    tags=tags,
                    config_hash=compute_config_hash(bucket_config),
                    created_at=creation_date,
                    raw_config=bucket_config,
                )
                resources.append(resource)

        except Exception as e:
            self.logger.error(f"Error collecting S3 buckets: {e}")

        self.logger.debug(f"Collected {len(resources)} S3 buckets")
        return resources
