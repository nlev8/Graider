"""Scope a Clever roster response to a single teacher's own sections.

Extracted from the existing logic at backend/routes/clever_routes.py:495-536
so the manual sync route, the periodic-sync cron, AND the post-login
background thread all share one tenancy filter.

Source: 2026-05-14 dimensional review S2.
"""
from typing import List, Tuple


def _section_teacher_ids(section_data):
    """Extract teacher IDs from a section's `teachers` field.

    Clever returns this as a list of strings OR a list of dicts with
    'id'. Handle both shapes.
    """
    teachers = section_data.get("teachers", [])
    out = []
    for t in teachers:
        if isinstance(t, str):
            out.append(t)
        elif isinstance(t, dict):
            tid = t.get("id", "")
            if tid:
                out.append(tid)
    return out


def filter_roster_to_teacher(
    roster: dict, teacher_clever_id: str,
) -> Tuple[List[dict], List[dict]]:
    """Return (own_sections, own_students) for the given Clever teacher ID.

    own_sections: sections where the teacher is listed in the `teachers`
                  field. Empty list if the teacher_clever_id is falsy
                  or doesn't own any section in this roster.

    own_students: students enrolled in own_sections (deduplicated by
                  Clever student id). Excludes students from sections
                  the teacher doesn't own.
    """
    if not teacher_clever_id:
        return [], []

    all_sections = roster.get("sections", [])
    own_sections = []
    own_student_ids = set()
    for section in all_sections:
        sd = section.get("data", section)
        if teacher_clever_id in _section_teacher_ids(sd):
            own_sections.append(section)
            own_student_ids.update(sd.get("students", []))

    own_students = [
        s for s in roster.get("students", [])
        if s.get("data", s).get("id", "") in own_student_ids
    ]
    return own_sections, own_students
