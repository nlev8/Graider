"""VB2b (audit #3, High) — student-history tenant isolation.

Before this fix, ALL student history was keyed only by `student_id` in a
single global directory (`~/.graider_data/student_history/{id}.json`) with
no teacher association:

  * `student_history.add_assignment_to_history(student_id, result)` took NO
    teacher_id and always wrote the global path → Teacher A and Teacher B
    grading two different students that happen to share an id (district
    student numbers collide across rosters) clobbered each other's history.
  * `services/writing_profile.update_writing_profile/get_writing_profile`
    read/wrote the same global file directly, also teacher-agnostic.
  * The 5 `/api/student-history*` route handlers enumerated/read/deleted the
    global directory with no teacher scoping. `GET /api/student-history`
    listed EVERY tenant's students; `GET/DELETE /api/student-history/<id>`
    read/deleted ANY tenant's file; `DELETE /api/student-history` wiped
    EVERY tenant's history at once (catastrophic cross-tenant data loss).

This is a FERPA right-to-privacy violation: one teacher could read or
destroy another teacher's students' performance records.

The fix threads `teacher_id` through the write path and scopes every
read/write to `_tenant_home(teacher_id)` (which is the global HOME for the
`local-dev` single-tenant path — so dev/local behavior is unchanged — and
`~/.graider_tenants/<safe_id>/` for any real teacher UUID).

These tests pin the post-fix isolation property. They are RED before the
fix: the function-level tests fail because `teacher_id` isn't accepted, and
the route tests fail because the handlers read a single global directory
instead of the caller's tenant directory.
"""
from __future__ import annotations

import json
import os

import pytest

import backend.student_history as sh
from backend import storage as st
from backend.services import writing_profile as wp


TEACHER_A = "teacher-aaaa-1111"
TEACHER_B = "teacher-bbbb-2222"


@pytest.fixture
def isolated_home(tmp_path, monkeypatch):
    """Redirect BOTH path roots into tmp_path so tenant dirs are isolated.

    - env HOME drives `os.path.expanduser("~/...")` used by the local-dev
      legacy paths in student_history / writing_profile.
    - `storage.HOME` (captured at import) drives `_tenant_home(teacher_id)`
      for real teacher UUIDs; Supabase is unconfigured in CI so storage is
      file-only and lands under tmp_path.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(st, "HOME", str(tmp_path))
    # Force the file backend so tests are deterministic and never read/write a
    # real Supabase (local dev may have SUPABASE_* configured; CI does not).
    monkeypatch.setattr(st, "_use_supabase", lambda tid: False)
    monkeypatch.setattr(st, "GRAIDER_DATA_DIR", os.path.join(str(tmp_path), ".graider_data"))
    monkeypatch.setattr(
        st, "STUDENT_HISTORY_DIR",
        os.path.join(str(tmp_path), ".graider_data", "student_history"),
    )
    # student_history's own legacy global dir (local-dev path).
    monkeypatch.setattr(
        sh, "HISTORY_DIR",
        os.path.join(str(tmp_path), ".graider_data", "student_history"),
    )
    return tmp_path


def _result(score=85, assignment="Essay 1"):
    return {
        "score": score,
        "letter_grade": "B",
        "assignment": assignment,
        "breakdown": {"content_accuracy": 25, "completeness": 35},
        "excellent_answers": [],
        "needs_improvement": [],
        "student_responses": [],
    }


def _tenant_history_file(home, teacher_id, student_id):
    return os.path.join(
        str(home), ".graider_tenants", teacher_id,
        ".graider_data", "student_history", f"{student_id}.json",
    )


# ──────────────────────────────────────────────────────────────────
# Data-model: add_assignment_to_history threads teacher_id
# ──────────────────────────────────────────────────────────────────

class TestAddAssignmentIsolation:
    def test_two_teachers_same_student_id_do_not_clobber(self, isolated_home):
        """Same student_id graded by two teachers → separate history."""
        # Same student_id "S1" — district numbers collide across rosters.
        sh.add_assignment_to_history("S1", _result(score=95, assignment="A-from-teacherA"),
                                     teacher_id=TEACHER_A)
        sh.add_assignment_to_history("S1", _result(score=40, assignment="B-from-teacherB"),
                                     teacher_id=TEACHER_B)

        hist_a = sh.load_student_history("S1", teacher_id=TEACHER_A)
        hist_b = sh.load_student_history("S1", teacher_id=TEACHER_B)

        names_a = {a["assignment"] for a in hist_a["assignments"]}
        names_b = {a["assignment"] for a in hist_b["assignments"]}
        assert names_a == {"A-from-teacherA"}, "teacher A sees teacher B's record (leak)"
        assert names_b == {"B-from-teacherB"}, "teacher B sees teacher A's record (leak)"

    def test_real_teacher_write_lands_in_tenant_dir_not_global(self, isolated_home):
        """A real teacher's write must NOT touch the global (shared) path."""
        sh.add_assignment_to_history("S1", _result(), teacher_id=TEACHER_A)

        tenant_file = _tenant_history_file(isolated_home, TEACHER_A, "S1")
        global_file = os.path.join(
            str(isolated_home), ".graider_data", "student_history", "S1.json",
        )
        assert os.path.exists(tenant_file), "real teacher's history not in tenant dir"
        assert not os.path.exists(global_file), (
            "real teacher's history leaked to the global teacher-agnostic path"
        )

    def test_local_dev_path_unchanged(self, isolated_home):
        """local-dev (no teacher) keeps writing the legacy global path."""
        sh.add_assignment_to_history("S1", _result())  # defaults to local-dev
        global_file = os.path.join(
            str(isolated_home), ".graider_data", "student_history", "S1.json",
        )
        assert os.path.exists(global_file)


