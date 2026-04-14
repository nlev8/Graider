"""Apply Batch B file 5 for settings_routes.py.

Codex Gate 1 rules carried into this file:
  - list_* silent metadata-pass reads → LEGACY (corruption hidden)
  - non-atomic settings writes → LEGACY (potential corruption)
  - dual-write secondary sink after primary success → INTENTIONAL
"""
import re, sys
from pathlib import Path

AUDIT = Path(__file__).resolve().parent.parent / "docs" / "exception-audit-2026-04.md"

DECISIONS = [
    # Module-level bootstrap
    ("backend/routes/settings_routes.py", 28, "INTENTIONAL", "ImportError accommodations → root-import fallback; bootstrap"),
    ("backend/routes/settings_routes.py", 41, "INTENTIONAL", "ImportError storage → outer fallback; bootstrap"),
    ("backend/routes/settings_routes.py", 44, "INTENTIONAL", "ImportError storage → None fallback; bootstrap"),

    # get_students_from_period_file
    ("backend/routes/settings_routes.py", 130, "INTENTIONAL", "ImportError pandas → typed warning; CSV path still works"),
    ("backend/routes/settings_routes.py", 153, "LEGACY", "outer period-file read fail → print + return students=[]; silent partial roster"),

    # parse_csv_headers
    ("backend/routes/settings_routes.py", 261, "INTENTIONAL", "Exception → error dict; tool-style return surfaced"),

    # list_rosters / list_periods / list_documents — Codex Gate 1 list_* rule
    ("backend/routes/settings_routes.py", 348, "LEGACY", "Codex Gate 1: per-roster metadata parse silent pass; corruption hidden"),
    ("backend/routes/settings_routes.py", 490, "LEGACY", "Codex Gate 1: cloud period metadata read silent print; same"),
    ("backend/routes/settings_routes.py", 509, "LEGACY", "Codex Gate 1: local period metadata read silent print; same"),
    ("backend/routes/settings_routes.py", 656, "LEGACY", "Codex Gate 1: per-document metadata pass; same"),

    # upload_period — dual-write secondary
    ("backend/routes/settings_routes.py", 428, "INTENTIONAL", "Supabase mirror save fail after local CSV write succeeded; primary durable write done"),

    # preview_parent_contacts / save_parent_contact_mapping — typed
    ("backend/routes/settings_routes.py", 893, "INTENTIONAL", "ImportError openpyxl → typed error dict"),
    ("backend/routes/settings_routes.py", 1106, "INTENTIONAL", "ImportError openpyxl → typed error dict"),

    # _process_rows
    ("backend/routes/settings_routes.py", 1003, "INTENTIONAL", "(ValueError, TypeError) int parse → raw_id fallback; typed"),

    # get_parent_contacts
    ("backend/routes/settings_routes.py", 1147, "INTENTIONAL", "results merge fail → pass; comment marks best-effort enrichment after primary contacts read"),

    # get_all_student_accommodations
    ("backend/routes/settings_routes.py", 1252, "INTENTIONAL", "cloud period parse → pass; explicit fallback chain to local files"),
    ("backend/routes/settings_routes.py", 1266, "LEGACY", "local period parse → pass; aggregation-skip in id_to_name lookup (silent name-loss)"),

    # _run_focus_import — Codex flagged str(e) leak
    ("backend/routes/settings_routes.py", 1572, "LEGACY", "outer focus-import → state['error']=str(e); failure surfaced via status='failed' BUT raw str(e) leaks internal filesystem/subprocess details (Codex Gate 1 flag)"),

    # _save_parent_contacts
    ("backend/routes/settings_routes.py", 1834, "INTENTIONAL", "RuntimeError on Flask g.user_id → teacher_id=None; typed outside-request-context fallback"),
    ("backend/routes/settings_routes.py", 1842, "INTENTIONAL", "Exception on storage_save retry attempt → continue (designed retry loop, second attempt follows after sleep)"),
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
