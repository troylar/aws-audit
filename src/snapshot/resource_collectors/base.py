"""Base resource collector interface."""

import logging
from abc import ABC, abstractmethod
from typing import List, Optional

import boto3

from ...models.resource import Resource

logger = logging.getLogger(__name__)


class BaseResourceCollector(ABC):
    """Abstract base class for AWS resource collectors.

    Each AWS service (EC2, IAM, Lambda, etc.) should implement this interface
    to provide a consistent way of collecting resources.
    """

    def __init__(self, session: boto3.Session, region: str):
        """Initialize the collector.

        Args:
            session: Boto3 session with AWS credentials
            region: AWS region to collect from (may be ignored for global services)
        """
        self.session = session
        self.region = region
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @abstractmethod
    def collect(self) -> List[Resource]:
        """Collect all resources for this service.

        Returns:
            List of Resource instances

        Raises:
            Exception: If collection fails (should be handled by caller)
        """
        pass

    @property
    @abstractmethod
    def service_name(self) -> str:
        """Return the AWS service name (e.g., 'ec2', 'iam', 'lambda')."""
        pass

    @property
    def is_global_service(self) -> bool:
        """Return True if this is a global service (like IAM).

        Global services should only be collected once, not per-region.
        """
        return False

    def _create_client(self, service_name: Optional[str] = None):  # type: ignore
        """Create a boto3 client for this service.

        Args:
            service_name: Service name override (defaults to self.service_name)

        Returns:
            Boto3 client instance
        """
        from ...aws.client import create_boto_client

        svc = service_name or self.service_name
        profile = self.session.profile_name if hasattr(self.session, "profile_name") else None

        return create_boto_client(service_name=svc, region_name=self.region, profile_name=profile)

    def _get_account_id(self) -> str:
        """Get the AWS account ID from the session.

        Returns:
            12-digit AWS account ID
        """
        sts = self._create_client("sts")
        return sts.get_caller_identity()["Account"]
