"""ECS resource collector."""

from typing import List

from ...models.resource import Resource
from ...utils.hash import compute_config_hash
from .base import BaseResourceCollector


class ECSCollector(BaseResourceCollector):
    """Collector for Amazon ECS (Elastic Container Service) resources."""

    @property
    def service_name(self) -> str:
        return "ecs"

    def collect(self) -> List[Resource]:
        """Collect ECS resources.

        Collects:
        - ECS Clusters
        - ECS Services (within each cluster)
        - ECS Task Definitions (active revisions)

        Returns:
            List of ECS resources
        """
        resources = []

        self._report_progress("clusters")
        resources.extend(self._collect_clusters())

        self._report_progress("services")
        resources.extend(self._collect_services())

        self._report_progress("task-definitions")
        resources.extend(self._collect_task_definitions())

        self.logger.debug(f"Collected {len(resources)} ECS resources in {self.region}")
        return resources

    def _collect_clusters(self) -> List[Resource]:
        """Collect ECS clusters.

        Returns:
            List of ECS cluster resources
        """
        resources = []
        client = self._create_client()

        try:
            paginator = client.get_paginator("list_clusters")
            for page in paginator.paginate():
                cluster_arns = page.get("clusterArns", [])

                if not cluster_arns:
                    continue

                # Get detailed info for clusters (in batches of 100)
                for i in range(0, len(cluster_arns), 100):
                    batch = cluster_arns[i : i + 100]
                    try:
                        response = client.describe_clusters(clusters=batch, include=["TAGS"])
                        for cluster in response.get("clusters", []):
                            cluster_name = cluster["clusterName"]
                            cluster_arn = cluster["clusterArn"]

                            # Extract tags
                            tags = {}
                            for tag in cluster.get("tags", []):
                                tags[tag["key"]] = tag["value"]

                            # Extract creation timestamp (not always available)
                            created_at = None

                            # Create resource
                            resource = Resource(
                                arn=cluster_arn,
                                resource_type="AWS::ECS::Cluster",
                                name=cluster_name,
                                region=self.region,
                                tags=tags,
                                config_hash=compute_config_hash(cluster),
                                created_at=created_at,
                                raw_config=cluster,
                            )
                            resources.append(resource)

                    except Exception as e:
                        self.logger.debug(f"Error describing cluster batch: {e}")

        except Exception as e:
            self.logger.error(f"Error collecting ECS clusters in {self.region}: {e}")

        return resources

    def _collect_services(self) -> List[Resource]:
        """Collect ECS services across all clusters.

        Returns:
            List of ECS service resources
        """
        resources = []
        client = self._create_client()

        try:
            # First, get all clusters
            cluster_arns = []
            paginator = client.get_paginator("list_clusters")
            for page in paginator.paginate():
                cluster_arns.extend(page.get("clusterArns", []))

            # Collect services from each cluster
            for cluster_arn in cluster_arns:
                try:
                    service_paginator = client.get_paginator("list_services")
                    service_arns = []
                    for page in service_paginator.paginate(cluster=cluster_arn):
                        service_arns.extend(page.get("serviceArns", []))

                    if not service_arns:
                        continue

                    # Get detailed info for services (in batches of 10)
                    for i in range(0, len(service_arns), 10):
                        batch = service_arns[i : i + 10]
                        try:
                            response = client.describe_services(cluster=cluster_arn, services=batch, include=["TAGS"])
                            for service in response.get("services", []):
                                service_name = service["serviceName"]
                                service_arn = service["serviceArn"]

                                # Extract tags
                                tags = {}
                                for tag in service.get("tags", []):
                                    tags[tag["key"]] = tag["value"]

                                # Extract creation date
                                created_at = service.get("createdAt")

                                # Create resource
                                resource = Resource(
                                    arn=service_arn,
                                    resource_type="AWS::ECS::Service",
                                    name=service_name,
                                    region=self.region,
                                    tags=tags,
                                    config_hash=compute_config_hash(service),
                                    created_at=created_at,
                                    raw_config=service,
                                )
                                resources.append(resource)

                        except Exception as e:
                            self.logger.debug(f"Error describing service batch: {e}")

                except Exception as e:
                    self.logger.debug(f"Error collecting services from cluster {cluster_arn}: {e}")

        except Exception as e:
            self.logger.error(f"Error collecting ECS services in {self.region}: {e}")

        return resources

    def _collect_task_definitions(self) -> List[Resource]:
        """Collect ECS task definitions (active revisions only).

        Returns:
            List of ECS task definition resources
        """
        client = self._create_client()

        try:
            # First list all task definition ARNs
            task_def_arns = []
            paginator = client.get_paginator("list_task_definitions")
            for page in paginator.paginate(status="ACTIVE"):
                task_def_arns.extend(page.get("taskDefinitionArns", []))

            if not task_def_arns:
                return []

            # Describe each task definition in parallel
            from concurrent.futures import ThreadPoolExecutor
            from typing import Optional

            def _describe_task_def(task_def_arn: str) -> Optional[Resource]:
                try:
                    response = client.describe_task_definition(taskDefinition=task_def_arn, include=["TAGS"])
                    task_def = response.get("taskDefinition", {})

                    family = task_def.get("family", "unknown")
                    revision = task_def.get("revision", 0)
                    name = f"{family}:{revision}"

                    tags = {}
                    for tag in response.get("tags", []):
                        tags[tag["key"]] = tag["value"]

                    return Resource(
                        arn=task_def_arn,
                        resource_type="AWS::ECS::TaskDefinition",
                        name=name,
                        region=self.region,
                        tags=tags,
                        config_hash=compute_config_hash(task_def),
                        created_at=None,
                        raw_config=task_def,
                    )

                except Exception as e:
                    self.logger.debug(f"Error describing task definition {task_def_arn}: {e}")
                    return None

            resources: list = []
            with ThreadPoolExecutor(max_workers=min(10, len(task_def_arns))) as executor:
                for resource in executor.map(_describe_task_def, task_def_arns):
                    if resource:
                        resources.append(resource)

            return resources

        except Exception as e:
            self.logger.error(f"Error collecting ECS task definitions in {self.region}: {e}")
            return []
