"""Tests for Step Functions resource collector."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.snapshot.resource_collectors.stepfunctions import StepFunctionsCollector


@pytest.fixture
def mock_session():
    """Create a mock boto3 session."""
    session = MagicMock()
    session.profile_name = "default"
    return session


class TestStepFunctionsCollectorProperties:
    """Tests for StepFunctionsCollector properties."""

    def test_service_name(self, mock_session):
        """Test service_name property returns stepfunctions."""
        collector = StepFunctionsCollector(session=mock_session, region="us-east-1")
        assert collector.service_name == "stepfunctions"


class TestStepFunctionsCollectorCollect:
    """Tests for StepFunctionsCollector.collect method."""

    @patch.object(StepFunctionsCollector, "_create_client")
    def test_collect_no_state_machines(self, mock_create_client, mock_session):
        """Test collecting when no state machines exist."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [{"stateMachines": []}]
        mock_client.get_paginator.return_value = mock_paginator
        mock_create_client.return_value = mock_client

        collector = StepFunctionsCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert resources == []
        mock_client.get_paginator.assert_called_once_with("list_state_machines")

    @patch.object(StepFunctionsCollector, "_create_client")
    def test_collect_single_state_machine(self, mock_create_client, mock_session):
        """Test collecting a single state machine."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
        mock_paginator.paginate.return_value = [
            {
                "stateMachines": [
                    {
                        "stateMachineArn": "arn:aws:states:us-east-1:123456789012:stateMachine:my-workflow",
                        "name": "my-workflow",
                    }
                ]
            }
        ]
        mock_client.get_paginator.return_value = mock_paginator
        mock_client.describe_state_machine.return_value = {
            "stateMachineArn": "arn:aws:states:us-east-1:123456789012:stateMachine:my-workflow",
            "name": "my-workflow",
            "status": "ACTIVE",
            "creationDate": created_at,
            "definition": '{"States": {}}',  # This should be excluded from raw_config
        }
        mock_client.list_tags_for_resource.return_value = {"tags": [{"key": "Environment", "value": "test"}]}
        mock_create_client.return_value = mock_client

        collector = StepFunctionsCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 1
        assert resources[0].name == "my-workflow"
        assert resources[0].resource_type == "AWS::StepFunctions::StateMachine"
        assert resources[0].region == "us-east-1"
        assert resources[0].tags == {"Environment": "test"}
        assert resources[0].created_at == created_at
        # Definition should not be in raw_config
        assert "definition" not in resources[0].raw_config

    @patch.object(StepFunctionsCollector, "_create_client")
    def test_collect_multiple_state_machines(self, mock_create_client, mock_session):
        """Test collecting multiple state machines."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [
            {
                "stateMachines": [
                    {"stateMachineArn": "arn:1", "name": "workflow-1"},
                    {"stateMachineArn": "arn:2", "name": "workflow-2"},
                ]
            }
        ]
        mock_client.get_paginator.return_value = mock_paginator
        mock_client.describe_state_machine.return_value = {
            "status": "ACTIVE",
        }
        mock_client.list_tags_for_resource.return_value = {"tags": []}
        mock_create_client.return_value = mock_client

        collector = StepFunctionsCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 2
        assert resources[0].name == "workflow-1"
        assert resources[1].name == "workflow-2"

    @patch.object(StepFunctionsCollector, "_create_client")
    def test_collect_handles_describe_error(self, mock_create_client, mock_session):
        """Test collecting continues when describe_state_machine fails."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [
            {
                "stateMachines": [
                    {
                        "stateMachineArn": "arn:aws:states:us-east-1:123456789012:stateMachine:good-workflow",
                        "name": "good-workflow",
                    },
                    {
                        "stateMachineArn": "arn:aws:states:us-east-1:123456789012:stateMachine:bad-workflow",
                        "name": "bad-workflow",
                    },
                ]
            }
        ]
        mock_client.get_paginator.return_value = mock_paginator

        def describe_side_effect(**kwargs):
            if "bad-workflow" in kwargs["stateMachineArn"]:
                raise Exception("Access denied")
            return {"status": "ACTIVE"}

        mock_client.describe_state_machine.side_effect = describe_side_effect
        mock_client.list_tags_for_resource.return_value = {"tags": []}
        mock_create_client.return_value = mock_client

        collector = StepFunctionsCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        # Should only get the good workflow
        assert len(resources) == 1
        assert resources[0].name == "good-workflow"

    @patch.object(StepFunctionsCollector, "_create_client")
    def test_collect_handles_tags_error(self, mock_create_client, mock_session):
        """Test collecting continues when list_tags_for_resource fails."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [
            {
                "stateMachines": [
                    {
                        "stateMachineArn": "arn:1",
                        "name": "my-workflow",
                    }
                ]
            }
        ]
        mock_client.get_paginator.return_value = mock_paginator
        mock_client.describe_state_machine.return_value = {"status": "ACTIVE"}
        mock_client.list_tags_for_resource.side_effect = Exception("Access denied")
        mock_create_client.return_value = mock_client

        collector = StepFunctionsCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        # Should still get the workflow without tags
        assert len(resources) == 1
        assert resources[0].tags == {}

    @patch.object(StepFunctionsCollector, "_create_client")
    def test_collect_handles_list_error(self, mock_create_client, mock_session):
        """Test collecting handles list_state_machines error."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.side_effect = Exception("Service unavailable")
        mock_client.get_paginator.return_value = mock_paginator
        mock_create_client.return_value = mock_client

        collector = StepFunctionsCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        # Should return empty list on error
        assert resources == []

    @patch.object(StepFunctionsCollector, "_create_client")
    def test_collect_with_pagination(self, mock_create_client, mock_session):
        """Test collecting with multiple pages."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [
            {"stateMachines": [{"stateMachineArn": "arn:1", "name": "workflow-1"}]},
            {"stateMachines": [{"stateMachineArn": "arn:2", "name": "workflow-2"}]},
        ]
        mock_client.get_paginator.return_value = mock_paginator
        mock_client.describe_state_machine.return_value = {"status": "ACTIVE"}
        mock_client.list_tags_for_resource.return_value = {"tags": []}
        mock_create_client.return_value = mock_client

        collector = StepFunctionsCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 2

    @patch.object(StepFunctionsCollector, "_create_client")
    def test_collect_generates_config_hash(self, mock_create_client, mock_session):
        """Test that config hash is generated."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [
            {
                "stateMachines": [
                    {
                        "stateMachineArn": "arn:1",
                        "name": "my-workflow",
                    }
                ]
            }
        ]
        mock_client.get_paginator.return_value = mock_paginator
        mock_client.describe_state_machine.return_value = {"status": "ACTIVE"}
        mock_client.list_tags_for_resource.return_value = {"tags": []}
        mock_create_client.return_value = mock_client

        collector = StepFunctionsCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 1
        assert resources[0].config_hash is not None
        assert len(resources[0].config_hash) > 0
