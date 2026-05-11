"""Gap-fill tests for backend/services/assistant_tools_planning.py.

Audit MAJOR #4 sprint follow-up to PR #315. Companion to existing
`tests/test_planning_tools.py` which pins the format-validation
contracts. This file targets the 42 missing LOC (75.8% baseline →
95%+ goal):

* `_get_standards_for_lesson`: lesson_file present + read happy,
  file-read exception swallow
* `suggest_remediation`: no-rows error, no-weak-areas success
  message, completeness/writing/effort branches
* `align_to_standards`: no-standards-loaded error, empty topic
* `get_pacing_status`: ahead/behind/on-track decision branches,
  no-standards error
* `generate_bell_ringer`: default date (today), past-lesson
  fallback, no-recent-lessons error
* `generate_exit_ticket`: no-lesson-no-topic error, vocab fallback
  via standards
* `suggest_grouping`: no-rows error, assignment filter, no-matching
  data error
* `generate_sub_plans`: missing-date error, no-lesson scheduled,
  ImportError fallback (no doc generator)

Per dual-rate-limit precedent (PRs #269/#270/#290+): test-only PR
merging on green CI when both Codex (until 2026-05-12) and Gemini
(quota exhausted) unavailable.
"""
from __future__ import annotations

import json
import os
from unittest.mock import patch, MagicMock

import pytest


MODULE = "backend.services.assistant_tools_planning"


# ──────────────────────────────────────────────────────────────────
# _get_standards_for_lesson
# ──────────────────────────────────────────────────────────────────


class TestGetStandardsForLesson:
    def test_no_lesson_returns_none(self):
        from backend.services.assistant_tools_planning import (
            _get_standards_for_lesson,
        )
        assert _get_standards_for_lesson(None) is None

    def test_no_lesson_file_returns_basic_dict(self):
        from backend.services.assistant_tools_planning import (
            _get_standards_for_lesson,
        )
        result = _get_standards_for_lesson({"lesson_title": "Intro"})
        assert result == {"title": "Intro", "vocab": [], "standards": []}

    def test_missing_lesson_file_returns_basic_dict(self, tmp_path):
        from backend.services import assistant_tools_planning as mod
        with patch.object(mod, "LESSONS_DIR", str(tmp_path)):
            result = mod._get_standards_for_lesson({
                "lesson_title": "T",
                "lesson_file": "Unit1/missing.json",
            })
        assert result == {"title": "T", "vocab": [], "standards": []}

    def test_full_happy_path(self, tmp_path):
        from backend.services import assistant_tools_planning as mod

        unit_dir = tmp_path / "Unit1"
        unit_dir.mkdir()
        lesson_data = {
            "title": "Bill of Rights",
            "vocabulary": ["amendment", "ratify"],
            "standards": ["SS.7.C.3.6"],
            "objectives": ["Understand amendments"],
            "days": [
                {"day": 1, "topic": "Intro to amendments"},
                {"day": 2, "topic": "Application"},
            ],
        }
        (unit_dir / "lesson.json").write_text(json.dumps(lesson_data))

        with patch.object(mod, "LESSONS_DIR", str(tmp_path)):
            result = mod._get_standards_for_lesson({
                "lesson_title": "fallback",
                "lesson_file": "Unit1/lesson.json",
            })
        assert result["title"] == "Bill of Rights"
        assert result["vocab"] == ["amendment", "ratify"]
        assert result["standards"] == ["SS.7.C.3.6"]
        assert result["objectives"] == ["Understand amendments"]
        assert "Intro to amendments" in result["topics"]

    def test_corrupt_lesson_file_swallows_exception(self, tmp_path):
        from backend.services import assistant_tools_planning as mod

        (tmp_path / "bad.json").write_text("{not valid json")
        with patch.object(mod, "LESSONS_DIR", str(tmp_path)):
            result = mod._get_standards_for_lesson({
                "lesson_title": "Bad",
                "lesson_file": "bad.json",
            })
        # Exception swallowed → returns basic dict
        assert result == {"title": "Bad", "vocab": [], "standards": []}


# ──────────────────────────────────────────────────────────────────
# suggest_remediation - error + branch paths
# ──────────────────────────────────────────────────────────────────


