"""Rubric prompt formatting — shared by grading pipeline + portal grading.

Extracted from the nested scope inside
backend/grading/pipeline.py:_run_grading_thread_inner as part of
Phase 3a PR4. Pure function; no side effects; no closure dependencies.
"""


def format_rubric_for_prompt(rubric_data):
    """Convert rubric dict to a formatted prompt string.

    Body BYTE-IDENTICAL to the nested definition formerly at
    backend/grading/pipeline.py:219 (de-indented to module level).
    """
    if not rubric_data or not rubric_data.get('categories'):
        return None

    categories = rubric_data.get('categories', [])
    generous = rubric_data.get('generous', True)

    lines = []
    lines.append("GRADING RUBRIC (from teacher's custom settings):")
    lines.append("")

    total_weight = sum(c.get('weight', 0) for c in categories)
    lines.append(f"Total Points: {total_weight}")
    lines.append("")

    for i, cat in enumerate(categories, 1):
        name = cat.get('name', f'Category {i}')
        weight = cat.get('weight', 0)
        desc = cat.get('description', '')
        lines.append(f"{i}. {name.upper()} ({weight} points)")
        if desc:
            lines.append(f"   - {desc}")
        lines.append("")

    lines.append("GRADE RANGES:")
    lines.append("- A: 90-100 (Excellent)")
    lines.append("- B: 80-89 (Good)")
    lines.append("- C: 70-79 (Satisfactory)")
    lines.append("- D: 60-69 (Needs Improvement)")
    lines.append("- F: Below 60 (Unsatisfactory)")
    lines.append("")

    if generous:
        lines.append("GRADING STYLE: Be ENCOURAGING and GENEROUS. When in doubt, give the student the benefit of the doubt.")
    else:
        lines.append("GRADING STYLE: Grade strictly according to the rubric criteria.")

    return "\n".join(lines)
