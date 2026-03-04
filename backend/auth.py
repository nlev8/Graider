"""
Supabase JWT Authentication for Graider.
Validates Bearer tokens on all /api/ routes except public endpoints.
Supports both ES256 (JWKS) and HS256 (legacy secret) verification.
"""
import os
import logging
import jwt
from jwt import PyJWKClient
from flask import request, jsonify, g

logger = logging.getLogger(__name__)

from backend.supabase_client import get_supabase as _get_supabase


# Routes that don't require authentication
PUBLIC_PREFIXES = [
    '/api/student/',       # Student portal (public, students don't have accounts)
]

PUBLIC_EXACT = [
    '/api/status',              # Grading status polling (used before auth check completes)
    '/api/stripe/webhook',      # Stripe webhook (verified via Stripe-Signature header)
    '/api/auth/notify-signup',  # Public signup notification (no JWT needed)
    '/api/auth/approve-user',   # One-click approval from admin email (HMAC-protected)
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
        except jwt.InvalidTokenError:
            pass  # Fall through to HS256

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
    def check_auth():
        # Skip auth entirely on localhost (development)
        host = request.host.split(':')[0]
        if host in ('localhost', '127.0.0.1'):
            g.user_id = 'local-dev'
            g.user_email = os.getenv('DEV_EMAIL', 'dev@localhost')
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

        # Approval gate — skip for the approval-status endpoint itself
        if request.path != '/api/auth/approval-status':
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

                return jsonify({
                    'error': 'Account pending approval',
                    'code': 'NOT_APPROVED',
                }), 403
