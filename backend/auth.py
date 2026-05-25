"""
Supabase JWT Authentication for Graider.
Validates Bearer tokens on all /api/ routes except public endpoints.
Supports both ES256 (JWKS) and HS256 (legacy secret) verification.
"""
import json
import os
import logging
import jwt
from jwt import PyJWKClient
from flask import request, jsonify, g, session

logger = logging.getLogger(__name__)

from backend.supabase_client import get_supabase as _get_supabase
import sentry_sdk

# Clever → Supabase account linking (uses storage.py for Supabase persistence)
def load_clever_links():
    """Load all clever_id → supabase_user_id mappings."""
    try:
        from backend.storage import list_keys, load
        keys = list_keys('clever_link:', 'system')
        links = {}
        for key in keys:
            data = load(key, 'system')
            if data and isinstance(data, dict):
                clever_id = key[len('clever_link:'):]
                links[clever_id] = data.get('supabase_user_id', '')
        return links
    except Exception as e:
        # Fallback to legacy file if storage not available
        sentry_sdk.capture_exception(e)
        legacy_path = os.path.expanduser("~/.graider_data/clever_links.json")
        try:
            with open(legacy_path, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}


def save_clever_link(clever_id, supabase_user_id):
    """Persist a clever_id → supabase_user_id link."""
    try:
        from backend.storage import save
        save(f'clever_link:{clever_id}', {'supabase_user_id': supabase_user_id}, 'system')
    except Exception as e:
        # Fallback to legacy file
        sentry_sdk.capture_exception(e)
        legacy_path = os.path.expanduser("~/.graider_data/clever_links.json")
        links = load_clever_links()
        links[clever_id] = supabase_user_id
        os.makedirs(os.path.dirname(legacy_path), exist_ok=True)
        with open(legacy_path, 'w') as f:
            json.dump(links, f)
    logger.info("Linked Clever account %s to Supabase user %s", clever_id, supabase_user_id)


def resolve_clever_user_id(clever_id):
    """Resolve a clever_id to a linked Supabase user_id, or return clever:{id}."""
    links = load_clever_links()
    return links.get(clever_id, f"clever:{clever_id}")


# Routes that don't require authentication
# SECURITY: Be explicit — only list endpoints that truly need to be public.
# Student dashboard/content endpoints use X-Student-Token (not JWT) for their own auth.
PUBLIC_PREFIXES = [
    '/api/student/join/',         # Anonymous join-code portal (GET assessment by code)
    '/api/student/submit/',       # Anonymous submission (join-code path, POST)
    '/api/student/class-submit/', # Class-based authenticated submission (X-Student-Token, not JWT)
    '/api/clever/',            # Clever OAuth flow (callback must be unauthenticated)
    '/api/classlink/',         # ClassLink OAuth flow (callback must be unauthenticated)
    '/api/lti/',               # LTI OIDC login, launch callback, JWKS (platform-initiated)
    '/api/district/',           # District admin setup (session-based auth, not JWT)
    '/api/sync/',               # Periodic sync webhook (auth via PERIODIC_SYNC_SECRET header)
]

PUBLIC_EXACT = [
    '/api/status',              # Grading status polling (used before auth check completes)
    '/api/stripe/webhook',      # Stripe webhook (verified via Stripe-Signature header)
    '/api/auth/notify-signup',  # Public signup notification (no JWT needed)
    '/api/auth/approve-user',   # One-click approval from admin email (HMAC-protected)
    '/api/student/login',       # Student email+code login (creates session token)
    '/api/student/session',     # Session validation (uses X-Student-Token)
    '/api/student/dashboard',   # Student dashboard (uses X-Student-Token, not JWT)
    '/api/student/shared-media', # Shared media access (public via join code)
]

# Student endpoints that use prefix matching (X-Student-Token auth, not JWT)
PUBLIC_PREFIXES += [
    '/api/student/content/',    # Class-based content access (uses X-Student-Token)
]

# JWKS client for ES256 verification (cached, refreshes automatically)
_jwks_client = None


def _get_jwks_client():
    """Lazy-init JWKS client from Supabase URL."""
    global _jwks_client
    if _jwks_client is None:
        supabase_url = os.getenv('SUPABASE_URL')
        if supabase_url:
            jwks_url = f"{supabase_url}/auth/v1/.well-known/jwks.json"
            _jwks_client = PyJWKClient(jwks_url)
    return _jwks_client


def get_jwt_secret():
    """Get the Supabase JWT secret from environment (HS256 fallback)."""
    secret = os.getenv('SUPABASE_JWT_SECRET')
    if not secret:
        raise RuntimeError('SUPABASE_JWT_SECRET not configured')
    return secret


