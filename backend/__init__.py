"""
Graider Backend Package
=======================

Flask-based backend for the Graider AI-powered grading assistant.

Structure:
- routes/: API route blueprints
- services/: Business logic services
- data/: Static data files (standards, etc.)
- config.py: Configuration management
"""

from .config import config, Config

__version__ = "1.0.0"

__all__ = ['config', 'Config']
