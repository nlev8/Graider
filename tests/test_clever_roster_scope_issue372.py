"""Regression tests for the Clever district-roster leak.

Source: 2026-05-14 dimensional review S2.
Pinned by both Codex + Gemini-proxy plan reviews.
"""


def _roster():
    """Teacher 'T' owns section S1 (students A, B).
    Other teacher 'OTHER' owns S2 (students C, D)."""
    return {
        "sections": [
            {"data": {"id": "S1", "teachers": ["T"],
                      "students": ["A", "B"], "name": "Period 1"}},
            {"data": {"id": "S2", "teachers": ["OTHER"],
                      "students": ["C", "D"], "name": "Period 2"}},
        ],
        "students": [
            {"data": {"id": x, "name": x}} for x in ["A", "B", "C", "D"]
        ],
    }


class TestFilterRosterToTeacher:
    def test_returns_only_teachers_own_sections(self):
        from backend.services.clever_roster_scope import filter_roster_to_teacher
        sections, students = filter_roster_to_teacher(_roster(), "T")
        section_ids = [s.get("data", s).get("id") for s in sections]
        student_ids = sorted(s.get("data", s).get("id") for s in students)
        assert section_ids == ["S1"]
        assert student_ids == ["A", "B"], (
            f"Expected only [A, B] (T's section students); got "
            f"{student_ids}. District-roster leak."
        )

    def test_returns_empty_when_teacher_owns_no_sections(self):
        from backend.services.clever_roster_scope import filter_roster_to_teacher
        sections, students = filter_roster_to_teacher(_roster(), "GHOST")
        assert sections == []
        assert students == []

    def test_handles_teacher_id_as_dict_form(self):
        """Clever sometimes returns teachers as [{id: '...'}] not [str]."""
        from backend.services.clever_roster_scope import filter_roster_to_teacher
        roster = _roster()
        roster["sections"][0]["data"]["teachers"] = [{"id": "T"}]
        sections, students = filter_roster_to_teacher(roster, "T")
        assert [s.get("data", s).get("id") for s in sections] == ["S1"]

    def test_section_with_no_enrolled_students(self):
        """A section in the teacher's set but with no students attribute
        should not crash."""
        from backend.services.clever_roster_scope import filter_roster_to_teacher
        roster = _roster()
        del roster["sections"][0]["data"]["students"]
        sections, students = filter_roster_to_teacher(roster, "T")
        assert [s.get("data", s).get("id") for s in sections] == ["S1"]
        assert students == []

    def test_empty_clever_id_returns_empty(self):
        from backend.services.clever_roster_scope import filter_roster_to_teacher
        sections, students = filter_roster_to_teacher(_roster(), "")
        assert sections == []
        assert students == []


class TestSyncRosterEndpointScopesToTeacher:
    """Integration: POST /api/clever/sync-roster end-to-end.
    Test setup mirrors tests/test_clever_routes_gaps.py:177-197 per Codex
    plan review."""

    def test_manual_sync_no_section_filter_does_not_leak_other_teachers(self):
        import os
        from unittest.mock import patch
        from flask import Flask
        from backend.routes.clever_routes import clever_bp

        app = Flask(__name__)
        app.config['TESTING'] = True
        app.config['SECRET_KEY'] = 'test'
        app.register_blueprint(clever_bp)

        persisted = {"students": None, "sections": None}
        def fake_persist_students(students, teacher_id):
            persisted["students"] = students
        def fake_persist_sections(sections, teacher_id):
            persisted["sections"] = sections

        env = {"CLEVER_CLIENT_ID": "cid", "CLEVER_CLIENT_SECRET": "csec",
               "CLEVER_DISTRICT_TOKEN": "tok",
               "CLEVER_REDIRECT_URI": "http://x/cb"}

        roster = _roster()  # T owns S1; OTHER owns S2

        with app.test_client() as client, \
             patch.dict(os.environ, env, clear=False), \
             patch('backend.routes.clever_routes._run_async',
                   return_value=roster), \
             patch('backend.routes.clever_routes.sync_roster'), \
             patch('backend.routes.clever_routes.persist_roster_as_csv',
                   side_effect=fake_persist_students), \
             patch('backend.routes.clever_routes.persist_sections_as_periods',
                   side_effect=fake_persist_sections), \
             patch('backend.routes.clever_routes._sync_classes_to_db',
                   return_value={"classes": 1, "students": 2, "enrollments": 2}), \
             patch('backend.routes.clever_routes.extract_student_accommodations',
                   return_value={}), \
             patch('backend.routes.clever_routes.map_sections_to_periods',
                   return_value=[]), \
             patch('backend.routes.clever_routes._clever_audit'):
            with client.session_transaction() as sess:
                sess["clever_user"] = {"clever_id": "T", "user_id": "T"}
            resp = client.post('/api/clever/sync-roster', json={})

        assert resp.status_code == 200, (
            f"expected 200, got {resp.status_code}: {resp.data!r}"
        )
        assert persisted["students"] is not None, (
            "persist_roster_as_csv was never called — route short-circuited"
        )
        persisted_student_ids = sorted(
            s.get("data", s).get("id", "") for s in persisted["students"]
        )
        assert persisted_student_ids == ["A", "B"], (
            f"District-roster leak. Teacher T's persisted students: "
            f"{persisted_student_ids}; expected [A, B] only."
        )
        # Also assert sections were filtered (Codex Q4 — map_sections_to_periods
        # should see only own sections via the roster["sections"] mutation).
        persisted_section_ids = [
            s.get("data", s).get("id", "") for s in persisted["sections"]
        ]
        assert persisted_section_ids == ["S1"], (
            f"Sections leak: expected [S1] only; got {persisted_section_ids}"
        )
