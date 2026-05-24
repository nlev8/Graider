"""Direct-import characterization tests for backend/services/student_remediation.py
(Wave 5 Slice 2 - behavior-preserving extraction from student_portal_routes)."""


def test_validate_and_clean_lesson_keeps_only_three_fields_and_strips():
    from backend.services.student_remediation import _validate_and_clean_lesson
    raw = {"intro": " hi ", "worked_example": "x", "key_takeaway": "y", "evil": "drop me"}
    out = _validate_and_clean_lesson(raw)
    assert out == {"intro": "hi", "worked_example": "x", "key_takeaway": "y"}


def test_validate_and_clean_lesson_rejects_nondict_missing_empty_oversize():
    from backend.services.student_remediation import _validate_and_clean_lesson
    assert _validate_and_clean_lesson("nope") is None
    assert _validate_and_clean_lesson({"intro": "a", "worked_example": "b"}) is None   # missing key_takeaway
    assert _validate_and_clean_lesson({"intro": "", "worked_example": "b", "key_takeaway": "c"}) is None  # empty
    big = "z" * 1501
    assert _validate_and_clean_lesson({"intro": big, "worked_example": "b", "key_takeaway": "c"}) is None  # oversize


def test_difficulty_directive_clamps_grade_and_handles_nonnumeric():
    from backend.services.student_remediation import _difficulty_directive
    assert "grade-6" in _difficulty_directive("easier", "7")     # one below
    assert "grade-8" in _difficulty_directive("harder", "7")     # one above
    assert "grade-1" in _difficulty_directive("easier", "1")  # K-12 floor: max(1, 0) clamps to grade-1, not grade-0
    assert "below the current grade" in _difficulty_directive("easier", "kindergarten")  # non-numeric phrasing
    assert _difficulty_directive("same", "7") == "Difficulty: grade-level review."


def test_build_remediation_prompt_uses_count_and_standard():
    from backend.services.student_remediation import _build_remediation_prompt, REMEDIATION_COUNT_DEFAULT
    p = _build_remediation_prompt(grade="7", subject="Civics", standard_code="SS.7.C.1")
    assert f"exactly {REMEDIATION_COUNT_DEFAULT}" in p
    assert "SS.7.C.1" in p
    # default 60/40 mc/sa split for the default count
    mc = round(REMEDIATION_COUNT_DEFAULT * 0.6)
    assert f"{mc} multiple-choice" in p


def test_build_remediation_prompt_dok_directive_only_when_valid():
    from backend.services.student_remediation import _build_remediation_prompt
    with_dok = _build_remediation_prompt(grade="7", subject="Civics", standard_code="X", dok=3)
    assert "DOK level 3" in with_dok
    without = _build_remediation_prompt(grade="7", subject="Civics", standard_code="X", dok=None)
    assert "DOK level" not in without


def test_check_remediation_cap_counts_per_student_window():
    from backend.services.student_remediation import _check_remediation_cap, REMEDIATION_PER_STUDENT_WEEKLY_CAP

    class _Resp:
        def __init__(self, data): self.data = data

    class _Q:
        def __init__(self, data): self._data = data
        def select(self, *a, **k): return self
        def eq(self, *a, **k): return self
        def gte(self, *a, **k): return self
        def execute(self): return _Resp(self._data)

    class _DB:
        def __init__(self, rows): self._rows = rows
        def table(self, *a, **k): return _Q(self._rows)

    # student "s1" appears in CAP rows -> capped; "s2" appears once -> clear
    rows = [{"id": str(i), "target_student_ids": ["s1"], "created_at": "2026-05-20"}
            for i in range(REMEDIATION_PER_STUDENT_WEEKLY_CAP)]
    rows.append({"id": "x", "target_student_ids": ["s2"], "created_at": "2026-05-20"})
    capped = _check_remediation_cap(_DB(rows), "teacher1", ["s1", "s2"])
    assert "s1" in capped and "s2" not in capped


def test_remediation_names_re_exported_from_route_module():
    # The re-export shim keeps the old import path working.
    from backend.routes.student_portal_routes import (
        _build_remediation_prompt, REMEDIATION_COUNT_DEFAULT, _gen_variant_for_student,
    )
    from backend.services.student_remediation import _build_remediation_prompt as svc_fn
    assert _build_remediation_prompt is svc_fn
    assert REMEDIATION_COUNT_DEFAULT == 8
    assert callable(_gen_variant_for_student)
