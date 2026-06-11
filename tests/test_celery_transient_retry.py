"""Celery transient-retry classification contract tests.

Closes audit MAJOR #7 (Codex full-codebase audit 2026-05-06): transient
retry was documented as inactive because grade_portal_submission_sync
swallowed exceptions before Celery's classifier could see them.

Pins:
- The sync function re-raises TransientError when called with
  raise_transient=True AND the exception is classified retryable
  (via backend.retry.is_retryable_error).
- The sync function still swallows-and-marks-failed when called with
  raise_transient=False (default — preserves thread-path behavior).
- Permanent exceptions (KeyError, etc.) are never re-raised regardless
  of raise_transient.
- The Celery task decorator includes autoretry_for=(TransientError,)
  with sane backoff parameters.
"""
import pytest
from unittest.mock import MagicMock, patch


# Mirror the autouse fixture from tests/test_grading_tasks.py — Celery refuses
# to import without CELERY_BROKER_URL set, and module reload is required so the
# decorator config is re-evaluated.
@pytest.fixture(autouse=True)
def _celery_env(monkeypatch):
    monkeypatch.setenv("CELERY_BROKER_URL", "redis://localhost:6379/15")
    import sys
    sys.modules.pop("backend.celery_app", None)
    sys.modules.pop("backend.tasks", None)
    sys.modules.pop("backend.tasks.grading_tasks", None)


# ──────────────────────────────────────────────────────────────────
# Direct re-raise contract on grade_portal_submission_sync
# ──────────────────────────────────────────────────────────────────


class TestSyncReRaiseOnTransient:
    """When called with raise_transient=True (Celery path), the blanket
    catch must classify retryable exceptions and re-raise as TransientError."""

    def _invoke_sync_with_exception(self, exc, raise_transient):
        """Helper: invoke grade_portal_submission_sync with the inner pipeline
        forced to raise `exc`. Returns (result, raised_exc) tuple.

        Injection point: patch `hashlib.sha256` in the portal_grading module
        namespace. It's used on the FIRST line inside the function's outer
        try block (the FERPA-hashed "Portal grading started" log). Patching
        it raises before any real pipeline call, so we exercise the blanket
        catch without booting Supabase or the AI pipeline."""
        from backend.services import portal_grading

        # task_id=None disables the dedup branch (which is OUTSIDE the try).
        with patch.object(portal_grading.hashlib, "sha256",
                          side_effect=exc), \
             patch("backend.supabase_client.get_supabase", return_value=None):
            try:
                portal_grading.grade_portal_submission_sync(
                    submission_id="test-sub-1",
                    assessment={"title": "t", "questions": []},
                    answers={},
                    student_info={"student_name": "x"},
                    teacher_config={},
                    teacher_id="t1",
                    raise_transient=raise_transient,
                )
                return ("returned", None)
            except Exception as raised:  # noqa: BLE001  # broad catch: returns fallback
                return ("raised", raised)

    def test_celery_path_reraises_transient_as_TransientError(self):
        from backend.tasks.grading_tasks import TransientError

        # ConnectionError is classified as transient by backend.retry.is_retryable_error.
        result, raised = self._invoke_sync_with_exception(
            ConnectionError("network blip"),
            raise_transient=True,
        )
        assert result == "raised"
        assert isinstance(raised, TransientError), (
            f"Expected TransientError, got {type(raised).__name__}"
        )

    def test_celery_path_reraises_timeout_as_TransientError(self):
        from backend.tasks.grading_tasks import TransientError

        # TimeoutError is also classified transient.
        result, raised = self._invoke_sync_with_exception(
            TimeoutError("request timed out"),
            raise_transient=True,
        )
        assert result == "raised"
        assert isinstance(raised, TransientError)

    def test_celery_path_reraises_keyword_match_as_TransientError(self):
        """is_retryable_error scans the exception string for transient
        keywords (e.g., 'connection reset')."""
        from backend.tasks.grading_tasks import TransientError

        # Generic Exception with retryable-keyword string: "connection reset"
        result, raised = self._invoke_sync_with_exception(
            Exception("connection reset by peer"),
            raise_transient=True,
        )
        assert result == "raised"
        assert isinstance(raised, TransientError)

    def test_celery_path_swallows_permanent_errors(self):
        """KeyError / ValueError / TypeError are programming errors, not
        transient. Even with raise_transient=True, the blanket catch
        must NOT re-raise these."""
        # KeyError → swallowed by existing flow → returns normally.
        result, raised = self._invoke_sync_with_exception(
            KeyError("missing config field"),
            raise_transient=True,
        )
        assert result == "returned", (
            f"Permanent KeyError must be swallowed (existing flow), "
            f"not re-raised. Got: result={result}, raised={raised!r}"
        )

    def test_thread_path_swallows_transient_errors(self):
        """raise_transient=False (default; thread-path callers) must
        preserve the existing swallow-and-mark-failed flow EVEN for
        transient exceptions. Only the Celery path opts into retry."""
        # ConnectionError IS classified transient — but raise_transient=False
        # means the sync function never re-raises.
        result, raised = self._invoke_sync_with_exception(
            ConnectionError("network blip"),
            raise_transient=False,
        )
        assert result == "returned", (
            "Thread path (raise_transient=False) must swallow transient "
            "errors per existing contract, not re-raise"
        )


