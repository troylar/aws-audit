"""Tests for CodeBuild resource collector."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.snapshot.resource_collectors.codebuild import CodeBuildCollector


@pytest.fixture
def mock_session():
    """Create a mock boto3 session."""
    session = MagicMock()
    session.profile_name = "default"
    return session


class TestCodeBuildCollectorProperties:
    """Tests for CodeBuildCollector properties."""

    def test_service_name(self, mock_session):
        """Test service_name property returns codebuild."""
        collector = CodeBuildCollector(session=mock_session, region="us-east-1")
        assert collector.service_name == "codebuild"


class TestCodeBuildCollectorCollect:
    """Tests for CodeBuildCollector.collect method."""

    @patch.object(CodeBuildCollector, "_create_client")
    def test_collect_no_projects(self, mock_create_client, mock_session):
        """Test collecting when no projects exist."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [{"projects": []}]
        mock_client.get_paginator.return_value = mock_paginator
        mock_create_client.return_value = mock_client

        collector = CodeBuildCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert resources == []
        mock_client.get_paginator.assert_called_once_with("list_projects")

    @patch.object(CodeBuildCollector, "_create_client")
    def test_collect_single_project(self, mock_create_client, mock_session):
        """Test collecting a single project."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [{"projects": ["my-project"]}]
        mock_client.get_paginator.return_value = mock_paginator

        created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
        mock_client.batch_get_projects.return_value = {
            "projects": [
                {
                    "name": "my-project",
                    "arn": "arn:aws:codebuild:us-east-1:123456789012:project/my-project",
                    "created": created_at,
                    "tags": [{"key": "Environment", "value": "test"}],
                }
            ]
        }
        mock_create_client.return_value = mock_client

        collector = CodeBuildCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 1
        assert resources[0].name == "my-project"
        assert resources[0].resource_type == "AWS::CodeBuild::Project"
        assert resources[0].region == "us-east-1"
        assert resources[0].tags == {"Environment": "test"}
        assert resources[0].created_at == created_at
        assert "my-project" in resources[0].arn

    @patch.object(CodeBuildCollector, "_create_client")
    def test_collect_multiple_projects(self, mock_create_client, mock_session):
        """Test collecting multiple projects."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [{"projects": ["project-1", "project-2", "project-3"]}]
        mock_client.get_paginator.return_value = mock_paginator

        mock_client.batch_get_projects.return_value = {
            "projects": [
                {"name": "project-1", "arn": "arn:1", "tags": []},
                {"name": "project-2", "arn": "arn:2", "tags": []},
                {"name": "project-3", "arn": "arn:3", "tags": []},
            ]
        }
        mock_create_client.return_value = mock_client

        collector = CodeBuildCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 3
        assert resources[0].name == "project-1"
        assert resources[1].name == "project-2"
        assert resources[2].name == "project-3"

    @patch.object(CodeBuildCollector, "_create_client")
    def test_collect_with_pagination(self, mock_create_client, mock_session):
        """Test collecting with multiple pages."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [
            {"projects": ["project-1"]},
            {"projects": ["project-2"]},
        ]
        mock_client.get_paginator.return_value = mock_paginator

        mock_client.batch_get_projects.return_value = {
            "projects": [
                {"name": "project-1", "arn": "arn:1", "tags": []},
                {"name": "project-2", "arn": "arn:2", "tags": []},
            ]
        }
        mock_create_client.return_value = mock_client

        collector = CodeBuildCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 2

    @patch.object(CodeBuildCollector, "_create_client")
    def test_collect_batches_over_100_projects(self, mock_create_client, mock_session):
        """Test that projects are batched in groups of 100."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        # Create 150 project names
        project_names = [f"project-{i}" for i in range(150)]
        mock_paginator.paginate.return_value = [{"projects": project_names}]
        mock_client.get_paginator.return_value = mock_paginator

        def batch_get_side_effect(names):
            return {"projects": [{"name": name, "arn": f"arn:{name}", "tags": []} for name in names]}

        mock_client.batch_get_projects.side_effect = batch_get_side_effect
        mock_create_client.return_value = mock_client

        collector = CodeBuildCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 150
        # Should have been called twice (100 + 50)
        assert mock_client.batch_get_projects.call_count == 2

    @patch.object(CodeBuildCollector, "_create_client")
    def test_collect_handles_list_error(self, mock_create_client, mock_session):
        """Test collecting handles list_projects error."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.side_effect = Exception("Service unavailable")
        mock_client.get_paginator.return_value = mock_paginator
        mock_create_client.return_value = mock_client

        collector = CodeBuildCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        # Should return empty list on error
        assert resources == []

    @patch.object(CodeBuildCollector, "_create_client")
    def test_collect_handles_batch_get_error(self, mock_create_client, mock_session):
        """Test collecting continues when batch_get_projects fails."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [{"projects": ["project-1"]}]
        mock_client.get_paginator.return_value = mock_paginator
        mock_client.batch_get_projects.side_effect = Exception("Access denied")
        mock_create_client.return_value = mock_client

        collector = CodeBuildCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        # Should return empty list when batch get fails
        assert resources == []

    @patch.object(CodeBuildCollector, "_create_client")
    def test_collect_generates_config_hash(self, mock_create_client, mock_session):
        """Test that config hash is generated."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [{"projects": ["my-project"]}]
        mock_client.get_paginator.return_value = mock_paginator

        mock_client.batch_get_projects.return_value = {
            "projects": [
                {
                    "name": "my-project",
                    "arn": "arn:aws:codebuild:us-east-1:123456789012:project/my-project",
                    "tags": [],
                }
            ]
        }
        mock_create_client.return_value = mock_client

        collector = CodeBuildCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 1
        assert resources[0].config_hash is not None
        assert len(resources[0].config_hash) > 0

    @patch.object(CodeBuildCollector, "_create_client")
    def test_collect_project_without_tags(self, mock_create_client, mock_session):
        """Test collecting project with no tags."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [{"projects": ["my-project"]}]
        mock_client.get_paginator.return_value = mock_paginator

        mock_client.batch_get_projects.return_value = {
            "projects": [
                {
                    "name": "my-project",
                    "arn": "arn:aws:codebuild:us-east-1:123456789012:project/my-project",
                    # No tags key
                }
            ]
        }
        mock_create_client.return_value = mock_client

        collector = CodeBuildCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 1
        assert resources[0].tags == {}

    @patch.object(CodeBuildCollector, "_create_client")
    def test_collect_project_without_created_date(self, mock_create_client, mock_session):
        """Test collecting project with no created date."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [{"projects": ["my-project"]}]
        mock_client.get_paginator.return_value = mock_paginator

        mock_client.batch_get_projects.return_value = {
            "projects": [
                {
                    "name": "my-project",
                    "arn": "arn:aws:codebuild:us-east-1:123456789012:project/my-project",
                    "tags": [],
                    # No created key
                }
            ]
        }
        mock_create_client.return_value = mock_client

        collector = CodeBuildCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 1
        assert resources[0].created_at is None

    @patch.object(CodeBuildCollector, "_create_client")
    def test_collect_with_multiple_tags(self, mock_create_client, mock_session):
        """Test collecting project with multiple tags."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [{"projects": ["my-project"]}]
        mock_client.get_paginator.return_value = mock_paginator

        mock_client.batch_get_projects.return_value = {
            "projects": [
                {
                    "name": "my-project",
                    "arn": "arn:aws:codebuild:us-east-1:123456789012:project/my-project",
                    "tags": [
                        {"key": "Environment", "value": "production"},
                        {"key": "Team", "value": "platform"},
                        {"key": "CostCenter", "value": "12345"},
                    ],
                }
            ]
        }
        mock_create_client.return_value = mock_client

        collector = CodeBuildCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 1
        assert resources[0].tags == {
            "Environment": "production",
            "Team": "platform",
            "CostCenter": "12345",
        }
