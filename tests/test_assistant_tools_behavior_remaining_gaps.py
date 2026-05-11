"""Additional gap-fill tests for backend/services/assistant_tools_behavior.py.

Audit MAJOR #4 sprint follow-up to PR #331. Companion to existing
`tests/test_assistant_tools_behavior_unit.py` and
`test_assistant_tools_behavior_gaps.py`. Targets remaining 33
missing LOC (92.1% baseline).

Focus: testable branches in `_load_behavior_events` (period filter +
fallback paths), `get_behavior_summary` per-student with notes/
transcripts, generate_behavior_email chat-only parent lookup, and
send_behavior_email non-dict-contact skip.

Per dual-rate-limit precedent: test-only PR merging on green CI.
"""
from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest


MODULE = "backend.services.assistant_tools_behavior"


# ──────────────────────────────────────────────────────────────────
# _load_behavior_events fallback path with period filter
# ──────────────────────────────────────────────────────────────────


class TestLoadBehaviorEventsFallback:
    def test_fallback_path_filters_by_period_in_python(self):
        # Joined query raises → fallback returns rows; period filter
        # applied in Python (line 105: `if period and ... != period`).
        from backend.services.assistant_tools_behavior import (
            _load_behavior_events,
        )

        # Gemini review (CRITICAL): assert against 'entries' (production
        # output) NOT 'entries_map' (internal-only). Also branch the
        # mock by table NAME rather than call_count.
        # Joined query raises → fallback queries 'behavior_events'
        # (single execute) then 'behavior_sessions' (in_().execute()).

        def table_side(name):
            chain = MagicMock()
            if name == "behavior_events":
                # Joined chain (eq().gte()/.eq() variants) raises
                chain.select.return_value.eq.return_value.execute.side_effect = (
                    # First call = joined query (failures), then fallback
                    RuntimeError("joined failed"),
                    MagicMock(data=[
                        {"student_name": "Alice", "type": "correction",
                         "note": "n1", "transcript": "",
                         "event_time": "2026-05-10T10:00:00",
                         "source": "manual", "session_id": "ses1"},
                    ]),
                )
                chain.select.return_value.eq.return_value.gte.return_value.eq.return_value.execute.side_effect = RuntimeError(
                    "joined w/ filters failed"
                )
            elif name == "behavior_sessions":
                chain.select.return_value.in_.return_value.execute.return_value = MagicMock(
                    data=[{"id": "ses1", "period": "Period 1",
                           "date": "2026-05-10"}],
                )
            return chain

        sb_with_side = MagicMock()
        sb_with_side.table.side_effect = table_side

        with patch(f"{MODULE}._get_supabase", return_value=sb_with_side):
            # Period mismatch → row filtered out in Python (line 104)
            result = _load_behavior_events(
                "teach-1", period="Period 99",
            )
        # Production output uses 'entries' list, NOT internal 'entries_map'
        # dict. Period filter excluded the row → either empty result, or
        # student dict exists with empty entries list.
        assert result == {} or all(
            len(s.get("entries", [])) == 0
            for s in result.values()
        )

    def test_fallback_query_also_fails_sentry_captures(self):
        from backend.services.assistant_tools_behavior import (
            _load_behavior_events,
        )

        sb = MagicMock()
        # Both joined and fallback queries fail
        sb.table.return_value.select.return_value.eq.return_value.execute.side_effect = (
            RuntimeError("joined failed"),
            RuntimeError("fallback failed"),
        )

        with patch(f"{MODULE}._get_supabase", return_value=sb), \
             patch(f"{MODULE}.sentry_sdk.capture_exception") as mock_sentry:
            result = _load_behavior_events("teach-1")
        # Empty result (both queries failed)
        assert result == {}
        # Sentry captured the second failure
        mock_sentry.assert_called()


# ──────────────────────────────────────────────────────────────────
# event_time parse exception (lines 141-142)
# ──────────────────────────────────────────────────────────────────


class TestEventTimeParseSwallow:
    def test_invalid_event_time_swallowed_to_empty(self):
        from backend.services.assistant_tools_behavior import (
            _load_behavior_events,
        )

        sb = MagicMock()
        # Joined query returns row with malformed event_time
        sb.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[
                {"student_name": "Alice", "type": "correction",
                 "note": "n1", "transcript": "",
                 "event_time": "not-a-valid-iso",  # parse will raise
                 "source": "manual",
                 "behavior_sessions": {"period": "P1",
                                       "date": "2026-05-10"}},
            ]
        )

        with patch(f"{MODULE}._get_supabase", return_value=sb):
            result = _load_behavior_events("teach-1")
        # Row still aggregated despite parse failure — and the
        # specific timestamp is empty (Gemini MINOR fold).
        assert "alice" in result
        assert len(result["alice"]["entries"]) >= 1
        # Verify the parse-swallow actually produced an empty
        # timestamp list (would catch a regression that re-raised
        # the parse error or stored a garbage value)
        entry = result["alice"]["entries"][0]
        assert entry.get("timestamps", []) == []


# ──────────────────────────────────────────────────────────────────
# debug_behavior exception path (lines 333-334)
# ──────────────────────────────────────────────────────────────────


class TestDebugBehaviorDataExceptions:
    def test_exception_returns_error_dict(self):
        from backend.services.assistant_tools_behavior import (
            debug_behavior,
        )

        sb = MagicMock()
        sb.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.side_effect = RuntimeError(
            "DB exploded"
        )

        with patch(f"{MODULE}._get_supabase", return_value=sb), \
             patch(f"{MODULE}._get_teacher_id", return_value="teach-1"):
            result = debug_behavior(teacher_id="teach-1")
        assert "error" in result
        assert "Debug query failed" in result["error"]


