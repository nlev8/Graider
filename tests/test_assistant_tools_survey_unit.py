"""Unit tests for backend/services/assistant_tools_survey.py.

Audit MAJOR #4 sprint follow-up to PR #267. Targets 74 uncovered LOC
(15% baseline).

Strategy
--------
Three public functions, all Supabase-backed:
  1. `create_parent_survey` — generates a unique 6-char join code (loops on
     collision), then inserts a row in `published_assessments`.
  2. `get_survey_results` — selects single survey (with join_code) or lists
     all teacher's surveys, computes per-question rating/text aggregations.
  3. `compile_survey_report` — runs `get_survey_results` then builds a
     markdown report with star distributions and overall average.

A chainable `_make_supabase` helper returns a fresh `_Chain` per `.table()`
call. The chain absorbs `.select/.eq/.order/.insert/.update` and pops the
next pre-scripted response from a queue on `.execute()`. Insert payloads
are recorded for assertion.

`TestTeacherIdRequired` pins every public tool invokes `require_teacher_id`.
`TestExports` pins `SURVEY_TOOL_DEFINITIONS` ↔ `SURVEY_TOOL_HANDLERS` parity.

Per `feedback_codex_always_high_effort.md` standing directive, the Codex
review will use high effort.
"""
from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest


# ──────────────────────────────────────────────────────────────────
# _get_supabase — thin wrapper
# ──────────────────────────────────────────────────────────────────


class TestGetSupabase:
    def test_delegates_to_get_supabase_or_raise(self):
        # Production wrapper just lazy-imports + calls
        # backend.supabase_client.get_supabase_or_raise. Patch the underlying
        # to return a sentinel and confirm passthrough.
        from backend.services import assistant_tools_survey as mod

        sentinel = object()
        with patch("backend.supabase_client.get_supabase_or_raise",
                   return_value=sentinel) as mock:
            result = mod._get_supabase()
        assert result is sentinel
        mock.assert_called_once_with()


# ──────────────────────────────────────────────────────────────────
# Supabase mock factory
# ──────────────────────────────────────────────────────────────────


def _make_supabase(execute_returns=None):
    """Build a chainable Supabase mock.

    Args:
        execute_returns: list of `.data` values, returned in order from
            successive `.execute()` calls.

    Returns:
        (db_mock, insert_payloads_list, table_names_list, chains_list).

    Each `_Chain` instance records `.filters` (list of (key, val) tuples
    from `.eq()` calls) and `.actions` (list of method-call labels). This
    lets tests pin tenant-scoping like `assert ('teacher_id', 't') in
    chains[0].filters` — without that, a regression that drops the
    `.eq('teacher_id', ...)` filter would silently leak cross-tenant rows.
    """
    insert_payloads: list = []
    table_names: list = []
    chains: list = []
    queue: list = list(execute_returns or [])

    class _Chain:
        def __init__(self):
            self._action = None
            self._payload = None
            self.filters: list = []
            self.actions: list = []

        def select(self, *_a, **_kw):
            self._action = "select"
            self.actions.append("select")
            return self

        def order(self, *_a, **_kw):
            self.actions.append("order")
            return self

        def eq(self, key, val):
            # PR #268 Codex round-1 MAJOR fold: record filter args so tests
            # can pin tenant-scoping. The old `*_a, **_kw` swallow made
            # filter regressions invisible to the suite.
            self.filters.append((key, val))
            self.actions.append(("eq", key, val))
            return self

        def insert(self, payload, **_kw):
            self._action = "insert"
            self._payload = payload
            self.actions.append("insert")
            return self

        def update(self, payload, **_kw):
            self._action = "update"
            self._payload = payload
            self.actions.append("update")
            return self

        def execute(self):
            if self._action == "insert":
                insert_payloads.append(self._payload)
            data = queue.pop(0) if queue else []
            result = MagicMock()
            result.data = data
            return result

    db = MagicMock()

    def _table(name):
        table_names.append(name)
        chain = _Chain()
        chains.append(chain)
        return chain

    db.table.side_effect = _table
    return db, insert_payloads, table_names, chains


