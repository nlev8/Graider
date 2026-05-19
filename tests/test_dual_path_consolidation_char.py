"""Characterization net for the dual publish-path consolidation (PR1).

Pins the CURRENT observable behavior of both submission paths BEFORE the
SubmissionRepository abstraction is wired in (it never is in PR1). Every
assertion here was probed against live code and pins exactly what was
observed (probe-then-pin, never assume).

Two paths are covered independently:
  - join-code  -> supabase_table='submissions'
  - class-based -> supabase_table='student_submissions'

Four seams are pinned for each, per the PR1 controller spec:
  1. claim   : _claim_submission_for_grading (UNCONDITIONAL 3-field write,
               returns None, no "already claimed" branch)
  2. fetch   : fetch_submission_full_context normalized context dict
               (the supabase_table=='submissions' branch + accommodations
               source difference live here)
  3. update  : _safe_update_submission table targeting, falsy-sid skip,
               sb=None Sentry capture
  4. failure : PortalGradingTask.on_failure extracts table from args[2]
               and writes {'status':'failed','error_message':str(exc)[:500]}

The repository adapter introduced in PR1 must reproduce these byte-identically;
PR2 rewires production to it. If any assertion here changes, the consolidation
is NOT behavior-preserving.
"""
import hashlib
from unittest.mock import MagicMock, patch

import pytest


# Both real submission tables. The Celery wire arg / on_failure args[2] uses
# these exact strings; the repository enum values must equal them.
JOIN_CODE_TABLE = "submissions"
CLASS_TABLE = "student_submissions"
BOTH_TABLES = [JOIN_CODE_TABLE, CLASS_TABLE]


# ---------------------------------------------------------------------------
# Seam 1: claim — _claim_submission_for_grading (UNCONDITIONAL write)
# ---------------------------------------------------------------------------
class TestClaimSeam:
    @pytest.mark.parametrize("table", BOTH_TABLES)
    def test_claim_writes_exact_three_fields_to_correct_table(self, table):
        """Fresh row: unconditional write of exactly status +
        grading_task_id + grading_started_at to the wired table.
        There is NO 'already claimed' branch in this function."""
        from backend.services.portal_grading import _claim_submission_for_grading

        sb = MagicMock()
        ret = _claim_submission_for_grading(sb, table, "sid-1", "task-99")

        # Returns None (no bool, no conditional) — pinned.
        assert ret is None

        assert sb.table.call_args.args[0] == table
        payload = sb.table.return_value.update.call_args.args[0]
        assert sorted(payload.keys()) == [
            "grading_started_at",
            "grading_task_id",
            "status",
        ]
        assert payload["status"] == "grading_in_progress"
        assert payload["grading_task_id"] == "task-99"
        # ISO-8601 UTC string with offset (datetime.now(timezone.utc).isoformat())
        assert isinstance(payload["grading_started_at"], str)
        assert payload["grading_started_at"].endswith("+00:00")
        # Targets the row by id.
        sb.table.return_value.update.return_value.eq.assert_called_once_with(
            "id", "sid-1"
        )

    @pytest.mark.parametrize("table", BOTH_TABLES)
    def test_claim_noop_when_sb_falsy(self, table):
        from backend.services.portal_grading import _claim_submission_for_grading

        assert _claim_submission_for_grading(None, table, "sid", "t") is None

    @pytest.mark.parametrize("table", BOTH_TABLES)
    def test_claim_noop_when_submission_id_falsy(self, table):
        from backend.services.portal_grading import _claim_submission_for_grading

        sb = MagicMock()
        assert _claim_submission_for_grading(sb, table, None, "t") is None
        assert _claim_submission_for_grading(sb, table, "", "t") is None
        assert sb.table.called is False


# ---------------------------------------------------------------------------
# Seam 2: fetch — fetch_submission_full_context normalized context dict
# ---------------------------------------------------------------------------
def _fake_sb(rows_by_table):
    """Build a fake supabase client whose .table(name)...execute() returns
    a MagicMock with .data set from rows_by_table[name]."""

    class _FT:
        def __init__(self, name):
            self.name = name

        def select(self, *a, **k):
            return self

        def eq(self, *a, **k):
            return self

        def single(self):
            return self

        def execute(self):
            resp = MagicMock()
            resp.data = rows_by_table.get(self.name)
            return resp

    class _FSB:
        def table(self, name):
            return _FT(name)

    return _FSB()


