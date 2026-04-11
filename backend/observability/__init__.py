"""Observability package for Graider.

Currently provides Sentry error tracking with PII scrubbing and the
@critical_path decorator for tagging high-risk entrypoints.

See docs/superpowers/specs/2026-04-11-observability-sentry-betterstack-design.md
and docs/observability.md for the full design and runbook.
"""

from backend.observability.sentry import init_sentry, critical_path

__all__ = ["init_sentry", "critical_path"]
