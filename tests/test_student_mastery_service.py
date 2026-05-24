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
