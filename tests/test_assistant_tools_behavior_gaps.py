"""Gap-fill unit tests for backend/services/assistant_tools_behavior.py.

Audit MAJOR #4 sprint follow-up to PR #306. Companion to existing
test_assistant_tools_behavior_unit.py. Targets the 157 uncovered LOC
(62% baseline → ~90%+).

Branches covered
* _gather_email_context full happy with manual notes + STT notes,
  30-day fallback when 14-day empty, no-data return None,
  parent contact dict-shape vs list-shape, roster fallback when
  no parent contact match
* _generate_email_ai full happy with anonymize/deanonymize +
  subject mapping for 3 tones, no-API-key returns None, exception
  returns None
* _generate_email_template tone branches
* generate_behavior_email orchestration: not-authenticated guard,
  no companion data error, chat-only mode without custom_note error,
  chat-only mode happy path, auto-tone detection (concern when
  corrections > praise, positive when praise > corrections)
* send_behavior_email parent lookup from contacts + roster fallback,
  no-parent-found error for method=email, focus method skips parent
  lookup, missing-field validation
"""
from __future__ import annotations

import json
from unittest.mock import patch, MagicMock

import pytest


# ──────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────


@pytest.fixture
def fake_students_data():
    """Behavior data shaped like _load_behavior_events output."""
    return {
        "jane_doe": {
            "name": "Jane Doe",
            "entries": [
                {
                    "date": "2026-05-01", "period": "P1",
                    "type": "correction", "count": 2,
                    "manual_notes": ["Talking during class"],
                    "stt_notes": ["[BLANK_AUDIO] said something"],
                    "notes": [], "transcripts": [], "timestamps": [],
                },
                {
                    "date": "2026-05-02", "period": "P1",
                    "type": "praise", "count": 1,
                    "manual_notes": ["Great answer"],
                    "stt_notes": [], "notes": [],
                    "transcripts": [], "timestamps": [],
                },
            ],
        },
    }


# ──────────────────────────────────────────────────────────────────
# _gather_email_context
# ──────────────────────────────────────────────────────────────────


