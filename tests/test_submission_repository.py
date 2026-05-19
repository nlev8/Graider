"""Unit tests for backend.services.submission_repository (PR1, additive).

The repository is unwired in PR1 (no production code imports it). These tests
pin its surface against the same observable behavior the characterization net
(tests/test_dual_path_consolidation_char.py) recorded for the legacy seam
functions in backend.services.portal_grading.

Fake supabase client (no real network/Supabase):
"""
import hashlib


class _Resp:
    def __init__(self, data):
        self.data = data


class _Query:
    def __init__(self, table):
        self._t = table
        self._filters = {}

    def select(self, *_a, **_k):
        return self

    def update(self, fields):
        self._t.updates.append(dict(fields))
        return self

    def eq(self, col, val):
        self._filters[col] = val
        return self

    def single(self):
        return self

    def execute(self):
        if self._t.raise_on_execute:
            raise self._t.raise_on_execute
        return _Resp(self._t.row)


class FakeTable:
    def __init__(self):
        self.row = None
        self.updates = []
        self.raise_on_execute = None


class FakeSupabase:
    def __init__(self):
        self.tables = {}

    def table(self, name):
        t = self.tables.setdefault(name, FakeTable())
        self._last = name
        return _Query(t)


# ---------------------------------------------------------------------------
# Step 1: enum + factory
# ---------------------------------------------------------------------------
def test_path_type_enum_values_are_the_legacy_table_strings():
    from backend.services.submission_repository import SubmissionPathType

    assert SubmissionPathType.JOIN_CODE.value == "submissions"
    assert SubmissionPathType.CLASS.value == "student_submissions"


def test_repository_for_enum_returns_correct_adapter():
    from backend.services.submission_repository import (
        ClassSubmissionRepository,
        JoinCodeSubmissionRepository,
        SubmissionPathType,
        repository_for,
    )

    sb = FakeSupabase()
    assert isinstance(
        repository_for(SubmissionPathType.JOIN_CODE, sb),
        JoinCodeSubmissionRepository,
    )
    assert isinstance(
        repository_for(SubmissionPathType.CLASS, sb),
        ClassSubmissionRepository,
    )


def test_repository_for_accepts_legacy_string():
    from backend.services.submission_repository import (
        ClassSubmissionRepository,
        JoinCodeSubmissionRepository,
        repository_for,
    )

    sb = FakeSupabase()
    assert isinstance(
        repository_for("submissions", sb), JoinCodeSubmissionRepository
    )
    assert isinstance(
        repository_for("student_submissions", sb), ClassSubmissionRepository
    )


def test_repository_for_rejects_unknown():
    import pytest

    from backend.services.submission_repository import repository_for

    with pytest.raises(ValueError):
        repository_for("not_a_table", FakeSupabase())


# ---------------------------------------------------------------------------
# Step 3: update (port of _safe_update_submission)
# ---------------------------------------------------------------------------
import pytest  # noqa: E402


@pytest.fixture
def repos():
    """(join_code_repo, class_repo) sharing one FakeSupabase."""
    from backend.services.submission_repository import repository_for

    sb = FakeSupabase()
    return (
        repository_for("submissions", sb),
        repository_for("student_submissions", sb),
        sb,
    )


def test_update_targets_own_table_with_payload_and_id():
    from backend.services.submission_repository import repository_for

    for table in ("submissions", "student_submissions"):
        sb = FakeSupabase()
        repo = repository_for(table, sb)
        repo.update("sid-1", {"status": "x"})
        assert sb.tables[table].updates == [{"status": "x"}]
        # No OTHER table was touched.
        assert set(sb.tables.keys()) == {table}


def test_update_falsy_submission_id_is_silent_noop():
    from backend.services.submission_repository import repository_for

    for table in ("submissions", "student_submissions"):
        sb = FakeSupabase()
        repo = repository_for(table, sb)
        assert repo.update("", {"a": 1}) is None
        assert repo.update(None, {"a": 1}) is None
        assert sb.tables == {}  # table() never called


def test_update_sb_none_pages_sentry_with_hashed_id(monkeypatch):
    from backend.services.submission_repository import repository_for

    captured = {}

    def fake_capture_message(msg, level=None):
        captured["msg"] = msg
        captured["level"] = level

    monkeypatch.setattr(
        "backend.services.submission_repository.sentry_sdk.capture_message",
        fake_capture_message,
    )
    repo = repository_for("submissions", None)
    assert repo.update("sid-secret", {"a": 1}) is None
    expected_hash = hashlib.sha256(b"sid-secret").hexdigest()[:8]
    assert captured["msg"] == (
        "Cannot update submission %s: Supabase client unavailable"
        % expected_hash
    )
    assert captured["level"] == "error"


