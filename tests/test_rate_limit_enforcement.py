"""Phase 4.6 follow-up — end-to-end HTTP-layer rate limit enforcement.

Previous tests pinned that ``@limiter.limit(...)`` decorators exist on the
expected routes (``tests/test_rate_limiting_coverage.py``) and that
ProxyFix produces the right client IP (``TestProxyFixClientIp`` in the
same file). Both are necessary but not sufficient — the Phase 4.6 bug
discovered 2026-04-18 was that limits existed in the registry and
ProxyFix *could* work, but a misconfigured ``x_for=1`` made every
request look like a different client and the limiter never fired.

This test exercises the complete HTTP request path: URL routing →
ProxyFix → flask-limiter ``before_request`` hook → bucket
increment → 429 on overflow. It floods a known rate-limited route
(``/api/student/join/<code>`` at 30/min) past its threshold from a
synthetic client IP and asserts that at least one request is rate-
limited.

No external services are required — the limiter runs with
``memory://`` storage when ``FLASK_ENV=development``. Production uses
Redis via the hard requirement in ``backend/extensions.py``, but the
request-path logic that determines whether a limit fires is
storage-independent.

Each test uses a UNIQUE synthetic client IP so the in-memory limiter
buckets don't leak between tests within the suite. IPs are drawn from
TEST-NET-3 (203.0.113.0/24) per RFC 5737.
"""
from __future__ import annotations

import os

import pytest


