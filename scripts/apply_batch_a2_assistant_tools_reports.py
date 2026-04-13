"""Apply Batch A.2 file 2 categorizations for assistant_tools_reports.py.

Codex Gate 1 pre-locked 5 rows:
  1831 → LEGACY          (get_recent_lessons silent skip in loop)
  1898 → LEGACY          (get_calendar fallback silent disappear)
  2122 → LEGACY          (save_assignment_config merge can overwrite)
  2337 → NEEDS_ALERT     (send_parent_emails pending-send preview fail)
  2484 → NEEDS_ALERT     (send_focus_comms pending-send preview fail)

Remaining 30 rows follow the pattern: most are `except Exception as e:
return {"error": ...}` — tool dispatch forwards the error dict back to
the model/UI, which shows it to the teacher. Per Codex Gate 1 answer
B: INTENTIONAL for this file because callers surface the failure.
"""
import re
import sys
from pathlib import Path

AUDIT = Path(__file__).resolve().parent.parent / "docs" / "exception-audit-2026-04.md"

DECISIONS = [
    # Module-level
    ("backend/services/assistant_tools_reports.py", 34, "INTENTIONAL", "ImportError storage fallback; bootstrap carveout"),
    ("backend/services/assistant_tools_reports.py", 37, "INTENTIONAL", "ImportError inner fallback; same pattern"),

    # _match_standards
    ("backend/services/assistant_tools_reports.py", 750, "INTENTIONAL", "(ValueError, TypeError) on DOK parse → permissive default; typed fallback"),

    # _parse_curriculum_map_for_dates / _parse_map_date
    ("backend/services/assistant_tools_reports.py", 792, "INTENTIONAL", "per-file in DOCUMENTS_DIR loop; continue on parse fail, try next"),
    ("backend/services/assistant_tools_reports.py", 804, "INTENTIONAL", "ImportError docx → return None; typed defined degraded mode"),
    ("backend/services/assistant_tools_reports.py", 811, "INTENTIONAL", "date format parse fail → return None; caller distinguishes via None"),
    ("backend/services/assistant_tools_reports.py", 823, "INTENTIONAL", "ValueError in format-match loop → try next format; typed iteration"),

    # _extract_pdf_text / _extract_docx_text
    ("backend/services/assistant_tools_reports.py", 1015, "INTENTIONAL", "ImportError → explicit error string with install hint; defined degraded mode"),
    ("backend/services/assistant_tools_reports.py", 1017, "INTENTIONAL", "Exception → explicit error string, not fake success"),
    ("backend/services/assistant_tools_reports.py", 1049, "INTENTIONAL", "ImportError docx → explicit error string; same"),
    ("backend/services/assistant_tools_reports.py", 1051, "INTENTIONAL", "Exception on docx parse → explicit error string"),

    # create_focus_assignment
    ("backend/services/assistant_tools_reports.py", 1129, "INTENTIONAL", "FileNotFoundError Node.js missing → typed error dict; defined tool-error shape"),
    ("backend/services/assistant_tools_reports.py", 1131, "INTENTIONAL", "Exception → error dict; tool dispatch forwards to model/UI"),

    # generate_worksheet_tool / generate_document_tool
    ("backend/services/assistant_tools_reports.py", 1570, "INTENTIONAL", "ImportError → typed error dict"),
    ("backend/services/assistant_tools_reports.py", 1572, "INTENTIONAL", "Exception → error dict; caller surfaces"),
    ("backend/services/assistant_tools_reports.py", 1585, "INTENTIONAL", "ImportError → typed error dict"),
    ("backend/services/assistant_tools_reports.py", 1587, "INTENTIONAL", "Exception → error dict"),

    # save_document_style_tool / list_document_styles_tool
    ("backend/services/assistant_tools_reports.py", 1674, "INTENTIONAL", "Exception → error dict; caller surfaces"),
    ("backend/services/assistant_tools_reports.py", 1684, "INTENTIONAL", "Exception → error dict"),

    # get_recent_lessons — Codex pre-locked
    ("backend/services/assistant_tools_reports.py", 1831, "LEGACY", "Codex Gate 1: silent drop of bad lesson files in aggregation loop; returns partial teacher-facing data with no warning"),

    # get_calendar — Codex pre-locked
    ("backend/services/assistant_tools_reports.py", 1898, "LEGACY", "Codex Gate 1: calendar fallback silently disappears"),

    # list_resources_tool
    ("backend/services/assistant_tools_reports.py", 2015, "INTENTIONAL", "per-file meta.json parse fail → skip meta; resource still listed"),
    ("backend/services/assistant_tools_reports.py", 2025, "INTENTIONAL", "outer DOCUMENTS_DIR read fail → error dict surfaced via tool dispatch"),

    # read_resource_tool
    ("backend/services/assistant_tools_reports.py", 2063, "INTENTIONAL", "Exception on file read → error dict with filename; caller surfaces"),
    ("backend/services/assistant_tools_reports.py", 2088, "INTENTIONAL", "meta.json parse fail → pass; optional enrichment of resource metadata"),

    # save_assignment_config — Codex pre-locked
    ("backend/services/assistant_tools_reports.py", 2122, "LEGACY", "Codex Gate 1: config merge can overwrite after unreadable prior config; silent data-loss"),

    # send_parent_emails
    ("backend/services/assistant_tools_reports.py", 2337, "NEEDS_ALERT", "Codex Gate 1: pending-send preview writes fail silently in parent-contact flows"),
    ("backend/services/assistant_tools_reports.py", 2359, "INTENTIONAL", "ImportError outlook_sender → typed error dict"),
    ("backend/services/assistant_tools_reports.py", 2361, "INTENTIONAL", "Exception → error dict"),

    # send_focus_comms
    ("backend/services/assistant_tools_reports.py", 2396, "INTENTIONAL", "Exception on Focus roster load → error dict surfaces to caller"),
    ("backend/services/assistant_tools_reports.py", 2484, "NEEDS_ALERT", "Codex Gate 1: pending-send preview writes fail silently in comms flows"),
    ("backend/services/assistant_tools_reports.py", 2505, "INTENTIONAL", "ImportError Focus Comms route → typed error dict"),
    ("backend/services/assistant_tools_reports.py", 2507, "INTENTIONAL", "Exception → error dict"),

    # confirm_and_send
    ("backend/services/assistant_tools_reports.py", 2541, "INTENTIONAL", "Exception on pending file read → error dict"),
    ("backend/services/assistant_tools_reports.py", 2643, "INTENTIONAL", "Exception launching send → error dict surfaces to caller"),
]


