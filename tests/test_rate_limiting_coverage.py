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


def test_extensions_global_default_is_100_per_minute(monkeypatch):
    """Phase 4.6 tightened the global default from 200/min → 100/min."""
    monkeypatch.setenv("FLASK_ENV", "development")
    monkeypatch.delenv("REDIS_URL", raising=False)

    import sys
    sys.modules.pop("backend.extensions", None)
    import backend.extensions

    # flask-limiter exposes resolved limit strings via limit_manager
    default_strs = [str(lim) for lim in backend.extensions.limiter.limit_manager.default_limits]
    assert any("100" in s for s in default_strs), (
        f"Expected a '100 per minute' default limit; got {default_strs}"
    )
    # And confirm we are NOT still at the old 200
    assert not any("200" in s for s in default_strs), (
        f"Global default still contains '200' — tightening regressed: {default_strs}"
    )
