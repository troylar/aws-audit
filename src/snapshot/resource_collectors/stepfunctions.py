"""Step Functions resource collector."""

from typing import List

from ...models.resource import Resource
from ...utils.hash import compute_config_hash
from .base import BaseResourceCollector


class StepFunctionsCollector(BaseResourceCollector):
    """Collector for AWS Step Functions resources."""

    @property
    def service_name(self) -> str:
        return "stepfunctions"

    def collect(self) -> List[Resource]:
        """Collect Step Functions state machines.

        Returns:
            List of Step Functions state machine resources
        """
        resources = []
        client = self._create_client("stepfunctions")

        try:
            paginator = client.get_paginator("list_state_machines")
            for page in paginator.paginate():
                for state_machine in page.get("stateMachines", []):
                    sm_arn = state_machine["stateMachineArn"]
                    sm_name = state_machine["name"]

                    try:
                        # Get detailed state machine info
                        sm_details = client.describe_state_machine(stateMachineArn=sm_arn)

                        # Get tags
                        tags = {}
                        try:
                            tag_response = client.list_tags_for_resource(resourceArn=sm_arn)
                            for tag in tag_response.get("tags", []):
                                tags[tag["key"]] = tag["value"]
                        except Exception as e:
                            self.logger.debug(f"Could not get tags for state machine {sm_name}: {e}")

                        # Extract creation date
                        created_at = sm_details.get("creationDate")

                        # Remove the definition for config hash (can be large)
                        # but keep key metadata
                        config = {k: v for k, v in sm_details.items() if k != "definition"}

                        # Create resource
                        resource = Resource(
                            arn=sm_arn,
                            resource_type="AWS::StepFunctions::StateMachine",
                            name=sm_name,
                            region=self.region,
                            tags=tags,
                            config_hash=compute_config_hash(config),
                            created_at=created_at,
                            raw_config=config,
                        )
                        resources.append(resource)

                    except Exception as e:
                        self.logger.debug(f"Error processing state machine {sm_name}: {e}")
                        continue

        except Exception as e:
            self.logger.error(f"Error collecting Step Functions state machines in {self.region}: {e}")

        self.logger.debug(f"Collected {len(resources)} Step Functions state machines in {self.region}")
        return resources
