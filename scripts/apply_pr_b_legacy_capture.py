"""PR-b scripted patcher: add sentry_sdk.capture_exception to the 116
non-SIS LEGACY catches from Task 4 audit, using AST-based line-drift
tolerance.

Why AST: files previously patched by PR-a may have `import sentry_sdk`
added, shifting all subsequent line numbers by +1. The audit line
numbers are frozen at Task 4 regeneration time. Find the current
except line by locating the except nearest to the audit line.

Carve-outs (7 rows) SKIPPED to avoid Sentry volume fanout per Codex Gate 1:
  - backend/services/openai_tts_service.py:248
  - backend/services/outlook_sender.py:327
  - backend/services/portal_grading.py:330, 340, 350, 361, 404
"""
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

CARVE_OUTS = {
    ("backend/services/openai_tts_service.py", 248),
    ("backend/services/outlook_sender.py", 327),
    ("backend/services/portal_grading.py", 330),
    ("backend/services/portal_grading.py", 340),
    ("backend/services/portal_grading.py", 350),
    ("backend/services/portal_grading.py", 361),
    ("backend/services/portal_grading.py", 404),
}

ALL_NON_SIS_LEGACY_RAW = """\
backend/accommodations.py:460
backend/app.py:246
backend/app.py:400
backend/app.py:412
backend/app.py:2005
backend/app.py:2288
backend/app.py:2342
backend/app.py:2740
backend/app.py:2752
backend/app.py:2764
backend/app.py:2865
backend/app.py:3040
backend/app.py:3056
backend/app.py:3090
backend/auth.py:248
backend/routes/admin_routes.py:109
backend/routes/admin_routes.py:127
backend/routes/admin_routes.py:310
backend/routes/admin_routes.py:390
backend/routes/admin_routes.py:476
backend/routes/admin_routes.py:510
backend/routes/analytics_routes.py:124
backend/routes/analytics_routes.py:354
backend/routes/analytics_routes.py:737
backend/routes/assignment_player_routes.py:1027
backend/routes/assignment_routes.py:65
backend/routes/assignment_routes.py:216
backend/routes/automation_routes.py:141
backend/routes/automation_routes.py:215
backend/routes/automation_routes.py:236
backend/routes/behavior_routes.py:421
backend/routes/behavior_routes.py:450
backend/routes/document_routes.py:91
backend/routes/email_routes.py:284
backend/routes/email_routes.py:1164
backend/routes/email_routes.py:1175
backend/routes/grading_routes.py:395
backend/routes/grading_routes.py:1387
backend/routes/grading_routes.py:1403
backend/routes/notebooklm_routes.py:195
backend/routes/settings_routes.py:153
backend/routes/settings_routes.py:348
backend/routes/settings_routes.py:490
backend/routes/settings_routes.py:509
backend/routes/settings_routes.py:656
backend/routes/settings_routes.py:1266
backend/routes/student_account_routes.py:434
backend/routes/student_account_routes.py:975
backend/routes/student_account_routes.py:988
backend/services/assistant_tools.py:242
backend/services/assistant_tools.py:509
backend/services/assistant_tools.py:546
backend/services/assistant_tools.py:673
backend/services/assistant_tools.py:693
backend/services/assistant_tools.py:725
backend/services/assistant_tools.py:743
backend/services/assistant_tools.py:786
backend/services/assistant_tools.py:831
backend/services/assistant_tools.py:852
backend/services/assistant_tools_automation.py:105
backend/services/assistant_tools_automation.py:192
backend/services/assistant_tools_behavior.py:188
backend/services/assistant_tools_data.py:68
backend/services/assistant_tools_data.py:152
backend/services/assistant_tools_reports.py:1831
backend/services/assistant_tools_reports.py:1898
backend/services/assistant_tools_reports.py:2122
backend/services/assistant_tools_student.py:342
backend/services/assistant_tools_student.py:495
backend/services/assistant_tools_student.py:522
backend/services/assistant_tools_student.py:548
backend/services/assistant_tools_student.py:557
backend/services/assistant_tools_student.py:574
backend/services/assistant_tools_student.py:591
backend/services/assistant_tools_student.py:608
backend/services/assistant_tools_student.py:1037
backend/services/document_generator.py:81
backend/services/document_generator.py:338
backend/services/document_generator.py:353
backend/services/document_generator.py:368
backend/services/document_generator.py:409
backend/services/document_generator.py:422
backend/services/document_generator.py:447
backend/services/document_generator.py:463
backend/services/document_generator.py:479
backend/services/document_generator.py:494
backend/services/document_generator.py:510
backend/services/document_generator.py:525
backend/services/document_generator.py:541
backend/services/document_generator.py:553
backend/services/document_generator.py:567
backend/services/document_generator.py:579
backend/services/grading_service.py:129
backend/services/notebooklm_service.py:502
backend/services/openai_tts_service.py:248
backend/services/outlook_sender.py:152
backend/services/outlook_sender.py:327
backend/services/outlook_sender.py:337
backend/services/outlook_sender.py:351
backend/services/portal_grading.py:330
backend/services/portal_grading.py:340
backend/services/portal_grading.py:350
backend/services/portal_grading.py:361
backend/services/portal_grading.py:404
backend/services/slide_generator.py:281
backend/services/worksheet_generator.py:233
backend/storage.py:319
backend/storage.py:576
backend/storage.py:601
backend/utils/auth_decorators.py:48
"""
ALL_NON_SIS_LEGACY = [
    tuple(p.split(":")) for p in ALL_NON_SIS_LEGACY_RAW.strip().splitlines()
]
ALL_NON_SIS_LEGACY = [(f, int(l)) for (f, l) in ALL_NON_SIS_LEGACY]


