# =============================================================================
# ADs Growth System - Security Middleware Unit Tests
# =============================================================================
"""
Comprehensive unit tests for SecurityHeadersMiddleware and RateLimitMiddleware.

Tests cover:
- All security headers are set on normal endpoints
- Health check endpoints skip security headers
- Production-only headers (HSTS, strict CSP) are applied in production mode
- Development CSP is more permissive
- Sensitive API paths get cache-control headers
- Non-sensitive API paths do not get cache-control headers
- Rate limiting: requests below limit pass through
- Rate limiting: requests above limit return 429
- Rate limiting: rate limit headers are included in responses
- Rate limiting: token bucket fallback when Redis is unavailable
"""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.requests import Request
from starlette.responses import Response
from starlette.testclient import TestClient

from app.middleware.rate_limit import RateLimitMiddleware, TokenBucket

# =============================================================================
# Helpers
# =============================================================================


def _make_request(
    path: str = "/api/v1/data", client_host: str = "127.0.0.1"
) -> MagicMock:
    """Create a minimal mock Request for middleware dispatch."""
    request = MagicMock(spec=Request)
    url = MagicMock()
    url.path = path
    request.url = url
    request.headers = {}
    request.state = MagicMock()
    request.state.user_id = None
    client = MagicMock()
    client.host = client_host
    request.client = client
    return request


async def _ok_call_next(request: Request) -> Response:
    """Simulated downstream handler that returns a plain 200."""
    return Response(content="OK", status_code=200)


# =============================================================================
# SecurityHeadersMiddleware Tests
# =============================================================================


