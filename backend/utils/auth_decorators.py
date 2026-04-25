"""Shared authentication decorators for route handlers."""
import functools
from typing import Any, Callable, TypeVar
from flask import g, jsonify
import sentry_sdk

# Type variable for the wrapped function's signature
F = TypeVar("F", bound=Callable[..., Any])


def require_teacher(f: F) -> F:
    """Decorator that enforces teacher authentication.
    Sets g.teacher_id for use in the wrapped route handler.
    Returns 401 if no authenticated teacher session exists."""
    @functools.wraps(f)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        teacher_id = getattr(g, 'user_id', None)
        if not teacher_id:
            return jsonify({"error": "Authentication required"}), 401
        g.teacher_id = teacher_id
        return f(*args, **kwargs)
    return wrapper  # type: ignore[return-value]


def require_clever_session(f: F) -> F:
    """Decorator that enforces Clever session authentication.
    Used for Clever-specific teacher endpoints that use OAuth session
    instead of JWT. Returns 401 if no active Clever session exists."""
    @functools.wraps(f)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        from flask import session
        clever_user = session.get("clever_user")
        if not clever_user:
            return jsonify({"error": "Clever session required"}), 401
        g.clever_user = clever_user
        g.teacher_id = getattr(g, 'user_id', clever_user.get('clever_id', ''))
        return f(*args, **kwargs)
    return wrapper  # type: ignore[return-value]


def require_admin(f: F) -> F:
    """Decorator that enforces school admin authentication.
    Checks admin_role:{user_id} exists in system storage.
    Sets g.admin_role for use in the wrapped route handler."""
    @functools.wraps(f)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        user_id = getattr(g, 'user_id', None)
        if not user_id:
            return jsonify({"error": "Authentication required"}), 401
        try:
            from backend.storage import load
            admin_role = load(f"admin_role:{user_id}", "system")  # type: ignore[no-untyped-call]
        except Exception as e:
            admin_role = None
            sentry_sdk.capture_exception(e)
        if not admin_role:
            return jsonify({"error": "Admin access required"}), 403
        g.teacher_id = user_id
        g.admin_role = admin_role
        return f(*args, **kwargs)
    return wrapper  # type: ignore[return-value]
