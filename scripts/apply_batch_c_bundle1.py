"""Batch C bundle 1: auth.py + notebooklm_service.py + assignment_routes.py
+ clever.py + stem_grading.py (35 rows). Codex Gate 1 pre-locks applied
for auth storage fallbacks, clever roster fetch masking, notebooklm
remote cleanup leaks, assignment_config silent overwrite."""
import re, sys
from pathlib import Path

AUDIT = Path(__file__).resolve().parent.parent / "docs" / "exception-audit-2026-04.md"

DECISIONS = [
    # ── auth.py ─────────────────────────────────────────────────
    ("backend/auth.py", 30, "NEEDS_ALERT", "Codex Gate 1: storage load fail silently shifts Clever link resolution to legacy file; security-critical auth continues"),
    ("backend/auth.py", 36, "INTENTIONAL", "typed (FileNotFoundError, json.JSONDecodeError) → {}; explicit degraded mode after storage fail"),
    ("backend/auth.py", 45, "NEEDS_ALERT", "Codex Gate 1: storage save fail silently shifts Clever link persistence to legacy file; same security class"),
    ("backend/auth.py", 132, "INTENTIONAL", "jwt.ExpiredSignatureError → None; typed expected auth flow"),
    ("backend/auth.py", 134, "INTENTIONAL", "jwt.InvalidTokenError → log.warning + try HS256 fallback; typed explicit fallback chain"),
    ("backend/auth.py", 146, "INTENTIONAL", "jwt.ExpiredSignatureError on HS256 → None; typed, chain exhausted"),
    ("backend/auth.py", 148, "INTENTIONAL", "jwt.InvalidTokenError on HS256 → None; typed, chain exhausted"),
    ("backend/auth.py", 248, "LEGACY", "Admin API approval fallback Exception → log.warning only; observability gap on fallback failure (not NEEDS_ALERT since it doesn't silently pass auth)"),

    # ── notebooklm_service.py ───────────────────────────────────
    ("backend/services/notebooklm_service.py", 66, "INTENTIONAL", "ImportError get_storage_path → expanduser default; typed bootstrap"),
    ("backend/services/notebooklm_service.py", 169, "INTENTIONAL", "session context.close() pass; cleanup best-effort on cancel"),
    ("backend/services/notebooklm_service.py", 173, "INTENTIONAL", "playwright.stop() pass; same cleanup pattern"),
    ("backend/services/notebooklm_service.py", 259, "NEEDS_ALERT", "Codex Gate 1: remote notebook cleanup fail → pass; user sees success but remote resources leak"),
    ("backend/services/notebooklm_service.py", 502, "LEGACY", "Codex Gate 1: partial source ingestion → print warning + continue; generated output silently degrades with missing sources"),
    ("backend/services/notebooklm_service.py", 799, "INTENTIONAL", "per-material retry → state['errors'].append; error surfaced in state"),
    ("backend/services/notebooklm_service.py", 810, "NEEDS_ALERT", "Codex Gate 1: remote cleanup in generation thread pass; same remote-leak class as 259"),

    # ── assignment_routes.py ────────────────────────────────────
    ("backend/routes/assignment_routes.py", 22, "INTENTIONAL", "ImportError storage → root-import fallback; bootstrap"),
    ("backend/routes/assignment_routes.py", 25, "INTENTIONAL", "ImportError inner → None; bootstrap"),
    ("backend/routes/assignment_routes.py", 65, "LEGACY", "Codex Gate 1: save_assignment_config on corrupted JSON → existing={}; silent merge-overwrite of prior config (same class as assistant_tools_reports:2122)"),
    ("backend/routes/assignment_routes.py", 155, "INTENTIONAL", "json.JSONDecodeError on AI response → typed error 500; caller surfaces"),
    ("backend/routes/assignment_routes.py", 216, "LEGACY", "per-assignment config load fail → default dict; silent corruption hidden, downstream uses defaults not flagged"),
    ("backend/routes/assignment_routes.py", 427, "INTENTIONAL", "ImportError python-docx → typed error dict"),
    ("backend/routes/assignment_routes.py", 531, "INTENTIONAL", "ImportError reportlab → typed error dict"),

    # ── clever.py (SIS compliance — no behavior changes, only Sentry adds in Task 5)
    ("backend/clever.py", 46, "LEGACY", "get_clever_config Exception → pass; config silently absent (no behavior change per SIS guardrail, Task 5 adds capture)"),
    ("backend/clever.py", 217, "NEEDS_ALERT", "Codex Gate 1: roster fetch error → log.error + break; clever_routes returns 'status: synced' with partial data"),
    ("backend/clever.py", 231, "NEEDS_ALERT", "Codex Gate 1: sections fetch same masking pattern"),
    ("backend/clever.py", 245, "NEEDS_ALERT", "Codex Gate 1: contacts fetch same masking pattern"),
    ("backend/clever.py", 361, "INTENTIONAL", "(JSONDecodeError, ValueError) → archived={}; typed archive-merge fallback"),
    ("backend/clever.py", 404, "INTENTIONAL", "(JSONDecodeError, ValueError) → overrides={}; typed overrides fallback"),
    ("backend/clever.py", 545, "INTENTIONAL", "(JSONDecodeError, ValueError) → existing={}; typed parent-contacts merge"),

    # ── stem_grading.py (pure grading, typed fallbacks) ─────────
    ("backend/services/stem_grading.py", 69, "INTENTIONAL", "sympify parse fail → pass; per-strategy skip in normalize chain"),
    ("backend/services/stem_grading.py", 75, "INTENTIONAL", "parse_latex fail → pass; same pattern"),
    ("backend/services/stem_grading.py", 101, "INTENTIONAL", "symbolic simplify fail → pass, fall through to numeric"),
    ("backend/services/stem_grading.py", 143, "INTENTIONAL", "ImportError sympy.parsing.latex → typed error dict"),
    ("backend/services/stem_grading.py", 217, "INTENTIONAL", "top-level Exception → error dict; caller surfaces"),
    ("backend/services/stem_grading.py", 514, "INTENTIONAL", "(ValueError, TypeError) coordinate parse → typed error feedback"),
]

ROW_RE = re.compile(r"^\| `(?P<file>[^`]+)` \| (?P<line>\d+) \| `(?P<exc>[^`]+)` \| (?P<behavior>[^|]+) \| `(?P<parent>[^`]+)` \| (?P<cat>\w+) \|$")


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