# ──────────────────────────────────────────────────────────────────
# Celery task decorator config
# ──────────────────────────────────────────────────────────────────


class TestCeleryTaskAutoretryConfig:
    """The @celery_app.task decorator on grade_portal_submission must
    include autoretry_for=(TransientError,) plus sane backoff config."""

    def test_decorator_has_autoretry_for_TransientError(self):
        from backend.tasks.grading_tasks import grade_portal_submission, TransientError

        # Celery exposes the decorator config as task attributes.
        assert TransientError in grade_portal_submission.autoretry_for, (
            f"autoretry_for must include TransientError; got "
            f"{grade_portal_submission.autoretry_for!r}"
        )

    def test_decorator_has_retry_backoff_capped(self):
        from backend.tasks.grading_tasks import grade_portal_submission

        # retry_backoff=True → exponential. retry_backoff_max=600 → 10 min cap.
        assert grade_portal_submission.retry_backoff is True
        assert grade_portal_submission.retry_backoff_max == 600
        assert grade_portal_submission.retry_jitter is True

    def test_decorator_has_max_retries_set(self):
        from backend.tasks.grading_tasks import grade_portal_submission

        # 3 retries = 4 total attempts. Reasonable for transient AI failures
        # without burning hours on a hopeless retry loop.
        assert grade_portal_submission.max_retries == 3

    def test_decorator_preserves_durability_settings(self):
        """Round-7 must NOT regress the durability / time-limit posture."""
        from backend.tasks.grading_tasks import grade_portal_submission

        assert grade_portal_submission.acks_late is True, "acks_late must remain True"
        # time_limit / soft_time_limit are stored on .time_limit / .soft_time_limit
        assert grade_portal_submission.time_limit == 900
        assert grade_portal_submission.soft_time_limit == 840


# ──────────────────────────────────────────────────────────────────
# Body wires raise_transient=True
# ──────────────────────────────────────────────────────────────────


class TestCeleryBodyOptsIntoTransientReraise:
    """Static-source pin: the Celery task body must call
    grade_portal_submission_sync with raise_transient=True so the
    blanket catch's transient-classifier branch fires."""

    def test_body_passes_raise_transient_true(self):
        from pathlib import Path
        src = Path(__file__).resolve().parent.parent / "backend/tasks/grading_tasks.py"
        text = src.read_text()
        assert "raise_transient=True" in text, (
            "grading_tasks.py must call grade_portal_submission_sync with "
            "raise_transient=True so transient errors bubble to Celery"
        )


