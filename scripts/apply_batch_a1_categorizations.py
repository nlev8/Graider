"""Apply Batch A.1 manual categorizations for backend/app.py.

One-shot tool. Reads docs/exception-audit-2026-04.md, rewrites each
listed (file, line) row with the decided category. Fails loud if a
row isn't found or is already categorized differently.

Decisions documented inline — reasoning is in the per-entry comment.
All 49 previously-UNCATEGORIZED rows in backend/app.py get a category.

Mapping follows the rubric + Codex Gate 1 clarifications:
  - Bootstrap carveout: INTENTIONAL only when fallback is explicit AND
    degraded mode is defined. Silent swallow of required auth/config
    does NOT qualify.
  - Objective best-effort test: INTENTIONAL only if primary durable
    write already succeeded and caught block is a secondary sink.
  - Bias CANDIDATE → LEGACY for ambiguous bare-Exception-pass.
"""
import re
import sys
from pathlib import Path

AUDIT = Path(__file__).resolve().parent.parent / "docs" / "exception-audit-2026-04.md"

# (file, line, category, reason)
DECISIONS = [
    # ── Module-level bootstrap ──────────────────────────────────────────
    ("backend/app.py", 38,  "INTENTIONAL", "ImportError → explicit stub fallback for student_history (defined degraded mode)"),
    ("backend/app.py", 41,  "INTENTIONAL", "ImportError inner fallback → same"),
    ("backend/app.py", 59,  "INTENTIONAL", "ImportError → explicit stub fallback for accommodations"),
    ("backend/app.py", 62,  "INTENTIONAL", "ImportError inner fallback → same"),
    ("backend/app.py", 74,  "INTENTIONAL", "ImportError → storage_load=None explicit fallback"),
    ("backend/app.py", 77,  "INTENTIONAL", "ImportError inner fallback → same"),
    ("backend/app.py", 169, "INTENTIONAL", "bootstrap logging config fail → print warning; logging is non-critical"),
    ("backend/app.py", 175, "NEEDS_ALERT", "auth middleware load fail → no degraded mode; app serves /api/ without auth. Codex Gate 3: startup security hook that keeps serving traffic must page."),
    ("backend/app.py", 204, "INTENTIONAL", "startup stale-partial recovery per-id inner pass; per-Codex: stale-partial recovery fits bootstrap carveout"),
    ("backend/app.py", 206, "INTENTIONAL", "outer catch of the recovery block; best-effort startup cleanup"),

    # ── get_audit_logs ────────────────────────────────────────────────
    ("backend/app.py", 246, "LEGACY",      "FERPA audit log read fail returns []; corrupted audit becomes invisible"),

    # ── load_support_documents_for_grading ────────────────────────────
    ("backend/app.py", 300, "INTENTIONAL", "docx parse fail → continue; per-doc skip, others load"),
    ("backend/app.py", 308, "INTENTIONAL", "PDF parse fail → continue; per-doc skip"),
    ("backend/app.py", 318, "INTENTIONAL", "outer per-doc catch → continue (loop iteration)"),

    # ── load_saved_results / save_results ─────────────────────────────
    ("backend/app.py", 400, "LEGACY",      "load_saved_results fallback pass + return []; silent data loss indistinguishable from empty"),
    ("backend/app.py", 412, "LEGACY",      "save_results fallback file-write; only write path when storage_save is None; silent data loss"),

    # ── calculate_late_penalty ────────────────────────────────────────
    ("backend/app.py", 865, "INTENTIONAL", "(ValueError,TypeError) → return None; typed documented fallback for parse"),
    ("backend/app.py", 871, "INTENTIONAL", "(OSError,TypeError) → return None; typed documented fallback for mtime"),

    # ── _run_grading_thread_inner (7 rows) ────────────────────────────
    ("backend/app.py", 655,  "INTENTIONAL", "config load per-file in loop → pass; skip bad config, others load"),
    ("backend/app.py", 975,  "INTENTIONAL", "per-period meta.json parse fail → pass; falls back to default class_level"),
    ("backend/app.py", 1016, "INTENTIONAL", "per-period CSV read fail → log to grading_state (user-visible warning)"),
    ("backend/app.py", 1044, "INTENTIONAL", "master CSV read fail → pass; already_graded set is augmentation, not required"),
    ("backend/app.py", 1773, "INTENTIONAL", "per-file future.result() fail → log + continue; user-visible"),
    ("backend/app.py", 2005, "LEGACY",      "audit trail JSON save fail → log to grading_state but FERPA audit lost silently"),
    ("backend/app.py", 2032, "NEEDS_ALERT", "outer grading thread catch; same pattern as portal_grading.py:612 that Hotfix 1 wired to capture_exception. Task 5 should apply the same fix here."),

    # ── grade_single_file (5 rows) ────────────────────────────────────
    ("backend/app.py", 1192, "INTENTIONAL", "temp file content match → pass; best-effort auxiliary match"),
    ("backend/app.py", 1347, "INTENTIONAL", "correction context fetch fail → print + skip feature; grading continues with degraded notes"),
    ("backend/app.py", 1528, "INTENTIONAL", "prior result CSV lookup fail → pass; prev_r defaults to None, caller handles"),
    ("backend/app.py", 1681, "INTENTIONAL", "baseline deviation detect fail → pass; baseline_deviation defaulted to 'normal'"),
    ("backend/app.py", 1690, "NEEDS_ALERT", "add_assignment_to_history fail → pass; student-history write. Codex Gate 3 consistency rule: same failure class as portal_grading.py:606 which is NEEDS_ALERT."),

    # ── grade_individual (3 rows) ─────────────────────────────────────
    ("backend/app.py", 2106, "INTENTIONAL", "student_info JSON parse fail → pass; student_info defaults to None, route tolerates"),
    ("backend/app.py", 2114, "INTENTIONAL", "assignment_config JSON parse fail → same pattern"),
    ("backend/app.py", 2229, "NEEDS_ALERT", "add_assignment_to_history fail → print; same data class as 1690. Mirror NEEDS_ALERT per Codex consistency rule."),

    # ── _remove_from_master_csv / _sync_approval_to_master_csv ────────
    ("backend/app.py", 2288, "LEGACY",      "master_grades.csv write fail → print; CSV is system-of-record for grading history"),
    ("backend/app.py", 2342, "LEGACY",      "same master_grades.csv write fail → print"),

    # ── export_individual_student_data (7 rows) ───────────────────────
    ("backend/app.py", 2667, "INTENTIONAL", "period meta.json parse → pass; fallback label from filename"),
    ("backend/app.py", 2688, "INTENTIONAL", "period CSV read fail → continue to next period"),
    ("backend/app.py", 2740, "LEGACY",      "accommodations JSON read fail → pass; export silently missing IEP data"),
    ("backend/app.py", 2752, "LEGACY",      "ELL JSON read fail → pass; export silently missing ELL data"),
    ("backend/app.py", 2764, "LEGACY",      "parent_contacts JSON read fail → pass; export silently missing contacts"),
    ("backend/app.py", 2865, "LEGACY",      "PDF build fail → pdf_path=None + print; user downloads incomplete export without notice"),
    ("backend/app.py", 2873, "INTENTIONAL", "macOS 'open' subprocess fail → pass; pure convenience on dev machine"),

    # ── import_individual_student_data (3 rows) ───────────────────────
    ("backend/app.py", 3040, "LEGACY",      "ELL JSON read fail → pass; merge reads prior data, silent loss"),
    ("backend/app.py", 3056, "LEGACY",      "parent_contacts JSON read fail → pass; same merge pattern"),
    ("backend/app.py", 3090, "LEGACY",      "roster CSV append fail → print; student roster not updated silently"),

    # ── extract_student_from_image ────────────────────────────────────
    ("backend/app.py", 3191, "INTENTIONAL", "anthropic ImportError → return typed error response; explicit degraded mode"),

    # ── list_periods ──────────────────────────────────────────────────
    ("backend/app.py", 3356, "INTENTIONAL", "student-count CSV iter fail → pass; count defaults to 0, period still listed"),

    # ── healthz ───────────────────────────────────────────────────────
    ("backend/app.py", 3430, "INTENTIONAL", "Supabase probe fail → 'error' status; failure IS the health-check signal"),
    ("backend/app.py", 3443, "INTENTIONAL", "Redis probe fail → 'error' status; same"),
]


