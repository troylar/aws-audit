# Generate New Resource Collector

Scaffold a new AWS resource collector following project patterns.

## Task

Create a new resource collector for an AWS service, following the established patterns in the codebase.

## Steps

### 1. Ask User for Service Details

Ask the user:
- **AWS service name** (e.g., "EFS", "ElastiCache", "Kinesis", "Glue")
- **Resource type(s) to collect** (e.g., "File Systems", "Clusters", "Data Streams")
- **Boto3 client name** (e.g., "efs", "elasticache", "kinesis", "glue")
- **Is this a global service or regional?** (most are regional, IAM/CloudFront/Route53 are global)
- **Boto3 API method to list resources** (e.g., "describe_file_systems", "describe_cache_clusters")

### 2. Read Existing Collector for Reference

Read a similar existing collector to understand the pattern:

```bash
# Read EC2 collector as reference (comprehensive example)
cat src/snapshot/resource_collectors/ec2_collector.py

# Or read simpler collector like SNS
cat src/snapshot/resource_collectors/sns_collector.py
```

### 3. Generate New Collector File

Create file at `src/snapshot/resource_collectors/<service_lowercase>_collector.py`

**Template:**
```python
"""<ServiceName> resource collector."""

from typing import Any, Dict, List
import logging

from .base import BaseResourceCollector
from ...models.resource import Resource
from ...utils.hash import compute_config_hash

logger = logging.getLogger(__name__)


class <ServiceName>Collector(BaseResourceCollector):
    """Collector for AWS <ServiceName> resources."""

    def __init__(self, session: Any, region: str) -> None:
        """Initialize <ServiceName> collector.

        Args:
            session: Boto3 session
            region: AWS region (ignored for global services)
        """
        super().__init__(session, region)
        # For global services, use a fixed region (e.g., us-east-1)
        client_region = "us-east-1" if self._is_global_service() else region
        self.client = session.client("<boto3_client_name>", region_name=client_region)

    def _is_global_service(self) -> bool:
        """Check if this is a global service."""
        # Return True for IAM, CloudFront, Route53, etc.
        return False  # Change to True if global service

    def collect(self) -> List[Resource]:
        """Collect <ServiceName> resources.

        Returns:
            List of Resource objects
        """
        resources = []

        try:
            # Use paginator if available
            paginator = self.client.get_paginator("<api_method>")
            for page in paginator.paginate():
                for item in page.get("<response_key>", []):
                    resource = self._create_resource(item)
                    if resource:
                        resources.append(resource)

        except self.client.exceptions.ServiceNotEnabledException:
            logger.debug(f"<ServiceName> not enabled in {self.region}")
        except Exception as e:
            logger.error(f"Error collecting <service> resources in {self.region}: {e}")

        logger.info(f"Collected {len(resources)} <service> resources from {self.region}")
        return resources

    def _create_resource(self, item: Dict[str, Any]) -> Resource:
        """Create Resource from API response.

        Args:
            item: API response item

        Returns:
            Resource object
        """
        try:
            # Extract resource details
            resource_id = item.get("<IdKey>", "")
            resource_name = item.get("<NameKey>", resource_id)
            resource_arn = item.get("<ArnKey>", "")

            # If ARN not in response, construct it
            if not resource_arn:
                resource_arn = self._construct_arn(resource_id)

            # Extract tags (format varies by service)
            tags = {}
            if "Tags" in item:
                # Key-value pair format
                tags = {tag["Key"]: tag["Value"] for tag in item.get("Tags", [])}
            elif "TagList" in item:
                # Alternative format
                tags = {tag["Key"]: tag["Value"] for tag in item.get("TagList", [])}

            # Extract creation date if available
            created_at = item.get("CreatedDate") or item.get("CreationDate") or item.get("CreateTime")

            # Compute config hash for change detection
            config_hash = compute_config_hash(item)

            return Resource(
                arn=resource_arn,
                resource_type="<service>:<resource_type>",  # e.g., "efs:file_system"
                name=resource_name,
                region=self.region,
                tags=tags,
                created_at=created_at,
                config_hash=config_hash,
                metadata={
                    # Add relevant metadata fields
                    "id": resource_id,
                    # Add other useful fields from item
                },
            )

        except Exception as e:
            logger.error(f"Error creating <service> resource: {e}")
            return None

    def _construct_arn(self, resource_id: str) -> str:
        """Construct ARN if not provided by API.

        Args:
            resource_id: Resource identifier

        Returns:
            ARN string
        """
        # ARN format: arn:aws:<service>:<region>:<account-id>:<resource-type>/<resource-id>
        # For global services, region is empty
        region_part = "" if self._is_global_service() else self.region

        # You may need to get account ID from STS
        # account_id = self.session.client('sts').get_caller_identity()['Account']

        return f"arn:aws:<service>:{region_part}:{{account_id}}:<resource_type>/{resource_id}"
```

### 4. Update Collector Registry

Update `src/snapshot/resource_collectors/__init__.py`:

```python
# Add import
from .<service_lowercase>_collector import <ServiceName>Collector

# Add to __all__
__all__ = [
    # ... existing collectors ...
    "<ServiceName>Collector",
]

# Add to COLLECTORS list
COLLECTORS = [
    # ... existing collectors ...
    <ServiceName>Collector,
]
```

### 5. Generate Unit Test

Create file at `tests/unit/snapshot/resource_collectors/test_<service_lowercase>_collector.py`

