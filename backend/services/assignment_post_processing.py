"""Assignment post-processing pipeline.

Extracted from backend/routes/planner_routes.py during Phase 3b1.
PR1: leaf helpers with no cross-refs to unmoved code.
Spec: docs/superpowers/specs/2026-04-15-phase3b1-planner-helpers-design.md
"""
import os
import sys
import json
import time

# Import MODEL_PRICING for token cost tracking
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from assignment_grader import MODEL_PRICING


def _extract_usage(completion, model="gpt-4o"):
    """Extract token usage and cost from an OpenAI completion response."""
    if not completion or not hasattr(completion, 'usage') or not completion.usage:
        return None
    inp = completion.usage.prompt_tokens or 0
    out = completion.usage.completion_tokens or 0
    pricing = MODEL_PRICING.get(model, {"input": 0, "output": 0})
    cost = (inp * pricing["input"] + out * pricing["output"]) / 1_000_000
    return {
        "model": model, "input_tokens": inp, "output_tokens": out,
        "total_tokens": inp + out, "cost": round(cost, 6),
        "cost_display": f"${cost:.4f}"
    }

PLANNER_COSTS_FILE = os.path.join(os.path.expanduser("~/.graider_data"), "planner_costs.json")


def _record_planner_cost(usage):
    """Record planner API usage to persistent JSON file."""
    if not usage or usage.get("total_tokens", 0) == 0:
        return
    today = time.strftime("%Y-%m-%d")
    os.makedirs(os.path.dirname(PLANNER_COSTS_FILE), exist_ok=True)
    try:
        with open(PLANNER_COSTS_FILE, 'r') as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {"total": {"input_tokens": 0, "output_tokens": 0, "total_cost": 0, "api_calls": 0}, "daily": {}}

    # Update totals
    data["total"]["input_tokens"] += usage.get("input_tokens", 0)
    data["total"]["output_tokens"] += usage.get("output_tokens", 0)
    data["total"]["total_cost"] += usage.get("cost", 0)
    data["total"]["api_calls"] += 1
    data["total"]["total_cost"] = round(data["total"]["total_cost"], 6)

    # Update daily
    if today not in data["daily"]:
        data["daily"][today] = {"input_tokens": 0, "output_tokens": 0, "total_cost": 0, "api_calls": 0}
    data["daily"][today]["input_tokens"] += usage.get("input_tokens", 0)
    data["daily"][today]["output_tokens"] += usage.get("output_tokens", 0)
    data["daily"][today]["total_cost"] += usage.get("cost", 0)
    data["daily"][today]["api_calls"] += 1
    data["daily"][today]["total_cost"] = round(data["daily"][today]["total_cost"], 6)

    with open(PLANNER_COSTS_FILE, 'w') as f:
        json.dump(data, f, indent=2)


# Required fields per question_type — missing any → downgrade to short_answer
_REQUIRED_FIELDS = {
    'multiple_choice': ['options'],
    'matching': ['terms', 'definitions'],
    'data_table': ['headers', 'expected_data'],
    'function_graph': ['correct_expressions'],
    'box_plot': ['data'],
    'dot_plot': ['correct_dots'],
    'stem_and_leaf': ['correct_leaves'],
    'bar_chart': ['chart_data'],
    'transformations': ['original_vertices', 'transformation_type'],
    'multiselect': ['options', 'correct'],
    'multi_part': ['parts'],
    'grid_match': ['row_labels', 'column_labels', 'correct'],
    'inline_dropdown': ['dropdowns'],
    # Geometry types — mode is the minimum requirement (dimensions filled by hydration)
    'triangle': ['mode'],
    'rectangle': ['mode'],
    'circle': ['mode'],
    'trapezoid': ['mode'],
    'parallelogram': ['mode'],
    'regular_polygon': ['mode', 'sides'],
    'rectangular_prism': ['mode'],
    'cylinder': ['mode'],
    'cone': ['mode'],
    'pyramid': ['mode'],
    'sphere': ['mode'],
}


def _validate_question(q):
    """Check required fields for question_type. Downgrade to short_answer if broken."""
    qt = q.get('question_type', 'short_answer')
    required = _REQUIRED_FIELDS.get(qt, [])
    for field in required:
        val = q.get(field)
        if val is None or val == '' or val == []:
            q['question_type'] = 'short_answer'
            return


