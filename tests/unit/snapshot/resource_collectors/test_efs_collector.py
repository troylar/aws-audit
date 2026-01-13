"""Unit tests for EFSCollector."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, Mock, patch

import boto3
import pytest
from botocore.exceptions import ClientError

from src.snapshot.resource_collectors.efs_collector import EFSCollector


class TestEFSCollector:
    """Tests for EFSCollector."""

    @pytest.fixture
    def mock_session(self) -> Mock:
        """Create a mock boto3 session."""
        session = Mock(spec=boto3.Session)
        session.profile_name = "test-profile"
        return session

    @pytest.fixture
    def collector(self, mock_session: Mock) -> EFSCollector:
        """Create an EFSCollector instance."""
        return EFSCollector(session=mock_session, region="us-east-1")

    def test_service_name(self, collector: EFSCollector) -> None:
        """Test that service_name returns 'efs'."""
        assert collector.service_name == "efs"

    def test_is_not_global_service(self, collector: EFSCollector) -> None:
        """Test that EFS is not a global service."""
        assert collector.is_global_service is False

    @patch("src.snapshot.resource_collectors.efs_collector.EFSCollector._create_client")
    def test_collect_with_single_file_system(self, mock_create_client: Mock, collector: EFSCollector) -> None:
        """Test collecting a single EFS file system."""
        # Setup mock client
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        # Mock paginator
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator

        created_time = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)

        # Mock file system response
        mock_paginator.paginate.return_value = [
            {
                "FileSystems": [
                    {
                        "FileSystemId": "fs-12345678",
                        "FileSystemArn": "arn:aws:elasticfilesystem:us-east-1:123456789012:file-system/fs-12345678",
                        "CreationTime": created_time,
                        "LifeCycleState": "available",
                        "PerformanceMode": "generalPurpose",
                        "Encrypted": True,
                        "KmsKeyId": "arn:aws:kms:us-east-1:123456789012:key/abcd1234",
                        "Tags": [
                            {"Key": "Environment", "Value": "prod"},
                            {"Key": "Owner", "Value": "team-a"},
                        ],
                    }
                ]
            }
        ]

        # Execute
        resources = collector.collect()

        # Verify
        assert len(resources) == 1
        resource = resources[0]
        assert resource.arn == "arn:aws:elasticfilesystem:us-east-1:123456789012:file-system/fs-12345678"
        assert resource.resource_type == "efs:file-system"
        assert resource.name == "fs-12345678"
        assert resource.region == "us-east-1"
        assert resource.tags == {"Environment": "prod", "Owner": "team-a"}
        assert resource.created_at == created_time
        assert resource.raw_config is not None
        assert resource.raw_config["encryption_enabled"] is True

    @patch("src.snapshot.resource_collectors.efs_collector.EFSCollector._create_client")
    def test_collect_with_multiple_file_systems(self, mock_create_client: Mock, collector: EFSCollector) -> None:
        """Test collecting multiple EFS file systems."""
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator

        # Mock multiple file systems
        mock_paginator.paginate.return_value = [
            {
                "FileSystems": [
                    {
                        "FileSystemId": "fs-11111111",
                        "FileSystemArn": "arn:aws:elasticfilesystem:us-east-1:123456789012:file-system/fs-11111111",
                        "CreationTime": datetime.now(timezone.utc),
                        "LifeCycleState": "available",
                        "PerformanceMode": "generalPurpose",
                        "Encrypted": True,
                        "Tags": [],
                    },
                    {
                        "FileSystemId": "fs-22222222",
                        "FileSystemArn": "arn:aws:elasticfilesystem:us-east-1:123456789012:file-system/fs-22222222",
                        "CreationTime": datetime.now(timezone.utc),
                        "LifeCycleState": "available",
                        "PerformanceMode": "maxIO",
                        "Encrypted": False,
                        "Tags": [],
                    },
                ]
            }
        ]

        resources = collector.collect()

        assert len(resources) == 2
        assert resources[0].name == "fs-11111111"
        assert resources[1].name == "fs-22222222"
        assert resources[1].raw_config["performance_mode"] == "maxIO"

    @patch("src.snapshot.resource_collectors.efs_collector.EFSCollector._create_client")
    def test_collect_with_pagination(self, mock_create_client: Mock, collector: EFSCollector) -> None:
        """Test collecting with multiple pages of file systems."""
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator

        # Mock paginated responses
        mock_paginator.paginate.return_value = [
            {
                "FileSystems": [
                    {
                        "FileSystemId": "fs-page1-1",
                        "FileSystemArn": "arn:aws:elasticfilesystem:us-east-1:123456789012:file-system/fs-page1-1",
                        "CreationTime": datetime.now(timezone.utc),
                        "LifeCycleState": "available",
                        "PerformanceMode": "generalPurpose",
                        "Encrypted": True,
                        "Tags": [],
                    }
                ]
            },
            {
                "FileSystems": [
                    {
                        "FileSystemId": "fs-page2-1",
                        "FileSystemArn": "arn:aws:elasticfilesystem:us-east-1:123456789012:file-system/fs-page2-1",
                        "CreationTime": datetime.now(timezone.utc),
                        "LifeCycleState": "available",
                        "PerformanceMode": "generalPurpose",
                        "Encrypted": True,
                        "Tags": [],
                    }
                ]
            },
        ]

        resources = collector.collect()

        assert len(resources) == 2
        assert resources[0].name == "fs-page1-1"
        assert resources[1].name == "fs-page2-1"

    @patch("src.snapshot.resource_collectors.efs_collector.EFSCollector._create_client")
    def test_collect_with_tag_filtering(self, mock_create_client: Mock, collector: EFSCollector) -> None:
        """Test that tags are properly extracted from file systems."""
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator

        mock_paginator.paginate.return_value = [
            {
                "FileSystems": [
                    {
                        "FileSystemId": "fs-12345678",
                        "FileSystemArn": "arn:aws:elasticfilesystem:us-east-1:123456789012:file-system/fs-12345678",
                        "CreationTime": datetime.now(timezone.utc),
                        "LifeCycleState": "available",
                        "PerformanceMode": "generalPurpose",
                        "Encrypted": True,
                        "Tags": [
                            {"Key": "Environment", "Value": "prod"},
                            {"Key": "CostCenter", "Value": "eng-001"},
                        ],
                    }
                ]
            }
        ]

        resources = collector.collect()

        assert len(resources) == 1
        assert resources[0].tags == {"Environment": "prod", "CostCenter": "eng-001"}

    @patch("src.snapshot.resource_collectors.efs_collector.EFSCollector._create_client")
    def test_collect_with_no_tags(self, mock_create_client: Mock, collector: EFSCollector) -> None:
        """Test collecting file systems with no tags."""
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator

        mock_paginator.paginate.return_value = [
            {
                "FileSystems": [
                    {
                        "FileSystemId": "fs-12345678",
                        "FileSystemArn": "arn:aws:elasticfilesystem:us-east-1:123456789012:file-system/fs-12345678",
                        "CreationTime": datetime.now(timezone.utc),
                        "LifeCycleState": "available",
                        "PerformanceMode": "generalPurpose",
                        "Encrypted": False,
                        "Tags": [],
                    }
                ]
            }
        ]

        resources = collector.collect()

        assert len(resources) == 1
        assert resources[0].tags == {}

    @patch("src.snapshot.resource_collectors.efs_collector.EFSCollector._create_client")
    def test_collect_empty_result(self, mock_create_client: Mock, collector: EFSCollector) -> None:
        """Test collecting when no file systems exist."""
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator

        mock_paginator.paginate.return_value = [{"FileSystems": []}]

        resources = collector.collect()

        assert len(resources) == 0

    @patch("src.snapshot.resource_collectors.efs_collector.EFSCollector._create_client")
    def test_collect_handles_region_without_efs(self, mock_create_client: Mock, collector: EFSCollector) -> None:
        """Test that collector handles regions where EFS is not available."""
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        # Mock ClientError for unsupported region
        error_response = {"Error": {"Code": "OptInRequired", "Message": "Service not available in this region"}}
        mock_client.get_paginator.side_effect = ClientError(error_response, "describe_file_systems")

        resources = collector.collect()

        # Should return empty list, not raise exception
        assert len(resources) == 0

    @patch("src.snapshot.resource_collectors.efs_collector.EFSCollector._create_client")
    def test_collect_handles_access_denied(self, mock_create_client: Mock, collector: EFSCollector) -> None:
        """Test that collector handles AccessDenied errors gracefully."""
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        error_response = {"Error": {"Code": "AccessDenied", "Message": "Not authorized"}}
        mock_client.get_paginator.side_effect = ClientError(error_response, "describe_file_systems")

        resources = collector.collect()

        # Should return empty list and log error
        assert len(resources) == 0

    @patch("src.snapshot.resource_collectors.efs_collector.EFSCollector._create_client")
    def test_collect_handles_general_exception(self, mock_create_client: Mock, collector: EFSCollector) -> None:
        """Test that collector handles general exceptions gracefully."""
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        mock_client.get_paginator.side_effect = Exception("Unexpected error")

        resources = collector.collect()

        # Should return empty list and log error
        assert len(resources) == 0

    @patch("src.snapshot.resource_collectors.efs_collector.EFSCollector._create_client")
    def test_collect_with_unencrypted_file_system(self, mock_create_client: Mock, collector: EFSCollector) -> None:
        """Test collecting unencrypted file system (no KMS key)."""
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator

        mock_paginator.paginate.return_value = [
            {
                "FileSystems": [
                    {
                        "FileSystemId": "fs-unencrypted",
                        "FileSystemArn": "arn:aws:elasticfilesystem:us-east-1:123456789012:file-system/fs-unencrypted",
                        "CreationTime": datetime.now(timezone.utc),
                        "LifeCycleState": "available",
                        "PerformanceMode": "generalPurpose",
                        "Encrypted": False,
                        "Tags": [],
                    }
                ]
            }
        ]

        resources = collector.collect()

        assert len(resources) == 1
        assert resources[0].raw_config["encryption_enabled"] is False
        assert resources[0].raw_config["kms_key_id"] is None

    @patch("src.snapshot.resource_collectors.efs_collector.EFSCollector._create_client")
    def test_resource_has_valid_config_hash(self, mock_create_client: Mock, collector: EFSCollector) -> None:
        """Test that collected resources have valid config hash."""
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator

        mock_paginator.paginate.return_value = [
            {
                "FileSystems": [
                    {
                        "FileSystemId": "fs-12345678",
                        "FileSystemArn": "arn:aws:elasticfilesystem:us-east-1:123456789012:file-system/fs-12345678",
                        "CreationTime": datetime.now(timezone.utc),
                        "LifeCycleState": "available",
                        "PerformanceMode": "generalPurpose",
                        "Encrypted": True,
                        "Tags": [],
                    }
                ]
            }
        ]

        resources = collector.collect()

        assert len(resources) == 1
        # Config hash should be 64-character hex string (SHA256)
        import re

        assert re.match(r"^[a-fA-F0-9]{64}$", resources[0].config_hash)

    @patch("src.snapshot.resource_collectors.efs_collector.EFSCollector._create_client")
    def test_collect_handles_individual_fs_error(self, mock_create_client: Mock, collector: EFSCollector) -> None:
        """Test that collector handles errors processing individual file systems."""
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator

        # Return file systems with one that will cause an error (missing required fields)
        mock_paginator.paginate.return_value = [
            {
                "FileSystems": [
                    {
                        # Good file system
                        "FileSystemId": "fs-good",
                        "FileSystemArn": "arn:aws:elasticfilesystem:us-east-1:123456789012:file-system/fs-good",
                        "CreationTime": datetime.now(timezone.utc),
                        "LifeCycleState": "available",
                        "PerformanceMode": "generalPurpose",
                        "Encrypted": True,
                        "Tags": [],
                    },
                    {
                        # Bad file system - missing FileSystemArn will cause error
                        "FileSystemId": "fs-bad",
                        # Missing FileSystemArn
                        "CreationTime": datetime.now(timezone.utc),
                        "LifeCycleState": "available",
                        "PerformanceMode": "generalPurpose",
                        "Encrypted": False,
                        "Tags": [],
                    },
                ]
            }
        ]

        resources = collector.collect()

        # Should get at least the good file system (may or may not get bad one depending on implementation)
        # The key thing is no exception is raised
        assert len(resources) >= 1
        assert any(r.name == "fs-good" for r in resources)

    @patch("src.snapshot.resource_collectors.efs_collector.EFSCollector._create_client")
    def test_collect_handles_unknown_client_error(self, mock_create_client: Mock, collector: EFSCollector) -> None:
        """Test that collector handles unknown ClientError codes."""
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        # Mock ClientError with unknown error code
        error_response = {"Error": {"Code": "UnknownErrorCode", "Message": "Something unexpected happened"}}
        mock_client.get_paginator.side_effect = ClientError(error_response, "describe_file_systems")

        resources = collector.collect()

        # Should return empty list on unknown error
        assert len(resources) == 0