class TestGatherEmailContext:
    def test_no_data_returns_none(self):
        from backend.services import assistant_tools_behavior as mod
        # Both 14-day AND 30-day windows return empty
        with patch.object(
            mod, "_load_behavior_events", return_value={},
        ):
            assert mod._gather_email_context("teach-1", "Nobody") is None

    def test_30_day_fallback_when_14_day_empty(self, fake_students_data):
        from backend.services import assistant_tools_behavior as mod
        # 14-day window empty; 30-day returns data
        call_count = {"i": 0}

        def loader(*args, **kwargs):
            i = call_count["i"]
            call_count["i"] += 1
            if i == 0:
                return {}  # 14-day window empty
            return fake_students_data  # 30-day window returns data

        settings = {"config": {
            "teacher_name": "Ms Doe", "subject": "Math",
            "school_name": "Lincoln", "email_signature": "",
        }}
        with patch.object(
            mod, "_load_behavior_events", side_effect=loader,
        ), patch.object(
            mod, "_load_settings", return_value=settings,
        ), patch.object(
            mod, "_load_parent_contacts", return_value={},
        ), patch.object(
            mod, "_load_roster", return_value=[],
        ):
            ctx = mod._gather_email_context("teach-1", "Jane Doe")
        assert ctx is not None
        assert ctx["name"] == "Jane Doe"
        assert ctx["corrections"] == 2
        assert ctx["praise"] == 1
        # 14-day called once, 30-day fallback called once
        assert call_count["i"] == 2

    def test_full_happy_with_dict_shape_contacts(self, fake_students_data):
        from backend.services import assistant_tools_behavior as mod
        # Parent contact stored as dict (keyed by student ID)
        contacts = {
            "stu-1": {
                "student_name": "Jane Doe",
                "parent_emails": ["parent@example.com"],
                "contacts": [{
                    "first_name": "Mom", "last_name": "Doe",
                }],
            },
        }
        settings = {"config": {
            "teacher_name": "Ms Doe", "subject": "Math",
            "school_name": "Lincoln", "email_signature": "Best,\nMs Doe",
        }}
        with patch.object(
            mod, "_load_behavior_events", return_value=fake_students_data,
        ), patch.object(
            mod, "_load_settings", return_value=settings,
        ), patch.object(
            mod, "_load_parent_contacts", return_value=contacts,
        ):
            ctx = mod._gather_email_context("teach-1", "Jane Doe")
        assert ctx["parent_email"] == "parent@example.com"
        assert "Mom" in ctx["parent_name"]
        assert "Doe" in ctx["parent_name"]
        assert ctx["teacher_name"] == "Ms Doe"
        # Manual notes preserved; STT noise included in stt_context
        assert "Talking during class" in ctx["correction_notes"]
        assert ctx["stt_context"]
        # 14-day window matched on first try; entries aggregated
        assert ctx["corrections"] == 2

    def test_list_shape_contacts(self, fake_students_data):
        from backend.services import assistant_tools_behavior as mod
        # Parent contacts stored as list (legacy shape)
        contacts = [
            {
                "student_name": "Jane Doe",
                "parent_email": "parent2@example.com",
                "parent_name": "John Doe",
            },
        ]
        settings = {"config": {}}
        with patch.object(
            mod, "_load_behavior_events", return_value=fake_students_data,
        ), patch.object(
            mod, "_load_settings", return_value=settings,
        ), patch.object(
            mod, "_load_parent_contacts", return_value=contacts,
        ):
            ctx = mod._gather_email_context("teach-1", "Jane Doe")
        assert ctx["parent_email"] == "parent2@example.com"
        assert ctx["parent_name"] == "John Doe"

    def test_falls_back_to_roster_when_no_parent_contact_match(
        self, fake_students_data,
    ):
        from backend.services import assistant_tools_behavior as mod
        # No matching contact → fall through to roster
        roster = [
            {
                "name": "Jane Doe",
                "parent_email": "roster-parent@example.com",
                "parent_name": "Roster Parent",
            },
        ]
        with patch.object(
            mod, "_load_behavior_events", return_value=fake_students_data,
        ), patch.object(
            mod, "_load_settings", return_value={"config": {}},
        ), patch.object(
            mod, "_load_parent_contacts", return_value={},
        ), patch.object(
            mod, "_load_roster", return_value=roster,
        ):
            ctx = mod._gather_email_context("teach-1", "Jane Doe")
        assert ctx["parent_email"] == "roster-parent@example.com"
        assert ctx["parent_name"] == "Roster Parent"


# ──────────────────────────────────────────────────────────────────
# _generate_email_ai
# ──────────────────────────────────────────────────────────────────


def _ctx():
    return {
        "name": "Jane Doe",
        "first_name": "Jane",
        "corrections": 3,
        "praise": 1,
        "correction_notes": ["Talking", "Off-task"],
        "praise_notes": ["Great work"],
        "correction_dates": ["2026-05-01", "2026-05-02"],
        "stt_context": ["[BLANK_AUDIO] context"],
        "parent_email": "parent@example.com",
        "parent_name": "Mom Doe",
        "teacher_name": "Ms Smith",
        "subject_area": "Math",
        "school_name": "Lincoln",
        "email_signature": "",
    }


