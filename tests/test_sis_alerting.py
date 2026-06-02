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
    # 2026-05-06: shifted 217/231/245 -> 225/240/255 by PR 6 of SIS compliance
    # hardening sprint (audit_log calls added in get_clever_user). Captures
    # themselves are unchanged — pins track the except blocks.
    ("backend/clever.py", 225),
    ("backend/clever.py", 240),
    ("backend/clever.py", 255),
    # 2026-05-07: original pin at line 54 was the `_clever_audit` except
    # block. PR #227 (audit MAJOR #10 close) made `_clever_audit` delegate
    # to `backend.utils.audit.audit_log` whose own try/except + Sentry
    # capture covers the same failure surface. The pin is removed because
    # the capture moved into central code (still reachable by any caller
    # path), not because Sentry coverage was lost.
    # 2026-05-06: shifted 231/254 -> 238/262 by PR 7 (post-sprint follow-up)
    # adding Returns docstring + `return` keyword in _sync_classes_to_db.
    # 2026-05-07: shifted 238 -> 241 and 262 -> 265 by PR #227 final commit
    # (the round-3 fold added ~9 lines to `_clever_audit`: pre-redaction
    # logger.info hardening + extended docstring). Captures themselves
    # unchanged. Net effect of PR #227 across rounds: -5 lines round-2
    # delegation + +9 lines round-3 redaction = net +3 vs pre-PR. The
    # test allows a window=8 search so this is comfortably within margin.
    # 2026-05-16: shifted 241 -> 310 by PR #395 (Task A multi-enrollment SSO:
    # _create_class_selection + _mint_clever_student_session helpers ~+50
    # lines before _create_clever_student_session). Capture at 312 (outer
    # except 310) unchanged — observability preserved, only the pin tracks.
    # 2026-05-16: shifted 310 -> 325 by PR Task C/C1 (_public_candidates
    # helper + multi-student-row enumeration in _create_clever_student_session).
    # Capture at 327 (outer except 325) unchanged.
    ("backend/routes/clever_routes.py", 325),
    # 2026-05-14: shifted 265 -> 286 by the security-quintet PR (Task 4b
    # added the Clever-ID resolver + filter_roster_to_teacher block to
    # _background_roster_sync — ~21 lines). Capture site at 288 unchanged.
    # 2026-05-16: shifted 286 -> 353 by PR #395 (same Task A helpers +
    # enumeration logic earlier in the file). Capture at 355 (except 353
    # in _background_roster_sync) unchanged.
    # 2026-05-16: shifted 353 -> 368 by PR Task C/C1 (same +~15 lines from
    # the multi-row enumeration block). Capture at 370 (except 368) unchanged.
    ("backend/routes/clever_routes.py", 368),
    # 2026-05-06: shifted 672 -> 692 by PR 3 of SIS compliance hardening sprint
    # (PII redaction in Clever logs added ~20 lines of helper code earlier in
    # the file). 2026-05-07: shifted 692 -> 699 by PR #227 same-as-above net
    # ~+9 line addition in _clever_audit. 2026-05-14: shifted 699 -> 711 by
    # the security-quintet PR (Task 4b additions to _background_roster_sync
    # earlier in the file). Capture site at 713 unchanged.
    # 2026-05-16: shifted 711 -> 796 by PR #395 (Task A: select_clever_class
    # endpoint + the two helpers added ~85 lines earlier). Capture at 798
    # (except sb_err 796, Clever data-deletion Supabase cleanup) unchanged.
    # 2026-05-16: shifted 796 -> 813 by PR Task C/C1 (multi-row enumeration
    # block earlier in the file). Capture at 815 (except sb_err 813) unchanged.
    # 2026-06-01: shifted 813 -> 798 by the Clever→UUID identity-parity branch
    # Task 3 (clever_callback): the inline email-merge block (~24 lines) was
    # replaced by a single resolve_clever_user_id_or_create call earlier in the
    # file, net ~-15 lines above this pin. Then shifted 798 -> 796 by the
    # follow-up dead-import cleanup (commit 074cdde removed `save_clever_link`
    # + `list_all_users` import lines, -2 above this pin). The Clever
    # data-deletion Supabase cleanup `except sb_err` capture (the original
    # meaning of this pin) is now at line 796. Capture itself unchanged.
    ("backend/routes/clever_routes.py", 796),
    # 2026-05-05: shifted 92 -> 102 and 150 -> 161 by PR 1 of SIS compliance
    # hardening sprint, which added 6 lines of imports + the OIDC validation
    # block. Captures themselves are unchanged — pins track the except block.
    # 2026-05-04: shifted 102 -> 115 and 161 -> 174 by PR 2 follow-up commit
    # which added `import re`, _NON_PRINTABLE_RE, _sanitize_for_audit helper
    # (~10 lines), and the LaunchPad audit_log block (~5 lines).
    # 2026-05-05 (PR 2 round-2 fix): shifted 115 -> 106 and 174 -> 165 by
    # removing _sanitize_for_audit + _NON_PRINTABLE_RE + `import re` (Codex
    # gate review found logging raw/truncated state values leaks auth secrets;
    # presence-boolean logging replaces it). Pins track the except blocks.
    # 2026-05-25 (PR #582, ClassLink SSO certification-readiness): the pin at
    # 106 tracked `_link_classlink_account`'s except — that function (email
    # auto-linking) was DELETED for tenant-scoped identity, so its pin is
    # removed (no catch left to protect). The surviving `_trigger_roster_sync`
    # `_bg_sync` capture shifted 165 -> 143 as the file shrank (~52 lines).
    # 2026-05-25: shifted 143 -> 295 by the ClassLink Roster Server cert-parity branch.
    # Task 3 extracted _run_classlink_roster_sync; Task 5 then inserted
    # _classlink_roster_external_id, the auth-code/selection stores,
    # _mint_classlink_student_session, and _create_classlink_student_session ABOVE
    # _trigger_roster_sync. The _bg_sync sentry_sdk.capture_exception (the original
    # meaning of this pin) is now at line 297.
    ("backend/routes/classlink_routes.py", 295),
    # 2026-05-25: NEW pin added by the same branch. Task 5's
    # _create_classlink_student_session has its own try/except that captures via
    # sentry_sdk.capture_exception at line 225. Pinning it explicitly so any future
    # refactor that drops the capture is caught by this SIS regression test.
    ("backend/routes/classlink_routes.py", 223),
    ("backend/routes/oneroster_routes.py", 157),
    ("backend/routes/oneroster_routes.py", 204),
    ("backend/routes/oneroster_routes.py", 218),
    # 2026-05-06: shifted 76/135/168/270/288 -> 105/165/199/302/321 by PR 6 of
    # SIS compliance hardening sprint (ROSTER_SYNC_START / ROSTER_SYNC_COMPLETE
    # / ROSTER_SYNC_FAILED audit_log boundary instrumentation added). Captures
    # themselves are unchanged — pins track the except blocks.
    ("backend/roster_sync.py", 105),
    ("backend/roster_sync.py", 165),
    ("backend/roster_sync.py", 199),
    # 2026-05-25: shifted 302 -> 299 by the ClassLink Roster Server cert-parity branch
    # (Task 4 restructured delete_roster_data to always delete orphan students). The
    # Supabase block's except + capture are now at 299/301.
    ("backend/roster_sync.py", 299),
    # 2026-05-25: shifted 321 -> 318 by the same Task 4 restructure. The OSError except
    # for the local-file cleanup is now at 318 (capture at 320).
    ("backend/roster_sync.py", 318),
    # 2026-05-02: shifted 145 -> 159 by the schema-audit fix that added a
    # two-step query in _discover_teachers (~14 lines). Pin tracks the
    # _save_cursor try-block.
    # 2026-05-14: shifted 159 -> 169 by the security-quintet PR Task 1
    # (added `import hmac` + ~10 lines of hardened _validate_secret).
    # Capture site at 171 unchanged.
    ("backend/routes/sync_routes.py", 169),
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
    # 2026-05-19 Tier 2 Slice 3 PR2: lowered 4 -> 2. The verbatim FERPA
    # cluster extraction moved 8 capture sites (the get_audit_logs reader
    # plus the 6 FERPA route bodies) out of backend/app.py into
    # backend/routes/ferpa_routes.py. origin/main app.py had 10 captures;
    # 2 stay, 8 relocated (conservation 10 = 2 + 8). Net Sentry coverage
    # unchanged; the relocated captures are floor-checked under
    # PR_B_EXPECTED_CAPTURES["backend/routes/ferpa_routes.py"] below.
    "backend/app.py": 2,
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
    # 2026-05-07: lowered 8 -> 7 by PR #227 (audit MAJOR #10 close) which
    # made `audit_log_accommodation` a delegating wrapper. The capture
    # moved into the central `backend.utils.audit.audit_log` (counted in
    # PR_A_EXPECTED_CAPTURES["backend/utils/audit.py"]: 2). Net Sentry
    # coverage unchanged.
    "backend/accommodations.py": 7,
    "backend/app.py": 2,  # 2026-05-19 Tier 2 Slice 3 PR2: lowered 10 -> 2. The verbatim FERPA cluster extraction relocated 8 capture sites (get_audit_logs + the 6 FERPA route bodies) to backend/routes/ferpa_routes.py (origin/main app.py 10 = 2 stay + 8 moved). Net Sentry coverage unchanged; relocated captures floor-checked below.
    "backend/grading/state.py": 2,
    "backend/grading/pipeline.py": 3,  # Phase 3a PR3: 3 captures moved from app.py
    "backend/routes/grading_results_routes.py": 3,  # 2026-05-19 Tier 2 Slice 3 PR1: the 3 captures that moved with the verbatim grading-results cluster out of app.py
    "backend/routes/ferpa_routes.py": 8,  # 2026-05-19 Tier 2 Slice 3 PR2: the 8 captures that moved with the verbatim FERPA cluster (get_audit_logs reader + 6 FERPA route bodies) out of app.py
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
    # Issue #339 (2026-05-14): floor lowered 21 -> 16 after `import_student_data`
    # was refactored to `backend.storage.{save,save_student_history}` for
    # teacher-scoped persistence. The 5 removed captures wrapped raw file
    # reads (`~/.graider_results.json`, history dir, accommodations, ELL,
    # parent contacts); those file accesses now route through `_file_load`
    # in `backend/storage.py`, which logs read failures via the storage
    # logger instead of paging Sentry. Net signal preserved (warnings still
    # land in logs), Sentry noise reduced.
    "backend/services/assistant_tools_student.py": 16,
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
