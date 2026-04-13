"""Auto-classify UNCATEGORIZED exception handlers in the audit file as
INTENTIONAL when the (exception_type, handler_behavior) pattern is
HIGH-CONFIDENCE safe. Everything ambiguous stays UNCATEGORIZED for
manual review.

Per Codex Gate 1 ruling (Phase 2 Task 4):
  - `log.exception + return`          → INTENTIONAL (top-level route guard)
  - Typed (non-Exception) catch + `pass` → INTENTIONAL (documented fallback)
  - any `raise` in the body           → INTENTIONAL (re-raise path)
  - `log.error + return`              → INTENTIONAL (graceful HTTP error)
  - Hotfix 1 _safe_* helpers (log.error, log.error + return, log.error + log.info + pass, etc. inside *_safe_* or _spawn_* parent) → INTENTIONAL (already wired to capture_exception elsewhere)

Explicitly does NOT auto-classify (stays UNCATEGORIZED):
  - bare `Exception` + `pass`
  - any `log.warning` behavior
  - any `print` behavior
  - `other` behavior
These all route to manual review where Phase 1 found 12 LEGACY + 12
NEEDS_ALERT hiding in the ambiguous bucket.
"""
import re
import sys
from pathlib import Path

AUDIT = Path(__file__).resolve().parent.parent / "docs" / "exception-audit-2026-04.md"

ROW_RE = re.compile(
    r"^\| `(?P<file>[^`]+)` \| (?P<line>\d+) \| `(?P<exc>[^`]+)` \| "
    r"(?P<behavior>[^|]+) \| `(?P<parent>[^`]+)` \| (?P<cat>\w+) \|$"
)


def is_typed_non_exception(exc_str: str) -> bool:
    """Return True if exc_str names anything other than bare `Exception`.
    Typed catches (ValueError, KeyError, tuples, module.ClassName) are
    treated as having documented fallback intent."""
    if exc_str == "Exception":
        return False
    if exc_str == "bare except":
        return False
    return True


def is_safe_helper_parent(parent: str) -> bool:
    """Return True if the handler's parent function is one of Hotfix 1's
    _safe_*/spawn helpers that already wire to sentry_sdk.capture_exception."""
    return (
        parent.startswith("_safe_")
        or parent == "_spawn_grading_thread_safe"
        or parent == "_import_from_assignment_grader"
    )


def classify(exc: str, behavior: str, parent: str) -> str | None:
    """Return 'INTENTIONAL' if high-confidence safe, else None."""
    b = behavior.strip()

    # Hotfix 1 helpers — all wire to capture_exception internally.
    if is_safe_helper_parent(parent):
        return "INTENTIONAL"

    # Top-level route guards: log.exception + return (500 or redirect).
    if b == "log.exception + return":
        return "INTENTIONAL"

    # Graceful HTTP error: log.error + return (non-500 response is 4xx).
    if b == "log.error + return":
        return "INTENTIONAL"

    # Any body that raises (re-raise or raise typed-check).
    # Behaviors like "raise + return" or pure "raise".
    if "raise" in b.split(" + "):
        return "INTENTIONAL"

    # Typed (non-Exception) catch + pass = documented fallback.
    if b == "pass" and is_typed_non_exception(exc):
        return "INTENTIONAL"

    # Everything else stays UNCATEGORIZED for manual review.
    return None


def main():
    text = AUDIT.read_text()
    lines = text.splitlines()

    changed = 0
    unchanged_count = 0
    for i, line in enumerate(lines):
        m = ROW_RE.match(line)
        if not m:
            continue
        if m.group("cat") != "UNCATEGORIZED":
            continue
        new_cat = classify(m.group("exc"), m.group("behavior"), m.group("parent"))
        if new_cat is None:
            unchanged_count += 1
            continue
        lines[i] = line.rsplit("|", 2)[0] + f"| {new_cat} |"
        changed += 1

    AUDIT.write_text("\n".join(lines) + "\n")
    print(f"Auto-classified {changed} rows as INTENTIONAL.", file=sys.stderr)
    print(f"Remaining UNCATEGORIZED (manual review bucket): {unchanged_count}",
          file=sys.stderr)


if __name__ == "__main__":
    main()
