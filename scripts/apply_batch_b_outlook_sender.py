"""Apply Batch B file 8 for outlook_sender.py.

Codex Gate 1 pre-lock rules:
  - Silent auth/navigation continuation → NEEDS_ALERT
  - Screenshot artifacts with parent emails + grades → NEEDS_ALERT FERPA
  - Ambiguous send completion / 'done' on EOF → NEEDS_ALERT
"""
import re, sys
from pathlib import Path

AUDIT = Path(__file__).resolve().parent.parent / "docs" / "exception-audit-2026-04.md"

DECISIONS = [
    # navigate_to_outlook — Codex Gate 1: silent auth masking
    ("backend/services/outlook_sender.py", 81,  "NEEDS_ALERT", "Codex Gate 1: portal login wait-for-ADFS silent pass can mask auth failure; navigation continues blind"),
    ("backend/services/outlook_sender.py", 98,  "NEEDS_ALERT", "Codex Gate 1: ADFS login click + load silent pass; same class (auth masking)"),
    ("backend/services/outlook_sender.py", 152, "LEGACY", "New mail button wait silent pass; UI label-difference fallback is less critical than auth but still hides Outlook-UI drift"),

    # send_email per-field
    ("backend/services/outlook_sender.py", 184, "INTENTIONAL", "CC expand button not-visible silent pass; comment 'CC field may already be visible' documents explicit expected-state fallback"),
    ("backend/services/outlook_sender.py", 206, "INTENTIONAL", "per-selector subject-field fill → continue in selector-try loop; raises at end if nothing worked"),
    ("backend/services/outlook_sender.py", 229, "INTENTIONAL", "per-selector body-field fill → continue in selector-try loop; same pattern"),

    # main loop (per-student send + error handling + screenshot)
    ("backend/services/outlook_sender.py", 327, "LEGACY", "outer per-student send fail → emit error + screenshot attempt + continue; mass-send partial loss is observable via emit but not paged"),
    ("backend/services/outlook_sender.py", 332, "NEEDS_ALERT", "Codex Gate 1 FERPA: page.screenshot(ERROR_SCREENSHOT) fail silent pass; screenshot would contain parent emails + grades — silent failure to persist evidence of partial send OR silent persistence of unredacted PII"),
    ("backend/services/outlook_sender.py", 337, "LEGACY", "Discard compose pass; cleanup-only, next iteration opens fresh"),
    ("backend/services/outlook_sender.py", 351, "LEGACY", "outer main() catch → emit error + screenshot; batch-level failure visibility via emit"),
    ("backend/services/outlook_sender.py", 355, "NEEDS_ALERT", "Codex Gate 1 FERPA: same screenshot-save silent fail as 332 but in outer batch-error path"),
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