class TestSuggestRemediationBranches:
    def test_no_rows_returns_error(self):
        from backend.services.assistant_tools_planning import (
            suggest_remediation,
        )
        with patch(f"{MODULE}._load_settings",
                   return_value={"config": {"availableTools": []}}), \
             patch(f"{MODULE}._load_master_csv", return_value=[]):
            result = suggest_remediation(teacher_id="t")
        assert "error" in result
        assert "No grade data" in result["error"]

    def test_no_weak_areas_returns_success_message(self):
        # All categories average >= 75 → no weak areas → success message
        from backend.services.assistant_tools_planning import (
            suggest_remediation,
        )
        rows = [
            {"assignment": "Q1", "content": 80, "completeness": 85,
             "writing": 90, "effort": 88},
            {"assignment": "Q2", "content": 82, "completeness": 87,
             "writing": 92, "effort": 89},
        ]
        with patch(f"{MODULE}._load_settings",
                   return_value={"config": {"availableTools": []}}), \
             patch(f"{MODULE}._load_master_csv", return_value=rows):
            result = suggest_remediation(teacher_id="t")
        assert "message" in result
        assert "performing well" in result["message"]

    def test_writing_weakness_suggests_worksheet(self):
        from backend.services.assistant_tools_planning import (
            suggest_remediation,
        )
        with patch(f"{MODULE}._load_settings",
                   return_value={"config": {"availableTools": []}}), \
             patch(f"{MODULE}._load_master_csv",
                   return_value=[{"assignment": "Q",
                                  "content": 80, "completeness": 80,
                                  "writing": 50, "effort": 80}]):
            result = suggest_remediation(teacher_id="t")
        # Writing weakness → generate_worksheet activity
        wri_block = next(s for s in result["suggestions"]
                         if "writing" in s["weakness"].lower())
        tools = [a["tool"] for a in wri_block["activities"]]
        assert "generate_worksheet" in tools

    def test_completeness_weakness_suggests_grouping(self):
        from backend.services.assistant_tools_planning import (
            suggest_remediation,
        )
        with patch(f"{MODULE}._load_settings",
                   return_value={"config": {"availableTools": []}}), \
             patch(f"{MODULE}._load_master_csv",
                   return_value=[{"assignment": "Q",
                                  "content": 80, "completeness": 40,
                                  "writing": 80, "effort": 80}]):
            result = suggest_remediation(teacher_id="t")
        comp_block = next(s for s in result["suggestions"]
                          if "completeness" in s["weakness"].lower())
        tools = [a["tool"] for a in comp_block["activities"]]
        assert "suggest_grouping" in tools

    def test_effort_weakness_suggests_gamified_tools(self):
        from backend.services.assistant_tools_planning import (
            suggest_remediation,
        )
        with patch(f"{MODULE}._load_settings",
                   return_value={"config": {
                       "availableTools": ["gimkit", "kahoot"]}}), \
             patch(f"{MODULE}._load_master_csv",
                   return_value=[{"assignment": "Q",
                                  "content": 80, "completeness": 80,
                                  "writing": 80, "effort": 50}]):
            result = suggest_remediation(teacher_id="t")
        effort_block = next(s for s in result["suggestions"]
                            if "effort" in s["weakness"].lower())
        descs = [a["description"] for a in effort_block["activities"]]
        assert any("Gimkit" in d or "Kahoot" in d for d in descs)


# ──────────────────────────────────────────────────────────────────
# align_to_standards - error paths
# ──────────────────────────────────────────────────────────────────


class TestAlignToStandardsErrors:
    def test_no_standards_returns_error(self):
        from backend.services.assistant_tools_planning import (
            align_to_standards,
        )
        with patch(f"{MODULE}._load_standards", return_value=[]):
            result = align_to_standards("constitution", teacher_id="t")
        assert "error" in result
        assert "No standards" in result["error"]


# ──────────────────────────────────────────────────────────────────
# get_pacing_status - all 3 status branches + error path
# ──────────────────────────────────────────────────────────────────


