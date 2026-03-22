"""Shared authentication decorators for route handlers."""
import functools
from flask import g, jsonify


def require_teacher(f):
    """Decorator that enforces teacher authentication.
    Sets g.teacher_id for use in the wrapped route handler.
    Returns 401 if no authenticated teacher session exists."""
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        teacher_id = getattr(g, 'user_id', None)
        if not teacher_id:
            return jsonify({"error": "Authentication required"}), 401
        g.teacher_id = teacher_id
        return f(*args, **kwargs)
    return wrapper


def require_clever_session(f):
    """Decorator that enforces Clever session authentication.
    Used for Clever-specific teacher endpoints that use OAuth session
    instead of JWT. Returns 401 if no active Clever session exists."""
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        from flask import session
        clever_user = session.get("clever_user")
        if not clever_user:
            return jsonify({"error": "Clever session required"}), 401
        g.clever_user = clever_user
        g.teacher_id = getattr(g, 'user_id', clever_user.get('clever_id', ''))
        return f(*args, **kwargs)
    return wrapper
