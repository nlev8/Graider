"""One-shot replay of Phase 1's 86 exception categorizations from commit
9f322b5 onto the regenerated docs/exception-audit-2026-04.md.

Not a permanent tool — run once at the start of Task 4. Matches rows by
(file, parent_function, exception_type, handler_behavior) to be resilient
to line-number shifts caused by Hotfix 1 (which modified portal_grading.py
and student_account_routes.py). When multiple rows match within a file,
picks the closest by order of appearance.

Fails loud if any of the 86 Phase 1 rows can't be uniquely matched.
"""
import re
import subprocess
import sys
from pathlib import Path

AUDIT = Path(__file__).resolve().parent.parent / "docs" / "exception-audit-2026-04.md"
PHASE1_COMMIT = "9f322b5"

ROW_RE = re.compile(
    r"^\| `(?P<file>[^`]+)` \| (?P<line>\d+) \| `(?P<exc>[^`]+)` \| "
    r"(?P<behavior>[^|]+) \| `(?P<parent>[^`]+)` \| (?P<cat>\w+) \|$"
)


def parse_rows(markdown_text):
    rows = []
    for i, line in enumerate(markdown_text.splitlines()):
        m = ROW_RE.match(line)
        if m:
            rows.append({
                "idx": i,
                "file": m.group("file"),
                "line": int(m.group("line")),
                "exc": m.group("exc"),
                "behavior": m.group("behavior").strip(),
                "parent": m.group("parent"),
                "cat": m.group("cat"),
            })
    return rows


def get_phase1_audit():
    """Extract the audit file contents from commit 9f322b5."""
    out = subprocess.run(
        ["git", "show", f"{PHASE1_COMMIT}:docs/exception-audit-2026-04.md"],
        capture_output=True, text=True, check=True,
    )
    return out.stdout


def replay():
    phase1_rows = [r for r in parse_rows(get_phase1_audit())
                   if r["cat"] in ("INTENTIONAL", "LEGACY", "NEEDS_ALERT")]
    print(f"Phase 1 rows with categories: {len(phase1_rows)}", file=sys.stderr)

    current_text = AUDIT.read_text()
    current_lines = current_text.splitlines()
    current_rows = parse_rows(current_text)

    matches = {}      # current-row idx -> category
    unmatched = []    # phase 1 rows that couldn't be uniquely matched
    ambiguous = []    # phase 1 rows with multiple matches after tiebreaking

    # Track which current rows have already been claimed by a phase1 row so
    # two phase1 rows don't steal the same current row.
    claimed = set()

    for p1 in phase1_rows:
        candidates = [
            (idx, r) for idx, r in enumerate(current_rows)
            if (r["file"] == p1["file"]
                and r["parent"] == p1["parent"]
                and r["exc"] == p1["exc"]
                and r["behavior"] == p1["behavior"]
                and idx not in claimed)
        ]
        if len(candidates) == 0:
            unmatched.append(p1)
        elif len(candidates) == 1:
            idx, _ = candidates[0]
            claimed.add(idx)
            matches[current_rows[idx]["idx"]] = p1["cat"]
        else:
            # Multiple candidates in the same (file, parent, exc, behavior)
            # bucket — pick the one whose line is closest to the Phase 1 line.
            candidates.sort(key=lambda c: abs(c[1]["line"] - p1["line"]))
            idx, _ = candidates[0]
            claimed.add(idx)
            matches[current_rows[idx]["idx"]] = p1["cat"]
            ambiguous.append((p1, len(candidates)))

    if unmatched:
        print(f"\nUNMATCHED {len(unmatched)} rows (hotfix may have removed them):", file=sys.stderr)
        for p1 in unmatched:
            print(f"  {p1['file']}:{p1['line']} parent={p1['parent']} "
                  f"behavior={p1['behavior']!r} was {p1['cat']}", file=sys.stderr)

    if ambiguous:
        print(f"\nAMBIGUOUS {len(ambiguous)} rows (closest-line tiebreaker used):", file=sys.stderr)
        for p1, count in ambiguous[:5]:
            print(f"  {p1['file']}:{p1['line']} had {count} candidates", file=sys.stderr)

    # Write back
    new_lines = list(current_lines)
    for idx, cat in matches.items():
        new_lines[idx] = new_lines[idx].rsplit("|", 2)[0] + f"| {cat} |"

    AUDIT.write_text("\n".join(new_lines) + "\n")
    print(f"\nApplied {len(matches)} categorizations. Remaining UNCATEGORIZED: "
          f"{sum(1 for r in current_rows if r['cat'] == 'UNCATEGORIZED') - len(matches)}",
          file=sys.stderr)


if __name__ == "__main__":
    replay()
