"""VPC Endpoints resource collector."""

from typing import List

from ...models.resource import Resource
from ...utils.hash import compute_config_hash
from .base import BaseResourceCollector


class VPCEndpointsCollector(BaseResourceCollector):
    """Collector for VPC Endpoints (Interface and Gateway endpoints)."""

    @property
    def service_name(self) -> str:
        return "vpc-endpoints"

    def collect(self) -> List[Resource]:
        """Collect VPC Endpoints.

        Collects both Interface and Gateway VPC endpoints.

        Returns:
            List of VPC Endpoint resources
        """
        resources = []
        client = self._create_client("ec2")

        try:
            paginator = client.get_paginator("describe_vpc_endpoints")
            for page in paginator.paginate():
                for endpoint in page.get("VpcEndpoints", []):
                    endpoint_id = endpoint["VpcEndpointId"]
                    service_name = endpoint.get("ServiceName", "unknown")
                    endpoint_type = endpoint.get("VpcEndpointType", "Unknown")

                    # Extract tags
                    tags = {}
                    for tag in endpoint.get("Tags", []):
                        tags[tag["Key"]] = tag["Value"]

                    # Get account ID for ARN
                    sts_client = self.session.client("sts")
                    account_id = sts_client.get_caller_identity()["Account"]

                    # Build ARN
                    arn = f"arn:aws:ec2:{self.region}:{account_id}:vpc-endpoint/{endpoint_id}"

                    # Extract creation date
                    created_at = endpoint.get("CreationTimestamp")

                    # Determine resource type based on endpoint type
                    if endpoint_type == "Interface":
                        resource_type = "AWS::EC2::VPCEndpoint::Interface"
                    elif endpoint_type == "Gateway":
                        resource_type = "AWS::EC2::VPCEndpoint::Gateway"
                    else:
                        resource_type = f"AWS::EC2::VPCEndpoint::{endpoint_type}"

                    # Use service name as the friendly name
                    name = f"{endpoint_id} ({service_name.split('.')[-1]})"

                    # Create resource
                    resource = Resource(
                        arn=arn,
                        resource_type=resource_type,
                        name=name,
                        region=self.region,
                        tags=tags,
                        config_hash=compute_config_hash(endpoint),
                        created_at=created_at,
                        raw_config=endpoint,
                    )
                    resources.append(resource)

        except Exception as e:
            self.logger.error(f"Error collecting VPC endpoints in {self.region}: {e}")

        self.logger.debug(f"Collected {len(resources)} VPC endpoints in {self.region}")
        return resources
