"""Assignment post-processing pipeline.

Extracted from backend/routes/planner_routes.py during Phase 3b1.
PR1: leaf helpers with no cross-refs to unmoved code.
PR2: classifier + hydrators + geometry/text utilities.
PR3: quality validators + project filter.
PR4: explicit-context _auto_fix_flagged_questions (Flask-decoupled).
Spec: docs/superpowers/specs/2026-04-15-phase3b1-planner-helpers-design.md
"""
import os
import sys
import json
import time
import math
import re

# Import MODEL_PRICING for token cost tracking
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from assignment_grader import MODEL_PRICING
from backend.retry import with_retry


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


# ── PR2: Classifier + Hydrators + Geometry/Text Utilities ─────────────────
# Phase 3b1 PR2 additions. Moved byte-identical from backend/routes/planner_routes.py.


# Types where the AI's classification is trusted (complex structural content)
_TRUSTED_AI_TYPES = frozenset({
    'data_table', 'box_plot', 'dot_plot', 'stem_and_leaf', 'bar_chart',
    'transformations', 'fraction_model', 'probability_tree',
    'tape_diagram', 'venn_diagram', 'protractor', 'angle_protractor',
    'unit_circle', 'multiselect', 'multi_part', 'grid_match',
    'inline_dropdown',
})


def _classify_question_type(q, section=None):
    """Deterministic question type classification.

    Assigns question_type based on text analysis and structural fields.
    Runs ONCE per question.

    Priority order:
    1. Preserve AI-specified type for trusted complex types
    2. Structural detection (options -> MC, terms -> matching, etc.)
    3. Geometry detection (shape + mode keywords)
    4. Graphing detection (equation patterns)
    5. Math equation detection
    6. Extended response detection
    7. Section type hint fallback
    8. Default -> short_answer
    """
    ai_type = q.get('question_type', q.get('type', ''))

    # Phase 0: Trust AI for complex structural types
    if ai_type in _TRUSTED_AI_TYPES:
        q['question_type'] = ai_type
        return

    text = q.get('question', '')
    text_lower = text.lower()
    answer = str(q.get('answer', ''))

    # Phase 1: Structural detection (fields present)
    if q.get('options') and len(q.get('options', [])) >= 2:
        q['question_type'] = 'multiple_choice'
        return

    if q.get('terms') and q.get('definitions'):
        q['question_type'] = 'matching'
        return

    if answer.strip().lower() in ('true', 'false'):
        q['question_type'] = 'true_false'
        return

    if '___' in text or '____' in text:
        q['question_type'] = 'fill_blank'
        return

    # Phase 2: Geometry detection
    if not _is_identification_question(text):
        shape, polygon_sides = _detect_primary_shape(text)
        mode = _detect_mode(text)
        if shape and mode:
            q['question_type'] = shape
            q['mode'] = mode
            if polygon_sides:
                q.setdefault('sides', polygon_sides)
            return
        # Shape without mode — check if AI already set a geometry type with mode
        if shape and ai_type in _ALL_GEOMETRY_TYPES and q.get('mode'):
            q['question_type'] = shape
            if polygon_sides:
                q.setdefault('sides', polygon_sides)
            return

    # Phase 3: Graphing detection
    if _looks_like_graphing_question(text_lower):
        equations = _extract_equations_from_text(text)
        if equations:
            q['question_type'] = 'function_graph'
            q['correct_expressions'] = equations
            return

    if 'coordinate plane' in text_lower or ('plot' in text_lower and 'point' in text_lower):
        q['question_type'] = 'coordinate_plane'
        return

    if 'number line' in text_lower and any(w in text_lower for w in ('plot', 'place', 'mark', 'graph')):
        q['question_type'] = 'number_line'
        return

    # Phase 4: Math equation detection
    math_verbs = ('solve', 'simplify', 'evaluate', 'factor', 'expand', 'calculate')
    if any(v in text_lower for v in math_verbs) and re.search(r'[=+\-*/^]', text):
        q['question_type'] = 'math_equation'
        return

    # Phase 5: Extended response
    essay_kw = ('essay', 'in detail', 'write a paragraph', 'extended response', 'explain at length')
    if any(k in text_lower for k in essay_kw) or len(answer) > 300:
        q['question_type'] = 'essay'
        return

    # Phase 6: Section type hint
    if section:
        sec_type = section.get('type', '')
        if sec_type in ('fill_blank', 'essay', 'matching'):
            q['question_type'] = sec_type
            return

    # Phase 7: Clear bad AI geometry type (no mode detected → not visual)
    if ai_type in _ALL_GEOMETRY_TYPES:
        q['question_type'] = 'short_answer'
        return

    # Default
    q['question_type'] = ai_type if ai_type else 'short_answer'


# ── Unified hydration dispatch ────────────────────────────────────────────

def _hydrate_question(q):
    """Populate rendering fields based on question_type. Deterministic — no AI calls."""
    qt = q.get('question_type', 'short_answer')

    # --- Geometry types ---
    if qt in _ALL_GEOMETRY_TYPES:
        _hydrate_geometry(q, qt)
        return

    # --- Function graph ---
    if qt == 'function_graph':
        q.setdefault('x_range', [-10, 10])
        q.setdefault('y_range', [-10, 10])
        q.setdefault('max_expressions', 3)
        if not q.get('correct_expressions'):
            eqs = _extract_equations_from_text(q.get('question', ''))
            if eqs:
                q['correct_expressions'] = eqs
        return

    # --- Coordinate plane ---
    if qt == 'coordinate_plane':
        q.setdefault('x_range', [-10, 10])
        q.setdefault('y_range', [-10, 10])
        q.setdefault('points_to_plot', [])
        return

    # --- Number line ---
    if qt == 'number_line':
        q.setdefault('min_val', -10)
        q.setdefault('max_val', 10)
        q.setdefault('points_to_plot', [])
        return

    # --- Data table ---
    if qt == 'data_table':
        _hydrate_data_table(q)
        return

    # --- Box plot ---
    if qt == 'box_plot':
        _hydrate_box_plot(q)
        return

    # --- Dot plot ---
    if qt == 'dot_plot':
        _hydrate_dot_plot(q)
        return

    # --- Stem and leaf ---
    if qt == 'stem_and_leaf':
        _hydrate_stem_and_leaf(q)
        return

    # --- Bar chart ---
    if qt == 'bar_chart':
        q.setdefault('chart_data', {'labels': [], 'values': [], 'title': ''})
        return

    # --- Transformations ---
    if qt == 'transformations':
        _hydrate_transformations(q)
        return

    # --- Fraction model ---
    if qt == 'fraction_model':
        _hydrate_fraction_model(q)
        return

    # --- Unit circle ---
    if qt == 'unit_circle':
        _hydrate_unit_circle(q)
        return

    # --- Protractor ---
    if qt in ('protractor', 'angle_protractor'):
        _hydrate_protractor(q)
        return

    # --- Venn diagram ---
    if qt == 'venn_diagram':
        q.setdefault('sets', 2)
        q.setdefault('set_labels', ['Set A', 'Set B'])
        q.setdefault('correct_values', {})
        q.setdefault('mode', 'count')
        return

    # --- Tape diagram ---
    if qt == 'tape_diagram':
        q.setdefault('tapes', [])
        q.setdefault('correct_values', {})
        return

    # --- Probability tree ---
    if qt == 'probability_tree':
        q.setdefault('tree', None)
        q.setdefault('correct_values', {})
        return

    # --- FAST types ---
    if qt == 'multiselect':
        correct = q.get('correct', [])
        if isinstance(correct, list):
            q['correct'] = [int(c) for c in correct if isinstance(c, (int, float))]
    elif qt == 'multi_part':
        for part in q.get('parts', []):
            part.setdefault('question_type', 'multiple_choice')
    elif qt == 'grid_match':
        _hydrate_grid_match(q)
    elif qt == 'inline_dropdown':
        _hydrate_inline_dropdown(q)
    elif qt == 'matching':
        _hydrate_matching(q)


def _hydrate_matching(q):
    """Normalize matching question's correct_answer into canonical dict format.

    Frontend MatchingCards.jsx accepts: dict {term: definition}, array of "term - def" strings,
    or integer index array [0,1,2,3]. We normalize everything to the dict format so grading
    and frontend rendering share one canonical shape.
    """
    terms = q.get('terms') or []
    definitions = q.get('definitions') or []
    if not terms or not definitions:
        return

    # Check both 'correct_answer' and 'answer' keys — some generator paths use one or the other
    raw = q.get('correct_answer')
    if raw is None:
        raw = q.get('answer')

    # Already dict format — leave as-is
    if isinstance(raw, dict):
        q['correct_answer'] = raw
        q.setdefault('answer', raw)
        return

    # Integer index array [0, 1, 2, 3] — terms[i] matches definitions[raw[i]]
    if isinstance(raw, list) and raw and all(isinstance(x, (int, float)) for x in raw):
        normalized = {}
        for i, def_idx in enumerate(raw):
            if i >= len(terms):
                break
            idx = int(def_idx)
            if 0 <= idx < len(definitions):
                normalized[terms[i]] = definitions[idx]
        q['correct_answer'] = normalized
        q['answer'] = normalized
        return

    # String array ["Term - definition", "Term: definition"] — parse each entry
    if isinstance(raw, list):
        normalized = {}
        for entry in raw:
            if not isinstance(entry, str):
                continue
            sep_idx = -1
            for sep in (': ', ' - ', ':', '-'):
                sep_idx = entry.find(sep)
                if sep_idx != -1:
                    sep_len = len(sep)
                    break
            if sep_idx == -1:
                continue
            term_part = entry[:sep_idx].strip()
            def_part = entry[sep_idx + sep_len:].strip()
            if term_part and def_part:
                normalized[term_part] = def_part
        if normalized:
            q['correct_answer'] = normalized
            q['answer'] = normalized
            return

    # Fallback: no valid answer found — assume terms[i] maps to definitions[i] in order
    q['correct_answer'] = {terms[i]: definitions[i] for i in range(min(len(terms), len(definitions)))}
    q['answer'] = q['correct_answer']