# FLASK_ENV must be set BEFORE backend.app is imported — other test files
# import it with this same side effect, so this is idempotent.
os.environ.setdefault("FLASK_ENV", "development")
os.environ.setdefault("SUPABASE_URL", "https://stub.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "stub")
os.environ.setdefault(
    "SUPABASE_JWT_SECRET",
    "stub-jwt-secret-stub-jwt-secret-stub-jwt-secret-stub-jwt-secret-stub",
)
os.environ.setdefault("FLASK_SECRET_KEY", "x" * 64)


@pytest.fixture
def test_client():
    """Flask test client using the real backend.app.

    Intentionally does NOT reimport backend modules — other tests in the
    suite share backend.app's session-scoped state (tool registry merge,
    Supabase client cache, etc.) and force-reimporting breaks them.

    Resets the limiter's in-memory storage on teardown (and entry) so
    tests are hermetic even when earlier tests in the same session
    incremented counters against overlapping keys.

    Relies on FLASK_ENV being set to a dev/test value before import so
    the limiter falls back to ``memory://`` storage instead of raising
    the production Redis requirement.
    """
    from backend.app import app
    from backend.extensions import limiter

    def _reset_limiter_storage():
        """Clear in-memory bucket counts to prevent cross-test leakage.

        flask-limiter's MemoryStorage keeps bucket state across several
        internal containers (Counter + dicts for events, expirations,
        sliding-window keys, locks). Clear each defensively — signature
        of ``reset()`` varies across versions and doesn't always wipe
        every container.
        """
        storage = getattr(limiter, "_storage", None)
        if storage is None:
            return
        for attr_name in ("storage", "events", "expirations",
                          "sliding_window_keys", "locks"):
            container = getattr(storage, attr_name, None)
            if container is not None and hasattr(container, "clear"):
                try:
                    container.clear()
                except Exception:
                    pass

    # Re-enable the limiter if an earlier test with
    # ``RATELIMIT_ENABLED=False`` called ``limiter.init_app(their_app)`` —
    # flask-limiter caches the enabled flag on the shared Limiter
    # instance, so the disabling leaks across tests. Restored here (and
    # on teardown) to keep this test hermetic without touching other
    # tests.
    previous_enabled = getattr(limiter, "enabled", True)
    limiter.enabled = True

    _reset_limiter_storage()
    app.config["TESTING"] = True
    app.config["RATELIMIT_ENABLED"] = True
    try:
        with app.test_client() as client:
            yield client
    finally:
        _reset_limiter_storage()
        limiter.enabled = previous_enabled


def _flood(client, headers, count):
    """Send N GETs, return list of status codes."""
    return [
        client.get("/api/student/join/FAKECODE", headers=headers).status_code
        for _ in range(count)
    ]


# Each test uses a DISTINCT client IP so the in-memory limiter doesn't
# leak state across tests in this file. TEST-NET-3 per RFC 5737.
_CLIENT_IP_FIRES = "203.0.113.5"
_CLIENT_IP_PARTITION_A = "203.0.113.22"
_CLIENT_IP_PARTITION_B = "203.0.113.23"
_CLIENT_IP_ROTATE = "203.0.113.77"


# ---------------------------------------------------------------------------
# Core enforcement test
# ---------------------------------------------------------------------------

def test_student_join_rate_limit_fires_after_30_per_minute(test_client):
    """30/min limit on ``/api/student/join/<code>`` must enforce in HTTP path.

    Sends 35 requests from the same synthetic client IP (via
    ``X-Forwarded-For`` that ProxyFix(x_for=2) resolves to a stable
    client-side value). Expects at least one 429 within the batch.

    If this assertion fails with zero 429s, one of the following is
    broken end-to-end:
      - ProxyFix is not in the WSGI middleware chain
      - ``x_for`` isn't wired such that the same XFF yields the same
        ``request.remote_addr``
      - the limit decorator isn't registered under the qname that
        flask-limiter looks up at request time
      - the before_request hook isn't running (extension not
        initialised or disabled)
      - the rate-limit bucket isn't actually incrementing across
        requests (storage pointer mismatch, key randomness)
    """
    headers = {"X-Forwarded-For": f"{_CLIENT_IP_FIRES}, 198.51.100.99"}
    statuses = _flood(test_client, headers, 35)

    rate_limited_indices = [i for i, code in enumerate(statuses) if code == 429]

    assert rate_limited_indices, (
        "Expected >=1x 429 in 35 requests to a 30-per-minute route. "
        f"Got statuses: {statuses}. "
        "Rate limit is not firing at the HTTP layer — see the failure "
        "modes listed in the docstring."
    )

    # First request cannot be rate-limited (bucket is fresh for this IP).
    assert statuses[0] != 429, (
        f"First request returned 429 — bucket was not empty for {_CLIENT_IP_FIRES}. "
        "Did an earlier test in this session leak limiter state onto this IP?"
    )

    # The 429 must happen at or after the 31st request (0-indexed: 30).
    first_429 = rate_limited_indices[0]
    assert first_429 >= 30, (
        f"First 429 was at request #{first_429 + 1}, expected at or after #31 "
        f"for a 30/min limit. Full status sequence: {statuses}"
    )


def test_student_join_rate_limit_keys_on_stable_client_ip(test_client):
    """Two distinct clients must NOT share a bucket.

    Send 25 requests as client A (below the 30/min threshold), then 25
    as client B — client B should still see zero 429s because their
    bucket starts fresh.
    """
    headers_a = {"X-Forwarded-For": f"{_CLIENT_IP_PARTITION_A}, 198.51.100.99"}
    headers_b = {"X-Forwarded-For": f"{_CLIENT_IP_PARTITION_B}, 198.51.100.99"}

    a_statuses = _flood(test_client, headers_a, 25)
    b_statuses = _flood(test_client, headers_b, 25)

    assert 429 not in a_statuses, (
        f"Client A hit 429 within first 25 requests (threshold 30): {a_statuses}"
    )
    assert 429 not in b_statuses, (
        "Client B saw 429s despite having sent <30 requests. Buckets "
        f"are NOT being partitioned by client IP. A={a_statuses} B={b_statuses}"
    )


def test_student_join_rate_limit_ignores_rotating_last_xff_hop(test_client):
    """Rotating the LAST XFF entry (Railway edge) must NOT create new buckets.

    This is the exact prod bug from 2026-04-18: Railway rotates its
    edge IP per request, and with ProxyFix(x_for=1) every request
    looked like a different client. With ProxyFix(x_for=2) the second-
    to-last entry (real client) stays stable and the bucket accumulates
    correctly.
    """
    statuses = []
    for i in range(35):
        # Rotate the last hop per request; second-to-last (client) stays put.
        rotating_last = f"198.51.100.{(i % 20) + 1}"
        headers = {"X-Forwarded-For": f"{_CLIENT_IP_ROTATE}, {rotating_last}"}
        resp = test_client.get("/api/student/join/FAKECODE", headers=headers)
        statuses.append(resp.status_code)

    rate_limited = [s for s in statuses if s == 429]
    assert rate_limited, (
        "Rotating the last XFF hop caused new rate-limit buckets per "
        "request — the exact bug that broke Phase 4.6 in production. "
        f"Status sequence: {statuses}"
    )
