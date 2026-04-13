"""Apply Batch B file 6 for email_routes.py.

Codex Gate 1 critical paths to NEEDS_ALERT:
  - send_emails recipient swap (parent contacts) without alert
  - export_outlook_emails ID-type mismatch silent skip
  - _read_outlook_output stderr ignored (status mask)
  - confirm_send replay double-send risk
"""
import re, sys
from pathlib import Path

AUDIT = Path(__file__).resolve().parent.parent / "docs" / "exception-audit-2026-04.md"

DECISIONS = [
    # send_emails — Codex flagged recipient swap path
    ("backend/routes/email_routes.py", 51,  "NEEDS_ALERT", "Codex Gate 1: parent_contacts read fail → silent recipient resolution loss; FERPA-adjacent recipient swap"),
    ("backend/routes/email_routes.py", 136, "INTENTIONAL", "ImportError email_service → typed error response; route guard"),

    # export_outlook_emails — Codex flagged ID-mismatch silent skip
    ("backend/routes/email_routes.py", 267, "NEEDS_ALERT", "Codex Gate 1: results_file read fail → empty results; export silently sends no/wrong data"),
    ("backend/routes/email_routes.py", 284, "LEGACY", "GraiderEmailer init fail → use passed teacher_name; defined fallback but loses config-driven name"),

    # send_confirmation_emails
    ("backend/routes/email_routes.py", 840, "INTENTIONAL", "ImportError assignment_grader → root-import fallback; bootstrap-style"),
    ("backend/routes/email_routes.py", 865, "INTENTIONAL", "stage_files fail → fall back to scan unstaged; explicit defined degraded path"),
    ("backend/routes/email_routes.py", 890, "INTENTIONAL", "per-config alias merge → pass; per-file skip in alias loop"),
    ("backend/routes/email_routes.py", 999, "NEEDS_ALERT", "parent_contacts read silent fail → email sends without parent CC; FERPA-adjacent recipient loss"),

    # pending_confirmations
    ("backend/routes/email_routes.py", 1091, "INTENTIONAL", "ImportError assignment_grader → root-import fallback"),
    ("backend/routes/email_routes.py", 1108, "INTENTIONAL", "grading_state missing → pass; comment 'skip' explicit defined fallback"),
    ("backend/routes/email_routes.py", 1116, "INTENTIONAL", "stage_files fail → fallback to scan unstaged; same as 865"),

    # _load_confirmed_filenames / _save_confirmed_filenames
    ("backend/routes/email_routes.py", 1164, "LEGACY", "confirmations file read → empty set; silent loss could cause re-send (not tracked as already-sent)"),
    ("backend/routes/email_routes.py", 1175, "LEGACY", "confirmations file write → print only; same data loss enables double-send"),

    # mark_confirmations_sent_file
    ("backend/routes/email_routes.py", 1219, "LEGACY", "results file write fail during confirmation marking → print only; silent state desync"),

    # _read_focus_comms_output — Codex flagged stderr ignore in outlook output reader
    ("backend/routes/email_routes.py", 1356, "NEEDS_ALERT", "Codex Gate 1: stderr read silent pass; subprocess crash details lost, status can mask failure"),

    # confirm_send — Codex flagged double-send risk
    ("backend/routes/email_routes.py", 1452, "NEEDS_ALERT", "Codex Gate 1: storage_load pending lookup fail → falls back to file; potential double-send retry"),
    ("backend/routes/email_routes.py", 1481, "NEEDS_ALERT", "Codex Gate 1: pending file remove fail in success path → silent retain enables replay double-send"),
    ("backend/routes/email_routes.py", 1494, "LEGACY", "pending file remove fail in error path → silent retain (less critical: error already returned)"),
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
