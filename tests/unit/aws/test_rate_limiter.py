"""Tests for rate limiter."""

import time

from src.aws.rate_limiter import (
    SERVICE_RATE_LIMITS,
    RateLimiter,
    ServiceRateLimiter,
    get_global_rate_limiter,
    rate_limited_call,
)


class TestRateLimiter:
    """Tests for RateLimiter class."""

    def test_init(self):
        """Test rate limiter initialization."""
        limiter = RateLimiter(rate=10.0)
        assert limiter.rate == 10.0
        assert limiter.tokens == 10.0

    def test_acquire_immediate(self):
        """Test immediate token acquisition when tokens available."""
        limiter = RateLimiter(rate=10.0)
        result = limiter.acquire(blocking=False)
        assert result is True
        assert limiter.tokens < 10.0

    def test_acquire_multiple(self):
        """Test acquiring multiple tokens."""
        limiter = RateLimiter(rate=5.0)
        for _ in range(5):
            result = limiter.acquire(blocking=False)
            assert result is True

    def test_try_acquire_no_tokens(self):
        """Test try_acquire returns False when no tokens available."""
        limiter = RateLimiter(rate=1.0)
        limiter.tokens = 0
        result = limiter.try_acquire()
        assert result is False

    def test_try_acquire_with_tokens(self):
        """Test try_acquire returns True when tokens available."""
        limiter = RateLimiter(rate=1.0)
        result = limiter.try_acquire()
        assert result is True

    def test_acquire_blocking_waits(self):
        """Test that blocking acquire waits for token."""
        limiter = RateLimiter(rate=100.0)  # High rate for fast test
        # Exhaust all tokens
        limiter.tokens = 0

        start = time.time()
        result = limiter.acquire(blocking=True)
        elapsed = time.time() - start

        assert result is True
        # Should have waited at least a small amount
        assert elapsed >= 0.001

    def test_token_refill(self):
        """Test that tokens refill over time."""
        limiter = RateLimiter(rate=100.0)
        limiter.tokens = 0
        limiter.last_update = time.time() - 0.1  # 100ms ago

        # Force a token check which should refill
        result = limiter.acquire(blocking=False)
        assert result is True  # Should have refilled tokens


class TestServiceRateLimiter:
    """Tests for ServiceRateLimiter class."""

    def test_init_default_limits(self):
        """Test initialization with default rate limits."""
        limiter = ServiceRateLimiter()
        assert limiter.rate_limits == SERVICE_RATE_LIMITS

    def test_init_custom_limits(self):
        """Test initialization with custom rate limits."""
        custom_limits = {"custom": 5.0, "default": 1.0}
        limiter = ServiceRateLimiter(rate_limits=custom_limits)
        assert limiter.rate_limits == custom_limits

    def test_get_limiter_creates_new(self):
        """Test that get_limiter creates a new limiter for new service."""
        limiter = ServiceRateLimiter()
        result = limiter.get_limiter("ec2")
        assert isinstance(result, RateLimiter)
        assert "ec2" in limiter._limiters

    def test_get_limiter_returns_existing(self):
        """Test that get_limiter returns existing limiter."""
        limiter = ServiceRateLimiter()
        first = limiter.get_limiter("ec2")
        second = limiter.get_limiter("ec2")
        assert first is second

    def test_get_limiter_uses_service_rate(self):
        """Test that limiter uses service-specific rate."""
        limiter = ServiceRateLimiter()
        iam_limiter = limiter.get_limiter("iam")
        assert iam_limiter.rate == SERVICE_RATE_LIMITS["iam"]

    def test_get_limiter_uses_default_rate(self):
        """Test that unknown service uses default rate."""
        limiter = ServiceRateLimiter()
        unknown_limiter = limiter.get_limiter("unknown_service")
        assert unknown_limiter.rate == SERVICE_RATE_LIMITS["default"]

    def test_acquire(self):
        """Test acquire method delegates to limiter."""
        limiter = ServiceRateLimiter()
        result = limiter.acquire("ec2", blocking=False)
        assert result is True

    def test_try_acquire(self):
        """Test try_acquire method."""
        limiter = ServiceRateLimiter()
        result = limiter.try_acquire("ec2")
        assert result is True


class TestGlobalRateLimiter:
    """Tests for global rate limiter functions."""

    def test_get_global_rate_limiter_creates_instance(self):
        """Test that get_global_rate_limiter creates instance."""
        # Reset global limiter
        import src.aws.rate_limiter as rl_module

        rl_module._global_limiter = None

        limiter = get_global_rate_limiter()
        assert isinstance(limiter, ServiceRateLimiter)

    def test_get_global_rate_limiter_returns_same(self):
        """Test that get_global_rate_limiter returns same instance."""
        first = get_global_rate_limiter()
        second = get_global_rate_limiter()
        assert first is second


class TestRateLimitedCall:
    """Tests for rate_limited_call function."""

    def test_rate_limited_call_executes_function(self):
        """Test that rate_limited_call executes the function."""

        def sample_func(x, y):
            return x + y

        result = rate_limited_call("ec2", sample_func, 1, 2)
        assert result == 3

    def test_rate_limited_call_with_kwargs(self):
        """Test rate_limited_call with keyword arguments."""

        def sample_func(name, value=10):
            return f"{name}:{value}"

        result = rate_limited_call("ec2", sample_func, "test", value=20)
        assert result == "test:20"

    def test_rate_limited_call_uses_rate_limiter(self):
        """Test that rate_limited_call uses the rate limiter."""
        call_count = 0

        def sample_func():
            nonlocal call_count
            call_count += 1
            return call_count

        # Make multiple calls
        for i in range(3):
            result = rate_limited_call("ec2", sample_func)
            assert result == i + 1

        assert call_count == 3


class TestServiceRateLimits:
    """Tests for service rate limit constants."""

    def test_iam_rate_limit(self):
        """Test IAM has specific rate limit."""
        assert "iam" in SERVICE_RATE_LIMITS
        assert SERVICE_RATE_LIMITS["iam"] == 5.0

    def test_cloudformation_rate_limit(self):
        """Test CloudFormation has specific rate limit."""
        assert "cloudformation" in SERVICE_RATE_LIMITS
        assert SERVICE_RATE_LIMITS["cloudformation"] == 2.0

    def test_sts_rate_limit(self):
        """Test STS has specific rate limit."""
        assert "sts" in SERVICE_RATE_LIMITS
        assert SERVICE_RATE_LIMITS["sts"] == 10.0

    def test_default_rate_limit(self):
        """Test default rate limit exists."""
        assert "default" in SERVICE_RATE_LIMITS
        assert SERVICE_RATE_LIMITS["default"] == 10.0
