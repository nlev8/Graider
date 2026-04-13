"""Apply Batch B file 7 for analytics_routes.py.

Codex Gate 1 pre-locks:
  124 → LEGACY (blanket analytics fetch exception → empty stats)
  354 → LEGACY (silent assignment-name aliasing drop)
  cleanup_master_csv has WRITES (not read-only) — 882 is pre-write
    approval-lookup read; silent drop leads to destructive write
    (same class as import merge failures, NEEDS_ALERT).
"""
import re, sys
from pathlib import Path

AUDIT = Path(__file__).resolve().parent.parent / "docs" / "exception-audit-2026-04.md"

DECISIONS = [
    # _find_master_grades
    ("backend/routes/analytics_routes.py", 33, "INTENTIONAL", "per-folder path-scan pass in master_grades locator; best-effort filesystem search"),

    # _fetch_assessment_analytics
    ("backend/routes/analytics_routes.py", 60, "INTENTIONAL", "ImportError supabase_client → root-import fallback; bootstrap"),
    ("backend/routes/analytics_routes.py", 124, "LEGACY", "Codex Gate 1: blanket Exception → empty assessment_stats; teacher-facing analytics silently degraded"),

    # _analytics_from_results
    ("backend/routes/analytics_routes.py", 135, "INTENTIONAL", "ImportError storage → root-import fallback; bootstrap"),

    # _load_valid_assignment_names
    ("backend/routes/analytics_routes.py", 354, "LEGACY", "Codex Gate 1: per-config alias merge silent pass; undercounts filtered analytics"),

    # get_analytics
    ("backend/routes/analytics_routes.py", 390, "INTENTIONAL", "ImportError storage primary → root-import fallback"),
    ("backend/routes/analytics_routes.py", 393, "INTENTIONAL", "ImportError storage inner → _storage_load=None; defined degraded mode"),

    # export_district_report
    ("backend/routes/analytics_routes.py", 695, "INTENTIONAL", "cloud settings read fail → pass; explicit fallback to local file"),
    ("backend/routes/analytics_routes.py", 708, "INTENTIONAL", "local file settings read fail → pass; explicit fallback to passed defaults"),
    ("backend/routes/analytics_routes.py", 737, "INTENTIONAL", "storage results iteration fail → pass; explicit fallback to master_grades.csv"),

    # cleanup_master_csv — Codex flagged as write route
    ("backend/routes/analytics_routes.py", 862, "INTENTIONAL", "ImportError parse_filename → sys.path fallback; bootstrap-style typed chain"),
    ("backend/routes/analytics_routes.py", 867, "INTENTIONAL", "ImportError after sys.path → parse_filename=None; defined degraded mode"),
    ("backend/routes/analytics_routes.py", 882, "NEEDS_ALERT", "Codex Gate 1: approval_lookup read silent pass BEFORE destructive master_grades.csv cleanup write at lines 980-987; pre-write discard class (same as import merge overwrite)"),

    # _is_corrupted_row
    ("backend/routes/analytics_routes.py", 925, "INTENTIONAL", "ValueError on float(score) → return True (corrupted marker); typed explicit semantic"),
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
