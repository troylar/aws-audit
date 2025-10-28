"""CodePipeline resource collector."""

from typing import List

from ...models.resource import Resource
from ...utils.hash import compute_config_hash
from .base import BaseResourceCollector


class CodePipelineCollector(BaseResourceCollector):
    """Collector for AWS CodePipeline resources."""

    @property
    def service_name(self) -> str:
        return "codepipeline"

    def collect(self) -> List[Resource]:
        """Collect CodePipeline pipelines.

        Returns:
            List of CodePipeline resources
        """
        resources = []
        client = self._create_client()

        try:
            paginator = client.get_paginator("list_pipelines")
            for page in paginator.paginate():
                for pipeline_summary in page.get("pipelines", []):
                    pipeline_name = pipeline_summary["name"]

                    try:
                        # Get detailed pipeline info
                        pipeline_response = client.get_pipeline(name=pipeline_name)
                        pipeline = pipeline_response.get("pipeline", {})
                        metadata = pipeline_response.get("metadata", {})

                        # Get tags
                        tags = {}
                        try:
                            # Build ARN for tags
                            pipeline_arn = metadata.get("pipelineArn", "")
                            if pipeline_arn:
                                tag_response = client.list_tags_for_resource(resourceArn=pipeline_arn)
                                for tag in tag_response.get("tags", []):
                                    tags[tag["key"]] = tag["value"]
                        except Exception as e:
                            self.logger.debug(f"Could not get tags for pipeline {pipeline_name}: {e}")

                        # Extract creation/update dates
                        created_at = metadata.get("created")

                        # Build ARN
                        arn = metadata.get(
                            "pipelineArn", f"arn:aws:codepipeline:{self.region}:*:pipeline/{pipeline_name}"
                        )

                        # Create resource (exclude large stage/action definitions for size)
                        config = {k: v for k, v in pipeline.items() if k not in ["stages"]}
                        config["stageCount"] = len(pipeline.get("stages", []))

                        resource = Resource(
                            arn=arn,
                            resource_type="AWS::CodePipeline::Pipeline",
                            name=pipeline_name,
                            region=self.region,
                            tags=tags,
                            config_hash=compute_config_hash(config),
                            created_at=created_at,
                            raw_config=config,
                        )
                        resources.append(resource)

                    except Exception as e:
                        self.logger.debug(f"Error processing pipeline {pipeline_name}: {e}")
                        continue

        except Exception as e:
            self.logger.error(f"Error collecting CodePipeline pipelines in {self.region}: {e}")

        self.logger.debug(f"Collected {len(resources)} CodePipeline pipelines in {self.region}")
        return resources