def validate_token(token):
    """
    Validate a Supabase JWT and return the decoded payload.
    Tries ES256 (JWKS) first, falls back to HS256 (legacy secret).
    Returns None if invalid.
    """
    # Try ES256 via JWKS first
    jwks = _get_jwks_client()
    if jwks:
        try:
            signing_key = jwks.get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=['ES256'],
                audience='authenticated',
            )
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError as e:
            logger.warning("ES256 validation failed, trying HS256: %s", type(e).__name__)

    # Fallback: HS256 with legacy secret
    try:
        payload = jwt.decode(
            token,
            get_jwt_secret(),
            algorithms=['HS256'],
            audience='authenticated',
        )
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def is_public_route(path):
    """Check if a route is public (no auth required)."""
    if path in PUBLIC_EXACT:
        return True
    for prefix in PUBLIC_PREFIXES:
        if path.startswith(prefix):
            return True
    return False


def init_auth(app):
    """
    Register the before_request auth hook on the Flask app.
    Call this BEFORE registering blueprints.
    """
    @app.before_request
    def set_request_id():
        """Generate a unique request ID for correlation across logs."""
        import uuid
        g.request_id = str(uuid.uuid4())[:8]

    @app.before_request
    def check_auth():
        # Skip auth on localhost ONLY if no JWT is present.
        # Behind a reverse proxy (Railway/gunicorn), request.host may resolve
        # to localhost even on production, so always prefer JWT when available.
        host = request.host.split(':')[0]
        has_bearer = request.headers.get('Authorization', '').startswith('Bearer ')
        is_dev = os.getenv('FLASK_ENV', '').lower() in ('development', 'dev')
        if is_dev and host in ('localhost', '127.0.0.1') and not has_bearer:
            # Allow test harness to simulate multiple teachers via header
            g.user_id = request.headers.get('X-Test-Teacher-Id',
                                            os.getenv('DEV_USER_ID', 'local-dev'))
            g.user_email = os.getenv('DEV_EMAIL', 'dev@localhost')
            # Issue #353: flag the request as a dev-shim teacher so
            # downstream gates (e.g. `approval_status`) can bypass
            # Supabase user-lookup paths that 500 in CI for any non-
            # 'local-dev' teacher_id. Was previously detectable only
            # via the literal `g.user_id == 'local-dev'` check.
            g.is_dev_shim = True
            return None

        # Clever SSO session (cookie-based, set during OAuth callback)
        clever_user = session.get('clever_user') if hasattr(session, 'get') else None
        if clever_user and not has_bearer:
            g.user_id = resolve_clever_user_id(clever_user['clever_id'])
            g.user_email = clever_user.get('email', '')
            g.auth_source = 'clever'
            g.district_id = clever_user.get('district', '')
            return None

        # ClassLink SSO session — identity GUID was formed (tenant-scoped) at
        # the OAuth callback and stored as `user_id`; read it verbatim.
        classlink_user = session.get('classlink_user') if hasattr(session, 'get') else None
        if classlink_user and not has_bearer:
            g.user_id = classlink_user.get('user_id', '')
            g.teacher_id = g.user_id
            g.user_email = classlink_user.get('email', '')
            g.auth_source = 'classlink'
            g.district_id = classlink_user.get('tenant_id', '')
            return None

        # Skip non-API routes (static files, index.html, etc.)
        if not request.path.startswith('/api/'):
            return None

        # Skip public routes
        if is_public_route(request.path):
            return None

        # Extract token from Authorization header
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Authentication required'}), 401

        token = auth_header[7:]  # Strip 'Bearer '
        payload = validate_token(token)
        if payload is None:
            return jsonify({'error': 'Invalid or expired token'}), 401

        # Attach user info to Flask's g object for use in route handlers
        g.user_id = payload.get('sub')
        g.user_email = payload.get('email', '')
        # Phase 4.5: raw JWT stashed here so get_request_supabase()
        # (in backend/supabase_client_scoped.py) can mint a per-user
        # Supabase client. This attr is ONLY set on the validated
        # Bearer-JWT path — never on Clever/ClassLink/student/dev.
        g.supabase_jwt = token

        # Approval gate — skip for the approval-status endpoint itself
        if request.path != '/api/auth/approval-status':
            # Clever/ClassLink users are district-approved by definition — skip gate
            if getattr(g, 'auth_source', None) in ('clever', 'classlink'):
                return None

            user_meta = payload.get('user_metadata', {})
            if not user_meta.get('approved'):
                # JWT metadata may be stale — check Supabase admin API as fallback
                try:
                    sb = _get_supabase()
                    if sb:
                        res = sb.auth.admin.get_user_by_id(g.user_id)
                        fresh_meta = (res.user.user_metadata or {}) if res and res.user else {}
                        if fresh_meta.get('approved'):
                            # User is actually approved, JWT is just stale
                            logger.info("User %s approved via admin API fallback (stale JWT)", g.user_email)
                            return None  # Allow request
                except Exception as e:
                    logger.warning("Admin API approval fallback failed: %s", str(e))
                    sentry_sdk.capture_exception(e)

                return jsonify({
                    'error': 'Account pending approval',
                    'code': 'NOT_APPROVED',
                }), 403
