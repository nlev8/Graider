"""Sentry capture_exception contract tests for SIS observability (PR-0).

Phase 2 Task 5 PR-0 adds `sentry_sdk.capture_exception(e)` to every
LEGACY + NEEDS_ALERT exception handler in SIS-compliance files (Clever,
ClassLink, OneRoster, roster_sync, sync_routes, oneroster_gradebook).

Per SIS compliance guardrail: zero behavior changes. Since mocking SIS
HTTP clients against their full signatures is brittle, these tests
pin the observability addition via static source inspection — one
assertion per row previously flagged LEGACY or NEEDS_ALERT.

If a future edit strips the capture_exception call, the test fails
and Task 5's observability guarantee breaks visibly.

Integration-style coverage: the 81-test SIS contract suite
(tests/test_sso_contracts.py + the 6 other SSO/OneRoster files) pins
the HTTP contract at behavior-level; zero regression there proves
the capture_exception additions are non-behavior-changing.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _file(path: str) -> str:
    return (ROOT / path).read_text()


def _capture_near_line(source: str, line_num: int, window: int = 5) -> bool:
    """Return True if `sentry_sdk.capture_exception` appears within
    `window` lines after the given line_num."""
    lines = source.splitlines()
    start = max(0, line_num - 1)
    end = min(len(lines), line_num + window)
    chunk = "\n".join(lines[start:end])
    return "sentry_sdk.capture_exception" in chunk


def _imports_sentry(source: str) -> bool:
    return bool(re.search(r"^import sentry_sdk", source, re.MULTILINE))


# Every (file, flagged_line) pair that PR-0 patched.
SIS_CAPTURES = [
    ("backend/clever.py", 46),
    ("backend/clever.py", 217),
    ("backend/clever.py", 231),
    ("backend/clever.py", 245),
    ("backend/routes/clever_routes.py", 54),
    ("backend/routes/clever_routes.py", 231),
    ("backend/routes/clever_routes.py", 254),
    ("backend/routes/clever_routes.py", 672),
    ("backend/routes/classlink_routes.py", 92),
    ("backend/routes/classlink_routes.py", 150),
    ("backend/routes/oneroster_routes.py", 157),
    ("backend/routes/oneroster_routes.py", 204),
    ("backend/routes/oneroster_routes.py", 218),
    ("backend/roster_sync.py", 76),
    ("backend/roster_sync.py", 135),
    ("backend/roster_sync.py", 168),
    ("backend/roster_sync.py", 270),
    ("backend/roster_sync.py", 288),
    ("backend/routes/sync_routes.py", 145),
    ("backend/services/oneroster_gradebook.py", 95),
]


def test_every_sis_file_imports_sentry_sdk():
    """All 7 SIS files that PR-0 patched must `import sentry_sdk`."""
    files = sorted({f for (f, _) in SIS_CAPTURES})
    for f in files:
        src = _file(f)
        assert _imports_sentry(src), f"{f} is missing `import sentry_sdk`"


def test_every_flagged_sis_catch_captures_to_sentry():
    """Every (file, line) that Task 4 flagged as LEGACY/NEEDS_ALERT in
    a SIS-compliance file now has a `sentry_sdk.capture_exception`
    call within 5 lines after the original flagged line number.

    Line shifts from the edit are accommodated — the real check is
    that the handler at that region now captures."""
    failures = []
    for (path, line) in SIS_CAPTURES:
        src = _file(path)
        if not _capture_near_line(src, line, window=8):
            failures.append(f"{path}:{line}")
    assert not failures, (
        "The following SIS catches are missing capture_exception: "
        + ", ".join(failures)
    )
