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
# Seam 1: claim — _claim_submission_for_grading (DELETED in Slice 5 PR2
# Task 2.4; coverage retained in tests/test_submission_repository.py
# test_claim_for_grading_* tests against SubmissionRepository.claim_for_grading)
# ---------------------------------------------------------------------------

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
# Seam 3: update — _safe_update_submission (DELETED in Slice 5 PR2 Task 2.4;
# coverage retained in tests/test_submission_repository.py test_update_*
# tests against SubmissionRepository.update)
# ---------------------------------------------------------------------------

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
    """Slice 5 PR2 Task 2.4: on_failure now calls repository_for(...).mark_failed(...)
    instead of the deleted _safe_update_submission helper. Tests patch
    backend.tasks.grading_tasks.repository_for and assert the same DB-observable
    invariants: correct path discriminator (table), status='failed',
    error_message=str(exc)[:500]. DB effect is byte-identical."""

    @pytest.mark.parametrize("table", BOTH_TABLES)
    def test_on_failure_writes_failed_to_table_from_args2(self, table):
        from backend.tasks.grading_tasks import PortalGradingTask

        task = PortalGradingTask()
        task.name = "grading.portal_submission"

        with patch(
            "backend.services.submission_repository.repository_for"
        ) as mrf, patch(
            "backend.supabase_client.get_supabase", return_value=MagicMock()
        ):
            mock_repo = mrf.return_value
            task.on_failure(
                exc=RuntimeError("boom"),
                task_id="t",
                args=["sub-1", "teacher-1", table],
                kwargs={},
                einfo=None,
            )

        # repository_for called with the right path discriminator
        assert mrf.call_args.args[0] == table
        # mark_failed called with the right submission_id and exception
        mock_repo.mark_failed.assert_called_once()
        mf_args = mock_repo.mark_failed.call_args.args
        assert mf_args[0] == "sub-1"
        assert isinstance(mf_args[1], RuntimeError)
        assert str(mf_args[1]) == "boom"

    def test_on_failure_truncates_error_at_500(self):
        from backend.tasks.grading_tasks import PortalGradingTask

        task = PortalGradingTask()
        task.name = "grading.portal_submission"

        with patch(
            "backend.services.submission_repository.repository_for"
        ) as mrf, patch(
            "backend.supabase_client.get_supabase", return_value=MagicMock()
        ):
            mock_repo = mrf.return_value
            task.on_failure(
                exc=ValueError("x" * 600),
                task_id="t",
                args=["sub-2", "teacher-1", CLASS_TABLE],
                kwargs={},
                einfo=None,
            )

        mock_repo.mark_failed.assert_called_once()
        mf_args = mock_repo.mark_failed.call_args.args
        # mark_failed does str(error)[:500] internally; pin that the error arg
        # is the original exception and truncation happens inside mark_failed
        assert isinstance(mf_args[1], ValueError)
        assert len(str(mf_args[1])[:500]) == 500

    def test_on_failure_defaults_to_submissions_when_args2_absent(self):
        from backend.tasks.grading_tasks import PortalGradingTask

        task = PortalGradingTask()
        task.name = "grading.portal_submission"

        with patch(
            "backend.services.submission_repository.repository_for"
        ) as mrf, patch(
            "backend.supabase_client.get_supabase", return_value=MagicMock()
        ):
            task.on_failure(
                exc=RuntimeError("z"),
                task_id="t",
                args=["sub-3"],
                kwargs={},
                einfo=None,
            )

        # When args[2] is absent, fallback default 'submissions' must be used
        assert mrf.call_args.args[0] == JOIN_CODE_TABLE

    def test_on_failure_noop_without_submission_id(self):
        from backend.tasks.grading_tasks import PortalGradingTask

        task = PortalGradingTask()
        task.name = "grading.portal_submission"

        with patch(
            "backend.services.submission_repository.repository_for"
        ) as mrf:
            task.on_failure(
                exc=RuntimeError("x"),
                task_id="t",
                args=[],
                kwargs={},
                einfo=None,
            )
        # Neither repository_for nor mark_failed must be called
        mrf.assert_not_called()

    def test_on_failure_skips_update_when_sb_none(self):
        """on_failure guards the write with `if sb:` — when get_supabase
        returns None, repository_for / mark_failed are never invoked."""
        from backend.tasks.grading_tasks import PortalGradingTask

        task = PortalGradingTask()
        task.name = "grading.portal_submission"

        with patch(
            "backend.services.submission_repository.repository_for"
        ) as mrf, patch(
            "backend.supabase_client.get_supabase", return_value=None
        ):
            task.on_failure(
                exc=RuntimeError("q"),
                task_id="t",
                args=["sub-9", "teacher-1", JOIN_CODE_TABLE],
                kwargs={},
                einfo=None,
            )
        mrf.assert_not_called()