class TestSecurityHeadersMiddleware:
    """Tests for the SecurityHeadersMiddleware."""

    @pytest.mark.asyncio
    async def test_core_security_headers_are_set(self):
        """All core security headers should be present on a normal API response."""
        from app.middleware.security import SecurityHeadersMiddleware

        app = MagicMock()
        middleware = SecurityHeadersMiddleware(app)

        request = _make_request("/api/v1/campaigns")
        response = await middleware.dispatch(request, _ok_call_next)

        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "SAMEORIGIN"
        assert response.headers["X-XSS-Protection"] == "1; mode=block"
        assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
        assert "camera=()" in response.headers["Permissions-Policy"]
        assert "microphone=()" in response.headers["Permissions-Policy"]
        assert response.headers["X-Permitted-Cross-Domain-Policies"] == "none"
        # CSP should always be present (dev or prod)
        assert "Content-Security-Policy" in response.headers

    @pytest.mark.asyncio
    async def test_health_check_skips_security_headers(self):
        """Health check endpoints should skip security headers for performance."""
        from app.middleware.security import SecurityHeadersMiddleware

        app = MagicMock()
        middleware = SecurityHeadersMiddleware(app)

        request = _make_request("/health")
        response = await middleware.dispatch(request, _ok_call_next)

        # Core headers should NOT be present on health check
        assert "X-Content-Type-Options" not in response.headers
        assert "X-Frame-Options" not in response.headers
        assert "Content-Security-Policy" not in response.headers

    @pytest.mark.asyncio
    async def test_production_mode_adds_hsts(self):
        """Production mode should add Strict-Transport-Security header."""
        from app.middleware.security import SecurityHeadersMiddleware

        app = MagicMock()
        middleware = SecurityHeadersMiddleware(app)

        request = _make_request("/api/v1/data")

        with patch("app.middleware.security.settings") as mock_settings:
            mock_settings.is_production = True
            response = await middleware.dispatch(request, _ok_call_next)

        hsts = response.headers.get("Strict-Transport-Security", "")
        assert "max-age=31536000" in hsts
        assert "includeSubDomains" in hsts
        assert "preload" in hsts

    @pytest.mark.asyncio
    async def test_production_csp_is_strict(self):
        """Production CSP should not contain 'unsafe-eval'."""
        from app.middleware.security import SecurityHeadersMiddleware

        app = MagicMock()
        middleware = SecurityHeadersMiddleware(app)

        request = _make_request("/api/v1/data")

        with patch("app.middleware.security.settings") as mock_settings:
            mock_settings.is_production = True
            response = await middleware.dispatch(request, _ok_call_next)

        csp = response.headers["Content-Security-Policy"]
        assert "unsafe-eval" not in csp
        assert "upgrade-insecure-requests" in csp
        assert "default-src 'self'" in csp

    @pytest.mark.asyncio
    async def test_development_csp_allows_unsafe_eval(self):
        """Development CSP should allow 'unsafe-eval' for hot reload."""
        from app.middleware.security import SecurityHeadersMiddleware

        app = MagicMock()
        middleware = SecurityHeadersMiddleware(app)

        request = _make_request("/api/v1/data")

        with patch("app.middleware.security.settings") as mock_settings:
            mock_settings.is_production = False
            mock_settings.is_staging = False  # MagicMock attrs are truthy unless set
            response = await middleware.dispatch(request, _ok_call_next)

        csp = response.headers["Content-Security-Policy"]
        assert "'unsafe-eval'" in csp
        assert "ws:" in csp  # WebSocket for dev hot reload

    @pytest.mark.asyncio
    async def test_development_mode_no_hsts(self):
        """Development mode should NOT add HSTS header."""
        from app.middleware.security import SecurityHeadersMiddleware

        app = MagicMock()
        middleware = SecurityHeadersMiddleware(app)

        request = _make_request("/api/v1/data")

        with patch("app.middleware.security.settings") as mock_settings:
            mock_settings.is_production = False
            response = await middleware.dispatch(request, _ok_call_next)

        assert "Strict-Transport-Security" not in response.headers

    @pytest.mark.asyncio
    async def test_sensitive_api_paths_get_cache_control(self):
        """Sensitive API paths should get no-cache headers."""
        from app.middleware.security import SecurityHeadersMiddleware

        app = MagicMock()
        middleware = SecurityHeadersMiddleware(app)

        sensitive_paths = [
            "/api/v1/auth/login",
            "/api/v1/users/me",
            "/api/v1/settings/general",
        ]

        with patch("app.middleware.security.settings") as mock_settings:
            mock_settings.is_production = False
            for path in sensitive_paths:
                request = _make_request(path)
                response = await middleware.dispatch(request, _ok_call_next)

                assert "no-store" in response.headers.get(
                    "Cache-Control", ""
                ), f"Cache-Control missing for sensitive path: {path}"
                assert response.headers.get("Pragma") == "no-cache"
                assert response.headers.get("Expires") == "0"

    @pytest.mark.asyncio
    async def test_non_sensitive_api_paths_no_cache_control(self):
        """Non-sensitive API paths should NOT get special cache-control headers."""
        from app.middleware.security import SecurityHeadersMiddleware

        app = MagicMock()
        middleware = SecurityHeadersMiddleware(app)

        request = _make_request("/api/v1/campaigns")

        with patch("app.middleware.security.settings") as mock_settings:
            mock_settings.is_production = False
            response = await middleware.dispatch(request, _ok_call_next)

        # Should not have the sensitive cache-control header
        assert "no-store" not in response.headers.get("Cache-Control", "")

    @pytest.mark.asyncio
    async def test_non_api_paths_no_cache_control(self):
        """Non-API paths should NOT get special cache-control headers."""
        from app.middleware.security import SecurityHeadersMiddleware

        app = MagicMock()
        middleware = SecurityHeadersMiddleware(app)

        request = _make_request("/static/app.js")

        with patch("app.middleware.security.settings") as mock_settings:
            mock_settings.is_production = False
            response = await middleware.dispatch(request, _ok_call_next)

        assert "no-store" not in response.headers.get("Cache-Control", "")

    @pytest.mark.asyncio
    async def test_permissions_policy_restricts_all_sensitive_apis(self):
        """Permissions-Policy should restrict all sensitive browser APIs."""
        from app.middleware.security import SecurityHeadersMiddleware

        app = MagicMock()
        middleware = SecurityHeadersMiddleware(app)

        request = _make_request("/api/v1/data")

        with patch("app.middleware.security.settings") as mock_settings:
            mock_settings.is_production = False
            response = await middleware.dispatch(request, _ok_call_next)

        policy = response.headers["Permissions-Policy"]
        for feature in ["camera", "microphone", "geolocation", "payment", "usb"]:
            assert f"{feature}=()" in policy, f"Missing restriction for: {feature}"


# =============================================================================
# TokenBucket Unit Tests
# =============================================================================


