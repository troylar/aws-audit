"""WAF resource collector."""

from typing import List

from ...models.resource import Resource
from ...utils.hash import compute_config_hash
from .base import BaseResourceCollector


class WAFCollector(BaseResourceCollector):
    """Collector for AWS WAF (Web Application Firewall) resources."""

    @property
    def service_name(self) -> str:
        return "waf"

    def collect(self) -> List[Resource]:
        """Collect WAF resources.

        Collects WAFv2 Web ACLs (regional and global/CloudFront).

        Returns:
            List of WAF Web ACL resources
        """
        resources = []

        # Collect regional Web ACLs
        resources.extend(self._collect_regional_web_acls())

        # Collect CloudFront Web ACLs (global, only from us-east-1)
        if self.region == "us-east-1":
            resources.extend(self._collect_cloudfront_web_acls())

        self.logger.debug(f"Collected {len(resources)} WAF Web ACLs in {self.region}")
        return resources

    def _collect_regional_web_acls(self) -> List[Resource]:
        """Collect regional WAFv2 Web ACLs.

        Returns:
            List of regional Web ACL resources
        """
        resources = []

        try:
            client = self._create_client("wafv2")

            paginator = client.get_paginator("list_web_acls")
            for page in paginator.paginate(Scope="REGIONAL"):
                for web_acl_summary in page.get("WebACLs", []):
                    web_acl_name = web_acl_summary["Name"]
                    web_acl_id = web_acl_summary["Id"]
                    web_acl_arn = web_acl_summary["ARN"]

                    try:
                        # Get detailed Web ACL info
                        web_acl_response = client.get_web_acl(Name=web_acl_name, Scope="REGIONAL", Id=web_acl_id)
                        web_acl = web_acl_response.get("WebACL", {})

                        # Get tags
                        tags = {}
                        try:
                            tag_response = client.list_tags_for_resource(ResourceARN=web_acl_arn)
                            for tag_info in tag_response.get("TagInfoForResource", {}).get("TagList", []):
                                tags[tag_info["Key"]] = tag_info["Value"]
                        except Exception as e:
                            self.logger.debug(f"Could not get tags for Web ACL {web_acl_name}: {e}")

                        # WAFv2 doesn't provide creation timestamp
                        created_at = None

                        # Remove large rule definitions for config hash
                        config = {k: v for k, v in web_acl.items() if k not in ["Rules"]}
                        config["RuleCount"] = len(web_acl.get("Rules", []))

                        # Create resource
                        resource = Resource(
                            arn=web_acl_arn,
                            resource_type="AWS::WAFv2::WebACL::Regional",
                            name=web_acl_name,
                            region=self.region,
                            tags=tags,
                            config_hash=compute_config_hash(config),
                            created_at=created_at,
                            raw_config=config,
                        )
                        resources.append(resource)

                    except Exception as e:
                        self.logger.debug(f"Error processing Web ACL {web_acl_name}: {e}")
                        continue

        except Exception as e:
            self.logger.error(f"Error collecting regional WAF Web ACLs in {self.region}: {e}")

        return resources

    def _collect_cloudfront_web_acls(self) -> List[Resource]:
        """Collect CloudFront (global) WAFv2 Web ACLs.

        Only collects when in us-east-1 since CloudFront resources are global.

        Returns:
            List of CloudFront Web ACL resources
        """
        resources = []

        try:
            client = self._create_client("wafv2")

            paginator = client.get_paginator("list_web_acls")
            for page in paginator.paginate(Scope="CLOUDFRONT"):
                for web_acl_summary in page.get("WebACLs", []):
                    web_acl_name = web_acl_summary["Name"]
                    web_acl_id = web_acl_summary["Id"]
                    web_acl_arn = web_acl_summary["ARN"]

                    try:
                        # Get detailed Web ACL info
                        web_acl_response = client.get_web_acl(Name=web_acl_name, Scope="CLOUDFRONT", Id=web_acl_id)
                        web_acl = web_acl_response.get("WebACL", {})

                        # Get tags
                        tags = {}
                        try:
                            tag_response = client.list_tags_for_resource(ResourceARN=web_acl_arn)
                            for tag_info in tag_response.get("TagInfoForResource", {}).get("TagList", []):
                                tags[tag_info["Key"]] = tag_info["Value"]
                        except Exception as e:
                            self.logger.debug(f"Could not get tags for CloudFront Web ACL {web_acl_name}: {e}")

                        # WAFv2 doesn't provide creation timestamp
                        created_at = None

                        # Remove large rule definitions for config hash
                        config = {k: v for k, v in web_acl.items() if k not in ["Rules"]}
                        config["RuleCount"] = len(web_acl.get("Rules", []))

                        # Create resource
                        resource = Resource(
                            arn=web_acl_arn,
                            resource_type="AWS::WAFv2::WebACL::CloudFront",
                            name=web_acl_name,
                            region="global",  # CloudFront is global
                            tags=tags,
                            config_hash=compute_config_hash(config),
                            created_at=created_at,
                            raw_config=config,
                        )
                        resources.append(resource)

                    except Exception as e:
                        self.logger.debug(f"Error processing CloudFront Web ACL {web_acl_name}: {e}")
                        continue

        except Exception as e:
            self.logger.error(f"Error collecting CloudFront WAF Web ACLs: {e}")

        return resources
