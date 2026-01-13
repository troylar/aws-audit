"""Tests for AWS Backup resource collector."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.snapshot.resource_collectors.backup import BackupCollector


@pytest.fixture
def mock_session():
    """Create a mock boto3 session."""
    session = MagicMock()
    session.profile_name = "default"
    return session


class TestBackupCollectorProperties:
    """Tests for BackupCollector properties."""

    def test_service_name(self, mock_session):
        """Test service_name property returns backup."""
        collector = BackupCollector(session=mock_session, region="us-east-1")
        assert collector.service_name == "backup"


class TestBackupCollectorCollect:
    """Tests for BackupCollector.collect method."""

    @patch.object(BackupCollector, "_create_client")
    def test_collect_no_resources(self, mock_create_client, mock_session):
        """Test collecting when no backup resources exist."""
        mock_client = MagicMock()
        mock_plans_paginator = MagicMock()
        mock_plans_paginator.paginate.return_value = [{"BackupPlansList": []}]
        mock_vaults_paginator = MagicMock()
        mock_vaults_paginator.paginate.return_value = [{"BackupVaultList": []}]

        def get_paginator_side_effect(op):
            if op == "list_backup_plans":
                return mock_plans_paginator
            elif op == "list_backup_vaults":
                return mock_vaults_paginator

        mock_client.get_paginator.side_effect = get_paginator_side_effect
        mock_create_client.return_value = mock_client

        collector = BackupCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert resources == []

    @patch.object(BackupCollector, "_create_client")
    def test_collect_single_backup_plan(self, mock_create_client, mock_session):
        """Test collecting a single backup plan."""
        mock_client = MagicMock()
        mock_plans_paginator = MagicMock()
        created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
        mock_plans_paginator.paginate.return_value = [{
            "BackupPlansList": [{
                "BackupPlanId": "plan-123",
                "BackupPlanName": "my-backup-plan",
                "BackupPlanArn": "arn:aws:backup:us-east-1:123456789012:backup-plan:plan-123",
                "CreationDate": created_at,
            }]
        }]
        mock_vaults_paginator = MagicMock()
        mock_vaults_paginator.paginate.return_value = [{"BackupVaultList": []}]

        def get_paginator_side_effect(op):
            if op == "list_backup_plans":
                return mock_plans_paginator
            elif op == "list_backup_vaults":
                return mock_vaults_paginator

        mock_client.get_paginator.side_effect = get_paginator_side_effect
        mock_client.get_backup_plan.return_value = {
            "BackupPlan": {
                "BackupPlanName": "my-backup-plan",
                "Rules": [],
            }
        }
        mock_client.list_tags.return_value = {"Tags": {"Environment": "test"}}
        mock_create_client.return_value = mock_client

        collector = BackupCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 1
        assert resources[0].name == "my-backup-plan"
        assert resources[0].resource_type == "AWS::Backup::BackupPlan"
        assert resources[0].region == "us-east-1"
        assert resources[0].tags == {"Environment": "test"}
        assert resources[0].created_at == created_at

    @patch.object(BackupCollector, "_create_client")
    def test_collect_single_backup_vault(self, mock_create_client, mock_session):
        """Test collecting a single backup vault."""
        mock_client = MagicMock()
        mock_plans_paginator = MagicMock()
        mock_plans_paginator.paginate.return_value = [{"BackupPlansList": []}]
        mock_vaults_paginator = MagicMock()
        created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
        mock_vaults_paginator.paginate.return_value = [{
            "BackupVaultList": [{
                "BackupVaultName": "my-vault",
                "BackupVaultArn": "arn:aws:backup:us-east-1:123456789012:backup-vault:my-vault",
                "CreationDate": created_at,
            }]
        }]

        def get_paginator_side_effect(op):
            if op == "list_backup_plans":
                return mock_plans_paginator
            elif op == "list_backup_vaults":
                return mock_vaults_paginator

        mock_client.get_paginator.side_effect = get_paginator_side_effect
        mock_client.list_tags.return_value = {"Tags": {"Environment": "prod"}}
        mock_create_client.return_value = mock_client

        collector = BackupCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 1
        assert resources[0].name == "my-vault"
        assert resources[0].resource_type == "AWS::Backup::BackupVault"
        assert resources[0].tags == {"Environment": "prod"}
        assert resources[0].created_at == created_at

    @patch.object(BackupCollector, "_create_client")
    def test_collect_plans_and_vaults(self, mock_create_client, mock_session):
        """Test collecting both backup plans and vaults."""
        mock_client = MagicMock()
        mock_plans_paginator = MagicMock()
        mock_plans_paginator.paginate.return_value = [{
            "BackupPlansList": [{
                "BackupPlanId": "plan-123",
                "BackupPlanName": "my-plan",
                "BackupPlanArn": "arn:aws:backup:us-east-1:123456789012:backup-plan:plan-123",
            }]
        }]
        mock_vaults_paginator = MagicMock()
        mock_vaults_paginator.paginate.return_value = [{
            "BackupVaultList": [{
                "BackupVaultName": "my-vault",
                "BackupVaultArn": "arn:aws:backup:us-east-1:123456789012:backup-vault:my-vault",
            }]
        }]

        def get_paginator_side_effect(op):
            if op == "list_backup_plans":
                return mock_plans_paginator
            elif op == "list_backup_vaults":
                return mock_vaults_paginator

        mock_client.get_paginator.side_effect = get_paginator_side_effect
        mock_client.get_backup_plan.return_value = {"BackupPlan": {}}
        mock_client.list_tags.return_value = {"Tags": {}}
        mock_create_client.return_value = mock_client

        collector = BackupCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 2
        resource_types = [r.resource_type for r in resources]
        assert "AWS::Backup::BackupPlan" in resource_types
        assert "AWS::Backup::BackupVault" in resource_types

    @patch.object(BackupCollector, "_create_client")
    def test_collect_handles_get_plan_error(self, mock_create_client, mock_session):
        """Test collecting continues when get_backup_plan fails."""
        mock_client = MagicMock()
        mock_plans_paginator = MagicMock()
        mock_plans_paginator.paginate.return_value = [{
            "BackupPlansList": [{
                "BackupPlanId": "plan-123",
                "BackupPlanName": "my-plan",
                "BackupPlanArn": "arn:aws:backup:us-east-1:123456789012:backup-plan:plan-123",
            }]
        }]
        mock_vaults_paginator = MagicMock()
        mock_vaults_paginator.paginate.return_value = [{"BackupVaultList": []}]

        def get_paginator_side_effect(op):
            if op == "list_backup_plans":
                return mock_plans_paginator
            elif op == "list_backup_vaults":
                return mock_vaults_paginator

        mock_client.get_paginator.side_effect = get_paginator_side_effect
        mock_client.get_backup_plan.side_effect = Exception("Access denied")
        mock_create_client.return_value = mock_client

        collector = BackupCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        # Should skip the plan that failed
        assert len(resources) == 0

    @patch.object(BackupCollector, "_create_client")
    def test_collect_handles_tags_error(self, mock_create_client, mock_session):
        """Test collecting continues when list_tags fails."""
        mock_client = MagicMock()
        mock_plans_paginator = MagicMock()
        mock_plans_paginator.paginate.return_value = [{
            "BackupPlansList": [{
                "BackupPlanId": "plan-123",
                "BackupPlanName": "my-plan",
                "BackupPlanArn": "arn:aws:backup:us-east-1:123456789012:backup-plan:plan-123",
            }]
        }]
        mock_vaults_paginator = MagicMock()
        mock_vaults_paginator.paginate.return_value = [{"BackupVaultList": []}]

        def get_paginator_side_effect(op):
            if op == "list_backup_plans":
                return mock_plans_paginator
            elif op == "list_backup_vaults":
                return mock_vaults_paginator

        mock_client.get_paginator.side_effect = get_paginator_side_effect
        mock_client.get_backup_plan.return_value = {"BackupPlan": {}}
        mock_client.list_tags.side_effect = Exception("Access denied")
        mock_create_client.return_value = mock_client

        collector = BackupCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        # Should still get the resource without tags
        assert len(resources) == 1
        assert resources[0].tags == {}

    @patch.object(BackupCollector, "_create_client")
    def test_collect_handles_list_plans_error(self, mock_create_client, mock_session):
        """Test collecting handles list_backup_plans error."""
        mock_client = MagicMock()
        mock_plans_paginator = MagicMock()
        mock_plans_paginator.paginate.side_effect = Exception("Service unavailable")
        mock_vaults_paginator = MagicMock()
        mock_vaults_paginator.paginate.return_value = [{"BackupVaultList": []}]

        def get_paginator_side_effect(op):
            if op == "list_backup_plans":
                return mock_plans_paginator
            elif op == "list_backup_vaults":
                return mock_vaults_paginator

        mock_client.get_paginator.side_effect = get_paginator_side_effect
        mock_create_client.return_value = mock_client

        collector = BackupCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        # Should return empty list for plans but still collect vaults
        assert resources == []

    @patch.object(BackupCollector, "_create_client")
    def test_collect_handles_list_vaults_error(self, mock_create_client, mock_session):
        """Test collecting handles list_backup_vaults error."""
        mock_client = MagicMock()
        mock_plans_paginator = MagicMock()
        mock_plans_paginator.paginate.return_value = [{"BackupPlansList": []}]
        mock_vaults_paginator = MagicMock()
        mock_vaults_paginator.paginate.side_effect = Exception("Service unavailable")

        def get_paginator_side_effect(op):
            if op == "list_backup_plans":
                return mock_plans_paginator
            elif op == "list_backup_vaults":
                return mock_vaults_paginator

        mock_client.get_paginator.side_effect = get_paginator_side_effect
        mock_create_client.return_value = mock_client

        collector = BackupCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        # Should still work (no vaults collected)
        assert resources == []

    @patch.object(BackupCollector, "_create_client")
    def test_collect_generates_config_hash(self, mock_create_client, mock_session):
        """Test that config hash is generated."""
        mock_client = MagicMock()
        mock_plans_paginator = MagicMock()
        mock_plans_paginator.paginate.return_value = [{
            "BackupPlansList": [{
                "BackupPlanId": "plan-123",
                "BackupPlanName": "my-plan",
                "BackupPlanArn": "arn:aws:backup:us-east-1:123456789012:backup-plan:plan-123",
            }]
        }]
        mock_vaults_paginator = MagicMock()
        mock_vaults_paginator.paginate.return_value = [{"BackupVaultList": []}]

        def get_paginator_side_effect(op):
            if op == "list_backup_plans":
                return mock_plans_paginator
            elif op == "list_backup_vaults":
                return mock_vaults_paginator

        mock_client.get_paginator.side_effect = get_paginator_side_effect
        mock_client.get_backup_plan.return_value = {"BackupPlan": {"Rules": []}}
        mock_client.list_tags.return_value = {"Tags": {}}
        mock_create_client.return_value = mock_client

        collector = BackupCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 1
        assert resources[0].config_hash is not None
        assert len(resources[0].config_hash) > 0
