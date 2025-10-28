"""Systems Manager resource collector."""

from typing import List

from ...models.resource import Resource
from ...utils.hash import compute_config_hash
from .base import BaseResourceCollector


class SSMCollector(BaseResourceCollector):
    """Collector for AWS Systems Manager resources (Parameter Store, Documents)."""

    @property
    def service_name(self) -> str:
        return "ssm"

    def collect(self) -> List[Resource]:
        """Collect Systems Manager resources.

        Collects:
        - Parameter Store parameters
        - SSM Documents (custom documents only)

        Returns:
            List of Systems Manager resources
        """
        resources = []

        # Collect Parameter Store parameters
        resources.extend(self._collect_parameters())

        # Collect SSM Documents
        resources.extend(self._collect_documents())

        self.logger.debug(f"Collected {len(resources)} Systems Manager resources in {self.region}")
        return resources

    def _collect_parameters(self) -> List[Resource]:
        """Collect Parameter Store parameters.

        Returns:
            List of Parameter resources
        """
        resources = []
        client = self._create_client()

        try:
            paginator = client.get_paginator("describe_parameters")
            for page in paginator.paginate():
                for param in page.get("Parameters", []):
                    param_name = param["Name"]
                    param_type = param["Type"]

                    # Build ARN
                    # Get account ID from session
                    sts_client = self.session.client("sts")
                    account_id = sts_client.get_caller_identity()["Account"]
                    arn = f"arn:aws:ssm:{self.region}:{account_id}:parameter{param_name}"

                    # Get tags
                    tags = {}
                    try:
                        tag_response = client.list_tags_for_resource(ResourceType="Parameter", ResourceId=param_name)
                        for tag in tag_response.get("TagList", []):
                            tags[tag["Key"]] = tag["Value"]
                    except Exception as e:
                        self.logger.debug(f"Could not get tags for parameter {param_name}: {e}")

                    # Get parameter details (metadata only, not the actual value for SecureString)
                    try:
                        # For SecureString, we don't want to expose the value
                        if param_type == "SecureString":
                            # Use describe_parameters data only
                            config = param
                        else:
                            # For String and StringList, we can get the value
                            param_details = client.get_parameter(Name=param_name, WithDecryption=False)
                            config = {
                                **param,
                                "Value": param_details["Parameter"].get("Value"),
                            }
                    except Exception as e:
                        self.logger.debug(f"Could not get details for parameter {param_name}: {e}")
                        config = param

                    # Extract last modified date as creation date proxy
                    created_at = param.get("LastModifiedDate")

                    # Create resource
                    resource = Resource(
                        arn=arn,
                        resource_type="AWS::SSM::Parameter",
                        name=param_name,
                        region=self.region,
                        tags=tags,
                        config_hash=compute_config_hash(config),
                        created_at=created_at,
                        raw_config=config,
                    )
                    resources.append(resource)

        except Exception as e:
            self.logger.error(f"Error collecting SSM parameters in {self.region}: {e}")

        return resources

    def _collect_documents(self) -> List[Resource]:
        """Collect SSM Documents (custom documents only).

        Returns:
            List of SSM Document resources
        """
        resources = []
        client = self._create_client()

        try:
            # Only collect custom documents (not AWS-owned)
            paginator = client.get_paginator("list_documents")
            for page in paginator.paginate(Filters=[{"Key": "Owner", "Values": ["Self"]}]):  # Only user-owned documents
                for doc in page.get("DocumentIdentifiers", []):
                    doc_name = doc["Name"]

                    # Get document details
                    try:
                        doc_details = client.describe_document(Name=doc_name)["Document"]

                        # Build ARN
                        arn = doc_details.get("DocumentArn", doc_name)

                        # Get tags
                        tags = {}
                        for tag in doc_details.get("Tags", []):
                            tags[tag["Key"]] = tag["Value"]

                        # Extract creation date
                        created_at = doc_details.get("CreatedDate")

                        # Create resource (without the actual document content to keep size manageable)
                        config = {k: v for k, v in doc_details.items() if k != "Content"}

                        resource = Resource(
                            arn=arn,
                            resource_type="AWS::SSM::Document",
                            name=doc_name,
                            region=self.region,
                            tags=tags,
                            config_hash=compute_config_hash(config),
                            created_at=created_at,
                            raw_config=config,
                        )
                        resources.append(resource)

                    except Exception as e:
                        self.logger.debug(f"Error processing document {doc_name}: {e}")
                        continue

        except Exception as e:
            self.logger.error(f"Error collecting SSM documents in {self.region}: {e}")

        return resources