ROW_RE = re.compile(
    r"^\| `(?P<file>[^`]+)` \| (?P<line>\d+) \| `(?P<exc>[^`]+)` \| "
    r"(?P<behavior>[^|]+) \| `(?P<parent>[^`]+)` \| (?P<cat>\w+) \|$"
)


def main():
    text = AUDIT.read_text()
    lines = text.splitlines()

    decision_map = {(f, line): (cat, reason) for (f, line, cat, reason) in DECISIONS}

    applied = 0
    not_found = []
    already_set = []

    for i, line_text in enumerate(lines):
        m = ROW_RE.match(line_text)
        if not m:
            continue
        key = (m.group("file"), int(m.group("line")))
        if key not in decision_map:
            continue
        cat, _ = decision_map.pop(key)
        existing_cat = m.group("cat")
        if existing_cat != "UNCATEGORIZED":
            already_set.append((key, existing_cat, cat))
            continue
        lines[i] = line_text.rsplit("|", 2)[0] + f"| {cat} |"
        applied += 1

    for k in decision_map:
        not_found.append(k)

    AUDIT.write_text("\n".join(lines) + "\n")

    print(f"Applied {applied}/{len(DECISIONS)} categorizations.", file=sys.stderr)
    if already_set:
        print(f"\n{len(already_set)} rows had a non-UNCATEGORIZED category already:",
              file=sys.stderr)
        for key, existing, intended in already_set:
            print(f"  {key} was {existing}, skipped (would have been {intended})",
                  file=sys.stderr)
    if not_found:
        print(f"\n{len(not_found)} decisions had no matching row:", file=sys.stderr)
        for key in not_found:
            print(f"  {key} not found", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
