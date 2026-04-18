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

2026-04-18 revision: fixed key-format bug discovered by Codex review.
flask-limiter 4.1.1's limit_manager stores decorated limits keyed on
the 3-part form ``module.name.qualname`` (see
``flask_limiter.util.get_qualified_name``). The earlier version of this
endpoint looked up with ``f"{module}.{name}"`` (2-part), which never
hit. Result: every ``limits_found: []`` was a key miss, not proof of
missing registration. This revision uses ``get_qualified_name`` for the
probe and also dumps the raw registry so we can compare the true
registered keys against what the url_map actually resolves to.
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
    the limiter's storage backend, the raw decorated-limits registry, and
    what qualified name the url_map resolves for a known rate-limited route.
    """
    if not _check_debug_secret():
        # 404 (not 401) so the endpoint doesn't advertise its existence
        # to scanners. Caller with the right secret gets the diagnostic.
        return jsonify({"error": "Not found"}), 404

    # Import the canonical key function so our lookup matches what
    # flask-limiter uses at decoration and request time.
    try:
        from flask_limiter.util import get_qualified_name
    except ImportError:
        get_qualified_name = None

    # Attempt to introspect limiter's internal state. Guard every access
    # because flask-limiter's private attrs may rename across minor versions.
    storage = getattr(limiter, '_storage', None)
    storage_type = type(storage).__name__ if storage is not None else 'none'

    try:
        storage_check = storage.check() if storage is not None else None
    except Exception as e:
        storage_check = f'check-error: {type(e).__name__}: {e}'

    # Dump the RAW decorated-limits registry — this is the source of truth
    # for what flask-limiter actually knows about, independent of any
    # url_map / view_fn resolution. Compare these keys against the
    # url_map_qnames map below to confirm module-path alignment.
    try:
        registry = getattr(limiter.limit_manager, '_decorated_limits', None)
        if registry is None:
            registry_keys = 'registry-attr-missing'
            registry_count = None
        else:
            registry_keys = sorted(registry.keys())
            registry_count = len(registry_keys)
    except Exception as e:
        registry_keys = f'registry-error: {type(e).__name__}: {e}'
        registry_count = None

    # For each URL rule, compute the qualified name the way flask-limiter
    # does and check whether the registry has it. This is the correct
    # (3-part) equivalent of the old introspection loop.
    try:
        from flask import current_app
        url_map_qnames: dict[str, dict] = {}
        for rule in current_app.url_map.iter_rules():
            endpoint = rule.endpoint
            view_fn = current_app.view_functions.get(endpoint)
            if view_fn is None:
                continue
            if get_qualified_name is not None:
                try:
                    qname = get_qualified_name(view_fn)
                except Exception:
                    qname = None
            else:
                qname = None

            try:
                limits_for_qname = limiter.limit_manager.decorated_limits(qname) if qname else []
            except Exception:
                limits_for_qname = []

            if limits_for_qname:
                url_map_qnames[f"{endpoint} ({rule.rule})"] = {
                    'qname': qname,
                    'limits': [str(l) for l in limits_for_qname],
                }
        matched_count = len(url_map_qnames)
    except Exception as e:
        url_map_qnames = f'introspection-error: {type(e).__name__}: {e}'
        matched_count = None

    try:
        default_limits = [str(l) for l in limiter.limit_manager.default_limits]
    except Exception as e:
        default_limits = f'introspection-error: {type(e).__name__}: {e}'

    # Resolve /api/student/join/<code> through Flask's url_map and use the
    # CORRECT 3-part qname for the lookup. This tells us unambiguously
    # whether the limit registered via the @limiter.limit decorator is
    # findable by the same callable Flask would dispatch to.
    try:
        from flask import current_app
        with current_app.test_request_context('/api/student/join/TESTCODE', method='GET'):
            endpoint = request.url_rule.endpoint if request.url_rule else None
            view_fn = current_app.view_functions.get(endpoint) if endpoint else None
            if view_fn is not None and get_qualified_name is not None:
                probe_qname = get_qualified_name(view_fn)
                probe_legacy_2part = f"{view_fn.__module__}.{view_fn.__name__}"
            else:
                probe_qname = None
                probe_legacy_2part = None
            try:
                probe_limits = (
                    limiter.limit_manager.decorated_limits(probe_qname)
                    if probe_qname else None
                )
            except Exception:
                probe_limits = None
        probe_result = {
            'route_tested': '/api/student/join/TESTCODE',
            'resolved_endpoint': endpoint,
            'probe_qname_3part': probe_qname,
            'probe_qname_2part_legacy': probe_legacy_2part,
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
            'registry_count': registry_count,
            'registry_keys': registry_keys,
            'url_map_matched_count': matched_count,
            'url_map_qnames_matched': url_map_qnames,
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
