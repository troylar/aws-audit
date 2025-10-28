"""DynamoDB resource collector."""

from typing import List

from ...models.resource import Resource
from ...utils.hash import compute_config_hash
from .base import BaseResourceCollector


class DynamoDBCollector(BaseResourceCollector):
    """Collector for AWS DynamoDB resources (tables)."""

    @property
    def service_name(self) -> str:
        return "dynamodb"

    def collect(self) -> List[Resource]:
        """Collect DynamoDB resources.

        Returns:
            List of DynamoDB tables
        """
        resources = []
        client = self._create_client()

        try:
            paginator = client.get_paginator("list_tables")
            for page in paginator.paginate():
                for table_name in page.get("TableNames", []):
                    try:
                        # Get table details
                        table_response = client.describe_table(TableName=table_name)
                        table = table_response.get("Table", {})

                        table_arn = table.get("TableArn")

                        # Get tags
                        tags = {}
                        try:
                            tag_response = client.list_tags_of_resource(ResourceArn=table_arn)
                            tags = {tag["Key"]: tag["Value"] for tag in tag_response.get("Tags", [])}
                        except Exception as e:
                            self.logger.debug(f"Could not get tags for DynamoDB table {table_name}: {e}")

                        # Create resource
                        resource = Resource(
                            arn=table_arn,
                            resource_type="AWS::DynamoDB::Table",
                            name=table_name,
                            region=self.region,
                            tags=tags,
                            config_hash=compute_config_hash(table),
                            created_at=table.get("CreationDateTime"),
                            raw_config=table,
                        )
                        resources.append(resource)

                    except Exception as e:
                        self.logger.debug(f"Could not get details for DynamoDB table {table_name}: {e}")

        except Exception as e:
            self.logger.error(f"Error collecting DynamoDB tables in {self.region}: {e}")

        self.logger.debug(f"Collected {len(resources)} DynamoDB tables in {self.region}")
        return resources
