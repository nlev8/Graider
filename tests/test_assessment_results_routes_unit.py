"""Unit tests for backend/routes/assessment_results_routes.py.

Audit MAJOR #4 sprint follow-up to PR #293. Companion to existing
tests/test_assessment_results.py which covers the helpers
(_compute_letter_grade + _compute_question_analysis). Targets the
remaining 79 uncovered LOC (55% baseline). Focus: get_assessment_
results endpoint at /api/assessment-results.

Endpoints / branches covered
* No assessments at all — empty list response
* Join-code path: published_assessments.assessment + submissions
  aggregation, content_type filter (skips non-'assessment')
* Class-based path: published_content + student_submissions, expected
  enrollment count, oneroster: prefix stripping, students join row
  fallback for student_id_number
* Audit log failure swallowed
* Per-path query failure swallowed
* Sort by published_at desc across both paths
* Category filter (formative / summative)
* student_id_number fallback when `students` join missing or non-dict

Strategy: minimal Flask test_client + chain-mocked Supabase via the
same FakeChain pattern. get_supabase patched at the route module's
import site. Multi-step flows (PA select → submissions select per
PA; PC select → submissions select + enrolled count + class lookup
per PC) driven via execute_sequence.
"""
from __future__ import annotations

import json
from unittest.mock import patch, MagicMock

import pytest


@pytest.fixture
def client():
    from backend.app import app
    from backend.extensions import limiter
    try:
        limiter.reset()
    except Exception:  # noqa: BLE001  # broad catch: best-effort, failure tolerated
        pass
    with app.test_client() as c:
        yield c


@pytest.fixture
def auth_headers():
    return {"X-Test-Teacher-Id": "teach-1"}


@pytest.fixture(autouse=True)
def dev_env(monkeypatch):
    monkeypatch.setenv("FLASK_ENV", "development")


# ──────────────────────────────────────────────────────────────────
# Chain-mock helper
# ──────────────────────────────────────────────────────────────────


class FakeChain:
    def __init__(self):
        self.calls: list[tuple[str, tuple, dict]] = []

    def _record(self, method, *args, **kwargs):
        self.calls.append((method, args, kwargs))
        return self

    def table(self, *a, **kw): return self._record("table", *a, **kw)
    def select(self, *a, **kw): return self._record("select", *a, **kw)
    def eq(self, *a, **kw): return self._record("eq", *a, **kw)
    def order(self, *a, **kw): return self._record("order", *a, **kw)
    def single(self, *a, **kw): return self._record("single", *a, **kw)
    def execute(self):
        # Replaced by patch_supabase()
        raise NotImplementedError


def patch_supabase(execute_sequence):
    """Patch get_supabase. execute_sequence is a list of MagicMocks
    (or callables) returned by successive .execute() calls."""
    chain = FakeChain()
    seq_iter = iter(execute_sequence)

    def execute_dispatcher():
        chain.calls.append(("execute", (), {}))
        try:
            return next(seq_iter)
        except StopIteration:
            return MagicMock(data=[])

    chain.execute = execute_dispatcher  # type: ignore[assignment]

    sb = MagicMock()
    sb.table.side_effect = chain.table

    p = patch(
        "backend.routes.assessment_results_routes.get_supabase",
        return_value=sb,
    )
    return p, chain


# ──────────────────────────────────────────────────────────────────
# /api/assessment-results
# ──────────────────────────────────────────────────────────────────


