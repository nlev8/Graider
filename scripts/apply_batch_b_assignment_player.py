"""Apply Batch B file 3 categorizations for assignment_player_routes.py.

File is pure deterministic grading logic — 21 typed fallbacks / defined
error shapes with no data persistence. 100% INTENTIONAL rate is
explicitly flagged to Codex Gate 3 for sanity check.

Codex Gate 1 pre-locks (carried forward from file context):
  - OCR/AI fallbacks → degraded-grading INTENTIONAL (371, 574)
  - 404/400 paths stay as-is (none in uncategorized set)
  - /submit write failures NEEDS_ALERT (none in uncategorized set)
"""
import re, sys
from pathlib import Path

AUDIT = Path(__file__).resolve().parent.parent / "docs" / "exception-audit-2026-04.md"

DECISIONS = [
    # Bootstrap
    ("backend/routes/assignment_player_routes.py", 33, "INTENTIONAL", "ImportError assignment_grader → AI_GRADING_AVAILABLE=False; bootstrap"),
    ("backend/routes/assignment_player_routes.py", 40, "INTENTIONAL", "ImportError mathpix → MATHPIX_AVAILABLE=False + stub function; bootstrap"),

    # Teacher context
    ("backend/routes/assignment_player_routes.py", 94, "INTENTIONAL", "_load_teacher_context → pass; defined empty-context fallback"),

    # OCR and AI fallbacks (Codex Gate 1 pre-lock)
    ("backend/routes/assignment_player_routes.py", 371, "INTENTIONAL", "GPT-4o Vision OCR fallback → print + return error in typed shape; Codex Gate 1: OCR fallback is degraded-grading INTENTIONAL"),
    ("backend/routes/assignment_player_routes.py", 574, "INTENTIONAL", "_grade_with_ai fail → print + fall back to grade_short_answer; Codex Gate 1: AI fallback degraded-grading INTENTIONAL"),

    # Deterministic graders — all return typed error shapes
    ("backend/routes/assignment_player_routes.py", 695, "INTENTIONAL", "grade_question top-level catch → return {error: true} with feedback; surfaced error shape"),
    ("backend/routes/assignment_player_routes.py", 933, "INTENTIONAL", "(ValueError, TypeError) on float() of explicit answer → typed fallback"),
    ("backend/routes/assignment_player_routes.py", 958, "INTENTIONAL", "(ValueError, TypeError) grade_geometry → return explicit feedback; typed"),
    ("backend/routes/assignment_player_routes.py", 994, "INTENTIONAL", "grade_box_plot per-cell pass → no partial credit penalty for that cell; defined scoring"),
    ("backend/routes/assignment_player_routes.py", 1027, "INTENTIONAL", "grade_math_equation catch → fall back to string compare; explicit degraded fallback"),
    ("backend/routes/assignment_player_routes.py", 1056, "INTENTIONAL", "grade_coordinates catch → error feedback; surfaced"),
    ("backend/routes/assignment_player_routes.py", 1092, "INTENTIONAL", "(ValueError, TypeError) per-cell → string compare fallback; typed"),
    ("backend/routes/assignment_player_routes.py", 1104, "INTENTIONAL", "grade_data_table outer → error feedback; surfaced"),
    ("backend/routes/assignment_player_routes.py", 1163, "INTENTIONAL", "sympify expr parse fail → continue to next expected expr; per-expr skip"),
    ("backend/routes/assignment_player_routes.py", 1173, "INTENTIONAL", "SymPy simplify fail → string compare fallback; explicit"),
    ("backend/routes/assignment_player_routes.py", 1190, "INTENTIONAL", "ImportError SymPy → normalized string comparison fallback; defined chain"),
    ("backend/routes/assignment_player_routes.py", 1451, "INTENTIONAL", "(ValueError, ZeroDivisionError) normalize_fraction → return unchanged s; typed"),
    ("backend/routes/assignment_player_routes.py", 1503, "INTENTIONAL", "ValueError per-cell tape diagram → case-insensitive string fallback; typed"),
    ("backend/routes/assignment_player_routes.py", 1523, "INTENTIONAL", "ValueError grade_tape_diagram → string fallback; typed"),
    ("backend/routes/assignment_player_routes.py", 1544, "INTENTIONAL", "ValueError per-region venn → case-insensitive fallback; typed"),
    ("backend/routes/assignment_player_routes.py", 1583, "INTENTIONAL", "(ValueError, TypeError) protractor angle parse → error feedback; typed surfaced"),
]

ROW_RE = re.compile(r"^\| `(?P<file>[^`]+)` \| (?P<line>\d+) \| `(?P<exc>[^`]+)` \| (?P<behavior>[^|]+) \| `(?P<parent>[^`]+)` \| (?P<cat>\w+) \|$")


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
