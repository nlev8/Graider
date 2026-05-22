"""Unit tests for backend.providers (the repository/supabase DI seam)."""
from unittest.mock import patch

from tests.test_submission_repository import FakeSupabase


def test_get_supabase_provider_returns_real_client_when_no_override():
    fake = FakeSupabase()
    with patch("backend.supabase_client.get_supabase", return_value=fake):
        from backend.providers import get_supabase_provider
        assert get_supabase_provider() is fake


def test_override_supabase_returns_fake_inside_block_real_after():
    real = FakeSupabase()
    fake = FakeSupabase()
    from backend.providers import get_supabase_provider, override_supabase
    with patch("backend.supabase_client.get_supabase", return_value=real):
        assert get_supabase_provider() is real
        with override_supabase(fake):
            assert get_supabase_provider() is fake
        assert get_supabase_provider() is real


def test_override_resets_even_on_exception():
    real = FakeSupabase()
    fake = FakeSupabase()
    from backend.providers import get_supabase_provider, override_supabase
    with patch("backend.supabase_client.get_supabase", return_value=real):
        try:
            with override_supabase(fake):
                assert get_supabase_provider() is fake
                raise RuntimeError("boom")
        except RuntimeError:
            pass
        assert get_supabase_provider() is real


def test_get_submission_repository_returns_joincode_adapter():
    from backend.services.submission_repository import (
        SubmissionPathType, JoinCodeSubmissionRepository,
    )
    from backend.providers import get_submission_repository, override_supabase
    fake = FakeSupabase()
    with override_supabase(fake):
        repo = get_submission_repository(SubmissionPathType.JOIN_CODE)
    assert isinstance(repo, JoinCodeSubmissionRepository)
    assert repo._sb is fake


def test_get_submission_repository_returns_class_adapter():
    from backend.services.submission_repository import (
        SubmissionPathType, ClassSubmissionRepository,
    )
    from backend.providers import get_submission_repository, override_supabase
    fake = FakeSupabase()
    with override_supabase(fake):
        repo = get_submission_repository(SubmissionPathType.CLASS)
    assert isinstance(repo, ClassSubmissionRepository)
    assert repo._sb is fake


def test_get_published_content_repository_returns_correct_adapters():
    from backend.services.submission_repository import SubmissionPathType
    from backend.services.published_content_repository import (
        JoinCodePublishedRepository, ClassPublishedRepository,
    )
    from backend.providers import get_published_content_repository, override_supabase
    fake = FakeSupabase()
    with override_supabase(fake):
        jc = get_published_content_repository(SubmissionPathType.JOIN_CODE)
        cl = get_published_content_repository(SubmissionPathType.CLASS)
    assert isinstance(jc, JoinCodePublishedRepository)
    assert isinstance(cl, ClassPublishedRepository)


def test_override_isolated_across_threads():
    """A fake set in one thread's context must not leak into another thread.
    contextvars default-isolates per-thread, so the child thread sees the
    real client, not the parent's override."""
    import threading
    from backend.providers import get_supabase_provider, override_supabase

    real = FakeSupabase()
    parent_fake = FakeSupabase()
    seen = {}

    def child():
        # New thread → fresh context → no override visible.
        seen["child"] = get_supabase_provider()

    with patch("backend.supabase_client.get_supabase", return_value=real):
        with override_supabase(parent_fake):
            assert get_supabase_provider() is parent_fake
            t = threading.Thread(target=child)
            t.start()
            t.join()

    assert seen["child"] is real  # child did NOT see parent's override