class TestGetPacingStatusBranches:
    def test_no_standards_returns_error(self):
        from backend.services.assistant_tools_planning import (
            get_pacing_status,
        )
        with patch(f"{MODULE}._load_standards", return_value=[]):
            result = get_pacing_status(teacher_id="t")
        assert "error" in result

    def test_ahead_when_pct_standards_above_pct_time(self):
        # 9 of 10 standards covered, but only 5 of 34 calendar days
        # done → pct_standards (90%) >> pct_time (14.7%) → ahead.
        # datetime.now() is frozen so future dates stay future regardless
        # of when the test runs (no timebomb).
        from datetime import datetime as _dt
        from backend.services.assistant_tools_planning import (
            get_pacing_status,
        )

        standards = [{"code": f"S.{i}"} for i in range(10)]
        past = [
            {"date": "2026-01-01", "lesson_title": "L1"},
            {"date": "2026-01-02", "lesson_title": "L2"},
            {"date": "2026-01-03", "lesson_title": "L3"},
            {"date": "2026-01-04", "lesson_title": "L4"},
            {"date": "2026-01-05", "lesson_title": "L5"},
        ]
        future = [
            {"date": f"2026-06-{i:02d}", "lesson_title": f"F{i}"}
            for i in range(1, 30)
        ]

        def mock_for_lesson(lesson):
            idx = int(lesson["lesson_title"][1:])
            return {"standards": [f"S.{idx*2-2}", f"S.{idx*2-1}"]}

        with patch(f"{MODULE}._load_standards", return_value=standards), \
             patch(f"{MODULE}._load_calendar",
                   return_value={"scheduled_lessons": past + future}), \
             patch(f"{MODULE}._load_settings",
                   return_value={"config": {}}), \
             patch(f"{MODULE}._get_standards_for_lesson",
                   side_effect=mock_for_lesson), \
             patch(f"{MODULE}.datetime") as mock_dt:
            mock_dt.now.return_value = _dt(2026, 3, 1)
            result = get_pacing_status(teacher_id="t")
        assert result["status"] == "ahead"

    def test_behind_when_pct_standards_below_pct_time(self):
        # 10 standards, past lessons cover only 1 — and we're 90%
        # through the calendar → behind.
        from datetime import datetime as _dt
        from backend.services.assistant_tools_planning import (
            get_pacing_status,
        )

        standards = [{"code": f"S.{i}"} for i in range(10)]
        past = [
            {"date": "2026-01-01", "lesson_title": "L1"},
        ] * 9
        future = [
            {"date": "2026-06-01", "lesson_title": "F1"},
        ]

        with patch(f"{MODULE}._load_standards", return_value=standards), \
             patch(f"{MODULE}._load_calendar",
                   return_value={"scheduled_lessons": past + future}), \
             patch(f"{MODULE}._load_settings",
                   return_value={"config": {}}), \
             patch(f"{MODULE}._get_standards_for_lesson",
                   return_value={"standards": ["S.0"]}), \
             patch(f"{MODULE}.datetime") as mock_dt:
            mock_dt.now.return_value = _dt(2026, 3, 1)
            result = get_pacing_status(teacher_id="t")
        assert result["status"] == "behind"

    def test_no_scheduled_lessons_pct_time_zero(self):
        # days_scheduled == 0 path → pct_time = 0
        from backend.services.assistant_tools_planning import (
            get_pacing_status,
        )

        standards = [{"code": "S.0"}]
        with patch(f"{MODULE}._load_standards", return_value=standards), \
             patch(f"{MODULE}._load_calendar",
                   return_value={"scheduled_lessons": []}), \
             patch(f"{MODULE}._load_settings",
                   return_value={"config": {}}):
            result = get_pacing_status(teacher_id="t")
        assert result["pct_calendar_elapsed"] == 0


# ──────────────────────────────────────────────────────────────────
# generate_bell_ringer - default date + past lesson fallback
# ──────────────────────────────────────────────────────────────────


class TestGenerateBellRingerBranches:
    def test_no_recent_lessons_returns_error(self):
        from backend.services.assistant_tools_planning import (
            generate_bell_ringer,
        )
        with patch(f"{MODULE}._load_calendar",
                   return_value={"scheduled_lessons": []}):
            result = generate_bell_ringer(date="2026-05-10", teacher_id="t")
        assert "error" in result
        assert "No recent lessons" in result["error"]

    def test_default_date_uses_today(self):
        from backend.services.assistant_tools_planning import (
            generate_bell_ringer,
        )
        # No specific lesson, just exercise the default-date path
        with patch(f"{MODULE}._load_calendar",
                   return_value={"scheduled_lessons": [
                       {"date": "1999-01-01", "lesson_title": "Old",
                        "lesson_file": ""},
                   ]}), \
             patch(f"{MODULE}._load_standards", return_value=[]):
            result = generate_bell_ringer(teacher_id="t")
        # Past-lesson fallback found "Old"
        assert "error" not in result
        assert result["source_lesson"] == "Old"

    def test_uses_yesterday_lesson_when_present(self):
        from backend.services.assistant_tools_planning import (
            generate_bell_ringer,
        )
        with patch(f"{MODULE}._load_calendar",
                   return_value={"scheduled_lessons": [
                       {"date": "2026-05-09", "lesson_title": "Yesterday's"},
                   ]}), \
             patch(f"{MODULE}._load_standards", return_value=[]):
            result = generate_bell_ringer(date="2026-05-10", teacher_id="t")
        assert result["source_lesson"] == "Yesterday's"