# ──────────────────────────────────────────────────────────────────
# create_parent_survey
# ──────────────────────────────────────────────────────────────────


class TestCreateParentSurvey:
    def test_default_title_and_questions_used_when_none(self):
        from backend.services.assistant_tools_survey import (
            create_parent_survey, DEFAULT_QUESTIONS,
        )

        db, payloads, _tbls, _chains = _make_supabase(execute_returns=[
            [],   # collision-check returns empty → break loop
            [],   # insert call
        ])
        with patch("backend.services.assistant_tools_survey._get_supabase",
                   return_value=db):
            result = create_parent_survey(teacher_id="teach-1")

        assert result["status"] == "success"
        assert len(payloads) == 1
        payload = payloads[0]
        assert payload["title"] == "Parent Communication Survey"
        assert payload["teacher_name"] == "Teacher"
        assert payload["assessment"]["questions"] == DEFAULT_QUESTIONS

    def test_custom_title_and_questions_passed_through(self):
        from backend.services.assistant_tools_survey import create_parent_survey

        db, payloads, _, _chains = _make_supabase(execute_returns=[[], []])
        custom_questions = [
            {"id": "q1", "text": "Custom?", "type": "rating"},
        ]
        with patch("backend.services.assistant_tools_survey._get_supabase",
                   return_value=db):
            result = create_parent_survey(
                title="My Survey",
                teacher_name="Mrs. Smith",
                questions=custom_questions,
                teacher_id="teach-1",
            )
        assert result["status"] == "success"
        assert payloads[0]["title"] == "My Survey"
        assert payloads[0]["teacher_name"] == "Mrs. Smith"
        assert payloads[0]["assessment"]["questions"] == custom_questions

    def test_join_code_collision_retries(self):
        # First select returns 1 record (collision), second returns empty.
        from backend.services.assistant_tools_survey import create_parent_survey

        db, payloads, _, _chains = _make_supabase(execute_returns=[
            [{"id": "preexisting"}],  # collision
            [],                        # clear
            [],                        # insert
        ])
        with patch("backend.services.assistant_tools_survey._get_supabase",
                   return_value=db), \
             patch("backend.services.assistant_tools_survey.random.choices",
                   side_effect=[
                       list("AAAAAA"),  # first attempt — collides
                       list("BBBBBB"),  # second attempt — clear
                   ]):
            result = create_parent_survey(teacher_id="teach-1")
        # Loop terminates after the second attempt
        assert result["join_code"] == "BBBBBB"
        # Only one insert (after the loop exits)
        assert len(payloads) == 1
        assert payloads[0]["join_code"] == "BBBBBB"

    def test_payload_structure_complete(self):
        from backend.services.assistant_tools_survey import create_parent_survey

        db, payloads, _, _chains = _make_supabase(execute_returns=[[], []])
        with patch("backend.services.assistant_tools_survey._get_supabase",
                   return_value=db):
            create_parent_survey(teacher_id="teach-tenant-9")
        p = payloads[0]
        assert p["teacher_id"] == "teach-tenant-9"
        assert p["assessment"]["content_type"] == "survey"
        assert p["assessment"]["responses"] == []
        assert p["settings"]["content_type"] == "survey"
        assert p["is_active"] is True
        assert p["submission_count"] == 0
        # Join code is 6 chars from the allowed alphabet
        assert len(p["join_code"]) == 6
        for c in p["join_code"]:
            assert c in "ABCDEFGHJKMNPQRSTUVWXYZ23456789", (
                f"Bad join-code char {c!r}"
            )

    def test_returns_url_and_message_with_question_count(self):
        from backend.services.assistant_tools_survey import create_parent_survey

        db, payloads, _, _chains = _make_supabase(execute_returns=[[], []])
        questions = [{"id": "a", "text": "?", "type": "rating"}] * 7
        with patch("backend.services.assistant_tools_survey._get_supabase",
                   return_value=db):
            result = create_parent_survey(
                questions=questions, teacher_id="teach-1",
            )
        code = result["join_code"]
        assert result["survey_url"] == f"/survey/{code}"
        assert "7 questions" in result["message"]
        assert "anonymous" in result["message"]
        assert code in result["message"]

    def test_table_name_is_published_assessments(self):
        from backend.services.assistant_tools_survey import create_parent_survey

        db, _payloads, table_names, _chains = _make_supabase(execute_returns=[[], []])
        with patch("backend.services.assistant_tools_survey._get_supabase",
                   return_value=db):
            create_parent_survey(teacher_id="teach-1")
        # Both the collision-check select and the insert hit the same table
        assert all(t == "published_assessments" for t in table_names)