class TestTokenBucket:
    """Tests for the in-memory token bucket fallback."""

    def test_bucket_allows_within_capacity(self):
        """Requests within capacity should be allowed."""
        bucket = TokenBucket(rate=10.0, capacity=20)

        for _ in range(20):
            assert bucket.consume() is True

    def test_bucket_denies_over_capacity(self):
        """Requests over capacity should be denied."""
        bucket = TokenBucket(rate=0.0, capacity=5)

        for _ in range(5):
            bucket.consume()

        assert bucket.consume() is False

    def test_bucket_refills_over_time(self):
        """Bucket should refill tokens over time based on rate."""
        bucket = TokenBucket(rate=100.0, capacity=10)

        # Consume all tokens
        for _ in range(10):
            bucket.consume()

        assert bucket.consume() is False

        # Manually advance time by setting last_update backwards
        bucket.last_update = time.monotonic() - 1.0  # 1 second ago

        # Now tokens should have refilled (rate=100/s, so at least 10 tokens)
        assert bucket.consume() is True

    def test_bucket_remaining_property(self):
        """Remaining should reflect current token count."""
        bucket = TokenBucket(rate=0.0, capacity=10)

        assert bucket.remaining == 10

        bucket.consume()
        assert bucket.remaining == 9

    def test_bucket_does_not_exceed_capacity(self):
        """Tokens should never exceed capacity even after long idle."""
        bucket = TokenBucket(rate=1000.0, capacity=5)

        # Advance time far into the future
        bucket.last_update = time.monotonic() - 100.0

        # Force a refill by consuming
        bucket.consume()
        # remaining should be at most capacity - 1
        assert bucket.remaining <= 4


# =============================================================================
# RateLimitMiddleware Tests
# =============================================================================