**Template:**
```python
"""Unit tests for <ServiceName> collector."""

import pytest
from unittest.mock import Mock, MagicMock
from src.snapshot.resource_collectors.<service_lowercase>_collector import <ServiceName>Collector


@pytest.fixture
def mock_session():
    """Create mock boto3 session."""
    session = Mock()
    client = MagicMock()
    session.client.return_value = client
    return session, client


def test_collect_<service_lowercase>_resources(mock_session):
    """Test successful collection of <service> resources."""
    session, client = mock_session

    # Mock API response
    client.get_paginator.return_value.paginate.return_value = [
        {
            "<response_key>": [
                {
                    "<IdKey>": "resource-123",
                    "<NameKey>": "test-resource",
                    "<ArnKey>": "arn:aws:<service>:us-east-1:123456789012:<resource_type>/resource-123",
                    "Tags": [
                        {"Key": "Environment", "Value": "test"},
                    ],
                }
            ]
        }
    ]

    collector = <ServiceName>Collector(session, "us-east-1")
    resources = collector.collect()

    assert len(resources) == 1
    assert resources[0].resource_type == "<service>:<resource_type>"
    assert resources[0].name == "test-resource"
    assert resources[0].region == "us-east-1"
    assert resources[0].tags["Environment"] == "test"


def test_collect_handles_service_not_enabled(mock_session):
    """Test handling when service is not enabled."""
    session, client = mock_session

    # Mock service not enabled exception
    client.get_paginator.return_value.paginate.side_effect = \
        client.exceptions.ServiceNotEnabledException("Service not enabled")

    collector = <ServiceName>Collector(session, "us-east-1")
    resources = collector.collect()

    assert len(resources) == 0


def test_collect_handles_errors(mock_session):
    """Test error handling during collection."""
    session, client = mock_session

    # Mock generic error
    client.get_paginator.return_value.paginate.side_effect = Exception("API error")

    collector = <ServiceName>Collector(session, "us-east-1")
    resources = collector.collect()

    assert len(resources) == 0


def test_collect_empty_results(mock_session):
    """Test handling empty results."""
    session, client = mock_session

    # Mock empty response
    client.get_paginator.return_value.paginate.return_value = [
        {"<response_key>": []}
    ]

    collector = <ServiceName>Collector(session, "us-east-1")
    resources = collector.collect()

    assert len(resources) == 0
```

### 6. Show Implementation Checklist

Present checklist to user:

```
✅ Collector created: src/snapshot/resource_collectors/<service>_collector.py
✅ Registered in: src/snapshot/resource_collectors/__init__.py
✅ Unit tests created: tests/unit/snapshot/resource_collectors/test_<service>_collector.py

📋 Next Steps:

Manual Tasks:
[ ] Review generated code and customize for service specifics
[ ] Update API method names and response keys to match boto3 docs
[ ] Verify ARN construction logic is correct
[ ] Add any service-specific error handling
[ ] Customize metadata fields to capture important resource properties

Testing & Verification:
[ ] Run unit tests: invoke test-unit
[ ] Fix any test failures
[ ] Test with real AWS account:
    awsinv snapshot create test --region us-east-1
[ ] Verify resources are collected correctly

Documentation:
[ ] Update README.md to add <ServiceName> to supported services list
[ ] Update CHANGELOG.md with new service support
[ ] Consider bumping version in pyproject.toml (minor version)

Commit:
[ ] git add src/snapshot/resource_collectors/<service>_collector.py
[ ] git add src/snapshot/resource_collectors/__init__.py
[ ] git add tests/unit/snapshot/resource_collectors/test_<service>_collector.py
[ ] git commit -m "feat: add <ServiceName> resource collector"

💡 Helpful Resources:
- Boto3 <ServiceName> docs: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/<service>.html
- Check paginator availability: client.can_paginate('<method>')
- Test with: awsinv snapshot create test-<service> --region us-east-1
```

## Example Usage

```
/new-collector
```

Then answer prompts:
- Service: "EFS"
- Resource type: "File Systems"
- Boto3 client: "efs"
- Regional: Yes
- API method: "describe_file_systems"

Claude generates:
- Complete collector implementation
- Unit tests
- Integration instructions

## Service Examples

**Common Services to Add:**
- **EFS**: File systems (`efs`, `describe_file_systems`)
- **ElastiCache**: Clusters (`elasticache`, `describe_cache_clusters`)
- **Kinesis**: Data Streams (`kinesis`, `list_streams`)
- **Glue**: Jobs, Crawlers, Databases (`glue`, `get_jobs`, `get_crawlers`, `get_databases`)
- **Athena**: Work Groups, Data Catalogs (`athena`, `list_work_groups`)
- **OpenSearch**: Domains (`opensearch`, `list_domain_names`)
- **AppSync**: GraphQL APIs (`appsync`, `list_graphql_apis`)
- **Cognito**: User Pools (`cognito-idp`, `list_user_pools`)
- **SageMaker**: Endpoints, Models (`sagemaker`, `list_endpoints`)

## Notes

- Always follow the BaseResourceCollector pattern
- Use paginators when available for complete resource discovery
- Handle service-not-enabled gracefully (some services aren't available in all regions)
- Extract tags carefully - format varies by service
- Compute config_hash for change detection
- Add proper logging for debugging
- Include comprehensive error handling
- Write tests for success, error, and empty cases

## Best Practices

1. **ARN Construction**: Get ARN from API when possible, construct only if necessary
2. **Tagging**: Handle both `Tags` and `TagList` formats
3. **Creation Date**: Look for `CreatedDate`, `CreationDate`, `CreateTime`
4. **Error Handling**: Catch service-specific exceptions first, then generic
5. **Logging**: Use debug for expected errors, error for unexpected
6. **Metadata**: Include useful fields that might be needed for filtering/analysis
7. **Testing**: Test against real AWS API to verify correctness
