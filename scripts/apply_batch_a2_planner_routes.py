"""Apply Batch A.2 file 4 categorizations for planner_routes.py.

Codex Gate 1: APPROVE. Rules carried forward:
  - Silent omission in aggregation loops → LEGACY
  - AI-response JSON parse failure swallowed → LEGACY (but in this
    file, all json.JSONDecodeError paths return explicit error dicts
    via jsonify — caller surfaces. So those rows are INTENTIONAL.)
  - Bootstrap fallbacks (ImportError) → INTENTIONAL
  - Top-level route Exception returning error dict → INTENTIONAL
  - Explicit "best-effort" secondary writes after primary succeeded
    → INTENTIONAL (Codex objective test)
"""
import re
import sys
from pathlib import Path

AUDIT = Path(__file__).resolve().parent.parent / "docs" / "exception-audit-2026-04.md"

DECISIONS = [
    # Module-level bootstrap
    ("backend/routes/planner_routes.py", 23, "INTENTIONAL", "genai ImportError → None fallback; bootstrap carveout"),
    ("backend/routes/planner_routes.py", 35, "INTENTIONAL", "storage ImportError → fallback; bootstrap"),
    ("backend/routes/planner_routes.py", 38, "INTENTIONAL", "storage inner ImportError → None; bootstrap"),

    # _record_planner_cost
    ("backend/routes/planner_routes.py", 68, "INTENTIONAL", "(FileNotFoundError, json.JSONDecodeError) → zero-init data; typed fallback"),

    # _auto_fix_flagged_questions
    ("backend/routes/planner_routes.py", 730, "INTENTIONAL", "auto-fix quality check fail → print; explicitly labeled 'non-fatal'; enrichment pass"),

    # load_support_documents_for_planning
    ("backend/routes/planner_routes.py", 2183, "INTENTIONAL", "per-doc docx parse → continue; per-file skip in loader loop"),
    ("backend/routes/planner_routes.py", 2191, "INTENTIONAL", "per-doc PDF parse → continue; same pattern"),
    ("backend/routes/planner_routes.py", 2203, "INTENTIONAL", "outer per-doc catch → continue (loop iteration)"),

    # _load_standards_file
    ("backend/routes/planner_routes.py", 2300, "LEGACY", "standards file read fail → return []; silent enrichment loss; teacher generates without standards alignment (same class as assistant_routes:289)"),

    # align_document_to_standards / rewrite_for_alignment
    ("backend/routes/planner_routes.py", 2510, "INTENTIONAL", "json.JSONDecodeError on AI response → return error JSON; typed, caller surfaces"),
    ("backend/routes/planner_routes.py", 2602, "INTENTIONAL", "same pattern, rewrite path"),

    # brainstorm_lesson_ideas / generate_lesson_plan / generate_assignment_from_lesson
    ("backend/routes/planner_routes.py", 2823, "INTENTIONAL", "Exception → print + fallback mock ideas; explicit degraded mode"),
    ("backend/routes/planner_routes.py", 3314, "INTENTIONAL", "Exception → print + mock mode fallback"),
    ("backend/routes/planner_routes.py", 3968, "INTENTIONAL", "Exception → print + error response (top-level route guard)"),

    # _save_grading_config_for_export
    ("backend/routes/planner_routes.py", 4340, "INTENTIONAL", "Supabase mirror fail → pass; comment says 'Local save succeeded, Supabase is best-effort'; primary durable write already succeeded"),
    ("backend/routes/planner_routes.py", 4344, "LEGACY", "outer local save fail → print only; local IS the primary grading-config write; silent data loss"),

    # _export_assignment_docx_graider
    ("backend/routes/planner_routes.py", 4523, "INTENTIONAL", "per-question visual embed fail → print + skip; user sees doc with some visuals missing (visible gap)"),

    # _create_visual_for_question
    ("backend/routes/planner_routes.py", 5440, "INTENTIONAL", "per-plot matplotlib fail → continue (per-line skip)"),
    ("backend/routes/planner_routes.py", 5749, "INTENTIONAL", "outer visual build catch → return None; caller handles None"),

    # generate_assessment top-level
    ("backend/routes/planner_routes.py", 6265, "INTENTIONAL", "top-level route guard: Exception → error dict + 500"),

    # parse_template_structure
    ("backend/routes/planner_routes.py", 6556, "INTENTIONAL", "Exception → structure['error']=str(e); error captured in return shape"),

    # get_assessment_templates
    ("backend/routes/planner_routes.py", 6578, "LEGACY", "per-template metadata parse → pass; silent template skip in aggregation loop; teacher sees partial list"),

    # grade_assessment_answers
    ("backend/routes/planner_routes.py", 7030, "INTENTIONAL", "ValueError on definitions.index → correct_letter=None; typed, caller handles via if/else"),
    ("backend/routes/planner_routes.py", 7120, "INTENTIONAL", "AI grading batch fail → print + fall back to basic comparison; explicit degraded mode"),

    # get_planner_costs
    ("backend/routes/planner_routes.py", 7285, "INTENTIONAL", "(FileNotFoundError, json.JSONDecodeError) → zero-cost response; typed first-time fallback"),

    # extract_text_from_file
    ("backend/routes/planner_routes.py", 7411, "INTENTIONAL", "ImportError pdfplumber → fall back to PyPDF2; explicit typed chain"),

    # generate_slides
    ("backend/routes/planner_routes.py", 8043, "LEGACY", "image generation fail → _image_data={}; silent slide-content loss (same class as get_recent_lessons 1831)"),

    # export_slides
    ("backend/routes/planner_routes.py", 8086, "INTENTIONAL", "per-image base64 decode fail → pass (per-item skip in loop)"),
]


ROW_RE = re.compile(
    r"^\| `(?P<file>[^`]+)` \| (?P<line>\d+) \| `(?P<exc>[^`]+)` \| "
    r"(?P<behavior>[^|]+) \| `(?P<parent>[^`]+)` \| (?P<cat>\w+) \|$"
)


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
