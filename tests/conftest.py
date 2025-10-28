"""Shared test fixtures for aws-baseline tests."""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_inventory_data() -> Dict[str, Any]:
    """Sample inventory data for testing."""
    return {
        "name": "test-inventory",
        "account_id": "123456789012",
        "description": "Test inventory",
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
        "inventory_name": "default",
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
