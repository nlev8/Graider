"""Gap-fill tests for backend/services/assistant_tools_communication.py.

Audit MAJOR #4 sprint follow-up to PR #321. Companion to existing
`tests/test_communication_tools.py`. Targets the 9 missing LOC
(95.6% baseline → 100% goal):

* `_trend_word` len(scores) < 2 → "insufficient data" (line 114)
* `generate_progress_report` no-rows error (line 164)
* `generate_report_card_comments` no-rows error (line 228), no-
  match for student_name (line 239)
* `generate_parent_conference_notes` empty student_name (line 377),
  parent_contacts.json read exception swallow (lines 396-397),
  parent contact lookup hit (line 408), accommodation note (line 413)

Per dual-rate-limit precedent: test-only PR merging on green CI.
"""
from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch

import pytest


MODULE = "backend.services.assistant_tools_communication"


# ──────────────────────────────────────────────────────────────────
# _trend_word edge case
# ──────────────────────────────────────────────────────────────────


class TestTrendWordEdge:
    def test_zero_scores_insufficient_data(self):
        from backend.services.assistant_tools_communication import (
            _trend_word,
        )
        assert _trend_word([]) == "insufficient data"

    def test_one_score_insufficient_data(self):
        from backend.services.assistant_tools_communication import (
            _trend_word,
        )
        assert _trend_word([85]) == "insufficient data"


# ──────────────────────────────────────────────────────────────────
# generate_progress_report no-rows
# ──────────────────────────────────────────────────────────────────


class TestProgressReportNoData:
    def test_no_rows_returns_error(self, patch_paths):
        from backend.services.assistant_tools_communication import (
            generate_progress_report,
        )
        with patch(f"{MODULE}._load_master_csv", return_value=[]):
            result = generate_progress_report(teacher_id="t")
        assert "error" in result
        assert "No grade data" in result["error"]


# ──────────────────────────────────────────────────────────────────
# generate_report_card_comments error paths
# ──────────────────────────────────────────────────────────────────


class TestReportCardCommentsErrors:
    def test_no_rows_returns_error(self, patch_paths):
        from backend.services.assistant_tools_communication import (
            generate_report_card_comments,
        )
        with patch(f"{MODULE}._load_master_csv", return_value=[]):
            result = generate_report_card_comments(teacher_id="t")
        assert "error" in result
        assert "No grade data" in result["error"]

    def test_student_name_not_found_returns_error(self, patch_paths):
        from backend.services.assistant_tools_communication import (
            generate_report_card_comments,
        )
        rows = [{"student_name": "Alice", "score": 80, "period": "P1"}]
        with patch(f"{MODULE}._load_master_csv", return_value=rows), \
             patch(f"{MODULE}._fuzzy_name_match", return_value=False):
            result = generate_report_card_comments(
                student_name="Nobody", teacher_id="t",
            )
        assert "error" in result
        assert "Nobody" in result["error"]


# ──────────────────────────────────────────────────────────────────
# generate_parent_conference_notes branches
# ──────────────────────────────────────────────────────────────────


