"""PR-a scripted patcher: add sentry_sdk.capture_exception to all 81
non-SIS NEEDS_ALERT catches from Task 4 audit.

(Note: the audit flagged 84 rows, but 3 were pre-resolved in the
portal_grading.py `_safe_*` helpers landed by Hotfix 1 / PR #52.
Those 3 rows — 474, 499, 523 — are omitted from this patcher's ROWS
list below. The `test_sis_alerting.py::test_pr_a_non_sis_files_have_expected_captures`
static assertion scopes to the 23 files this patcher actually modifies.)

Strategy (matches PR-0 manual pattern):
  1. Ensure `import sentry_sdk` at module level.
  2. For each flagged except at (file, line):
     a. If bare `except X:` without `as <name>`, rename to `as e:`.
     b. Locate first non-blank line of body.
     c. If body is just `pass`, replace with `sentry_sdk.capture_exception(<name>)`.
     d. Else insert `sentry_sdk.capture_exception(<name>)` AFTER the
        first body line (so logger.warning fires first, matching PR-0).

Idempotent: skips catches that already contain `sentry_sdk.capture_exception`
within 8 lines of the except line.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# (file, line) pairs — 81 non-SIS NEEDS_ALERT rows from Task 4 audit.
# SIS files (clever*, classlink*, oneroster*, roster_sync, sync_routes,
# lti_routes, oneroster_gradebook) were handled in PR-0.
ROWS = [
    # accommodations.py — 7 rows (FERPA IEP/504)
    ("backend/accommodations.py", 54),
    ("backend/accommodations.py", 268),
    ("backend/accommodations.py", 303),
    ("backend/accommodations.py", 333),
    ("backend/accommodations.py", 363),
    ("backend/accommodations.py", 382),
    ("backend/accommodations.py", 694),

    # analytics_routes.py — 1 row
    ("backend/routes/analytics_routes.py", 882),

    # api_keys.py — 2 rows
    ("backend/api_keys.py", 91),
    ("backend/api_keys.py", 124),

    # app.py — 4 rows
    ("backend/app.py", 175),
    ("backend/app.py", 1690),
    ("backend/app.py", 2032),
    ("backend/app.py", 2229),

    # assessment_results_routes.py — 3 rows
    ("backend/routes/assessment_results_routes.py", 170),
    ("backend/routes/assessment_results_routes.py", 233),
    ("backend/routes/assessment_results_routes.py", 308),

    # assistant_routes.py — 3 rows
    ("backend/routes/assistant_routes.py", 1062),
    ("backend/routes/assistant_routes.py", 1964),
    ("backend/routes/assistant_routes.py", 2039),

    # assistant_tools.py — 3 rows
    ("backend/services/assistant_tools.py", 329),
    ("backend/services/assistant_tools.py", 446),
    ("backend/services/assistant_tools.py", 961),

    # assistant_tools_behavior.py — 3 rows
    ("backend/services/assistant_tools_behavior.py", 108),
    ("backend/services/assistant_tools_behavior.py", 198),
    ("backend/services/assistant_tools_behavior.py", 865),

    # assistant_tools_communication.py — 1 row
    ("backend/services/assistant_tools_communication.py", 395),

    # assistant_tools_reports.py — 2 rows
    ("backend/services/assistant_tools_reports.py", 2337),
    ("backend/services/assistant_tools_reports.py", 2484),

    # assistant_tools_student.py — 12 rows
    ("backend/services/assistant_tools_student.py", 428),
    ("backend/services/assistant_tools_student.py", 684),
    ("backend/services/assistant_tools_student.py", 691),
    ("backend/services/assistant_tools_student.py", 724),
    ("backend/services/assistant_tools_student.py", 734),
    ("backend/services/assistant_tools_student.py", 749),
    ("backend/services/assistant_tools_student.py", 755),
    ("backend/services/assistant_tools_student.py", 900),
    ("backend/services/assistant_tools_student.py", 938),
    ("backend/services/assistant_tools_student.py", 972),
    ("backend/services/assistant_tools_student.py", 990),
    ("backend/services/assistant_tools_student.py", 1007),

    # auth.py — 2 rows
    ("backend/auth.py", 30),
    ("backend/auth.py", 45),

    # automation_routes.py — 1 row
    ("backend/routes/automation_routes.py", 258),

    # behavior_routes.py — 4 rows
    ("backend/routes/behavior_routes.py", 172),
    ("backend/routes/behavior_routes.py", 287),
    ("backend/routes/behavior_routes.py", 378),
    ("backend/routes/behavior_routes.py", 387),

    # district_routes.py — 3 rows
    ("backend/routes/district_routes.py", 82),
    ("backend/routes/district_routes.py", 128),
    ("backend/routes/district_routes.py", 138),

    # email_routes.py — 8 rows
    ("backend/routes/email_routes.py", 51),
    ("backend/routes/email_routes.py", 267),
    ("backend/routes/email_routes.py", 999),
    ("backend/routes/email_routes.py", 1219),
    ("backend/routes/email_routes.py", 1356),
    ("backend/routes/email_routes.py", 1452),
    ("backend/routes/email_routes.py", 1481),
    ("backend/routes/email_routes.py", 1494),

    # grading_routes.py — 9 rows
    ("backend/routes/grading_routes.py", 163),
    ("backend/routes/grading_routes.py", 182),
    ("backend/routes/grading_routes.py", 204),
    ("backend/routes/grading_routes.py", 212),
    ("backend/routes/grading_routes.py", 287),
    ("backend/routes/grading_routes.py", 371),
    ("backend/routes/grading_routes.py", 1509),
    ("backend/routes/grading_routes.py", 1525),
    ("backend/routes/grading_routes.py", 1549),

    # notebooklm_service.py — 3 rows
    ("backend/services/notebooklm_service.py", 259),
    ("backend/services/notebooklm_service.py", 502),
    ("backend/services/notebooklm_service.py", 810),

    # outlook_sender.py — 4 rows
    ("backend/services/outlook_sender.py", 81),
    ("backend/services/outlook_sender.py", 98),
    ("backend/services/outlook_sender.py", 332),
    ("backend/services/outlook_sender.py", 355),

    # portal_grading.py — 3 rows (474, 499, 523) OMITTED: Hotfix 1 / PR #52
    # restructured those into `_safe_generate_feedback`, `_safe_save_results`,
    # `_safe_update_submission` helpers which already call
    # sentry_sdk.capture_exception. Current capture count is 7 (3 _safe_*
    # helpers + thread-top-level + thread-spawn + import-fallback + etc).

    # settings_routes.py — 1 row
    ("backend/routes/settings_routes.py", 1572),

    # student_history.py — 2 rows
    ("backend/student_history.py", 79),
    ("backend/student_history.py", 104),

    # stripe_routes.py — 1 row
    ("backend/routes/stripe_routes.py", 261),

    # utils/audit.py — 2 rows
    ("backend/utils/audit.py", 38),
    ("backend/utils/audit.py", 56),
]


EXCEPT_RE = re.compile(
    r"^(\s*)except\s+([^\s:]+(?:\s*,\s*[^\s:]+)*|\([^)]+\))"
    r"(?:\s+as\s+(\w+))?\s*:\s*(?:#.*)?$"
)


def ensure_sentry_import(src_lines: list[str]) -> tuple[list[str], bool]:
    """Insert `import sentry_sdk` near the other imports if missing."""
    for line in src_lines:
        if re.match(r"^import sentry_sdk\b", line):
            return src_lines, False
    # Find last import line in the top ~50 lines.
    last_import = -1
    for i, line in enumerate(src_lines[:80]):
        if re.match(r"^(from|import)\s+\S", line):
            last_import = i
    if last_import < 0:
        return src_lines, False
    src_lines.insert(last_import + 1, "import sentry_sdk")
    return src_lines, True


def patch_catch(src_lines: list[str], line_num: int) -> tuple[bool, str]:
    """Patch the except handler at src_lines[line_num - 1].
    Returns (patched, msg)."""
    idx = line_num - 1
    if idx < 0 or idx >= len(src_lines):
        return False, f"line {line_num} out of range"

    # Idempotence: skip if capture already present within window
    window = "\n".join(src_lines[idx:idx + 8])
    if "sentry_sdk.capture_exception" in window:
        return False, "already patched"

    m = EXCEPT_RE.match(src_lines[idx])
    if not m:
        return False, f"no except match: {src_lines[idx]!r}"
    indent, exc_types, binding = m.group(1), m.group(2), m.group(3)

    if binding is None:
        # Rename bare except to bind as `e`
        binding = "e"
        src_lines[idx] = f"{indent}except {exc_types.strip()} as {binding}:"

    inner_indent = indent + "    "
    capture_line = f"{inner_indent}sentry_sdk.capture_exception({binding})"

    # Strategy:
    # - If next line is exactly "<inner_indent>pass", replace it with capture.
    # - Else insert capture AFTER the first non-blank body line (so logger
    #   fires first, matching PR-0 pattern).
    if idx + 1 >= len(src_lines):
        return False, "except at EOF"

    next_line = src_lines[idx + 1]
    if next_line.strip() == "pass" and next_line.startswith(inner_indent):
        src_lines[idx + 1] = capture_line
        return True, "replaced pass"

    # Find first non-blank body line after the except.
    j = idx + 1
    while j < len(src_lines) and src_lines[j].strip() == "":
        j += 1
    if j >= len(src_lines):
        return False, "no body"
    # Insert capture line AFTER src_lines[j] (the first body statement).
    # But preserve continuations: if line j ends with `,` or `(` unclosed,
    # skip until statement-end. For simplicity, only handle `logger.x(...)`
    # single-line statements here — multi-line args are rare in our hits.
    src_lines.insert(j + 1, capture_line)
    return True, "inserted after body[0]"


def main():
    touched_files: dict[str, int] = {}
    skipped = []
    errors = []
    by_file: dict[str, list[int]] = {}
    for (path, line) in ROWS:
        by_file.setdefault(path, []).append(line)

    for path, lines_to_patch in by_file.items():
        src_path = ROOT / path
        src = src_path.read_text()
        src_lines = src.splitlines()

        src_lines, imp_added = ensure_sentry_import(src_lines)

        # Patch catches in REVERSE line order so insertions don't shift
        # earlier line numbers.
        patches_applied = 0
        for line in sorted(lines_to_patch, reverse=True):
            # After import insertion, line numbers >= last_import shift by 1.
            # Find current effective line number by searching for context.
            # For simplicity, rebuild src_lines with trailing newline and
            # use the ORIGINAL line number — we inserted at a position that
            # shifts all subsequent lines by +1. So original line L is now
            # at index L (not L-1).
            effective_line = line + (1 if imp_added else 0)
            ok, msg = patch_catch(src_lines, effective_line)
            if ok:
                patches_applied += 1
            elif msg == "already patched":
                skipped.append(f"{path}:{line} — {msg}")
            else:
                errors.append(f"{path}:{line} — {msg}")

        src_path.write_text("\n".join(src_lines) + "\n")
        touched_files[path] = patches_applied

    for f, n in sorted(touched_files.items()):
        print(f"  {f}: {n} catches patched", file=sys.stderr)
    print(f"\nTotal: {sum(touched_files.values())} patches across {len(touched_files)} files", file=sys.stderr)
    if skipped:
        print(f"\nSkipped (idempotent): {len(skipped)}", file=sys.stderr)
        for s in skipped[:5]:
            print(f"  {s}", file=sys.stderr)
    if errors:
        print(f"\nERRORS: {len(errors)}", file=sys.stderr)
        for e in errors:
            print(f"  {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