class TestGenerateEmailAi:
    def test_no_api_key_returns_none(self):
        from backend.services import assistant_tools_behavior as mod
        with patch(
            "backend.api_keys.get_api_key", return_value="",
        ):
            assert mod._generate_email_ai(
                _ctx(), "concern", None, "teach-1",
            ) is None

    def test_happy_path_returns_subject_and_body(self):
        from backend.services import assistant_tools_behavior as mod
        # Stub out anonymize_for_ai to return the prompt unchanged
        # (no PII redaction needed for the test).
        fake_resp = MagicMock()
        text_part = MagicMock()
        text_part.text = "Dear Mom Doe,\n\nJane has been..."
        fake_resp.content_parts = [text_part]
        fake_adapter = MagicMock()
        fake_adapter.chat.return_value = fake_resp

        with patch(
            "backend.api_keys.get_api_key", return_value="sk-x",
        ), patch.object(
            mod, "anonymize_for_ai",
            side_effect=lambda prompt, _roster: (prompt, {}),
        ), patch.object(
            mod, "deanonymize",
            side_effect=lambda body, mapping: body,
        ), patch.object(
            mod, "audit_tool_action",
        ), patch(
            "backend.services.llm_adapter.AnthropicAdapter",
            return_value=fake_adapter,
        ):
            result = mod._generate_email_ai(
                _ctx(), "concern", "Custom note", "teach-1",
            )
        assert result is not None
        subject, body = result
        # Subject map matches the tone
        assert "Behavior Update" in subject
        assert "Jane" in subject
        # Body returned (anonymize/deanonymize round-tripped)
        assert "Jane has been" in body or "Mom Doe" in body

    def test_subject_for_positive_tone(self):
        from backend.services import assistant_tools_behavior as mod
        fake_resp = MagicMock()
        text_part = MagicMock()
        text_part.text = "Body text"
        fake_resp.content_parts = [text_part]
        fake_adapter = MagicMock()
        fake_adapter.chat.return_value = fake_resp
        with patch(
            "backend.api_keys.get_api_key", return_value="sk-x",
        ), patch.object(
            mod, "anonymize_for_ai",
            side_effect=lambda prompt, _r: (prompt, {}),
        ), patch.object(
            mod, "deanonymize",
            side_effect=lambda b, m: b,
        ), patch.object(
            mod, "audit_tool_action",
        ), patch(
            "backend.services.llm_adapter.AnthropicAdapter",
            return_value=fake_adapter,
        ):
            subject, _body = mod._generate_email_ai(
                _ctx(), "positive", None, "teach-1",
            )
        assert "Positive Behavior Update" in subject

    def test_subject_for_followup_tone(self):
        from backend.services import assistant_tools_behavior as mod
        fake_resp = MagicMock()
        text_part = MagicMock(); text_part.text = "Body"
        fake_resp.content_parts = [text_part]
        fake_adapter = MagicMock(); fake_adapter.chat.return_value = fake_resp
        with patch(
            "backend.api_keys.get_api_key", return_value="sk-x",
        ), patch.object(
            mod, "anonymize_for_ai",
            side_effect=lambda p, _r: (p, {}),
        ), patch.object(
            mod, "deanonymize", side_effect=lambda b, m: b,
        ), patch.object(
            mod, "audit_tool_action",
        ), patch(
            "backend.services.llm_adapter.AnthropicAdapter",
            return_value=fake_adapter,
        ):
            subject, _ = mod._generate_email_ai(
                _ctx(), "followup", None, "teach-1",
            )
        assert "Behavior Follow-Up" in subject

    def test_exception_returns_none(self):
        from backend.services import assistant_tools_behavior as mod
        with patch(
            "backend.api_keys.get_api_key", return_value="sk-x",
        ), patch.object(
            mod, "anonymize_for_ai",
            side_effect=RuntimeError("anon failed"),
        ):
            assert mod._generate_email_ai(
                _ctx(), "concern", None, "teach-1",
            ) is None


# ──────────────────────────────────────────────────────────────────
# generate_behavior_email orchestration
# ──────────────────────────────────────────────────────────────────


