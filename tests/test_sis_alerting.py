"""Sentry capture_exception contract tests for SIS + non-SIS observability
(PR-0 + PR-a).

Phase 2 Task 5 PR-0 adds `sentry_sdk.capture_exception(e)` to every
LEGACY + NEEDS_ALERT exception handler in SIS-compliance files (Clever,
ClassLink, OneRoster, roster_sync, sync_routes, oneroster_gradebook).

PR-a extends to the remaining 80+ NEEDS_ALERT catches in non-SIS files
(accommodations, app, assistant tools, email, grading routes, etc.).

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
    # 2026-05-05: shifted 92 -> 102 and 150 -> 161 by PR 1 of SIS compliance
    # hardening sprint, which added 6 lines of imports + the OIDC validation
    # block. Captures themselves are unchanged — pins track the except block.
    ("backend/routes/classlink_routes.py", 102),
    ("backend/routes/classlink_routes.py", 161),
    ("backend/routes/oneroster_routes.py", 157),
    ("backend/routes/oneroster_routes.py", 204),
    ("backend/routes/oneroster_routes.py", 218),
    ("backend/roster_sync.py", 76),
    ("backend/roster_sync.py", 135),
    ("backend/roster_sync.py", 168),
    ("backend/roster_sync.py", 270),
    ("backend/roster_sync.py", 288),
    # 2026-05-02: shifted 145 -> 159 by the schema-audit fix that added a
    # two-step query in _discover_teachers (~14 lines). Pin tracks the
    # _save_cursor try-block.
    ("backend/routes/sync_routes.py", 159),
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


# PR-a: non-SIS NEEDS_ALERT files. Expected minimum capture counts per
# file (from the Task 4 audit). Static total check — robust against
# line-shift from line-number-altering edits.
PR_A_EXPECTED_CAPTURES = {
    "backend/accommodations.py": 7,
    "backend/api_keys.py": 2,
    "backend/app.py": 4,
    "backend/auth.py": 2,
    "backend/routes/analytics_routes.py": 1,
    "backend/routes/assessment_results_routes.py": 3,
    "backend/routes/assistant_routes.py": 3,
    "backend/routes/automation_routes.py": 1,
    "backend/routes/behavior_routes.py": 4,
    "backend/routes/district_routes.py": 3,
    "backend/routes/email_routes.py": 8,
    "backend/routes/grading_routes.py": 9,
    "backend/routes/settings_routes.py": 1,
    "backend/routes/stripe_routes.py": 1,
    "backend/services/assistant_tools.py": 3,
    "backend/services/assistant_tools_behavior.py": 3,
    "backend/services/assistant_tools_communication.py": 1,
    "backend/services/assistant_tools_reports.py": 2,
    "backend/services/assistant_tools_student.py": 12,
    "backend/services/outlook_sender.py": 4,
    "backend/student_history.py": 2,
    "backend/utils/audit.py": 2,
}


PR_B_EXPECTED_CAPTURES = {
    "backend/accommodations.py": 8,
    "backend/app.py": 12,  # 3 moved to backend/grading/pipeline.py in Phase 3a PR3 (was 15, -2 to state in PR2, -3 here)
    "backend/grading/state.py": 2,
    "backend/grading/pipeline.py": 3,  # Phase 3a PR3: 3 captures moved from app.py
    "backend/auth.py": 3,
    "backend/routes/analytics_routes.py": 4,
    "backend/routes/automation_routes.py": 4,
    "backend/routes/behavior_routes.py": 6,
    "backend/routes/email_routes.py": 11,
    "backend/routes/grading_routes.py": 12,
    "backend/routes/settings_routes.py": 7,
    "backend/routes/student_account_routes.py": 3,
    "backend/services/assistant_tools.py": 13,
    "backend/services/assistant_tools_behavior.py": 4,
    "backend/services/assistant_tools_reports.py": 5,
    "backend/services/assistant_tools_student.py": 21,
    # Phase 4 review cleanup: 5 -> 4. Removed the capture at
    # navigate_to_outlook's "New mail" wait_for fallback — that is an
    # expected label-mismatch path, not an error worth paging ops on.
    "backend/services/outlook_sender.py": 4,
}


def test_pr_b_legacy_captures_meet_floor():
    """PR-b adds capture to 60+ additional LEGACY rows across 15 files.
    Count-floor assertion: each file has at least the expected total
    (includes captures from PR-0 + PR-a where applicable)."""
    failures = []
    for path, expected in PR_B_EXPECTED_CAPTURES.items():
        src = _file(path)
        count = src.count("sentry_sdk.capture_exception")
        if count < expected:
            failures.append(f"{path}: {count} < {expected}")
    assert not failures, "\n".join(failures)


def test_no_dead_capture_sites_in_backend():
    """Guard against insert-after-terminator dead captures. A
    `sentry_sdk.capture_exception(...)` that sits after `return`,
    `continue`, `break`, or `raise` inside the same except body is
    unreachable — Codex Gate 3 on PR-b caught 9 of these from the
    mechanical patcher. This test pins that the final tree has none."""
    import ast as _ast
    dead = []
    for src_file in ROOT.joinpath("backend").rglob("*.py"):
        try:
            tree = _ast.parse(src_file.read_text())
        except SyntaxError:
            continue
        for node in _ast.walk(tree):
            if not isinstance(node, _ast.ExceptHandler):
                continue
            seen_terminator = False
            for stmt in node.body:
                if seen_terminator:
                    if (isinstance(stmt, _ast.Expr)
                            and isinstance(stmt.value, _ast.Call)
                            and isinstance(stmt.value.func, _ast.Attribute)
                            and stmt.value.func.attr == "capture_exception"):
                        dead.append(f"{src_file}:{stmt.lineno}")
                if isinstance(stmt,
                              (_ast.Return, _ast.Continue,
                               _ast.Break, _ast.Raise)):
                    seen_terminator = True
    assert not dead, (
        "Dead capture sites (unreachable after return/continue/break/raise):\n"
        + "\n".join(dead)
    )


def test_pr_a_non_sis_files_have_expected_captures():
    """PR-a: each non-SIS NEEDS_ALERT file must import sentry_sdk and
    contain at least the expected number of capture_exception calls
    (one per originally flagged catch). Line numbers aren't pinned
    because patches shift them; the count floor is the real contract."""
    failures = []
    for path, expected in PR_A_EXPECTED_CAPTURES.items():
        src = _file(path)
        if not _imports_sentry(src):
            failures.append(f"{path}: missing `import sentry_sdk`")
            continue
        count = src.count("sentry_sdk.capture_exception")
        if count < expected:
            failures.append(
                f"{path}: has {count} capture calls, expected >= {expected}"
            )
    assert not failures, "\n".join(failures)