class TestFetchContextSeam:
    def test_join_code_normalized_context_is_exact(self):
        """Join-code path ('submissions'): student_id is forced to '' (the
        submissions table has no student_id column); accommodations come
        from published_assessments.settings.student_accommodations."""
        from backend.services.portal_grading import fetch_submission_full_context

        sub = {
            "id": "sub-1",
            "assessment_id": "a-1",
            "answers": {"q1": "ans"},
            "student_name": "Ana",
            "student_email": "ana@example.com",
        }
        pub = {
            "id": "a-1",
            "assessment": {"questions": [{"id": "q1"}]},
            "settings": {
                "student_accommodations": {"iep": True, "extended_time": 1.5}
            },
        }
        sb = _fake_sb({JOIN_CODE_TABLE: sub, "published_assessments": pub})

        with patch(
            "backend.supabase_client.get_supabase", return_value=sb
        ), patch(
            "backend.services.grading_service.load_teacher_config",
            return_value={"grade_level": "8"},
        ):
            ctx = fetch_submission_full_context(
                JOIN_CODE_TABLE, "sub-1", "teacher-1"
            )

        assert ctx == {
            "assessment": {"questions": [{"id": "q1"}]},
            "answers": {"q1": "ans"},
            "student_info": {
                "name": "Ana",
                "email": "ana@example.com",
                "student_name": "Ana",
                "student_email": "ana@example.com",
                "student_id": "",
            },
            "teacher_config": {"grade_level": "8"},
            "student_accommodations": {"iep": True, "extended_time": 1.5},
        }

    def test_class_based_normalized_context_is_exact(self):
        """Class-based path ('student_submissions'): student_id is taken
        from the row; accommodations fall through to data['accommodations']
        when published settings has none."""
        from backend.services.portal_grading import fetch_submission_full_context

        sub = {
            "id": "sub-2",
            "assessment_id": "a-2",
            "answers": {"0-1": "work"},
            "student_name": "Bob",
            "student_email": "bob@example.com",
            "student_id": "real-id-42",
            "accommodations": {"ell": True},
        }
        pub = {"id": "a-2", "assessment": {"questions": [{"id": "q9"}]}, "settings": {}}
        sb = _fake_sb({CLASS_TABLE: sub, "published_assessments": pub})

        with patch(
            "backend.supabase_client.get_supabase", return_value=sb
        ), patch(
            "backend.services.grading_service.load_teacher_config",
            return_value={"grade_level": "10", "subject": "Bio"},
        ):
            ctx = fetch_submission_full_context(
                CLASS_TABLE, "sub-2", "teacher-9"
            )

        assert ctx == {
            "assessment": {"questions": [{"id": "q9"}]},
            "answers": {"0-1": "work"},
            "student_info": {
                "name": "Bob",
                "email": "bob@example.com",
                "student_name": "Bob",
                "student_email": "bob@example.com",
                "student_id": "real-id-42",
            },
            "teacher_config": {"grade_level": "10", "subject": "Bio"},
            "student_accommodations": {"ell": True},
        }

    def test_fetch_context_none_when_no_sb(self):
        from backend.services.portal_grading import fetch_submission_full_context

        with patch("backend.supabase_client.get_supabase", return_value=None):
            assert (
                fetch_submission_full_context(JOIN_CODE_TABLE, "sub-1", "t")
                is None
            )

    @pytest.mark.parametrize("table", BOTH_TABLES)
    def test_fetch_context_none_when_submission_absent(self, table):
        from backend.services.portal_grading import fetch_submission_full_context

        sb = _fake_sb({})  # every table returns .data=None
        with patch("backend.supabase_client.get_supabase", return_value=sb):
            assert (
                fetch_submission_full_context(table, "nope", "t") is None
            )


# ---------------------------------------------------------------------------
# Seam 3: update — _safe_update_submission
# ---------------------------------------------------------------------------
class TestUpdateSeam:
    @pytest.mark.parametrize("table", BOTH_TABLES)
    def test_update_targets_correct_table(self, table):
        from backend.services.portal_grading import _safe_update_submission

        sb = MagicMock()
        _safe_update_submission(
            sb, "sid-1", {"status": "x"}, table_name=table
        )
        assert sb.table.call_args.args[0] == table
        assert sb.table.return_value.update.call_args.args[0] == {"status": "x"}
        sb.table.return_value.update.return_value.eq.assert_called_once_with(
            "id", "sid-1"
        )

    @pytest.mark.parametrize("table", BOTH_TABLES)
    def test_update_falsy_sid_silent_skip(self, table):
        from backend.services.portal_grading import _safe_update_submission

        sb = MagicMock()
        assert (
            _safe_update_submission(sb, "", {"a": 1}, table_name=table) is None
        )
        assert (
            _safe_update_submission(sb, None, {"a": 1}, table_name=table)
            is None
        )
        assert sb.table.called is False

    def test_update_sb_none_pages_sentry_with_hashed_id(self):
        """sb=None with a real submission_id is a config problem: logger.error
        + sentry capture_message(level='error'), id is sha256[:8] hashed."""
        from backend.services.portal_grading import _safe_update_submission

        with patch(
            "backend.services.portal_grading.sentry_sdk.capture_message"
        ) as cap, patch(
            "backend.services.portal_grading.logger.error"
        ) as log_err:
            ret = _safe_update_submission(
                None, "sid-secret", {"a": 1}, table_name=JOIN_CODE_TABLE
            )

        assert ret is None
        expected_hash = hashlib.sha256(b"sid-secret").hexdigest()[:8]
        expected_msg = (
            "Cannot update submission %s: Supabase client unavailable"
            % expected_hash
        )
        cap.assert_called_once_with(expected_msg, level="error")
        log_err.assert_called_once_with(expected_msg)


