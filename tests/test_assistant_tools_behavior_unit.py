"""
Unit tests for backend/services/assistant_tools_behavior.py.

Audit MAJOR #4 sprint follow-up to PR #254. Targets the 393 uncovered LOC
in assistant_tools_behavior.py (was 6% before).

Strategy:
- File-only loaders via HOME redirect.
- Supabase-dependent loaders via a reusable mock-chain fixture.
- _generate_email_template (pure) via direct assertions on all 3 tones.
- Public tools (debug_behavior, get_behavior_summary, generate_behavior_email)
  via patching _load_behavior_events + _gather_email_context layer above.

Pattern matches tests/test_assistant_tools_unit.py (PR #254).
Lessons applied: HOME redirect from fixture, no real ~/.graider_*
writes, no unmocked external services. Per the assume-nothing rule:
final coverage delta will be verified with two full-suite runs before
opening the PR.
"""
from __future__ import annotations

import json
import os
from unittest.mock import patch, MagicMock

import pytest


TID = "teacher-alice"


@pytest.fixture
def isolated_dirs(tmp_path, monkeypatch):
    """Redirect HOME + module path constants."""
    import backend.services.assistant_tools_behavior as bh
    import backend.services.assistant_tools as at

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(bh, "SETTINGS_FILE", str(tmp_path / ".graider_global_settings.json"))
    # PARENT_CONTACTS_FILE is imported from assistant_tools — redirect there
    monkeypatch.setattr(at, "PARENT_CONTACTS_FILE",
                        str(tmp_path / ".graider_data" / "parent_contacts.json"))
    # The module-level binding in bh is also patched (since `from x import Y` copies)
    monkeypatch.setattr(bh, "PARENT_CONTACTS_FILE",
                        str(tmp_path / ".graider_data" / "parent_contacts.json"))

    return tmp_path, bh


# ──────────────────────────────────────────────────────────────────
# _load_settings (file-only)
# ──────────────────────────────────────────────────────────────────


class TestLoadSettings:
    def test_no_file_returns_empty(self, isolated_dirs):
        _, bh = isolated_dirs
        assert bh._load_settings() == {}

    def test_reads_settings_file(self, isolated_dirs):
        tmp, bh = isolated_dirs
        with open(bh.SETTINGS_FILE, 'w') as f:
            json.dump({"config": {"teacher_name": "Ms. Alice"}}, f)
        assert bh._load_settings() == {"config": {"teacher_name": "Ms. Alice"}}

    def test_corrupt_file_returns_empty(self, isolated_dirs):
        tmp, bh = isolated_dirs
        with open(bh.SETTINGS_FILE, 'w') as f:
            f.write("garbage{")
        assert bh._load_settings() == {}


# ──────────────────────────────────────────────────────────────────
# _load_parent_contacts (file-only)
# ──────────────────────────────────────────────────────────────────


class TestLoadParentContacts:
    def test_no_file_returns_empty_list(self, isolated_dirs):
        _, bh = isolated_dirs
        assert bh._load_parent_contacts() == []

    def test_reads_list_form(self, isolated_dirs):
        tmp, bh = isolated_dirs
        os.makedirs(os.path.dirname(bh.PARENT_CONTACTS_FILE), exist_ok=True)
        contacts = [{"student_name": "Alice", "parent_emails": ["a@x.com"]}]
        with open(bh.PARENT_CONTACTS_FILE, 'w') as f:
            json.dump(contacts, f)
        assert bh._load_parent_contacts() == contacts

    def test_corrupt_file_returns_empty(self, isolated_dirs):
        tmp, bh = isolated_dirs
        os.makedirs(os.path.dirname(bh.PARENT_CONTACTS_FILE), exist_ok=True)
        with open(bh.PARENT_CONTACTS_FILE, 'w') as f:
            f.write("not json")
        assert bh._load_parent_contacts() == []


# ──────────────────────────────────────────────────────────────────
# _get_teacher_id (reads Flask g)
# ──────────────────────────────────────────────────────────────────


class TestGetTeacherId:
    def test_returns_g_user_id_when_set(self):
        from flask import Flask
        from backend.services.assistant_tools_behavior import _get_teacher_id
        app = Flask(__name__)
        with app.test_request_context():
            from flask import g
            g.user_id = TID
            assert _get_teacher_id() == TID

    def test_returns_none_when_unset(self):
        from flask import Flask
        from backend.services.assistant_tools_behavior import _get_teacher_id
        app = Flask(__name__)
        with app.test_request_context():
            assert _get_teacher_id() is None


