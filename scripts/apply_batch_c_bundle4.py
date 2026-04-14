"""Batch C bundle 4: elevenlabs + assistant_tools_automation +
district_routes + oneroster + staging + seo_service (22 rows).
Codex Gate 1 pre-locked district_routes NA paths + automation LEG."""
import re, sys
from pathlib import Path

AUDIT = Path(__file__).resolve().parent.parent / "docs" / "exception-audit-2026-04.md"

DECISIONS = [
    # elevenlabs_service.py
    ("backend/services/elevenlabs_service.py", 17, "INTENTIONAL", "ImportError websocket → None; bootstrap"),
    ("backend/services/elevenlabs_service.py", 204, "INTENTIONAL", "EOS send pass on close; cleanup best-effort"),
    ("backend/services/elevenlabs_service.py", 227, "INTENTIONAL", "keepalive send fail → break; typed loop exit"),
    ("backend/services/elevenlabs_service.py", 259, "INTENTIONAL", "_on_message flush-done pass; state-machine best-effort"),

    # assistant_tools_automation.py
    ("backend/services/assistant_tools_automation.py", 14, "INTENTIONAL", "ImportError storage → root; bootstrap"),
    ("backend/services/assistant_tools_automation.py", 17, "INTENTIONAL", "ImportError inner → None; bootstrap"),
    ("backend/services/assistant_tools_automation.py", 105, "LEGACY", "Codex Gate 1: list_automations per-workflow silent skip (corrupt JSON hidden from teacher)"),
    ("backend/services/assistant_tools_automation.py", 192, "LEGACY", "Codex Gate 1: run_automation per-workflow silent skip (same class)"),

    # district_routes.py — Codex Gate 1 NEEDS_ALERT
    ("backend/routes/district_routes.py", 82, "NEEDS_ALERT", "Codex Gate 1: provider-switch classes query fail → log.warning + return 0; cleanup mask"),
    ("backend/routes/district_routes.py", 128, "NEEDS_ALERT", "Codex Gate 1: per-class delete fail log.warning + continue; destructive partial"),
    ("backend/routes/district_routes.py", 138, "NEEDS_ALERT", "Codex Gate 1: per-student delete pass; destructive partial mask"),
    ("backend/routes/district_routes.py", 429, "INTENTIONAL", "test_connection fail → log.warning + 502 error JSON; surfaced to admin UI"),

    # oneroster.py — SIS compliance: no behavior change
    ("backend/services/oneroster.py" if False else "backend/oneroster.py", 203, "INTENTIONAL", "demographics fetch fail → log.info('optional'); explicit optional-enrichment"),
    ("backend/oneroster.py", 423, "INTENTIONAL", "per-teacher config read log.debug; optional"),
    ("backend/oneroster.py", 435, "INTENTIONAL", "teacher_sourced_id load pass; optional enrichment"),
    ("backend/oneroster.py", 446, "INTENTIONAL", "district config read log.debug; optional"),

    # staging.py
    ("backend/staging.py", 145, "INTENTIONAL", "OSError stat() → continue; per-file skip in scan"),
    ("backend/staging.py", 192, "INTENTIONAL", "OSError stat() → curr_size=None; typed degraded"),
    ("backend/staging.py", 204, "INTENTIONAL", "OSError stat() → file_size=-1; typed degraded"),

    # seo_service.py
    ("backend/services/seo_service.py", 28, "INTENTIONAL", "ImportError anthropic → None + error msg; typed bootstrap"),
    ("backend/services/seo_service.py", 50, "INTENTIONAL", "json.JSONDecodeError → error dict; typed surfaced"),
    ("backend/services/seo_service.py", 52, "INTENTIONAL", "outer Exception → error dict; surfaced to caller"),
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
