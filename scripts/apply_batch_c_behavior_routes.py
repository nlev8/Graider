"""Apply Batch C file 1 for behavior_routes.py.

Codex Gate 1 pre-locks: 172, 287, 378, 387 NEEDS_ALERT (FERPA behavior
query silent failures masking as empty data).
"""
import re, sys
from pathlib import Path

AUDIT = Path(__file__).resolve().parent.parent / "docs" / "exception-audit-2026-04.md"

DECISIONS = [
    ("backend/routes/behavior_routes.py", 172, "NEEDS_ALERT", "Codex Gate 1: Supabase query fail → empty rows + success response; FERPA data masked"),
    ("backend/routes/behavior_routes.py", 202, "INTENTIONAL", "per-event timestamp parse pass; best-effort formatting, event still listed"),
    ("backend/routes/behavior_routes.py", 268, "INTENTIONAL", "(ValueError, TypeError) on limit param → 50 default; typed query-param fallback"),
    ("backend/routes/behavior_routes.py", 287, "NEEDS_ALERT", "Codex Gate 1: same silent FERPA query mask as 172 in events endpoint"),
    ("backend/routes/behavior_routes.py", 361, "INTENTIONAL", "_get_supabase() fail → zero-count debug response; defined degraded mode"),
    ("backend/routes/behavior_routes.py", 378, "NEEDS_ALERT", "Codex Gate 1: sessions query silent fail in debug_behavior_data; masks backend FERPA failure"),
    ("backend/routes/behavior_routes.py", 387, "NEEDS_ALERT", "Codex Gate 1: events query silent fail; same class"),
    ("backend/routes/behavior_routes.py", 421, "LEGACY", "per-period meta.json parse silent pass; aggregation-skip in period_meta"),
    ("backend/routes/behavior_routes.py", 450, "LEGACY", "outer period-CSV scan fail silent; aggregation-skip in roster listing"),
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
