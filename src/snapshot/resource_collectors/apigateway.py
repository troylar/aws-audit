"""API Gateway resource collector."""

from typing import List

from ...models.resource import Resource
from ...utils.hash import compute_config_hash
from .base import BaseResourceCollector


class APIGatewayCollector(BaseResourceCollector):
    """Collector for AWS API Gateway resources (REST, HTTP, WebSocket APIs)."""

    @property
    def service_name(self) -> str:
        return "apigateway"

    def collect(self) -> List[Resource]:
        """Collect API Gateway resources.

        Collects:
        - REST APIs (v1)
        - HTTP APIs (v2)
        - WebSocket APIs (v2)

        Returns:
            List of API Gateway APIs
        """
        resources = []

        # Collect REST APIs (v1)
        resources.extend(self._collect_rest_apis())

        # Collect HTTP and WebSocket APIs (v2)
        resources.extend(self._collect_v2_apis())

        self.logger.debug(f"Collected {len(resources)} API Gateway APIs in {self.region}")
        return resources

    def _collect_rest_apis(self) -> List[Resource]:
        """Collect REST APIs (API Gateway v1).

        Returns:
            List of REST API resources
        """
        resources = []
        client = self._create_client()

        try:
            paginator = client.get_paginator("get_rest_apis")
            for page in paginator.paginate():
                for api in page.get("items", []):
                    api_id = api["id"]
                    api_name = api["name"]

                    # Get tags
                    tags = {}
                    try:
                        tag_response = client.get_tags(
                            resourceArn=f"arn:aws:apigateway:{self.region}::/restapis/{api_id}"
                        )
                        tags = tag_response.get("tags", {})
                    except Exception as e:
                        self.logger.debug(f"Could not get tags for REST API {api_id}: {e}")

                    # Build ARN
                    arn = f"arn:aws:apigateway:{self.region}::/restapis/{api_id}"

                    # Extract creation date
                    created_at = api.get("createdDate")

                    # Create resource
                    resource = Resource(
                        arn=arn,
                        resource_type="AWS::ApiGateway::RestApi",
                        name=api_name,
                        region=self.region,
                        tags=tags,
                        config_hash=compute_config_hash(api),
                        created_at=created_at,
                        raw_config=api,
                    )
                    resources.append(resource)

        except Exception as e:
            self.logger.error(f"Error collecting REST APIs in {self.region}: {e}")

        return resources

    def _collect_v2_apis(self) -> List[Resource]:
        """Collect HTTP and WebSocket APIs (API Gateway v2).

        Returns:
            List of v2 API resources
        """
        resources = []

        try:
            client = self._create_client("apigatewayv2")

            paginator = client.get_paginator("get_apis")
            for page in paginator.paginate():
                for api in page.get("Items", []):
                    api_id = api["ApiId"]
                    api_name = api["Name"]
                    protocol_type = api["ProtocolType"]  # HTTP or WEBSOCKET

                    # Get tags
                    tags = api.get("Tags", {})

                    # Build ARN
                    arn = f"arn:aws:apigateway:{self.region}::/apis/{api_id}"

                    # Extract creation date
                    created_at = api.get("CreatedDate")

                    # Determine resource type based on protocol
                    if protocol_type == "HTTP":
                        resource_type = "AWS::ApiGatewayV2::Api::HTTP"
                    elif protocol_type == "WEBSOCKET":
                        resource_type = "AWS::ApiGatewayV2::Api::WebSocket"
                    else:
                        resource_type = f"AWS::ApiGatewayV2::Api::{protocol_type}"

                    # Create resource
                    resource = Resource(
                        arn=arn,
                        resource_type=resource_type,
                        name=api_name,
                        region=self.region,
                        tags=tags,
                        config_hash=compute_config_hash(api),
                        created_at=created_at,
                        raw_config=api,
                    )
                    resources.append(resource)

        except Exception as e:
            self.logger.error(f"Error collecting API Gateway v2 APIs in {self.region}: {e}")

        return resources