# ──────────────────────────────────────────────────────────────────
# generate_exit_ticket - no-lesson + vocab branches
# ──────────────────────────────────────────────────────────────────


class TestGenerateExitTicketBranches:
    def test_no_lesson_no_topic_returns_error(self):
        from backend.services.assistant_tools_planning import (
            generate_exit_ticket,
        )
        with patch(f"{MODULE}._load_calendar",
                   return_value={"scheduled_lessons": []}), \
             patch(f"{MODULE}._load_standards", return_value=[]):
            result = generate_exit_ticket(date="2026-05-10", teacher_id="t")
        assert "error" in result
        assert "No lesson scheduled" in result["error"]

    def test_vocab_falls_back_to_standards_vocab(self):
        # Lesson has no vocab → falls back to matching standards' vocab
        from backend.services.assistant_tools_planning import (
            generate_exit_ticket,
        )
        with patch(f"{MODULE}._load_calendar",
                   return_value={"scheduled_lessons": []}), \
             patch(f"{MODULE}._load_standards",
                   return_value=[
                       {"code": "S.1", "benchmark": "constitution stuff",
                        "vocabulary": ["amendment"],
                        "essential_questions": ["Why amendments?"]},
                   ]):
            result = generate_exit_ticket(
                topic="constitution", teacher_id="t",
            )
        assert "error" not in result
        questions = result["questions"]
        # At least 1 question should reference vocab
        assert any("amendment" in q["question"].lower()
                   for q in questions)

    def test_default_date_uses_today(self):
        from backend.services.assistant_tools_planning import (
            generate_exit_ticket,
        )
        with patch(f"{MODULE}._load_calendar",
                   return_value={"scheduled_lessons": []}), \
             patch(f"{MODULE}._load_standards",
                   return_value=[
                       {"code": "S.1", "benchmark": "x", "vocabulary": [],
                        "essential_questions": []},
                   ]):
            # No date specified → uses today
            result = generate_exit_ticket(topic="x", teacher_id="t")
        assert "error" not in result


# ──────────────────────────────────────────────────────────────────
# suggest_grouping - error + filter paths
# ──────────────────────────────────────────────────────────────────


class TestSuggestGroupingBranches:
    def test_no_rows_returns_error(self):
        from backend.services.assistant_tools_planning import (
            suggest_grouping,
        )
        with patch(f"{MODULE}._load_master_csv", return_value=[]):
            result = suggest_grouping(
                period="P1", group_type="heterogeneous", teacher_id="t",
            )
        assert "error" in result
        assert "No grade data" in result["error"]

    def test_assignment_filter_excludes_non_matches(self):
        from backend.services.assistant_tools_planning import (
            suggest_grouping,
        )
        rows = [
            {"student_name": "Alice", "score": 90, "assignment": "Quiz"},
            {"student_name": "Bob", "score": 80, "assignment": "Quiz"},
            {"student_name": "Carol", "score": 70, "assignment": "Other"},
        ]
        with patch(f"{MODULE}._load_master_csv", return_value=rows):
            result = suggest_grouping(
                period="P1", group_type="homogeneous",
                assignment_name="Quiz", group_size=2, teacher_id="t",
            )
        # Only Alice + Bob (Quiz match) → 1 group of 2
        assert result["total_students"] == 2
        names = []
        for g in result["groups"]:
            names.extend(m["student"] for m in g["members"])
        assert "Carol" not in names

    def test_assignment_filter_no_matches_returns_error(self):
        from backend.services.assistant_tools_planning import (
            suggest_grouping,
        )
        rows = [
            {"student_name": "Alice", "score": 90, "assignment": "Other"},
        ]
        with patch(f"{MODULE}._load_master_csv", return_value=rows):
            result = suggest_grouping(
                period="P1", group_type="heterogeneous",
                assignment_name="Quiz", teacher_id="t",
            )
        assert "error" in result
        assert "No matching grade data" in result["error"]


