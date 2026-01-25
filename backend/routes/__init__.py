"""
Graider API Routes
==================

All API route blueprints for the Graider application.

Usage:
    from backend.routes import register_routes
    register_routes(app)
"""
from .settings_routes import settings_bp
from .assignment_routes import assignment_bp
from .analytics_routes import analytics_bp
from .planner_routes import planner_bp
from .document_routes import document_bp
from .email_routes import email_bp
from .grading_routes import grading_bp, init_grading_routes


def register_routes(app, grading_state=None, run_grading_fn=None, reset_fn=None):
    """Register all route blueprints with the Flask app."""

    # Initialize grading routes with state references if provided
    if grading_state is not None:
        init_grading_routes(grading_state, run_grading_fn, reset_fn)

    # Register all blueprints
    app.register_blueprint(settings_bp)
    app.register_blueprint(assignment_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(planner_bp)
    app.register_blueprint(document_bp)
    app.register_blueprint(email_bp)
    app.register_blueprint(grading_bp)


__all__ = [
    'register_routes',
    'settings_bp',
    'assignment_bp',
    'analytics_bp',
    'planner_bp',
    'document_bp',
    'email_bp',
    'grading_bp',
    'init_grading_routes'
]
