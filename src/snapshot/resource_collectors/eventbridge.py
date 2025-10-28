"""EventBridge resource collector."""

from typing import List

from ...models.resource import Resource
from ...utils.hash import compute_config_hash
from .base import BaseResourceCollector


class EventBridgeCollector(BaseResourceCollector):
    """Collector for Amazon EventBridge resources (Event Buses, Rules)."""

    @property
    def service_name(self) -> str:
        return "eventbridge"

    def collect(self) -> List[Resource]:
        """Collect EventBridge resources.

        Collects:
        - Event Buses (custom and partner buses)
        - Event Rules (across all buses)

        Returns:
            List of EventBridge resources
        """
        resources = []

        # Collect Event Buses
        resources.extend(self._collect_event_buses())

        # Collect Event Rules (across all buses)
        resources.extend(self._collect_event_rules())

        self.logger.debug(f"Collected {len(resources)} EventBridge resources in {self.region}")
        return resources

    def _collect_event_buses(self) -> List[Resource]:
        """Collect EventBridge Event Buses.

        Returns:
            List of Event Bus resources
        """
        resources = []
        client = self._create_client("events")

        try:
            paginator = client.get_paginator("list_event_buses")
            for page in paginator.paginate():
                for bus in page.get("EventBuses", []):
                    bus_name = bus["Name"]
                    bus_arn = bus["Arn"]

                    # Get tags
                    tags = {}
                    try:
                        tag_response = client.list_tags_for_resource(ResourceARN=bus_arn)
                        for tag in tag_response.get("Tags", []):
                            tags[tag["Key"]] = tag["Value"]
                    except Exception as e:
                        self.logger.debug(f"Could not get tags for event bus {bus_name}: {e}")

                    # Extract creation time (if available)
                    created_at = bus.get("CreationTime")

                    # Create resource
                    resource = Resource(
                        arn=bus_arn,
                        resource_type="AWS::Events::EventBus",
                        name=bus_name,
                        region=self.region,
                        tags=tags,
                        config_hash=compute_config_hash(bus),
                        created_at=created_at,
                        raw_config=bus,
                    )
                    resources.append(resource)

        except Exception as e:
            self.logger.error(f"Error collecting EventBridge event buses in {self.region}: {e}")

        return resources

    def _collect_event_rules(self) -> List[Resource]:
        """Collect EventBridge Rules across all event buses.

        Returns:
            List of Event Rule resources
        """
        resources = []
        client = self._create_client("events")

        try:
            # First, get all event buses to collect rules from each
            event_buses = ["default"]  # Start with default bus

            try:
                paginator = client.get_paginator("list_event_buses")
                for page in paginator.paginate():
                    for bus in page.get("EventBuses", []):
                        bus_name = bus["Name"]
                        if bus_name != "default":
                            event_buses.append(bus_name)
            except Exception as e:
                self.logger.debug(f"Error listing event buses: {e}")

            # Collect rules from each bus
            for bus_name in event_buses:
                try:
                    paginator = client.get_paginator("list_rules")
                    for page in paginator.paginate(EventBusName=bus_name):
                        for rule in page.get("Rules", []):
                            rule_name = rule["Name"]
                            rule_arn = rule["Arn"]

                            # Get tags
                            tags = {}
                            try:
                                tag_response = client.list_tags_for_resource(ResourceARN=rule_arn)
                                for tag in tag_response.get("Tags", []):
                                    tags[tag["Key"]] = tag["Value"]
                            except Exception as e:
                                self.logger.debug(f"Could not get tags for rule {rule_name}: {e}")

                            # Get full rule details
                            try:
                                rule_details = client.describe_rule(Name=rule_name, EventBusName=bus_name)
                                # Merge with basic rule info
                                full_rule = {**rule, **rule_details}
                            except Exception as e:
                                self.logger.debug(f"Could not get details for rule {rule_name}: {e}")
                                full_rule = rule

                            # Extract creation time (not typically available for rules)
                            created_at = None

                            # Create resource
                            resource = Resource(
                                arn=rule_arn,
                                resource_type="AWS::Events::Rule",
                                name=rule_name,
                                region=self.region,
                                tags=tags,
                                config_hash=compute_config_hash(full_rule),
                                created_at=created_at,
                                raw_config=full_rule,
                            )
                            resources.append(resource)

                except Exception as e:
                    self.logger.error(f"Error collecting rules from event bus {bus_name}: {e}")

        except Exception as e:
            self.logger.error(f"Error collecting EventBridge rules in {self.region}: {e}")

        return resources
