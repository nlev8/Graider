"""Apply Batch B file 10 for assistant_tools_behavior.py.

Codex Gate 1: APPROVE-WITH-CHANGES. FERPA behavior-data severity +
carry-forward from email_routes.py pending-send swallow rule = NEEDS_ALERT.
"""
import re, sys
from pathlib import Path

AUDIT = Path(__file__).resolve().parent.parent / "docs" / "exception-audit-2026-04.md"

DECISIONS = [
    # _load_behavior_events
    ("backend/services/assistant_tools_behavior.py", 78, "INTENTIONAL", "joined query fail → logger.warning + try fallback; defined degraded-mode chain to non-join query"),
    ("backend/services/assistant_tools_behavior.py", 108, "LEGACY", "fallback query also fails → logger.error only; teacher sees empty rows, can't distinguish 'no events' from query failure"),
    ("backend/services/assistant_tools_behavior.py", 139, "INTENTIONAL", "per-event timestamp parse → pass; best-effort HH:MM formatting, event still listed"),

    # _load_settings
    ("backend/services/assistant_tools_behavior.py", 188, "LEGACY", "settings parse fail → {}; corruption hidden (same class as other settings loaders)"),

    # _load_parent_contacts — FERPA recipient-resolution
    ("backend/services/assistant_tools_behavior.py", 198, "NEEDS_ALERT", "parent_contacts parse fail → []; mirrors email_routes.py:51 FERPA recipient-resolution silent loss"),

    # debug_behavior — tool-dispatch surfaced
    ("backend/services/assistant_tools_behavior.py", 329, "INTENTIONAL", "Exception → error dict; caller surfaces via tool dispatch"),

    # _generate_email_ai
    ("backend/services/assistant_tools_behavior.py", 617, "INTENTIONAL", "AI email gen fail → log.warning + return None; caller falls back to default template (defined degraded mode)"),

    # send_behavior_email pending-send — Codex email_routes.py rule
    ("backend/services/assistant_tools_behavior.py", 855, "NEEDS_ALERT", "pending_send storage_save swallow; mirrors email_routes.py:1452 NEEDS_ALERT (replay/double-send risk)"),
    ("backend/services/assistant_tools_behavior.py", 865, "NEEDS_ALERT", "pending_send file fallback swallow; same class (persistence-path silent loss)"),
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