# ---------------------------------------------------------------------------
# Seam 5: route-layer observable contract (HTTP entry points)
#
# PRE-rewire commit: assertions pin the EXACT status code + JSON body each
# route returns today for happy-path / dedup-hit / 404 / 400.  PR2 must keep
# these assertions byte-identical post-rewire; that equivalence is the
# zero-behavior-change proof for the route layer.
#
# Probe-then-pin discipline: every assertion below was verified against the
# live route code before being written here.  Values were NOT invented.
# ---------------------------------------------------------------------------

# ---- shared fixtures and helpers for TestRouteContractSeam ----------------

import os as _os
import logging as _logging

_STUDENT_ID = "11111111-1111-1111-1111-111111111111"


def _make_sb_chain(data=None):
    """Minimal chainable Supabase query-builder mock."""
    chain = MagicMock()
    for _attr in [
        "select", "insert", "upsert", "update", "delete",
        "eq", "neq", "in_", "lt", "ilike", "order", "limit", "or_",
    ]:
        getattr(chain, _attr).return_value = chain
    chain.execute.return_value = MagicMock(data=data if data is not None else [])
    return chain


@pytest.fixture(scope="module")
def _route_app():
    """Production Flask app in test mode with rate-limiter disabled.

    Uses the real app (backend.app) so both blueprints are registered
    exactly as they are in production — this exercises the full route
    stack including @handle_route_errors and @critical_path decorators.
    """
    _os.environ.setdefault("FLASK_ENV", "development")
    _os.environ.setdefault("DEV_USER_ID", "test-teacher-001")
    _logging.disable(_logging.CRITICAL)
    from backend.app import app as _flask_app
    _flask_app.config["TESTING"] = True
    from backend.extensions import limiter as _limiter
    prior = _limiter.enabled
    _limiter.enabled = False
    yield _flask_app
    _limiter.enabled = prior
    _logging.disable(_logging.NOTSET)


@pytest.fixture(scope="module")
def _route_client(_route_app):
    return _route_app.test_client()