class TestRateLimitMiddleware:
    """Tests for the RateLimitMiddleware using in-memory fallback."""

    @pytest.mark.asyncio
    async def test_requests_below_limit_pass_through(self):
        """Requests below the rate limit should pass through and get rate headers."""
        app = MagicMock()
        middleware = RateLimitMiddleware(app, requests_per_minute=100, burst_size=20)
        # Force in-memory mode (no Redis)
        middleware._redis_available = False

        request = _make_request("/api/v1/data", client_host="10.0.0.1")
        response = await middleware.dispatch(request, _ok_call_next)

        assert response.status_code == 200
        assert "X-RateLimit-Limit" in response.headers
        assert response.headers["X-RateLimit-Limit"] == "100"
        assert "X-RateLimit-Remaining" in response.headers
        assert "X-RateLimit-Reset" in response.headers

    @pytest.mark.asyncio
    async def test_requests_above_limit_return_429(self):
        """Requests above the rate limit should return 429 Too Many Requests."""
        app = MagicMock()
        # Use burst_size=8 so fallback capacity (8//4=2) allows at least 1 OK
        middleware = RateLimitMiddleware(app, requests_per_minute=5, burst_size=8)
        middleware._redis_available = False

        request = _make_request("/api/v1/data", client_host="10.0.0.2")

        # Fallback capacity = max(1, 8//4) = 2; exhaust it
        for _ in range(2):
            resp = await middleware.dispatch(request, _ok_call_next)
            assert resp.status_code == 200

        # Next request should be rate-limited
        resp = await middleware.dispatch(request, _ok_call_next)
        assert resp.status_code == 429

    @pytest.mark.asyncio
    async def test_429_response_includes_retry_after(self):
        """429 responses should include Retry-After header."""
        app = MagicMock()
        middleware = RateLimitMiddleware(app, requests_per_minute=5, burst_size=1)
        middleware._redis_available = False

        request = _make_request("/api/v1/data", client_host="10.0.0.3")

        # Exhaust the single token
        await middleware.dispatch(request, _ok_call_next)

        # Trigger rate limit
        resp = await middleware.dispatch(request, _ok_call_next)
        assert resp.status_code == 429
        assert "Retry-After" in resp.headers
        assert resp.headers["X-RateLimit-Remaining"] == "0"

    @pytest.mark.asyncio
    async def test_rate_limit_resets_after_window(self):
        """Rate limit should reset after the time window (via token refill)."""
        app = MagicMock()
        middleware = RateLimitMiddleware(app, requests_per_minute=60, burst_size=2)
        middleware._redis_available = False

        request = _make_request("/api/v1/data", client_host="10.0.0.4")

        # Exhaust burst
        for _ in range(2):
            await middleware.dispatch(request, _ok_call_next)

        # Should be rate-limited now
        resp = await middleware.dispatch(request, _ok_call_next)
        assert resp.status_code == 429

        # Simulate time passing to refill tokens
        client_id = middleware._get_client_identifier(request)
        bucket = middleware._buckets.get(client_id)
        if bucket:
            bucket.last_update = time.monotonic() - 10.0  # 10 seconds ago

        # Should be allowed again after refill
        resp = await middleware.dispatch(request, _ok_call_next)
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_different_clients_have_separate_limits(self):
        """Different IPs should have separate rate limit buckets."""
        app = MagicMock()
        middleware = RateLimitMiddleware(app, requests_per_minute=5, burst_size=2)
        middleware._redis_available = False

        request_a = _make_request("/api/v1/data", client_host="10.0.0.10")
        request_b = _make_request("/api/v1/data", client_host="10.0.0.11")

        # Exhaust client A
        for _ in range(2):
            await middleware.dispatch(request_a, _ok_call_next)
        resp_a = await middleware.dispatch(request_a, _ok_call_next)
        assert resp_a.status_code == 429

        # Client B should still be allowed
        resp_b = await middleware.dispatch(request_b, _ok_call_next)
        assert resp_b.status_code == 200

    def test_client_identifier_uses_ip(self):
        """Client identifier should use IP when no user_id is set."""
        app = MagicMock()
        middleware = RateLimitMiddleware(app)

        request = _make_request("/api/v1/data", client_host="192.168.1.1")
        request.state.user_id = None

        client_id = middleware._get_client_identifier(request)
        assert client_id == "ip:192.168.1.1"

    def test_client_identifier_uses_user_id(self):
        """Client identifier should use user_id when authenticated."""
        app = MagicMock()
        middleware = RateLimitMiddleware(app)

        request = _make_request("/api/v1/data")
        request.state.user_id = 42

        client_id = middleware._get_client_identifier(request)
        assert client_id == "user:42"

    def test_client_ip_from_x_forwarded_for(self):
        """Client IP should be extracted from X-Forwarded-For header.

        The middleware picks the rightmost untrusted IP (closest to the
        proxy) to prevent spoofing via prepended headers.
        """
        app = MagicMock()
        middleware = RateLimitMiddleware(app)

        # client.host must be a trusted proxy for headers to be used
        request = _make_request("/api/v1/data", client_host="127.0.0.1")
        request.headers = {"X-Forwarded-For": "203.0.113.50, 70.41.3.18"}

        ip = middleware._get_client_ip(request)
        # Rightmost untrusted IP is returned
        assert ip == "70.41.3.18"

    def test_client_ip_from_x_real_ip(self):
        """Client IP should fall back to X-Real-IP header."""
        app = MagicMock()
        middleware = RateLimitMiddleware(app)

        request = _make_request("/api/v1/data")
        request.headers = {"X-Real-IP": "203.0.113.75"}

        ip = middleware._get_client_ip(request)
        assert ip == "203.0.113.75"

    def test_rate_limit_response_structure(self):
        """The 429 response should have the correct JSON structure."""
        app = MagicMock()
        middleware = RateLimitMiddleware(app, requests_per_minute=100)

        response = middleware._rate_limit_response(remaining=0)

        assert response.status_code == 429
        assert response.headers["Retry-After"] == "60"
        assert response.headers["X-RateLimit-Limit"] == "100"
        assert response.headers["X-RateLimit-Remaining"] == "0"

    @pytest.mark.asyncio
    async def test_cleanup_removes_full_buckets(self):
        """Bucket cleanup should remove buckets that are at full capacity."""
        app = MagicMock()
        middleware = RateLimitMiddleware(app, requests_per_minute=60, burst_size=10)
        middleware._redis_available = False

        # Create a bucket that has been idle (full capacity)
        idle_bucket = TokenBucket(rate=1.0, capacity=10)
        idle_bucket.tokens = 10.0
        middleware._buckets["ip:idle-client"] = idle_bucket

        # Force cleanup by setting last_cleanup far in the past
        middleware._last_cleanup = time.monotonic() - 600

        middleware._maybe_cleanup()

        assert "ip:idle-client" not in middleware._buckets


# =============================================================================
# Redis fixed-window counter
# =============================================================================


class _FakePipeline:
    """Records INCR/EXPIRE calls and returns a monotonic count per key."""

    def __init__(self, counts: dict[str, int], expire_calls: list[tuple[str, int]]):
        self._counts = counts
        self._expire_calls = expire_calls
        self._queued: list[tuple[str, str, int]] = []

    def incr(self, key: str) -> None:
        self._queued.append(("incr", key, 0))

    def expire(self, key: str, ttl: int) -> None:
        self._queued.append(("expire", key, ttl))

    async def execute(self) -> list:
        results = []
        for op, key, ttl in self._queued:
            if op == "incr":
                self._counts[key] = self._counts.get(key, 0) + 1
                results.append(self._counts[key])
            else:
                self._expire_calls.append((key, ttl))
                results.append(True)
        self._queued = []
        return results