# ──────────────────────────────────────────────────────────────────
# get_survey_results
# ──────────────────────────────────────────────────────────────────


def _survey_record(*, join_code="ABC123", title="Survey", responses=None,
                   questions=None, content_type="survey",
                   created_at="2026-05-01"):
    """Helper to build a `published_assessments` row matching production shape."""
    return {
        "join_code": join_code,
        "title": title,
        "submission_count": len(responses or []),
        "created_at": created_at,
        "assessment": {
            "content_type": content_type,
            "questions": questions or [],
            "responses": responses or [],
        },
    }


class TestGetSurveyResults:
    def test_no_data_returns_error(self):
        from backend.services.assistant_tools_survey import get_survey_results

        db, _, _, _chains = _make_supabase(execute_returns=[[]])
        with patch("backend.services.assistant_tools_survey._get_supabase",
                   return_value=db):
            result = get_survey_results(
                join_code="ABC123", teacher_id="teach-1",
            )
        assert result == {"error": "No surveys found"}

    def test_with_join_code_returns_single_survey(self):
        from backend.services.assistant_tools_survey import get_survey_results

        record = _survey_record(
            join_code="XY1234",
            title="Spring Feedback",
            questions=[
                {"id": "comm", "text": "Communication?", "type": "rating"},
            ],
            responses=[{"comm": 5}, {"comm": 4}, {"comm": 3}],
        )
        db, _, _, _chains = _make_supabase(execute_returns=[[record]])
        with patch("backend.services.assistant_tools_survey._get_supabase",
                   return_value=db):
            result = get_survey_results(
                join_code="XY1234", teacher_id="teach-1",
            )
        # Single-survey shape (no `surveys` wrapper)
        assert result["join_code"] == "XY1234"
        assert result["title"] == "Spring Feedback"
        assert result["total_responses"] == 3

    def test_without_join_code_returns_surveys_list(self):
        from backend.services.assistant_tools_survey import get_survey_results

        records = [
            _survey_record(join_code="A1", title="S1"),
            _survey_record(join_code="B2", title="S2"),
        ]
        db, _, _, _chains = _make_supabase(execute_returns=[records])
        with patch("backend.services.assistant_tools_survey._get_supabase",
                   return_value=db):
            result = get_survey_results(teacher_id="teach-1")
        assert "surveys" in result
        assert len(result["surveys"]) == 2
        assert result["surveys"][0]["join_code"] == "A1"
        assert result["surveys"][1]["join_code"] == "B2"

    def test_skips_non_survey_records(self):
        from backend.services.assistant_tools_survey import get_survey_results

        records = [
            _survey_record(join_code="A1", title="ActualSurvey"),
            _survey_record(join_code="B2", title="AssessmentRow",
                           content_type="assessment"),
        ]
        db, _, _, _chains = _make_supabase(execute_returns=[records])
        with patch("backend.services.assistant_tools_survey._get_supabase",
                   return_value=db):
            result = get_survey_results(teacher_id="teach-1")
        # Only the survey record should appear
        assert len(result["surveys"]) == 1
        assert result["surveys"][0]["join_code"] == "A1"

    def test_rating_question_summary(self):
        from backend.services.assistant_tools_survey import get_survey_results

        record = _survey_record(
            questions=[{"id": "q1", "text": "How good?", "type": "rating"}],
            responses=[
                {"q1": 5}, {"q1": 5}, {"q1": 4}, {"q1": 3}, {"q1": 1},
            ],
        )
        db, _, _, _chains = _make_supabase(execute_returns=[[record]])
        with patch("backend.services.assistant_tools_survey._get_supabase",
                   return_value=db):
            result = get_survey_results(
                join_code="ABC123", teacher_id="teach-1",
            )
        q1 = result["questions"]["q1"]
        assert q1["type"] == "rating"
        assert q1["count"] == 5
        # avg = (5+5+4+3+1)/5 = 3.6
        assert q1["average"] == 3.6
        # Distribution covers ranges 1..5
        assert q1["distribution"] == {
            "1": 1, "2": 0, "3": 1, "4": 1, "5": 2,
        }

    def test_rating_question_with_no_responses_avg_is_zero(self):
        from backend.services.assistant_tools_survey import get_survey_results

        record = _survey_record(
            questions=[{"id": "q1", "text": "?", "type": "rating"}],
            responses=[],
        )
        db, _, _, _chains = _make_supabase(execute_returns=[[record]])
        with patch("backend.services.assistant_tools_survey._get_supabase",
                   return_value=db):
            result = get_survey_results(
                join_code="ABC123", teacher_id="teach-1",
            )
        q1 = result["questions"]["q1"]
        assert q1["count"] == 0
        assert q1["average"] == 0  # divide-by-zero guard

    def test_rating_skips_responses_missing_qid(self):
        from backend.services.assistant_tools_survey import get_survey_results

        record = _survey_record(
            questions=[{"id": "rating1", "text": "?", "type": "rating"}],
            # Some responses don't have rating1 — should be skipped from avg
            responses=[
                {"rating1": 5},
                {"other_key": "ignored"},
                {"rating1": 3},
            ],
        )
        db, _, _, _chains = _make_supabase(execute_returns=[[record]])
        with patch("backend.services.assistant_tools_survey._get_supabase",
                   return_value=db):
            result = get_survey_results(
                join_code="ABC123", teacher_id="teach-1",
            )
        q = result["questions"]["rating1"]
        assert q["count"] == 2
        assert q["average"] == 4.0

    def test_text_question_summary(self):
        from backend.services.assistant_tools_survey import get_survey_results

        record = _survey_record(
            questions=[{"id": "feedback", "text": "Anything?", "type": "text"}],
            responses=[
                {"feedback": "Great teacher"},
                {"feedback": "Communicates well"},
                {"other_key": "no feedback here"},  # filtered out
                {"feedback": ""},  # truthy filter drops empty strings
            ],
        )
        db, _, _, _chains = _make_supabase(execute_returns=[[record]])
        with patch("backend.services.assistant_tools_survey._get_supabase",
                   return_value=db):
            result = get_survey_results(
                join_code="ABC123", teacher_id="teach-1",
            )
        q = result["questions"]["feedback"]
        assert q["type"] == "text"
        assert q["count"] == 2
        assert q["responses"] == ["Great teacher", "Communicates well"]

    def test_join_code_path_scopes_query_by_join_code_AND_teacher_id(self):
        # PR #268 Codex round-1 MAJOR fold: pin tenant scoping. A regression
        # that drops `.eq('teacher_id', teacher_id)` from production at
        # backend/services/assistant_tools_survey.py:103 would have leaked
        # cross-tenant survey rows. The previous `_Chain.eq(*_a, **_kw)`
        # swallowed all filter args, making this regression invisible.
        from backend.services.assistant_tools_survey import get_survey_results

        record = _survey_record()
        db, _, _, chains = _make_supabase(execute_returns=[[record]])
        with patch("backend.services.assistant_tools_survey._get_supabase",
                   return_value=db):
            get_survey_results(join_code="ABC123", teacher_id="teach-X")

        # Single .table() call → single chain → both filters present
        assert len(chains) == 1
        filters = dict(chains[0].filters)
        assert filters.get("join_code") == "ABC123"
        assert filters.get("teacher_id") == "teach-X", (
            "Cross-tenant safety: teacher_id MUST be in the .eq() filters"
        )

    def test_list_path_scopes_query_by_teacher_id_and_content_type(self):
        # The no-join-code path must filter by teacher_id AND content_type so
        # the teacher only sees their own SURVEY records (not assessments).
        from backend.services.assistant_tools_survey import get_survey_results

        db, _, _, chains = _make_supabase(execute_returns=[[]])
        with patch("backend.services.assistant_tools_survey._get_supabase",
                   return_value=db):
            get_survey_results(teacher_id="teach-Y")

        assert len(chains) == 1
        filters = dict(chains[0].filters)
        assert filters.get("teacher_id") == "teach-Y", (
            "Cross-tenant safety: teacher_id filter required on list path"
        )
        assert filters.get("settings->>content_type") == "survey", (
            "List path must scope to survey content_type"
        )

    def test_join_code_matching_non_survey_record_returns_error(self):
        # PR #268 Codex round-1 MINOR fold + Rule #11 production fix:
        # If a join_code matches a row that ISN'T a survey (e.g., an
        # assessment with the same code under a different content_type),
        # the filter loop at viz.py:120-121 leaves `surveys` empty.
        # Previously fell through to `{"surveys": []}` → callers like
        # compile_survey_report then built "Survey 'None' has no responses
        # yet" reports about a code that doesn't actually exist as a
        # survey. Now returns the error path.
        from backend.services.assistant_tools_survey import get_survey_results

        # The DB returns a row but its content_type is "assessment", not "survey"
        non_survey = _survey_record(
            join_code="LOST01",
            content_type="assessment",
        )
        db, _, _, _chains = _make_supabase(execute_returns=[[non_survey]])
        with patch("backend.services.assistant_tools_survey._get_supabase",
                   return_value=db):
            result = get_survey_results(
                join_code="LOST01", teacher_id="teach-1",
            )
        # Error path, not `{"surveys": []}`
        assert result == {"error": "No surveys found"}

    def test_list_path_filters_non_surveys_but_returns_empty_list(self):
        # Symmetric coverage: the no-join_code list path with only
        # non-survey rows should still return `{"surveys": []}` (NOT an
        # error) — the production behavior for a teacher with no surveys
        # yet must remain stable.
        from backend.services.assistant_tools_survey import get_survey_results

        non_surveys = [
            _survey_record(join_code="A1", content_type="assessment"),
            _survey_record(join_code="B2", content_type="assessment"),
        ]
        db, _, _, _chains = _make_supabase(execute_returns=[non_surveys])
        with patch("backend.services.assistant_tools_survey._get_supabase",
                   return_value=db):
            result = get_survey_results(teacher_id="teach-1")
        # No join_code → empty surveys list (not error)
        assert result == {"surveys": []}