class TestAssessmentResults:
    def test_no_assessments_returns_empty(self, client, auth_headers):
        # Two queries fire (PA + PC), both return empty data.
        seq = [
            MagicMock(data=[]),  # published_assessments
            MagicMock(data=[]),  # published_content
        ]
        p, _ = patch_supabase(seq)
        with p:
            resp = client.get(
                "/api/assessment-results", headers=auth_headers,
            )
        assert resp.status_code == 200
        assert resp.get_json() == {"assessments": []}

    def test_join_code_assessment_full_aggregation(
        self, client, auth_headers,
    ):
        # One published_assessment with 2 submissions (one graded, one
        # pending). Confirm stats, letter grades, status, sort.
        pa_row = {
            "id": "pa-1",
            "join_code": "ABC123",
            "title": "Quiz One",
            "is_active": True,
            "created_at": "2026-05-01T10:00:00",
            "settings": {
                "content_type": "assessment",
                "assessment_category": "formative",
                "period": "P3",
            },
            "assessment": {
                "title": "Quiz One",
                "sections": [],
            },
        }
        subs = [
            {
                "student_name": "Alice",
                "student_id": "s1",
                "student_id_number": "ID-1",
                "score": 85,
                "percentage": 85,
                "time_taken_seconds": 600,
                "submitted_at": "2026-05-01T10:30:00",
                "results": {},
                "answers": {},
            },
            {
                # Pending: score=None
                "student_name": "Bob",
                "student_id": "s2",
                "student_id_number": "ID-2",
                "score": None,
                "percentage": None,
                "time_taken_seconds": None,
                "submitted_at": "2026-05-01T10:25:00",
                "results": {},
                "answers": {},
            },
        ]
        seq = [
            MagicMock(data=[pa_row]),  # published_assessments
            MagicMock(data=subs),       # submissions
            MagicMock(data=[]),          # published_content (empty)
        ]
        p, _ = patch_supabase(seq)
        with p:
            resp = client.get(
                "/api/assessment-results", headers=auth_headers,
            )
        body = resp.get_json()
        assert len(body["assessments"]) == 1
        a = body["assessments"][0]
        assert a["title"] == "Quiz One"
        assert a["source"] == "join_code"
        assert a["join_code"] == "ABC123"
        # Stats: 1 graded + 1 pending
        s = a["stats"]
        assert s["total_submissions"] == 2
        assert s["graded_count"] == 1
        assert s["pending_count"] == 1
        assert s["average_score"] == 85
        assert s["highest_score"] == 85
        assert s["lowest_score"] == 85
        assert s["average_time_seconds"] == 600
        # Submissions[0] has letter grade B (85 → 80-89 → B)
        alice = next(s for s in a["submissions"] if s["student_name"] == "Alice")
        assert alice["letter_grade"] == "B"
        assert alice["status"] == "graded"
        bob = next(s for s in a["submissions"] if s["student_name"] == "Bob")
        assert bob["letter_grade"] is None
        assert bob["status"] == "pending"

    def test_join_code_skips_non_assessment_content_type(
        self, client, auth_headers,
    ):
        pa_row = {
            "id": "pa-1", "join_code": "X",
            "settings": {"content_type": "survey"},  # NOT assessment
            "assessment": {},
        }
        seq = [
            MagicMock(data=[pa_row]),
            MagicMock(data=[]),  # PC
        ]
        p, _ = patch_supabase(seq)
        with p:
            resp = client.get(
                "/api/assessment-results", headers=auth_headers,
            )
        # Survey content type is filtered out
        assert resp.get_json()["assessments"] == []

    def test_class_based_assessment_with_oneroster_prefix_stripped(
        self, client, auth_headers,
    ):
        pc_row = {
            "id": "pc-1",
            "title": "Class Quiz",
            "is_active": True,
            "created_at": "2026-05-02T09:00:00",
            "join_code": "DEF456",
            "class_id": "cls-1",
            "period": "P5",
            "settings": {
                "assessment_category": "summative",
            },
            "content": {"sections": []},
        }
        # Student submission with `students` join row carrying ID number
        subs = [
            {
                "student_name": "Carol",
                "student_id": "s1",
                "students": {"student_id_number": "ID-100"},
                "score": 92,
                "percentage": 92,
                "time_taken_seconds": 500,
                "submitted_at": "2026-05-02T09:30:00",
                "status": "graded",
                "results": {},
                "answers": {},
            },
            {
                # Submitted/partial counts as pending
                "student_name": "Dan",
                "students": None,  # join missing → fallback
                "student_id_number": "ID-200",  # fallback to row column
                "score": None,
                "percentage": None,
                "submitted_at": "2026-05-02T09:25:00",
                "status": "submitted",
                "results": {},
                "answers": {},
            },
        ]
        # Class lookup returns oneroster: prefixed external id → stripped
        cls_row = {"clever_section_id": "oneroster:section-xyz"}
        seq = [
            MagicMock(data=[]),                # PA empty
            MagicMock(data=[pc_row]),          # PC
            MagicMock(data=subs),              # student_submissions
            MagicMock(count=10, data=None),    # enrolled count
            MagicMock(data=cls_row),           # classes select.single
        ]
        p, _ = patch_supabase(seq)
        with p:
            resp = client.get(
                "/api/assessment-results", headers=auth_headers,
            )
        body = resp.get_json()
        assert len(body["assessments"]) == 1
        a = body["assessments"][0]
        assert a["source"] == "class_based"
        assert a["assessment_category"] == "summative"
        # Oneroster prefix stripped
        assert a["class_sourced_id"] == "section-xyz"
        # Expected count from enrollment
        assert a["stats"]["expected_submissions"] == 10
        # 1 graded + 1 submitted-pending
        assert a["stats"]["graded_count"] == 1
        assert a["stats"]["pending_count"] == 1
        # Carol got ID-100 from the students join
        carol = next(s for s in a["submissions"]
                     if s["student_name"] == "Carol")
        assert carol["student_id_number"] == "ID-100"
        assert carol["letter_grade"] == "A"  # 92 → A
        # Dan falls back to the row's student_id_number column
        dan = next(s for s in a["submissions"] if s["student_name"] == "Dan")
        assert dan["student_id_number"] == "ID-200"

    def test_class_based_no_oneroster_prefix_leaves_class_sourced_empty(
        self, client, auth_headers,
    ):
        # When the class's clever_section_id doesn't have the
        # oneroster: prefix, class_sourced_id stays empty.
        pc_row = {
            "id": "pc-1", "title": "T", "is_active": True,
            "created_at": "2026-05-02T09:00:00",
            "class_id": "cls-1", "settings": {}, "content": {},
        }
        seq = [
            MagicMock(data=[]),           # PA
            MagicMock(data=[pc_row]),     # PC
            MagicMock(data=[]),           # subs
            MagicMock(count=5, data=None),# enrolled
            MagicMock(data={"clever_section_id": "clever-direct-id"}),
        ]
        p, _ = patch_supabase(seq)
        with p:
            resp = client.get(
                "/api/assessment-results", headers=auth_headers,
            )
        a = resp.get_json()["assessments"][0]
        # No oneroster: prefix → no class_sourced_id
        assert a["class_sourced_id"] == ""

    def test_enrollment_count_query_failure_swallowed(
        self, client, auth_headers,
    ):
        # When the class_students enrolled-count query raises, the
        # except fall-through leaves expected_submissions=None but the
        # rest of the response shape is intact.
        pc_row = {
            "id": "pc-1", "title": "T", "is_active": True,
            "created_at": "2026-05-02T09:00:00",
            "class_id": "cls-1", "settings": {}, "content": {},
        }

        # Build a custom execute sequence where the 4th call (enrolled
        # count probe) raises but everything else returns data.
        call_index = {"i": 0}
        responses = [
            MagicMock(data=[]),           # PA
            MagicMock(data=[pc_row]),     # PC
            MagicMock(data=[]),           # subs
        ]

        def execute_dispatcher():
            i = call_index["i"]
            call_index["i"] += 1
            if i < len(responses):
                return responses[i]
            if i == 3:
                # enrolled count → raise
                raise RuntimeError("count probe failed")
            if i == 4:
                # classes lookup also raises (covered by separate except)
                raise RuntimeError("class lookup failed")
            return MagicMock(data=[])

        chain = FakeChain()
        chain.execute = execute_dispatcher  # type: ignore
        sb = MagicMock()
        sb.table.side_effect = chain.table
        with patch(
            "backend.routes.assessment_results_routes.get_supabase",
            return_value=sb,
        ):
            resp = client.get(
                "/api/assessment-results", headers=auth_headers,
            )
        body = resp.get_json()
        assert resp.status_code == 200
        assert body["assessments"][0]["stats"]["expected_submissions"] is None
        assert body["assessments"][0]["class_sourced_id"] == ""

    def test_join_code_query_failure_swallowed(
        self, client, auth_headers,
    ):
        # PA query raises → entire join-code branch skipped, but PC
        # branch still runs and returns one assessment.
        call_index = {"i": 0}
        pc_row = {
            "id": "pc-1", "title": "From PC", "is_active": True,
            "created_at": "2026-05-02T09:00:00",
            "class_id": None, "settings": {}, "content": {},
        }
        responses = [
            None,  # PA → raise via index
            MagicMock(data=[pc_row]),  # PC
            MagicMock(data=[]),  # subs
        ]

        def execute_dispatcher():
            i = call_index["i"]
            call_index["i"] += 1
            if i == 0:
                raise RuntimeError("supabase down")
            if i < len(responses):
                return responses[i]
            return MagicMock(data=[])

        chain = FakeChain()
        chain.execute = execute_dispatcher  # type: ignore
        sb = MagicMock()
        sb.table.side_effect = chain.table
        with patch(
            "backend.routes.assessment_results_routes.get_supabase",
            return_value=sb,
        ):
            resp = client.get(
                "/api/assessment-results", headers=auth_headers,
            )
        body = resp.get_json()
        assert len(body["assessments"]) == 1
        assert body["assessments"][0]["title"] == "From PC"

    def test_class_based_query_failure_swallowed(
        self, client, auth_headers,
    ):
        # PC query raises → entire class-based branch skipped, but PA
        # branch still ran (empty here) so total = 0.
        call_index = {"i": 0}

        def execute_dispatcher():
            i = call_index["i"]
            call_index["i"] += 1
            if i == 0:
                return MagicMock(data=[])
            if i == 1:
                raise RuntimeError("PC query died")
            return MagicMock(data=[])

        chain = FakeChain()
        chain.execute = execute_dispatcher  # type: ignore
        sb = MagicMock()
        sb.table.side_effect = chain.table
        with patch(
            "backend.routes.assessment_results_routes.get_supabase",
            return_value=sb,
        ):
            resp = client.get(
                "/api/assessment-results", headers=auth_headers,
            )
        # Both branches fail-silent → total 0
        assert resp.status_code == 200
        assert resp.get_json()["assessments"] == []

    def test_audit_log_failure_swallowed(self, client, auth_headers):
        # The audit_log import itself raises. The except branch logs
        # via _logger and continues; response shape unaffected.
        seq = [MagicMock(data=[]), MagicMock(data=[])]
        p, _ = patch_supabase(seq)
        with p, patch(
            "backend.utils.audit.audit_log",
            side_effect=RuntimeError("audit dead"),
        ):
            resp = client.get(
                "/api/assessment-results", headers=auth_headers,
            )
        assert resp.status_code == 200

    def test_sort_descending_by_published_at_across_paths(
        self, client, auth_headers,
    ):
        # PA assessment dated 2026-04-01, PC assessment dated 2026-05-02.
        # After both branches load, the .sort(reverse=True) should put
        # PC before PA in the response.
        pa_row = {
            "id": "pa-1", "join_code": "X", "title": "Old PA",
            "is_active": True, "created_at": "2026-04-01T00:00:00",
            "settings": {"content_type": "assessment"},
            "assessment": {},
        }
        pc_row = {
            "id": "pc-1", "title": "New PC", "is_active": True,
            "created_at": "2026-05-02T00:00:00",
            "class_id": None, "settings": {}, "content": {},
        }
        seq = [
            MagicMock(data=[pa_row]),
            MagicMock(data=[]),  # PA submissions
            MagicMock(data=[pc_row]),
            MagicMock(data=[]),  # PC submissions
        ]
        p, _ = patch_supabase(seq)
        with p:
            resp = client.get(
                "/api/assessment-results", headers=auth_headers,
            )
        body = resp.get_json()
        titles = [a["title"] for a in body["assessments"]]
        assert titles == ["New PC", "Old PA"]

    def test_category_filter_formative_only(
        self, client, auth_headers,
    ):
        pa_form = {
            "id": "pa-form", "join_code": "F", "title": "Formative",
            "is_active": True, "created_at": "2026-05-01T00:00:00",
            "settings": {"content_type": "assessment",
                         "assessment_category": "formative"},
            "assessment": {},
        }
        pa_summ = {
            "id": "pa-summ", "join_code": "S", "title": "Summative",
            "is_active": True, "created_at": "2026-05-02T00:00:00",
            "settings": {"content_type": "assessment",
                         "assessment_category": "summative"},
            "assessment": {},
        }
        seq = [
            MagicMock(data=[pa_form, pa_summ]),
            MagicMock(data=[]),  # subs for pa_form
            MagicMock(data=[]),  # subs for pa_summ
            MagicMock(data=[]),  # PC empty
        ]
        p, _ = patch_supabase(seq)
        with p:
            resp = client.get(
                "/api/assessment-results?category=formative",
                headers=auth_headers,
            )
        body = resp.get_json()
        assert len(body["assessments"]) == 1
        assert body["assessments"][0]["title"] == "Formative"

    def test_category_filter_invalid_value_keeps_all(
        self, client, auth_headers,
    ):
        # category=garbage isn't in (formative, summative) → no filter
        pa_form = {
            "id": "pa-1", "join_code": "F", "title": "T",
            "is_active": True, "created_at": "2026-05-01T00:00:00",
            "settings": {"content_type": "assessment"},
            "assessment": {},
        }
        seq = [
            MagicMock(data=[pa_form]),
            MagicMock(data=[]),
            MagicMock(data=[]),
        ]
        p, _ = patch_supabase(seq)
        with p:
            resp = client.get(
                "/api/assessment-results?category=garbage",
                headers=auth_headers,
            )
        body = resp.get_json()
        assert len(body["assessments"]) == 1