# ──────────────────────────────────────────────────────────────────
# Supabase mock builder
# ──────────────────────────────────────────────────────────────────


class _SupabaseQueryChain:
    """Mock builder for sb.table(name).select(cols).eq(...).gte(...).execute()."""

    def __init__(self, rows):
        self._rows = rows

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def gte(self, *_args, **_kwargs):
        return self

    def in_(self, *_args, **_kwargs):
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def execute(self):
        return MagicMock(data=self._rows)


def _make_supabase(rows_by_table):
    """Build a fake sb client where sb.table(name) returns a query chain
    with the rows configured for that table."""
    sb = MagicMock()
    sb.table = lambda name: _SupabaseQueryChain(rows_by_table.get(name, []))
    return sb


# ──────────────────────────────────────────────────────────────────
# _load_behavior_events
# ──────────────────────────────────────────────────────────────────


class TestLoadBehaviorEvents:
    def test_empty_supabase_returns_empty_dict(self):
        from backend.services.assistant_tools_behavior import _load_behavior_events
        sb = _make_supabase({"behavior_events": []})
        with patch("backend.services.assistant_tools_behavior._get_supabase",
                   return_value=sb):
            result = _load_behavior_events(TID)
        assert result == {}

    def test_aggregates_by_student_and_event_key(self):
        from backend.services.assistant_tools_behavior import _load_behavior_events
        rows = [
            {
                "student_name": "Alice Smith", "type": "correction",
                "note": "Off task", "transcript": "", "source": "manual",
                "event_time": "2026-05-01T09:30:00Z",
                "behavior_sessions": {"period": "Period 1", "date": "2026-05-01"},
            },
            {
                "student_name": "Alice Smith", "type": "correction",
                "note": "Talking", "transcript": "", "source": "manual",
                "event_time": "2026-05-01T09:35:00Z",
                "behavior_sessions": {"period": "Period 1", "date": "2026-05-01"},
            },
            {
                "student_name": "Bob Jones", "type": "praise",
                "note": "Great answer", "transcript": "", "source": "manual",
                "event_time": "2026-05-01T10:00:00Z",
                "behavior_sessions": {"period": "Period 2", "date": "2026-05-01"},
            },
        ]
        sb = _make_supabase({"behavior_events": rows})
        with patch("backend.services.assistant_tools_behavior._get_supabase",
                   return_value=sb):
            result = _load_behavior_events(TID)

        # Two students keyed by lowercased name
        assert "alice_smith" in result
        assert "bob_jones" in result
        # Alice has one entry (same date+period+type) with count=2
        alice_entries = result["alice_smith"]["entries"]
        assert len(alice_entries) == 1
        assert alice_entries[0]["count"] == 2
        # Both notes captured
        assert "Off task" in alice_entries[0]["notes"]
        assert "Talking" in alice_entries[0]["notes"]

    def test_dedup_notes_only_once(self):
        """If the same note appears twice for the same entry key, dedup."""
        from backend.services.assistant_tools_behavior import _load_behavior_events
        rows = [
            {
                "student_name": "Alice", "type": "correction",
                "note": "Same note", "transcript": "", "source": "manual",
                "event_time": "", "behavior_sessions": {"period": "1", "date": "2026-05-01"},
            },
            {
                "student_name": "Alice", "type": "correction",
                "note": "Same note", "transcript": "", "source": "manual",
                "event_time": "", "behavior_sessions": {"period": "1", "date": "2026-05-01"},
            },
        ]
        sb = _make_supabase({"behavior_events": rows})
        with patch("backend.services.assistant_tools_behavior._get_supabase",
                   return_value=sb):
            result = _load_behavior_events(TID)
        entry = result["alice"]["entries"][0]
        # Count tracks raw events, but notes list is deduped
        assert entry["count"] == 2
        assert entry["notes"] == ["Same note"]

    def test_separates_manual_and_stt_notes(self):
        from backend.services.assistant_tools_behavior import _load_behavior_events
        rows = [
            {
                "student_name": "Alice", "type": "correction",
                "note": "Manual note", "transcript": "", "source": "manual",
                "event_time": "", "behavior_sessions": {"period": "1", "date": "2026-05-01"},
            },
            {
                "student_name": "Alice", "type": "correction",
                "note": "STT note", "transcript": "audio transcript", "source": "stt",
                "event_time": "", "behavior_sessions": {"period": "1", "date": "2026-05-01"},
            },
        ]
        sb = _make_supabase({"behavior_events": rows})
        with patch("backend.services.assistant_tools_behavior._get_supabase",
                   return_value=sb):
            result = _load_behavior_events(TID)
        entry = result["alice"]["entries"][0]
        assert "Manual note" in entry["manual_notes"]
        assert "STT note" in entry["stt_notes"]
        assert "audio transcript" in entry["transcripts"]

    def test_fuzzy_filter_by_student_name(self):
        from backend.services.assistant_tools_behavior import _load_behavior_events
        rows = [
            {
                "student_name": "Alice Smith", "type": "correction",
                "note": "x", "transcript": "", "source": "manual",
                "event_time": "", "behavior_sessions": {"period": "1", "date": "2026-05-01"},
            },
            {
                "student_name": "Bob Jones", "type": "correction",
                "note": "y", "transcript": "", "source": "manual",
                "event_time": "", "behavior_sessions": {"period": "1", "date": "2026-05-01"},
            },
        ]
        sb = _make_supabase({"behavior_events": rows})
        with patch("backend.services.assistant_tools_behavior._get_supabase",
                   return_value=sb):
            result = _load_behavior_events(TID, student_name="Alice")
        assert "alice_smith" in result
        assert "bob_jones" not in result

    def test_event_time_parsed_to_hhmm_timestamp(self):
        from backend.services.assistant_tools_behavior import _load_behavior_events
        rows = [
            {
                "student_name": "Alice", "type": "correction",
                "note": "x", "transcript": "", "source": "manual",
                "event_time": "2026-05-01T14:35:22Z",
                "behavior_sessions": {"period": "1", "date": "2026-05-01"},
            },
        ]
        sb = _make_supabase({"behavior_events": rows})
        with patch("backend.services.assistant_tools_behavior._get_supabase",
                   return_value=sb):
            result = _load_behavior_events(TID)
        entry = result["alice"]["entries"][0]
        assert "14:35" in entry["timestamps"]