def _hydrate_geometry(q, qt):
    """Populate geometry dimensions and compute answer."""
    # Extract dimensions from question text BEFORE applying defaults
    _extract_dimensions_from_text(q)
    # Apply shape-specific defaults for any missing fields
    defaults = _GEOMETRY_DEFAULTS.get(qt)
    if defaults:
        for field, value in defaults.items():
            q.setdefault(field, value)
    # Compute derived slant heights for cones/pyramids
    if qt == 'cone' and 'slant_height' not in q:
        q['slant_height'] = round(math.sqrt(q.get('radius', 4)**2 + q.get('height', 6)**2), 2)
    if qt == 'pyramid' and 'slant_height' not in q:
        bv, hv = q.get('base', 6), q.get('height', 8)
        q['slant_height'] = round(math.sqrt(hv**2 + (bv/2)**2), 2)
    # Compute answer from formula registry
    result = _compute_geometry_answer(qt, q)
    if result is not None:
        q['answer'] = str(round(result, 2))


# Regex compiled once for data_table analysis detection
_ANALYSIS_PATTERN = re.compile(
    r'\b(determine|identify|describe|explain|analyze|interpret|compare|classify)\b', re.IGNORECASE
)

# Keywords that signal a column is the computed result (student fills it in)
_CALC_KEYWORDS = re.compile(
    r'\b(calculat|comput|find|determin|solv)', re.IGNORECASE
)
# Formula pattern: "result = operand op operand" e.g. "speed = distance ÷ time"
_FORMULA_RE = re.compile(
    r'(\w[\w\s/]*?)\s*=\s*\w[\w\s/]*?\s*[÷/×*+\-]\s*\w', re.IGNORECASE
)


def _infer_editable_columns(q, question_text):
    """Infer which columns students should fill in based on question text and headers.

    Returns a list of 0-based column indices, or empty list if can't determine.
    """
    headers = q.get('headers', q.get('column_headers', []))
    if not headers:
        return []

    text_lower = question_text.lower()

    # Strategy 1: Match formula result variable to a column header
    # e.g. "speed = distance ÷ time" → editable column is "speed" / "avg speed"
    formula_match = _FORMULA_RE.search(question_text)
    if formula_match:
        result_var = formula_match.group(1).strip().lower()
        for idx, h in enumerate(headers):
            h_lower = h.lower()
            # Check if the formula result variable appears in the header
            # e.g. "speed" in "Avg Speed (m/s)" or "density" in "Density (g/mL)"
            if result_var in h_lower or any(
                word in h_lower for word in result_var.split() if len(word) > 2
            ):
                return [idx]

    # Strategy 2: "calculate/compute/find the X" → match X to headers
    calc_phrases = re.findall(
        r'(?:calculat|comput|find|determin)\w*\s+(?:the\s+)?(?:average\s+|mean\s+|total\s+|net\s+)?'
        r'(\w[\w\s]{2,30}?)(?:\s+(?:for|of|in|from|using|based)\b|[.,;]|\s*$)',
        text_lower,
    )
    if calc_phrases:
        editable = []
        for phrase in calc_phrases:
            phrase_words = set(phrase.strip().split())
            for idx, h in enumerate(headers):
                h_words = set(re.sub(r'\([^)]*\)', '', h).lower().split())
                # Match if the calculated thing shares significant words with a header
                overlap = phrase_words & h_words - {'the', 'a', 'an', 'each', 'for', 'of'}
                if overlap and len(overlap) >= 1:
                    if idx not in editable:
                        editable.append(idx)
        if editable:
            return editable

    # Strategy 3: If row_labels match the first column of expected_data,
    # the first column is labels (given). If all other columns are numeric
    # but only the last column is the "result", mark the last as editable.
    # This catches generic "complete the table" with an obvious structure.
    expected = q.get('expected_data', [])
    row_labels = q.get('row_labels', [])
    if expected and row_labels and _CALC_KEYWORDS.search(text_lower):
        # If there's a clear calculation keyword and we couldn't match above,
        # assume the last column is the computed result
        if len(headers) >= 3:
            return [len(headers) - 1]

    return []


def _hydrate_data_table(q):
    """Normalize data_table fields. Downgrade analysis-type or empty tables to short_answer."""
    # Map AI-generated field names to frontend-expected names
    if 'column_headers' in q and 'headers' not in q:
        q['headers'] = q['column_headers']
    expected = q.get('expected_data', [])
    # If no expected_data but we have headers/row_labels, build a fillable table
    if not expected:
        headers = q.get('headers', q.get('column_headers', []))
        row_labels = q.get('row_labels', [])
        num_rows = q.get('num_rows', len(row_labels) if row_labels else 5)
        num_cols = len(headers) if headers else 2
        if headers or row_labels:
            if not headers:
                q['headers'] = [f'Column {i+1}' for i in range(num_cols)]
            expected = [[''] * num_cols for _ in range(num_rows)]
            q['expected_data'] = expected
            q['initial_data'] = [[''] * num_cols for _ in range(num_rows)]
            q['num_rows'] = num_rows
            return
        # No structural data at all — downgrade
        q['question_type'] = 'short_answer'
        return
    # Downgrade: analysis questions where the student reads data, not fills it
    question_text = q.get('question', '')
    if (_ANALYSIS_PATTERN.search(question_text)
            and 'fill' not in question_text.lower()
            and 'complete' not in question_text.lower()
            and 'calculate' not in question_text.lower()):
        headers = q.get('headers', q.get('column_headers', []))
        if headers:
            table_lines = [' | '.join(str(h) for h in headers)]
            table_lines.append(' | '.join('---' for _ in headers))
            for row in expected:
                table_lines.append(' | '.join(str(v) for v in row))
            table_md = '\n'.join(table_lines)
            if table_md not in question_text:
                q['question'] = question_text.rstrip() + '\n\n' + table_md
        q['question_type'] = 'short_answer'
        return
    # Normal data_table: create initial_data from expected_data
    # Determine editable columns: explicit from AI, or infer from question text + headers
    if 'initial_data' not in q:
        editable = q.get('editable_columns') or _infer_editable_columns(q, question_text)
        if editable:
            q['editable_columns'] = editable  # persist for frontend/grading
            q['initial_data'] = [
                ['' if cIdx in editable else val for cIdx, val in enumerate(row)]
                for row in expected
            ]
        else:
            # Can't determine — all cells editable (classification tables, etc.)
            q['initial_data'] = [[''] * len(row) for row in expected]
    if 'num_rows' not in q:
        q['num_rows'] = len(expected)