def test_update_swallows_execute_exception_and_captures(monkeypatch):
    from backend.services.submission_repository import repository_for

    sb = FakeSupabase()
    sb.table("submissions")  # materialize
    sb.tables["submissions"].raise_on_execute = RuntimeError("db down")
    captured = {}
    monkeypatch.setattr(
        "backend.services.submission_repository.sentry_sdk.capture_exception",
        lambda e: captured.setdefault("exc", e),
    )
    repo = repository_for("submissions", sb)
    # Does not raise.
    assert repo.update("sid-1", {"status": "x"}) is None
    assert isinstance(captured["exc"], RuntimeError)


# ---------------------------------------------------------------------------
# Step 5: fetch (port of _fetch_submission_row)
# ---------------------------------------------------------------------------
def test_fetch_returns_own_table_row():
    from backend.services.submission_repository import repository_for

    for table in ("submissions", "student_submissions"):
        sb = FakeSupabase()
        sb.table(table)  # materialize
        sb.tables[table].row = {"id": "sid-1", "status": "queued"}
        repo = repository_for(table, sb)
        assert repo.fetch("sid-1") == {"id": "sid-1", "status": "queued"}


def test_fetch_none_when_absent():
    from backend.services.submission_repository import repository_for

    for table in ("submissions", "student_submissions"):
        sb = FakeSupabase()  # row defaults to None
        repo = repository_for(table, sb)
        assert repo.fetch("nope") is None


def test_fetch_none_when_sb_or_id_falsy():
    from backend.services.submission_repository import repository_for

    repo_no_sb = repository_for("submissions", None)
    assert repo_no_sb.fetch("sid") is None
    sb = FakeSupabase()
    repo = repository_for("submissions", sb)
    assert repo.fetch(None) is None
    assert repo.fetch("") is None
    assert sb.tables == {}  # table() never called for falsy id


def test_fetch_none_and_captures_on_execute_exception(monkeypatch):
    from backend.services.submission_repository import repository_for

    sb = FakeSupabase()
    sb.table("submissions")
    sb.tables["submissions"].raise_on_execute = RuntimeError("boom")
    captured = {}
    monkeypatch.setattr(
        "backend.services.submission_repository.sentry_sdk.capture_exception",
        lambda e: captured.setdefault("exc", e),
    )
    repo = repository_for("submissions", sb)
    assert repo.fetch("sid-1") is None
    assert isinstance(captured["exc"], RuntimeError)


# ---------------------------------------------------------------------------
# Step 7: claim_for_grading (Correction #1 — UNCONDITIONAL write, returns None)
# ---------------------------------------------------------------------------
def test_claim_writes_exact_three_fields_to_own_table():
    from backend.services.submission_repository import repository_for

    for table in ("submissions", "student_submissions"):
        sb = FakeSupabase()
        repo = repository_for(table, sb)
        ret = repo.claim_for_grading("sid-1", "task-99")
        # Returns None — no bool, no "already claimed" branch.
        assert ret is None
        writes = sb.tables[table].updates
        assert len(writes) == 1
        payload = writes[0]
        assert sorted(payload.keys()) == [
            "grading_started_at",
            "grading_task_id",
            "status",
        ]
        assert payload["status"] == "grading_in_progress"
        assert payload["grading_task_id"] == "task-99"
        assert isinstance(payload["grading_started_at"], str)
        assert payload["grading_started_at"].endswith("+00:00")
        assert set(sb.tables.keys()) == {table}


def test_claim_is_unconditional_even_when_already_in_progress():
    """Correction #1: there is NO 'already claimed' guard. A second claim
    with a different task_id overwrites unconditionally."""
    from backend.services.submission_repository import repository_for

    sb = FakeSupabase()
    sb.table("submissions")
    sb.tables["submissions"].row = {
        "id": "sid-1",
        "status": "grading_in_progress",
        "grading_task_id": "other-task",
    }
    repo = repository_for("submissions", sb)
    assert repo.claim_for_grading("sid-1", "new-task") is None
    assert sb.tables["submissions"].updates[-1]["grading_task_id"] == "new-task"


def test_claim_noop_when_sb_or_id_falsy():
    from backend.services.submission_repository import repository_for

    assert repository_for("submissions", None).claim_for_grading(
        "sid", "t"
    ) is None
    sb = FakeSupabase()
    repo = repository_for("submissions", sb)
    assert repo.claim_for_grading(None, "t") is None
    assert repo.claim_for_grading("", "t") is None
    assert sb.tables == {}