# ---------------------------------------------------------------------------
# Seam 4: failure — PortalGradingTask.on_failure
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _celery_broker_env(monkeypatch):
    """grading_tasks imports backend.celery_app which requires the broker
    env var. Mirror tests/test_grading_tasks.py's isolation pattern."""
    import sys

    monkeypatch.setenv("CELERY_BROKER_URL", "redis://localhost:6379/15")
    sys.modules.pop("backend.celery_app", None)
    sys.modules.pop("backend.tasks", None)
    sys.modules.pop("backend.tasks.grading_tasks", None)


class TestFailureSeam:
    @pytest.mark.parametrize("table", BOTH_TABLES)
    def test_on_failure_writes_failed_to_table_from_args2(self, table):
        from backend.tasks.grading_tasks import PortalGradingTask

        task = PortalGradingTask()
        task.name = "grading.portal_submission"

        with patch(
            "backend.services.portal_grading._safe_update_submission"
        ) as mu, patch(
            "backend.supabase_client.get_supabase", return_value=MagicMock()
        ):
            task.on_failure(
                exc=RuntimeError("boom"),
                task_id="t",
                args=["sub-1", "teacher-1", table],
                kwargs={},
                einfo=None,
            )

        assert mu.call_args.args[2] == {
            "status": "failed",
            "error_message": "boom",
        }
        assert mu.call_args.kwargs["table_name"] == table

    def test_on_failure_truncates_error_at_500(self):
        from backend.tasks.grading_tasks import PortalGradingTask

        task = PortalGradingTask()
        task.name = "grading.portal_submission"

        with patch(
            "backend.services.portal_grading._safe_update_submission"
        ) as mu, patch(
            "backend.supabase_client.get_supabase", return_value=MagicMock()
        ):
            task.on_failure(
                exc=ValueError("x" * 600),
                task_id="t",
                args=["sub-2", "teacher-1", CLASS_TABLE],
                kwargs={},
                einfo=None,
            )

        payload = mu.call_args.args[2]
        assert payload["status"] == "failed"
        assert len(payload["error_message"]) == 500

    def test_on_failure_defaults_to_submissions_when_args2_absent(self):
        from backend.tasks.grading_tasks import PortalGradingTask

        task = PortalGradingTask()
        task.name = "grading.portal_submission"

        with patch(
            "backend.services.portal_grading._safe_update_submission"
        ) as mu, patch(
            "backend.supabase_client.get_supabase", return_value=MagicMock()
        ):
            task.on_failure(
                exc=RuntimeError("z"),
                task_id="t",
                args=["sub-3"],
                kwargs={},
                einfo=None,
            )

        assert mu.call_args.kwargs["table_name"] == JOIN_CODE_TABLE

    def test_on_failure_noop_without_submission_id(self):
        from backend.tasks.grading_tasks import PortalGradingTask

        task = PortalGradingTask()
        task.name = "grading.portal_submission"

        with patch(
            "backend.services.portal_grading._safe_update_submission"
        ) as mu:
            task.on_failure(
                exc=RuntimeError("x"),
                task_id="t",
                args=[],
                kwargs={},
                einfo=None,
            )
        assert mu.called is False

    def test_on_failure_skips_update_when_sb_none(self):
        """on_failure guards the write with `if sb:` — when get_supabase
        returns None, _safe_update_submission is never invoked."""
        from backend.tasks.grading_tasks import PortalGradingTask

        task = PortalGradingTask()
        task.name = "grading.portal_submission"

        with patch(
            "backend.services.portal_grading._safe_update_submission"
        ) as mu, patch(
            "backend.supabase_client.get_supabase", return_value=None
        ):
            task.on_failure(
                exc=RuntimeError("q"),
                task_id="t",
                args=["sub-9", "teacher-1", JOIN_CODE_TABLE],
                kwargs={},
                einfo=None,
            )
        assert mu.called is False


# ---------------------------------------------------------------------------
# PR2 grep gate: the per-table supabase_table string dispatch must be gone
# from the grading pipeline body (replaced by SubmissionRepository).
# ---------------------------------------------------------------------------
import pathlib


def test_no_supabase_table_string_dispatch_remains():
    pg = pathlib.Path("backend/services/portal_grading.py").read_text()
    assert "supabase_table ==" not in pg
    assert "table_name=supabase_table" not in pg
    assert 'supabase_table="submissions"' not in pg
    assert 'supabase_table="student_submissions"' not in pg