class TestRetryClassifierCoverage:
    """Round-2 Codex MAJOR fold: openai/anthropic APIConnectionError don't
    subclass builtin ConnectionError, stringify as 'Connection error.', and
    don't expose .status_code. The classifier needs class-name + keyword
    coverage."""

    def test_class_name_match_for_openai_apiconnectionerror(self):
        """Synthetic class with the openai SDK class name should classify
        as transient. Mirrors openai.APIConnectionError's signature: no
        ConnectionError ancestry, no .status_code."""
        from backend.retry import is_retryable_error

        class APIConnectionError(Exception):
            pass

        assert is_retryable_error(APIConnectionError("Connection error.")) is True

    def test_class_name_match_for_anthropic(self):
        from backend.retry import is_retryable_error

        # anthropic.APIConnectionError is the same class name; same dispatch.
        class APIConnectionError(Exception):
            pass

        assert is_retryable_error(APIConnectionError("network blip")) is True

    def test_class_name_match_for_apitimeout(self):
        from backend.retry import is_retryable_error

        class APITimeoutError(Exception):
            pass

        assert is_retryable_error(APITimeoutError("request timed out")) is True

    def test_class_name_match_for_rate_limit(self):
        from backend.retry import is_retryable_error

        class RateLimitError(Exception):
            pass

        assert is_retryable_error(RateLimitError("429 too many requests")) is True

    def test_class_name_match_for_google_serviceunavailable(self):
        from backend.retry import is_retryable_error

        class ServiceUnavailable(Exception):
            pass

        assert is_retryable_error(ServiceUnavailable("backend overloaded")) is True

    def test_keyword_connection_error_now_matches(self):
        """openai.APIConnectionError stringifies as 'Connection error.'
        Round-2 added 'connection error' to the keyword list as fallback
        when the class name is unfamiliar."""
        from backend.retry import is_retryable_error

        # NOT one of the known class names AND short string — only the
        # 'connection error' keyword can save it.
        class SomeNewSDKError(Exception):
            pass

        assert is_retryable_error(SomeNewSDKError("Connection error.")) is True

    def test_permanent_classes_still_false(self):
        """ValueError, TypeError, KeyError must remain non-retryable."""
        from backend.retry import is_retryable_error

        assert is_retryable_error(ValueError("bad input")) is False
        assert is_retryable_error(TypeError("wrong type")) is False
        assert is_retryable_error(KeyError("missing field")) is False


