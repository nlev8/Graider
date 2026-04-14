"""Batch C bundle 3: assistant_tools_data + lesson_routes +
assessment_results_routes + utils/audit + storage (23 rows)."""
import re, sys
from pathlib import Path

AUDIT = Path(__file__).resolve().parent.parent / "docs" / "exception-audit-2026-04.md"

DECISIONS = [
    # assistant_tools_data.py
    ("backend/services/assistant_tools_data.py", 16, "INTENTIONAL", "ImportError storage → root-import; bootstrap"),
    ("backend/services/assistant_tools_data.py", 19, "INTENTIONAL", "ImportError inner → None; bootstrap"),
    ("backend/services/assistant_tools_data.py", 68, "LEGACY", "_load_memories Exception → []; silent loss (same as assistant_tools.py:831)"),
    ("backend/services/assistant_tools_data.py", 127, "INTENTIONAL", "_load_calendar Exception → caller default; defined fallback (same as assistant_tools.py:804)"),
    ("backend/services/assistant_tools_data.py", 152, "LEGACY", "_load_email_config pass + {}; silent email-config loss (same as assistant_tools.py:852)"),

    # lesson_routes.py
    ("backend/routes/lesson_routes.py", 15, "INTENTIONAL", "ImportError anthropic → None; bootstrap"),
    ("backend/routes/lesson_routes.py", 28, "INTENTIONAL", "ImportError storage → root-import; bootstrap"),
    ("backend/routes/lesson_routes.py", 31, "INTENTIONAL", "ImportError inner → None; bootstrap"),
    ("backend/routes/lesson_routes.py", 142, "LEGACY", "per-lesson parse pass; aggregation-skip in listing"),
    ("backend/routes/lesson_routes.py", 260, "INTENTIONAL", "_load_calendar Exception → _DEFAULT_CALENDAR; explicit typed fallback"),

    # assessment_results_routes.py — FERPA results viewer
    ("backend/routes/assessment_results_routes.py", 170, "NEEDS_ALERT", "Codex Gate 1: audit_log fail on VIEW_ASSESSMENT_RESULTS → log.warning; FERPA access unaudited"),
    ("backend/routes/assessment_results_routes.py", 233, "NEEDS_ALERT", "join-code assessments fetch log.warning + partial list; FERPA data masked"),
    ("backend/routes/assessment_results_routes.py", 256, "INTENTIONAL", "enrolled count preview enrichment pass; best-effort"),
    ("backend/routes/assessment_results_routes.py", 263, "INTENTIONAL", "OneRoster ext_id parse pass; best-effort enrichment"),
    ("backend/routes/assessment_results_routes.py", 308, "NEEDS_ALERT", "class-based assessments fetch log.warning + partial; same class as 233"),

    # utils/audit.py — Codex Gate 1 BLOCK flagged both-sides silent
    ("backend/utils/audit.py", 30, "INTENTIONAL", "(ImportError, RuntimeError) → 'unknown' teacher_id; typed Flask-context fallback"),
    ("backend/utils/audit.py", 38, "NEEDS_ALERT", "Codex Gate 1 BLOCK: audit local file append fail → pass; FERPA audit event silent loss"),
    ("backend/utils/audit.py", 45, "INTENTIONAL", "ImportError supabase_client → root-import; bootstrap"),
    ("backend/utils/audit.py", 56, "NEEDS_ALERT", "Codex Gate 1 BLOCK: audit Supabase insert fail → pass; combined with 38 means FERPA event fully lost"),

    # storage.py — underlying dual-write helper
    ("backend/storage.py", 139, "INTENTIONAL", "_file_load log.warning + None; typed fallback, caller detects None"),
    ("backend/storage.py", 319, "INTENTIONAL", "_file_load_student_history Exception → None; same pattern"),
    ("backend/storage.py", 576, "LEGACY", "sync_all_to_cloud per-period CSV sync log.warning; aggregation-loss"),
    ("backend/storage.py", 601, "LEGACY", "sync_all_to_cloud per-history pass; aggregation-loss"),
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
