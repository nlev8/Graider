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
from .assignment_player_routes import assignment_player_bp
from .student_portal_routes import student_portal_bp
from .lesson_routes import lesson_bp
from .assistant_routes import assistant_bp
from .stripe_routes import stripe_bp
from .auth_routes import auth_bp
from .automation_routes import automation_bp


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
    app.register_blueprint(assignment_player_bp)
    app.register_blueprint(student_portal_bp)
    app.register_blueprint(lesson_bp)
    app.register_blueprint(assistant_bp)
    app.register_blueprint(stripe_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(automation_bp)


__all__ = [
    'register_routes',
    'settings_bp',
    'assignment_bp',
    'analytics_bp',
    'planner_bp',
    'document_bp',
    'email_bp',
    'grading_bp',
    'init_grading_routes',
    'lesson_bp',
    'assistant_bp',
    'stripe_bp',
    'auth_bp',
    'automation_bp',
]