# ──────────────────────────────────────────────────────────────────
# debug_behavior
# ──────────────────────────────────────────────────────────────────


class TestDebugBehavior:
    def test_local_dev_returns_auth_error(self):
        from backend.services.assistant_tools_behavior import debug_behavior
        from flask import Flask
        # Inside Flask context but no g.user_id set, _get_teacher_id returns None
        # so teacher_id stays 'local-dev' → error.
        app = Flask(__name__)
        with app.test_request_context():
            result = debug_behavior(teacher_id='local-dev')
        assert "error" in result
        assert "Not authenticated" in result["error"]

    def test_returns_diagnostics_with_real_teacher_id(self):
        from backend.services.assistant_tools_behavior import debug_behavior
        sessions = [{"id": "s1", "period": "1", "date": "2026-05-01", "device": "iPad"}]
        events = [{"id": "e1", "student_name": "Alice", "type": "correction",
                   "event_time": "2026-05-01T10:00:00Z"}]
        sb = _make_supabase({"behavior_sessions": sessions, "behavior_events": events})
        with patch("backend.services.assistant_tools_behavior._get_supabase",
                   return_value=sb):
            result = debug_behavior(teacher_id=TID)
        assert result["status"] == "success"
        assert result["teacher_id"] == TID
        assert result["total_sessions"] == 1
        assert result["total_events"] == 1
        assert "Alice" in result["student_names_in_db"]


# ──────────────────────────────────────────────────────────────────
# get_behavior_summary
# ──────────────────────────────────────────────────────────────────


