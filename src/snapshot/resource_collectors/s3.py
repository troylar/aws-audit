"""S3 resource collector."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

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
        resources: List[Resource] = []
        client = self._create_client()

        try:
            # List all buckets
            response = client.list_buckets()
            buckets = response.get("Buckets", [])

            if not buckets:
                return resources

            # Fetch per-bucket details in parallel
            with ThreadPoolExecutor(max_workers=min(10, len(buckets))) as executor:
                futures = {executor.submit(self._collect_bucket_details, client, bucket): bucket for bucket in buckets}
                for future in as_completed(futures):
                    result = future.result()
                    if result:
                        resources.append(result)

        except Exception as e:
            self.logger.error(f"Error collecting S3 buckets: {e}")

        self.logger.debug(f"Collected {len(resources)} S3 buckets")
        return resources

    def _collect_bucket_details(self, client: Any, bucket: Dict) -> Optional[Resource]:
        """Collect details for a single S3 bucket."""
        bucket_name = bucket["Name"]
        creation_date = bucket.get("CreationDate")

        try:
            # Get bucket location to determine region
            try:
                location_response = client.get_bucket_location(Bucket=bucket_name)
                location = location_response.get("LocationConstraint")
                bucket_region = location if location else "us-east-1"
            except Exception as e:
                self.logger.debug(f"Could not get location for bucket {bucket_name}: {e}")
                bucket_region = "unknown"

            # Get bucket tags
            tags = {}
            try:
                tag_response = client.get_bucket_tagging(Bucket=bucket_name)
                tags = {tag["Key"]: tag["Value"] for tag in tag_response.get("TagSet", [])}
            except Exception as e:
                err_str = str(e)
                if "NoSuchTagSet" not in err_str:
                    self.logger.debug(f"Could not get tags for bucket {bucket_name}: {e}")

            # Get additional bucket configuration for config hash
            bucket_config = {
                "Name": bucket_name,
                "CreationDate": creation_date,
                "Region": bucket_region,
            }

            try:
                versioning = client.get_bucket_versioning(Bucket=bucket_name)
                bucket_config["Versioning"] = versioning.get("Status", "Disabled")
            except Exception:
                pass

            try:
                encryption = client.get_bucket_encryption(Bucket=bucket_name)
                bucket_config["Encryption"] = encryption.get("ServerSideEncryptionConfiguration")
            except Exception:
                pass

            arn = f"arn:aws:s3:::{bucket_name}"

            return Resource(
                arn=arn,
                resource_type="AWS::S3::Bucket",
                name=bucket_name,
                region=bucket_region,
                tags=tags,
                config_hash=compute_config_hash(bucket_config),
                created_at=creation_date,
                raw_config=bucket_config,
            )

        except Exception as e:
            self.logger.debug(f"Error collecting details for bucket {bucket_name}: {e}")
            return None
