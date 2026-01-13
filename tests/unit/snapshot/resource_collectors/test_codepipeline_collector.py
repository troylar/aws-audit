"""Tests for CodePipeline resource collector."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.snapshot.resource_collectors.codepipeline import CodePipelineCollector


@pytest.fixture
def mock_session():
    """Create a mock boto3 session."""
    session = MagicMock()
    session.profile_name = "default"
    return session


class TestCodePipelineCollectorProperties:
    """Tests for CodePipelineCollector properties."""

    def test_service_name(self, mock_session):
        """Test service_name property returns codepipeline."""
        collector = CodePipelineCollector(session=mock_session, region="us-east-1")
        assert collector.service_name == "codepipeline"


class TestCodePipelineCollectorCollect:
    """Tests for CodePipelineCollector.collect method."""

    @patch.object(CodePipelineCollector, "_create_client")
    def test_collect_no_pipelines(self, mock_create_client, mock_session):
        """Test collecting when no pipelines exist."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [{"pipelines": []}]
        mock_client.get_paginator.return_value = mock_paginator
        mock_create_client.return_value = mock_client

        collector = CodePipelineCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert resources == []
        mock_client.get_paginator.assert_called_once_with("list_pipelines")

    @patch.object(CodePipelineCollector, "_create_client")
    def test_collect_single_pipeline(self, mock_create_client, mock_session):
        """Test collecting a single pipeline."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [{"pipelines": [{"name": "my-pipeline"}]}]
        mock_client.get_paginator.return_value = mock_paginator

        created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
        mock_client.get_pipeline.return_value = {
            "pipeline": {
                "name": "my-pipeline",
                "version": 1,
                "stages": [{"name": "Source"}, {"name": "Build"}, {"name": "Deploy"}],
            },
            "metadata": {
                "pipelineArn": "arn:aws:codepipeline:us-east-1:123456789012:my-pipeline",
                "created": created_at,
            },
        }
        mock_client.list_tags_for_resource.return_value = {
            "tags": [{"key": "Environment", "value": "test"}]
        }
        mock_create_client.return_value = mock_client

        collector = CodePipelineCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 1
        assert resources[0].name == "my-pipeline"
        assert resources[0].resource_type == "AWS::CodePipeline::Pipeline"
        assert resources[0].region == "us-east-1"
        assert resources[0].tags == {"Environment": "test"}
        assert resources[0].created_at == created_at
        # Stages should be excluded but stageCount should be included
        assert "stages" not in resources[0].raw_config
        assert resources[0].raw_config["stageCount"] == 3

    @patch.object(CodePipelineCollector, "_create_client")
    def test_collect_multiple_pipelines(self, mock_create_client, mock_session):
        """Test collecting multiple pipelines."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [{
            "pipelines": [
                {"name": "pipeline-1"},
                {"name": "pipeline-2"},
            ]
        }]
        mock_client.get_paginator.return_value = mock_paginator

        mock_client.get_pipeline.return_value = {
            "pipeline": {"name": "test", "stages": []},
            "metadata": {"pipelineArn": "arn:test"},
        }
        mock_client.list_tags_for_resource.return_value = {"tags": []}
        mock_create_client.return_value = mock_client

        collector = CodePipelineCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 2

    @patch.object(CodePipelineCollector, "_create_client")
    def test_collect_with_pagination(self, mock_create_client, mock_session):
        """Test collecting with multiple pages."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [
            {"pipelines": [{"name": "pipeline-1"}]},
            {"pipelines": [{"name": "pipeline-2"}]},
        ]
        mock_client.get_paginator.return_value = mock_paginator

        mock_client.get_pipeline.return_value = {
            "pipeline": {"name": "test", "stages": []},
            "metadata": {"pipelineArn": "arn:test"},
        }
        mock_client.list_tags_for_resource.return_value = {"tags": []}
        mock_create_client.return_value = mock_client

        collector = CodePipelineCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 2

    @patch.object(CodePipelineCollector, "_create_client")
    def test_collect_handles_list_error(self, mock_create_client, mock_session):
        """Test collecting handles list_pipelines error."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.side_effect = Exception("Service unavailable")
        mock_client.get_paginator.return_value = mock_paginator
        mock_create_client.return_value = mock_client

        collector = CodePipelineCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert resources == []

    @patch.object(CodePipelineCollector, "_create_client")
    def test_collect_handles_get_pipeline_error(self, mock_create_client, mock_session):
        """Test collecting continues when get_pipeline fails."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [{
            "pipelines": [
                {"name": "good-pipeline"},
                {"name": "bad-pipeline"},
            ]
        }]
        mock_client.get_paginator.return_value = mock_paginator

        def get_pipeline_side_effect(name):
            if name == "bad-pipeline":
                raise Exception("Access denied")
            return {
                "pipeline": {"name": name, "stages": []},
                "metadata": {"pipelineArn": f"arn:{name}"},
            }

        mock_client.get_pipeline.side_effect = get_pipeline_side_effect
        mock_client.list_tags_for_resource.return_value = {"tags": []}
        mock_create_client.return_value = mock_client

        collector = CodePipelineCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        # Should only get the good pipeline
        assert len(resources) == 1
        assert resources[0].name == "good-pipeline"

    @patch.object(CodePipelineCollector, "_create_client")
    def test_collect_handles_tags_error(self, mock_create_client, mock_session):
        """Test collecting continues when list_tags_for_resource fails."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [{"pipelines": [{"name": "my-pipeline"}]}]
        mock_client.get_paginator.return_value = mock_paginator

        mock_client.get_pipeline.return_value = {
            "pipeline": {"name": "my-pipeline", "stages": []},
            "metadata": {"pipelineArn": "arn:test"},
        }
        mock_client.list_tags_for_resource.side_effect = Exception("Access denied")
        mock_create_client.return_value = mock_client

        collector = CodePipelineCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        # Should still get the pipeline without tags
        assert len(resources) == 1
        assert resources[0].tags == {}

    @patch.object(CodePipelineCollector, "_create_client")
    def test_collect_generates_config_hash(self, mock_create_client, mock_session):
        """Test that config hash is generated."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [{"pipelines": [{"name": "my-pipeline"}]}]
        mock_client.get_paginator.return_value = mock_paginator

        mock_client.get_pipeline.return_value = {
            "pipeline": {"name": "my-pipeline", "stages": []},
            "metadata": {"pipelineArn": "arn:test"},
        }
        mock_client.list_tags_for_resource.return_value = {"tags": []}
        mock_create_client.return_value = mock_client

        collector = CodePipelineCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 1
        assert resources[0].config_hash is not None
        assert len(resources[0].config_hash) > 0

    @patch.object(CodePipelineCollector, "_create_client")
    def test_collect_without_arn_in_metadata(self, mock_create_client, mock_session):
        """Test collecting pipeline when ARN is missing from metadata."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [{"pipelines": [{"name": "my-pipeline"}]}]
        mock_client.get_paginator.return_value = mock_paginator

        mock_client.get_pipeline.return_value = {
            "pipeline": {"name": "my-pipeline", "stages": []},
            "metadata": {},  # No pipelineArn
        }
        mock_create_client.return_value = mock_client

        collector = CodePipelineCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 1
        # Should use constructed ARN
        assert "my-pipeline" in resources[0].arn
        # Tags should be empty since we can't get them without ARN
        assert resources[0].tags == {}

    @patch.object(CodePipelineCollector, "_create_client")
    def test_collect_with_multiple_tags(self, mock_create_client, mock_session):
        """Test collecting pipeline with multiple tags."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [{"pipelines": [{"name": "my-pipeline"}]}]
        mock_client.get_paginator.return_value = mock_paginator

        mock_client.get_pipeline.return_value = {
            "pipeline": {"name": "my-pipeline", "stages": []},
            "metadata": {"pipelineArn": "arn:test"},
        }
        mock_client.list_tags_for_resource.return_value = {
            "tags": [
                {"key": "Environment", "value": "production"},
                {"key": "Team", "value": "platform"},
                {"key": "CostCenter", "value": "12345"},
            ]
        }
        mock_create_client.return_value = mock_client

        collector = CodePipelineCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 1
        assert resources[0].tags == {
            "Environment": "production",
            "Team": "platform",
            "CostCenter": "12345",
        }
