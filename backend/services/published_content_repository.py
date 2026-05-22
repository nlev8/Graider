"""Published-content repository abstraction for the dual publish path.

Parallel to backend.services.submission_repository. The published-content
tables (published_assessments for the join-code path, published_content for
the class-based path) are read by the route entry points. This module
abstracts that read behind a uniform interface so the routes do not need
to know which table is queried or by which column.

Reuses the SubmissionPathType enum and the path-discriminator semantics from
submission_repository (the enum value equals the legacy submissions table
string so the Celery boundary stays unchanged). This module never imports
backend.app and never imports a route module.

``PublishedContentRepository`` is a base class for path-specific adapters.
Subclasses must set ``table_name`` and ``lookup_column`` as class attributes.
Direct instantiation of the base class will raise ``NotImplementedError`` at
runtime (matching the sibling ``SubmissionRepository`` pattern).
"""
import logging
from typing import Optional

import sentry_sdk

from backend.services.submission_repository import SubmissionPathType, _UNSET

logger = logging.getLogger(__name__)


class PublishedContentRepository:
    """Base class for published-content row I/O; one subclass per publish path.

    Subclasses must set ``table_name`` and ``lookup_column`` as class
    attributes. The base class raises ``NotImplementedError`` at runtime if
    those attributes are left empty, mirroring the sibling
    ``SubmissionRepository`` pattern.
    """

    table_name: str = ""
    lookup_column: str = ""

    def __init__(self, sb):
        self._sb = sb

    def fetch_by_lookup_key(self, key) -> Optional[dict]:
        """Return the published-content row dict, or None if absent."""
        if not self.table_name or not self.lookup_column:
            raise NotImplementedError(
                "PublishedContentRepository subclass must set table_name and lookup_column"
            )
        if not self._sb or not key:
            return None
        try:
            result = self._sb.table(self.table_name).select("*").eq(
                self.lookup_column, key
            ).execute()
        except Exception as e:
            logger.error("fetch_by_lookup_key failed for table %s: %s", self.table_name, e)
            sentry_sdk.capture_exception(e)
            return None
        rows = result.data if result else None
        if not rows:
            return None
        return rows[0] if isinstance(rows, list) else rows


class JoinCodePublishedRepository(PublishedContentRepository):
    table_name = "published_assessments"
    lookup_column = "join_code"


class ClassPublishedRepository(PublishedContentRepository):
    table_name = "published_content"
    lookup_column = "id"


def published_content_repository_for(path_type, sb=_UNSET) -> PublishedContentRepository:
    """Reconstruct the adapter from the path discriminator. When sb is omitted,
    resolve it from backend.providers (the DI seam). Accepts the
    SubmissionPathType enum or the legacy table-name string (transitional)."""
    if sb is _UNSET:
        from backend.providers import get_supabase_provider
        sb = get_supabase_provider()
    if isinstance(path_type, str):
        path_type = SubmissionPathType(path_type)
    if path_type is SubmissionPathType.JOIN_CODE:
        return JoinCodePublishedRepository(sb)
    if path_type is SubmissionPathType.CLASS:
        return ClassPublishedRepository(sb)
    raise ValueError(f"unknown submission path type: {path_type!r}")