# ──────────────────────────────────────────────────────────────────
# _compute_question_analysis: gap-fill helper tests
# Lines 67/92: MC correct/student answer with "A)" form → strip ")"
# Lines 141-152: "matching or other types" fallback branch
# ──────────────────────────────────────────────────────────────────


class TestComputeQuestionAnalysisGaps:
    def test_mc_correct_answer_with_paren_form_stripped(self):
        """Correct answer "B)" should normalize to "B" so the
        is_correct flag lands on the right distribution slot."""
        from backend.routes.assessment_results_routes import (
            _compute_question_analysis,
        )
        assessment = {
            "sections": [{
                "questions": [{
                    "type": "multiple_choice",
                    "number": 1,
                    "answer": "B)",  # Form with trailing paren
                    "options": ["A opt", "B opt", "C opt"],
                    "points": 1,
                }],
            }],
        }
        # Submit one correct (B) and one with "A)" form too
        subs = [
            {"answers": {"0-0": "B"}},          # correct
            {"answers": {"0-0": "A)"}},         # "A)" form → A
        ]
        result = _compute_question_analysis(assessment, subs)
        assert len(result) == 1
        q = result[0]
        # B is the correct letter; distribution["B"] should be is_correct=True
        assert q["response_distribution"]["B"]["is_correct"] is True
        assert q["response_distribution"]["B"]["count"] == 1
        # "A)" student answer normalized → A bucket
        assert q["response_distribution"]["A"]["count"] == 1
        # 1 correct out of 2
        assert q["percent_correct"] == 50

    def test_matching_question_type_fallback_branch(self):
        """An unknown q_type (e.g. 'matching') falls into the trailing
        else branch (lines 141-152) which tallies via results.questions
        is_correct flags."""
        from backend.routes.assessment_results_routes import (
            _compute_question_analysis,
        )
        assessment = {
            "sections": [{
                "questions": [{
                    "type": "matching",
                    "number": 5,
                    "answer": {"a": "1", "b": "2"},
                    "points": 4,
                }],
            }],
        }
        subs = [
            {"results": {"questions": [
                {"number": 5, "is_correct": True},
            ]}},
            {"results": {"questions": [
                {"number": 5, "is_correct": False},
            ]}},
            # Another matching result for question 7 (different number)
            # → does NOT count toward question 5's totals.
            {"results": {"questions": [
                {"number": 7, "is_correct": True},
            ]}},
        ]
        result = _compute_question_analysis(assessment, subs)
        q = result[0]
        # 1 correct + 1 incorrect (third sub doesn't match number=5)
        assert q["total_responses"] == 2
        assert q["percent_correct"] == 50

    def test_matching_zero_responses_returns_zero_percent(self):
        from backend.routes.assessment_results_routes import (
            _compute_question_analysis,
        )
        assessment = {
            "sections": [{
                "questions": [{
                    "type": "matching", "number": 1,
                    "answer": {}, "points": 1,
                }],
            }],
        }
        result = _compute_question_analysis(assessment, [])
        assert result[0]["percent_correct"] == 0
        assert result[0]["total_responses"] == 0