class TestGenerateBehaviorEmailOrchestration:
    def test_local_dev_unauthenticated_returns_error(self):
        from backend.services import assistant_tools_behavior as mod
        with patch.object(
            mod, "_get_teacher_id", return_value=None,
        ):
            result = mod.generate_behavior_email("Jane", teacher_id="local-dev")
        assert "Not authenticated" in result.get("error", "")

    def test_companion_data_mode_no_data_returns_error(self):
        from backend.services import assistant_tools_behavior as mod
        with patch.object(
            mod, "_gather_email_context", return_value=None,
        ):
            result = mod.generate_behavior_email(
                "Nobody", teacher_id="teach-1",
            )
        assert "No behavior data found" in result.get("error", "")

    def test_chat_only_mode_without_custom_note_returns_error(self):
        from backend.services import assistant_tools_behavior as mod
        result = mod.generate_behavior_email(
            "Jane",
            tone="concern",
            custom_note=None,
            use_behavior_data=False,
            teacher_id="teach-1",
        )
        assert "must provide context" in result.get("error", "")

    def test_chat_only_mode_with_note_uses_template(self):
        from backend.services import assistant_tools_behavior as mod
        # Chat-only mode bypasses _gather_email_context. AI returns None
        # → falls to template path.
        with patch.object(
            mod, "_load_settings", return_value={"config": {}},
        ), patch.object(
            mod, "_load_parent_contacts", return_value={},
        ), patch.object(
            mod, "_load_roster", return_value=[],
        ), patch.object(
            mod, "_generate_email_ai", return_value=None,
        ):
            result = mod.generate_behavior_email(
                "Jane",
                custom_note="Was disruptive yesterday",
                use_behavior_data=False,
                teacher_id="teach-1",
            )
        assert result["status"] == "success"
        assert result["data"]["ai_generated"] is False
        # Template default tone is concern when no companion data
        assert result["data"]["tone"] == "concern"
        # corrections/praise NOT included when no behavior data
        assert "corrections" not in result["data"]

    def test_auto_tone_concern_when_corrections_dominate(
        self, fake_students_data,
    ):
        # corrections=3+, corrections > praise → tone=concern
        from backend.services import assistant_tools_behavior as mod
        ctx = _ctx()
        ctx["corrections"] = 5
        ctx["praise"] = 1
        with patch.object(
            mod, "_gather_email_context", return_value=ctx,
        ), patch.object(
            mod, "_generate_email_ai", return_value=("Subject", "Body"),
        ):
            result = mod.generate_behavior_email(
                "Jane", teacher_id="teach-1",
            )
        assert result["data"]["tone"] == "concern"

    def test_auto_tone_positive_when_praise_dominates(self):
        from backend.services import assistant_tools_behavior as mod
        ctx = _ctx()
        ctx["corrections"] = 1
        ctx["praise"] = 5
        with patch.object(
            mod, "_gather_email_context", return_value=ctx,
        ), patch.object(
            mod, "_generate_email_ai", return_value=("Subject", "Body"),
        ):
            result = mod.generate_behavior_email(
                "Jane", teacher_id="teach-1",
            )
        assert result["data"]["tone"] == "positive"

    def test_ai_returns_none_falls_to_template(self):
        from backend.services import assistant_tools_behavior as mod
        ctx = _ctx()
        with patch.object(
            mod, "_gather_email_context", return_value=ctx,
        ), patch.object(
            mod, "_generate_email_ai", return_value=None,
        ):
            result = mod.generate_behavior_email(
                "Jane", tone="concern", teacher_id="teach-1",
            )
        # Used template (ai_generated=False) but still returned content
        assert result["data"]["ai_generated"] is False
        assert result["data"]["body"]
        # corrections+praise included because use_behavior_data=True
        assert "corrections" in result["data"]


# ──────────────────────────────────────────────────────────────────
# send_behavior_email
# ──────────────────────────────────────────────────────────────────


