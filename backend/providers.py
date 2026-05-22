"""Dependency provider for the repository/supabase seam.

Single resolution point for the supabase client + repository adapters at
the seam abstracted in Tier 2 Slices 4-5. Lets tests swap the database
for a fake at one switch (override_supabase) instead of monkeypatching
get_supabase() per-module.

Wraps, does not replace: backend.supabase_client.get_supabase() stays the
real accessor; this module calls it. Context-independent (plain module
functions) so it works in both Flask-request and Celery-task contexts.
The override is contextvars-backed so it cannot leak across tests or
worker threads.

See docs/superpowers/specs/2026-05-22-di-provider-design.md.
"""
import contextlib
import contextvars
from typing import Any

_supabase_override: contextvars.ContextVar = contextvars.ContextVar(
    "supabase_override", default=None
)


def get_supabase_provider() -> Any:
    """Resolve the supabase client: the test override if one is set in the
    current context, else the real client from supabase_client."""
    override = _supabase_override.get()
    if override is not None:
        return override
    from backend.supabase_client import get_supabase
    return get_supabase()


def get_submission_repository(path_type):
    """Build the SubmissionRepository adapter for path_type using the
    provider-resolved supabase client."""
    from backend.services.submission_repository import repository_for
    return repository_for(path_type, get_supabase_provider())


def get_published_content_repository(path_type):
    """Build the PublishedContentRepository adapter for path_type using the
    provider-resolved supabase client."""
    from backend.services.published_content_repository import (
        published_content_repository_for,
    )
    return published_content_repository_for(path_type, get_supabase_provider())


@contextlib.contextmanager
def override_supabase(fake):
    """Test-only: route get_supabase_provider() to `fake` for the duration
    of the with-block. contextvars-scoped so it cannot leak across tests or
    worker threads; resets on exit (including on exception)."""
    token = _supabase_override.set(fake)
    try:
        yield
    finally:
        _supabase_override.reset(token)
