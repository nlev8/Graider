"""
Supabase JWT Authentication for Graider.
Validates Bearer tokens on all /api/ routes except public endpoints.
"""
import os
import jwt
from flask import request, jsonify, g


# Routes that don't require authentication
PUBLIC_PREFIXES = [
    '/api/student/',       # Student portal (public, students don't have accounts)
]

PUBLIC_EXACT = [
    '/api/status',         # Grading status polling (used before auth check completes)
]


def get_jwt_secret():
    """Get the Supabase JWT secret from environment."""
    secret = os.getenv('SUPABASE_JWT_SECRET')
    if not secret:
        raise RuntimeError('SUPABASE_JWT_SECRET not configured')
    return secret


def validate_token(token):
    """
    Validate a Supabase JWT and return the decoded payload.
    Returns None if invalid.
    """
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
