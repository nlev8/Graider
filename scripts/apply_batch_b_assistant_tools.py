"""Apply Batch B file 2 categorizations for assistant_tools.py.

Codex Gate 1 locked nuances for this file (tool registry/dispatcher):
  - Dispatcher boundary: INTENTIONAL only when preserving tool-call
    error-dict contract AND not silently normalizing infra faults.
  - Dynamic import (_merge_submodules): INTENTIONAL only with visible
    logging/counting.
  - Arg/schema failures: INTENTIONAL if returned as actionable error
    payload, not coerced.
  - Fan-out aggregation: LEGACY unless best-effort semantics are
    explicit AND failed tools are surfaced.
"""
import re
import sys
from pathlib import Path

AUDIT = Path(__file__).resolve().parent.parent / "docs" / "exception-audit-2026-04.md"

DECISIONS = [
    # Module-level bootstrap
    ("backend/services/assistant_tools.py", 32, "INTENTIONAL", "ImportError storage fallback; bootstrap carveout"),
    ("backend/services/assistant_tools.py", 35, "INTENTIONAL", "ImportError inner fallback; storage_load/save/list_keys = None"),

    # _load_results
    ("backend/services/assistant_tools.py", 242, "LEGACY", "results file read fail → []; silent data loss, same class as app.py:400"),

    # _load_master_csv
    ("backend/services/assistant_tools.py", 329, "LEGACY", "per-row CSV parse → pass; aggregation-skip feeds master grades"),

    # _load_period_class_levels
    ("backend/services/assistant_tools.py", 420, "INTENTIONAL", "per-period meta parse → pass; per-file skip in loader, defined default 'standard'"),

    # _load_accommodations
    ("backend/services/assistant_tools.py", 446, "LEGACY", "per-student accommodation parse → pass; FERPA-adjacent, silent IEP/504 data missing"),

    # _load_settings
    ("backend/services/assistant_tools.py", 463, "INTENTIONAL", "settings parse → pass + return {}; downstream .get() calls handle missing keys"),

    # _load_standards
    ("backend/services/assistant_tools.py", 481, "INTENTIONAL", "primary-path fail → explicit fallback to legacy file path"),
    ("backend/services/assistant_tools.py", 509, "LEGACY", "legacy file parse → return []; silent standards enrichment loss (same class as 2300)"),

    # _load_saved_lessons
    ("backend/services/assistant_tools.py", 546, "LEGACY", "per-lesson parse → pass; aggregation-skip in lesson listing"),

    # _load_roster
    ("backend/services/assistant_tools.py", 631, "INTENTIONAL", "per-period meta.json parse → pass; per-file skip, falls through to roster scan"),
    ("backend/services/assistant_tools.py", 673, "LEGACY", "per-roster CSV parse → pass; aggregation-skip in roster listing"),
    ("backend/services/assistant_tools.py", 693, "LEGACY", "per-Clever-roster JSON → pass; aggregation-skip"),
    ("backend/services/assistant_tools.py", 725, "LEGACY", "ClassLink roster parse → pass; aggregation-skip"),

    # _load_parent_contacts
    ("backend/services/assistant_tools.py", 743, "LEGACY", "parent contacts file read → {}; silent loss, same class as _load_results"),

    # _load_saved_assignments
    ("backend/services/assistant_tools.py", 786, "LEGACY", "per-assignment parse → pass; aggregation-skip"),

    # _load_calendar
    ("backend/services/assistant_tools.py", 804, "INTENTIONAL", "calendar file read → return caller-supplied default; explicit defined degraded mode"),

    # _load_memories
    ("backend/services/assistant_tools.py", 831, "LEGACY", "memory file read → []; silent assistant-memory loss at helper layer"),

    # _load_email_config
    ("backend/services/assistant_tools.py", 852, "LEGACY", "email config parse → pass + {}; silent email config loss"),

    # _merge_submodules
    ("backend/services/assistant_tools.py", 919, "INTENTIONAL", "(ImportError, AttributeError) on submodule registration → all_loaded=False (tracked); optional capability loading with visible counter"),

    # execute_tool
    ("backend/services/assistant_tools.py", 961, "NEEDS_ALERT", "audit_tool_action fail → pass; FERPA audit-write silent swallow; mirror consistency with assistant_routes:1062 NEEDS_ALERT"),
    ("backend/services/assistant_tools.py", 974, "INTENTIONAL", "(ValueError, TypeError) on inspect.signature → kwargs.pop teacher_id; typed fallback"),
    ("backend/services/assistant_tools.py", 979, "LEGACY", "dispatcher boundary Exception → error dict; per Codex blind spot: preserves contract but silently normalizes infra/programming faults; Task 5 adds capture_exception"),
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