EXCEPT_RE = re.compile(
    r"^(\s*)except\s+([^\s:]+(?:\s*,\s*[^\s:]+)*|\([^)]+\))"
    r"(?:\s+as\s+(\w+))?\s*:\s*(?:#.*)?$"
)


def ensure_sentry_import(src_lines: list[str]) -> tuple[list[str], int]:
    """Insert `import sentry_sdk` near imports. Return (new_lines, shift)
    where shift is +1 if inserted, 0 if already present."""
    for line in src_lines:
        if re.match(r"^import sentry_sdk\b", line):
            return src_lines, 0
    last_import = -1
    for i, line in enumerate(src_lines[:120]):
        if re.match(r"^(from|import)\s+\S", line):
            last_import = i
    if last_import < 0:
        return src_lines, 0
    src_lines.insert(last_import + 1, "import sentry_sdk")
    return src_lines, 1


def find_except_near(tree: ast.Module, target_line: int) -> int | None:
    """Return the line number of the ExceptHandler closest to target_line
    (within ±10 lines), or None."""
    best = None
    best_dist = 11
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            dist = abs(node.lineno - target_line)
            if dist < best_dist:
                best = node.lineno
                best_dist = dist
    return best


_TERMINATORS = ("return", "continue", "break", "raise")


def _is_terminator_statement(line: str) -> bool:
    """Return True if a stripped line is a terminator (return/continue/
    break/raise with any args). Prevents inserting capture AFTER it."""
    stripped = line.strip()
    for kw in _TERMINATORS:
        if stripped == kw or stripped.startswith(kw + " ") or stripped.startswith(kw + "("):
            return True
    return False


def patch_catch(src_lines: list[str], line_num: int) -> tuple[bool, str]:
    idx = line_num - 1
    if idx < 0 or idx >= len(src_lines):
        return False, "oob"
    if "sentry_sdk.capture_exception" in "\n".join(src_lines[idx:idx + 8]):
        return False, "already"
    m = EXCEPT_RE.match(src_lines[idx])
    if not m:
        return False, f"no-except: {src_lines[idx][:60]!r}"
    indent, exc_types, binding = m.group(1), m.group(2), m.group(3)
    if binding is None:
        binding = "e"
        src_lines[idx] = f"{indent}except {exc_types.strip()} as {binding}:"
    inner_indent = indent + "    "
    capture_line = f"{inner_indent}sentry_sdk.capture_exception({binding})"
    if idx + 1 >= len(src_lines):
        return False, "eof"
    next_line = src_lines[idx + 1]
    if next_line.strip() == "pass" and next_line.startswith(inner_indent):
        src_lines[idx + 1] = capture_line
        return True, "replaced-pass"
    # Find first non-blank body line
    j = idx + 1
    while j < len(src_lines) and src_lines[j].strip() == "":
        j += 1
    if j >= len(src_lines):
        return False, "no-body"
    # CRITICAL: if the first body stmt is a terminator (return/continue/
    # break/raise), inserting AFTER it creates a dead capture. Insert
    # BEFORE it instead so capture runs before control transfer.
    if _is_terminator_statement(src_lines[j]):
        src_lines.insert(j, capture_line)
        return True, "inserted-before-terminator"
    # Otherwise insert AFTER first body stmt so logger.x fires first.
    src_lines.insert(j + 1, capture_line)
    return True, "inserted-after"


def main():
    rows = [(f, l) for (f, l) in ALL_NON_SIS_LEGACY if (f, l) not in CARVE_OUTS]
    by_file: dict[str, list[int]] = {}
    for (f, l) in rows:
        by_file.setdefault(f, []).append(l)

    touched: dict[str, int] = {}
    skipped = []
    errors = []

    for path, lines_to_patch in by_file.items():
        src_path = ROOT / path
        if not src_path.exists():
            errors.append(f"{path}: missing")
            continue
        src_lines = src_path.read_text().splitlines()

        # Ensure import first
        src_lines, import_shift = ensure_sentry_import(src_lines)

        # For each target line, use AST to find nearest ExceptHandler.
        # Patch in REVERSE order (highest line first) to avoid shifting
        # earlier targets.
        # Build AST fresh each iteration since insertions shift lines.
        for target_line in sorted(lines_to_patch, reverse=True):
            try:
                tree = ast.parse("\n".join(src_lines))
            except SyntaxError as e:
                errors.append(f"{path}:{target_line} — syntax: {e}")
                continue
            # Target drifted by import_shift if target > import position.
            # Try both shifted and unshifted.
            candidates = [target_line + import_shift, target_line]
            matched = None
            for cand in candidates:
                matched = find_except_near(tree, cand)
                if matched is not None:
                    break
            if matched is None:
                errors.append(f"{path}:{target_line} — no-except-nearby")
                continue

            ok, msg = patch_catch(src_lines, matched)
            if ok:
                touched[path] = touched.get(path, 0) + 1
            elif msg == "already":
                skipped.append(f"{path}:{target_line}")
            else:
                errors.append(f"{path}:{target_line}→{matched} — {msg}")

        src_path.write_text("\n".join(src_lines) + "\n")

    for f, n in sorted(touched.items()):
        print(f"  {f}: {n}", file=sys.stderr)
    print(f"\nTotal: {sum(touched.values())} patches across {len(touched)} files", file=sys.stderr)
    print(f"Carve-outs skipped: {len(CARVE_OUTS)}", file=sys.stderr)
    if skipped:
        print(f"Already captured: {len(skipped)}", file=sys.stderr)
    if errors:
        print(f"\nERRORS: {len(errors)}", file=sys.stderr)
        for e in errors[:30]:
            print(f"  {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
