"""Regression tests for constant-time compares on OAuth state + nonce.

Source: 2026-05-14 dimensional review (state/nonce variants — deferred
from PR #372's security quintet because of lower blast radius). Issue
#373 tracks all 6 sites; this file pins the fix in place.

Each callback/launch function must compare state and nonce via
hmac.compare_digest. The previous `!=`/`==` operators were
timing-dependent — short-circuit byte-by-byte comparison leaks the
expected value via response-latency side-channel. Session-bound CSRF
tokens are short-lived but the vulnerability class is identical to
the PERIODIC_SYNC_SECRET case closed in PR #372.
"""
import inspect


def _src(func):
    return inspect.getsource(func)


class TestCleverCallback:
    """clever_routes.py:333 — `if state != expected_state`."""

    def test_clever_callback_uses_constant_time_state_compare(self):
        from backend.routes.clever_routes import clever_callback
        src = _src(clever_callback)
        assert "state != expected_state" not in src, (
            "clever_callback still uses != for state compare; "
            "switch to hmac.compare_digest (issue #373)"
        )
        assert "state == expected_state" not in src
        assert "hmac.compare_digest" in src, (
            "clever_callback must call hmac.compare_digest on state"
        )


class TestClassLinkCallback:
    """classlink_routes.py:237,258,348 — 2x state + 1x nonce."""

    def test_classlink_callback_uses_constant_time_state_compare(self):
        from backend.routes.classlink_routes import classlink_callback
        src = _src(classlink_callback)
        assert "state != expected_state" not in src, (
            "classlink_callback still uses != for state compare; "
            "switch to hmac.compare_digest (issue #373)"
        )
        assert "state == expected_state" not in src

    def test_classlink_callback_uses_constant_time_nonce_compare(self):
        from backend.routes.classlink_routes import classlink_callback
        src = _src(classlink_callback)
        assert "token_nonce != expected_nonce" not in src, (
            "classlink_callback still uses != for nonce compare"
        )
        assert "token_nonce == expected_nonce" not in src

    def test_classlink_callback_imports_hmac_compare_digest(self):
        from backend.routes.classlink_routes import classlink_callback
        src = _src(classlink_callback)
        # At least 3 compare_digest calls (2 state + 1 nonce)
        count = src.count("hmac.compare_digest")
        assert count >= 3, (
            f"classlink_callback should call hmac.compare_digest at "
            f"least 3 times (2 state + 1 nonce); found {count}"
        )


class TestLTILaunch:
    """lti_routes.py:113,131 — 1x state + 1x nonce."""

    def test_lti_launch_uses_constant_time_state_compare(self):
        from backend.routes.lti_routes import lti_launch
        src = _src(lti_launch)
        assert "state != expected_state" not in src, (
            "lti_launch still uses != for state compare"
        )
        assert "state == expected_state" not in src

    def test_lti_launch_uses_constant_time_nonce_compare(self):
        from backend.routes.lti_routes import lti_launch
        src = _src(lti_launch)
        assert "token_nonce != expected_nonce" not in src, (
            "lti_launch still uses != for nonce compare"
        )
        assert "token_nonce == expected_nonce" not in src

    def test_lti_launch_imports_hmac_compare_digest(self):
        from backend.routes.lti_routes import lti_launch
        src = _src(lti_launch)
        count = src.count("hmac.compare_digest")
        assert count >= 2, (
            f"lti_launch should call hmac.compare_digest at least 2 "
            f"times (1 state + 1 nonce); found {count}"
        )
