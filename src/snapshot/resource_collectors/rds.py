"""RDS resource collector."""

from typing import List

from ...models.resource import Resource
from ...utils.hash import compute_config_hash
from .base import BaseResourceCollector


class RDSCollector(BaseResourceCollector):
    """Collector for AWS RDS resources (instances, clusters, snapshots)."""

    @property
    def service_name(self) -> str:
        return "rds"

    def collect(self) -> List[Resource]:
        """Collect RDS resources.

        Returns:
            List of RDS resources
        """
        resources = []
        account_id = self._get_account_id()

        # Collect DB instances
        resources.extend(self._collect_db_instances(account_id))

        # Collect DB clusters (Aurora)
        resources.extend(self._collect_db_clusters(account_id))

        self.logger.debug(f"Collected {len(resources)} RDS resources in {self.region}")
        return resources

    def _collect_db_instances(self, account_id: str) -> List[Resource]:
        """Collect RDS DB instances."""
        resources = []
        client = self._create_client()

        try:
            paginator = client.get_paginator("describe_db_instances")
            for page in paginator.paginate():
                for db_instance in page["DBInstances"]:
                    db_id = db_instance["DBInstanceIdentifier"]
                    db_arn = db_instance["DBInstanceArn"]

                    # Extract tags
                    tags = {}
                    try:
                        tag_response = client.list_tags_for_resource(ResourceName=db_arn)
                        tags = {tag["Key"]: tag["Value"] for tag in tag_response.get("TagList", [])}
                    except Exception as e:
                        self.logger.debug(f"Could not get tags for DB instance {db_id}: {e}")

                    # Create resource
                    resource = Resource(
                        arn=db_arn,
                        resource_type="AWS::RDS::DBInstance",
                        name=db_id,
                        region=self.region,
                        tags=tags,
                        config_hash=compute_config_hash(db_instance),
                        created_at=db_instance.get("InstanceCreateTime"),
                        raw_config=db_instance,
                    )
                    resources.append(resource)

        except Exception as e:
            self.logger.error(f"Error collecting RDS DB instances in {self.region}: {e}")

        return resources

    def _collect_db_clusters(self, account_id: str) -> List[Resource]:
        """Collect RDS DB clusters (Aurora)."""
        resources = []
        client = self._create_client()

        try:
            paginator = client.get_paginator("describe_db_clusters")
            for page in paginator.paginate():
                for db_cluster in page["DBClusters"]:
                    cluster_id = db_cluster["DBClusterIdentifier"]
                    cluster_arn = db_cluster["DBClusterArn"]

                    # Extract tags
                    tags = {}
                    try:
                        tag_response = client.list_tags_for_resource(ResourceName=cluster_arn)
                        tags = {tag["Key"]: tag["Value"] for tag in tag_response.get("TagList", [])}
                    except Exception as e:
                        self.logger.debug(f"Could not get tags for DB cluster {cluster_id}: {e}")

                    # Create resource
                    resource = Resource(
                        arn=cluster_arn,
                        resource_type="AWS::RDS::DBCluster",
                        name=cluster_id,
                        region=self.region,
                        tags=tags,
                        config_hash=compute_config_hash(db_cluster),
                        created_at=db_cluster.get("ClusterCreateTime"),
                        raw_config=db_cluster,
                    )
                    resources.append(resource)

        except Exception as e:
            self.logger.error(f"Error collecting RDS DB clusters in {self.region}: {e}")

        return resources
