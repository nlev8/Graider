"""Sentry alerting contract test for assistant_routes._load_rubric.

Mirrors the pattern in tests/test_portal_grading_alerting.py and
tests/test_pipeline_safety_rails.py: pin the alerting contract for a
behavior-critical observability handler so future refactors can't
silently strip the sentry_sdk.capture_exception call.

The fix lives in PR chore/assistant-routes-observability — silent rubric
load failure was upgraded to logger.warning + sentry_sdk.capture_exception
because falling back to the default rubric is a user-visible behavior
change (assistant loses the teacher's custom rubric context).
"""
from unittest.mock import patch, mock_open


def test_rubric_load_failure_alerts_to_sentry():
    """If RUBRIC_FILE is malformed JSON, _load_rubric must:
    1. Return None (graceful fallback contract — assistant uses default).
    2. Call sentry_sdk.capture_exception so the corrupt config is visible.
    3. Log at WARNING level (production-visible breadcrumb).
    """
    from backend.routes import assistant_routes

    with patch("backend.routes.assistant_routes.os.path.exists", return_value=True), \
         patch("backend.routes.assistant_routes.open",
               mock_open(read_data="{not valid json"), create=True), \
         patch("backend.routes.assistant_routes.sentry_sdk") as mock_sentry, \
         patch.object(assistant_routes.logger, "warning") as mock_warn:
        result = assistant_routes._load_rubric()

        # Contract 1: graceful None on failure.
        assert result is None

        # Contract 2: Sentry sees the exception.
        mock_sentry.capture_exception.assert_called_once()

        # Contract 3: warning-level log fires (production-visible).
        assert mock_warn.call_count >= 1
        # Per Codex review of the original PR: log basename only, not the
        # absolute path. Verify the log call doesn't leak the full path.
        log_args = mock_warn.call_args_list[0]
        joined = " ".join(str(a) for a in log_args.args)
        # Should not contain full home directory path.
        assert "/Users/" not in joined and "/home/" not in joined, (
            "Rubric WARNING log must use basename, not absolute path "
            f"(found path-like string in: {joined!r})"
        )


def test_rubric_load_success_does_not_alert():
    """Happy path contract: when the rubric loads cleanly, neither
    sentry_sdk.capture_exception nor logger.warning should fire.
    Defends against accidental over-alerting (e.g. someone adding the
    capture_exception outside the except block).
    """
    from backend.routes import assistant_routes

    valid_rubric_json = '{"categories": [{"name": "Content"}]}'
    with patch("backend.routes.assistant_routes.os.path.exists", return_value=True), \
         patch("backend.routes.assistant_routes.open",
               mock_open(read_data=valid_rubric_json), create=True), \
         patch("backend.routes.assistant_routes.sentry_sdk") as mock_sentry, \
         patch.object(assistant_routes.logger, "warning") as mock_warn:
        result = assistant_routes._load_rubric()

        assert result == {"categories": [{"name": "Content"}]}
        mock_sentry.capture_exception.assert_not_called()
        mock_warn.assert_not_called()
