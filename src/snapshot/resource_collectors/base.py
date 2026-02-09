"""Base resource collector interface."""

import logging
from abc import ABC, abstractmethod
from typing import Callable, Dict, List, Optional

import boto3

from ...models.resource import Resource

logger = logging.getLogger(__name__)


class BaseResourceCollector(ABC):
    """Abstract base class for AWS resource collectors.

    Each AWS service (EC2, IAM, Lambda, etc.) should implement this interface
    to provide a consistent way of collecting resources.
    """

    def __init__(self, session: boto3.Session, region: str, account_id: Optional[str] = None):
        """Initialize the collector.

        Args:
            session: Boto3 session with AWS credentials
            region: AWS region to collect from (may be ignored for global services)
            account_id: AWS account ID (avoids redundant STS calls if provided)
        """
        self.session = session
        self.region = region
        self._account_id = account_id
        self._clients: Dict[str, object] = {}
        self._progress_callback: Optional[Callable[[str], None]] = None
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def set_progress_callback(self, callback: Callable[[str], None]) -> None:
        """Set a callback for reporting sub-step progress.

        Args:
            callback: Function that accepts a status string (e.g., "databases", "crawlers")
        """
        self._progress_callback = callback

    def _report_progress(self, step: str) -> None:
        """Report current sub-step to the progress callback if set."""
        if self._progress_callback:
            self._progress_callback(step)

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
        """Get or create a cached boto3 client for this service.

        Args:
            service_name: Service name override (defaults to self.service_name)

        Returns:
            Boto3 client instance (cached per service name)
        """
        svc = service_name or self.service_name

        if svc not in self._clients:
            from ...aws.client import create_boto_client

            profile = self.session.profile_name if hasattr(self.session, "profile_name") else None
            self._clients[svc] = create_boto_client(service_name=svc, region_name=self.region, profile_name=profile)

        return self._clients[svc]

    def _get_account_id(self) -> str:
        """Get the AWS account ID.

        Returns cached value if account_id was provided at init,
        otherwise falls back to STS call.

        Returns:
            12-digit AWS account ID
        """
        if self._account_id:
            return self._account_id
        sts = self._create_client("sts")
        self._account_id = sts.get_caller_identity()["Account"]
        return self._account_id