# ──────────────────────────────────────────────────────────────────
# get_behavior_summary per-student notes + transcripts (380-381)
# ──────────────────────────────────────────────────────────────────


class TestBehaviorSummaryNotesTranscripts:
    def test_per_student_collects_notes_and_transcripts(self):
        from backend.services.assistant_tools_behavior import (
            get_behavior_summary,
        )

        students_data = {
            "alice": {
                "name": "Alice Smith",
                "entries": [
                    {"date": "2026-05-10", "type": "correction",
                     "count": 1,
                     "notes": ["needed redirect"],
                     "transcripts": ["please return to seat"]},
                    {"date": "2026-05-09", "type": "praise",
                     "count": 1,
                     "notes": ["completed work"],
                     "transcripts": ["great job"]},
                ],
            }
        }
        with patch(f"{MODULE}._load_behavior_events",
                   return_value=students_data):
            result = get_behavior_summary(
                student_name="Alice", teacher_id="teach-1",
            )
        assert result["status"] == "success"
        records = result["data"]
        assert records[0]["total_corrections"] == 1
        assert records[0]["total_praise"] == 1
        assert len(records[0]["notes"]) == 2
        assert len(records[0]["recent_transcripts"]) == 2


# ──────────────────────────────────────────────────────────────────
# generate_behavior_email chat-only parent contact lookup
# (lines 735-752: non-dict skip, fuzzy match, parent_emails list,
# contacts array, fallback to roster)
# ──────────────────────────────────────────────────────────────────


class TestChatOnlyParentLookup:
    def test_chat_only_parent_email_from_contacts(self):
        from backend.services.assistant_tools_behavior import (
            generate_behavior_email,
        )

        contacts = {
            "sid-alice": {
                "student_name": "Alice Smith",
                "parent_emails": ["mom@example.com"],
                "contacts": [{"first_name": "Mary", "last_name": "Smith"}],
            },
            "non-dict-entry": "should be skipped",  # non-dict, line 735
        }
        with patch(f"{MODULE}._load_parent_contacts",
                   return_value=contacts), \
             patch(f"{MODULE}._load_settings",
                   return_value={"config": {"teacher_name": "T"}}), \
             patch(f"{MODULE}._fuzzy_name_match",
                   side_effect=lambda q, n: q.lower() in (n or "").lower()), \
             patch(f"{MODULE}._generate_email_ai", return_value=None):
            result = generate_behavior_email(
                student_name="Alice Smith",
                use_behavior_data=False,
                custom_note="some context about Alice",
                teacher_id="teach-1",
            )
        assert result["data"]["to_email"] == "mom@example.com"
        assert "Mary Smith" in result["data"]["parent_name"]

    def test_chat_only_parent_email_from_roster_fallback(self):
        from backend.services.assistant_tools_behavior import (
            generate_behavior_email,
        )

        # No matching parent contact → falls back to roster
        roster = [
            {"name": "Alice Smith",
             "parent_email": "mom@example.com",
             "parent_name": "Mary Smith"},
        ]
        with patch(f"{MODULE}._load_parent_contacts", return_value={}), \
             patch(f"{MODULE}._load_roster", return_value=roster), \
             patch(f"{MODULE}._load_settings",
                   return_value={"config": {"teacher_name": "T"}}), \
             patch(f"{MODULE}._fuzzy_name_match",
                   side_effect=lambda q, n: q.lower() in (n or "").lower()), \
             patch(f"{MODULE}._generate_email_ai", return_value=None):
            result = generate_behavior_email(
                student_name="Alice",
                use_behavior_data=False,
                custom_note="context",
                teacher_id="teach-1",
            )
        assert result["data"]["to_email"] == "mom@example.com"
        assert result["data"]["parent_name"] == "Mary Smith"

    def test_chat_only_default_concern_tone_when_no_data(self):
        # Line 778 + 780: no behavior data + no tone → defaults to "concern"
        from backend.services.assistant_tools_behavior import (
            generate_behavior_email,
        )

        with patch(f"{MODULE}._load_parent_contacts", return_value={}), \
             patch(f"{MODULE}._load_roster", return_value=[]), \
             patch(f"{MODULE}._load_settings",
                   return_value={"config": {"teacher_name": "T"}}), \
             patch(f"{MODULE}._generate_email_ai", return_value=None):
            result = generate_behavior_email(
                student_name="Alice",
                use_behavior_data=False,
                custom_note="context",
                teacher_id="teach-1",
            )
        assert result["data"]["tone"] == "concern"


# ──────────────────────────────────────────────────────────────────
# send_behavior_email non-dict contact skip (line 829)
# ──────────────────────────────────────────────────────────────────


class TestSendBehaviorEmailNonDictContact:
    def test_non_dict_contact_skipped_in_email_method(self):
        from backend.services.assistant_tools_behavior import (
            send_behavior_email,
        )

        # contacts dict with one non-dict entry + one valid match
        contacts = {
            "non-dict": "string-value",  # line 829: skipped
            "sid-alice": {
                "student_name": "Alice",
                "parent_emails": ["alice-mom@example.com"],
            },
        }
        with patch(f"{MODULE}._load_parent_contacts",
                   return_value=contacts), \
             patch(f"{MODULE}._fuzzy_name_match",
                   side_effect=lambda q, n: q.lower() in (n or "").lower()):
            result = send_behavior_email(
                student_name="Alice",
                method="email",
                subject="Re: Alice",
                body="Hello",
                teacher_id="teach-1",
            )
        # Result is a pending-confirmation payload (function previews + saves)
        # — the matched parent_email survived the non-dict skip
        # No error means the contact lookup succeeded
        assert "No parent email" not in result.get("error", "")
