"""SNS resource collector."""

from typing import List

from ...models.resource import Resource
from ...utils.hash import compute_config_hash
from .base import BaseResourceCollector


class SNSCollector(BaseResourceCollector):
    """Collector for AWS SNS resources (topics)."""

    @property
    def service_name(self) -> str:
        return "sns"

    def collect(self) -> List[Resource]:
        """Collect SNS resources.

        Returns:
            List of SNS topics
        """
        resources = []
        client = self._create_client()

        try:
            paginator = client.get_paginator("list_topics")
            for page in paginator.paginate():
                for topic in page.get("Topics", []):
                    topic_arn = topic["TopicArn"]

                    # Get topic name from ARN
                    topic_name = topic_arn.split(":")[-1]

                    # Get topic attributes
                    try:
                        attrs_response = client.get_topic_attributes(TopicArn=topic_arn)
                        attributes = attrs_response.get("Attributes", {})

                        # Get tags
                        tags = {}
                        try:
                            tag_response = client.list_tags_for_resource(ResourceArn=topic_arn)
                            tags = {tag["Key"]: tag["Value"] for tag in tag_response.get("Tags", [])}
                        except Exception as e:
                            self.logger.debug(f"Could not get tags for SNS topic {topic_name}: {e}")

                        # Create resource
                        resource = Resource(
                            arn=topic_arn,
                            resource_type="AWS::SNS::Topic",
                            name=topic_name,
                            region=self.region,
                            tags=tags,
                            config_hash=compute_config_hash(attributes),
                            created_at=None,  # SNS topics don't expose creation date
                            raw_config=attributes,
                        )
                        resources.append(resource)

                    except Exception as e:
                        self.logger.debug(f"Could not get attributes for SNS topic {topic_name}: {e}")

        except Exception as e:
            self.logger.error(f"Error collecting SNS topics in {self.region}: {e}")

        self.logger.debug(f"Collected {len(resources)} SNS topics in {self.region}")
        return resources