# ──────────────────────────────────────────────────────────────────
# compile_survey_report
# ──────────────────────────────────────────────────────────────────


class TestCompileSurveyReport:
    def test_passes_through_get_survey_results_error(self):
        from backend.services.assistant_tools_survey import compile_survey_report

        db, _, _, _chains = _make_supabase(execute_returns=[[]])  # → "No surveys found"
        with patch("backend.services.assistant_tools_survey._get_supabase",
                   return_value=db):
            result = compile_survey_report(
                join_code="ABC123", teacher_id="teach-1",
            )
        assert result == {"error": "No surveys found"}

    def test_zero_responses_returns_share_message(self):
        from backend.services.assistant_tools_survey import compile_survey_report

        record = _survey_record(
            title="Empty Survey",
            questions=[{"id": "q1", "text": "?", "type": "rating"}],
            responses=[],  # zero responses
        )
        db, _, _, _chains = _make_supabase(execute_returns=[[record]])
        with patch("backend.services.assistant_tools_survey._get_supabase",
                   return_value=db):
            result = compile_survey_report(
                join_code="EMPTY1", teacher_id="teach-1",
            )
        assert "no responses yet" in result["report"]
        assert "Empty Survey" in result["report"]
        assert result["join_code"] == "EMPTY1"
        # Share-link path included so teacher can copy it
        assert "/survey/EMPTY1" in result["report"]

    def test_with_ratings_builds_full_report(self):
        from backend.services.assistant_tools_survey import compile_survey_report

        record = _survey_record(
            title="Final Survey",
            questions=[
                {"id": "comm", "text": "Communication?", "type": "rating"},
                {"id": "supp", "text": "Support?", "type": "rating"},
            ],
            responses=[
                {"comm": 5, "supp": 4},
                {"comm": 5, "supp": 5},
                {"comm": 4, "supp": 4},
            ],
        )
        db, _, _, _chains = _make_supabase(execute_returns=[[record]])
        with patch("backend.services.assistant_tools_survey._get_supabase",
                   return_value=db):
            result = compile_survey_report(
                join_code="FINAL1", teacher_id="teach-1",
            )
        report = result["report"]
        assert "Parent Survey Report: Final Survey" in report
        assert "Total Responses:** 3" in report
        # comm avg = (5+5+4)/3 = 4.7; supp avg = (4+5+4)/3 = 4.3
        assert "Average: 4.7/5.0" in report
        assert "Average: 4.3/5.0" in report
        # Distribution star bars present
        assert "5 star:" in report
        assert "4 star:" in report
        # Overall average = (4.7+4.3)/2 = 4.5
        assert result["overall_average"] == 4.5
        assert result["total_responses"] == 3

    def test_with_text_responses_quotes_each(self):
        from backend.services.assistant_tools_survey import compile_survey_report

        record = _survey_record(
            title="Text Survey",
            questions=[
                {"id": "fb", "text": "Feedback?", "type": "text"},
            ],
            responses=[
                {"fb": "Excellent communication"},
                {"fb": "Very supportive teacher"},
            ],
        )
        db, _, _, _chains = _make_supabase(execute_returns=[[record]])
        with patch("backend.services.assistant_tools_survey._get_supabase",
                   return_value=db):
            result = compile_survey_report(
                join_code="TX1234", teacher_id="teach-1",
            )
        report = result["report"]
        assert "2 written responses" in report
        assert '"Excellent communication"' in report
        assert '"Very supportive teacher"' in report
        # No rating questions, overall_average defaults to 0
        assert result["overall_average"] == 0

    def test_text_section_omitted_when_no_responses(self):
        from backend.services.assistant_tools_survey import compile_survey_report

        record = _survey_record(
            title="No Text Survey",
            questions=[
                {"id": "rating1", "text": "Rate?", "type": "rating"},
                {"id": "fb", "text": "Comments?", "type": "text"},
            ],
            responses=[
                {"rating1": 5},  # no `fb` value
            ],
        )
        db, _, _, _chains = _make_supabase(execute_returns=[[record]])
        with patch("backend.services.assistant_tools_survey._get_supabase",
                   return_value=db):
            result = compile_survey_report(
                join_code="X11111", teacher_id="teach-1",
            )
        report = result["report"]
        # Comments section header should be omitted (responses list is empty)
        assert "Comments?" not in report
        # But the rating section IS rendered
        assert "Rate?" in report

    def test_star_distribution_uses_asterisks(self):
        # Production builds bars with `'*' * count`. Pin the exact count.
        from backend.services.assistant_tools_survey import compile_survey_report

        record = _survey_record(
            title="Bars",
            questions=[{"id": "q", "text": "Q?", "type": "rating"}],
            responses=[
                {"q": 5}, {"q": 5}, {"q": 5},  # 3 fives → 3 asterisks
                {"q": 1},                       # 1 one → 1 asterisk
            ],
        )
        db, _, _, _chains = _make_supabase(execute_returns=[[record]])
        with patch("backend.services.assistant_tools_survey._get_supabase",
                   return_value=db):
            result = compile_survey_report(
                join_code="BAR111", teacher_id="teach-1",
            )
        report = result["report"]
        # 5-star line shows "*** (3)" and 1-star line shows "* (1)"
        assert "5 star: *** (3)" in report
        assert "1 star: * (1)" in report
        # 2-, 3-, 4-star with zero responses still present (empty bar)
        assert "2 star:  (0)" in report
        assert "3 star:  (0)" in report
        assert "4 star:  (0)" in report


