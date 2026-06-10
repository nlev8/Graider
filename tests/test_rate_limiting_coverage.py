"""Phase 4.6 PR1 — rate limiting coverage regression guard.

Pins the `@limiter.limit(...)` decorators added to public-facing routes
so a future refactor can't silently remove them. Also verifies
backend/extensions.py's production Redis requirement (raises RuntimeError
when REDIS_URL is unset and FLASK_ENV != development).

What this test does NOT do:
  - Exercise actual rate-limit enforcement at HTTP layer (requires live
    Redis or in-memory limiter + Flask test client, and would be flaky).
    The existing tests that use the routes implicitly confirm the
    decorators don't break anything; this test only pins their presence.
  - Police every future route for limits. Rate-limit selection is a
    per-endpoint judgment; this test maintains a fixed list of
    'must-have-limits' routes rather than trying to infer policy.

Maintainer note: when adding a new public (no-auth) route with
user-controlled input, add it to EXPECTED_LIMITS below.
"""
from __future__ import annotations

import ast
import os
import pathlib

import pytest


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


# (file_relative_path, route_path_substring, expected_limit_spec_substring)
# The limit_spec check is substring-based (e.g. "10 per minute") so
# tightening/loosening by updating both spec + test is explicit.
EXPECTED_LIMITS = [
    (
        "backend/routes/student_portal_routes.py",
        "/api/student/join/",
        "30 per minute",
    ),
    (
        "backend/routes/student_portal_routes.py",
        "/api/student/submit/",
        "10 per minute",
    ),
    (
        "backend/routes/stripe_routes.py",
        "/api/stripe/webhook",
        "100 per minute",
    ),
    (
        # audit #7: district-admin login is a single shared password — needs a
        # dedicated limit so the global 100/min default can't be used to brute force it.
        "backend/routes/district_routes.py",
        "/api/district/auth",
        "10 per minute",
    ),
]


