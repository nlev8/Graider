"""Unit tests for backend.services.published_content_repository (PR1, additive).

Parallel to backend.services.submission_repository. Reuses SubmissionPathType
as the path discriminator. Nothing in production imports this module in PR1.
"""
from tests.test_submission_repository import FakeSupabase


def test_module_imports():
    from backend.services.published_content_repository import (
        PublishedContentRepository,
        JoinCodePublishedRepository,
        ClassPublishedRepository,
        published_content_repository_for,
    )
    assert PublishedContentRepository.__name__ == "PublishedContentRepository"


def test_factory_returns_correct_adapter():
    from backend.services.submission_repository import SubmissionPathType
    from backend.services.published_content_repository import (
        JoinCodePublishedRepository,
        ClassPublishedRepository,
        published_content_repository_for,
    )
    sb = FakeSupabase()
    assert isinstance(
        published_content_repository_for(SubmissionPathType.JOIN_CODE, sb),
        JoinCodePublishedRepository,
    )
    assert isinstance(
        published_content_repository_for(SubmissionPathType.CLASS, sb),
        ClassPublishedRepository,
    )


def test_factory_accepts_legacy_string():
    from backend.services.published_content_repository import (
        JoinCodePublishedRepository,
        ClassPublishedRepository,
        published_content_repository_for,
    )
    sb = FakeSupabase()
    assert isinstance(
        published_content_repository_for("submissions", sb),
        JoinCodePublishedRepository,
    )
    assert isinstance(
        published_content_repository_for("student_submissions", sb),
        ClassPublishedRepository,
    )


def test_joincode_fetch_by_lookup_key_hit():
    sb = FakeSupabase()
    sb.table("published_assessments")  # materialize FakeTable
    sb.tables["published_assessments"].row = {
        "id": "pa-1", "join_code": "ABCD12", "assessment": {"title": "T"}
    }
    from backend.services.published_content_repository import JoinCodePublishedRepository
    repo = JoinCodePublishedRepository(sb)
    row = repo.fetch_by_lookup_key("ABCD12")
    assert row is not None
    assert row["id"] == "pa-1"


def test_joincode_fetch_by_lookup_key_miss():
    sb = FakeSupabase()
    sb.table("published_assessments")  # materialize FakeTable, row stays None
    from backend.services.published_content_repository import JoinCodePublishedRepository
    repo = JoinCodePublishedRepository(sb)
    assert repo.fetch_by_lookup_key("ABCD12") is None


def test_class_fetch_by_lookup_key_hit():
    sb = FakeSupabase()
    sb.table("published_content")  # materialize FakeTable
    sb.tables["published_content"].row = {
        "id": "content-1", "content": {}, "due_date": "2026-06-01"
    }
    from backend.services.published_content_repository import ClassPublishedRepository
    repo = ClassPublishedRepository(sb)
    row = repo.fetch_by_lookup_key("content-1")
    assert row is not None
    assert row["id"] == "content-1"


def test_class_fetch_by_lookup_key_miss():
    sb = FakeSupabase()
    sb.table("published_content")  # materialize FakeTable, row stays None
    from backend.services.published_content_repository import ClassPublishedRepository
    repo = ClassPublishedRepository(sb)
    assert repo.fetch_by_lookup_key("content-1") is None


def test_falsy_inputs_return_none():
    from backend.services.published_content_repository import JoinCodePublishedRepository
    repo = JoinCodePublishedRepository(FakeSupabase())
    assert repo.fetch_by_lookup_key(None) is None
    assert repo.fetch_by_lookup_key("") is None
    repo2 = JoinCodePublishedRepository(None)
    assert repo2.fetch_by_lookup_key("ABCD12") is None


def test_joincode_fetch_records_lookup_filter():
    """Filter-correctness assertion — proves the production query uses
    the right column. PR2 cannot silently swap the lookup_column."""
    sb = FakeSupabase()
    sb.table("published_assessments")  # materialize FakeTable
    sb.tables["published_assessments"].row = {"id": "pa-1", "join_code": "ABCD12"}
    from backend.services.published_content_repository import JoinCodePublishedRepository
    repo = JoinCodePublishedRepository(sb)
    repo.fetch_by_lookup_key("ABCD12")
    last_q = sb.tables["published_assessments"].last_query
    # _Query.eq(col, val) stores as _filters[col] = val (not a tuple key)
    assert last_q._filters["join_code"] == "ABCD12"


def test_class_fetch_records_lookup_filter():
    sb = FakeSupabase()
    sb.table("published_content")  # materialize FakeTable
    sb.tables["published_content"].row = {"id": "content-1"}
    from backend.services.published_content_repository import ClassPublishedRepository
    repo = ClassPublishedRepository(sb)
    repo.fetch_by_lookup_key("content-1")
    last_q = sb.tables["published_content"].last_query
    # _Query.eq(col, val) stores as _filters[col] = val (not a tuple key)
    assert last_q._filters["id"] == "content-1"


def test_joincode_fetch_captures_on_execute_exception(monkeypatch):
    """Mirror submission_repository.fetch() error contract."""
    captured = {}
    def fake_capture(exc):
        captured["exc"] = exc
    monkeypatch.setattr("backend.services.published_content_repository.sentry_sdk.capture_exception", fake_capture)
    sb = FakeSupabase()
    sb.table("published_assessments")  # materialize FakeTable
    sb.tables["published_assessments"].raise_on_execute = RuntimeError("boom")
    from backend.services.published_content_repository import JoinCodePublishedRepository
    repo = JoinCodePublishedRepository(sb)
    assert repo.fetch_by_lookup_key("ABCD12") is None
    assert isinstance(captured.get("exc"), RuntimeError)


def test_class_fetch_captures_on_execute_exception(monkeypatch):
    captured = {}
    def fake_capture(exc):
        captured["exc"] = exc
    monkeypatch.setattr("backend.services.published_content_repository.sentry_sdk.capture_exception", fake_capture)
    sb = FakeSupabase()
    sb.table("published_content")  # materialize FakeTable
    sb.tables["published_content"].raise_on_execute = RuntimeError("boom")
    from backend.services.published_content_repository import ClassPublishedRepository
    repo = ClassPublishedRepository(sb)
    assert repo.fetch_by_lookup_key("content-1") is None
    assert isinstance(captured.get("exc"), RuntimeError)


def test_factory_unknown_path_type_raises():
    """Defensive guard — the factory raises rather than silently returning None."""
    import pytest
    from backend.services.published_content_repository import published_content_repository_for
    sb = FakeSupabase()
    with pytest.raises(ValueError, match="bogus"):
        published_content_repository_for("bogus", sb)


def test_base_repository_raises_not_implemented():
    """Base class with empty table_name/lookup_column raises NotImplementedError."""
    import pytest
    from backend.services.published_content_repository import PublishedContentRepository
    base = PublishedContentRepository(FakeSupabase())
    with pytest.raises(NotImplementedError, match="table_name"):
        base.fetch_by_lookup_key("anything")
