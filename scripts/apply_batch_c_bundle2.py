"""Batch C bundle 2: student_history + automation_routes + admin_routes
+ roster_sync + assistant_tools_grading (29 rows)."""
import re, sys
from pathlib import Path

AUDIT = Path(__file__).resolve().parent.parent / "docs" / "exception-audit-2026-04.md"

DECISIONS = [
    # student_history.py
    ("backend/student_history.py", 17, "INTENTIONAL", "ImportError storage → root-import fallback; bootstrap"),
    ("backend/student_history.py", 20, "INTENTIONAL", "ImportError inner → None; bootstrap"),
    ("backend/student_history.py", 27, "INTENTIONAL", "ImportError rubric_config → root-import fallback; bootstrap"),
    ("backend/student_history.py", 30, "INTENTIONAL", "ImportError inner rubric → hardcoded RUBRIC_MAX_SCORES default; bootstrap"),
    ("backend/student_history.py", 79, "NEEDS_ALERT", "load_student_history read fail → pass; silent trajectory-data loss; mirrors app.py:1690 NEEDS_ALERT"),
    ("backend/student_history.py", 104, "NEEDS_ALERT", "save_student_history write fail → print; FERPA trajectory system-of-record write"),

    # automation_routes.py
    ("backend/routes/automation_routes.py", 56, "INTENTIONAL", "subprocess terminate fail → try kill; cleanup best-effort"),
    ("backend/routes/automation_routes.py", 59, "INTENTIONAL", "subprocess kill fail → pass; final cleanup best-effort"),
    ("backend/routes/automation_routes.py", 141, "LEGACY", "per-workflow parse fail → pass; aggregation-loss in listing"),
    ("backend/routes/automation_routes.py", 215, "LEGACY", "per-template parse fail → pass; aggregation-loss"),
    ("backend/routes/automation_routes.py", 236, "LEGACY", "per-workflow lookup parse pass → 'template not found' masks corruption"),
    ("backend/routes/automation_routes.py", 258, "NEEDS_ALERT", "delete_template file remove fail → still returns 'deleted'; false success (same class as grading_routes:163-212 clear_results)"),

    # admin_routes.py — admin operational metadata; partial visibility
    ("backend/routes/admin_routes.py", 109, "LEGACY", "SIS teacher discovery log.warning; admin sees partial teacher list"),
    ("backend/routes/admin_routes.py", 127, "LEGACY", "fallback teacher discovery log.warning; same class"),
    ("backend/routes/admin_routes.py", 310, "LEGACY", "per-teacher enrichment log.warning + zero defaults; same class"),
    ("backend/routes/admin_routes.py", 390, "LEGACY", "overview aggregation log.warning; same class"),
    ("backend/routes/admin_routes.py", 476, "LEGACY", "teacher summary log.warning; same class"),
    ("backend/routes/admin_routes.py", 510, "LEGACY", "activity fetch log.warning; same class"),

    # roster_sync.py
    ("backend/roster_sync.py", 18, "INTENTIONAL", "_get_supabase fail → None; typed client init fallback"),
    ("backend/roster_sync.py", 76, "NEEDS_ALERT", "Codex Gate 1: classes batch upsert fail log.warning + zero return; SIS sync masked as partial success"),
    ("backend/roster_sync.py", 135, "NEEDS_ALERT", "students batch upsert same masking"),
    ("backend/roster_sync.py", 168, "NEEDS_ALERT", "enrollments batch upsert same masking"),
    ("backend/roster_sync.py", 270, "NEEDS_ALERT", "Supabase roster deletion fail log.error; FERPA delete silent partial"),
    ("backend/roster_sync.py", 288, "LEGACY", "per-file roster remove typed OSError + log.warning; cleanup-only, less critical than SQL delete"),

    # assistant_tools_grading.py
    ("backend/services/assistant_tools_grading.py", 29, "INTENTIONAL", "ImportError storage → root-import fallback; bootstrap"),
    ("backend/services/assistant_tools_grading.py", 32, "INTENTIONAL", "ImportError inner → None; bootstrap"),
    ("backend/services/assistant_tools_grading.py", 88, "INTENTIONAL", "stage_files fail → fallback to raw folder; explicit defined degraded mode"),
    ("backend/services/assistant_tools_grading.py", 837, "INTENTIONAL", "settings.json parse fail → folder='' then downstream resolves; best-effort"),
    ("backend/services/assistant_tools_grading.py", 854, "INTENTIONAL", "stage_files fail → raw folder + duplicates=0; same pattern as 88"),
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