def _find_route_decorators(tree: ast.AST) -> list[tuple[ast.FunctionDef, list[ast.expr]]]:
    """Return (funcdef, decorator_list) for every top-level function with decorators."""
    results: list[tuple[ast.FunctionDef, list[ast.expr]]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.decorator_list:
            results.append((node, node.decorator_list))
    return results


def _decorator_call_target(dec: ast.expr) -> str | None:
    """Return 'module.func' for `@x.y(...)` decorator call forms. None otherwise."""
    if isinstance(dec, ast.Call):
        func = dec.func
        if isinstance(func, ast.Attribute):
            if isinstance(func.value, ast.Name):
                return f"{func.value.id}.{func.attr}"
            if isinstance(func.value, ast.Attribute):  # nested attr
                return f"...{func.value.attr}.{func.attr}"
    return None


def _decorator_route_path(dec: ast.expr) -> str | None:
    """If decorator is `@<bp>.route('...', methods=...)`, return the path string."""
    if not isinstance(dec, ast.Call):
        return None
    func = dec.func
    if not (isinstance(func, ast.Attribute) and func.attr == "route"):
        return None
    if not dec.args:
        return None
    first = dec.args[0]
    if isinstance(first, ast.Constant) and isinstance(first.value, str):
        return first.value
    return None


def _decorator_limit_spec(dec: ast.expr) -> str | None:
    """If decorator is `@limiter.limit('...')`, return the spec string."""
    if not isinstance(dec, ast.Call):
        return None
    func = dec.func
    # Accept both @limiter.limit(...) and @<aliased>.limit(...)
    if not (isinstance(func, ast.Attribute) and func.attr == "limit"):
        return None
    if not dec.args:
        return None
    first = dec.args[0]
    if isinstance(first, ast.Constant) and isinstance(first.value, str):
        return first.value
    return None


@pytest.mark.parametrize("file_rel,path_sub,limit_sub", EXPECTED_LIMITS)
def test_route_has_expected_rate_limit(file_rel, path_sub, limit_sub):
    """Each (file, route) entry must have the expected @limiter.limit decorator."""
    path = REPO_ROOT / file_rel
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    matched_funcs: list[tuple[ast.FunctionDef, list[str]]] = []
    for fn, decs in _find_route_decorators(tree):
        route_paths = [p for p in (_decorator_route_path(d) for d in decs) if p]
        if any(path_sub in rp for rp in route_paths):
            limits = [spec for spec in (_decorator_limit_spec(d) for d in decs) if spec]
            matched_funcs.append((fn, limits))

    assert matched_funcs, (
        f"No route matching path substring {path_sub!r} found in {file_rel}. "
        f"Did the route get renamed or removed? Update EXPECTED_LIMITS."
    )

    for fn, limits in matched_funcs:
        assert any(limit_sub in spec for spec in limits), (
            f"Route {path_sub!r} in {file_rel} (function {fn.name!r} at line {fn.lineno}) "
            f"is missing @limiter.limit decorator with spec containing {limit_sub!r}. "
            f"Found limits: {limits or 'NONE'}"
        )


def test_extensions_enforces_redis_in_production(monkeypatch):
    """backend/extensions.py must raise RuntimeError when REDIS_URL is unset
    in non-dev FLASK_ENV. Prevents silent per-worker fallback in prod.
    """
    # Clear Redis + set prod-like env
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.setenv("FLASK_ENV", "production")

    # Force re-evaluation of extensions.py module
    import sys
    sys.modules.pop("backend.extensions", None)

    with pytest.raises(RuntimeError, match="REDIS_URL is required"):
        import backend.extensions  # noqa: F401


def test_extensions_allows_in_memory_in_development(monkeypatch):
    """Dev mode tolerates missing REDIS_URL."""
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.setenv("FLASK_ENV", "development")

    import sys
    sys.modules.pop("backend.extensions", None)
    import backend.extensions
    assert backend.extensions.limiter is not None


def test_extensions_startup_probe_failure_fails_closed_in_production(monkeypatch):
    """Hardening sprint PR1 sub-item (2026-06-09 reconciliation, Security
    level-8 'fails closed'): when REDIS_URL is SET but the startup Redis
    probe fails in production, backend/extensions.py must raise
    RuntimeError (non-zero exit) instead of silently degrading to
    per-worker memory:// rate limits for the process lifetime.

    Same class of behavior as the missing-REDIS_URL check: a broken
    storage backend at boot is a deploy-blocking config/infra error in
    prod, not a degradation to absorb.
    """
    monkeypatch.setenv("REDIS_URL", "redis://redis.invalid:6379/0")
    monkeypatch.setenv("FLASK_ENV", "production")

    # extensions.py probes via `redis.from_url(...).ping()` — make the
    # probe fail at the from_url call (covers DNS/conn/auth failures alike;
    # the module's except block catches any Exception from the probe).
    import redis

    def _probe_fails(*args, **kwargs):
        raise redis.exceptions.ConnectionError("simulated: Redis unreachable at startup")

    monkeypatch.setattr(redis, "from_url", _probe_fails)

    import sys
    sys.modules.pop("backend.extensions", None)
    with pytest.raises(RuntimeError, match="Redis .*unreachable at startup"):
        import backend.extensions  # noqa: F401


def test_extensions_startup_probe_failure_falls_back_in_dev(monkeypatch):
    """Dev/test keeps the 2026-05-20 hotfix #5 behavior: probe failure
    falls back to memory:// without raising (local dev shouldn't require
    a live Redis just because REDIS_URL is set in .env)."""
    monkeypatch.setenv("REDIS_URL", "redis://redis.invalid:6379/0")
    monkeypatch.setenv("FLASK_ENV", "development")

    import redis

    def _probe_fails(*args, **kwargs):
        raise redis.exceptions.ConnectionError("simulated: Redis unreachable at startup")

    monkeypatch.setattr(redis, "from_url", _probe_fails)

    import sys
    sys.modules.pop("backend.extensions", None)
    import backend.extensions

    assert backend.extensions.limiter is not None
    assert backend.extensions._storage_uri == "memory://"


def test_extensions_global_default_is_100_per_minute(monkeypatch):
    """Phase 4.6 tightened the global default from 200/min → 100/min.

    Inspects the parsed RateLimitItem object directly (limit.amount,
    limit.multiples, GRANULARITY.name) rather than substring-matching
    against str(RuntimeLimit), which CONTAINS the function pointer
    repr like `key_func=<function get_remote_address at 0x7f2000445080>`.
    A pointer hex address coincidentally containing '200' triggered a
    false-positive failure on PR #256 CI. (Codex investigation confirmed
    main has the same brittleness — failure depends on memory layout.)
    """
    monkeypatch.setenv("FLASK_ENV", "development")
    monkeypatch.delenv("REDIS_URL", raising=False)

    import sys
    sys.modules.pop("backend.extensions", None)
    import backend.extensions

    defaults = list(backend.extensions.limiter.limit_manager.default_limits)
    # default_limits is a list of LimitGroup wrappers; each .limit is the
    # parsed RateLimitItem with .amount, .multiples, and a GRANULARITY.
    parsed = [lim.limit for lim in defaults]
    assert any(
        getattr(p, "amount", None) == 100
        and getattr(p, "multiples", None) == 1
        and getattr(type(p), "GRANULARITY", None) is not None
        and type(p).GRANULARITY.name == "minute"
        for p in parsed
    ), f"Expected a '100 per minute' default limit; got {parsed!r}"
    # Confirm we are NOT still at the old 200/min (or any /min variant).
    assert not any(
        getattr(p, "amount", None) == 200
        and getattr(p, "multiples", None) == 1
        and getattr(type(p), "GRANULARITY", None) is not None
        and type(p).GRANULARITY.name == "minute"
        for p in parsed
    ), f"Global default still '200 per minute' — tightening regressed: {parsed!r}"


class TestProxyFixClientIp:
    """Phase 4.6 follow-up — ProxyFix must expose the stable real client IP.

    Railway's ingress rotates its edge IP across requests (observed
    .22 → .37 → .39 → .20 → .24 in back-to-back probes 2026-04-18).
    With ``ProxyFix(x_for=1)`` werkzeug sets ``request.remote_addr`` to
    ``XFF[-1]`` — the rotating edge — and every request from the same
    client got its own rate-limit bucket. flask-limiter could never
    fire.

    ``x_for=2`` picks ``XFF[-2]`` which, on Railway's canonical 2-hop
    chain ``[client, edge]``, is the stable client IP.

    Spoofing: Railway always APPENDS the real TCP source as the
    penultimate XFF entry. Empirically a client sending
    ``X-Forwarded-For: 6.6.6.6`` produced
    ``"6.6.6.6, 99.77.78.219, 157.52.98.26"`` at the app, so ``[-2]``
    was still the real client. These tests pin that behaviour.
    """

    def _build_app_with_proxyfix(self, x_for: int = 2):
        """Return a minimal Flask app with ProxyFix wired the way app.py does."""
        from flask import Flask, request
        from werkzeug.middleware.proxy_fix import ProxyFix

        app = Flask(__name__)
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=x_for, x_proto=1, x_host=1)

        @app.route("/echo")
        def _echo():  # pragma: no cover — exercised via test_client below
            return {"remote_addr": request.remote_addr}

        return app

    def test_x_for_2_picks_second_to_last_xff_entry(self):
        """The canonical Railway chain [client, edge] resolves to client."""
        app = self._build_app_with_proxyfix(x_for=2)
        with app.test_client() as client:
            resp = client.get(
                "/echo",
                headers={"X-Forwarded-For": "99.77.78.219, 157.52.98.22"},
                environ_overrides={"REMOTE_ADDR": "157.52.98.22"},
            )
            assert resp.json["remote_addr"] == "99.77.78.219"

    def test_x_for_2_survives_spoofed_leading_xff_entry(self):
        """A client-injected leading XFF entry does NOT poison remote_addr.

        Because Railway always appends the real TCP source BEFORE its own
        edge IP, the [-2] position is insulated from client injection.
        """
        app = self._build_app_with_proxyfix(x_for=2)
        with app.test_client() as client:
            resp = client.get(
                "/echo",
                headers={"X-Forwarded-For": "6.6.6.6, 99.77.78.219, 157.52.98.26"},
                environ_overrides={"REMOTE_ADDR": "157.52.98.26"},
            )
            assert resp.json["remote_addr"] == "99.77.78.219", (
                "Spoofed leading XFF entry leaked into remote_addr — "
                "rate-limit poisoning possible."
            )

    def test_x_for_2_survives_multiple_spoofed_entries(self):
        """Two client-injected entries still can't reach position [-2]."""
        app = self._build_app_with_proxyfix(x_for=2)
        with app.test_client() as client:
            resp = client.get(
                "/echo",
                headers={
                    "X-Forwarded-For":
                        "6.6.6.6, 7.7.7.7, 99.77.78.219, 157.52.98.26",
                },
                environ_overrides={"REMOTE_ADDR": "157.52.98.26"},
            )
            assert resp.json["remote_addr"] == "99.77.78.219"

    def test_x_for_1_would_expose_rotating_edge_ip_regression_guard(self):
        """Regression guard — pre-fix config gave the rotating edge IP.

        Verifies the bug is real by demonstrating what x_for=1 does with
        Railway's chain. If this assertion ever changes, werkzeug
        semantics have shifted and the fix needs re-evaluation.
        """
        app = self._build_app_with_proxyfix(x_for=1)
        with app.test_client() as client:
            resp = client.get(
                "/echo",
                headers={"X-Forwarded-For": "99.77.78.219, 157.52.98.22"},
                environ_overrides={"REMOTE_ADDR": "157.52.98.22"},
            )
            # Pre-fix behavior: remote_addr is the last XFF entry = rotating edge
            assert resp.json["remote_addr"] == "157.52.98.22"

    def test_x_for_2_falls_back_when_xff_missing(self):
        """Local / direct requests without XFF still get SOME remote_addr.

        ProxyFix only rewrites REMOTE_ADDR when there are enough trusted
        hops to consume — if XFF is empty or too short, it leaves the
        direct TCP source in place. Critical for local dev + unit tests.
        """
        app = self._build_app_with_proxyfix(x_for=2)
        with app.test_client() as client:
            resp = client.get(
                "/echo",
                environ_overrides={"REMOTE_ADDR": "10.0.0.5"},
            )
            assert resp.json["remote_addr"] == "10.0.0.5"


