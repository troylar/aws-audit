"""Shared test fixtures for aws-baseline tests."""

import tempfile
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def cli_runner():
    """Pre-configured Typer CliRunner."""
    return CliRunner()


@pytest.fixture
def mock_storage():
    """Mock SnapshotStorage for CLI tests."""
    storage = MagicMock()
    storage.list_snapshots.return_value = []
    storage.load_snapshot.return_value = None
    storage.list_collections.return_value = []
    return storage


@pytest.fixture
def mock_database():
    """Mock Database for web and storage tests."""
    db = MagicMock()
    db.ensure_schema.return_value = None
    return db


@pytest.fixture
def sample_resource_data() -> Dict[str, Any]:
    """Sample AWS resource data for testing."""
    return {
        "resource_type": "ec2:instance",
        "resource_id": "i-1234567890abcdef0",
        "arn": "arn:aws:ec2:us-east-1:123456789012:instance/i-1234567890abcdef0",
        "region": "us-east-1",
        "name": "test-instance",
        "tags": {"Name": "test-instance", "Environment": "test"},
        "config": {
            "InstanceId": "i-1234567890abcdef0",
            "InstanceType": "t3.micro",
            "State": {"Name": "running"},
        },
    }


@pytest.fixture
def sample_generation_state() -> Dict[str, Any]:
    """Sample GenerationState for generate module tests."""
    return {
        "snapshot_name": "test-snapshot",
        "format": "terraform",
        "output_dir": "/tmp/test-output",
        "resources": [],
        "resource_map": {},
        "layers": [],
        "generated_files": [],
        "guardrail_results": None,
        "errors": [],
    }


@pytest.fixture
def sample_collection_data() -> Dict[str, Any]:
    """Sample collection data for testing."""
    return {
        "name": "test-collection",
        "account_id": "123456789012",
        "description": "Test collection",
        "include_tags": {"Environment": "production"},
        "exclude_tags": {"Status": "archived"},
        "snapshots": ["snapshot1.yaml", "snapshot2.yaml"],
        "active_snapshot": "snapshot1.yaml",
        "created_at": "2024-01-01T00:00:00+00:00",
        "last_updated": "2024-01-02T00:00:00+00:00",
    }


@pytest.fixture
def sample_snapshot_data() -> Dict[str, Any]:
    """Sample snapshot data for testing."""
    return {
        "name": "test-snapshot",
        "created_at": "2024-01-01T00:00:00+00:00",
        "account_id": "123456789012",
        "regions": ["us-east-1", "us-west-2"],
        "is_active": True,
        "resource_count": 10,
        "service_counts": {"ec2": 5, "s3": 3, "iam": 2},
        "metadata": {},
        "filters_applied": None,
        "total_resources_before_filter": None,
        "collection_name": "default",
        "resources": [],
    }


@pytest.fixture
def mock_aws_identity():
    """Mock AWS identity for testing."""
    return {
        "account_id": "123456789012",
        "arn": "arn:aws:iam::123456789012:user/test-user",
        "user_id": "AIDAEXAMPLE",
    }
