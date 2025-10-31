"""EKS resource collector."""

from typing import List, Tuple

from ...models.resource import Resource
from ...utils.hash import compute_config_hash
from .base import BaseResourceCollector


class EKSCollector(BaseResourceCollector):
    """Collector for Amazon EKS (Elastic Kubernetes Service) resources."""

    @property
    def service_name(self) -> str:
        return "eks"

    def collect(self) -> List[Resource]:
        """Collect EKS resources.

        Collects:
        - EKS Clusters
        - Node Groups (within each cluster)
        - Fargate Profiles (within each cluster)

        Returns:
            List of EKS resources
        """
        resources = []

        # Collect clusters
        cluster_resources, cluster_names = self._collect_clusters()
        resources.extend(cluster_resources)

        # Collect node groups for each cluster
        resources.extend(self._collect_node_groups(cluster_names))

        # Collect Fargate profiles for each cluster
        resources.extend(self._collect_fargate_profiles(cluster_names))

        self.logger.debug(f"Collected {len(resources)} EKS resources in {self.region}")
        return resources

    def _collect_clusters(self) -> Tuple[List[Resource], List[str]]:  # type: ignore
        """Collect EKS clusters.

        Returns:
            Tuple of (list of cluster resources, list of cluster names)
        """
        resources = []
        cluster_names = []
        client = self._create_client()

        try:
            paginator = client.get_paginator("list_clusters")
            for page in paginator.paginate():
                for cluster_name in page.get("clusters", []):
                    cluster_names.append(cluster_name)

                    try:
                        # Get detailed cluster info
                        cluster_response = client.describe_cluster(name=cluster_name)
                        cluster = cluster_response.get("cluster", {})

                        cluster_arn = cluster.get("arn", "")

                        # Extract tags
                        tags = cluster.get("tags", {})

                        # Extract creation date
                        created_at = cluster.get("createdAt")

                        # Create resource
                        resource = Resource(
                            arn=cluster_arn,
                            resource_type="AWS::EKS::Cluster",
                            name=cluster_name,
                            region=self.region,
                            tags=tags,
                            config_hash=compute_config_hash(cluster),
                            created_at=created_at,
                            raw_config=cluster,
                        )
                        resources.append(resource)

                    except Exception as e:
                        self.logger.debug(f"Error processing cluster {cluster_name}: {e}")
                        continue

        except Exception as e:
            self.logger.error(f"Error collecting EKS clusters in {self.region}: {e}")

        return resources, cluster_names

    def _collect_node_groups(self, cluster_names: List[str]) -> List[Resource]:
        """Collect EKS node groups for given clusters.

        Args:
            cluster_names: List of cluster names to collect node groups from

        Returns:
            List of node group resources
        """
        resources = []
        client = self._create_client()

        for cluster_name in cluster_names:
            try:
                paginator = client.get_paginator("list_nodegroups")
                for page in paginator.paginate(clusterName=cluster_name):
                    for nodegroup_name in page.get("nodegroups", []):
                        try:
                            # Get detailed node group info
                            ng_response = client.describe_nodegroup(
                                clusterName=cluster_name, nodegroupName=nodegroup_name
                            )
                            nodegroup = ng_response.get("nodegroup", {})

                            ng_arn = nodegroup.get("nodegroupArn", "")

                            # Extract tags
                            tags = nodegroup.get("tags", {})

                            # Extract creation date
                            created_at = nodegroup.get("createdAt")

                            # Create resource
                            resource = Resource(
                                arn=ng_arn,
                                resource_type="AWS::EKS::Nodegroup",
                                name=f"{cluster_name}/{nodegroup_name}",
                                region=self.region,
                                tags=tags,
                                config_hash=compute_config_hash(nodegroup),
                                created_at=created_at,
                                raw_config=nodegroup,
                            )
                            resources.append(resource)

                        except Exception as e:
                            self.logger.debug(f"Error processing node group {nodegroup_name}: {e}")
                            continue

            except Exception as e:
                self.logger.debug(f"Error collecting node groups for cluster {cluster_name}: {e}")

        return resources

    def _collect_fargate_profiles(self, cluster_names: List[str]) -> List[Resource]:
        """Collect EKS Fargate profiles for given clusters.

        Args:
            cluster_names: List of cluster names to collect Fargate profiles from

        Returns:
            List of Fargate profile resources
        """
        resources = []
        client = self._create_client()

        for cluster_name in cluster_names:
            try:
                paginator = client.get_paginator("list_fargate_profiles")
                for page in paginator.paginate(clusterName=cluster_name):
                    for profile_name in page.get("fargateProfileNames", []):
                        try:
                            # Get detailed Fargate profile info
                            profile_response = client.describe_fargate_profile(
                                clusterName=cluster_name, fargateProfileName=profile_name
                            )
                            profile = profile_response.get("fargateProfile", {})

                            profile_arn = profile.get("fargateProfileArn", "")

                            # Extract tags
                            tags = profile.get("tags", {})

                            # Extract creation date
                            created_at = profile.get("createdAt")

                            # Create resource
                            resource = Resource(
                                arn=profile_arn,
                                resource_type="AWS::EKS::FargateProfile",
                                name=f"{cluster_name}/{profile_name}",
                                region=self.region,
                                tags=tags,
                                config_hash=compute_config_hash(profile),
                                created_at=created_at,
                                raw_config=profile,
                            )
                            resources.append(resource)

                        except Exception as e:
                            self.logger.debug(f"Error processing Fargate profile {profile_name}: {e}")
                            continue

            except Exception as e:
                self.logger.debug(f"Error collecting Fargate profiles for cluster {cluster_name}: {e}")

        return resources