# ──────────────────────────────────────────────────────────────────
# generate_sub_plans - error + ImportError fallback
# ──────────────────────────────────────────────────────────────────


class TestGenerateSubPlansBranches:
    def test_missing_date_returns_error(self):
        from backend.services.assistant_tools_planning import (
            generate_sub_plans,
        )
        result = generate_sub_plans(date="", teacher_id="t")
        assert "error" in result

    def test_no_lesson_for_date_includes_note(self):
        from backend.services.assistant_tools_planning import (
            generate_sub_plans,
        )
        with patch(f"{MODULE}._load_calendar",
                   return_value={"scheduled_lessons": [],
                                 "holidays": []}), \
             patch(f"{MODULE}._load_settings",
                   return_value={"config": {"teacher_name": "Mr X",
                                            "subject": "Civics",
                                            "school_name": "S"}}), \
             patch("backend.services.document_generator.generate_document",
                   return_value={"document": "X", "filename": "f.docx"}):
            # Single weekday with no lesson
            result = generate_sub_plans(date="2026-05-11", teacher_id="t")
        # daily_plans key should be present (with the no-lesson plan)
        assert "daily_plans" in result
        no_lesson = next(p for p in result["daily_plans"]
                         if p.get("note"))
        assert "Plan independent" in no_lesson["note"]

    def test_doc_generator_import_error_falls_back(self):
        from backend.services.assistant_tools_planning import (
            generate_sub_plans,
        )
        with patch(f"{MODULE}._load_calendar",
                   return_value={"scheduled_lessons": [],
                                 "holidays": []}), \
             patch(f"{MODULE}._load_settings",
                   return_value={"config": {"teacher_name": "T",
                                            "subject": "X",
                                            "school_name": "S"}}), \
             patch.dict("sys.modules",
                        {"backend.services.document_generator": None}):
            result = generate_sub_plans(date="2026-05-11", teacher_id="t")
        # ImportError → structured fallback dict
        assert "teacher" in result
        assert "daily_plans" in result
        assert "document generator not available" in result["message"]

    def test_holiday_skips_day(self):
        from backend.services.assistant_tools_planning import (
            generate_sub_plans,
        )
        with patch(f"{MODULE}._load_calendar",
                   return_value={
                       "scheduled_lessons": [],
                       "holidays": [
                           {"date": "2026-05-11", "name": "Holiday X"},
                       ],
                   }), \
             patch(f"{MODULE}._load_settings",
                   return_value={"config": {}}), \
             patch("backend.services.document_generator.generate_document",
                   return_value={"document": "x", "filename": "f.docx"}):
            result = generate_sub_plans(
                date="2026-05-11", end_date="2026-05-11", teacher_id="t",
            )
        holidays = [p for p in result["daily_plans"] if p.get("holiday")]
        assert len(holidays) == 1
        assert holidays[0]["holiday"] == "Holiday X"

    def test_full_pipeline_with_lesson_data(self):
        from backend.services.assistant_tools_planning import (
            generate_sub_plans,
        )
        with patch(f"{MODULE}._load_calendar",
                   return_value={
                       "scheduled_lessons": [
                           {"date": "2026-05-11", "lesson_title": "L1",
                            "unit": "Unit 1", "day_number": 1,
                            "lesson_file": ""},
                       ],
                       "holidays": [],
                   }), \
             patch(f"{MODULE}._load_settings",
                   return_value={"config": {"teacher_name": "T",
                                            "subject": "Civics",
                                            "school_name": "S"}}), \
             patch(f"{MODULE}._get_standards_for_lesson",
                   return_value={"objectives": ["o1", "o2"],
                                 "vocab": ["v1"], "topics": []}), \
             patch("backend.services.document_generator.generate_document",
                   return_value={"document": "x", "filename": "f.docx"}):
            result = generate_sub_plans(
                date="2026-05-11", end_date="2026-05-11", teacher_id="t",
            )
        # Daily plan has objectives + vocabulary
        plan = next(p for p in result["daily_plans"]
                    if p.get("lesson_title") == "L1")
        assert plan["objectives"] == ["o1", "o2"]
        assert plan["vocabulary"] == ["v1"]