def _hydrate_box_plot(q):
    """Compute 5-number summary from data array."""
    q.setdefault('data', [[]])
    q.setdefault('labels', ['Data'])
    raw = q.get('data', [])
    if raw and isinstance(raw[0], list):
        raw = raw[0]
    if raw:
        d = sorted(raw)
        n = len(d)
        def median_of(arr):
            m = len(arr)
            if m % 2 == 0:
                return (arr[m//2 - 1] + arr[m//2]) / 2
            return arr[m//2]
        med = median_of(d)
        lower = d[:n//2]
        upper = d[n//2 + (1 if n % 2 else 0):]
        q1 = median_of(lower) if lower else d[0]
        q3 = median_of(upper) if upper else d[-1]
        q['correct_values'] = {
            'min': d[0], 'max': d[-1], 'median': med,
            'q1': q1, 'q3': q3,
            'range': d[-1] - d[0], 'iqr': q3 - q1
        }


def _hydrate_dot_plot(q):
    """Compute correct_dots frequency map from data array."""
    q.setdefault('min_val', 0)
    q.setdefault('max_val', 10)
    q.setdefault('step', 1)
    q.setdefault('correct_dots', {})
    data = q.get('data', [])
    if data and not q.get('correct_dots'):
        dots = {}
        for val in data:
            key = str(val)
            dots[key] = dots.get(key, 0) + 1
        q['correct_dots'] = dots


def _hydrate_stem_and_leaf(q):
    """Compute correct leaves from data array."""
    q.setdefault('data', [])
    q.setdefault('stems', [])
    q.setdefault('correct_leaves', {})
    data = q.get('data', [])
    if data and not q.get('correct_leaves'):
        leaves = {}
        for val in sorted(data):
            stem = val // 10
            leaf = val % 10
            key = str(stem)
            if key not in leaves:
                leaves[key] = []
            leaves[key].append(str(leaf))
        q['correct_leaves'] = {k: ' '.join(v) for k, v in leaves.items()}
        if not q.get('stems'):
            q['stems'] = sorted(set(str(val // 10) for val in data))


def _hydrate_transformations(q):
    """Compute correct_vertices from original + transform params."""
    q.setdefault('original_vertices', [[1, 1], [4, 1], [4, 3]])
    q.setdefault('transformation_type', 'translation')
    q.setdefault('transform_params', {})
    q.setdefault('correct_vertices', [])
    q.setdefault('grid_range', [-8, 8])
    q.setdefault('mode', 'plot')
    orig = q.get('original_vertices', q.get('originalVertices', []))
    t_type = q.get('transformation_type', q.get('transformationType', ''))
    params = q.get('transform_params', q.get('transformParams', {}))
    if orig and t_type and params and not q.get('correct_vertices', q.get('correctVertices')):
        computed = []
        for v in orig:
            x, y = v[0], v[1]
            if t_type == 'translation':
                computed.append([x + params.get('dx', 0), y + params.get('dy', 0)])
            elif t_type == 'reflection':
                axis = params.get('axis', 'y-axis')
                if axis == 'y-axis':
                    computed.append([-x, y])
                elif axis == 'x-axis':
                    computed.append([x, -y])
                elif axis == 'y=x':
                    computed.append([y, x])
                elif axis == 'y=-x':
                    computed.append([-y, -x])
                else:
                    computed.append([x, y])
            elif t_type == 'rotation':
                deg = params.get('degrees', 90)
                cx = params.get('centerX', 0)
                cy = params.get('centerY', 0)
                rad = math.radians(deg)
                nx = round((x - cx) * math.cos(rad) - (y - cy) * math.sin(rad) + cx, 2)
                ny = round((x - cx) * math.sin(rad) + (y - cy) * math.cos(rad) + cy, 2)
                computed.append([nx, ny])
            elif t_type == 'dilation':
                k = params.get('scale', 2)
                cx = params.get('centerX', 0)
                cy = params.get('centerY', 0)
                computed.append([round(cx + k * (x - cx), 2), round(cy + k * (y - cy), 2)])
            else:
                computed.append([x, y])
        q['correct_vertices'] = computed
        q['correctVertices'] = computed


def _hydrate_fraction_model(q):
    """Compute correct_numerator from answer fraction string."""
    q.setdefault('model_type', 'area')
    q.setdefault('denominator', 4)
    ans = q.get('answer', '')
    if ans and '/' in str(ans) and not q.get('correct_numerator'):
        try:
            parts = str(ans).split('/')
            num = int(parts[0].strip())
            q['correct_numerator'] = num
        except (ValueError, IndexError):
            pass


def _hydrate_unit_circle(q):
    """Fill in standard trig values for hidden angles."""
    q.setdefault('hidden_angles', [])
    q.setdefault('hidden_values', [])
    q.setdefault('correct_values', {})
    if not q.get('correct_values') and not q.get('correctAnswers'):
        std_angles = {
            '0': {'cos': '1', 'sin': '0'},
            '30': {'cos': '\u221a3/2', 'sin': '1/2'},
            '45': {'cos': '\u221a2/2', 'sin': '\u221a2/2'},
            '60': {'cos': '1/2', 'sin': '\u221a3/2'},
            '90': {'cos': '0', 'sin': '1'},
            '120': {'cos': '-1/2', 'sin': '\u221a3/2'},
            '135': {'cos': '-\u221a2/2', 'sin': '\u221a2/2'},
            '150': {'cos': '-\u221a3/2', 'sin': '1/2'},
            '180': {'cos': '-1', 'sin': '0'},
            '210': {'cos': '-\u221a3/2', 'sin': '-1/2'},
            '225': {'cos': '-\u221a2/2', 'sin': '-\u221a2/2'},
            '240': {'cos': '-1/2', 'sin': '-\u221a3/2'},
            '270': {'cos': '0', 'sin': '-1'},
            '300': {'cos': '1/2', 'sin': '-\u221a3/2'},
            '315': {'cos': '\u221a2/2', 'sin': '-\u221a2/2'},
            '330': {'cos': '\u221a3/2', 'sin': '-1/2'},
            '360': {'cos': '1', 'sin': '0'},
        }
        hidden = q.get('hidden_values', q.get('hiddenValues', []))
        if hidden:
            vals = {}
            for h in hidden:
                angle_str = str(h).replace('\u00b0', '')
                if angle_str in std_angles:
                    for k, v in std_angles[angle_str].items():
                        vals[f"{angle_str}_{k}"] = v
            if vals:
                q['correct_values'] = vals
                q['correctAnswers'] = vals


def _hydrate_protractor(q):
    """Set protractor defaults and compute answer from target_angle."""
    q.setdefault('mode', 'measure')
    mode = q.get('mode', 'measure')
    if mode == 'construct' and q.get('target_angle') and not q.get('answer'):
        q['answer'] = str(q['target_angle'])
    elif mode == 'classify' and q.get('target_angle') and not q.get('answer'):
        angle = q['target_angle']
        if angle < 90:
            q['answer'] = 'acute'
        elif angle == 90:
            q['answer'] = 'right'
        elif angle < 180:
            q['answer'] = 'obtuse'
        elif angle == 180:
            q['answer'] = 'straight'
        else:
            q['answer'] = 'reflex'


def _hydrate_grid_match(q):
    """Validate correct matrix dimensions match labels."""
    rows = q.get('row_labels', [])
    cols = q.get('column_labels', [])
    correct = q.get('correct', [])
    if len(correct) != len(rows):
        q['correct'] = correct[:len(rows)] + [[0] * len(cols)] * max(0, len(rows) - len(correct))
    for i, row in enumerate(q.get('correct', [])):
        if len(row) != len(cols):
            q['correct'][i] = row[:len(cols)] + [0] * max(0, len(cols) - len(row))


def _hydrate_inline_dropdown(q):
    """Validate dropdown count matches placeholders in question text."""
    text = q.get('question', '')
    placeholders = re.findall(r'\{(\d+)\}', text)
    dropdowns = q.get('dropdowns', [])
    expected_count = len(placeholders)
    if len(dropdowns) < expected_count:
        while len(dropdowns) < expected_count:
            dropdowns.append({'options': ['\u2014'], 'correct': 0})
        q['dropdowns'] = dropdowns


# ── Shape keyword → question_type mapping ──────────────────────────────────
_SHAPE_KEYWORDS = [
    # Multi-word first (longest match wins)
    ('rectangular prism', 'rectangular_prism'),
    ('regular polygon', 'regular_polygon'),
    ('right triangle', 'triangle'),
    ('isosceles triangle', 'triangle'),
    ('equilateral triangle', 'triangle'),
    ('scalene triangle', 'triangle'),
    ('right prism', 'rectangular_prism'),
    ('triangular prism', 'rectangular_prism'),
    ('square pyramid', 'pyramid'),
    # Single-word
    ('rhombus', 'parallelogram'),
    ('parallelogram', 'parallelogram'),
    ('rectangle', 'rectangle'),
    ('trapezoid', 'trapezoid'),
    ('triangle', 'triangle'),
    ('cylinder', 'cylinder'),
    ('circle', 'circle'),
    ('sphere', 'sphere'),
    ('pyramid', 'pyramid'),
    ('cone', 'cone'),
    ('cube', 'rectangular_prism'),
    ('prism', 'rectangular_prism'),
    ('square', 'rectangle'),
    ('hexagon', 'regular_polygon'),
    ('pentagon', 'regular_polygon'),
    ('octagon', 'regular_polygon'),
    ('heptagon', 'regular_polygon'),
    ('decagon', 'regular_polygon'),
    ('nonagon', 'regular_polygon'),
]

_POLYGON_SIDES = {
    'pentagon': 5, 'hexagon': 6, 'heptagon': 7, 'octagon': 8,
    'nonagon': 9, 'decagon': 10,
}

_MODE_KEYWORDS = [
    ('surface area', 'surface_area'),
    ('lateral area', 'lateral_area'),
    ('pythagorean', 'pythagorean'),
    ('missing side', 'pythagorean'),
    ('hypotenuse', 'pythagorean'),
    ('missing angle', 'angles'),
    ('angle sum', 'angles'),
    ('scale factor', 'similarity'),
    ('similarity', 'similarity'),
    ('similar triangles', 'similarity'),
    ('decompose', 'decompose'),
    ('midsegment', 'midsegment'),
    ('circumference', 'perimeter'),
    ('perimeter', 'perimeter'),
    ('volume', 'volume'),
    ('area', 'area'),
]

_ALL_GEOMETRY_TYPES = {
    'triangle', 'rectangle', 'circle', 'trapezoid', 'parallelogram',
    'regular_polygon', 'rectangular_prism', 'cylinder', 'cone',
    'pyramid', 'sphere', 'geometry',
    'pythagorean', 'angles', 'similarity', 'trig',
}


def _detect_primary_shape(text):
    """Detect the primary geometry shape referenced in question text.

    Returns (question_type, polygon_sides_or_None) or (None, None) if no shape found.
    Uses subject-position heuristics: shapes appearing as 'the [SHAPE]', 'a [SHAPE]',
    'following [SHAPE]' are prioritized. Falls back to first shape mention.
    """
    import re
    text_lower = text.lower()

    # Phase 1: Subject-position patterns — "of the parallelogram", "the following cylinder"
    subject_patterns = [
        r'(?:of|the|this|a|an|following|given)\s+',  # "of the [SHAPE]"
        r'^.*?(?:find|calculate|compute|determine|what is)\b.*?',  # "Find the area of [SHAPE]"
    ]

    best_match = None
    best_pos = len(text_lower)

    for keyword, qtype in _SHAPE_KEYWORDS:
        # Find all occurrences
        for m in re.finditer(r'\b' + re.escape(keyword) + r's?\b', text_lower):
            pos = m.start()
            # Check if this occurrence is in a subject position
            prefix = text_lower[:pos]
            is_subject = False
            for sp in subject_patterns:
                if re.search(sp + r'$', prefix):
                    is_subject = True
                    break

            # Subject-position shapes get priority (negative position)
            effective_pos = -1000 + pos if is_subject else pos

            if effective_pos < best_pos:
                best_pos = effective_pos
                best_match = (qtype, keyword)

    if best_match:
        qtype, keyword = best_match
        sides = _POLYGON_SIDES.get(keyword)
        return qtype, sides

    return None, None


def _detect_mode(text):
    """Detect the calculation mode from question text."""
    text_lower = text.lower()
    for keyword, mode in _MODE_KEYWORDS:
        if keyword in text_lower:
            return mode
    return None


def _is_identification_question(text):
    """Check if question text is asking to identify/classify a shape (not calculate)."""
    import re
    identification_patterns = [
        r'\bidentify\b',
        r'\bname\s+the\b',
        r'\bwhat\s+type\b',
        r'\bclassify\b',
        r'\bwhich\s+type\b',
        r'\bwhich\s+shape\b',
        r'\bwhat\s+kind\b',
    ]
    return any(re.search(p, text, re.IGNORECASE) for p in identification_patterns)


def _infer_shape_answer(text):
    """Infer the shape name from property descriptions in the question text."""
    import re
    text_lower = text.lower()

    has_equal_sides = bool(re.search(r'four\s+equal\s+sides|all\s+sides\s+equal', text_lower))
    has_right_angles = bool(re.search(r'four\s+right\s+angles|all\s+angles\s+(?:are\s+)?90', text_lower))
    has_perp_diag = bool(re.search(r'diagonals?\s+(?:are\s+)?perpendicular|right\s+angles?\s+diagonals?', text_lower))
    has_one_parallel = bool(re.search(r'one\s+pair\s+of\s+parallel\s+sides|exactly\s+one\s+pair.*parallel', text_lower))
    has_opp_equal = bool(re.search(r'opposite\s+sides\s+(?:are\s+)?(?:equal|parallel|congruent)', text_lower))

    if has_equal_sides and has_perp_diag:
        return 'rhombus'
    if has_equal_sides and has_right_angles:
        return 'square'
    if has_right_angles:
        return 'rectangle'
    if has_one_parallel:
        return 'trapezoid'
    if has_opp_equal:
        return 'parallelogram'

    return None


def _looks_like_graphing_question(text):
    """Check if question text suggests it should be a graphing/function_graph question."""
    import re
    graphing_patterns = [
        r'graph\s+(the\s+)?(line|equation|function|system)',
        r'(view|see|look at)\s+(the\s+)?graph',
        r'on\s+(the\s+)?(coordinate\s+plane|graph)',
        r'(plot|sketch|draw)\s+(the\s+)?(graph|line|function)',
        r'shown\s+on\s+the\s+(coordinate\s+plane|graph)',
        r'system\s+of\s+(linear\s+)?equations',
        r'(slope|y-intercept).*graph',
    ]
    return any(re.search(p, text) for p in graphing_patterns)


def _extract_equations_from_text(text):
    """Extract y = ... or f(x) = ... equations from question text."""
    import re
    equations = []
    # Match patterns like: y = 2x + 1, y = -x + 3, f(x) = x^2 - 4
    patterns = [
        r'y\s*=\s*([^,.\n;]+?)(?=[,.\n;]|\s+and\s+|\s+shown|\s+on|\s+how|\s+determine|\s+what|\s+find|$)',
        r'f\s*\(\s*x\s*\)\s*=\s*([^,.\n;]+?)(?=[,.\n;]|\s+and\s+|\s+shown|\s+on|\s+how|\s+determine|\s+what|\s+find|$)',
    ]
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for m in matches:
            expr = m.strip().rstrip('.')
            if expr and len(expr) > 1:
                # Normalize: ensure "y = " prefix
                if not expr.lower().startswith('y') and not expr.lower().startswith('f'):
                    expr = 'y = ' + expr
                elif expr.lower().startswith('f'):
                    expr = 'y = ' + re.sub(r'f\s*\(\s*x\s*\)\s*=\s*', '', expr, flags=re.IGNORECASE)
                else:
                    expr = 'y = ' + expr
                equations.append(expr)
    # Deduplicate while preserving order
    seen = set()
    unique = []
    for eq in equations:
        norm = eq.replace(' ', '').lower()
        if norm not in seen:
            seen.add(norm)
            unique.append(eq)
    return unique


def _split_markdown_table(text):
    """Detect markdown pipe tables in text and split into parts.

    Returns { before, table: { headers, rows }, after } or None if no table found.
    Handles both multi-line and single-line pipe table formats.
    """
    import re
    if not text or '|' not in text:
        return None

    lines = text.split('\n') if '\n' in text else re.split(r'(?=\|[\s-]+\|)', text)

    table_lines = []
    before_lines = []
    after_lines = []
    in_table = False

    for i, line in enumerate(lines):
        stripped = line.strip()
        # Separator row (|---|---|)
        is_sep = bool(re.match(r'^\|[\s\-:|]+\|$', stripped))
        # Data row (| x | y |)
        is_pipe = stripped.startswith('|') and stripped.endswith('|') and stripped.count('|') >= 3

        if (is_pipe or is_sep) and not in_table:
            in_table = True
            before_lines = lines[:i]

        if in_table:
            if is_pipe or is_sep:
                table_lines.append(stripped)
            else:
                after_lines = lines[i:]
                break
        if not in_table and i == len(lines) - 1:
            return None  # No table found

    if len(table_lines) < 2:
        return None

    def parse_row(line):
        cells = line.split('|')
        return [c.strip() for c in cells if c.strip() and not re.match(r'^[\s\-:]+$', c.strip())]

    # Filter out separator rows
    data_rows = [l for l in table_lines if not re.match(r'^\|[\s\-:|]+\|$', l)]
    if len(data_rows) < 2:
        return None

    headers = parse_row(data_rows[0])
    rows = [parse_row(r) for r in data_rows[1:]]

    return {
        'before': ' '.join(before_lines).strip(),
        'table': {'headers': headers, 'rows': rows},
        'after': ' '.join(after_lines).strip()
    }


def _extract_dimensions_from_text(question):
    """Extract numeric dimensions from question text when JSON fields are missing.

    Catches cases where the AI puts 'radius = 2 and height = 5' in the question text
    but omits the actual JSON fields, causing wrong defaults to be applied.
    Handles patterns like: 'Base = 8 cm', 'radius of 5', 'height is 12 meters', 'r = 3'
    """
    import re
    text = question.get('question', '')
    if not text:
        return

    # Unit suffix that may follow a number (optional capture, not part of value)
    _UNIT = r'(?:\s*(?:cm|m|mm|in|ft|yd|units?|meters?|feet|inches|yards|kilometers?|km|miles?|mi)?)'

    # Dual-base extraction: "bases measuring 10 cm and 14 cm" or "bases of 10 and 14"
    dual = re.search(
        r'bases\s+(?:measuring|of)\s+([\d.]+)' + _UNIT + r'\s+and\s+([\d.]+)',
        text, re.IGNORECASE
    )
    if dual and 'base' not in question and 'topBase' not in question:
        v1, v2 = float(dual.group(1)), float(dual.group(2))
        question['base'] = max(v1, v2)
        question['topBase'] = min(v1, v2)

    # Map of text patterns to JSON field names
    # Each entry: field → list of regex patterns (first match wins)
    # Patterns are ordered: explicit (= :) → verbal (of/is) → bare number (last resort)
    dimension_patterns = {
        'radius': [
            r'radius\s*[=:]\s*([\d.]+)' + _UNIT,
            r'radius\s+(?:of|is|measures?)\s+([\d.]+)' + _UNIT,
            r'r\s*=\s*([\d.]+)' + _UNIT,
            r'radius\s+([\d.]+)' + _UNIT,  # bare: "radius 5 cm"
        ],
        'height': [
            r'height\s*[=:]\s*([\d.]+)' + _UNIT,
            r'height\s+(?:of|is|measures?)\s+([\d.]+)' + _UNIT,
            r'h\s*=\s*([\d.]+)' + _UNIT,
            r'height\s+([\d.]+)' + _UNIT,  # bare: "height 4"
        ],
        'base': [
            r'(?<!top\s)base\s*[=:]\s*([\d.]+)' + _UNIT,
            r'(?<!top\s)base\s+(?:of|is|measures?)\s+([\d.]+)' + _UNIT,
            r'b\s*=\s*([\d.]+)' + _UNIT,
            r'length\s*[=:]\s*([\d.]+)' + _UNIT,  # "length" → base
            r'length\s+(?:of|is|measures?)\s+([\d.]+)' + _UNIT,
            r'length\s+([\d.]+)' + _UNIT,  # bare: "length 10 cm"
            r'(?<!top\s)base\s+([\d.]+)' + _UNIT,  # bare: "base 8"
        ],
        'topBase': [
            r'top\s*base\s*[=:]\s*([\d.]+)' + _UNIT,
            r'top\s*base\s+(?:of|is|measures?)\s+([\d.]+)' + _UNIT,
            r'parallel\s+side[s]?\s*[=:]\s*([\d.]+)' + _UNIT,
        ],
        'width': [
            r'width\s*[=:]\s*([\d.]+)' + _UNIT,
            r'width\s+(?:of|is|measures?)\s+([\d.]+)' + _UNIT,
            r'w\s*=\s*([\d.]+)' + _UNIT,
            r'width\s+([\d.]+)' + _UNIT,  # bare: "width 6 cm"
        ],
        'side_length': [
            r'side\s*(?:length)?\s*[=:]\s*([\d.]+)' + _UNIT,
            r'(?:each\s+)?side\s+(?:is|of|measures?)\s+([\d.]+)' + _UNIT,
        ],
        'slant_height': [
            r'slant\s*height\s*[=:]\s*([\d.]+)' + _UNIT,
            r'slant\s+(?:of|is|measures?)\s+([\d.]+)' + _UNIT,
            r'l\s*=\s*([\d.]+)' + _UNIT,
        ],
        'midsegment': [
            r'midsegment\s*(?:measuring|of|is|=|:)\s*([\d.]+)' + _UNIT,
            r'midsegment\s+([\d.]+)' + _UNIT,
        ],
    }

    for field, patterns in dimension_patterns.items():
        if field not in question:  # Only extract if not already in JSON
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    try:
                        question[field] = float(match.group(1))
                    except ValueError:
                        pass
                    break

    # ── Pythagorean-specific extraction ──────────────────────────────────
    # When mode is pythagorean, extract side_a, side_b, side_c from text
    mode = question.get('mode', '')
    qt = question.get('question_type', '')
    if mode == 'pythagorean' or qt == 'pythagorean':
        _extract_pythagorean_sides(question, text, _UNIT)


def _extract_pythagorean_sides(question, text, _UNIT):
    """Extract side_a, side_b, side_c and missing_side from pythagorean question text."""
    import re

    # Extract hypotenuse
    hyp = None
    hyp_patterns = [
        r'hypotenuse\s*(?:is|=|:| of)\s*([\d.]+)' + _UNIT,
        r'hypotenuse\s+([\d.]+)' + _UNIT,
        r'c\s*=\s*([\d.]+)' + _UNIT,
    ]
    for p in hyp_patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            hyp = float(m.group(1))
            break
    # Also check JSON fields the AI might have used
    if not hyp:
        hyp = question.get('hypotenuse') or question.get('side_c')

    # Extract legs — look for "one side is X", "legs of X and Y", "sides X and Y"
    legs = []
    # "legs of 5 and 12" or "sides of 5 and 12"
    dual = re.search(r'(?:legs?|sides?)\s+(?:of|are|measuring)\s+([\d.]+)\s*(?:and|,)\s*([\d.]+)', text, re.IGNORECASE)
    if dual:
        legs = [float(dual.group(1)), float(dual.group(2))]
    else:
        # "one side is 5" / "a side of 5" / "one leg is 5"
        side_matches = re.findall(r'(?:one\s+)?(?:side|leg)\s+(?:is|of|=|:| measures?)\s*([\d.]+)', text, re.IGNORECASE)
        for sm in side_matches:
            v = float(sm)
            if v not in legs:
                legs.append(v)

    # Also check JSON fields
    if question.get('side_a') and question['side_a'] not in legs:
        legs.append(float(question['side_a']))
    if question.get('side_b') and question['side_b'] not in legs:
        legs.append(float(question['side_b']))

    # Assign: side_a (bottom), side_b (vertical), side_c (hypotenuse)
    if hyp and len(legs) >= 1:
        question.setdefault('side_a', legs[0])
        question.setdefault('side_c', hyp)
        if len(legs) >= 2:
            question.setdefault('side_b', legs[1])
        # Derive missing side
        a = question.get('side_a')
        c = question.get('side_c')
        b = question.get('side_b')
        if a and c and not b:
            question['side_b'] = round(math.sqrt(c ** 2 - a ** 2) * 100) / 100
            question.setdefault('missing_side', 'b')
        elif b and c and not a:
            question['side_a'] = round(math.sqrt(c ** 2 - b ** 2) * 100) / 100
            question.setdefault('missing_side', 'a')
        elif a and b and not c:
            question['side_c'] = round(math.sqrt(a ** 2 + b ** 2) * 100) / 100
            question.setdefault('missing_side', 'c')
    elif hyp and len(legs) == 0:
        # Only hypotenuse given — mark c, missing_side stays as is
        question.setdefault('side_c', hyp)
        question.setdefault('missing_side', 'c')
    elif len(legs) >= 2 and not hyp:
        question.setdefault('side_a', legs[0])
        question.setdefault('side_b', legs[1])
        question.setdefault('side_c', round(math.sqrt(legs[0] ** 2 + legs[1] ** 2) * 100) / 100)
        question.setdefault('missing_side', 'c')

    # Ensure mode is set
    question.setdefault('mode', 'pythagorean')


_GEOMETRY_DEFAULTS = {
    'triangle':          {'base': 6, 'height': 4, 'mode': 'area'},
    'pythagorean':       {'side_a': 3, 'side_b': 4, 'side_c': 5, 'missing_side': 'c', 'mode': 'pythagorean'},
    'geometry':          {'base': 6, 'height': 4, 'mode': 'area'},
    'rectangle':         {'base': 6, 'height': 4, 'mode': 'area'},
    'circle':            {'radius': 5, 'mode': 'area'},
    'trapezoid':         {'topBase': 4, 'base': 8, 'height': 5, 'mode': 'area'},
    'parallelogram':     {'base': 7, 'height': 4, 'mode': 'area'},
    'regular_polygon':   {'sides': 6, 'side_length': 4, 'mode': 'area'},
    'rectangular_prism': {'base': 5, 'width': 3, 'height': 4, 'mode': 'volume'},
    'cylinder':          {'radius': 3, 'height': 7, 'mode': 'volume'},
    'cone':              {'radius': 4, 'height': 6, 'slant_height': 7.21, 'mode': 'volume'},
    'pyramid':           {'base': 6, 'height': 8, 'slant_height': 8.54, 'mode': 'volume'},
    'sphere':            {'radius': 5, 'mode': 'volume'},
}


def _compute_geometry_answer(qt, q):
    """Compute answer for any (shape, mode) pair. Returns float or None."""
    import math

    mode = q.get('mode', 'area')
    b    = q.get('base', 6)
    h    = q.get('height', 4)
    w    = q.get('width', b)
    r    = q.get('radius', 5)
    tb   = q.get('topBase', q.get('top_base', 4))
    n    = q.get('sides', 6)
    s    = q.get('side_length', 4)
    sl   = q.get('slant_height', 0)

    # ── AREA ──
    if mode == 'area':
        if qt in ('triangle', 'geometry'):  return b * h / 2
        if qt == 'rectangle':               return w * h
        if qt == 'circle':                  return math.pi * r**2
        if qt == 'trapezoid':               return 0.5 * (b + tb) * h
        if qt == 'parallelogram':           return b * h
        if qt == 'regular_polygon':
            apothem = s / (2 * math.tan(math.pi / n))
            return 0.5 * n * s * apothem

    # ── PERIMETER ──
    if mode == 'perimeter':
        if qt in ('triangle', 'geometry'):
            return q.get('side_a', 5) + q.get('side_b', 4) + q.get('side_c', 3)
        if qt == 'rectangle':               return 2 * w + 2 * h
        if qt == 'circle':                  return 2 * math.pi * r
        if qt == 'trapezoid':
            offset = abs(b - tb) / 2
            leg = math.sqrt(offset**2 + h**2) if h else offset
            return b + tb + 2 * leg
        if qt == 'parallelogram':
            side = q.get('side_length', q.get('width', math.sqrt(h**2 + 4)))
            return 2 * b + 2 * side
        if qt == 'regular_polygon':         return n * s

    # circumference is perimeter for circles
    if mode == 'circumference' and qt == 'circle':
        return 2 * math.pi * r

    # ── VOLUME ──
    if mode == 'volume':
        if qt == 'rectangular_prism':       return b * w * h
        if qt == 'cylinder':                return math.pi * r**2 * h
        if qt == 'cone':                    return (1/3) * math.pi * r**2 * h
        if qt == 'pyramid':                 return (1/3) * b**2 * h
        if qt == 'sphere':                  return (4/3) * math.pi * r**3

    # ── SURFACE AREA ──
    if mode == 'surface_area':
        if qt == 'rectangular_prism':       return 2 * (b*w + b*h + w*h)
        if qt == 'cylinder':                return 2*math.pi*r**2 + 2*math.pi*r*h
        if qt == 'cone':                    return math.pi*r**2 + math.pi*r*sl
        if qt == 'pyramid':                 return b**2 + 2*b*sl
        if qt == 'sphere':                  return 4 * math.pi * r**2

    # ── LATERAL AREA ──
    if mode == 'lateral_area':
        if qt == 'cone':                    return math.pi * r * sl
        if qt == 'pyramid':                 return 2 * b * sl

    # ── MIDSEGMENT ──
    if mode == 'midsegment':
        if qt == 'trapezoid':               return (b + tb) / 2

    # ── DECOMPOSE ──
    if mode == 'decompose':
        if qt == 'regular_polygon':
            apothem = s / (2 * math.tan(math.pi / n))
            return 0.5 * n * s * apothem

    # ── TRIANGLE-SPECIFIC MODES ──
    if qt in ('triangle', 'geometry'):
        if mode == 'pythagorean':
            a = q.get('side_a', b)
            bv = q.get('side_b', h)
            missing = q.get('missing_side', 'c')
            if missing == 'c': return math.sqrt(a**2 + bv**2)
            elif missing == 'a':
                c = q.get('side_c', math.sqrt(a**2 + bv**2))
                return math.sqrt(c**2 - bv**2)
            elif missing == 'b':
                c = q.get('side_c', math.sqrt(a**2 + bv**2))
                return math.sqrt(c**2 - a**2)
        if mode == 'angles':
            a1, a2 = q.get('angle1', 60), q.get('angle2', 70)
            missing = q.get('missing_angle', 3)
            if missing == 3: return 180 - a1 - a2
            elif missing == 2: return 180 - a1 - q.get('angle3', 50)
            elif missing == 1: return 180 - a2 - q.get('angle3', 50)
        if mode == 'trig':
            theta_rad = math.radians(q.get('theta', 30))
            func = q.get('trig_func', 'sin')
            solve_for = q.get('solve_for', None)
            hyp = q.get('side_c', q.get('hypotenuse', 10))
            ratio = {'sin': math.sin, 'cos': math.cos, 'tan': math.tan}.get(func, math.sin)(theta_rad)
            if not solve_for: return round(ratio, 4)
            if solve_for in ('opp', 'opposite'): return hyp * math.sin(theta_rad)
            if solve_for in ('adj', 'adjacent'): return hyp * math.cos(theta_rad)
            if solve_for in ('hyp', 'hypotenuse'):
                opp = q.get('side_a', q.get('opposite', 5))
                return opp / math.sin(theta_rad)

    return None  # Unsupported (shape, mode) pair


# ── PR3: Quality Validation (project filter + quality checks) ─────────────
# Phase 3b1 PR3 additions. Moved byte-identical from backend/routes/planner_routes.py.


# ── Phase 3b: Project/activity question filter ──────────────────────────────
import re as _re

_PROJECT_KEYWORDS = _re.compile(
    r'\b('
    r'create\s+(a|an|the)\s+(infographic|poster|brochure|pamphlet|flyer|diorama|model|presentation|slideshow|video|song|rap|skit|collage|mural|display|exhibit|portfolio|scrapbook|comic|storyboard)'
    r'|design\s+(a|an|the)\s+(infographic|poster|brochure|pamphlet|flyer|project|presentation|website|app)'
    r'|using\s+(canva|google\s+slides?|powerpoint|prezi|piktochart|adobe|imovie|tinkercad|scratch|desmos|geogebra)'
    r'|submit\s+(the|your|a|an)\s+(infographic|poster|project|presentation|video|recording|physical)'
    r'|build\s+(a|an)\s+(model|diorama|prototype|display)'
    r'|perform\s+(a|an)\s+(skit|presentation|demonstration)'
    r'|collaborate\s+with\s+(your|a)\s+(partner|group|classmates?|team)'
    r'|work\s+with\s+(your|a)\s+(partner|group|classmates?|team)\s+to'
    r'|present\s+(your|the)\s+(findings|project|work|results)\s+to\s+(the\s+)?class'
    r'|record\s+(a|yourself|your)\s+(video|audio|presentation|screencast)'
    r')\b',
    _re.IGNORECASE,
)


def _is_project_question(q):
    """Return True if the question is a project/activity that can't be answered in the portal."""
    text = q.get('question', '')
    return bool(_PROJECT_KEYWORDS.search(text))


# ── Phase 3c: Question quality validation ─────────────────────────────────


def _validate_question_quality(assignment, subject=None, grade=None, valid_standard_codes=None):
    """Phase 3c: Run deterministic quality checks on every question.

    Returns a list of warning dicts: [{section_idx, question_idx, issue, severity}]
    Attaches 'warning' and 'warning_severity' fields to flagged questions.
    Also removes duplicate questions (identical question text).
    """
    warnings = []

    # ── Deduplication: remove questions with identical text ──
    seen_texts = set()
    for section in assignment.get('sections', []):
        unique_questions = []
        for q in section.get('questions', []):
            text = (q.get('question', '') or '').strip().lower()
            if text and text in seen_texts:
                # Skip duplicate — don't even include it
                continue
            if text:
                seen_texts.add(text)
            unique_questions.append(q)
        section['questions'] = unique_questions

    for sIdx, section in enumerate(assignment.get('sections', [])):
        for qIdx, q in enumerate(section.get('questions', [])):
            issues = _check_question_quality(q, subject=subject, grade=grade,
                                             valid_standard_codes=valid_standard_codes)
            if issues:
                # Use the most severe issue as the primary warning
                worst = max(issues, key=lambda i: 0 if i['severity'] == 'warning' else 1)
                q['warning'] = worst['issue']
                q['warning_severity'] = worst['severity']
                for issue in issues:
                    warnings.append({
                        'section_idx': sIdx,
                        'question_idx': qIdx,
                        'issue': issue['issue'],
                        'severity': issue['severity'],
                    })
    return warnings


def _check_question_quality(q, subject=None, grade=None, valid_standard_codes=None):
    """Run Tier A deterministic checks on a single question. Returns list of issues."""
    issues = []
    qt = q.get('question_type', q.get('type', 'short_answer'))
    text = q.get('question', '')

    # Check 1: Removed — point values are corrected by _normalize_points (Phase 5).
    # Flagging here produced confusing "Auto-fixed: Invalid point value" warnings
    # on questions whose points were already corrected by the time the user sees them.

    # Check 2: Answer exists for non-essay/extended types
    non_answer_types = {'essay', 'extended_response', 'multi_part'}
    if qt not in non_answer_types:
        answer = q.get('answer')
        if answer is None or answer == '' or answer == []:
            issues.append({'issue': 'Missing answer key', 'severity': 'warning'})

    # Check 3: MC answer matches one of the options
    if qt == 'multiple_choice' and q.get('options') and q.get('answer'):
        answer = str(q['answer']).strip()
        options = q.get('options', [])
        option_texts = [str(o).strip() for o in options]
        # Check both direct match and letter-prefix match (e.g., "B" matches "B) ...")
        matched = False
        for opt_text in option_texts:
            if answer == opt_text or opt_text.startswith(answer + ')') or opt_text.startswith(answer + '.'):
                matched = True
                break
        # Also check if answer is a letter A-D and we have that many options
        if not matched and len(answer) == 1 and answer.upper() in 'ABCDEFGH':
            idx = ord(answer.upper()) - ord('A')
            if 0 <= idx < len(options):
                matched = True
        if not matched:
            issues.append({'issue': 'Answer does not match any option', 'severity': 'error'})

    # Check 4: Over-determined math problems (more givens than needed)
    if qt in ('math_equation', 'geometry', 'short_answer', 'triangle', 'circle',
              'rectangle', 'trapezoid', 'regular_polygon'):
        numbers = _re.findall(r'\b\d+(?:\.\d+)?\b', text)
        # More than 5 distinct numeric values in a single question is suspicious
        distinct_nums = set(numbers)
        if len(distinct_nums) > 5:
            issues.append({
                'issue': f'Potentially over-determined: {len(distinct_nums)} numeric values given',
                'severity': 'warning',
            })

    # Check 5: Tangent-secant consistency check
    if 'tangent' in text.lower() and ('secant' in text.lower() or 'external' in text.lower()):
        numbers = [float(n) for n in _re.findall(r'\b\d+(?:\.\d+)?\b', text)]
        if len(numbers) >= 3:
            # t² = external × whole — check if any triplet satisfies this
            from itertools import combinations
            found_valid = False
            for combo in combinations(numbers, 3):
                a, b, c = sorted(combo)
                # Check t² = ext × whole in all permutations
                if (abs(a * a - b * c) < 0.5 or abs(b * b - a * c) < 0.5
                        or abs(c * c - a * b) < 0.5):
                    found_valid = True
                    break
            if not found_valid and len(numbers) >= 3:
                issues.append({
                    'issue': 'Given values may not satisfy tangent-secant theorem (t² = external × whole)',
                    'severity': 'warning',
                })

    # Check 6: Pythagorean theorem consistency
    if _re.search(r'\b(right\s+triangle|hypotenuse)\b', text, _re.IGNORECASE):
        numbers = [float(n) for n in _re.findall(r'\b\d+(?:\.\d+)?\b', text)]
        if len(numbers) >= 3:
            from itertools import combinations
            found_valid = False
            for combo in combinations(numbers, 3):
                a, b, c = sorted(combo)
                if abs(a * a + b * b - c * c) < 0.5:
                    found_valid = True
                    break
            if not found_valid:
                issues.append({
                    'issue': 'Given values may not satisfy Pythagorean theorem (a² + b² = c²)',
                    'severity': 'warning',
                })

    # Check 7: Mixing 3D physical with 2D geometry
    _3d_words = _re.compile(
        r'\b(tower|cable|pole|building|ladder|wall|ground|shadow|height of the)\b', _re.IGNORECASE
    )
    _2d_theorems = _re.compile(
        r'\b(inscribed angle|central angle|chord[- ]chord|tangent[- ]secant|secant[- ]secant|'
        r'arc length|sector area|power of a point)\b', _re.IGNORECASE
    )
    if _3d_words.search(text) and _2d_theorems.search(text):
        issues.append({
            'issue': 'Mixes 3D physical scenario with 2D circle theorem — may confuse students',
            'severity': 'warning',
        })

    # ── ELA / Reading checks ──────────────────────────────────────────────

    # Check 8: Question references a passage/text but none is included
    _PASSAGE_REF_RE = _re.compile(
        r'\b(according to the (passage|text|article|excerpt|author|narrator|speaker|poem|story)'
        r'|refer(ring)? to the (passage|text|reading|excerpt|article)'
        r'|based on the (passage|text|reading|excerpt|article)'
        r'|in the (passage|text|excerpt|article|poem|story) above'
        r'|re-?read (the |this )?(passage|text|excerpt|paragraph|stanza)'
        r'|the (passage|text|excerpt|article|poem|story) (states|describes|suggests|implies|reveals|shows|demonstrates|indicates|mentions)'
        r'|use (textual |)evidence from the (passage|text|reading)'
        r'|cite evidence from the (passage|text))\b',
        _re.IGNORECASE,
    )
    if _PASSAGE_REF_RE.search(text):
        # A question referencing a passage should have substantial text embedding it.
        # Heuristic: if the question is under 300 chars, the passage is almost certainly
        # not included inline — it's a dangling reference.
        if len(text) < 300:
            issues.append({
                'issue': 'References a passage/text but no passage appears to be included in the question',
                'severity': 'error',
            })

    # Check 9: "Read the following" but passage is too short to be real
    _READ_FOLLOWING_RE = _re.compile(
        r'\b(read the following|read this)\s+(passage|text|excerpt|article|poem|paragraph|story)',
        _re.IGNORECASE,
    )
    if _READ_FOLLOWING_RE.search(text):
        # Split on the directive to find the passage portion
        parts = _READ_FOLLOWING_RE.split(text, maxsplit=1)
        # The passage body is everything after the "read the following passage" phrase
        passage_body = parts[-1] if len(parts) > 1 else ''
        # Strip any trailing question portion (often after a blank line or question mark)
        passage_lines = passage_body.split('\n')
        passage_content = '\n'.join(
            ln for ln in passage_lines
            if not _re.match(r'^\s*(question|what |how |why |which |where |when |who |identify|explain|describe|analyze|compare|evaluate)', ln, _re.IGNORECASE)
        ).strip()
        if len(passage_content) < 80:
            issues.append({
                'issue': 'Says "read the following" but the included passage is too short or missing',
                'severity': 'warning',
            })

    # Check 10: Quotation/citation without attribution
    _QUOTE_RE = _re.compile(r'[""\u201c].{15,}?[""\u201d]')
    _ATTRIBUTION_RE = _re.compile(
        r'\b(according to|written by|by [A-Z]|from ["\u201c]|—\s*[A-Z]|\(\w+,?\s*\d{4}\))\b',
        _re.IGNORECASE,
    )
    if _QUOTE_RE.search(text) and not _ATTRIBUTION_RE.search(text):
        # Only flag for ELA-style questions (not math word problems that might quote a scenario)
        if qt in ('short_answer', 'extended_response', 'essay', 'multiple_choice'):
            # Check the quote isn't just a math expression or short phrase
            quote_match = _QUOTE_RE.search(text)
            quoted_text = quote_match.group(0) if quote_match else ''
            if len(quoted_text) > 40:  # Substantial quote, not a term definition
                issues.append({
                    'issue': 'Contains a substantial quotation without clear attribution (author/source)',
                    'severity': 'warning',
                })

    # ── Science checks ─────────────────────────────────────────────────────

    # Check 11: Mixed unit systems (metric + imperial in same question)
    _METRIC_UNITS = _re.compile(
        r'\b(\d+(?:\.\d+)?)\s*'
        r'(meters?|m\b|centimeters?|cm\b|millimeters?|mm\b|kilometers?|km\b'
        r'|grams?|g\b|kilograms?|kg\b|milligrams?|mg\b'
        r'|liters?|L\b|milliliters?|mL\b'
        r'|degrees?\s*[Cc]elsius|°C'
        r'|newtons?|N\b|joules?|J\b|watts?|W\b|pascals?|Pa\b)',
        _re.IGNORECASE,
    )
    _IMPERIAL_UNITS = _re.compile(
        r'\b(\d+(?:\.\d+)?)\s*'
        r'(feet|ft\b|foot|inches|in\b|inch|yards?|yd\b|miles?\b|mi\b'
        r'|pounds?|lbs?\b|ounces?|oz\b|tons?\b'
        r'|gallons?|gal\b|quarts?|qt\b|pints?\b|cups?\b|fl\.?\s*oz'
        r'|degrees?\s*[Ff]ahrenheit|°F)',
        _re.IGNORECASE,
    )
    has_metric = _METRIC_UNITS.search(text)
    has_imperial = _IMPERIAL_UNITS.search(text)
    # Mixed units are a problem UNLESS the question is explicitly about conversion
    _CONVERSION_HINT = _re.compile(
        r'\b(convert|conversion|equivalent|how many .+ in|express .+ in|change .+ to)\b',
        _re.IGNORECASE,
    )
    if has_metric and has_imperial and not _CONVERSION_HINT.search(text):
        issues.append({
            'issue': 'Mixes metric and imperial units — use one system or make it a conversion problem',
            'severity': 'warning',
        })

    # Check 12: Physically impossible values for common quantities
    _IMPOSSIBLE_CHECKS = [
        # (pattern to find value+unit, validation function, issue message)
        (
            _re.compile(r'(-?\d+(?:\.\d+)?)\s*(?:degrees?\s*[Cc]elsius|°C)\b'),
            lambda v: v < -273.15,
            'Temperature below absolute zero ({val}°C)',
        ),
        (
            _re.compile(r'(-?\d+(?:\.\d+)?)\s*(?:degrees?\s*[Ff]ahrenheit|°F)\b'),
            lambda v: v < -459.67,
            'Temperature below absolute zero ({val}°F)',
        ),
        (
            _re.compile(r'(-?\d+(?:\.\d+)?)\s*(?:kg|kilograms?|g|grams?|mg|milligrams?|lbs?|pounds?|oz|ounces?)\b', _re.IGNORECASE),
            lambda v: v < 0,
            'Negative mass ({val}) — mass cannot be negative',
        ),
        (
            _re.compile(r'(-?\d+(?:\.\d+)?)\s*(?:m/s|km/h|mph|ft/s)\b', _re.IGNORECASE),
            lambda v: v < 0,
            'Negative speed ({val}) — speed is a scalar and cannot be negative',
        ),
        (
            _re.compile(r'\bpH\s+(?:of\s+)?(-?\d+(?:\.\d+)?)\b', _re.IGNORECASE),
            lambda v: v < 0 or v > 14,
            'pH value {val} is outside valid range (0-14)',
        ),
        (
            _re.compile(r'(\d+(?:\.\d+)?)\s*%\s*(?:concentration|efficiency|probability|chance|yield)\b', _re.IGNORECASE),
            lambda v: v > 100,
            'Percentage value {val}% exceeds 100%',
        ),
    ]
    for pattern, is_invalid, msg_template in _IMPOSSIBLE_CHECKS:
        match = pattern.search(text)
        if match:
            try:
                val = float(match.group(1))
                if is_invalid(val):
                    issues.append({
                        'issue': msg_template.format(val=match.group(1)),
                        'severity': 'error',
                    })
            except (ValueError, IndexError):
                pass

    # Check 13: Science question references a diagram/figure/lab setup not provided
    _FIGURE_REF_RE = _re.compile(
        r'\b(refer to (the |)(figure|diagram|graph|chart|table|image|picture|illustration|lab setup|model|map)'
        r'|(figure|diagram|graph|chart|table|image|illustration)\s+(above|below|on the right|on the left|shown)'
        r'|see (the |)(figure|diagram|graph|chart) (\d+|[A-Z])'
        r'|use the (data|graph|chart|diagram|figure|table) (provided|shown|above|below))\b',
        _re.IGNORECASE,
    )
    if _FIGURE_REF_RE.search(text):
        # For data_table type, the table data is in structured fields — that's fine
        if qt not in ('data_table', 'box_plot', 'dot_plot', 'stem_and_leaf',
                       'bar_chart', 'coordinate_plane', 'function_graph'):
            # Check if there's structured visual data attached
            has_visual_data = any(q.get(f) for f in [
                'chart_data', 'data', 'expected_data', 'column_headers',
                'original_vertices', 'points_to_plot',
            ])
            if not has_visual_data and len(text) < 500:
                issues.append({
                    'issue': 'References a figure/diagram/graph but no visual data is included in the question',
                    'severity': 'error',
                })

    # Check 14: data_table with empty or placeholder expected_data
    if qt == 'data_table':
        expected = q.get('expected_data', [])
        if not expected:
            issues.append({
                'issue': 'Data table has no expected_data — table will appear empty',
                'severity': 'error',
            })
        elif expected:
            # Check if all cells are empty/placeholder
            all_empty = all(
                all(cell == '' or cell is None for cell in row)
                for row in expected
            )
            if all_empty:
                issues.append({
                    'issue': 'Data table expected_data contains only empty values — no correct answers provided',
                    'severity': 'error',
                })

    # CHECK 15: Off-subject detection via standards validation
    if valid_standard_codes and q.get('standard'):
        q_standard = q['standard'].strip()
        if q_standard and q_standard not in valid_standard_codes:
            # Check prefix match (e.g., "SC.6.E" matches "SC.6.E.7.1")
            prefix_match = any(q_standard.startswith(code) or code.startswith(q_standard)
                               for code in valid_standard_codes)
            if not prefix_match:
                issues.append({
                    'issue': f'Off-subject: standard "{q_standard}" is not in the selected '
                             f'{subject or "subject"} standards for grade {grade or "this grade"}',
                    'severity': 'error',
                })

    return issues


# ─────────────────────────────────────────────────────────────────────────────
# PR4: _auto_fix_flagged_questions with explicit-context signature
# ─────────────────────────────────────────────────────────────────────────────


def _auto_fix_flagged_questions(assignment, warnings, subject=None, grade=None,
                                valid_standard_codes=None, *, user_id=None, client=None):
    """Attempt AI-powered fixes for flagged questions.

    Uses gpt-4o-mini to review and fix problematic questions in a single batch.
    Only called when deterministic checks flag issues.

    Explicit-context signature (PR4): callers pass `user_id` and an OpenAI
    `client` instance — preferred path, zero Flask coupling.

    Fallback (PR5): when `_post_process_assignment` (also in this module)
    calls this byte-identically without user_id/client, fall back to pulling
    from Flask `g` and building a client from `backend.api_keys`. This keeps
    the orchestrator body unchanged while preserving production behavior.
    If neither explicit args nor a live Flask context provide a usable key,
    the function silently returns (matches the old adapter's behavior).
    """
    # Collect questions with errors (not just warnings)
    error_items = [w for w in warnings if w['severity'] == 'error']
    if not error_items:
        return  # Only auto-fix errors; warnings are shown to teacher

    # PR5 fallback: when called from the byte-identical _post_process_assignment
    # (co-located in this module) without user_id/client, derive them from
    # Flask g + backend.api_keys. Silently return on any failure so the
    # grading pipeline never crashes on an auto-fix setup issue.
    if user_id is None or client is None:
        try:
            from flask import g as _flask_g
            from backend.api_keys import get_api_key as _get_api_key
            from openai import OpenAI as _OpenAI
            if user_id is None:
                user_id = getattr(_flask_g, 'user_id', 'local-dev')
            if client is None:
                api_key = _get_api_key('openai', user_id)
                if not api_key or api_key.startswith('your-'):
                    return
                client = _OpenAI(api_key=api_key)
        except Exception as e:
            print(f"Auto-fix quality check failed (non-fatal): {e}")
            return

    # Build batch for AI review
    batch = []
    for w in error_items:
        s = assignment.get('sections', [])[w['section_idx']]
        q = s.get('questions', [])[w['question_idx']]
        batch.append({
            'index': len(batch),
            'section_idx': w['section_idx'],
            'question_idx': w['question_idx'],
            'question': q.get('question', ''),
            'question_type': q.get('question_type', 'short_answer'),
            'answer': q.get('answer', ''),
            'options': q.get('options', []),
            'issue': w['issue'],
        })

    if not batch or len(batch) > 20:
        return  # Skip if too many — something else is wrong

    try:
        subject_constraint = ''
        if subject and grade:
            standards_hint = ''
            if valid_standard_codes:
                standards_hint = f"\n- Valid standard codes: {', '.join(valid_standard_codes[:10])}"
            subject_constraint = f"""
CRITICAL SUBJECT CONSTRAINT:
- All fixed questions MUST be for {subject} at grade {grade} level{standards_hint}
- If a question was flagged as off-subject, REPLACE it entirely with a {subject} question
  that maps to one of the valid standard codes above
"""

        prompt = f"""Review these {len(batch)} questions that were flagged for issues.
For each, provide a corrected version. Return JSON array:
[{{"index": 0, "fixed_question": "corrected question text", "fixed_answer": "corrected answer", "fixed_options": ["A) ...", ...] or null, "fixed_standard": "standard code or null"}}]
{subject_constraint}
Flagged questions:
{json.dumps(batch, indent=2)}

Rules:
- Fix mathematical inconsistencies so given values are correct
- For MC questions, ensure the answer matches one option
- Keep the same difficulty level and topic
- If flagged as off-subject, replace with an on-subject question for the correct standard
- Return ONLY the JSON array, no other text"""

        completion = with_retry(
            lambda: client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You fix assessment questions. Return valid JSON only."},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.3,
            ),
            label="auto_fix_flagged_questions",
        )

        content = completion.choices[0].message.content
        result = json.loads(content)
        fixes = result if isinstance(result, list) else result.get('fixes', result.get('questions', []))

        # Apply fixes
        for fix in fixes:
            idx = fix.get('index')
            if idx is None or idx >= len(batch):
                continue
            item = batch[idx]
            s = assignment.get('sections', [])[item['section_idx']]
            q = s.get('questions', [])[item['question_idx']]
            if fix.get('fixed_question'):
                q['question'] = fix['fixed_question']
            if fix.get('fixed_answer'):
                q['answer'] = fix['fixed_answer']
            if fix.get('fixed_options') and isinstance(fix['fixed_options'], list):
                q['options'] = fix['fixed_options']
            if fix.get('fixed_standard'):
                q['standard'] = fix['fixed_standard']
            # Update warning to indicate it was auto-fixed
            q['warning'] = f"Auto-fixed: {item['issue']}"
            q['warning_severity'] = 'info'

        usage = _extract_usage(completion, "gpt-4o-mini")
        _record_planner_cost(usage)

    except Exception as e:
        print(f"Auto-fix quality check failed (non-fatal): {e}")


# ─────────────────────────────────────────────────────────────────────────────
# PR5: Orchestrator + prompt builders (moved byte-identical from planner_routes)
# ─────────────────────────────────────────────────────────────────────────────


def _build_subject_boundary_prompt(subject, grade, standard_codes=None):
    """Build mandatory subject/grade boundary constraint for AI prompts."""
    if not subject or not grade:
        return ''

    valid_codes_line = ''
    if standard_codes:
        valid_codes_line = (
            f"\n- Valid standard codes for this assessment: {', '.join(standard_codes)}"
            f"\n- ONLY use these exact standard codes in question 'standard' fields"
        )

    return f"""
SUBJECT BOUNDARY CONSTRAINT (MANDATORY — VIOLATIONS WILL BE REJECTED):
This content is EXCLUSIVELY for {subject} at grade {grade} level.
- EVERY question MUST directly test {subject} content knowledge
- EVERY question's "standard" field MUST reference one of the provided standards{valid_codes_line}
- Ensure vocabulary and cognitive complexity are appropriate for grade {grade}
- Do NOT generate questions that primarily test a different subject area
- Cross-disciplinary skills (reading a graph, writing an explanation) are acceptable ONLY when they serve {subject} content
- Questions violating these constraints will be automatically detected and regenerated
"""


def _build_section_categories_prompt(categories, subject='', question_type_counts=None):
    """Build AI prompt section describing which assessment sections to generate."""
    if not categories or not any(categories.values()):
        return "Generate standard sections: Multiple Choice and Short Answer."

    section_map = {
        'multiple_choice': {
            'name': 'Multiple Choice',
            'instruction': 'Generate standard multiple choice questions with 4 options (A-D). Use type "multiple_choice".',
        },
        'short_answer': {
            'name': 'Short Answer / Gridded Response',
            'instruction': 'Generate short answer questions requiring 1-3 sentence responses or numeric answers. Use type "short_answer".',
        },
        'math_computation': {
            'name': 'Math Computation',
            'instruction': 'Generate math computation questions (solve equations, evaluate expressions, simplify). Use type "math_equation". Include the equation in the question text.',
        },
        'geometry_visual': {
            'name': 'Geometry & Measurement',
            'instruction': 'Generate geometry questions with interactive visuals. Use question_type "geometry" and include shape_type, dimensions, and measurement_type fields. Supported shapes: rectangle, triangle, circle, trapezoid, parallelogram, cylinder, cone, sphere, prism. Students interact with shape renderers — do NOT ask them to draw.',
        },
        'graphing': {
            'name': 'Graphing & Coordinate Plane',
            'instruction': 'Generate questions using interactive graphs. Use question_type "function_graph" (with x_range, y_range, correct_expressions as equation strings) for graphing lines/functions/systems. Use "coordinate_plane" (with min_val, max_val, points_to_plot as [x,y] pairs) for plotting points. Use "number_line" (with min_val, max_val, points_to_plot) for number lines. ALWAYS set the correct question_type and include all data fields — the system renders graphs programmatically from these fields.',
        },
        'data_analysis': {
            'name': 'Data Analysis',
            'instruction': 'Generate data analysis questions with interactive visuals. Use question_type "data_table" (with column_headers, row_labels, expected_data), "box_plot" (with data array, labels), "dot_plot" (with min_val/max_val/step, correct_dots), "stem_and_leaf" (with data, stems, correct_leaves), "bar_chart" (with chart_data). ALWAYS set the correct question_type and include all data fields.',
        },
        'extended_writing': {
            'name': 'Extended Writing / Essay',
            'instruction': 'Generate extended response questions requiring paragraph-length analysis with evidence. Use type "extended_response". Include a detailed rubric.',
        },
        'vocabulary': {
            'name': 'Vocabulary / Matching',
            'instruction': 'Generate vocabulary matching questions. Use type "matching" with terms and definitions arrays.',
        },
        'true_false': {
            'name': 'True / False',
            'instruction': 'Generate true/false statement evaluation questions. Use type "true_false".',
        },
        'florida_fast': {
            'name': 'FL FAST Item Types',
            'instruction': 'Generate Florida FAST-style items. Use "multiselect" (select all that apply with options array and correct indices array), "multi_part" (compound Part A/B with parts array where each part has its own question_type, options, answer, and points), "grid_match" (matrix matching with row_labels, column_labels, and correct 2D one-hot array), "inline_dropdown" (cloze with {0},{1} placeholders in question text and dropdowns array with options and correct index). These mirror the actual FAST test format.',
        },
    }

    enabled = [k for k, v in categories.items() if v]
    lines = ["ALLOWED section types (use ONLY the ones relevant to the topic/standards):"]
    for i, key in enumerate(enabled, 1):
        info = section_map.get(key, {})
        count = (question_type_counts or {}).get(key, 0)
        if count and count > 0:
            lines.append("  - " + info.get('name', key) + " (EXACTLY " + str(count) + " questions): " + info.get('instruction', ''))
        else:
            lines.append("  - " + info.get('name', key) + ": " + info.get('instruction', ''))

    disabled = [k for k, v in categories.items() if not v]
    if disabled:
        disabled_names = [section_map.get(k, {}).get('name', k) for k in disabled]
        lines.append(f"\nNEVER include these section types: {', '.join(disabled_names)}")

    lines.append("\nIMPORTANT: Only use section types that are relevant to the ACTUAL TOPIC being assessed.")
    lines.append("Do NOT force a section type just because it is allowed — e.g., do NOT add a Geometry section to a statistics/data topic, do NOT add Data Analysis to a pure algebra topic.")
    lines.append("Every question must directly relate to the standards and topic. Never generate filler questions from unrelated math domains.")
    lines.append("Organize the assignment into separate sections, each with its own 'name', 'instructions', and 'questions' array.")
    return '\n'.join(lines)


def _post_process_assignment(assignment, target_question_count=None, target_total_points=None,
                             subject=None, grade=None, valid_standard_codes=None):
    """Unified 6-phase deterministic post-processing pipeline.

    Phase 1: _classify_question_type — assigns question_type from text/structure
    Phase 2: _hydrate_question — populates rendering fields (dimensions, answers, etc.)
    Phase 3: _validate_question — downgrades broken questions to short_answer
    Phase 3b: _filter_project_questions — removes project/activity prompts
    Phase 3c: _validate_question_quality — flags problematic questions
    Phase 4: _enforce_question_count — trims/pads to target (if provided)
    Phase 5: _normalize_points — ensures points sum correctly
    """
    if not assignment or not isinstance(assignment, dict):
        return assignment, None
    for section in assignment.get('sections', []):
        for q in section.get('questions', []):
            _classify_question_type(q, section)   # Phase 1: Deterministic type
            _hydrate_question(q)                   # Phase 2: Populate fields
            _validate_question(q)                  # Phase 3: Downgrade if broken
    # Phase 3b: Strip questions that are projects/activities (not answerable in portal)
    for section in assignment.get('sections', []):
        section['questions'] = [
            q for q in section.get('questions', [])
            if not _is_project_question(q)
        ]
    # Remove empty sections left after filtering
    assignment['sections'] = [
        s for s in assignment.get('sections', [])
        if s.get('questions')
    ]
    # Phase 3c: Validate question quality (deterministic + optional AI fix)
    warnings = _validate_question_quality(assignment, subject=subject, grade=grade,
                                          valid_standard_codes=valid_standard_codes)
    if warnings:
        _auto_fix_flagged_questions(assignment, warnings, subject=subject, grade=grade,
                                    valid_standard_codes=valid_standard_codes)
    extra_usage = None
    # Phase 4: Enforce question count (if target given)
    if target_question_count is not None:
        assignment, extra_usage = _enforce_question_count(assignment, target_question_count)
    # Phase 5: Normalize points (always runs)
    _normalize_points(assignment, target_total_points)
    return assignment, extra_usage