ROW_RE = re.compile(
    r"^\| `(?P<file>[^`]+)` \| (?P<line>\d+) \| `(?P<exc>[^`]+)` \| "
    r"(?P<behavior>[^|]+) \| `(?P<parent>[^`]+)` \| (?P<cat>\w+) \|$"
)


def main():
    text = AUDIT.read_text()
    lines = text.splitlines()
    dmap = {(f, line): cat for (f, line, cat, _) in DECISIONS}
    applied = 0
    mismatches = []
    not_found = list(dmap.keys())

    for i, line_text in enumerate(lines):
        m = ROW_RE.match(line_text)
        if not m:
            continue
        key = (m.group("file"), int(m.group("line")))
        if key not in dmap:
            continue
        if m.group("cat") != "UNCATEGORIZED":
            mismatches.append((key, m.group("cat"), dmap[key]))
            not_found.remove(key)
            continue
        lines[i] = line_text.rsplit("|", 2)[0] + f"| {dmap[key]} |"
        applied += 1
        not_found.remove(key)

    AUDIT.write_text("\n".join(lines) + "\n")
    print(f"Applied {applied}/{len(DECISIONS)}", file=sys.stderr)
    if mismatches:
        for k, existing, intended in mismatches:
            print(f"SKIP {k}: was {existing}, would have been {intended}", file=sys.stderr)
    if not_found:
        for k in not_found:
            print(f"NOT FOUND {k}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