class TestParentConferenceNotesBranches:
    def test_empty_student_name_returns_error(self, patch_paths):
        from backend.services.assistant_tools_communication import (
            generate_parent_conference_notes,
        )
        result = generate_parent_conference_notes(
            student_name="", teacher_id="t",
        )
        assert result == {"error": "student_name is required."}

    def test_feedback_error_propagates(self, patch_paths):
        # If draft_student_feedback returns an error, propagate it
        from backend.services.assistant_tools_communication import (
            generate_parent_conference_notes,
        )
        with patch(f"{MODULE}.draft_student_feedback",
                   return_value={"error": "feedback err"}):
            result = generate_parent_conference_notes(
                student_name="Alice", teacher_id="t",
            )
        assert result == {"error": "feedback err"}

    def test_corrupt_parent_contacts_json_swallowed(
        self, patch_paths, tmp_path,
    ):
        # PARENT_CONTACTS_FILE exists but is corrupt JSON →
        # exception swallowed, parent_name stays default
        from backend.services.assistant_tools_communication import (
            generate_parent_conference_notes,
        )
        from backend.services import assistant_tools_communication as mod

        bad_file = tmp_path / "parent_contacts.json"
        bad_file.write_text("{not valid json")

        feedback_data = {
            "student_name": "Alice Smith",
            "first_name": "Alice",
            "overall_avg": 80.0,
            "trend": "improving",
            "assignments_graded": 5,
            "strengths": {"categories": [], "skills": [],
                          "best_assignment": {"name": "Q1", "score": 90}},
            "growth_areas": {"categories": [], "skills": [],
                             "lowest_assignment": {"name": "Q2", "score": 70}},
            "next_steps": [],
        }
        with patch.object(mod, "PARENT_CONTACTS_FILE", str(bad_file)), \
             patch(f"{MODULE}.draft_student_feedback",
                   return_value=feedback_data), \
             patch(f"{MODULE}._load_settings",
                   return_value={"config": {"teacher_name": "T"}}), \
             patch(f"{MODULE}._load_master_csv", return_value=[]), \
             patch(f"{MODULE}.sentry_sdk.capture_exception") as mock_sentry:
            result = generate_parent_conference_notes(
                student_name="Alice", teacher_id="t",
            )
        # Function still returns valid agenda; sentry alerted
        assert "agenda" in result
        mock_sentry.assert_called_once()
        # parent_name fell back to default
        assert result["parent_name"] == "Parent/Guardian"

    def test_parent_contact_hit_uses_primary_contact_name(
        self, patch_paths, tmp_path,
    ):
        from backend.services.assistant_tools_communication import (
            generate_parent_conference_notes,
        )
        from backend.services import assistant_tools_communication as mod

        contacts_file = tmp_path / "parent_contacts.json"
        contacts_file.write_text(json.dumps({
            "sid-alice": {
                "primary_contact_name": "Mary Smith",
                "primary_email": "mary@example.com",
            }
        }))

        feedback_data = {
            "student_name": "Alice Smith",
            "first_name": "Alice",
            "overall_avg": 85.0,
            "trend": "improving",
            "assignments_graded": 4,
            "strengths": {"categories": [], "skills": [],
                          "best_assignment": {"name": "Q", "score": 90}},
            "growth_areas": {"categories": [], "skills": [],
                             "lowest_assignment": {"name": "Q", "score": 75}},
            "next_steps": [],
        }
        rows = [{"student_name": "Alice Smith", "student_id": "sid-alice"}]

        with patch.object(mod, "PARENT_CONTACTS_FILE", str(contacts_file)), \
             patch(f"{MODULE}.draft_student_feedback",
                   return_value=feedback_data), \
             patch(f"{MODULE}._load_settings",
                   return_value={"config": {"teacher_name": "T"}}), \
             patch(f"{MODULE}._load_master_csv", return_value=rows), \
             patch(f"{MODULE}._fuzzy_name_match",
                   side_effect=lambda q, n: "alice" in n.lower()):
            result = generate_parent_conference_notes(
                student_name="Alice", teacher_id="t",
            )

        assert result["parent_name"] == "Mary Smith"

    def test_has_accommodations_adds_note(self, patch_paths):
        from backend.services.assistant_tools_communication import (
            generate_parent_conference_notes,
        )

        feedback_data = {
            "student_name": "Alice Smith",
            "first_name": "Alice",
            "overall_avg": 80.0,
            "trend": "stable",
            "assignments_graded": 5,
            "strengths": {"categories": [], "skills": [],
                          "best_assignment": {"name": "Q", "score": 90}},
            "growth_areas": {"categories": [], "skills": [],
                             "lowest_assignment": {"name": "Q", "score": 75}},
            "next_steps": [],
            "has_accommodations": True,
        }
        with patch(f"{MODULE}.draft_student_feedback",
                   return_value=feedback_data), \
             patch(f"{MODULE}._load_settings",
                   return_value={"config": {"teacher_name": "T"}}), \
             patch(f"{MODULE}._load_master_csv", return_value=[]):
            result = generate_parent_conference_notes(
                student_name="Alice", teacher_id="t",
            )

        # Accommodation note set
        assert "IEP/504" in result["agenda"]["accommodation_note"]
