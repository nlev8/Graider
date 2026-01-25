"""
Graider Services
================

Business logic services for the Graider application.

Services:
- grading_service: AI-powered assignment grading
- email_service: Email sending functionality
- watcher_service: File system watching for auto-grade
"""

# Services are imported directly when needed to avoid circular imports
# Example: from backend.services.grading_service import grade_assignment

__all__ = [
    'grading_service',
    'email_service',
    'watcher_service'
]
