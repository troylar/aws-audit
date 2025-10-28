"""CloudFormation resource collector."""

from typing import List

from ...models.resource import Resource
from ...utils.hash import compute_config_hash
from .base import BaseResourceCollector


class CloudFormationCollector(BaseResourceCollector):
    """Collector for AWS CloudFormation resources (stacks)."""

    @property
    def service_name(self) -> str:
        return "cloudformation"

    def collect(self) -> List[Resource]:
        """Collect CloudFormation resources.

        Returns:
            List of CloudFormation stacks
        """
        resources = []
        client = self._create_client()

        try:
            paginator = client.get_paginator("describe_stacks")
            for page in paginator.paginate():
                for stack in page.get("Stacks", []):
                    stack_name = stack["StackName"]
                    stack_id = stack["StackId"]

                    # Extract tags
                    tags = {}
                    for tag in stack.get("Tags", []):
                        tags[tag["Key"]] = tag["Value"]

                    # Create resource
                    resource = Resource(
                        arn=stack_id,  # Stack ID is actually the ARN
                        resource_type="AWS::CloudFormation::Stack",
                        name=stack_name,
                        region=self.region,
                        tags=tags,
                        config_hash=compute_config_hash(stack),
                        created_at=stack.get("CreationTime"),
                        raw_config=stack,
                    )
                    resources.append(resource)

        except Exception as e:
            self.logger.error(f"Error collecting CloudFormation stacks in {self.region}: {e}")

        self.logger.debug(f"Collected {len(resources)} CloudFormation stacks in {self.region}")
        return resources