# ---------------------------------------------------------------------------
# Step 9: mark_failed (Correction #3 — status='failed', error_message[:500])
# ---------------------------------------------------------------------------
def test_mark_failed_writes_exact_fields_to_own_table():
    from backend.services.submission_repository import repository_for

    for table in ("submissions", "student_submissions"):
        sb = FakeSupabase()
        repo = repository_for(table, sb)
        assert repo.mark_failed("sid-1", RuntimeError("boom")) is None
        assert sb.tables[table].updates == [
            {"status": "failed", "error_message": "boom"}
        ]
        assert set(sb.tables.keys()) == {table}


def test_mark_failed_truncates_error_at_500():
    from backend.services.submission_repository import repository_for

    sb = FakeSupabase()
    repo = repository_for("student_submissions", sb)
    repo.mark_failed("sid-1", ValueError("x" * 600))
    payload = sb.tables["student_submissions"].updates[0]
    assert payload["status"] == "failed"
    assert len(payload["error_message"]) == 500
    assert payload["error_message"] == "x" * 500


def test_mark_failed_stringifies_non_str_error():
    from backend.services.submission_repository import repository_for

    sb = FakeSupabase()
    repo = repository_for("submissions", sb)
    repo.mark_failed("sid-1", KeyError("missing"))
    assert sb.tables["submissions"].updates[0]["error_message"] == str(
        KeyError("missing")
    )


# ---------------------------------------------------------------------------
# Step 11: normalize_context — byte-identical to the char-net dicts
# ---------------------------------------------------------------------------
# These reproduce the EXACT normalized context dicts pinned by
# tests/test_dual_path_consolidation_char.py (the live
# fetch_submission_full_context output). The relocated :526 branch body
# (JOIN_CODE: student_id='') and :else (CLASS: data['student_id'] or '')
# must yield byte-identical dicts.
def test_join_code_normalize_context_byte_identical():
    from backend.services.submission_repository import (
        JoinCodeSubmissionRepository,
    )

    row = {
        "id": "sub-1",
        "assessment_id": "a-1",
        "answers": {"q1": "ans"},
        "student_name": "Ana",
        "student_email": "ana@example.com",
    }
    base = {
        "assessment": {"questions": [{"id": "q1"}]},
        "teacher_config": {"grade_level": "8"},
        "student_accommodations": {"iep": True, "extended_time": 1.5},
    }
    repo = JoinCodeSubmissionRepository(FakeSupabase())
    ctx = repo.normalize_context(row, base)
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


def test_join_code_normalize_context_forces_empty_student_id():
    """Even when the join-code row carries a student_id, the relocated
    'submissions' branch hard-codes '' (parity with the legacy thread spawn)."""
    from backend.services.submission_repository import (
        JoinCodeSubmissionRepository,
    )

    row = {
        "answers": {},
        "student_name": "X",
        "student_email": "x@e.com",
        "student_id": "should-be-ignored",
    }
    repo = JoinCodeSubmissionRepository(FakeSupabase())
    ctx = repo.normalize_context(row, {"assessment": None,
                                       "teacher_config": {},
                                       "student_accommodations": None})
    assert ctx["student_info"]["student_id"] == ""


def test_class_normalize_context_byte_identical():
    from backend.services.submission_repository import (
        ClassSubmissionRepository,
    )

    row = {
        "id": "sub-2",
        "assessment_id": "a-2",
        "answers": {"0-1": "work"},
        "student_name": "Bob",
        "student_email": "bob@example.com",
        "student_id": "real-id-42",
        "accommodations": {"ell": True},
    }
    base = {
        "assessment": {"questions": [{"id": "q9"}]},
        "teacher_config": {"grade_level": "10", "subject": "Bio"},
        "student_accommodations": {"ell": True},
    }
    repo = ClassSubmissionRepository(FakeSupabase())
    ctx = repo.normalize_context(row, base)
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


def test_class_normalize_context_student_id_falls_back_to_empty():
    """Class-based 'else' branch: data.get('student_id') or '' -> '' when
    the row has no student_id (byte-faithful relocation of line 529)."""
    from backend.services.submission_repository import (
        ClassSubmissionRepository,
    )

    row = {"answers": {}, "student_name": "Y", "student_email": "y@e.com"}
    repo = ClassSubmissionRepository(FakeSupabase())
    ctx = repo.normalize_context(row, {"assessment": None,
                                       "teacher_config": {},
                                       "student_accommodations": None})
    assert ctx["student_info"]["student_id"] == ""


def test_base_normalize_context_raises_not_implemented():
    from backend.services.submission_repository import SubmissionRepository

    repo = SubmissionRepository(FakeSupabase())
    import pytest as _pt

    with _pt.raises(NotImplementedError):
        repo.normalize_context({}, {})