# ──────────────────────────────────────────────────────────────────
# require_teacher_id contract
# ──────────────────────────────────────────────────────────────────


class TestTeacherIdRequired:
    """Pin that every public tool actually invokes require_teacher_id().

    Per the assistant_tools_* family pattern, the cross-tenant safety
    contract must run on every tool entry. These tests fail if a future
    change drops the call or moves it after side-effecting work.
    """

    def test_create_parent_survey_calls_require_teacher_id(self):
        from backend.services.assistant_tools_survey import create_parent_survey

        db, _, _, _chains = _make_supabase(execute_returns=[[], []])
        with patch("backend.services.assistant_tools_survey.require_teacher_id") as mock_req, \
             patch("backend.services.assistant_tools_survey._get_supabase",
                   return_value=db):
            create_parent_survey(teacher_id="t")
        mock_req.assert_called_once_with("t")

    def test_get_survey_results_calls_require_teacher_id(self):
        from backend.services.assistant_tools_survey import get_survey_results

        db, _, _, _chains = _make_supabase(execute_returns=[[]])
        with patch("backend.services.assistant_tools_survey.require_teacher_id") as mock_req, \
             patch("backend.services.assistant_tools_survey._get_supabase",
                   return_value=db):
            get_survey_results(teacher_id="t")
        mock_req.assert_called_once_with("t")

    def test_compile_survey_report_calls_require_teacher_id_directly(self):
        # PR #268 Codex round-1 MAJOR fold: the previous test asserted only
        # `call_count >= 1`, which would have passed even if compile's
        # OWN direct require_teacher_id call at viz.py:162 were removed
        # (because get_survey_results delegate also calls it). Patch the
        # delegate to short-circuit so this isolates compile's own call.
        from backend.services.assistant_tools_survey import compile_survey_report

        with patch("backend.services.assistant_tools_survey.require_teacher_id") as mock_req, \
             patch("backend.services.assistant_tools_survey.get_survey_results",
                   return_value={"error": "stubbed"}):
            compile_survey_report(join_code="ABC123", teacher_id="t")
        # With the delegate stubbed, only compile's DIRECT call should fire.
        mock_req.assert_called_once_with("t")


