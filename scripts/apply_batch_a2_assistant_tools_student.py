"""Apply Batch A.2 file 3 categorizations for assistant_tools_student.py.

Codex Gate 1 pre-locked shape rules for this file:
  - Student aggregation loops with silent skip → LEGACY (_find_all_student_files:342)
  - Pending preview/confirm state swallows → NEEDS_ALERT (blind spot at 684,691,724,734,749,755)
  - Import merge fallbacks that overwrite after silent data discard → NEEDS_ALERT (938,972,990,1007)
  - FERPA writes (e.g. Supabase student delete at 428) → NEEDS_ALERT
"""
import re
import sys
from pathlib import Path

AUDIT = Path(__file__).resolve().parent.parent / "docs" / "exception-audit-2026-04.md"

DECISIONS = [
    # _find_all_student_files — Codex pre-locked
    ("backend/services/assistant_tools_student.py", 342, "LEGACY",      "Codex Gate 1: silent file-read skip in loop feeds deletion preview/execution; partial teacher-facing data"),

    # _delete_student_supabase
    ("backend/services/assistant_tools_student.py", 428, "NEEDS_ALERT", "FERPA write path: Supabase student delete failure; log.warning only; mirrors Clever delete-data NEEDS_ALERT"),

    # _execute_student_removal — Flask g fallback + per-source deletes
    ("backend/services/assistant_tools_student.py", 445, "INTENTIONAL", "Flask g teacher_id typed fallback → 'local-dev'; explicit degraded mode"),
    ("backend/services/assistant_tools_student.py", 479, "INTENTIONAL", "per-roster-file read fail → roster_info.append({'error': ...}); error surfaced in partial result"),
    ("backend/services/assistant_tools_student.py", 495, "LEGACY",      "per-source delete (roster CSV) fail → errors.append; FERPA delete partial-fail, ops invisible"),
    ("backend/services/assistant_tools_student.py", 522, "LEGACY",      "per-source delete (grading_results) fail → errors.append; same class"),
    ("backend/services/assistant_tools_student.py", 548, "LEGACY",      "per-source delete (master CSV) fail → errors.append; same class"),
    ("backend/services/assistant_tools_student.py", 557, "LEGACY",      "per-source delete (student history) fail → errors.append; same class"),
    ("backend/services/assistant_tools_student.py", 574, "LEGACY",      "per-source delete (accommodations) fail → errors.append; FERPA-adjacent"),
    ("backend/services/assistant_tools_student.py", 591, "LEGACY",      "per-source delete (parent contacts) fail → errors.append; FERPA-adjacent"),
    ("backend/services/assistant_tools_student.py", 608, "LEGACY",      "per-source delete (ELL data) fail → errors.append; FERPA-adjacent"),

    # remove_student_from_roster
    ("backend/services/assistant_tools_student.py", 642, "INTENTIONAL", "Flask g teacher_id typed fallback"),
    ("backend/services/assistant_tools_student.py", 676, "INTENTIONAL", "grading_state count query pass — best-effort preview enrichment"),
    ("backend/services/assistant_tools_student.py", 684, "NEEDS_ALERT", "Codex Gate 1 blind spot: pending preview state swallow"),
    ("backend/services/assistant_tools_student.py", 691, "NEEDS_ALERT", "Codex Gate 1 blind spot: pending preview state swallow"),

    # confirm_student_removal
    ("backend/services/assistant_tools_student.py", 716, "INTENTIONAL", "Flask g teacher_id typed fallback"),
    ("backend/services/assistant_tools_student.py", 724, "NEEDS_ALERT", "Codex Gate 1 blind spot: pending confirm state swallow"),
    ("backend/services/assistant_tools_student.py", 734, "NEEDS_ALERT", "Codex Gate 1 blind spot: pending confirm state swallow"),
    ("backend/services/assistant_tools_student.py", 749, "NEEDS_ALERT", "Codex Gate 1 blind spot: pending confirm state swallow"),
    ("backend/services/assistant_tools_student.py", 755, "NEEDS_ALERT", "Codex Gate 1 blind spot: pending confirm state swallow"),

    # import_student_data
    ("backend/services/assistant_tools_student.py", 875, "INTENTIONAL", "(json.JSONDecodeError, UnicodeDecodeError) → error dict; typed fallback, caller surfaces"),
    ("backend/services/assistant_tools_student.py", 900, "NEEDS_ALERT", "results_file read fail → silent merge-loss; Codex rule: pre-write read discard leads to overwrite"),
    ("backend/services/assistant_tools_student.py", 921, "INTENTIONAL", "results_file write fail → return error dict; caller surfaces via tool dispatch"),
    ("backend/services/assistant_tools_student.py", 938, "NEEDS_ALERT", "Codex Gate 1: import merge fallback overwrites after silent data discard (student_history)"),
    ("backend/services/assistant_tools_student.py", 972, "NEEDS_ALERT", "Codex Gate 1: same pattern (accommodations)"),
    ("backend/services/assistant_tools_student.py", 990, "NEEDS_ALERT", "Codex Gate 1: same pattern (ELL data)"),
    ("backend/services/assistant_tools_student.py", 1007, "NEEDS_ALERT", "Codex Gate 1: same pattern (parent contacts)"),
    ("backend/services/assistant_tools_student.py", 1037, "LEGACY",     "roster CSV append fail → print; non-tool-dispatch silent swallow; same class as app.py:3090"),
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