class TestSendBehaviorEmail:
    def test_missing_student_name_returns_error(self):
        from backend.services import assistant_tools_behavior as mod
        result = mod.send_behavior_email(
            "", "Subject", "Body", teacher_id="teach-1",
        )
        assert "student_name is required" in result.get("error", "")

    def test_missing_subject_returns_error(self):
        from backend.services import assistant_tools_behavior as mod
        result = mod.send_behavior_email(
            "Jane", "", "Body", teacher_id="teach-1",
        )
        assert "subject is required" in result.get("error", "")

    def test_missing_body_returns_error(self):
        from backend.services import assistant_tools_behavior as mod
        result = mod.send_behavior_email(
            "Jane", "Subject", "", teacher_id="teach-1",
        )
        assert "body is required" in result.get("error", "")

    def test_focus_method_skips_parent_lookup(self):
        # method="focus" bypasses parent email lookup
        from backend.services import assistant_tools_behavior as mod
        with patch.object(
            mod, "_load_parent_contacts",
        ) as pc_mock, patch(
            "backend.storage.save",
        ), patch(
            "backend.utils.pending_send.pending_send_path",
            return_value="/tmp/test-pending.json",
        ), patch("os.makedirs"), patch("builtins.open"), patch("json.dump"):
            result = mod.send_behavior_email(
                "Jane", "Subject", "Body",
                method="focus", teacher_id="teach-1",
            )
        # Parent contact lookup never happened
        pc_mock.assert_not_called()
        assert result["NOT_SENT"] is True
        assert "Focus Communications" in result["to"]

    def test_email_method_no_parent_returns_error(self):
        from backend.services import assistant_tools_behavior as mod
        with patch.object(
            mod, "_load_parent_contacts", return_value={},
        ), patch.object(
            mod, "_load_roster", return_value=[],
        ):
            result = mod.send_behavior_email(
                "Jane", "Subject", "Body",
                method="email", teacher_id="teach-1",
            )
        assert "No parent email found" in result.get("error", "")

    def test_email_method_finds_parent_in_contacts(self):
        from backend.services import assistant_tools_behavior as mod
        contacts = {
            "stu-1": {
                "student_name": "Jane Doe",
                "parent_emails": ["parent@example.com"],
            },
        }
        with patch.object(
            mod, "_load_parent_contacts", return_value=contacts,
        ), patch(
            "backend.storage.save",
        ), patch(
            "backend.utils.pending_send.pending_send_path",
            return_value="/tmp/test-pending.json",
        ), patch("os.makedirs"), patch("builtins.open"), patch("json.dump"):
            result = mod.send_behavior_email(
                "Jane Doe", "Subject", "Body",
                method="email", teacher_id="teach-1",
            )
        assert result["NOT_SENT"] is True
        assert result["to"] == "parent@example.com"

    def test_email_method_falls_back_to_roster(self):
        from backend.services import assistant_tools_behavior as mod
        roster = [{
            "name": "Jane Doe",
            "parent_email": "roster-parent@x.com",
        }]
        with patch.object(
            mod, "_load_parent_contacts", return_value={},
        ), patch.object(
            mod, "_load_roster", return_value=roster,
        ), patch(
            "backend.storage.save",
        ), patch(
            "backend.utils.pending_send.pending_send_path",
            return_value="/tmp/test-pending.json",
        ), patch("os.makedirs"), patch("builtins.open"), patch("json.dump"):
            result = mod.send_behavior_email(
                "Jane Doe", "Subject", "Body",
                method="email", teacher_id="teach-1",
            )
        assert result["to"] == "roster-parent@x.com"

    def test_filesystem_fallback_failure_swallowed_with_sentry(self):
        from backend.services import assistant_tools_behavior as mod
        with patch.object(
            mod, "_load_parent_contacts", return_value={},
        ), patch(
            "backend.storage.save",
            side_effect=RuntimeError("storage offline"),
        ), patch(
            "backend.utils.pending_send.pending_send_path",
            side_effect=RuntimeError("path fail"),
        ), patch(
            "backend.services.assistant_tools_behavior.sentry_sdk.capture_exception",
        ) as sentry_mock:
            # Must not raise — both storage AND filesystem fallback fail
            result = mod.send_behavior_email(
                "Jane", "Subject", "Body",
                method="focus", teacher_id="teach-1",
            )
        # sentry got the filesystem-fallback exception
        assert sentry_mock.called
        assert result["NOT_SENT"] is True