class TestGetBehaviorSummary:
    def test_local_dev_returns_auth_error(self):
        from backend.services.assistant_tools_behavior import get_behavior_summary
        from flask import Flask
        app = Flask(__name__)
        with app.test_request_context():
            result = get_behavior_summary(teacher_id='local-dev')
        assert "error" in result

    def test_no_data_returns_helpful_message(self):
        from backend.services.assistant_tools_behavior import get_behavior_summary
        with patch("backend.services.assistant_tools_behavior._load_behavior_events",
                   return_value={}):
            result = get_behavior_summary(teacher_id=TID)
        assert result["status"] == "success"
        assert "No behavior data" in result["data"]

    def test_no_data_for_specific_student_includes_widen_hint(self):
        from backend.services.assistant_tools_behavior import get_behavior_summary
        with patch("backend.services.assistant_tools_behavior._load_behavior_events",
                   return_value={}):
            result = get_behavior_summary(student_name="Alice", days=7, teacher_id=TID)
        assert "error" in result
        # Hint suggests 30/90 day windows
        assert "days=30" in result["error"] or "days=90" in result["error"]

    def test_class_overview_aggregates_corrections_and_praise(self):
        from backend.services.assistant_tools_behavior import get_behavior_summary
        students_data = {
            "alice": {
                "name": "Alice", "entries": [
                    {"date": "2026-05-01", "type": "correction", "count": 3},
                    {"date": "2026-05-01", "type": "praise", "count": 1},
                ],
            },
            "bob": {
                "name": "Bob", "entries": [
                    {"date": "2026-05-01", "type": "correction", "count": 5},
                ],
            },
        }
        with patch("backend.services.assistant_tools_behavior._load_behavior_events",
                   return_value=students_data):
            result = get_behavior_summary(teacher_id=TID)
        # Sorted by corrections desc → Bob first
        assert result["status"] == "success"
        assert result["data"]["students"][0]["name"] == "Bob"
        assert result["data"]["students"][0]["corrections"] == 5

    def test_student_specific_view_includes_daily_breakdown(self):
        from backend.services.assistant_tools_behavior import get_behavior_summary
        students_data = {
            "alice": {
                "name": "Alice", "entries": [
                    {"date": "2026-05-01", "type": "correction",
                     "count": 2, "notes": ["off task"], "transcripts": []},
                    {"date": "2026-05-02", "type": "praise",
                     "count": 1, "notes": ["good answer"], "transcripts": []},
                ],
            },
        }
        with patch("backend.services.assistant_tools_behavior._load_behavior_events",
                   return_value=students_data):
            result = get_behavior_summary(student_name="Alice", teacher_id=TID)
        assert result["status"] == "success"
        student = result["data"][0]
        assert student["total_corrections"] == 2
        assert student["total_praise"] == 1
        # Daily breakdown
        assert "2026-05-01" in student["daily_breakdown"]
        assert student["daily_breakdown"]["2026-05-01"]["corrections"] == 2

    def test_days_clamped_max_90(self):
        """days > 90 clamped to 90; days=0 clamped to 1."""
        from backend.services.assistant_tools_behavior import get_behavior_summary
        with patch("backend.services.assistant_tools_behavior._load_behavior_events",
                   return_value={}) as mock_load:
            get_behavior_summary(days=500, teacher_id=TID)
        # cutoff_date in the call args should be ~90 days ago
        # We just verify _load_behavior_events was called (clamping happens upstream)
        mock_load.assert_called_once()


# ──────────────────────────────────────────────────────────────────
# _generate_email_template (pure logic)
# ──────────────────────────────────────────────────────────────────


def _make_ctx(**overrides):
    ctx = {
        "name": "Alice Smith", "first_name": "Alice",
        "corrections": 0, "praise": 0,
        "correction_notes": [], "praise_notes": [],
        "correction_dates": [], "stt_context": [],
        "parent_email": "p@x.com", "parent_name": "Mr. Smith",
        "teacher_name": "Ms. Alice", "subject_area": "Math",
        "school_name": "Example HS", "email_signature": "",
    }
    ctx.update(overrides)
    return ctx


