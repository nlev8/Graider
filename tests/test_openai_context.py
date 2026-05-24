"""Direct tests for the pure openai_context helper (Wave 6 Slice 2)."""


def test_build_openai_context_returns_user_id_and_none_client():
    from backend.services.openai_context import build_openai_context
    assert build_openai_context("teacher-123") == ("teacher-123", None)
    assert build_openai_context("local-dev") == ("local-dev", None)