def _build_question_count_instruction(config):
    """Build the question count prompt instruction for AI generation."""
    total_q = config.get('totalQuestions', 10)
    per_section = config.get('questionsPerSection', 0)
    if per_section > 0:
        per_sec = per_section
    else:
        per_sec = max(total_q // 3, 2)  # default ~3 sections
    instruction = f"QUESTION COUNT: Generate exactly {total_q} questions total."
    instruction += f" Distribute them across your sections — aim for {per_sec} questions per section."
    instruction += f" You MUST have at least {total_q} questions in the final JSON."
    return instruction


def _count_questions(assignment):
    """Count total questions across all sections."""
    total = 0
    for section in assignment.get('sections', []):
        total += len(section.get('questions', []))
    return total


def _enforce_question_count(assignment, target, client=None, config=None):
    """Programmatically enforce exact question count. No AI calls.

    - Over target: trims questions from the largest sections.
    - Under target: accepts what the AI generated (fewer questions is better than duplicates).
    Returns (assignment, None) — no extra usage since this is pure logic.
    """
    sections = assignment.get('sections', [])
    if not sections:
        return assignment, None

    current = _count_questions(assignment)
    if current <= target:
        # Accept what we have — never pad with duplicates
        pass
    else:
        # ── Over target: trim from largest sections first ──
        while current > target:
            largest = max(sections, key=lambda s: len(s.get('questions', [])))
            qs = largest.get('questions', [])
            if not qs:
                break
            qs.pop()  # remove last question
            current -= 1

    # Renumber all questions sequentially and update section point totals
    num = 1
    for s in sections:
        for q in s.get('questions', []):
            q['number'] = num
            num += 1
        s['points'] = sum(q.get('points', 2) for q in s.get('questions', []))

    # Update total_points on the assignment
    assignment['total_points'] = sum(s.get('points', 0) for s in sections)

    return assignment, None


def _merge_usage(base, extra):
    """Merge an extra usage dict into a base usage dict."""
    if not extra:
        return base
    if not base:
        return extra
    return {
        "model": base.get("model", "gpt-4o"),
        "input_tokens": base.get("input_tokens", 0) + extra.get("input_tokens", 0),
        "output_tokens": base.get("output_tokens", 0) + extra.get("output_tokens", 0),
        "total_tokens": base.get("total_tokens", 0) + extra.get("total_tokens", 0),
        "cost": round(base.get("cost", 0) + extra.get("cost", 0), 6),
        "cost_display": f"${base.get('cost', 0) + extra.get('cost', 0):.4f}",
    }


# ── Phase 5: Deterministic point normalization ────────────────────────────

_DEFAULT_POINTS = {
    'multiple_choice': 1, 'true_false': 1, 'matching': 1,
    'short_answer': 2, 'fill_blank': 1, 'math_equation': 2,
    'data_table': 3, 'geometry': 3, 'coordinate_plane': 3,
    'number_line': 2, 'extended_response': 4, 'essay': 4,
    'multi_part': 4, 'grid_match': 3, 'multiselect': 2,
    'triangle': 3, 'rectangle': 3, 'circle': 3, 'trapezoid': 3,
    'regular_polygon': 3, 'function_graph': 3, 'box_plot': 3,
    'dot_plot': 3, 'stem_and_leaf': 3, 'bar_chart': 3,
    'transformations': 3, 'fraction_model': 2, 'probability_tree': 3,
    'tape_diagram': 2, 'venn_diagram': 3, 'protractor': 2,
    'inline_dropdown': 1,
}


def _normalize_points(assignment, target_total=None):
    """Phase 5: Ensure every question has points and section/total sums are correct.

    1. Assign default points to any question missing them (based on question_type).
    2. Recalculate each section's points as sum of its question points.
    3. If target_total is provided and sum doesn't match, scale proportionally.
    4. Update assignment total_points.
    """
    sections = assignment.get('sections', [])
    if not sections:
        return

    # Step 1: Ensure every question has a points field
    for section in sections:
        for q in section.get('questions', []):
            qt = q.get('question_type', q.get('type', 'short_answer'))
            if not q.get('points') or not isinstance(q.get('points'), (int, float)) or q['points'] <= 0:
                q['points'] = _DEFAULT_POINTS.get(qt, 2)

    # Step 2: Recalculate section points from question sums
    for section in sections:
        section['points'] = sum(q.get('points', 1) for q in section.get('questions', []))

    # Step 3: If target_total given and doesn't match, scale proportionally
    current_total = sum(s.get('points', 0) for s in sections)
    if target_total and current_total > 0 and current_total != target_total:
        scale = target_total / current_total
        # Collect all questions for scaling
        all_questions = []
        for section in sections:
            all_questions.extend(section.get('questions', []))
        if all_questions:
            # Scale each question's points (minimum 1)
            for q in all_questions:
                q['points'] = max(1, round(q['points'] * scale))
            # Recalculate actual sum after rounding
            rounded_total = sum(q['points'] for q in all_questions)
            drift = target_total - rounded_total
            if drift != 0:
                # Absorb rounding drift into the question with the most points
                largest_q = max(all_questions, key=lambda q: q['points'])
                largest_q['points'] = max(1, largest_q['points'] + drift)
            # Recalculate section points after scaling
            for section in sections:
                section['points'] = sum(q.get('points', 1) for q in section.get('questions', []))

    # Step 4: Update assignment total_points
    assignment['total_points'] = sum(s.get('points', 0) for s in sections)
