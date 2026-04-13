"""Apply Batch B file 1 categorizations for grading_routes.py.

Codex Gate 1: APPROVE with pre-locks:
  - 287, 371 (grade/result write silent swallow) → NEEDS_ALERT
  - 1509, 1525, 1549 (migrate_student_names partial fails) → NEEDS_ALERT
"""
import re
import sys
from pathlib import Path

AUDIT = Path(__file__).resolve().parent.parent / "docs" / "exception-audit-2026-04.md"

DECISIONS = [
    # clear_results — silent write failures
    ("backend/routes/grading_routes.py", 163, "LEGACY", "results_file update silent fail after filter; data loss"),
    ("backend/routes/grading_routes.py", 182, "LEGACY", "master_grades.csv update silent fail; same class (system-of-record)"),
    ("backend/routes/grading_routes.py", 204, "LEGACY", "results_file remove silent fail; stale data left"),
    ("backend/routes/grading_routes.py", 212, "LEGACY", "master_grades.csv remove silent fail"),

    # _sync_result_to_master_csv — Codex pre-lock NEEDS_ALERT
    ("backend/routes/grading_routes.py", 287, "NEEDS_ALERT", "Codex Gate 1: master_grades.csv sync silent fail; primary grade persistence path"),

    # update_result
    ("backend/routes/grading_routes.py", 371, "NEEDS_ALERT", "Codex Gate 1: results_file save silent fail after grading_state update"),
    ("backend/routes/grading_routes.py", 395, "LEGACY", "record_correction write fail → log.warning; correction-tracking feedback-loop data, not graded-record"),

    # Math tool routes — typed ImportError
    ("backend/routes/grading_routes.py", 435, "INTENTIONAL", "ImportError stem_grading → typed error JSON"),
    ("backend/routes/grading_routes.py", 470, "INTENTIONAL", "ImportError grade_data_table → typed error JSON"),
    ("backend/routes/grading_routes.py", 498, "INTENTIONAL", "ImportError grade_coordinate_question → typed error JSON"),
    ("backend/routes/grading_routes.py", 525, "INTENTIONAL", "ImportError grade_place_name → typed error JSON"),
    ("backend/routes/grading_routes.py", 551, "INTENTIONAL", "ImportError check_math_equivalence → typed error JSON"),

    # export_focus_csv
    ("backend/routes/grading_routes.py", 628, "INTENTIONAL", "per-roster file read in loop → pass; try next roster"),
    ("backend/routes/grading_routes.py", 669, "INTENTIONAL", "per-period file read in loop → pass; same pattern"),
    ("backend/routes/grading_routes.py", 778, "INTENTIONAL", "Claude name-matching fail → print + continue; matching is enrichment, comment says 'Continue without matching'"),

    # export_focus_batch / export_lms_csv — macOS convenience
    ("backend/routes/grading_routes.py", 902, "INTENTIONAL", "macOS subprocess open → pass; dev convenience only"),
    ("backend/routes/grading_routes.py", 1019, "INTENTIONAL", "macOS subprocess open → pass; same"),

    # list_student_history
    ("backend/routes/grading_routes.py", 1325, "INTENTIONAL", "per-student history read fail → append record with error field; error surfaced in result"),

    # _build_student_name_lookup — aggregation-loss
    ("backend/routes/grading_routes.py", 1387, "LEGACY", "roster CSV read fail → pass; silent name-lookup skip, feeds migrations/matching (aggregation-loss)"),
    ("backend/routes/grading_routes.py", 1403, "LEGACY", "period CSV read fail → pass; same class"),

    # delete_all_student_history
    ("backend/routes/grading_routes.py", 1468, "INTENTIONAL", "per-file history delete fail → append error; caller surfaces errors array"),

    # migrate_student_names — Codex pre-locks NEEDS_ALERT
    ("backend/routes/grading_routes.py", 1509, "NEEDS_ALERT", "Codex Gate 1: one-time migration roster read silent fail"),
    ("backend/routes/grading_routes.py", 1525, "NEEDS_ALERT", "Codex Gate 1: period CSV read silent fail in migration"),
    ("backend/routes/grading_routes.py", 1549, "NEEDS_ALERT", "Codex Gate 1: profile write silent fail in migration"),
]

ROW_RE = re.compile(
    r"^\| `(?P<file>[^`]+)` \| (?P<line>\d+) \| `(?P<exc>[^`]+)` \| "
    r"(?P<behavior>[^|]+) \| `(?P<parent>[^`]+)` \| (?P<cat>\w+) \|$"
)


def main():
    text = AUDIT.read_text()
    lines = text.splitlines()
    dmap = {(f, line): cat for (f, line, cat, _) in DECISIONS}
    applied = 0
    not_found = list(dmap.keys())
    for i, line_text in enumerate(lines):
        m = ROW_RE.match(line_text)
        if not m:
            continue
        key = (m.group("file"), int(m.group("line")))
        if key not in dmap or m.group("cat") != "UNCATEGORIZED":
            if key in dmap:
                not_found.remove(key)
            continue
        lines[i] = line_text.rsplit("|", 2)[0] + f"| {dmap[key]} |"
        applied += 1
        not_found.remove(key)
    AUDIT.write_text("\n".join(lines) + "\n")
    print(f"Applied {applied}/{len(DECISIONS)}", file=sys.stderr)
    if not_found:
        for k in not_found:
            print(f"NOT FOUND {k}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