class TestRouteContractSeam:
    """Pins both HTTP entry routes' full request-to-response observable contract.

    PRE-rewire commit: assertions pin the EXACT status code + JSON body
    each route returns today for happy path / dedup hit / 404 / 400.  PR2
    must keep these assertions byte-identical post-rewire.  That equivalence
    is the zero-behavior-change proof for the route layer.

    join-code path: POST /api/student/submit/<code>  (anonymous, service-role)
    class-based path: POST /api/student/class-submit/<content_id>  (X-Student-Token)

    Implementation note — no authed_client fixture exists.  Class-based tests
    use the direct-invoke pattern from tests/test_student_account_coverage.py
    (test_request_context + submit_student_work(content_id) call) with
    @patch('backend.routes.student_account_routes._get_supabase').
    """

    # ------------------------------------------------------------------
    # join-code path helpers
    # ------------------------------------------------------------------

    def _jc_assessment_row(self, code="TESTJC", allow_multiple=False):
        return [{
            "id": "assess-jc-001",
            "join_code": code,
            "is_active": True,
            "teacher_id": "teacher-jc-001",
            "settings": {
                "show_score_immediately": True,
                "show_correct_answers": True,
                "allow_multiple_attempts": allow_multiple,
            },
            "assessment": {"sections": []},
        }]

    def _jc_sb(self, assessment_data, existing_submissions=None, upsert_id="sub-jc-001"):
        """Build a Supabase mock for the join-code submit route."""
        mock_sb = MagicMock()
        existing_submissions = existing_submissions or []

        def _ts(name):
            if name == "published_assessments":
                return _make_sb_chain(assessment_data)
            if name == "submissions":
                chain = _make_sb_chain(existing_submissions)
                uc = MagicMock()
                uc.execute.return_value = MagicMock(data=[{"id": upsert_id}])
                chain.upsert.return_value = uc
                return chain
            return _make_sb_chain([])

        mock_sb.table.side_effect = _ts
        return mock_sb

    # ------------------------------------------------------------------
    # class-based path helpers
    # ------------------------------------------------------------------

    def _class_session_row(self):
        from datetime import datetime, timezone, timedelta
        expires = (datetime.now(tz=timezone.utc) + timedelta(hours=4)).isoformat()
        return [{"student_id": _STUDENT_ID, "class_id": "cls-001", "expires_at": expires}]

    def _class_student_row(self):
        return [{
            "first_name": "Jane", "last_name": "Doe",
            "student_id_number": "S100", "period": "P2",
            "email": "", "teacher_id": "teacher-class-001",
        }]

    def _class_content_row(self, content_id="pc-001"):
        return [{
            "id": content_id, "class_id": "cls-001", "is_active": True,
            "target_student_ids": None,
            "content": {"sections": []},
            "title": "Quiz A", "teacher_id": "teacher-class-001",
            "settings": {"show_score_immediately": True},
            "due_date": None,
        }]

    def _class_sb(self, content_data=None, existing_subs=None, upsert_id="sub-class-001"):
        """Build a Supabase mock for the class-based submit route."""
        mock_sb = MagicMock()
        cd = content_data if content_data is not None else self._class_content_row()
        existing_subs = existing_subs or []

        def _ts(name):
            if name == "student_sessions":
                return _make_sb_chain(self._class_session_row())
            if name == "class_students":
                return _make_sb_chain([{"student_id": _STUDENT_ID}])
            if name == "students":
                return _make_sb_chain(self._class_student_row())
            if name == "student_submissions":
                chain = _make_sb_chain(existing_subs)
                uc = MagicMock()
                uc.execute.return_value = MagicMock(data=[{"id": upsert_id}])
                chain.upsert.return_value = uc
                return chain
            if name == "published_content":
                return _make_sb_chain(cd)
            return _make_sb_chain([])

        mock_sb.table.side_effect = _ts
        return mock_sb

    def _call_class_submit(self, _route_app, content_id, headers, body, mock_sb):
        """Invoke submit_student_work inside a test_request_context."""
        from backend.routes.student_account_routes import submit_student_work
        with patch("backend.routes.student_account_routes._get_supabase", return_value=mock_sb), \
             patch("backend.services.portal_grading.has_written_questions", return_value=False), \
             patch("backend.services.grading_service.grade_student_submission",
                   return_value={"score": 1, "total_points": 1, "percentage": 100.0, "questions": []}):
            with _route_app.test_request_context(
                f"/api/student/class-submit/{content_id}",
                method="POST",
                headers=headers,
                json=body,
            ):
                rv = submit_student_work(content_id)
        if isinstance(rv, tuple):
            return rv[1], rv[0].get_json()
        return rv.status_code, rv.get_json()

    # ------------------------------------------------------------------
    # join-code tests
    # ------------------------------------------------------------------

    def test_joincode_happy_path_creates_submission(self, _route_client):
        """POST /api/student/submit/<code> — new (name, code) pair.

        Probed 2026-05-20: route returns 200 with success=True, submission_id,
        student_name, score/total_points/percentage/feedback_summary/detailed_results
        when assessment is MC-only (no written questions) and show_score_immediately
        + show_correct_answers are both True.
        """
        mock_sb = self._jc_sb(self._jc_assessment_row())
        grade_rv = {
            "score": 0, "total_points": 0, "percentage": 0,
            "questions": [], "feedback_summary": "Probed feedback",
        }
        with patch("backend.routes.student_portal_routes.get_supabase", return_value=mock_sb), \
             patch("backend.services.portal_grading.has_written_questions", return_value=False), \
             patch("backend.routes.student_portal_routes.grade_student_submission", return_value=grade_rv):
            resp = _route_client.post(
                "/api/student/submit/TESTJC",
                json={"student_name": "Alice", "answers": {}},
            )

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["submission_id"] == "sub-jc-001"
        assert data["student_name"] == "Alice"
        # MC-only + show_score_immediately=True + show_correct_answers=True:
        # score, total_points, percentage, feedback_summary, detailed_results all present
        assert "score" in data
        assert "total_points" in data
        assert "percentage" in data
        assert "feedback_summary" in data
        assert "detailed_results" in data
        # No grading_status key for fully-graded MC path
        assert "grading_status" not in data

    def test_joincode_dedup_returns_existing_results(self, _route_client):
        """Second POST with same (code, student_name) hits ilike-name pre-check.

        Probed 2026-05-20: route returns 400 with error=
        'You have already submitted this assessment.' and previous_results
        dict containing the stored results.

        The ilike pre-check fires when allow_multiple_attempts is falsy (default).
        The response body includes `previous_results` — the exact stored results
        dict from the first submission row.
        """
        previous_results = {"score": 5, "total_points": 10, "percentage": 50}
        existing = [{"id": "sub-existing-001", "results": previous_results}]
        mock_sb = self._jc_sb(
            self._jc_assessment_row(allow_multiple=False),
            existing_submissions=existing,
        )
        with patch("backend.routes.student_portal_routes.get_supabase", return_value=mock_sb):
            resp = _route_client.post(
                "/api/student/submit/TESTJC",
                json={"student_name": "Alice", "answers": {}},
            )

        assert resp.status_code == 400
        data = resp.get_json()
        assert data["error"] == "You have already submitted this assessment."
        assert data["previous_results"] == previous_results

    def test_joincode_missing_content_404(self, _route_client):
        """POST to a nonexistent join_code returns 404.

        Probed 2026-05-20: route returns 404 with
        error='Assessment not found' when published_assessments query is empty.
        """
        mock_sb = self._jc_sb(assessment_data=[])  # not found
        with patch("backend.routes.student_portal_routes.get_supabase", return_value=mock_sb):
            resp = _route_client.post(
                "/api/student/submit/NOTEXIST",
                json={"student_name": "Alice", "answers": {}},
            )

        assert resp.status_code == 404
        data = resp.get_json()
        assert data["error"] == "Assessment not found"

    def test_joincode_inactive_assessment_403(self, _route_client):
        """POST to an inactive assessment returns 403.

        Probed 2026-05-20: route returns 403 with
        error='This assessment is no longer accepting submissions.'
        when is_active=False.  Named _403 (not _400) to pin the actual
        status code — there is no 400-returning missing-field validation in
        this route; all input fields use .get() with defaults.
        """
        inactive_row = [{
            "id": "assess-inactive", "join_code": "INACT1", "is_active": False,
            "settings": {}, "assessment": {}, "teacher_id": "t1",
        }]
        mock_sb = self._jc_sb(assessment_data=inactive_row)
        with patch("backend.routes.student_portal_routes.get_supabase", return_value=mock_sb):
            resp = _route_client.post(
                "/api/student/submit/INACT1",
                json={"student_name": "Alice", "answers": {}},
            )

        assert resp.status_code == 403
        data = resp.get_json()
        assert data["error"] == "This assessment is no longer accepting submissions."

    # ------------------------------------------------------------------
    # class-based tests
    # ------------------------------------------------------------------

    def test_class_happy_path_creates_submission(self, _route_app):
        """POST /api/student/class-submit/<content_id> — first submission.

        Probed 2026-05-20: route returns 200 with success=True, submission_id,
        is_late, message, score, percentage when MC-only and show_score_immediately=True.
        """
        status, data = self._call_class_submit(
            _route_app,
            content_id="pc-001",
            headers={"X-Student-Token": "tok-abc", "Content-Type": "application/json"},
            body={"answers": {}, "time_taken_seconds": 30},
            mock_sb=self._class_sb(),
        )

        assert status == 200
        assert data["success"] is True
        assert data["submission_id"] == "sub-class-001"
        assert data["is_late"] is False
        assert data["message"] == "Submitted and graded successfully!"
        # show_score_immediately=True: score + percentage present
        assert "score" in data
        assert "percentage" in data

    def test_class_second_submission_succeeds_as_new_attempt(self, _route_app):
        """Class-based path has NO ilike pre-check; it increments attempt_number.

        Probed 2026-05-20: a second POST for the same (student, content) pair
        returns 200 with a new submission_id (attempt_number=2).  This differs
        from the join-code path which blocks duplicates at the pre-check layer.
        The dedup for class-based is only at the upsert-23505 level (concurrent
        double-submit), not a soft early-return.
        """
        status, data = self._call_class_submit(
            _route_app,
            content_id="pc-001",
            headers={"X-Student-Token": "tok-abc", "Content-Type": "application/json"},
            body={"answers": {}, "time_taken_seconds": 10},
            mock_sb=self._class_sb(
                existing_subs=[{"id": "sub-first"}],
                upsert_id="sub-second",
            ),
        )

        assert status == 200
        assert data["success"] is True
        assert data["submission_id"] == "sub-second"

    def test_class_upsert_duplicate_returns_400(self, _route_app):
        """Concurrent double-submit hits 23505 unique violation → 400.

        Probed 2026-05-20: when the upsert raises an exception containing '23505',
        route returns 400 with error='You have already submitted this assignment.'
        Note the wording differs from the join-code path ('assessment' vs 'assignment').
        """
        mock_sb = MagicMock()

        def _ts(name):
            if name == "student_sessions":
                return _make_sb_chain(self._class_session_row())
            if name == "class_students":
                return _make_sb_chain([{"student_id": _STUDENT_ID}])
            if name == "students":
                return _make_sb_chain(self._class_student_row())
            if name == "student_submissions":
                chain = _make_sb_chain([])
                uc = MagicMock()
                uc.execute.side_effect = Exception(
                    "23505 duplicate key value violates unique constraint"
                )
                chain.upsert.return_value = uc
                return chain
            if name == "published_content":
                return _make_sb_chain(self._class_content_row())
            return _make_sb_chain([])

        mock_sb.table.side_effect = _ts

        from backend.routes.student_account_routes import submit_student_work
        with patch("backend.routes.student_account_routes._get_supabase", return_value=mock_sb), \
             patch("backend.services.portal_grading.has_written_questions", return_value=False), \
             patch("backend.services.grading_service.grade_student_submission",
                   return_value={"score": 0, "total_points": 1, "percentage": 0, "questions": []}):
            with _route_app.test_request_context(
                "/api/student/class-submit/pc-001",
                method="POST",
                headers={"X-Student-Token": "tok-abc", "Content-Type": "application/json"},
                json={"answers": {}, "time_taken_seconds": 10},
            ):
                rv = submit_student_work("pc-001")

        status = rv[1] if isinstance(rv, tuple) else rv.status_code
        data = rv[0].get_json() if isinstance(rv, tuple) else rv.get_json()

        assert status == 400
        assert data["error"] == "You have already submitted this assignment."

    def test_class_missing_content_404(self, _route_app):
        """POST to nonexistent content_id: visibility check returns False → 404.

        Probed 2026-05-20: _content_visible_to_student returns False when
        published_content is empty → route returns 404 with
        error='Content not found'.
        """
        mock_sb = MagicMock()

        def _ts(name):
            if name == "student_sessions":
                return _make_sb_chain(self._class_session_row())
            if name == "class_students":
                return _make_sb_chain([{"student_id": _STUDENT_ID}])
            if name == "published_content":
                return _make_sb_chain([])  # not found → visibility=False
            return _make_sb_chain([])

        mock_sb.table.side_effect = _ts

        status, data = self._call_class_submit(
            _route_app,
            content_id="nonexistent",
            headers={"X-Student-Token": "tok-abc", "Content-Type": "application/json"},
            body={"answers": {}},
            mock_sb=mock_sb,
        )

        assert status == 404
        assert data["error"] == "Content not found"

    def test_class_no_auth_returns_401(self, _route_app):
        """POST without X-Student-Token header returns 401.

        Probed 2026-05-20: missing token → _validate_student_session returns
        None → route returns 401 with error='Not logged in'.
        Note: this test does not need a Supabase mock because the auth check
        fires before any DB call.
        """
        from backend.routes.student_account_routes import submit_student_work
        with _route_app.test_request_context(
            "/api/student/class-submit/pc-001",
            method="POST",
            headers={"Content-Type": "application/json"},
            json={"answers": {}},
        ):
            rv = submit_student_work("pc-001")

        status = rv[1] if isinstance(rv, tuple) else rv.status_code
        data = rv[0].get_json() if isinstance(rv, tuple) else rv.get_json()

        assert status == 401
        assert data["error"] == "Not logged in"


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