class _FakeRedis:
    def __init__(self):
        self.counts: dict[str, int] = {}
        self.expire_calls: list[tuple[str, int]] = []

    def pipeline(self) -> _FakePipeline:
        return _FakePipeline(self.counts, self.expire_calls)


class TestRedisFixedWindow:
    """The Redis counter must reset on its own once a window elapses.

    Regression guard: the counter key used to be a bare ``rl:<client>`` whose
    TTL was refreshed by an unconditional EXPIRE on every request. Any caller
    polling faster than the window (notably the container healthcheck, every
    30s against a 60s window) kept the key alive indefinitely, so its count
    accumulated without bound and the caller was throttled permanently.
    """

    @pytest.mark.asyncio
    async def test_window_is_encoded_in_the_key(self):
        """Each window gets its own key, so counts cannot carry across."""
        app = MagicMock()
        middleware = RateLimitMiddleware(app, requests_per_minute=100)
        fake = _FakeRedis()
        middleware._get_redis = AsyncMock(return_value=fake)

        with patch("app.middleware.rate_limit.time.time", return_value=1_000_000.0):
            await middleware._check_redis("ip:1.2.3.4")
        with patch("app.middleware.rate_limit.time.time", return_value=1_000_061.0):
            await middleware._check_redis("ip:1.2.3.4")

        assert set(fake.counts) == {
            "rl:ip:1.2.3.4:999960",
            "rl:ip:1.2.3.4:1000020",
        }
        # Two distinct windows, each counted once — not one key counted twice.
        assert all(c == 1 for c in fake.counts.values())

    @pytest.mark.asyncio
    async def test_counter_resets_across_windows(self):
        """A client at the limit in one window is allowed again in the next."""
        app = MagicMock()
        middleware = RateLimitMiddleware(app, requests_per_minute=3)
        fake = _FakeRedis()
        middleware._get_redis = AsyncMock(return_value=fake)

        with patch("app.middleware.rate_limit.time.time", return_value=1_000_000.0):
            for _ in range(3):
                allowed, _ = await middleware._check_redis("ip:5.6.7.8")
                assert allowed
            allowed, remaining = await middleware._check_redis("ip:5.6.7.8")
            assert allowed is False
            assert remaining == 0

        # Next window: budget is restored without any TTL having to lapse.
        with patch("app.middleware.rate_limit.time.time", return_value=1_000_060.0):
            allowed, remaining = await middleware._check_redis("ip:5.6.7.8")
            assert allowed is True
            assert remaining == 2

    @pytest.mark.asyncio
    async def test_frequent_poller_is_never_throttled(self):
        """The healthcheck pattern: one call every 30s must never hit 429.

        This is the exact scenario that marked the API unhealthy after ~50
        minutes while /health itself still returned 200.
        """
        app = MagicMock()
        middleware = RateLimitMiddleware(app, requests_per_minute=100)
        fake = _FakeRedis()
        middleware._get_redis = AsyncMock(return_value=fake)

        now = 1_000_000.0
        for _ in range(240):  # 240 probes x 30s = 2 hours
            with patch("app.middleware.rate_limit.time.time", return_value=now):
                allowed, _ = await middleware._check_redis("ip:127.0.0.1")
            assert allowed, "healthcheck probe was rate-limited"
            now += 30

        # At most 2 probes land in any single 60s window.
        assert max(fake.counts.values()) <= 2

    @pytest.mark.asyncio
    async def test_health_endpoints_bypass_the_limiter(self):
        """/health* must not consume budget or ever return 429."""
        app = MagicMock()
        middleware = RateLimitMiddleware(app, requests_per_minute=1, burst_size=1)
        middleware._redis_available = False

        for path in ("/health", "/health/live", "/health/ready"):
            for _ in range(5):
                resp = await middleware.dispatch(
                    _make_request(path, client_host="10.0.0.9"), _ok_call_next
                )
                assert resp.status_code == 200

        # Exempt paths never allocate a bucket.
        assert middleware._buckets == {}

    @pytest.mark.asyncio
    async def test_reset_header_points_at_the_real_window_boundary(self):
        """X-RateLimit-Reset must be the window end, not 'now + 60'."""
        app = MagicMock()
        middleware = RateLimitMiddleware(app, requests_per_minute=100)
        middleware._redis_available = False

        with patch("app.middleware.rate_limit.time.time", return_value=1_000_030.0):
            resp = await middleware.dispatch(
                _make_request("/api/v1/data", client_host="10.0.0.10"), _ok_call_next
            )

        # Window began at 1_000_020 and ends at 1_000_080 — not 1_000_090.
        assert resp.headers["X-RateLimit-Reset"] == "1000080"
