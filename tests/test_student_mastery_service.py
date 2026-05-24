"""Direct-import characterization tests for backend/services/student_mastery.py
(Wave 5 Slice 1 - behavior-preserving extraction from student_portal_routes)."""
from datetime import datetime


def test_parse_ts_handles_z_suffix_and_garbage():
    from backend.services.student_mastery import _parse_ts
    assert _parse_ts("2026-01-02T03:04:05Z") == datetime.fromisoformat("2026-01-02T03:04:05+00:00")
    assert _parse_ts("") == datetime.min
    assert _parse_ts(None) == datetime.min
    assert _parse_ts("not-a-date") == datetime.min


def test_coalesce_keeps_falsy_but_not_none():
    from backend.services.student_mastery import _coalesce
    assert _coalesce(None, 0, 5) == 0          # 0 is a legitimate value, not skipped
    assert _coalesce(None, None, default="x") == "x"
    assert _coalesce(None, "", "y") == ""       # "" is legitimate


def test_normalize_mastery_shape_wraps_flat_and_passes_new():
    from backend.services.student_mastery import _normalize_mastery_shape
    flat = {"points_earned": 4, "points_possible": 5, "question_count": 2, "percentage": 80}
    out = _normalize_mastery_shape(flat)
    assert out == {"overall": flat, "by_dok": {}}
    assert _normalize_mastery_shape("garbage") is None


def test_sanitize_standards_mastery_mutates_in_place_returns_none():
    from backend.services.student_mastery import _sanitize_standards_mastery
    sub = {"id": "s1", "results": {"standards_mastery": "not-a-dict"}}
    ret = _sanitize_standards_mastery(sub)
    assert ret is None                                  # returns None
    assert sub["results"]["standards_mastery"] == {}    # mutated in place


def test_flatten_mastery_for_response_returns_new_dict():
    from backend.services.student_mastery import _flatten_mastery_for_response
    results = {"standards_mastery": {"A": {"overall": {"points_earned": 3, "points_possible": 6, "question_count": 1}}}}
    out = _flatten_mastery_for_response(results)
    assert out is not results                            # new dict, no mutation
    assert out["standards_mastery"]["A"]["percentage"] == 50.0


def test_aggregate_mastery_latest_sums_overall():
    from backend.services.student_mastery import _aggregate_mastery_for_student
    subs = {"c1": [{"id": "s1", "attempt_number": 1,
                    "results": {"standards_mastery": {"A": {"points_earned": 8, "points_possible": 10, "question_count": 2}}}}]}
    out = _aggregate_mastery_for_student(subs, {"c1": "Quiz"}, "latest")
    assert out["A"]["percentage"] == 80.0
    assert out["A"]["points_possible"] == 10


def test_aggregate_mastery_average_mode_averages_percentages():
    from backend.services.student_mastery import _aggregate_mastery_for_student
    subs = {"c1": [
        {"id": "s1", "attempt_number": 1,
         "results": {"standards_mastery": {"A": {"points_earned": 6, "points_possible": 10, "question_count": 1}}}},
        {"id": "s2", "attempt_number": 2,
         "results": {"standards_mastery": {"A": {"points_earned": 10, "points_possible": 10, "question_count": 1}}}},
    ]}
    out = _aggregate_mastery_for_student(subs, {"c1": "Quiz"}, "average")
    assert out["A"]["percentage"] == 80.0  # mean of 60% and 100%, not summed


def test_select_submissions_by_mode_best_vs_latest_vs_average():
    from backend.services.student_mastery import _select_submissions_by_mode
    subs = {"c1": [
        {"id": "a", "percentage": 90, "attempt_number": 1, "submitted_at": "2026-01-01T00:00:00Z"},
        {"id": "b", "percentage": 60, "attempt_number": 2, "submitted_at": "2026-01-02T00:00:00Z"},
    ]}
    assert _select_submissions_by_mode(subs, "best")["c1"][0]["id"] == "a"    # highest percentage
    assert _select_submissions_by_mode(subs, "latest")["c1"][0]["id"] == "b"  # highest attempt_number
    assert len(_select_submissions_by_mode(subs, "average")["c1"]) == 2       # average keeps all


def test_build_standards_breakdown_sorts_worst_first_flat_input():
    from backend.services.student_mastery import _build_standards_breakdown_for_student
    mastery = {
        "HI.1": {"percentage": 90, "points_earned": 9, "points_possible": 10, "question_count": 1, "contributing_submissions": []},
        "LO.2": {"percentage": 40, "points_earned": 4, "points_possible": 10, "question_count": 1, "contributing_submissions": []},
    }
    rows = _build_standards_breakdown_for_student(mastery, {})
    assert [r["code"] for r in rows] == ["LO.2", "HI.1"]  # ASC by percentage = worst-first
    assert rows[0]["by_dok"] == []                         # flat input emits empty by_dok


def test_build_trajectory_nulls_sort_last():
    from backend.services.student_mastery import _build_trajectory_for_student
    subs = [
        {"id": "late", "content_id": "c1", "submitted_at": None, "percentage": 50, "attempt_number": 1, "results": {}},
        {"id": "early", "content_id": "c1", "submitted_at": "2026-01-01T00:00:00Z", "percentage": 70, "attempt_number": 1, "results": {}},
        {"id": "mid", "content_id": "c1", "submitted_at": "2026-02-01T00:00:00Z", "percentage": 80, "attempt_number": 1, "results": {}},
    ]
    out = _build_trajectory_for_student(subs, {"c1": "Quiz"})
    assert [o["submission_id"] for o in out] == ["early", "mid", "late"]  # chronological; null submitted_at last