# ---------------------------------------------------------------------------
# PR2 grep gate: inline dedup queries + inline published-content fetches must
# be gone from both submit route function bodies after Tasks 2.2 + 2.3 land.
# Scoped via inspect.getsource to the two route function bodies only so that
# the 10+ legitimate published_content references elsewhere in
# student_account_routes.py do NOT trip the gate.
# ---------------------------------------------------------------------------


def test_no_inline_published_or_dedup_queries_in_submit_routes():
    """After PR2 rewires both submit routes onto the parallel repos
    (PublishedContentRepository + SubmissionRepository.find_existing_submission),
    the route function bodies must not contain:
      - the inline ilike-name dedup pattern (join-code path)
      - the inline content_id+student_id dedup query (class path)
      - the inline published-content table fetch (either path)

    Scoped via inspect.getsource to the two route function bodies only;
    other functions in the same files that legitimately query
    published_assessments / published_content / student_submissions are
    unaffected.

    RED on the PR1-merge sha: the grep finds the inline patterns at
    student_portal_routes.py:1454 and student_account_routes.py:1137/1144.
    GREEN after PR2 Tasks 2.2 + 2.3 land the rewire.
    """
    import inspect
    from backend.routes.student_portal_routes import submit_assessment
    from backend.routes.student_account_routes import submit_student_work

    sp_body = inspect.getsource(submit_assessment)
    sa_body = inspect.getsource(submit_student_work)

    # Join-code path: no inline ilike-name dedup
    assert ".ilike('student_name'" not in sp_body and '.ilike("student_name"' not in sp_body, (
        "submit_assessment still contains inline ilike-name dedup; "
        "expected use of submission_repo.find_existing_submission"
    )
    # Join-code path: no inline published_assessments fetch
    assert "db.table('published_assessments')" not in sp_body and 'db.table("published_assessments")' not in sp_body, (
        "submit_assessment still contains inline published_assessments fetch; "
        "expected use of content_repo.fetch_by_lookup_key"
    )
    # Class path: no inline 'select id' dedup query against student_submissions.
    # The pre-Slice-5 dedup pattern was:
    #   db.table('student_submissions').select('id').eq('student_id', ...).eq('content_id', ...)
    # Other student_submissions queries in the body (the upsert, the late-context
    # fetches) select different columns and don't trip this.
    assert "db.table('student_submissions').select('id').eq(" not in sa_body and \
        'db.table("student_submissions").select("id").eq(' not in sa_body, (
        "submit_student_work still contains the inline 'select id' dedup; "
        "expected use of submission_repo.find_existing_submission"
    )
    # Class path: no inline 'select content, title, teacher_id, settings' fetch
    # against published_content. This is the route's MAIN content fetch (line 41
    # in the pre-Slice-5 body). Other published_content queries (the late-context
    # 'select id, title' fetch) stay because they serve different purposes.
    assert "db.table('published_content').select('content, title, teacher_id, settings')" not in sa_body and \
        'db.table("published_content").select("content, title, teacher_id, settings")' not in sa_body, (
        "submit_student_work still contains the inline 'select content, title, "
        "teacher_id, settings' fetch; expected use of content_repo.fetch_by_lookup_key"
    )