# ──────────────────────────────────────────────────────────────────
# Data-model: writing_profile threads teacher_id
# ──────────────────────────────────────────────────────────────────

_STYLE = {
    "avg_word_length": 5.0,
    "avg_sentence_length": 12.0,
    "complexity_score": 30.0,
    "academic_word_count": 3,
    "uses_contractions": False,
}


class TestWritingProfileIsolation:
    def test_profile_not_readable_across_tenants(self, isolated_home):
        wp.update_writing_profile("S1", _STYLE, "Alice", teacher_id=TEACHER_A)

        assert wp.get_writing_profile("S1", teacher_id=TEACHER_A) is not None
        assert wp.get_writing_profile("S1", teacher_id=TEACHER_B) is None, (
            "teacher B can read teacher A's student writing profile (leak)"
        )

    def test_profile_local_dev_unchanged(self, isolated_home):
        wp.update_writing_profile("S1", _STYLE, "Alice")  # local-dev
        prof = wp.get_writing_profile("S1")
        assert prof is not None
        assert prof["sample_count"] == 1

    def test_crafted_student_id_cannot_escape_tenant_dir(self, isolated_home):
        """A path-traversal student_id must stay inside the tenant dir."""
        evil = "../../../../tmp/graider_pwn"
        wp.update_writing_profile(evil, _STYLE, "Mallory", teacher_id=TEACHER_A)
        # Nothing was written outside the teacher's tenant history dir.
        escaped = os.path.join(str(isolated_home).rsplit("/", 4)[0], "graider_pwn.json")
        assert not os.path.exists("/tmp/graider_pwn.json")
        assert not os.path.exists(escaped)
        # The sanitized file lives inside the tenant dir; no slash survived, so
        # it cannot traverse out of the directory.
        tenant_dir = os.path.join(
            str(isolated_home), ".graider_tenants", TEACHER_A,
            ".graider_data", "student_history",
        )
        files = os.listdir(tenant_dir) if os.path.isdir(tenant_dir) else []
        assert files and all("/" not in f and "\\" not in f for f in files)


# ──────────────────────────────────────────────────────────────────
# Routes: /api/student-history* are scoped to the calling teacher
# ──────────────────────────────────────────────────────────────────

@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("FLASK_ENV", "development")
    from backend.app import app as flask_app
    from backend.extensions import limiter
    flask_app.config["TESTING"] = True
    flask_app.config["RATELIMIT_ENABLED"] = False
    limiter.enabled = False
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


def _hdr(teacher_id):
    return {"X-Test-Teacher-Id": teacher_id, "Content-Type": "application/json"}


