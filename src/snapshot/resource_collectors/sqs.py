"""SQS resource collector."""

from datetime import datetime, timezone
from typing import List

from ...models.resource import Resource
from ...utils.hash import compute_config_hash
from .base import BaseResourceCollector


class SQSCollector(BaseResourceCollector):
    """Collector for AWS SQS resources (queues)."""

    @property
    def service_name(self) -> str:
        return "sqs"

    def collect(self) -> List[Resource]:
        """Collect SQS resources.

        Returns:
            List of SQS queues
        """
        resources = []
        account_id = self._get_account_id()
        client = self._create_client()

        try:
            # List all queue URLs
            response = client.list_queues()
            queue_urls = response.get("QueueUrls", [])

            for queue_url in queue_urls:
                try:
                    # Get queue attributes
                    attrs_response = client.get_queue_attributes(QueueUrl=queue_url, AttributeNames=["All"])
                    attributes = attrs_response.get("Attributes", {})

                    # Get queue name from URL
                    queue_name = queue_url.split("/")[-1]

                    # Build ARN
                    queue_arn = attributes.get("QueueArn", f"arn:aws:sqs:{self.region}:{account_id}:{queue_name}")

                    # Get tags
                    tags = {}
                    try:
                        tag_response = client.list_queue_tags(QueueUrl=queue_url)
                        tags = tag_response.get("Tags", {})
                    except Exception as e:
                        self.logger.debug(f"Could not get tags for SQS queue {queue_name}: {e}")

                    # Convert CreatedTimestamp from epoch seconds to datetime
                    created_at = None
                    created_timestamp = attributes.get("CreatedTimestamp")
                    if created_timestamp:
                        try:
                            created_at = datetime.fromtimestamp(int(created_timestamp), tz=timezone.utc)
                        except (ValueError, OSError) as e:
                            self.logger.debug(f"Could not parse CreatedTimestamp for {queue_name}: {e}")

                    # Create resource
                    resource = Resource(
                        arn=queue_arn,
                        resource_type="AWS::SQS::Queue",
                        name=queue_name,
                        region=self.region,
                        tags=tags,
                        config_hash=compute_config_hash(attributes),
                        created_at=created_at,
                        raw_config=attributes,
                    )
                    resources.append(resource)

                except Exception as e:
                    self.logger.debug(f"Could not get attributes for SQS queue {queue_url}: {e}")

        except Exception as e:
            self.logger.error(f"Error collecting SQS queues in {self.region}: {e}")

        self.logger.debug(f"Collected {len(resources)} SQS queues in {self.region}")
        return resources