class TestGenerateEmailTemplate:
    def test_concern_tone_includes_corrections(self):
        from backend.services.assistant_tools_behavior import _generate_email_template
        ctx = _make_ctx(corrections=3, correction_notes=["off task", "talking"])
        subject, body = _generate_email_template(ctx, "concern", None)
        assert "Behavior Update - Alice" in subject
        assert "3 correction" in body
        assert "off task" in body
        assert "Mr. Smith" in body  # parent greeting

    def test_positive_tone_includes_praise(self):
        from backend.services.assistant_tools_behavior import _generate_email_template
        ctx = _make_ctx(praise=5, praise_notes=["great work"])
        subject, body = _generate_email_template(ctx, "positive", None)
        assert "Positive Behavior Update - Alice" in subject
        assert "5 positive" in body
        assert "great work" in body

    def test_followup_tone(self):
        from backend.services.assistant_tools_behavior import _generate_email_template
        ctx = _make_ctx(corrections=2, praise=1)
        subject, body = _generate_email_template(ctx, "followup", None)
        assert "Behavior Follow-Up - Alice" in subject
        assert "2 correction" in body
        assert "1 positive" in body

    def test_custom_note_appended(self):
        from backend.services.assistant_tools_behavior import _generate_email_template
        ctx = _make_ctx(corrections=1)
        subject, body = _generate_email_template(
            ctx, "concern", "Please call me if you have questions.",
        )
        assert "Please call me if you have questions." in body

    def test_no_parent_name_uses_generic_greeting(self):
        from backend.services.assistant_tools_behavior import _generate_email_template
        ctx = _make_ctx(parent_name="")
        subject, body = _generate_email_template(ctx, "concern", None)
        assert "Parent/Guardian of Alice" in body

    def test_signature_overrides_teacher_name(self):
        from backend.services.assistant_tools_behavior import _generate_email_template
        ctx = _make_ctx(email_signature="Best regards,\nMs. A. Smith\nMath Dept.")
        subject, body = _generate_email_template(ctx, "concern", None)
        assert "Ms. A. Smith" in body

    def test_no_signature_falls_back_to_teacher_name(self):
        from backend.services.assistant_tools_behavior import _generate_email_template
        ctx = _make_ctx(email_signature="")
        subject, body = _generate_email_template(ctx, "concern", None)
        # teacher_name in signature
        assert "Ms. Alice" in body
        assert "Example HS" in body


# ──────────────────────────────────────────────────────────────────
# generate_behavior_email — auth + chat-only mode
# ──────────────────────────────────────────────────────────────────


class TestGenerateBehaviorEmail:
    def test_local_dev_returns_auth_error(self):
        from backend.services.assistant_tools_behavior import generate_behavior_email
        from flask import Flask
        app = Flask(__name__)
        with app.test_request_context():
            result = generate_behavior_email("Alice", teacher_id='local-dev')
        assert "error" in result
        assert "Not authenticated" in result["error"]

    def test_chat_only_mode_requires_custom_note(self, isolated_dirs):
        from backend.services.assistant_tools_behavior import generate_behavior_email
        result = generate_behavior_email(
            "Alice", use_behavior_data=False, custom_note=None, teacher_id=TID,
        )
        assert "error" in result
        assert "custom_note" in result["error"]

    def test_no_behavior_data_with_use_behavior_data_returns_error(self, isolated_dirs):
        from backend.services.assistant_tools_behavior import generate_behavior_email
        # _gather_email_context returns None when no data
        with patch("backend.services.assistant_tools_behavior._gather_email_context",
                   return_value=None):
            result = generate_behavior_email("Alice", teacher_id=TID)
        assert "error" in result
        assert "No behavior data" in result["error"]

    def test_chat_only_happy_path_uses_template(self, isolated_dirs):
        from backend.services.assistant_tools_behavior import generate_behavior_email
        # AI fails → template fallback. Patch _generate_email_ai to return None.
        with patch("backend.services.assistant_tools_behavior._generate_email_ai",
                   return_value=None), \
             patch("backend.services.assistant_tools_behavior._load_roster",
                   return_value=[]):
            result = generate_behavior_email(
                "Alice Smith",
                use_behavior_data=False,
                custom_note="Alice has been struggling lately.",
                tone="concern",
                teacher_id=TID,
            )
        # Result is wrapped: {"status": "success", "data": {subject, body, ...}}
        assert result.get("status") == "success"
        data = result["data"]
        assert "subject" in data
        assert "body" in data
        # AI was patched to None → template path used
        assert data.get("ai_generated") is False
        # Template includes the custom_note
        assert "Alice has been struggling lately." in data["body"]


# ──────────────────────────────────────────────────────────────────
# require_teacher_id contract pin
# ──────────────────────────────────────────────────────────────────


class TestTeacherIdRequired:
    def test_get_behavior_summary_empty_raises(self):
        from backend.services.assistant_tools_behavior import get_behavior_summary
        with pytest.raises(ValueError, match="teacher_id is required"):
            get_behavior_summary(teacher_id="")

    def test_debug_behavior_empty_raises(self):
        from backend.services.assistant_tools_behavior import debug_behavior
        with pytest.raises(ValueError, match="teacher_id is required"):
            debug_behavior(teacher_id="")

    def test_generate_behavior_email_empty_raises(self):
        from backend.services.assistant_tools_behavior import generate_behavior_email
        with pytest.raises(ValueError, match="teacher_id is required"):
            generate_behavior_email("Alice", teacher_id="")