class TestAssistantRemovalIsolation:
    """VB2b (Codex-found): the AI assistant's remove-student tool deleted the
    GLOBAL history file directly — a cross-tenant deletion vector. It now routes
    through the tenant-scoped storage layer."""

    def test_assistant_removal_cannot_delete_other_tenants_history(
        self, isolated_home, monkeypatch,
    ):
        from backend.services import assistant_tools_student as ats

        # Teacher A has a graded student "S1".
        st.save_student_history(
            teacher_id=TEACHER_A, student_id="S1",
            history={"student_id": "S1", "assignments": [{"score": 90}]},
        )
        # Force a roster match so removal reaches the history-delete branch.
        monkeypatch.setattr(ats, "_find_all_student_files",
                            lambda name, dirs: [("Sam One", "x.csv", "rosters")])
        monkeypatch.setattr(ats, "_load_roster",
                            lambda: [{"student_name": "Sam One", "student_id": "S1"}])

        # Teacher B asks the assistant to remove "Sam One" → must NOT touch A's S1.
        ats._execute_student_removal("Sam One", teacher_id=TEACHER_B)
        assert os.path.exists(_tenant_history_file(isolated_home, TEACHER_A, "S1")), (
            "assistant removal by teacher B deleted teacher A's history (cross-tenant)"
        )

        # Teacher A removing their own student DOES delete it.
        ats._execute_student_removal("Sam One", teacher_id=TEACHER_A)
        assert not os.path.exists(_tenant_history_file(isolated_home, TEACHER_A, "S1"))


class TestRouteTenantScoping:
    def _seed(self, home, teacher_id, student_id, history):
        """Write history straight into the teacher's tenant dir."""
        path = _tenant_history_file(home, teacher_id, student_id)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(history, f)

    def test_list_only_shows_calling_teachers_students(self, isolated_home, client):
        self._seed(isolated_home, TEACHER_A, "S1", {"student_id": "S1", "assignments": []})
        self._seed(isolated_home, TEACHER_B, "S2", {"student_id": "S2", "assignments": []})

        resp = client.get("/api/student-history", headers=_hdr(TEACHER_A))
        assert resp.status_code == 200
        ids = {s["student_id"] for s in resp.get_json()["students"]}
        assert "S1" in ids, "teacher A cannot see their own student"
        assert "S2" not in ids, "teacher A sees teacher B's student (leak)"

    def test_get_other_tenants_history_is_404(self, isolated_home, client):
        self._seed(isolated_home, TEACHER_A, "S1",
                   {"student_id": "S1", "assignments": [{"score": 91}]})

        # Owner can read.
        own = client.get("/api/student-history/S1", headers=_hdr(TEACHER_A))
        assert own.status_code == 200

        # Another teacher cannot.
        other = client.get("/api/student-history/S1", headers=_hdr(TEACHER_B))
        assert other.status_code == 404, "teacher B read teacher A's student history (leak)"

    def test_delete_one_cannot_cross_tenants(self, isolated_home, client):
        self._seed(isolated_home, TEACHER_A, "S1", {"student_id": "S1", "assignments": []})

        resp = client.delete("/api/student-history/S1", headers=_hdr(TEACHER_B))
        assert resp.status_code == 404, "teacher B deleted teacher A's history (cross-tenant)"
        assert os.path.exists(_tenant_history_file(isolated_home, TEACHER_A, "S1"))

    def test_delete_all_does_not_wipe_other_tenants(self, isolated_home, client):
        self._seed(isolated_home, TEACHER_A, "S1", {"student_id": "S1", "assignments": []})
        self._seed(isolated_home, TEACHER_B, "S9", {"student_id": "S9", "assignments": []})

        resp = client.delete("/api/student-history", headers=_hdr(TEACHER_B))
        assert resp.status_code == 200
        # Teacher B's own history is gone, teacher A's survives.
        assert not os.path.exists(_tenant_history_file(isolated_home, TEACHER_B, "S9"))
        assert os.path.exists(_tenant_history_file(isolated_home, TEACHER_A, "S1")), (
            "delete-all wiped another tenant's history (catastrophic cross-tenant loss)"
        )