# ──────────────────────────────────────────────────────────────────
# Module-level exports
# ──────────────────────────────────────────────────────────────────


class TestExports:
    def test_tool_definitions_lists_all_three(self):
        from backend.services.assistant_tools_survey import SURVEY_TOOL_DEFINITIONS

        names = {td["name"] for td in SURVEY_TOOL_DEFINITIONS}
        assert names == {
            "create_parent_survey",
            "get_survey_results",
            "compile_survey_report",
        }

    def test_handlers_match_definitions(self):
        from backend.services.assistant_tools_survey import (
            SURVEY_TOOL_DEFINITIONS, SURVEY_TOOL_HANDLERS,
        )
        defined = {td["name"] for td in SURVEY_TOOL_DEFINITIONS}
        handled = set(SURVEY_TOOL_HANDLERS.keys())
        assert defined == handled

    def test_handlers_are_callable(self):
        from backend.services.assistant_tools_survey import SURVEY_TOOL_HANDLERS

        for name, h in SURVEY_TOOL_HANDLERS.items():
            assert callable(h), f"Handler for {name} not callable"

    def test_default_questions_shape(self):
        # Pin the default-questions structure since `create_parent_survey`
        # falls back to it. A regression that drops a required key would
        # leak into every survey.
        from backend.services.assistant_tools_survey import DEFAULT_QUESTIONS

        assert len(DEFAULT_QUESTIONS) >= 4
        for q in DEFAULT_QUESTIONS:
            assert set(q.keys()) >= {"id", "text", "type"}
            assert q["type"] in ("rating", "text")
