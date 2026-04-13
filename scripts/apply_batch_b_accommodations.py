"""Apply Batch B file 9 for backend/accommodations.py.

Codex Gate 1: REDIRECT raised broader design concerns (prompt injection,
lockless writes, audit bypass) — those are out of scope for exception
categorization but inform severity. Core rule from earlier files:
silent IEP/504 parse/write failure = NEEDS_ALERT (same class as
assistant_tools.py:446 which was flipped to NEEDS_ALERT).
"""
import re, sys
from pathlib import Path

AUDIT = Path(__file__).resolve().parent.parent / "docs" / "exception-audit-2026-04.md"

DECISIONS = [
    # Module bootstrap
    ("backend/accommodations.py", 25, "INTENTIONAL", "ImportError storage → root-import fallback; bootstrap"),
    ("backend/accommodations.py", 28, "INTENTIONAL", "ImportError inner → None fallback; bootstrap"),

    # audit_log_accommodation — FERPA write path
    ("backend/accommodations.py", 54, "NEEDS_ALERT", "FERPA audit log append fail → print only; mirrors assistant_routes:1062 + assistant_tools:961 NEEDS_ALERT"),

    # load_presets (custom)
    ("backend/accommodations.py", 268, "NEEDS_ALERT", "custom presets parse fail → silent drop; presets define IEP/504 semantics, drop affects grading differentiation"),

    # save_preset / delete_preset / save_student_accommodations / clear_all — FERPA IEP/504 writes
    ("backend/accommodations.py", 303, "NEEDS_ALERT", "preset save fail → returns False to caller; FERPA IEP/504 write failure should page even if caller surfaces"),
    ("backend/accommodations.py", 333, "NEEDS_ALERT", "preset delete fail → returns False; same class"),
    ("backend/accommodations.py", 382, "NEEDS_ALERT", "student accommodation save fail → returns False; FERPA IEP/504 write"),
    ("backend/accommodations.py", 694, "NEEDS_ALERT", "clear_all_accommodations fail → returns False; destructive FERPA-wide mutation silent-fail path"),

    # load_student_accommodations — mirrors assistant_tools.py:446 (Codex flip)
    ("backend/accommodations.py", 363, "NEEDS_ALERT", "student accommodations parse fail → return {}; silent IEP/504 parse loss; mirrors assistant_tools.py:446 NEEDS_ALERT"),

    # _get_ell_language
    ("backend/accommodations.py", 460, "LEGACY", "ELL language lookup fail → pass + return None; downstream gets English-only feedback instead of bilingual; degradation but not FERPA-audit-critical write"),
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
