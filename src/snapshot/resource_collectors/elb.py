"""ELB/ALB resource collector."""

from typing import List

from ...models.resource import Resource
from ...utils.hash import compute_config_hash
from .base import BaseResourceCollector


class ELBCollector(BaseResourceCollector):
    """Collector for AWS Load Balancer resources (Classic ELB, ALB, NLB)."""

    @property
    def service_name(self) -> str:
        return "elb"

    def collect(self) -> List[Resource]:
        """Collect ELB resources.

        Returns:
            List of load balancers
        """
        resources = []
        account_id = self._get_account_id()

        # Collect v2 load balancers (ALB, NLB, GWLB)
        resources.extend(self._collect_v2_load_balancers(account_id))

        # Collect classic load balancers
        resources.extend(self._collect_classic_load_balancers(account_id))

        self.logger.debug(f"Collected {len(resources)} load balancers in {self.region}")
        return resources

    def _collect_v2_load_balancers(self, account_id: str) -> List[Resource]:
        """Collect ALB/NLB/GWLB load balancers."""
        resources = []

        try:
            elbv2_client = self._create_client("elbv2")

            paginator = elbv2_client.get_paginator("describe_load_balancers")
            for page in paginator.paginate():
                for lb in page.get("LoadBalancers", []):
                    lb_arn = lb["LoadBalancerArn"]
                    lb_name = lb["LoadBalancerName"]
                    lb_type = lb.get("Type", "application")  # application, network, gateway

                    # Get tags
                    tags = {}
                    try:
                        tag_response = elbv2_client.describe_tags(ResourceArns=[lb_arn])
                        for tag_desc in tag_response.get("TagDescriptions", []):
                            tags = {tag["Key"]: tag["Value"] for tag in tag_desc.get("Tags", [])}
                    except Exception as e:
                        self.logger.debug(f"Could not get tags for load balancer {lb_name}: {e}")

                    # Determine resource type
                    if lb_type == "application":
                        resource_type = "AWS::ElasticLoadBalancingV2::LoadBalancer::Application"
                    elif lb_type == "network":
                        resource_type = "AWS::ElasticLoadBalancingV2::LoadBalancer::Network"
                    elif lb_type == "gateway":
                        resource_type = "AWS::ElasticLoadBalancingV2::LoadBalancer::Gateway"
                    else:
                        resource_type = "AWS::ElasticLoadBalancingV2::LoadBalancer"

                    # Create resource
                    resource = Resource(
                        arn=lb_arn,
                        resource_type=resource_type,
                        name=lb_name,
                        region=self.region,
                        tags=tags,
                        config_hash=compute_config_hash(lb),
                        created_at=lb.get("CreatedTime"),
                        raw_config=lb,
                    )
                    resources.append(resource)

        except Exception as e:
            self.logger.error(f"Error collecting v2 load balancers in {self.region}: {e}")

        return resources

    def _collect_classic_load_balancers(self, account_id: str) -> List[Resource]:
        """Collect classic load balancers."""
        resources = []

        try:
            elb_client = self._create_client("elb")

            paginator = elb_client.get_paginator("describe_load_balancers")
            for page in paginator.paginate():
                for lb in page.get("LoadBalancerDescriptions", []):
                    lb_name = lb["LoadBalancerName"]

                    # Build ARN (classic ELBs don't return ARN directly)
                    lb_arn = f"arn:aws:elasticloadbalancing:{self.region}:{account_id}:loadbalancer/{lb_name}"

                    # Get tags
                    tags = {}
                    try:
                        tag_response = elb_client.describe_tags(LoadBalancerNames=[lb_name])
                        for tag_desc in tag_response.get("TagDescriptions", []):
                            tags = {tag["Key"]: tag["Value"] for tag in tag_desc.get("Tags", [])}
                    except Exception as e:
                        self.logger.debug(f"Could not get tags for classic ELB {lb_name}: {e}")

                    # Create resource
                    resource = Resource(
                        arn=lb_arn,
                        resource_type="AWS::ElasticLoadBalancing::LoadBalancer",
                        name=lb_name,
                        region=self.region,
                        tags=tags,
                        config_hash=compute_config_hash(lb),
                        created_at=lb.get("CreatedTime"),
                        raw_config=lb,
                    )
                    resources.append(resource)

        except Exception as e:
            self.logger.error(f"Error collecting classic load balancers in {self.region}: {e}")

        return resources