class TestContextFetchPropagatesTransient:
    """Round-2 Codex MAJOR fold: fetch_submission_full_context previously
    returned None on ALL exceptions (incl. supabase 5xx), so the Celery
    body never saw retryable failures during context fetch. Now it
    re-raises retryable exceptions; permanent ones still return None."""

    def test_fetch_helper_reraises_transient(self):
        """ConnectionError during sb.table().select() bubbles up."""
        from backend.services import portal_grading

        mock_sb = MagicMock()
        mock_sb.table.return_value.select.return_value.eq.return_value.single.return_value.execute.side_effect = ConnectionError("network blip")

        with patch("backend.supabase_client.get_supabase", return_value=mock_sb):
            with pytest.raises(ConnectionError):
                portal_grading.fetch_submission_full_context(
                    "student_submissions", "test-sub", "teacher-1"
                )

    def test_fetch_helper_returns_none_on_permanent(self):
        """KeyError (programming error) → returns None per existing flow."""
        from backend.services import portal_grading

        mock_sb = MagicMock()
        mock_sb.table.return_value.select.return_value.eq.return_value.single.return_value.execute.side_effect = KeyError("missing column")

        with patch("backend.supabase_client.get_supabase", return_value=mock_sb):
            result = portal_grading.fetch_submission_full_context(
                "student_submissions", "test-sub", "teacher-1"
            )
            assert result is None

    def test_celery_body_converts_transient_fetch_error_to_TransientError(self):
        """Static-source pin: grading_tasks.py wraps the fetch_submission_full_context
        call with try/except and converts retryable exceptions into TransientError
        so Celery's autoretry catches them."""
        from pathlib import Path

        src = Path(__file__).resolve().parent.parent / "backend/tasks/grading_tasks.py"
        text = src.read_text()
        # The wrapping pattern must exist
        assert "ctx = fetch_submission_full_context(" in text
        # And there must be a TransientError raise tied to the fetch path
        assert "raise TransientError(str(e)" in text, (
            "grading_tasks.py must convert retryable fetch-context errors "
            "into TransientError so Celery's autoretry kicks in"
        )

    def test_published_assessments_fetch_propagates_transient(self):
        """Round-2 round-2 Codex MAJOR fold: transient ConnectionError during
        published_assessments fetch (the SECOND try/catch inside
        fetch_submission_full_context) must propagate, not silently leave
        ctx['assessment']=None."""
        from backend.services import portal_grading

        submission_row = MagicMock()
        submission_row.data = {
            'id': 'sub-1',
            'assessment_id': 'pa-1',
            'student_name': 'S',
            'email': 's@x.com',
        }

        def table_side_effect(name):
            chain = MagicMock(name=f'table({name})')
            if name == 'published_assessments':
                # Transient failure on the second fetch
                chain.select.return_value.eq.return_value.single.return_value.execute.side_effect = (
                    ConnectionError("assessment fetch network blip")
                )
            else:
                chain.select.return_value.eq.return_value.single.return_value.execute.return_value = submission_row
            return chain

        mock_sb = MagicMock()
        mock_sb.table.side_effect = table_side_effect

        with patch("backend.supabase_client.get_supabase", return_value=mock_sb), \
             patch("backend.services.grading_service.load_teacher_config", return_value={}):
            with pytest.raises(ConnectionError):
                portal_grading.fetch_submission_full_context(
                    "student_submissions", "sub-1", "teacher-1"
                )

    def test_published_assessments_fetch_returns_partial_on_permanent_error(self):
        """Permanent (non-retryable) errors during published_assessments fetch
        should NOT propagate — fall through to inline `data.get('assessment')`
        path so existing flow preserved."""
        from backend.services import portal_grading

        submission_row = MagicMock()
        # Submission has inline `assessment` field as fallback path
        submission_row.data = {
            'id': 'sub-1',
            'assessment_id': 'pa-1',
            'assessment': {'title': 'inline-fallback', 'questions': []},
            'student_name': 'S',
            'email': 's@x.com',
        }

        def table_side_effect(name):
            chain = MagicMock(name=f'table({name})')
            if name == 'published_assessments':
                chain.select.return_value.eq.return_value.single.return_value.execute.side_effect = (
                    KeyError("schema mismatch")  # permanent
                )
            else:
                chain.select.return_value.eq.return_value.single.return_value.execute.return_value = submission_row
            return chain

        mock_sb = MagicMock()
        mock_sb.table.side_effect = table_side_effect

        with patch("backend.supabase_client.get_supabase", return_value=mock_sb), \
             patch("backend.services.grading_service.load_teacher_config", return_value={}):
            result = portal_grading.fetch_submission_full_context(
                "student_submissions", "sub-1", "teacher-1"
            )
            # Should return ctx with the inline assessment (fall-through path)
            assert result is not None
            assert result["assessment"]["title"] == "inline-fallback"


class TestClassifierApiStatusErrorFalsePositive:
    """Round-2 round-2 Codex MAJOR fold: APIStatusError was added to the
    class-name allowlist in error, causing 4xx (400/401) to retry. Removed
    so it falls through to status-code classification."""

    def test_apistatuserror_with_4xx_does_not_retry(self):
        from backend.retry import is_retryable_error

        class APIStatusError(Exception):
            def __init__(self, msg, status_code):
                super().__init__(msg)
                self.status_code = status_code

        # 400 / 401 / 403 / 404 must NOT retry
        for status in (400, 401, 403, 404):
            err = APIStatusError(f"client error {status}", status)
            assert is_retryable_error(err) is False, (
                f"APIStatusError with status={status} must NOT retry"
            )

    def test_apistatuserror_with_5xx_does_retry(self):
        from backend.retry import is_retryable_error

        class APIStatusError(Exception):
            def __init__(self, msg, status_code):
                super().__init__(msg)
                self.status_code = status_code

        # 500 / 502 / 503 / 504 / 408 / 429 / 529 → retry via _get_status_code
        for status in (408, 429, 500, 502, 503, 504, 529):
            err = APIStatusError(f"server error {status}", status)
            assert is_retryable_error(err) is True, (
                f"APIStatusError with status={status} must retry"
            )
