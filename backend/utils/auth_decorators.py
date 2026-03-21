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
