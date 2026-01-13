"""Tests for SSM resource collector."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.snapshot.resource_collectors.ssm import SSMCollector


@pytest.fixture
def mock_session():
    """Create a mock boto3 session."""
    session = MagicMock()
    session.profile_name = "default"
    # Mock the STS client that's used to get account ID
    mock_sts = MagicMock()
    mock_sts.get_caller_identity.return_value = {"Account": "123456789012"}
    session.client.return_value = mock_sts
    return session


class TestSSMCollectorProperties:
    """Tests for SSMCollector properties."""

    def test_service_name(self, mock_session):
        """Test service_name property returns ssm."""
        collector = SSMCollector(session=mock_session, region="us-east-1")
        assert collector.service_name == "ssm"


class TestSSMCollectorCollect:
    """Tests for SSMCollector.collect method."""

    @patch.object(SSMCollector, "_create_client")
    def test_collect_no_resources(self, mock_create_client, mock_session):
        """Test collecting when no SSM resources exist."""
        mock_client = MagicMock()

        mock_params_paginator = MagicMock()
        mock_params_paginator.paginate.return_value = [{"Parameters": []}]

        mock_docs_paginator = MagicMock()
        mock_docs_paginator.paginate.return_value = [{"DocumentIdentifiers": []}]

        def get_paginator_side_effect(op):
            if op == "describe_parameters":
                return mock_params_paginator
            elif op == "list_documents":
                return mock_docs_paginator

        mock_client.get_paginator.side_effect = get_paginator_side_effect
        mock_create_client.return_value = mock_client

        collector = SSMCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert resources == []

    @patch.object(SSMCollector, "_create_client")
    def test_collect_single_parameter_string(self, mock_create_client, mock_session):
        """Test collecting a single string parameter."""
        mock_client = MagicMock()

        modified_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
        mock_params_paginator = MagicMock()
        mock_params_paginator.paginate.return_value = [{
            "Parameters": [{
                "Name": "/my/parameter",
                "Type": "String",
                "LastModifiedDate": modified_at,
            }]
        }]

        mock_docs_paginator = MagicMock()
        mock_docs_paginator.paginate.return_value = [{"DocumentIdentifiers": []}]

        def get_paginator_side_effect(op):
            if op == "describe_parameters":
                return mock_params_paginator
            elif op == "list_documents":
                return mock_docs_paginator

        mock_client.get_paginator.side_effect = get_paginator_side_effect
        mock_client.list_tags_for_resource.return_value = {
            "TagList": [{"Key": "Environment", "Value": "test"}]
        }
        mock_client.get_parameter.return_value = {
            "Parameter": {"Value": "my-value"}
        }
        mock_create_client.return_value = mock_client

        collector = SSMCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 1
        assert resources[0].name == "/my/parameter"
        assert resources[0].resource_type == "AWS::SSM::Parameter"
        assert resources[0].region == "us-east-1"
        assert resources[0].tags == {"Environment": "test"}
        assert resources[0].created_at == modified_at
        assert "123456789012" in resources[0].arn

    @patch.object(SSMCollector, "_create_client")
    def test_collect_secure_string_parameter(self, mock_create_client, mock_session):
        """Test collecting a SecureString parameter doesn't expose value."""
        mock_client = MagicMock()

        mock_params_paginator = MagicMock()
        mock_params_paginator.paginate.return_value = [{
            "Parameters": [{
                "Name": "/my/secret",
                "Type": "SecureString",
            }]
        }]

        mock_docs_paginator = MagicMock()
        mock_docs_paginator.paginate.return_value = [{"DocumentIdentifiers": []}]

        def get_paginator_side_effect(op):
            if op == "describe_parameters":
                return mock_params_paginator
            elif op == "list_documents":
                return mock_docs_paginator

        mock_client.get_paginator.side_effect = get_paginator_side_effect
        mock_client.list_tags_for_resource.return_value = {"TagList": []}
        mock_create_client.return_value = mock_client

        collector = SSMCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 1
        assert resources[0].name == "/my/secret"
        # Should not call get_parameter for SecureString
        mock_client.get_parameter.assert_not_called()

    @patch.object(SSMCollector, "_create_client")
    def test_collect_single_document(self, mock_create_client, mock_session):
        """Test collecting a single SSM document."""
        mock_client = MagicMock()

        mock_params_paginator = MagicMock()
        mock_params_paginator.paginate.return_value = [{"Parameters": []}]

        mock_docs_paginator = MagicMock()
        mock_docs_paginator.paginate.return_value = [{
            "DocumentIdentifiers": [{
                "Name": "my-document",
            }]
        }]

        def get_paginator_side_effect(op):
            if op == "describe_parameters":
                return mock_params_paginator
            elif op == "list_documents":
                return mock_docs_paginator

        mock_client.get_paginator.side_effect = get_paginator_side_effect

        created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
        mock_client.describe_document.return_value = {
            "Document": {
                "Name": "my-document",
                "DocumentArn": "arn:aws:ssm:us-east-1:123456789012:document/my-document",
                "CreatedDate": created_at,
                "Tags": [{"Key": "Team", "Value": "platform"}],
            }
        }
        mock_create_client.return_value = mock_client

        collector = SSMCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 1
        assert resources[0].name == "my-document"
        assert resources[0].resource_type == "AWS::SSM::Document"
        assert resources[0].tags == {"Team": "platform"}
        assert resources[0].created_at == created_at

    @patch.object(SSMCollector, "_create_client")
    def test_collect_parameters_and_documents(self, mock_create_client, mock_session):
        """Test collecting both parameters and documents."""
        mock_client = MagicMock()

        mock_params_paginator = MagicMock()
        mock_params_paginator.paginate.return_value = [{
            "Parameters": [{
                "Name": "/my/param",
                "Type": "String",
            }]
        }]

        mock_docs_paginator = MagicMock()
        mock_docs_paginator.paginate.return_value = [{
            "DocumentIdentifiers": [{
                "Name": "my-doc",
            }]
        }]

        def get_paginator_side_effect(op):
            if op == "describe_parameters":
                return mock_params_paginator
            elif op == "list_documents":
                return mock_docs_paginator

        mock_client.get_paginator.side_effect = get_paginator_side_effect
        mock_client.list_tags_for_resource.return_value = {"TagList": []}
        mock_client.get_parameter.return_value = {"Parameter": {}}
        mock_client.describe_document.return_value = {
            "Document": {
                "Name": "my-doc",
                "DocumentArn": "arn:1",
                "Tags": [],
            }
        }
        mock_create_client.return_value = mock_client

        collector = SSMCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 2
        resource_types = [r.resource_type for r in resources]
        assert "AWS::SSM::Parameter" in resource_types
        assert "AWS::SSM::Document" in resource_types

    @patch.object(SSMCollector, "_create_client")
    def test_collect_handles_parameter_tags_error(self, mock_create_client, mock_session):
        """Test collecting continues when parameter tags fail."""
        mock_client = MagicMock()

        mock_params_paginator = MagicMock()
        mock_params_paginator.paginate.return_value = [{
            "Parameters": [{
                "Name": "/my/param",
                "Type": "String",
            }]
        }]

        mock_docs_paginator = MagicMock()
        mock_docs_paginator.paginate.return_value = [{"DocumentIdentifiers": []}]

        def get_paginator_side_effect(op):
            if op == "describe_parameters":
                return mock_params_paginator
            elif op == "list_documents":
                return mock_docs_paginator

        mock_client.get_paginator.side_effect = get_paginator_side_effect
        mock_client.list_tags_for_resource.side_effect = Exception("Access denied")
        mock_client.get_parameter.return_value = {"Parameter": {}}
        mock_create_client.return_value = mock_client

        collector = SSMCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 1
        assert resources[0].tags == {}

    @patch.object(SSMCollector, "_create_client")
    def test_collect_handles_get_parameter_error(self, mock_create_client, mock_session):
        """Test collecting continues when get_parameter fails."""
        mock_client = MagicMock()

        mock_params_paginator = MagicMock()
        mock_params_paginator.paginate.return_value = [{
            "Parameters": [{
                "Name": "/my/param",
                "Type": "String",
            }]
        }]

        mock_docs_paginator = MagicMock()
        mock_docs_paginator.paginate.return_value = [{"DocumentIdentifiers": []}]

        def get_paginator_side_effect(op):
            if op == "describe_parameters":
                return mock_params_paginator
            elif op == "list_documents":
                return mock_docs_paginator

        mock_client.get_paginator.side_effect = get_paginator_side_effect
        mock_client.list_tags_for_resource.return_value = {"TagList": []}
        mock_client.get_parameter.side_effect = Exception("Access denied")
        mock_create_client.return_value = mock_client

        collector = SSMCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        # Should still get the parameter with basic info
        assert len(resources) == 1

    @patch.object(SSMCollector, "_create_client")
    def test_collect_handles_describe_parameters_error(self, mock_create_client, mock_session):
        """Test collecting handles describe_parameters error."""
        mock_client = MagicMock()

        mock_params_paginator = MagicMock()
        mock_params_paginator.paginate.side_effect = Exception("Service unavailable")

        mock_docs_paginator = MagicMock()
        mock_docs_paginator.paginate.return_value = [{"DocumentIdentifiers": []}]

        def get_paginator_side_effect(op):
            if op == "describe_parameters":
                return mock_params_paginator
            elif op == "list_documents":
                return mock_docs_paginator

        mock_client.get_paginator.side_effect = get_paginator_side_effect
        mock_create_client.return_value = mock_client

        collector = SSMCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        # Should still work (no parameters but might have documents)
        assert resources == []

    @patch.object(SSMCollector, "_create_client")
    def test_collect_handles_describe_document_error(self, mock_create_client, mock_session):
        """Test collecting continues when describe_document fails."""
        mock_client = MagicMock()

        mock_params_paginator = MagicMock()
        mock_params_paginator.paginate.return_value = [{"Parameters": []}]

        mock_docs_paginator = MagicMock()
        mock_docs_paginator.paginate.return_value = [{
            "DocumentIdentifiers": [{"Name": "my-doc"}]
        }]

        def get_paginator_side_effect(op):
            if op == "describe_parameters":
                return mock_params_paginator
            elif op == "list_documents":
                return mock_docs_paginator

        mock_client.get_paginator.side_effect = get_paginator_side_effect
        mock_client.describe_document.side_effect = Exception("Access denied")
        mock_create_client.return_value = mock_client

        collector = SSMCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        # Should skip the document that failed
        assert resources == []

    @patch.object(SSMCollector, "_create_client")
    def test_collect_handles_list_documents_error(self, mock_create_client, mock_session):
        """Test collecting handles list_documents error."""
        mock_client = MagicMock()

        mock_params_paginator = MagicMock()
        mock_params_paginator.paginate.return_value = [{"Parameters": []}]

        mock_docs_paginator = MagicMock()
        mock_docs_paginator.paginate.side_effect = Exception("Service unavailable")

        def get_paginator_side_effect(op):
            if op == "describe_parameters":
                return mock_params_paginator
            elif op == "list_documents":
                return mock_docs_paginator

        mock_client.get_paginator.side_effect = get_paginator_side_effect
        mock_create_client.return_value = mock_client

        collector = SSMCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        # Should still work (no documents)
        assert resources == []

    @patch.object(SSMCollector, "_create_client")
    def test_collect_document_without_arn(self, mock_create_client, mock_session):
        """Test collecting document without DocumentArn in response."""
        mock_client = MagicMock()

        mock_params_paginator = MagicMock()
        mock_params_paginator.paginate.return_value = [{"Parameters": []}]

        mock_docs_paginator = MagicMock()
        mock_docs_paginator.paginate.return_value = [{
            "DocumentIdentifiers": [{"Name": "my-doc"}]
        }]

        def get_paginator_side_effect(op):
            if op == "describe_parameters":
                return mock_params_paginator
            elif op == "list_documents":
                return mock_docs_paginator

        mock_client.get_paginator.side_effect = get_paginator_side_effect
        mock_client.describe_document.return_value = {
            "Document": {
                "Name": "my-doc",
                # No DocumentArn field
                "Tags": [],
            }
        }
        mock_create_client.return_value = mock_client

        collector = SSMCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 1
        # Should use name as ARN
        assert resources[0].arn == "my-doc"
