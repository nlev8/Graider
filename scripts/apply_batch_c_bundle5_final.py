"""Batch C bundle 5 (FINAL) — 49 rows across 26 files. Completes Task 4.

Codex Gate 1 pre-locks:
  api_keys.py 91, 124 → NEEDS_ALERT (credential resolution silent loss)
  stripe_routes.py 261 → NEEDS_ALERT (payment sub metadata sync silent fail)
  auth_routes.py 68 → INTENTIONAL (fail-closed security, do not weaken)
"""
import re, sys
from pathlib import Path

AUDIT = Path(__file__).resolve().parent.parent / "docs" / "exception-audit-2026-04.md"

DECISIONS = [
    # openai_tts_service.py
    ("backend/services/openai_tts_service.py", 20, "INTENTIONAL", "module ImportError → None; bootstrap"),
    ("backend/services/openai_tts_service.py", 216, "INTENTIONAL", "queue.Empty → continue; typed polling loop"),
    ("backend/services/openai_tts_service.py", 248, "LEGACY", "per-chunk TTS fail log.error; audio gap silent, no alert"),

    # mathpix_ocr.py
    ("backend/services/mathpix_ocr.py", 115, "INTENTIONAL", "OCR error → typed error dict"),
    ("backend/services/mathpix_ocr.py", 123, "INTENTIONAL", "OCR error → typed error dict"),
    ("backend/services/mathpix_ocr.py", 133, "INTENTIONAL", "OCR error → typed error dict"),

    # assistant_tools_ai.py
    ("backend/services/assistant_tools_ai.py", 113, "INTENTIONAL", "ImportError anthropic → None+msg; typed bootstrap"),
    ("backend/services/assistant_tools_ai.py", 135, "INTENTIONAL", "json.JSONDecodeError → error dict"),
    ("backend/services/assistant_tools_ai.py", 137, "INTENTIONAL", "outer Exception → error dict"),

    # populate_fl_standards.py (one-off script)
    ("backend/scripts/populate_fl_standards.py", 177, "INTENTIONAL", "IXL fetch fail → print + return None; one-off script"),
    ("backend/scripts/populate_fl_standards.py", 315, "INTENTIONAL", "code sort parse → append default; typed within sort"),
    ("backend/scripts/populate_fl_standards.py", 415, "INTENTIONAL", "enrich_batch per-std fail → print + continue; one-off script"),

    # document_routes.py
    ("backend/routes/document_routes.py", 91, "LEGACY", "_parse_docx per-image pass; silent embed loss in doc parse"),
    ("backend/routes/document_routes.py", 107, "INTENTIONAL", "_parse_docx outer → error dict; surfaced"),
    ("backend/routes/document_routes.py", 201, "INTENTIONAL", "_parse_pdf outer → error dict; surfaced"),

    # auth_routes.py — Codex pre-locks
    ("backend/routes/auth_routes.py", 68, "INTENTIONAL", "Codex Gate 1: approve_user fail-closed denies on signer/config failure; security-critical INTENTIONAL"),
    ("backend/routes/auth_routes.py", 179, "INTENTIONAL", "notify_signup log.warning; best-effort notification"),
    ("backend/routes/auth_routes.py", 218, "INTENTIONAL", "notify_signup log.error; best-effort notification"),

    # api_keys.py — Codex pre-locks
    ("backend/api_keys.py", 43, "INTENTIONAL", "(ImportError, RuntimeError) Flask g → ''; typed outside-request fallback"),
    ("backend/api_keys.py", 91, "NEEDS_ALERT", "Codex Gate 1: credential resolution silent load fail degrades to env/empty; no operator signal"),
    ("backend/api_keys.py", 124, "NEEDS_ALERT", "Codex Gate 1: resolve_keys_for_teacher same credential-silent-loss class"),

    # utils/logging_utils.py
    ("backend/utils/logging_utils.py", 16, "INTENTIONAL", "log format fallback; internal helper"),
    ("backend/utils/logging_utils.py", 32, "INTENTIONAL", "log format fallback; same"),

    # supabase_resilient.py
    ("backend/supabase_resilient.py", 74, "INTENTIONAL", "operation classifier fail → return default type; typed"),
    ("backend/supabase_resilient.py", 134, "INTENTIONAL", "AttributeError method introspect → 'unknown'; typed"),

    # grading_service.py
    ("backend/services/grading_service.py", 129, "LEGACY", "teacher config load log.debug; silent config loss (aggregation of grading pipeline inputs)"),
    ("backend/services/grading_service.py", 250, "INTENTIONAL", "AI batch grading log.error + fall back per-item; explicit degraded path"),

    # email_service.py
    ("backend/services/email_service.py", 21, "INTENTIONAL", "module-level print; dev-setup message"),
    ("backend/services/email_service.py", 133, "INTENTIONAL", "send_email fail → print + return False; surfaced to caller"),

    # assistant_tools_planning.py
    ("backend/services/assistant_tools_planning.py", 191, "INTENTIONAL", "standards lookup fail → error dict; caller surfaces"),
    ("backend/services/assistant_tools_planning.py", 724, "INTENTIONAL", "sub_plans outer → error dict; caller surfaces"),

    # assistant_tools_edtech.py
    ("backend/services/assistant_tools_edtech.py", 331, "INTENTIONAL", "Kahoot quiz fail → error dict; surfaced"),
    ("backend/services/assistant_tools_edtech.py", 478, "INTENTIONAL", "Nearpod questions fail → error dict; surfaced"),

    # sync_routes.py (SIS compliance preserved)
    ("backend/routes/sync_routes.py", 32, "INTENTIONAL", "get_supabase fail → None; typed fallback"),
    ("backend/routes/sync_routes.py", 145, "LEGACY", "_save_cursor log.warning; periodic-sync cursor silently stale (drift)"),

    # stripe_routes.py — Codex pre-lock
    ("backend/routes/stripe_routes.py", 205, "INTENTIONAL", "typed (SignatureVerificationError) + outer → 400/error response"),
    ("backend/routes/stripe_routes.py", 261, "NEEDS_ALERT", "Codex Gate 1: payment webhook succeeds externally but subscription metadata sync silent fail"),

    # notebooklm_routes.py
    ("backend/routes/notebooklm_routes.py", 29, "INTENTIONAL", "ImportError guard → typed availability check"),
    ("backend/routes/notebooklm_routes.py", 195, "LEGACY", "nlm_create_notebook log.warning; external-integration failure hidden"),

    # auth_decorators.py
    ("backend/utils/auth_decorators.py", 48, "LEGACY", "admin_role storage load fail → admin_role=None; silent admin-role denial (user gets 'not admin' response, can't distinguish backend fail)"),

    # worksheet_generator.py
    ("backend/services/worksheet_generator.py", 233, "LEGACY", "per-visual embed continue; same class as document_generator.py:338 (visible gap silent)"),

    # visualization.py
    ("backend/services/visualization.py", 608, "INTENTIONAL", "per-curve plot continue; per-line skip in matplotlib"),

    # slide_generator.py
    ("backend/services/slide_generator.py", 281, "LEGACY", "generate_slide_images log.warning; image-gen silent content loss (mirrors planner_routes:8043)"),

    # oneroster_gradebook.py (SIS compliance preserved)
    ("backend/services/oneroster_gradebook.py", 95, "NEEDS_ALERT", "per-score post_results log.warning + append errors; SIS grade-push partial; mirrors clever.py:217 NEEDS_ALERT pattern"),

    # correction_patterns.py
    ("backend/services/correction_patterns.py", 15, "INTENTIONAL", "module-level ImportError fallback; bootstrap"),

    # assistant_tools_stem.py
    ("backend/services/assistant_tools_stem.py", 221, "INTENTIONAL", "handle_grade_coordinates → error dict; caller surfaces"),

    # assistant_tools_communication.py
    ("backend/services/assistant_tools_communication.py", 395, "NEEDS_ALERT", "parent_contacts read silent pass; FERPA recipient-resolution mirrors assistant_tools_behavior:198"),

    # assistant_tools_assessments.py
    ("backend/services/assistant_tools_assessments.py", 23, "INTENTIONAL", "_get_supabase fail → None; typed"),

    # lti_routes.py (SIS compliance preserved)
    ("backend/routes/lti_routes.py", 124, "INTENTIONAL", "LTI launch fail → log.warning + typed error response; caller (LMS) surfaces"),
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
