"""Route53 resource collector."""

from typing import List

from ...models.resource import Resource
from ...utils.hash import compute_config_hash
from .base import BaseResourceCollector


class Route53Collector(BaseResourceCollector):
    """Collector for Amazon Route53 resources (Hosted Zones)."""

    @property
    def service_name(self) -> str:
        return "route53"

    @property
    def is_global_service(self) -> bool:
        """Route53 is a global service."""
        return True

    def collect(self) -> List[Resource]:
        """Collect Route53 resources.

        Collects:
        - Hosted Zones (public and private)
        - Resource Record Sets within each zone

        Returns:
            List of Route53 hosted zone resources
        """
        resources = []
        client = self._create_client()

        try:
            # Collect hosted zones
            paginator = client.get_paginator("list_hosted_zones")
            for page in paginator.paginate():
                for zone in page.get("HostedZones", []):
                    zone_id = zone["Id"].split("/")[-1]  # Extract ID from '/hostedzone/Z123'
                    zone_name = zone["Name"]

                    # Get tags
                    tags = {}
                    try:
                        tag_response = client.list_tags_for_resource(ResourceType="hostedzone", ResourceId=zone_id)
                        for tag in tag_response.get("Tags", []):
                            tags[tag["Key"]] = tag["Value"]
                    except Exception as e:
                        self.logger.debug(f"Could not get tags for hosted zone {zone_id}: {e}")

                    # Get record count and additional details
                    try:
                        zone_details = client.get_hosted_zone(Id=zone["Id"])
                        hosted_zone_info = zone_details.get("HostedZone", {})
                        # Merge basic info with detailed info
                        full_zone = {**zone, **hosted_zone_info}
                    except Exception as e:
                        self.logger.debug(f"Could not get details for hosted zone {zone_id}: {e}")
                        full_zone = zone

                    # Build ARN (Route53 hosted zones use a specific ARN format)
                    # Note: ARNs for Route53 are not standard across all operations
                    arn = f"arn:aws:route53:::hostedzone/{zone_id}"

                    # Route53 doesn't provide creation timestamp, use None
                    created_at = None

                    # Create resource
                    resource = Resource(
                        arn=arn,
                        resource_type="AWS::Route53::HostedZone",
                        name=zone_name,
                        region="global",  # Route53 is global
                        tags=tags,
                        config_hash=compute_config_hash(full_zone),
                        created_at=created_at,
                        raw_config=full_zone,
                    )
                    resources.append(resource)

        except Exception as e:
            self.logger.error(f"Error collecting Route53 hosted zones: {e}")

        self.logger.debug(f"Collected {len(resources)} Route53 hosted zones")
        return resources
