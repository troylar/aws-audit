"""CodeBuild resource collector."""

from typing import List

from ...models.resource import Resource
from ...utils.hash import compute_config_hash
from .base import BaseResourceCollector


class CodeBuildCollector(BaseResourceCollector):
    """Collector for AWS CodeBuild resources."""

    @property
    def service_name(self) -> str:
        return "codebuild"

    def collect(self) -> List[Resource]:
        """Collect CodeBuild projects.

        Returns:
            List of CodeBuild project resources
        """
        resources = []
        client = self._create_client()

        try:
            paginator = client.get_paginator("list_projects")
            project_names = []
            for page in paginator.paginate():
                project_names.extend(page.get("projects", []))

            # Get detailed info for projects (in batches of 100)
            for i in range(0, len(project_names), 100):
                batch = project_names[i : i + 100]
                try:
                    response = client.batch_get_projects(names=batch)
                    for project in response.get("projects", []):
                        project_name = project["name"]
                        project_arn = project["arn"]

                        # Extract tags
                        tags = {}
                        for tag in project.get("tags", []):
                            tags[tag["key"]] = tag["value"]

                        # Extract creation date
                        created_at = project.get("created")

                        # Create resource
                        resource = Resource(
                            arn=project_arn,
                            resource_type="AWS::CodeBuild::Project",
                            name=project_name,
                            region=self.region,
                            tags=tags,
                            config_hash=compute_config_hash(project),
                            created_at=created_at,
                            raw_config=project,
                        )
                        resources.append(resource)

                except Exception as e:
                    self.logger.debug(f"Error processing project batch: {e}")

        except Exception as e:
            self.logger.error(f"Error collecting CodeBuild projects in {self.region}: {e}")

        self.logger.debug(f"Collected {len(resources)} CodeBuild projects in {self.region}")
        return resources
