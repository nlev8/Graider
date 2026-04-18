"""
Temporary debug routes — TO BE DELETED after investigation completes.

Added 2026-04-17 to diagnose why flask-limiter rate limits aren't firing
in production (see session memory + PR #89 Codex+Explore cross-check).

Gated by a shared-secret header (X-Debug-Secret matching the
DEBUG_ENDPOINT_SECRET env var) rather than @require_admin because the
admin decorator requires a JWT bearer token that's awkward to pass
from a browser address bar. Shared-secret lets the operator curl once
and move on.

Remove this file + its registration in backend/routes/__init__.py after
the rate-limit investigation resolves. Also unset the
DEBUG_ENDPOINT_SECRET env var on Railway.
"""
import os
import hmac
from flask import Blueprint, jsonify, request

from backend.extensions import limiter


debug_bp = Blueprint('debug', __name__)


def _check_debug_secret():
    """Constant-time-compare the incoming X-Debug-Secret header against env."""
    expected = os.getenv('DEBUG_ENDPOINT_SECRET', '')
    if not expected:
        return False
    provided = request.headers.get('X-Debug-Secret', '')
    return hmac.compare_digest(expected, provided)


@debug_bp.route('/api/_debug/limiter', methods=['GET'])
@limiter.exempt
def limiter_state():
    """Dump flask-limiter runtime state for debugging.

    Shared-secret-gated via X-Debug-Secret header. Returns JSON describing
    the limiter's storage backend, any registered decorated limits, whether
    headers are enabled, and what the current-request key-function
    resolution sees.
    """
    if not _check_debug_secret():
        # 404 (not 401) so the endpoint doesn't advertise its existence
        # to scanners. Caller with the right secret gets the diagnostic.
        return jsonify({"error": "Not found"}), 404

    # Attempt to introspect limiter's internal state. Guard every access
    # because flask-limiter's private attrs may rename across minor versions.
    storage = getattr(limiter, '_storage', None)
    storage_type = type(storage).__name__ if storage is not None else 'none'

    try:
        storage_check = storage.check() if storage is not None else None
    except Exception as e:
        storage_check = f'check-error: {type(e).__name__}: {e}'

    # flask-limiter 4.1.1: decorated_limits is a METHOD (callable_name: str) → list[RuntimeLimit]
    # Enumerate every Flask URL rule and query its limits to build the full decorated map.
    try:
        from flask import current_app
        decorated_by_endpoint: dict[str, list[str]] = {}
        for rule in current_app.url_map.iter_rules():
            endpoint = rule.endpoint
            view_fn = current_app.view_functions.get(endpoint)
            if view_fn is None:
                continue
            callable_name = f"{view_fn.__module__}.{view_fn.__name__}"
            try:
                limits_for_endpoint = limiter.limit_manager.decorated_limits(callable_name)
            except Exception:
                limits_for_endpoint = []
            if limits_for_endpoint:
                decorated_by_endpoint[f"{endpoint} ({rule.rule})"] = [str(l) for l in limits_for_endpoint]
        decorated_count = sum(len(v) for v in decorated_by_endpoint.values())
        decorated_endpoint_count = len(decorated_by_endpoint)
    except Exception as e:
        decorated_by_endpoint = f'introspection-error: {type(e).__name__}: {e}'
        decorated_count = 0
        decorated_endpoint_count = None

    try:
        default_limits = [str(l) for l in limiter.limit_manager.default_limits]
    except Exception as e:
        default_limits = f'introspection-error: {type(e).__name__}: {e}'

    # Resolve the current request's endpoint through Flask's url_map to see
    # what flask-limiter would use as the callable_name for THIS request path.
    # This tells us if the decorator-registration callable_name matches what
    # gets looked up at request time.
    try:
        from flask import current_app
        # Match /api/student/join/TESTCODE (typical rate-limited route)
        with current_app.test_request_context('/api/student/join/TESTCODE', method='GET'):
            endpoint = request.url_rule.endpoint if request.url_rule else None
            view_fn = current_app.view_functions.get(endpoint) if endpoint else None
            probe_callable_name = f"{view_fn.__module__}.{view_fn.__name__}" if view_fn else None
            probe_limits = limiter.limit_manager.decorated_limits(probe_callable_name) if probe_callable_name else None
        probe_result = {
            'route_tested': '/api/student/join/TESTCODE',
            'resolved_endpoint': endpoint,
            'resolved_callable_name': probe_callable_name,
            'limits_found': [str(l) for l in (probe_limits or [])],
        }
    except Exception as e:
        probe_result = f'probe-error: {type(e).__name__}: {e}'

    # Key function resolution — what does flask-limiter see as the rate-limit
    # key for THIS request?
    try:
        from flask_limiter.util import get_remote_address
        key_default = get_remote_address()
    except Exception as e:
        key_default = f'key-error: {type(e).__name__}: {e}'

    return jsonify({
        'storage': {
            'type': storage_type,
            'check_result': storage_check,
            'storage_uri_configured': getattr(limiter, '_storage_uri', None),
        },
        'limits': {
            'default': default_limits,
            'decorated_count_total': decorated_count,
            'decorated_endpoint_count': decorated_endpoint_count,
            'decorated_by_endpoint': decorated_by_endpoint,
        },
        'probe_student_join': probe_result,
        'config': {
            'enabled': getattr(limiter, 'enabled', 'unknown'),
            'headers_enabled': getattr(limiter, '_headers_enabled', 'unknown'),
            'in_memory_fallback_enabled': getattr(limiter, '_in_memory_fallback_enabled', 'unknown'),
            'storage_dead': getattr(limiter, '_storage_dead', 'unknown'),
            'swallow_errors': getattr(limiter, '_swallow_errors', 'unknown'),
        },
        'request_key_resolution': {
            'remote_addr': request.remote_addr,
            'x_forwarded_for': request.headers.get('X-Forwarded-For'),
            'x_real_ip': request.headers.get('X-Real-IP'),
            'get_remote_address_result': key_default,
        },
    })