def test_app_py_proxyfix_uses_x_for_2():
    """Pin the production ProxyFix config so a future refactor can't
    silently revert to x_for=1 and re-break rate limiting on Railway.
    """
    import ast

    app_py_path = REPO_ROOT / "backend" / "app.py"
    tree = ast.parse(app_py_path.read_text())

    proxyfix_calls = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        # Match ProxyFix(...) at any attribute depth (ProxyFix, x.ProxyFix, etc.)
        if isinstance(func, ast.Name) and func.id == "ProxyFix":
            proxyfix_calls.append(node)
        elif isinstance(func, ast.Attribute) and func.attr == "ProxyFix":
            proxyfix_calls.append(node)

    assert proxyfix_calls, "backend/app.py must instantiate ProxyFix"

    for call in proxyfix_calls:
        x_for = None
        for kw in call.keywords:
            if kw.arg == "x_for" and isinstance(kw.value, ast.Constant):
                x_for = kw.value.value
        assert x_for == 2, (
            f"ProxyFix at line {call.lineno} uses x_for={x_for} — must be 2. "
            "x_for=1 puts Railway's rotating edge IP in request.remote_addr "
            "which silently disables every flask-limiter @limit on Railway. "
            "If Railway's proxy topology changes, update the comment and "
            "the ProxyFixClientIp tests together."
        )
