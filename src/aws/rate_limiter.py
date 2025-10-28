"""Rate limiter utility using token bucket algorithm."""

import logging
import time
from threading import Lock
from typing import Dict, Optional

logger = logging.getLogger(__name__)


# Service-specific rate limits (calls per second)
# Based on AWS API throttling limits
SERVICE_RATE_LIMITS: Dict[str, float] = {
    "iam": 5.0,  # IAM has strict rate limits (global service)
    "cloudformation": 2.0,  # CloudFormation is particularly slow
    "sts": 10.0,  # STS is also rate-limited
    "default": 10.0,  # Conservative default for other services
}


class RateLimiter:
    """Token bucket rate limiter for controlling API call frequency.

    This prevents hitting AWS API rate limits by throttling client-side
    before the request is even made.
    """

    def __init__(self, rate: float):
        """Initialize rate limiter.

        Args:
            rate: Maximum number of calls per second
        """
        self.rate = rate
        self.tokens = rate
        self.last_update = time.time()
        self.lock = Lock()

        logger.debug(f"Initialized rate limiter with rate {rate} calls/sec")

    def acquire(self, blocking: bool = True) -> bool:
        """Acquire permission to make an API call.

        This method will block until a token is available (if blocking=True)
        or return immediately (if blocking=False).

        Args:
            blocking: If True, wait until token available. If False, return immediately.

        Returns:
            True if token acquired, False if blocking=False and no token available
        """
        with self.lock:
            now = time.time()
            elapsed = now - self.last_update

            # Refill tokens based on elapsed time
            self.tokens = min(self.rate, self.tokens + elapsed * self.rate)
            self.last_update = now

            if self.tokens >= 1:
                # Token available
                self.tokens -= 1
                return True
            else:
                # No token available
                if not blocking:
                    return False

                # Calculate how long to sleep
                sleep_time = (1 - self.tokens) / self.rate
                logger.debug(f"Rate limiter sleeping for {sleep_time:.3f}s")

        # Sleep outside the lock to allow other threads
        time.sleep(sleep_time)

        # Acquire token after sleeping
        with self.lock:
            self.tokens = 0
            self.last_update = time.time()
            return True

    def try_acquire(self) -> bool:
        """Try to acquire a token without blocking.

        Returns:
            True if token acquired, False otherwise
        """
        return self.acquire(blocking=False)


class ServiceRateLimiter:
    """Manages rate limiters for different AWS services."""

    def __init__(self, rate_limits: Optional[Dict[str, float]] = None):
        """Initialize service rate limiter.

        Args:
            rate_limits: Dictionary mapping service names to rates (optional)
        """
        self.rate_limits = rate_limits or SERVICE_RATE_LIMITS
        self._limiters: Dict[str, RateLimiter] = {}
        self._lock = Lock()

    def get_limiter(self, service_name: str) -> RateLimiter:
        """Get or create a rate limiter for a service.

        Args:
            service_name: AWS service name (e.g., 'iam', 'ec2')

        Returns:
            RateLimiter instance for the service
        """
        with self._lock:
            if service_name not in self._limiters:
                rate = self.rate_limits.get(service_name, self.rate_limits["default"])
                self._limiters[service_name] = RateLimiter(rate)
                logger.debug(f"Created rate limiter for {service_name} ({rate} calls/sec)")

            return self._limiters[service_name]

    def acquire(self, service_name: str, blocking: bool = True) -> bool:
        """Acquire permission to call an AWS service API.

        Args:
            service_name: AWS service name
            blocking: Whether to block until token available

        Returns:
            True if token acquired
        """
        limiter = self.get_limiter(service_name)
        return limiter.acquire(blocking=blocking)

    def try_acquire(self, service_name: str) -> bool:
        """Try to acquire permission without blocking.

        Args:
            service_name: AWS service name

        Returns:
            True if token acquired, False otherwise
        """
        return self.acquire(service_name, blocking=False)


# Global service rate limiter instance
_global_limiter: Optional[ServiceRateLimiter] = None


def get_global_rate_limiter() -> ServiceRateLimiter:
    """Get the global service rate limiter instance.

    Returns:
        Global ServiceRateLimiter instance
    """
    global _global_limiter
    if _global_limiter is None:
        _global_limiter = ServiceRateLimiter()
    return _global_limiter


def rate_limited_call(service_name: str, func, *args, **kwargs):  # type: ignore[no-untyped-def]
    """Execute a function with rate limiting applied.

    Args:
        service_name: AWS service name for rate limiting
        func: Function to call
        *args: Positional arguments to pass to func
        **kwargs: Keyword arguments to pass to func

    Returns:
        Result of func(*args, **kwargs)
    """
    limiter = get_global_rate_limiter()
    limiter.acquire(service_name)
    return func(*args, **kwargs)
