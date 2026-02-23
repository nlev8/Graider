"""
Lesson Planner API routes for Graider.
Handles standards retrieval and lesson plan generation/export.
"""
import os
import sys
import json
import time
import subprocess
from flask import Blueprint, request, jsonify
from pathlib import Path

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


GEOMETRY_SUBTYPES = {
    'geometry', 'triangle', 'rectangle', 'circle', 'trapezoid',
    'parallelogram', 'rectangular_prism', 'cylinder', 'regular_polygon',
    'pythagorean', 'angles', 'similarity', 'trig'
}


def _build_section_categories_prompt(categories, subject=''):
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
    }

    enabled = [k for k, v in categories.items() if v]
    lines = [f"ALLOWED section types (use ONLY the ones relevant to the topic/standards):"]
    for i, key in enumerate(enabled, 1):
        info = section_map.get(key, {})
        lines.append(f"  - {info.get('name', key)}: {info.get('instruction', '')}")

    disabled = [k for k, v in categories.items() if not v]
    if disabled:
        disabled_names = [section_map.get(k, {}).get('name', k) for k in disabled]
        lines.append(f"\nNEVER include these section types: {', '.join(disabled_names)}")

    lines.append("\nIMPORTANT: Only use section types that are relevant to the ACTUAL TOPIC being assessed.")
    lines.append("Do NOT force a section type just because it is allowed — e.g., do NOT add a Geometry section to a statistics/data topic, do NOT add Data Analysis to a pure algebra topic.")
    lines.append("Every question must directly relate to the standards and topic. Never generate filler questions from unrelated math domains.")
    lines.append("Organize the assignment into separate sections, each with its own 'name', 'instructions', and 'questions' array.")
    return '\n'.join(lines)


def _auto_upgrade_visual_types(assignment):
    """Programmatically detect questions that should be visual types but were generated as short_answer.

    The AI sometimes generates questions like 'View the graph of y = 2x + 1...' as short_answer
    instead of function_graph with the proper data fields. This function:
    1. Detects equation patterns in question text and upgrades to function_graph
    2. Detects coordinate/point plotting and upgrades to coordinate_plane
    3. Ensures all visual types have their required data fields
    4. Validates existing visual questions have complete data
    """
    import re

    if not assignment or not isinstance(assignment, dict):
        return assignment

    for section in assignment.get('sections', []):
        for q in section.get('questions', []):
            qt = q.get('question_type', q.get('type', ''))
            text = q.get('question', '').lower()

            # ── Auto-upgrade: short_answer questions about graphing → function_graph ──
            if qt in ('short_answer', '') and _looks_like_graphing_question(text):
                equations = _extract_equations_from_text(q.get('question', ''))
                if equations:
                    q['question_type'] = 'function_graph'
                    q.setdefault('x_range', [-10, 10])
                    q.setdefault('y_range', [-10, 10])
                    q['correct_expressions'] = equations
                    q.setdefault('max_expressions', len(equations))
                    # Clean the question text — remove "view the graph" phrasing
                    cleaned = re.sub(
                        r'(?i)(view|see|look at|observe|examine)\s+(the\s+)?(graph|diagram|plot|coordinate plane)\s*(below|above|shown|of)?\s*',
                        '', q.get('question', '')
                    ).strip()
                    if cleaned:
                        q['question'] = cleaned[0].upper() + cleaned[1:] if len(cleaned) > 1 else cleaned.upper()

            # ── Validate function_graph has required fields ──
            if q.get('question_type') == 'function_graph':
                q.setdefault('x_range', [-10, 10])
                q.setdefault('y_range', [-10, 10])
                # Try to extract expressions from question text if missing
                if not q.get('correct_expressions'):
                    equations = _extract_equations_from_text(q.get('question', ''))
                    if equations:
                        q['correct_expressions'] = equations
                q.setdefault('max_expressions', max(len(q.get('correct_expressions', [])), 1))

            # ── Validate coordinate_plane has required fields ──
            if q.get('question_type') == 'coordinate_plane':
                q.setdefault('min_val', -10)
                q.setdefault('max_val', 10)
                q.setdefault('points_to_plot', [])

            # ── Validate number_line has required fields ──
            if q.get('question_type') == 'number_line':
                q.setdefault('min_val', -10)
                q.setdefault('max_val', 10)
                q.setdefault('points_to_plot', [])

            # ── Validate box_plot has required fields ──
            if q.get('question_type') == 'box_plot':
                q.setdefault('data', [[]])
                q.setdefault('labels', ['Data'])

            # ── Validate bar_chart has required fields ──
            if q.get('question_type') == 'bar_chart':
                q.setdefault('chart_data', {'labels': [], 'values': [], 'title': ''})

            # ── Validate dot_plot has required fields ──
            if q.get('question_type') == 'dot_plot':
                q.setdefault('min_val', 0)
                q.setdefault('max_val', 10)
                q.setdefault('step', 1)
                q.setdefault('correct_dots', {})

            # ── Validate stem_and_leaf has required fields ──
            if q.get('question_type') == 'stem_and_leaf':
                q.setdefault('data', [])
                q.setdefault('stems', [])
                q.setdefault('correct_leaves', {})

            # ── Validate transformations has required fields ──
            if q.get('question_type') == 'transformations':
                q.setdefault('original_vertices', [[1, 1], [4, 1], [4, 3]])
                q.setdefault('transformation_type', 'translation')
                q.setdefault('transform_params', {})
                q.setdefault('correct_vertices', [])
                q.setdefault('grid_range', [-8, 8])
                q.setdefault('mode', 'plot')

            # ── Validate fraction_model has required fields ──
            if q.get('question_type') == 'fraction_model':
                q.setdefault('model_type', 'area')
                q.setdefault('denominator', 4)

            # ── Validate unit_circle has required fields ──
            if q.get('question_type') == 'unit_circle':
                q.setdefault('hidden_angles', [])
                q.setdefault('hidden_values', [])
                q.setdefault('correct_values', {})

            # ── Validate protractor has required fields ──
            if q.get('question_type') in ('protractor', 'angle_protractor'):
                q.setdefault('mode', 'measure')

            # ── Validate venn_diagram has required fields ──
            if q.get('question_type') == 'venn_diagram':
                q.setdefault('sets', 2)
                q.setdefault('set_labels', ['Set A', 'Set B'])
                q.setdefault('correct_values', {})
                q.setdefault('mode', 'count')

            # ── Validate tape_diagram has required fields ──
            if q.get('question_type') == 'tape_diagram':
                q.setdefault('tapes', [])
                q.setdefault('correct_values', {})

            # ── Validate probability_tree has required fields ──
            if q.get('question_type') == 'probability_tree':
                q.setdefault('tree', None)
                q.setdefault('correct_values', {})

    return assignment


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


def _ensure_geometry_defaults(assignment):
    """Ensure geometry questions in an assignment have required default fields."""
    if not assignment or not isinstance(assignment, dict):
        return assignment
    for section in assignment.get('sections', []):
        for q in section.get('questions', []):
            qt = q.get('question_type', '')
            if qt == 'regular_polygon':
                q.setdefault('sides', 6)
                q.setdefault('side_length', 4)
                q.setdefault('mode', 'area')
            elif qt in ('triangle', 'geometry'):
                q.setdefault('base', 6)
                q.setdefault('height', 4)
                q.setdefault('mode', 'area')
            elif qt == 'rectangle':
                q.setdefault('base', 6)
                q.setdefault('height', 4)
                q.setdefault('mode', 'area')
            elif qt == 'circle':
                q.setdefault('radius', 5)
            elif qt == 'trapezoid':
                q.setdefault('topBase', 4)
                q.setdefault('base', 8)
                q.setdefault('height', 5)
            elif qt == 'parallelogram':
                q.setdefault('base', 7)
                q.setdefault('height', 4)
            elif qt == 'rectangular_prism':
                q.setdefault('base', 5)
                q.setdefault('width', 3)
                q.setdefault('height', 4)
            elif qt == 'cylinder':
                q.setdefault('radius', 3)
                q.setdefault('height', 7)
    return assignment


def _ensure_data_table_defaults(assignment):
    """Normalize data_table questions so frontend receives the expected field names."""
    if not assignment or not isinstance(assignment, dict):
        return assignment
    for section in assignment.get('sections', []):
        for q in section.get('questions', []):
            qt = q.get('question_type', q.get('type', ''))
            if qt == 'data_table':
                # Map AI-generated field names to frontend-expected names
                if 'column_headers' in q and 'headers' not in q:
                    q['headers'] = q['column_headers']
                # Create blank initial_data from expected_data shape
                expected = q.get('expected_data', [])
                if expected and 'initial_data' not in q:
                    q['initial_data'] = [[''] * len(row) for row in expected]
                # Ensure num_rows for PDF export
                if expected and 'num_rows' not in q:
                    q['num_rows'] = len(expected)
    return assignment


def _hydrate_math_visuals(assignment):
    """Programmatically compute correct answers and visual data for math/visual questions.

    The AI should only pick the concept and provide minimal params (dimensions, data, etc.).
    This function does ALL the math — areas, volumes, quartiles, transformations, etc.
    Code is 100% correct; AI is bad at arithmetic.
    """
    import math

    if not assignment or not isinstance(assignment, dict):
        return assignment

    for section in assignment.get('sections', []):
        for q in section.get('questions', []):
            qt = q.get('question_type', q.get('type', ''))

            # ── Geometry: compute answer from dimensions ──
            if qt in ('triangle', 'geometry'):
                mode = q.get('mode', 'area')
                base = q.get('base', 6)
                height = q.get('height', 4)
                if mode == 'area':
                    q['answer'] = str(round(base * height / 2, 2))
                elif mode == 'perimeter':
                    a = q.get('side_a', 5)
                    b = q.get('side_b', 4)
                    c = q.get('side_c', 3)
                    q['answer'] = str(round(a + b + c, 2))
                elif mode == 'pythagorean':
                    a = q.get('side_a', base)
                    b = q.get('side_b', height)
                    missing = q.get('missing_side', 'c')
                    if missing == 'c':
                        q['answer'] = str(round(math.sqrt(a**2 + b**2), 2))
                    elif missing == 'a':
                        c = q.get('side_c', math.sqrt(a**2 + b**2))
                        q['answer'] = str(round(math.sqrt(c**2 - b**2), 2))
                    elif missing == 'b':
                        c = q.get('side_c', math.sqrt(a**2 + b**2))
                        q['answer'] = str(round(math.sqrt(c**2 - a**2), 2))
                elif mode == 'angles':
                    a1 = q.get('angle1', 60)
                    a2 = q.get('angle2', 70)
                    missing = q.get('missing_angle', 3)
                    if missing == 3:
                        q['answer'] = str(round(180 - a1 - a2, 2))
                    elif missing == 2:
                        a3 = q.get('angle3', 50)
                        q['answer'] = str(round(180 - a1 - a3, 2))
                    elif missing == 1:
                        a3 = q.get('angle3', 50)
                        q['answer'] = str(round(180 - a2 - a3, 2))
                elif mode == 'trig':
                    theta_deg = q.get('theta', 30)
                    theta_rad = math.radians(theta_deg)
                    func = q.get('trig_func', 'sin')
                    solve_for = q.get('solve_for', None)
                    hyp = q.get('side_c', q.get('hypotenuse', 10))
                    if func == 'sin':
                        ratio = math.sin(theta_rad)
                    elif func == 'cos':
                        ratio = math.cos(theta_rad)
                    else:
                        ratio = math.tan(theta_rad)
                    if not solve_for:
                        q['answer'] = str(round(ratio, 4))
                    elif solve_for in ('opp', 'opposite'):
                        q['answer'] = str(round(hyp * math.sin(theta_rad), 2))
                    elif solve_for in ('adj', 'adjacent'):
                        q['answer'] = str(round(hyp * math.cos(theta_rad), 2))
                    elif solve_for in ('hyp', 'hypotenuse'):
                        opp = q.get('side_a', q.get('opposite', 5))
                        q['answer'] = str(round(opp / math.sin(theta_rad), 2))

            elif qt == 'rectangle':
                w = q.get('width', q.get('base', 6))
                h = q.get('height', 4)
                mode = q.get('mode', 'area')
                if mode == 'area':
                    q['answer'] = str(round(w * h, 2))
                elif mode == 'perimeter':
                    q['answer'] = str(round(2 * w + 2 * h, 2))

            elif qt == 'circle':
                r = q.get('radius', 5)
                mode = q.get('mode', 'area')
                if mode == 'area':
                    q['answer'] = str(round(math.pi * r**2, 2))
                elif mode in ('circumference', 'perimeter'):
                    q['answer'] = str(round(2 * math.pi * r, 2))

            elif qt == 'trapezoid':
                b1 = q.get('base', 8)
                b2 = q.get('topBase', q.get('top_base', 4))
                h = q.get('height', 5)
                q['answer'] = str(round(0.5 * (b1 + b2) * h, 2))

            elif qt == 'parallelogram':
                b = q.get('base', 7)
                h = q.get('height', 4)
                q['answer'] = str(round(b * h, 2))

            elif qt == 'regular_polygon':
                sides = q.get('sides', 6)
                sl = q.get('side_length', 4)
                mode = q.get('mode', 'area')
                if mode == 'perimeter':
                    q['answer'] = str(round(sides * sl, 2))
                elif mode == 'area':
                    apothem = sl / (2 * math.tan(math.pi / sides))
                    q['answer'] = str(round(0.5 * sides * sl * apothem, 2))

            elif qt == 'rectangular_prism':
                l = q.get('base', 5)
                w = q.get('width', 3)
                h = q.get('height', 4)
                mode = q.get('mode', 'volume')
                if mode == 'volume':
                    q['answer'] = str(round(l * w * h, 2))
                elif mode == 'surface_area':
                    q['answer'] = str(round(2 * (l*w + l*h + w*h), 2))

            elif qt == 'cylinder':
                r = q.get('radius', 3)
                h = q.get('height', 7)
                mode = q.get('mode', 'volume')
                if mode == 'volume':
                    q['answer'] = str(round(math.pi * r**2 * h, 2))
                elif mode == 'surface_area':
                    q['answer'] = str(round(2 * math.pi * r**2 + 2 * math.pi * r * h, 2))

            # ── Box Plot: compute 5-number summary from data ──
            elif qt == 'box_plot':
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

            # ── Stem and Leaf: compute correct leaves from data ──
            elif qt == 'stem_and_leaf':
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

            # ── Dot Plot: compute correct_dots from data ──
            elif qt == 'dot_plot':
                data = q.get('data', [])
                if data and not q.get('correct_dots'):
                    dots = {}
                    for val in data:
                        key = str(val)
                        dots[key] = dots.get(key, 0) + 1
                    q['correct_dots'] = dots

            # ── Transformations: compute correct_vertices from params ──
            elif qt == 'transformations':
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

            # ── Fraction Model: compute correct_numerator from answer fraction ──
            elif qt == 'fraction_model':
                ans = q.get('answer', '')
                denom = q.get('denominator', 4)
                if ans and '/' in str(ans) and not q.get('correct_numerator'):
                    try:
                        parts = str(ans).split('/')
                        num = int(parts[0].strip())
                        q['correct_numerator'] = num
                    except (ValueError, IndexError):
                        pass

            # ── Protractor: set answer from target_angle for construct mode ──
            elif qt in ('protractor', 'angle_protractor'):
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

            # ── Unit Circle: set standard trig values ──
            elif qt == 'unit_circle':
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

    return assignment


planner_bp = Blueprint('planner', __name__)

# Path to standards data
DATA_DIR = Path(__file__).parent.parent / 'data'
DOCUMENTS_DIR = os.path.expanduser("~/.graider_data/documents")


def load_support_documents_for_planning() -> str:
    """Load curriculum guides, standards, and other planning documents."""
    if not os.path.exists(DOCUMENTS_DIR):
        return ""

    docs_content = []
    total_chars = 0
    max_chars = 12000  # Increased limit for richer planning context

    # Document types useful for lesson planning (prioritized)
    planning_doc_types = ['curriculum', 'standards', 'pacing_guide', 'textbook', 'assessment', 'general']

    for f in os.listdir(DOCUMENTS_DIR):
        if f.endswith('.meta.json'):
            try:
                with open(os.path.join(DOCUMENTS_DIR, f), 'r') as mf:
                    metadata = json.load(mf)

                doc_type = metadata.get('doc_type', 'general')
                filepath = metadata.get('filepath', '')
                description = metadata.get('description', '')

                # Include all planning-relevant document types
                if doc_type not in planning_doc_types:
                    continue

                if not os.path.exists(filepath):
                    continue

                content = ""
                if filepath.endswith('.txt') or filepath.endswith('.md'):
                    with open(filepath, 'r', encoding='utf-8') as df:
                        content = df.read()
                elif filepath.endswith('.docx'):
                    try:
                        from docx import Document
                        doc = Document(filepath)
                        content = '\n'.join([p.text for p in doc.paragraphs])
                    except:
                        continue
                elif filepath.endswith('.pdf'):
                    try:
                        import fitz
                        pdf = fitz.open(filepath)
                        content = '\n'.join([page.get_text() for page in pdf])
                        pdf.close()
                    except:
                        continue

                if content and total_chars + len(content) < max_chars:
                    doc_label = doc_type.upper()
                    if description:
                        doc_label += f" - {description}"
                    # Use more content per document (up to 4000 chars)
                    chunk = content[:4000]
                    docs_content.append(f"[{doc_label}]\n{chunk}")
                    total_chars += len(chunk)

            except Exception as e:
                continue

    if not docs_content:
        return ""

    return "\n\nREFERENCE DOCUMENTS:\n" + "\n\n".join(docs_content)


def load_standards(state, subject, grade=None):
    """Load standards from JSON file, optionally filtered by grade."""
    # Clean subject name for filename (replace spaces with underscores, slashes with hyphens)
    subject_clean = subject.lower().replace(' ', '_').replace('/', '-')
    filename = f"standards_{state.lower()}_{subject_clean}.json"
    filepath = DATA_DIR / filename

    if filepath.exists():
        with open(filepath, 'r') as f:
            data = json.load(f)
            # Handle both formats: wrapped dict {"standards": [...]} or flat array [...]
            if isinstance(data, list):
                standards = data
                file_grade = ''
            else:
                standards = data.get('standards', [])
                file_grade = data.get('grade', '')  # e.g., "7", "8", "9-10", "6-8"

            # Filter by grade if provided
            if grade and standards:
                # Check if file covers a single grade that matches exactly
                if file_grade and str(file_grade) == str(grade) and '-' not in str(file_grade):
                    # Exact single-grade match - return all standards
                    return standards

                # Check if the requested grade is within the file's range
                grade_in_range = False
                if file_grade and '-' in str(file_grade):
                    parts = str(file_grade).split('-')
                    try:
                        min_grade = int(parts[0])
                        max_grade = int(parts[1])
                        requested = int(grade) if grade.isdigit() else 0
                        grade_in_range = min_grade <= requested <= max_grade
                    except (ValueError, IndexError):
                        pass

                # Map grades to high school courses (subject-specific)
                GRADE_TO_COURSE = {
                    'math': {'9': 'Algebra 1', '10': 'Geometry', '11': 'Algebra 2', '12': 'Pre-Calculus'},
                    'science': {'9': 'Biology', '10': 'Chemistry', '11': 'Physics', '12': 'Earth/Space Science'},
                    'us_history': {'9': 'American History', '10': 'American History', '11': 'American History', '12': 'American History'},
                    'world_history': {'9': 'World History', '10': 'World History', '11': 'World History', '12': 'World History'},
                }
                subject_courses = GRADE_TO_COURSE.get(subject_clean, {})

                # Filter by code pattern (for multi-grade files or fallback)
                filtered = []
                for s in standards:
                    code = s.get('code', '')
                    # Extract grade from code patterns like MA.6.xxx, SC.7.xxx, SS.8.xxx
                    code_parts = code.split('.')
                    if len(code_parts) >= 2:
                        code_grade = code_parts[1]
                        # Match grade (handle K, 1-12)
                        if code_grade == grade or code_grade == f"0{grade}":
                            filtered.append(s)
                        # For kindergarten
                        elif grade == 'K' and code_grade in ['K', '0', '00']:
                            filtered.append(s)
                        # For high school codes like "912" - filter by course field
                        elif code_grade == '912' and grade in subject_courses:
                            expected_course = subject_courses[grade]
                            if s.get('course') == expected_course:
                                filtered.append(s)

                # If we found grade-specific standards, return them
                if filtered:
                    return filtered
                # If grade is in the file's range but no code-based matches,
                # return all (file may not use grade-based code patterns)
                if grade_in_range:
                    return standards
                return []  # No matches for this grade
            return standards
    return []


@planner_bp.route('/api/get-standards', methods=['POST'])
def get_standards():
    """Get standards for a specific state, grade, and subject."""
    data = request.json
    state = data.get('state', 'FL')
    grade = data.get('grade', '7')
    subject = data.get('subject', 'Civics')

    # Try to load from JSON files first, filtered by grade
    standards = load_standards(state, subject, grade)

    if standards:
        return jsonify({"standards": standards, "grade": grade, "subject": subject})

    # Fallback to empty if no data file exists
    return jsonify({"standards": [], "grade": grade, "subject": subject})


@planner_bp.route('/api/get-lesson-templates', methods=['POST'])
def get_lesson_templates():
    """Get subject-specific lesson activity templates."""
    data = request.json
    subject = data.get('subject', '').lower().replace(' ', '_').replace('/', '-')

    templates_file = DATA_DIR / 'lesson_templates.json'
    if not templates_file.exists():
        return jsonify({"templates": None, "error": "Templates file not found"})

    try:
        with open(templates_file, 'r') as f:
            all_templates = json.load(f)

        # Try exact match first
        if subject in all_templates:
            return jsonify({"templates": all_templates[subject], "subject": subject})

        # Try partial match (e.g., 'us_history' -> 'social_studies')
        subject_mapping = {
            'us_history': 'social_studies',
            'world_history': 'social_studies',
            'civics': 'social_studies',
            'english-ela': 'social_studies',  # Use social_studies templates as fallback
        }

        mapped_subject = subject_mapping.get(subject)
        if mapped_subject and mapped_subject in all_templates:
            return jsonify({"templates": all_templates[mapped_subject], "subject": mapped_subject})

        # Return all available subjects
        return jsonify({
            "templates": None,
            "available_subjects": list(all_templates.keys()),
            "requested": subject
        })

    except Exception as e:
        return jsonify({"error": str(e)})


@planner_bp.route('/api/brainstorm-lesson-ideas', methods=['POST'])
def brainstorm_lesson_ideas():
    """Generate multiple lesson plan ideas/concepts for selected standards."""
    data = request.json
    selected_standards = data.get('standards', [])
    config = data.get('config', {})

    if not selected_standards:
        return jsonify({"error": "No standards selected"})

    try:
        from openai import OpenAI
        from dotenv import load_dotenv

        app_dir = Path(__file__).parent.parent.parent
        load_dotenv(app_dir / '.env', override=True)
        api_key = os.getenv("OPENAI_API_KEY")

        if not api_key or api_key.strip() == "" or "your-key-here" in api_key:
            raise Exception("Missing or placeholder API Key")

        client = OpenAI(api_key=api_key)

        # Load support documents for context
        support_docs = load_support_documents_for_planning()

        # Build available tools instruction
        available_tools = config.get('availableTools', [])
        tools_instruction = ""
        if available_tools:
            tool_names = {
                'microsoft_365': 'Microsoft 365 (Word, Excel, PowerPoint)',
                'microsoft_teams': 'Microsoft Teams',
                'google_classroom': 'Google Classroom',
                'google_slides': 'Google Slides',
                'google_docs': 'Google Docs',
                'canvas': 'Canvas LMS',
                'nearpod': 'Nearpod',
                'edpuzzle': 'Edpuzzle',
                'pear_deck': 'Pear Deck',
                'padlet': 'Padlet',
                'flipgrid': 'Flip/Flipgrid',
                'canva': 'Canva',
                'adobe_express': 'Adobe Express',
                'ixl': 'IXL',
                'desmos': 'Desmos',
                'geogebra': 'GeoGebra',
                'delta_math': 'DeltaMath',
                'fl_math_4_all': 'FL Math 4 All',
                'prodigy': 'Prodigy',
                'zearn': 'Zearn',
                'newsela': 'Newsela',
                'commonlit': 'CommonLit',
                'phet': 'PhET Simulations',
                'dbq_online': 'DBQ Online',
                'cpalms': 'CPALMS',
                'brainpop': 'BrainPOP',
                'edgenuity': 'Edgenuity',
                'everfi': 'EVERFI',
                'progress_learning': 'Progress Learning',
                'hour_of_code': 'Hour of Code',
                'kahoot': 'Kahoot',
                'quizlet': 'Quizlet',
                'blooket': 'Blooket',
                'gimkit': 'Gimkit',
                'khan_academy': 'Khan Academy',
                'youtube': 'YouTube',
            }
            # Handle both preset tools and custom tools (prefixed with "custom:")
            tool_list = []
            for t in available_tools:
                if t.startswith('custom:'):
                    tool_list.append(t[7:])  # Remove "custom:" prefix
                else:
                    tool_list.append(tool_names.get(t, t))
            tools_instruction = f"""
AVAILABLE TECHNOLOGY TOOLS (teacher has access to these):
{', '.join(tool_list)}

IMPORTANT: At least 2-3 of your ideas should incorporate these specific tools. For each technology-enhanced idea, explain exactly HOW to use the tool (e.g., "Create a Nearpod lesson with drag-and-drop activities" or "Use Kahoot for a competitive review game with 15 questions")."""
        else:
            tools_instruction = """
NO TECHNOLOGY TOOLS SELECTED: Focus entirely on non-digital activities using standard classroom materials (whiteboards, paper, manipulatives, discussions, group work)."""

        # Format standards as numbered list for clarity
        standards_text = ""
        for i, s in enumerate(selected_standards, 1):
            standards_text += f"\n{i}. {s}"

        prompt = f"""You are an expert curriculum developer brainstorming lesson plan ideas for a {config.get('grade', '7')}th grade {config.get('subject', 'Social Studies')} class.
{support_docs}

STANDARDS TO COVER (every idea MUST directly address these specific standards):
{standards_text}

IMPORTANT: Read the benchmark text, vocabulary, and learning targets above carefully. Every lesson idea must be DIRECTLY about the specific topic described in the standard(s). Do NOT generate ideas about other topics, time periods, or standards — ONLY the ones listed above.
{tools_instruction}

Generate 6 creative and diverse lesson plan ideas that would effectively teach these exact standards. Each idea should represent a DIFFERENT teaching approach.

CRITICAL REQUIREMENTS:
1. Every idea MUST directly teach the specific content described in the standards above — not related or adjacent topics
2. ALL activities must be CONCRETE and ACTIONABLE - things a teacher can actually do tomorrow
3. NEVER invent fictional apps, websites, platforms, or games (no "Math Ninja", "Number Quest", etc.)
4. For technology activities, ONLY use tools from the AVAILABLE TECHNOLOGY TOOLS list above (if any)
5. Focus on activities using standard classroom materials: whiteboards, manipulatives, worksheets, discussions, group work
6. Be SPECIFIC about what students actually do - not vague descriptions
7. For Math: use real problem types, manipulatives (fraction bars, algebra tiles), or proven strategies (number talks, think-pair-share)
8. For Science: use actual lab materials or household items for experiments
9. Avoid buzzwords without substance - every activity must have clear, executable steps

Return JSON with this structure:
{{
    "ideas": [
        {{
            "id": 1,
            "title": "Engaging, descriptive title",
            "approach": "Activity-Based|Discussion|Project|Simulation|Research|Collaborative|Technology-Enhanced|Primary Sources|Game-Based",
            "brief": "1-2 sentence description of the lesson concept",
            "hook": "The engaging opening or hook for students",
            "key_activity": "The main learning activity in 1 sentence",
            "tools_used": "Specific tools from the available list and HOW they will be used (or 'None - hands-on activity' if no tech)",
            "assessment_type": "How learning will be assessed"
        }}
    ]
}}

Make each idea distinct - vary the approaches (hands-on activities, discussions, projects, simulations, research, collaborative work, technology integration, primary source analysis, games/competitions). Be creative and specific to the content."""

        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are an expert curriculum developer. Return valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )

        content = completion.choices[0].message.content
        ideas = json.loads(content)
        usage = _extract_usage(completion, "gpt-4o")
        _record_planner_cost(usage)
        return jsonify({**ideas, "usage": usage})

    except Exception as e:
        error_msg = str(e)
        print(f"Brainstorm Error: {error_msg}")
        # Fallback mock ideas
        mock_ideas = {
            "ideas": [
                {"id": 1, "title": "Interactive Discussion", "approach": "Discussion", "brief": "Engage students in guided discussion.", "hook": "Opening question", "key_activity": "Socratic seminar", "assessment_type": "Participation rubric"},
                {"id": 2, "title": "Hands-On Activity", "approach": "Activity-Based", "brief": "Students learn through doing.", "hook": "Mystery item reveal", "key_activity": "Station rotations", "assessment_type": "Exit ticket"},
                {"id": 3, "title": "Research Project", "approach": "Research", "brief": "Students investigate topics independently.", "hook": "Essential question", "key_activity": "Guided research", "assessment_type": "Presentation"},
            ]
        }
        return jsonify({**mock_ideas, "error": error_msg, "method": "Mock"})


@planner_bp.route('/api/generate-lesson-plan', methods=['POST'])
def generate_lesson_plan():
    """Generate a lesson plan using AI."""
    data = request.json
    selected_standards = data.get('standards', [])
    config = data.get('config', {})
    selected_idea = data.get('selectedIdea')  # Optional: from brainstorming
    generate_variations = data.get('generateVariations', False)  # Generate multiple variations

    if not selected_standards:
        return jsonify({"error": "No standards selected"})

    try:
        from openai import OpenAI
        from dotenv import load_dotenv

        # Load .env from the app directory
        app_dir = Path(__file__).parent.parent.parent
        load_dotenv(app_dir / '.env', override=True)
        api_key = os.getenv("OPENAI_API_KEY")

        if not api_key or api_key.strip() == "" or "your-key-here" in api_key:
            raise Exception("Missing or placeholder API Key")

        client = OpenAI(api_key=api_key)

        period_length = config.get('periodLength', 50)
        content_type = config.get('type', 'Lesson Plan')

        # Load support documents (curriculum guides, standards)
        support_docs = load_support_documents_for_planning()

        # Build available tools instruction (same mapping as brainstorm)
        available_tools = config.get('availableTools', [])
        tools_instruction = ""
        if available_tools:
            tool_names = {
                'microsoft_365': 'Microsoft 365 (Word, Excel, PowerPoint)',
                'microsoft_teams': 'Microsoft Teams',
                'google_classroom': 'Google Classroom',
                'google_slides': 'Google Slides',
                'google_docs': 'Google Docs',
                'canvas': 'Canvas LMS',
                'nearpod': 'Nearpod',
                'edpuzzle': 'Edpuzzle',
                'pear_deck': 'Pear Deck',
                'padlet': 'Padlet',
                'flipgrid': 'Flip/Flipgrid',
                'canva': 'Canva',
                'adobe_express': 'Adobe Express',
                'ixl': 'IXL',
                'desmos': 'Desmos',
                'geogebra': 'GeoGebra',
                'delta_math': 'DeltaMath',
                'fl_math_4_all': 'FL Math 4 All',
                'prodigy': 'Prodigy',
                'zearn': 'Zearn',
                'newsela': 'Newsela',
                'commonlit': 'CommonLit',
                'phet': 'PhET Simulations',
                'dbq_online': 'DBQ Online',
                'cpalms': 'CPALMS',
                'brainpop': 'BrainPOP',
                'edgenuity': 'Edgenuity',
                'everfi': 'EVERFI',
                'progress_learning': 'Progress Learning',
                'hour_of_code': 'Hour of Code',
                'kahoot': 'Kahoot',
                'quizlet': 'Quizlet',
                'blooket': 'Blooket',
                'gimkit': 'Gimkit',
                'khan_academy': 'Khan Academy',
                'youtube': 'YouTube',
            }
            tool_list = []
            for t in available_tools:
                if t.startswith('custom:'):
                    tool_list.append(t[7:])
                else:
                    tool_list.append(tool_names.get(t, t))
            tools_instruction = f"""

AVAILABLE TECHNOLOGY TOOLS (teacher has access to these - ONLY use these for tech activities):
{', '.join(tool_list)}
"""
        else:
            tools_instruction = """

NO TECHNOLOGY TOOLS: Focus entirely on non-digital activities (whiteboards, paper, manipulatives, discussions, group work).
"""

        # Build idea-specific guidance if a brainstormed idea was selected
        idea_guidance = ""
        if selected_idea:
            idea_guidance = f"""
IMPORTANT: Base this plan on the following concept:
- Title/Theme: {selected_idea.get('title', '')}
- Teaching Approach: {selected_idea.get('approach', '')}
- Concept: {selected_idea.get('brief', '')}
- Opening Hook: {selected_idea.get('hook', '')}
- Key Activity: {selected_idea.get('key_activity', '')}
- Assessment Type: {selected_idea.get('assessment_type', '')}

Develop this specific concept into a complete, detailed lesson plan.
"""

        # Handle title - if empty, instruct AI to generate based on standards
        provided_title = config.get('title', '').strip()
        if provided_title:
            title_instruction = f'Title: "{provided_title}"'
        else:
            title_instruction = "Title: Generate a descriptive, engaging title based on the standards and content below."

        # Build content-type-specific prompt, JSON structure, and instructions
        common_header = f"""You are an expert curriculum developer creating a COMPLETE, READY-TO-USE {content_type} for a {config.get('grade', '7')}th grade {config.get('subject', 'Civics')} class.
{support_docs}
{idea_guidance}
{tools_instruction}
{title_instruction}
Standards to Cover:
{', '.join(selected_standards)}

Additional Requirements:
{config.get('requirements', 'None specified')}
"""
        teacher_notes_block = f"""
TEACHER'S ADDITIONAL INSTRUCTIONS (MUST FOLLOW):
{config.get('globalAINotes', '')}
""" if config.get('globalAINotes') else ''

        # Build section categories instruction for assignments
        assignment_section_cats = config.get('sectionCategories', {})
        assignment_sections_block = ''
        if assignment_section_cats and any(assignment_section_cats.values()):
            assignment_sections_block = '\n' + _build_section_categories_prompt(assignment_section_cats, config.get('subject', '')) + '\n'

        if content_type == 'Assignment':
            prompt = common_header + f"""
Create a complete, ready-to-use assignment that directly assesses the standards listed above.
The assignment should be appropriate for grade {config.get('grade', '7')} students.
{assignment_sections_block}
CRITICAL REQUIREMENTS:
1. THE ASSIGNMENT MUST BE 100% SELF-CONTAINED — every resource referenced (tables, charts, reading passages, data) MUST be included in the JSON
2. For Math: use REAL numbers and actual problems, not placeholders
3. Include clear, specific answer keys for every question
4. ONLY include section types that the teacher has enabled above — do NOT add vocabulary or matching sections unless explicitly enabled
5. All questions must be answerable based on the standards content

SUPPORTED QUESTION TYPES:
- multiple_choice, fill_blank, short_answer, matching, essay, true_false
- math_equation (student writes an expression/equation)
- data_table (include column_headers, row_labels, expected_data)
- coordinates (include lat/lng answer and tolerance_km)
- bar_chart, box_plot, number_line, coordinate_plane, geometry/triangle/rectangle/regular_polygon
- function_graph (student graphs functions on a coordinate plane — include x_range, y_range, correct_expressions)
- dot_plot (include categories or min_val/max_val/step, correct_dots)
- stem_and_leaf (include data array, stems, correct_leaves)
- unit_circle (include hidden_angles, hidden_values, correct_values)
- transformations (include original_vertices, transformation_type, transform_params, correct_vertices)
- fraction_model (include model_type, denominator, correct_numerator)
- probability_tree (include tree structure, correct_values)
- tape_diagram (include tapes array, correct_values)
- venn_diagram (include sets count, set_labels, correct_values)
- protractor (include given_angle or target_angle, mode: measure/draw)

GEOMETRY QUESTION TYPES (use for math/geometry standards):
- TRIANGLE: {{"question_type": "triangle", "base": 6, "height": 4, "mode": "area", "answer": "12"}}
- RECTANGLE: {{"question_type": "rectangle", "base": 8, "height": 5, "mode": "area", "answer": "40"}}
- REGULAR_POLYGON: {{"question_type": "regular_polygon", "sides": 7, "side_length": 4, "mode": "area", "answer": "58.14"}}
  Use for pentagon (5), hexagon (6), heptagon (7), octagon (8), etc. Set "mode": "decompose" to show triangle decomposition.
  NEVER use "heptagon", "pentagon", "hexagon", "octagon" etc. as question_type — always use "regular_polygon" with the "sides" field.

Return JSON with this structure:
{{
    "title": "Assignment title",
    "overview": "2-3 sentence summary of what this assignment covers",
    "instructions": "Clear student instructions",
    "time_estimate": "Estimated completion time",
    "total_points": 100,
    "sections": [
        {{
            "name": "Section name (e.g., Part A: Vocabulary)",
            "type": "multiple_choice|fill_blank|short_answer|matching|essay|true_false|math_equation|data_table",
            "points": 20,
            "questions": [
                {{
                    "number": 1,
                    "question": "The question text",
                    "question_type": "short_answer",
                    "options": ["A) ...", "B) ...", "C) ...", "D) ..."],
                    "answer": "The correct answer",
                    "points": 2
                }}
            ]
        }}
    ],
    "answer_key": {{
        "section_name": ["answer1", "answer2"]
    }},
    "rubric": {{
        "criteria": [
            {{"name": "Criterion", "points": 10, "description": "What earns full points"}}
        ]
    }}
}}
{teacher_notes_block}

STUDENT PORTAL CAPABILITIES — Questions are completed digitally. Students CAN:
- Type text answers (short_answer, essay)
- Select from multiple choice or true/false options
- Type math expressions using a virtual keyboard (math_equation)
- Fill in data table cells (data_table)
- Plot points on number lines and coordinate planes by clicking
- Interact with geometry visualizations (measure areas, perimeters, etc.)
- Graph functions on an interactive coordinate plane (function_graph)
- Drag box plot handles, fill in 5-number summaries
- Use an interactive protractor to measure or construct angles
- Fill in probability trees, Venn diagrams, tape diagrams, fraction models

VISUAL/GRAPHICAL QUESTION TYPES — the system renders these PROGRAMMATICALLY as interactive components:
- function_graph: {{"question_type": "function_graph", "x_range": [-10, 10], "y_range": [-10, 10], "correct_expressions": ["y = 2*x + 1"], "max_expressions": 2}}
- coordinate_plane: {{"question_type": "coordinate_plane", "min_val": -5, "max_val": 5, "points_to_plot": [[2, 3], [-1, 4]]}}
- number_line: {{"question_type": "number_line", "min_val": -10, "max_val": 10, "points_to_plot": [-3, 0, 5]}}
- bar_chart: {{"question_type": "bar_chart", "chart_data": {{"labels": [...], "values": [...], "title": "..."}}}}
- box_plot: {{"question_type": "box_plot", "data": [[45, 52, 58, 65, 70, 78, 85, 92]], "labels": ["Scores"]}}
- dot_plot: {{"question_type": "dot_plot", "min_val": 0, "max_val": 10, "step": 1, "correct_dots": {{"3": 2, "5": 4}}}}
- stem_and_leaf: {{"question_type": "stem_and_leaf", "data": [23, 25, 31, 34], "stems": [2, 3], "correct_leaves": {{"2": [3, 5], "3": [1, 4]}}}}
- triangle/rectangle/regular_polygon: {{"question_type": "triangle", "base": 6, "height": 4, "mode": "area"}}
- transformations: {{"question_type": "transformations", "original_vertices": [[1,1],[4,1],[4,3]], "transformation_type": "translation", "transform_params": {{"dx": 3, "dy": 2}}, "correct_vertices": [[4,3],[7,3],[7,5]]}}
- fraction_model: {{"question_type": "fraction_model", "model_type": "area", "denominator": 8, "correct_numerator": 3}}
- unit_circle: {{"question_type": "unit_circle", "hidden_angles": [30, 45, 60], "hidden_values": ["sin", "cos"], "correct_values": {{...}}}}
- probability_tree/tape_diagram/venn_diagram/protractor: see full docs in assignment-from-lesson endpoint

CRITICAL VISUAL RULES:
1. NEVER use "short_answer" for graphing, plotting, or shape questions — ALWAYS use the appropriate visual type above
2. NEVER say "View the graph" or "See the diagram" — the system RENDERS the visual from the data fields you provide
3. EVERY visual question MUST include "question_type" and ALL required data fields for that type

Make the questions SPECIFIC with real content tied to the standards. Include a variety of question types. For STEM subjects, use interactive visual components wherever appropriate."""

        elif content_type == 'Project':
            prompt = common_header + f"""
Create a complete, ready-to-use project-based learning experience for grade {config.get('grade', '7')} students.
Duration: {config.get('duration', 1)} day(s), Class Period: {period_length} minutes

CRITICAL REQUIREMENTS:
1. All phases must be CONCRETE and ACTIONABLE
2. Include specific deliverables students must produce
3. Include a detailed rubric with clear criteria
4. Specify REAL materials and resources needed
5. Be SPECIFIC about what students do at each phase

Return JSON with this structure:
{{
    "title": "Project title",
    "overview": "2-3 sentence summary",
    "essential_questions": ["Question 1", "Question 2"],
    "driving_question": "The central question students will investigate",
    "total_points": 100,
    "phases": [
        {{
            "phase": 1,
            "name": "Phase name (e.g., Research & Planning)",
            "duration": "2 days",
            "description": "What students do in this phase",
            "tasks": ["Specific task 1", "Specific task 2"],
            "deliverable": "What students submit at end of this phase",
            "teacher_checkpoints": ["What teacher checks"]
        }}
    ],
    "milestones": [
        {{"name": "Milestone name", "due": "Day X", "description": "What should be completed"}}
    ],
    "final_deliverable": {{
        "format": "Poster/Presentation/Report/etc",
        "requirements": ["Requirement 1", "Requirement 2"],
        "presentation_time": "5-7 minutes"
    }},
    "rubric": {{
        "criteria": [
            {{"name": "Criterion", "points": 25, "description": "What earns full points", "levels": {{"excellent": "...", "proficient": "...", "developing": "...", "beginning": "..."}}}}
        ]
    }},
    "materials": ["Material 1", "Material 2"],
    "resources": ["Resource 1", "Resource 2"]
}}
{teacher_notes_block}
Make the project SPECIFIC and DETAILED with real-world connections to the standards."""

        else:
            # Lesson Plan / Unit Plan — keep existing prompt
            prompt = common_header + f"""
Duration: {config.get('duration', 1)} day(s)
Class Period Length: {period_length} minutes

Create a COMPREHENSIVE, DETAILED plan that a teacher can use immediately without any additional preparation.

CRITICAL REQUIREMENTS - FOLLOW THESE EXACTLY:
1. ALL activities must be CONCRETE and ACTIONABLE - executable tomorrow with no additional prep
2. NEVER invent fictional apps, websites, platforms, or games
3. For technology activities, ONLY use tools from the AVAILABLE TECHNOLOGY TOOLS list (if provided above)
4. Focus on proven teaching strategies: think-pair-share, jigsaw, gallery walk, Socratic seminar, station rotations, number talks
5. Specify REAL materials: whiteboards, markers, index cards, graph paper, rulers, manipulatives, printed worksheets
6. For Math: include actual example problems with numbers, not placeholders
7. For Science: use real lab materials or common household items
8. Be SPECIFIC about what students physically do at each step
9. Avoid vague phrases like "interactive digital platform" or "engaging online tool"
10. Every activity description must answer: What materials? What do students do? What does the teacher do?

Return JSON with this structure:
{{
    "title": "Full descriptive title",
    "overview": "2-3 sentence summary",
    "essential_questions": ["Question 1", "Question 2"],
    "days": [
        {{
            "day": 1,
            "topic": "Specific topic",
            "objective": "Students will be able to...",
            "standards_addressed": ["Standards covered"],
            "vocabulary": [{{"term": "word", "definition": "definition"}}],
            "timing": [
                {{"minutes": "0-5", "duration": "5 min", "activity": "Bell Ringer", "description": "Details"}}
            ],
            "bell_ringer": {{
                "prompt": "Question or task",
                "expected_responses": ["Possible answers"],
                "discussion_points": ["Follow-up questions"]
            }},
            "direct_instruction": {{
                "key_points": ["Main concepts"],
                "examples": ["Examples to share"],
                "check_for_understanding": ["Questions to ask"]
            }},
            "activity": {{
                "name": "Activity name",
                "description": "Step-by-step instructions",
                "grouping": "Individual/Pairs/Groups",
                "student_tasks": ["Step 1", "Step 2"],
                "teacher_role": "What teacher does",
                "differentiation": {{
                    "struggling": "Support strategies",
                    "advanced": "Extension activities"
                }}
            }},
            "assessment": {{
                "type": "Formative/Summative",
                "description": "How learning is assessed",
                "criteria": ["What demonstrates mastery"],
                "exit_ticket": "Exit ticket question"
            }},
            "materials": ["Item 1", "Item 2"],
            "homework": "Assignment or null",
            "teacher_notes": "Tips and notes"
        }}
    ],
    "unit_assessment": {{
        "type": "Test/Project/etc",
        "description": "Description",
        "components": ["What it includes"],
        "rubric_criteria": ["Grading criteria"]
    }},
    "resources": ["Resource 1", "Resource 2"]
}}
{teacher_notes_block}
Make the content SPECIFIC and DETAILED with real examples and facts."""

        # If generating variations, create 3 different versions
        if generate_variations:
            variations = []

            if content_type == 'Assignment':
                approaches = [
                    ("Multiple Choice & Short Answer", "Focus on recall and comprehension with multiple choice, true/false, fill-in-the-blank, and short answer questions."),
                    ("Application & Analysis", "Focus on applying concepts to new scenarios, data analysis, and problem-solving questions."),
                    ("Extended Response & Essay", "Focus on open-ended questions, essay prompts, and critical thinking responses.")
                ]
            elif content_type == 'Project':
                approaches = [
                    ("Individual Research", "Student works independently on research, analysis, and presentation of findings."),
                    ("Group Collaboration", "Students work in teams with defined roles and shared deliverables."),
                    ("Creative Expression", "Students demonstrate learning through creative media — poster, video, infographic, etc.")
                ]
            else:
                approaches = [
                    ("Activity-Based", "Focus on hands-on activities, station rotations, and interactive learning experiences."),
                    ("Discussion & Analysis", "Focus on Socratic questioning, primary source analysis, and class discussions."),
                    ("Project-Based", "Focus on student-created projects, research, and presentations.")
                ]

            total_usage = {"model": "gpt-4o", "input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "cost": 0}
            for approach_name, approach_desc in approaches:
                variation_prompt = prompt + f"\n\nIMPORTANT: Use a {approach_name} approach. {approach_desc}"

                completion = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": "You are an expert curriculum developer. Return valid JSON only."},
                        {"role": "user", "content": variation_prompt}
                    ],
                    response_format={"type": "json_object"}
                )

                u = _extract_usage(completion, "gpt-4o")
                if u:
                    for k in ["input_tokens", "output_tokens", "total_tokens", "cost"]:
                        total_usage[k] += u[k]

                content = completion.choices[0].message.content
                plan = json.loads(content)
                _auto_upgrade_visual_types(plan)
                _ensure_geometry_defaults(plan)
                _ensure_data_table_defaults(plan)
                _hydrate_math_visuals(plan)
                plan['approach'] = approach_name
                variations.append(plan)

            total_usage["cost"] = round(total_usage["cost"], 6)
            total_usage["cost_display"] = f"${total_usage['cost']:.4f}"
            _record_planner_cost(total_usage)
            return jsonify({"variations": variations, "method": "AI", "usage": total_usage})

        # Single plan generation
        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are an expert curriculum developer. Return valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )

        content = completion.choices[0].message.content
        plan = json.loads(content)
        _auto_upgrade_visual_types(plan)
        _ensure_geometry_defaults(plan)
        _ensure_data_table_defaults(plan)
        _hydrate_math_visuals(plan)
        usage = _extract_usage(completion, "gpt-4o")
        _record_planner_cost(usage)
        return jsonify({"plan": plan, "method": "AI", "usage": usage})

    except Exception as e:
        error_msg = str(e)
        print(f"OpenAI API Error: {error_msg}. Falling back to Mock Mode.")

        # Fallback Mock Plan
        content_type = config.get('type', 'Unit Plan')

        mock_plan = {
            "title": f"{config.get('title', 'Unit Plan')} ({content_type} - Mock)",
            "overview": f"GENERATED IN MOCK MODE. Error: {error_msg}",
            "days": [],
            "unit_assessment": "Mock Assessment"
        }

        if content_type == 'Assignment':
            mock_plan['days'] = [{
                "day": 1,
                "topic": "Assignment: Core Concepts",
                "objective": "Students will demonstrate understanding.",
                "vocabulary": ["Key Term 1", "Key Term 2"],
                "bell_ringer": "Review instructions.",
                "activity": "Complete the assignment.",
                "assessment": "Graded submission.",
                "materials": ["Worksheet", "Resources"]
            }]
        else:
            mock_plan['days'] = [
                {
                    "day": i + 1,
                    "topic": f"Mock Topic {i + 1}",
                    "objective": "Students will understand key concepts.",
                    "vocabulary": ["Term 1", "Term 2"],
                    "bell_ringer": "Prompt on board.",
                    "activity": "Group activity.",
                    "assessment": "Exit Ticket.",
                    "materials": ["Textbook", "Worksheet"]
                } for i in range(int(config.get('duration', 5)))
            ]

        return jsonify({"plan": mock_plan, "method": "Mock", "error": error_msg})


@planner_bp.route('/api/generate-assignment-from-lesson', methods=['POST'])
def generate_assignment_from_lesson():
    """Generate an assignment based on an existing lesson plan."""
    data = request.json
    lesson_plan = data.get('lessonPlan', {})
    config = data.get('config', {})
    assignment_type = data.get('assignmentType', 'worksheet')  # worksheet, quiz, project, homework

    if not lesson_plan:
        return jsonify({"error": "No lesson plan provided"})

    try:
        from openai import OpenAI
        from dotenv import load_dotenv

        app_dir = Path(__file__).parent.parent.parent
        load_dotenv(app_dir / '.env', override=True)
        api_key = os.getenv("OPENAI_API_KEY")

        if not api_key or api_key.strip() == "" or "your-key-here" in api_key:
            raise Exception("Missing or placeholder API Key")

        client = OpenAI(api_key=api_key)

        # Extract lesson details for context
        lesson_title = lesson_plan.get('title', 'Untitled Lesson')
        lesson_overview = lesson_plan.get('overview', '')
        essential_questions = lesson_plan.get('essential_questions', [])
        days = lesson_plan.get('days', [])

        # Gather vocabulary, objectives, and key content from all days
        all_vocabulary = []
        all_objectives = []
        all_key_points = []

        for day in days:
            vocab = day.get('vocabulary', [])
            for v in vocab:
                if isinstance(v, dict):
                    all_vocabulary.append(f"{v.get('term', '')}: {v.get('definition', '')}")
                else:
                    all_vocabulary.append(str(v))

            if day.get('objective'):
                all_objectives.append(day['objective'])

            di = day.get('direct_instruction', {})
            if isinstance(di, dict) and di.get('key_points'):
                all_key_points.extend(di['key_points'])

        # Assignment type templates
        subject = config.get('subject', '').lower()
        is_stem = any(s in subject for s in ['math', 'algebra', 'geometry', 'calculus', 'science', 'physics', 'chemistry', 'biology'])

        type_instructions = {
            'worksheet': "Create a practice worksheet with a MIX of question types: multiple choice, short answer, fill-in-the-blank, and matching questions. For STEM subjects, also include math_equation questions where students solve equations or write expressions.",
            'quiz': "Create a quiz with multiple choice, true/false, short answer, and (for STEM subjects) math_equation questions. Follow state assessment format: multiple choice should make up 40-50% of questions.",
            'project': "Create a creative project assignment with clear requirements, rubric, and deliverables.",
            'homework': "Create a homework assignment that reinforces the lesson content with a mix of multiple choice, short answer, and practice problems.",
            'essay': "Create an essay prompt with a clear thesis question, requirements, and grading criteria.",
            'lab': "Create a lab activity or investigation with hypothesis, procedure, data collection (use data_table questions for recording data), and analysis questions."
        }

        type_instruction = type_instructions.get(assignment_type, type_instructions['worksheet'])

        if is_stem:
            type_instruction += " IMPORTANT: For Math/Science subjects, align with Florida FAST assessment format. Include multiple_choice questions (4 answer choices, one correct) and short_answer questions. For math, use math_equation type for solving/simplifying. If the lesson involves data or measurements, include data_table questions with actual numeric values. EVERY table referenced in a question MUST use question_type 'data_table' with column_headers, row_labels, and expected_data — NEVER put table data as raw text inside the question string."

        # Apply section category constraints from the UI
        section_categories = config.get('sectionCategories', {})
        if section_categories and any(section_categories.values()):
            section_prompt = _build_section_categories_prompt(section_categories, config.get('subject', ''))
            type_instruction += "\n\n" + section_prompt

        # Build available tools instruction
        available_tools = config.get('availableTools', [])
        tools_instruction = ""
        if available_tools:
            tool_names = {
                'microsoft_365': 'Microsoft 365 (Word, Excel, PowerPoint)',
                'microsoft_teams': 'Microsoft Teams',
                'google_classroom': 'Google Classroom',
                'google_slides': 'Google Slides',
                'google_docs': 'Google Docs',
                'canvas': 'Canvas LMS',
                'nearpod': 'Nearpod',
                'edpuzzle': 'Edpuzzle',
                'pear_deck': 'Pear Deck',
                'padlet': 'Padlet',
                'flipgrid': 'Flip/Flipgrid',
                'canva': 'Canva',
                'adobe_express': 'Adobe Express',
                'ixl': 'IXL',
                'desmos': 'Desmos',
                'geogebra': 'GeoGebra',
                'delta_math': 'DeltaMath',
                'fl_math_4_all': 'FL Math 4 All',
                'prodigy': 'Prodigy',
                'zearn': 'Zearn',
                'newsela': 'Newsela',
                'commonlit': 'CommonLit',
                'phet': 'PhET Simulations',
                'dbq_online': 'DBQ Online',
                'cpalms': 'CPALMS',
                'brainpop': 'BrainPOP',
                'edgenuity': 'Edgenuity',
                'everfi': 'EVERFI',
                'progress_learning': 'Progress Learning',
                'hour_of_code': 'Hour of Code',
                'kahoot': 'Kahoot',
                'quizlet': 'Quizlet',
                'blooket': 'Blooket',
                'gimkit': 'Gimkit',
                'khan_academy': 'Khan Academy',
                'youtube': 'YouTube',
            }
            tool_list = []
            for t in available_tools:
                if t.startswith('custom:'):
                    tool_list.append(t[7:])
                else:
                    tool_list.append(tool_names.get(t, t))
            tools_instruction = f"""
AVAILABLE TECHNOLOGY TOOLS (student has access to these):
{', '.join(tool_list)}

CRITICAL: When an assignment requires digital creation (infographics, presentations, videos, graphs, etc.):
- ALWAYS specify which tool from the list above to use (e.g., "Using Canva, create an infographic...")
- Include the specific tool name in the question text
- If multiple tools could work, pick the most appropriate one and name it explicitly
"""
        else:
            tools_instruction = """
NO TECHNOLOGY TOOLS SPECIFIED: Focus on paper-based or physical deliverables only.
"""

        prompt = f"""You are an expert teacher creating an assessment/assignment based on a lesson plan.
{tools_instruction}
LESSON PLAN DETAILS:
Title: {lesson_title}
Overview: {lesson_overview}

Essential Questions:
{chr(10).join(f'- {q}' for q in essential_questions) if essential_questions else 'None specified'}

Learning Objectives:
{chr(10).join(f'- {obj}' for obj in all_objectives) if all_objectives else 'None specified'}

Key Content Points:
{chr(10).join(f'- {kp}' for kp in all_key_points[:10]) if all_key_points else 'None specified'}

Vocabulary:
{chr(10).join(f'- {v}' for v in all_vocabulary[:15]) if all_vocabulary else 'None specified'}

ASSIGNMENT TYPE: {assignment_type.title()}
{type_instruction}

Create a complete, ready-to-use assignment that:
1. Directly assesses the lesson objectives
2. Uses the vocabulary and key concepts from the lesson
3. Aligns with the essential questions
4. Is appropriate for grade {config.get('grade', '7')} students

CRITICAL REQUIREMENTS:
- THE ASSIGNMENT MUST BE 100% SELF-CONTAINED. Every resource referenced in the instructions (tables, charts, data sets, reading passages, maps, diagrams, timelines, primary sources) MUST be fully included in the assignment JSON. NEVER tell students to "complete the data table" or "analyze the chart" without providing the actual table data or chart data in the question object. If a question references a table, include "expected_data" with headers and pre-filled data. If it references a reading passage, include the full passage text in the question field.
- For data_table questions: ALWAYS include "column_headers" (array of header strings), "row_labels" (array of row labels), and "expected_data" (2D array of correct values). The student sees the headers and row labels and fills in the values.
- CRITICAL: NEVER put table data as plain text or markdown pipes (| x | y |) inside the "question" string. If a question involves a table, use question_type "data_table" with structured data fields. Tables rendered as text are unreadable.
- For Math: Use REAL numbers and actual problems (e.g., "Solve: 3/4 + 1/2 = ?"), not placeholders
- All questions must be answerable based on the lesson content
- Include clear, specific answer keys
- Word problems should use realistic scenarios (shopping, cooking, sports) not fictional games or apps
- Avoid vague or overly complex language for the grade level
- NEVER use vague instructions like "analyze the data" without providing the data inline

STUDENT PORTAL CAPABILITIES — Questions are completed digitally. Students CAN:
- Type text answers (short_answer, essay)
- Select from multiple choice or true/false options
- Type math expressions using a virtual keyboard (math_equation)
- Fill in data table cells (data_table)
- Plot points on number lines and coordinate planes by clicking
- Interact with geometry visualizations (measure areas, perimeters, etc.)
- Drag box plot handles, fill in 5-number summaries
- Use an interactive protractor to measure or construct angles
- Fill in probability trees, Venn diagrams, tape diagrams, fraction models

Students CANNOT:
- Draw, sketch, or create freehand diagrams directly in the portal
- Physically construct anything — no compass, ruler, or protractor drawing

Students CAN upload images:
- Students can upload photos of handwritten work (paper-and-pencil drawings, constructions, etc.)
- Use this when no interactive component fits the task

PREFERRED: Use interactive components whenever possible. Only fall back to "upload a photo" for tasks that genuinely require freehand drawing.

Rephrase examples:
- "Draw supplementary angles" → "If one angle is 130°, what is the supplementary angle? Explain." (short_answer or math_equation)
- "Sketch the graph of y=2x+1" → Use type "function_graph" or "coordinate_plane" with points to plot
- "Draw a triangle" → Use type "geometry" or "triangle" with given dimensions
- "Construct an angle of 45°" → Use type "protractor" with mode "construct" and target_angle 45
- "Draw and label a diagram of the cell cycle" → "Describe the stages of the cell cycle. You may upload a photo of your diagram." (short_answer with allow_image_upload: true)

SPECIAL STEM QUESTION TYPES (use when appropriate):

1. MATH EQUATIONS (type: "math_equation"):
   - Student writes a mathematical expression/equation as their answer
   - System can check symbolic equivalence (2x+4 equals 4+2x)
   - Use for: solving equations, simplifying expressions, writing formulas
   - Include "answer" as the correct expression (e.g., "x = 5" or "3/4")

2. DATA TABLES (type: "data_table"):
   - Student fills in a table with numerical data that THEY compute or provide
   - System grades with tolerance (±5% for measurements)
   - Use for: science labs, statistics, recording observations, completing function tables
   - ONLY use when the student needs to FILL IN missing values. Do NOT use data_table for questions where data is already given and the student must analyze, plot, or interpret it — those should be "short_answer", "coordinate_plane", or "multiple_choice"
   - MUST include "column_headers" (e.g., ["x", "y"]), "row_labels" (e.g., ["1", "2", "3"]), and "expected_data" (2D array of correct cell values)
   - The table structure MUST be fully defined — never tell students to "complete a table" without providing the table

3. COORDINATES (type: "coordinates"):
   - Student provides geographic coordinates (latitude, longitude)
   - System grades based on distance (within X km is correct)
   - Use for: geography, map skills, location identification
   - Include "answer" as {{"lat": 25.7617, "lng": -80.1918}} and "tolerance_km" (default 50)

VISUAL/GRAPHICAL QUESTION TYPES (include actual data for rendering — the system renders these PROGRAMMATICALLY):

4. BAR CHART (type: "bar_chart"):
   - Display a bar graph and ask interpretation questions
   - MUST include "chart_data" with labels and values
   - Example: {{"question_type": "bar_chart", "chart_data": {{"labels": ["Mon", "Tue", "Wed", "Thu", "Fri"], "values": [12, 19, 8, 15, 22], "title": "Daily Sales", "y_label": "Number Sold"}}}}

5. BOX PLOT (type: "box_plot"):
   - Student identifies min, Q1, median, Q3, max, range, IQR
   - MUST include "data" array with the dataset
   - Example: {{"question_type": "box_plot", "data": [[45, 52, 58, 60, 65, 70, 72, 78, 85, 92]], "labels": ["Class Scores"]}}

6. NUMBER LINE (type: "number_line"):
   - Student plots points on a number line
   - Include "min_val", "max_val", and "points_to_plot"
   - Example: {{"question_type": "number_line", "min_val": -10, "max_val": 10, "points_to_plot": [-3, 0, 5]}}

7. COORDINATE PLANE (type: "coordinate_plane"):
   - Student plots points on an x-y grid (4 quadrants)
   - Include "min_val", "max_val", and "points_to_plot" as [x, y] pairs
   - Example: {{"question_type": "coordinate_plane", "min_val": -5, "max_val": 5, "points_to_plot": [[2, 3], [-1, 4], [0, -2]]}}

8. GEOMETRY (type: "triangle", "rectangle", or "regular_polygon"):
   - Student calculates area of shapes with given dimensions
   - Include "base", "height", and "question_type" (triangle or rectangle)
   - Example: {{"question_type": "triangle", "base": 6, "height": 4, "mode": "area", "answer": "12"}}
   - REGULAR_POLYGON: {{"question_type": "regular_polygon", "sides": 7, "side_length": 4, "mode": "area", "answer": "58.14"}}
     Use for pentagon (5), hexagon (6), heptagon (7), octagon (8), etc. Set "mode": "decompose" to show triangle decomposition.
     NEVER use "heptagon", "pentagon", "hexagon", "octagon" etc. as question_type — always use "regular_polygon" with the "sides" field.

9. FUNCTION GRAPH (type: "function_graph") — CRITICAL FOR ALGEBRA/GRAPHING:
   - Student graphs functions on an interactive coordinate plane
   - MUST include "x_range", "y_range" as [min, max], and "correct_expressions" as an array of equation strings
   - Use for: graphing linear equations, systems of equations, quadratic/polynomial functions, slope/intercept
   - Example: {{"question_type": "function_graph", "x_range": [-10, 10], "y_range": [-10, 10], "correct_expressions": ["y = 2*x + 1", "y = -x + 3"], "max_expressions": 2, "answer": "The lines intersect at (0.67, 2.33)"}}
   - EVERY question about graphing lines, functions, or systems MUST use this type — NEVER use "short_answer" for graphing questions

10. DOT PLOT (type: "dot_plot"):
    - Student places dots on categories or a number line
    - Include "categories" (string array) or "min_val"/"max_val"/"step" for numeric, and "correct_dots"
    - Example: {{"question_type": "dot_plot", "min_val": 0, "max_val": 10, "step": 1, "correct_dots": {{"3": 2, "5": 4, "7": 1}}, "chart_title": "Quiz Scores"}}

11. STEM AND LEAF (type: "stem_and_leaf"):
    - Student organizes data into stems and leaves
    - Include "data" (number array), "stems" (array of stem values), "correct_leaves"
    - Example: {{"question_type": "stem_and_leaf", "data": [23, 25, 31, 34, 37, 42, 45], "stems": [2, 3, 4], "correct_leaves": {{"2": [3, 5], "3": [1, 4, 7], "4": [2, 5]}}, "chart_title": "Test Scores"}}

12. UNIT CIRCLE (type: "unit_circle"):
    - Student fills in missing angles or trig values on the unit circle
    - Include "hidden_angles" (angles to blank out), "hidden_values" (which values to hide), "correct_values"
    - Example: {{"question_type": "unit_circle", "hidden_angles": [30, 45, 60], "hidden_values": ["sin", "cos"], "correct_values": {{"30": {{"sin": "1/2", "cos": "√3/2"}}}}, "show_radians": true}}

13. TRANSFORMATIONS (type: "transformations"):
    - Student applies geometric transformations (translation, reflection, rotation, dilation)
    - Include "original_vertices", "transformation_type", "transform_params", "correct_vertices"
    - Example: {{"question_type": "transformations", "original_vertices": [[1,1],[4,1],[4,3]], "transformation_type": "translation", "transform_params": {{"dx": 3, "dy": 2}}, "correct_vertices": [[4,3],[7,3],[7,5]], "grid_range": [-8, 8], "mode": "plot"}}

14. FRACTION MODEL (type: "fraction_model"):
    - Student shades parts of a visual fraction model
    - Include "model_type" (area/bar/number_line), "denominator", "correct_numerator"
    - Example: {{"question_type": "fraction_model", "model_type": "area", "denominator": 8, "correct_numerator": 3, "answer": "3/8"}}

15. PROBABILITY TREE (type: "probability_tree"):
    - Student fills in probabilities on a tree diagram
    - Include "tree" structure with branches and "correct_values"
    - Example: {{"question_type": "probability_tree", "tree": {{"label": "Start", "branches": [{{"label": "Heads", "probability": "1/2", "branches": [{{"label": "Heads", "probability": "1/2"}}, {{"label": "Tails", "probability": "1/2"}}]}}, {{"label": "Tails", "probability": "1/2"}}]}}, "correct_values": {{"P(HH)": "1/4"}}}}

16. TAPE DIAGRAM (type: "tape_diagram"):
    - Student works with tape/bar model diagrams for ratios and proportions
    - Include "tapes" array with labels and segments, "correct_values"
    - Example: {{"question_type": "tape_diagram", "tapes": [{{"label": "Boys", "segments": 3, "value_per_segment": null}}, {{"label": "Girls", "segments": 5, "value_per_segment": null}}], "correct_values": {{"total": 40, "boys": 15, "girls": 25}}, "chart_title": "Ratio of Boys to Girls"}}

17. VENN DIAGRAM (type: "venn_diagram"):
    - Student fills in regions of a Venn diagram
    - Include "sets" (2 or 3), "set_labels", "correct_values"
    - Example: {{"question_type": "venn_diagram", "sets": 2, "set_labels": ["Even Numbers", "Multiples of 3"], "correct_values": {{"only_a": 4, "only_b": 3, "intersection": 2, "outside": 1}}, "mode": "count"}}

18. PROTRACTOR (type: "protractor"):
    - Student measures or constructs angles using a protractor visual
    - Include "given_angle" or "target_angle", "mode" (measure/draw)
    - Example: {{"question_type": "protractor", "given_angle": 45, "mode": "measure", "answer": "45", "show_classification": true}}

CRITICAL RULES FOR VISUAL QUESTIONS (MUST FOLLOW):

1. USE THESE VISUAL TYPES — they render as interactive components in the student portal:
   bar_chart, box_plot, number_line, coordinate_plane, function_graph,
   triangle, rectangle, regular_polygon, dot_plot, stem_and_leaf, unit_circle,
   transformations, fraction_model, probability_tree, tape_diagram, venn_diagram, protractor

2. NEVER use "short_answer" for a question about graphing, plotting, or visualizing — ALWAYS use the appropriate visual type above.
   - Graphing equations → function_graph
   - Plotting points → coordinate_plane
   - Plotting on a number line → number_line
   - Geometric shapes → triangle/rectangle/regular_polygon
   - Data display → bar_chart/box_plot/dot_plot/stem_and_leaf

3. NEVER mention or reference:
   - "See attached graph" or "View the graph" — the system RENDERS the graph from data you provide
   - "Look at the diagram below" without providing the data fields
   - Any visual that doesn't have its data fields in the question JSON object

4. EVERY visual question MUST include:
   - "question_type": one of the supported types above
   - ALL required data fields for that type (see examples above)
   - The data fields ARE the visual — the system draws the graph/chart/shape from them

5. If you want to ask about data interpretation without a visual:
   - Describe the data in words within the question text
   - Use "short_answer" type
   - Example: "A store sold 12 apples on Monday, 19 on Tuesday, and 8 on Wednesday. Which day had the most sales?"

Return JSON with this structure:
{{
    "title": "Assignment title",
    "type": "{assignment_type}",
    "instructions": "Clear student instructions",
    "time_estimate": "Estimated completion time",
    "total_points": 100,
    "sections": [
        {{
            "name": "Section name (e.g., Part A: Vocabulary)",
            "type": "multiple_choice|fill_blank|short_answer|matching|essay|true_false|math_equation|data_table|coordinates",
            "points": 20,
            "questions": [
                {{
                    "number": 1,
                    "question": "The question text",
                    "question_type": "short_answer",  // or "math_equation", "data_table", "coordinates"
                    "options": ["A) ...", "B) ...", "C) ...", "D) ..."],  // for multiple choice
                    "answer": "The correct answer",  // for most types
                    "expected_data": [[1, 2], [3, 4]],  // for data_table type
                    "tolerance": 0.05,  // for data_table (optional, default 5%)
                    "tolerance_km": 50,  // for coordinates (optional, default 50km)
                    "points": 2
                }}
            ]
        }}
    ],
    "answer_key": {{
        "section_name": ["answer1", "answer2", ...]
    }},
    "rubric": {{
        "criteria": [
            {{"name": "Criterion", "points": 10, "description": "What earns full points"}}
        ]
    }}
}}

SUBJECT-SPECIFIC GUIDANCE:
- For MATH subjects: Include at least one "math_equation" section where students solve and write expressions
- For SCIENCE subjects: Include a "data_table" section for lab data, measurements, or observations
- For GEOGRAPHY subjects: Include a "coordinates" section for map/location questions
{f'''
TEACHER'S ADDITIONAL INSTRUCTIONS (MUST FOLLOW):
{config.get('globalAINotes', '')}
''' if config.get('globalAINotes') else ''}
Make the questions specific to the lesson content. Include a variety of question types appropriate for the assignment type."""

        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are an expert teacher. Return valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )

        content = completion.choices[0].message.content
        assignment = json.loads(content)
        _auto_upgrade_visual_types(assignment)
        _ensure_geometry_defaults(assignment)
        _ensure_data_table_defaults(assignment)
        _hydrate_math_visuals(assignment)
        # Embed context for portal grading (so AI grading has full 18-factor access)
        assignment['grade_level'] = config.get('grade', config.get('grade_level', '7'))
        assignment['subject'] = config.get('subject', 'General')
        usage = _extract_usage(completion, "gpt-4o")
        _record_planner_cost(usage)
        return jsonify({"assignment": assignment, "method": "AI", "usage": usage})

    except Exception as e:
        error_msg = str(e)
        print(f"Assignment Generation Error: {error_msg}")

        # Fallback mock assignment
        mock_assignment = {
            "title": f"{assignment_type.title()} - {lesson_plan.get('title', 'Lesson')}",
            "type": assignment_type,
            "instructions": "Complete all sections. Show your work.",
            "time_estimate": "30-45 minutes",
            "total_points": 100,
            "sections": [
                {
                    "name": "Part A: Key Concepts",
                    "type": "short_answer",
                    "points": 50,
                    "questions": [
                        {"number": 1, "question": "Explain the main concept from the lesson.", "points": 25},
                        {"number": 2, "question": "Give an example that demonstrates your understanding.", "points": 25}
                    ]
                },
                {
                    "name": "Part B: Vocabulary",
                    "type": "matching",
                    "points": 50,
                    "questions": [
                        {"number": 1, "question": "Match terms to definitions", "points": 50}
                    ]
                }
            ],
            "error": error_msg,
            "method": "Mock"
        }
        return jsonify({"assignment": mock_assignment, "method": "Mock", "error": error_msg})


@planner_bp.route('/api/export-lesson-plan', methods=['POST'])
def export_lesson_plan():
    """Export the lesson plan to a Word document."""
    data = request.json
    plan = data.get('plan', data)

    try:
        from docx import Document
        from docx.shared import Pt, Inches
        from docx.enum.text import WD_ALIGN_PARAGRAPH

        doc = Document()

        # Helper functions
        def format_vocab(vocab_list):
            if not vocab_list:
                return ""
            items = []
            for v in vocab_list:
                if isinstance(v, dict):
                    term = v.get('term', '')
                    defn = v.get('definition', '')
                    items.append(f"{term}: {defn}" if defn else term)
                else:
                    items.append(str(v))
            return '\n'.join(items)

        def format_bell_ringer(br):
            if not br:
                return ""
            if isinstance(br, str):
                return br
            prompt = br.get('prompt', '')
            responses = br.get('expected_responses', [])
            result = prompt
            if responses:
                result += "\n\nExpected Responses:\n" + '\n'.join(f"- {r}" for r in responses)
            return result

        def format_activity(act):
            if not act:
                return ""
            if isinstance(act, str):
                return act
            parts = []
            if act.get('name'):
                parts.append(f"Activity: {act['name']}")
            if act.get('description'):
                parts.append(act['description'])
            if act.get('grouping'):
                parts.append(f"Grouping: {act['grouping']}")
            if act.get('student_tasks'):
                parts.append("\nStudent Tasks:")
                for i, t in enumerate(act['student_tasks'], 1):
                    parts.append(f"  {i}. {t}")
            if act.get('differentiation'):
                diff = act['differentiation']
                if diff.get('struggling'):
                    parts.append(f"\nSupport for Struggling: {diff['struggling']}")
                if diff.get('advanced'):
                    parts.append(f"Extension for Advanced: {diff['advanced']}")
            return '\n'.join(parts)

        def format_assessment(asmt):
            if not asmt:
                return ""
            if isinstance(asmt, str):
                return asmt
            parts = []
            if asmt.get('type'):
                parts.append(f"Type: {asmt['type']}")
            if asmt.get('description'):
                parts.append(asmt['description'])
            if asmt.get('exit_ticket'):
                parts.append(f"\nExit Ticket: \"{asmt['exit_ticket']}\"")
            return '\n'.join(parts)

        # Title
        title = doc.add_heading(plan.get('title', 'Lesson Plan'), 0)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER

        # Overview
        if plan.get('overview'):
            doc.add_heading('Overview', level=1)
            doc.add_paragraph(plan['overview'])

        # Essential Questions
        if plan.get('essential_questions'):
            doc.add_heading('Essential Questions', level=1)
            for q in plan['essential_questions']:
                doc.add_paragraph(f"* {q}")

        # Daily Plans
        if plan.get('days'):
            doc.add_heading('Daily Lesson Plans', level=1)

            for day in plan['days']:
                doc.add_heading(f"Day {day.get('day')}: {day.get('topic')}", level=2)

                if day.get('objective'):
                    p = doc.add_paragraph()
                    p.add_run('Learning Objective: ').bold = True
                    p.add_run(day['objective'])

                if day.get('standards_addressed'):
                    p = doc.add_paragraph()
                    p.add_run('Standards: ').bold = True
                    p.add_run(', '.join(day['standards_addressed']))

                if day.get('timing'):
                    doc.add_heading('Lesson Timing', level=3)
                    for t in day['timing']:
                        time_str = t.get('minutes') or t.get('duration', '')
                        doc.add_paragraph(f"{time_str} - {t.get('activity', '')}: {t.get('description', '')}")

                vocab_text = format_vocab(day.get('vocabulary'))
                if vocab_text:
                    doc.add_heading('Vocabulary', level=3)
                    doc.add_paragraph(vocab_text)

                br_text = format_bell_ringer(day.get('bell_ringer'))
                if br_text:
                    doc.add_heading('Bell Ringer', level=3)
                    doc.add_paragraph(br_text)

                if day.get('direct_instruction'):
                    di = day['direct_instruction']
                    doc.add_heading('Direct Instruction', level=3)
                    if di.get('key_points'):
                        doc.add_paragraph('Key Points:')
                        for kp in di['key_points']:
                            doc.add_paragraph(f"* {kp}")
                    if di.get('check_for_understanding'):
                        doc.add_paragraph('\nCheck for Understanding:')
                        for q in di['check_for_understanding']:
                            doc.add_paragraph(f"* \"{q}\"")

                act_text = format_activity(day.get('activity'))
                if act_text:
                    doc.add_heading('Main Activity', level=3)
                    doc.add_paragraph(act_text)

                asmt_text = format_assessment(day.get('assessment'))
                if asmt_text:
                    doc.add_heading('Assessment', level=3)
                    doc.add_paragraph(asmt_text)

                if day.get('materials'):
                    doc.add_heading('Materials', level=3)
                    doc.add_paragraph(', '.join(day['materials']))

                if day.get('homework'):
                    doc.add_heading('Homework', level=3)
                    doc.add_paragraph(day['homework'])

                if day.get('teacher_notes'):
                    doc.add_heading('Teacher Notes', level=3)
                    doc.add_paragraph(day['teacher_notes'])

                doc.add_paragraph()

        # Unit Assessment
        if plan.get('unit_assessment'):
            doc.add_heading('Summative Assessment', level=1)
            ua = plan['unit_assessment']
            if isinstance(ua, dict):
                if ua.get('type'):
                    doc.add_paragraph(f"Type: {ua['type']}")
                if ua.get('description'):
                    doc.add_paragraph(ua['description'])
                if ua.get('components'):
                    doc.add_paragraph('\nComponents:')
                    for c in ua['components']:
                        doc.add_paragraph(f"* {c}")
            else:
                doc.add_paragraph(str(ua))

        # Resources
        if plan.get('resources'):
            doc.add_heading('Resources', level=1)
            for r in plan['resources']:
                doc.add_paragraph(f"* {r}")

        # Save file
        filename = f"Lesson_Plan_{int(time.time())}.docx"
        output_folder = os.path.expanduser("~/Downloads/Graider")
        os.makedirs(output_folder, exist_ok=True)
        filepath = os.path.join(output_folder, filename)
        doc.save(filepath)

        # Open the file
        subprocess.run(['open', filepath])

        return jsonify({"status": "success", "path": filepath})

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error exporting plan: {e}")
        return jsonify({"error": str(e)})


@planner_bp.route('/api/export-generated-assignment', methods=['POST'])
def export_generated_assignment():
    """Export a generated assignment to PDF format with visual elements."""
    data = request.json
    assignment = data.get('assignment', {})
    format_type = data.get('format', 'pdf')  # Default to PDF now
    include_answers = data.get('include_answers', False)

    title = assignment.get('title', 'Assignment')
    instructions = assignment.get('instructions', '')
    sections = assignment.get('sections', [])
    total_points = assignment.get('total_points', 100)
    time_estimate = assignment.get('time_estimate', '')

    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.units import inch
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
        from reportlab.lib.colors import black, gray, lightgrey, red, green
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Image,
            Table, TableStyle, PageBreak, KeepTogether
        )
        import io

        # Set up styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle', parent=styles['Heading1'],
            alignment=TA_CENTER, fontSize=18, spaceAfter=6
        )
        heading_style = ParagraphStyle(
            'CustomHeading', parent=styles['Heading2'],
            fontSize=14, spaceAfter=6, spaceBefore=12
        )
        normal_style = styles['Normal']
        bold_style = ParagraphStyle(
            'Bold', parent=styles['Normal'],
            fontName='Helvetica-Bold'
        )
        center_style = ParagraphStyle(
            'Center', parent=styles['Normal'],
            alignment=TA_CENTER
        )
        answer_style = ParagraphStyle(
            'Answer', parent=styles['Normal'],
            fontName='Helvetica-Bold', textColor=green
        )

        # Build the PDF
        safe_title = "".join(c for c in title if c.isalnum() or c in ' -_').strip()
        suffix = "_ANSWER_KEY" if include_answers else "_Student"
        filename = f"{safe_title}{suffix}.pdf"
        output_folder = os.path.expanduser("~/Downloads/Graider/Assignments")
        os.makedirs(output_folder, exist_ok=True)
        filepath = os.path.join(output_folder, filename)

        doc = SimpleDocTemplate(
            filepath, pagesize=letter,
            topMargin=0.5*inch, bottomMargin=0.5*inch,
            leftMargin=0.75*inch, rightMargin=0.75*inch
        )

        story = []

        # Title
        story.append(Paragraph(title, title_style))
        story.append(Spacer(1, 0.1*inch))

        # Name/Date/Period or Answer Key header
        if include_answers:
            story.append(Paragraph(
                "<b>ANSWER KEY - FOR TEACHER USE ONLY</b>",
                center_style
            ))
        else:
            story.append(Paragraph(
                "Name: _______________________  Date: _______________  Period: _____",
                center_style
            ))

        # Meta info
        if time_estimate or total_points:
            meta_text = []
            if time_estimate:
                meta_text.append(f"Time: {time_estimate}")
            if total_points:
                meta_text.append(f"Total Points: {total_points}")
            story.append(Paragraph("    ".join(meta_text), center_style))

        story.append(Spacer(1, 0.15*inch))

        # Instructions
        if instructions:
            story.append(Paragraph(f"<b>Instructions:</b> {instructions}", normal_style))
            story.append(Spacer(1, 0.15*inch))

        question_num = 1

        # Process sections
        for section in sections:
            section_name = section.get('name', 'Section')
            section_points = section.get('points', 0)
            section_type = section.get('type', 'short_answer')
            questions = section.get('questions', [])

            # Section header
            pts_text = f" ({section_points} points)" if section_points else ""
            story.append(Paragraph(f"<b>{section_name}</b>{pts_text}", heading_style))

            for q in questions:
                q_number = q.get('number', question_num)
                q_text = q.get('question', '')
                q_points = q.get('points', 0)
                q_options = q.get('options', [])
                q_answer = q.get('answer', '')
                q_type = q.get('question_type', section_type)
                q_visual = q.get('visual_type', None)  # number_line, coordinate_plane, etc.

                # Question text
                pts_text = f" ({q_points} pts)" if q_points else ""
                story.append(Paragraph(
                    f"<b>Question {q_number}:</b> {q_text}{pts_text}",
                    normal_style
                ))
                story.append(Spacer(1, 0.05*inch))

                # Multiple choice options
                if q_options:
                    for opt in q_options:
                        story.append(Paragraph(f"&nbsp;&nbsp;&nbsp;&nbsp;{opt}", normal_style))

                # Add visual elements based on question type
                if q_visual or q_type in ['number_line', 'coordinate_plane', 'graph',
                                          'geometry', 'triangle', 'rectangle', 'regular_polygon',
                                          'circle', 'trapezoid', 'parallelogram',
                                          'rectangular_prism', 'cylinder',
                                          'pythagorean', 'trig', 'angles', 'similarity',
                                          'box_plot', 'bar_chart', 'function_graph',
                                          'dot_plot', 'stem_and_leaf', 'unit_circle',
                                          'transformations', 'fraction_model',
                                          'probability_tree', 'tape_diagram',
                                          'venn_diagram', 'protractor', 'angle_protractor',
                                          'histogram', 'pie_chart']:
                    visual_image = _create_visual_for_question(q, include_answers)
                    if visual_image:
                        story.append(Spacer(1, 0.1*inch))
                        story.append(visual_image)
                        story.append(Spacer(1, 0.1*inch))

                # Answer section
                if include_answers:
                    # Show answer
                    if q_type == 'coordinates' and isinstance(q_answer, dict):
                        ans_text = f"ANSWER: Lat: {q_answer.get('lat', 0)}, Lng: {q_answer.get('lng', 0)}"
                    else:
                        ans_text = f"ANSWER: {q_answer}"
                    story.append(Paragraph(f"<b>{ans_text}</b>", answer_style))

                    if q_type == 'math_equation':
                        story.append(Paragraph("<i>(Equivalent forms accepted)</i>", normal_style))
                    elif q_type == 'coordinates':
                        tolerance_km = q.get('tolerance_km', 50)
                        story.append(Paragraph(f"<i>(Acceptable within {tolerance_km} km)</i>", normal_style))
                else:
                    # Answer space for students
                    if q_type == 'math_equation':
                        story.append(Paragraph("Show your work:", normal_style))
                        for _ in range(3):
                            story.append(Paragraph("_" * 85, normal_style))
                        story.append(Paragraph("<b>Final Answer:</b> " + "_" * 50, normal_style))
                    elif q_type == 'coordinates':
                        story.append(Paragraph(
                            "<b>Latitude:</b> _______________°  <b>Longitude:</b> _______________°",
                            normal_style
                        ))
                    elif q_type == 'data_table':
                        # Create empty table — handle both normalized and raw AI field names
                        headers = q.get('headers', q.get('column_headers', ['Column 1', 'Column 2', 'Column 3']))
                        row_labels = q.get('row_labels', [])
                        expected = q.get('expected_data', [])
                        num_rows = q.get('num_rows', len(expected) if expected else 5)
                        if row_labels:
                            table_data = [[''] + headers]
                            for ri in range(num_rows):
                                label = row_labels[ri] if ri < len(row_labels) else ''
                                table_data.append([label] + [''] * len(headers))
                        else:
                            table_data = [headers] + [[''] * len(headers) for _ in range(num_rows)]
                        col_count = len(table_data[0])
                        t = Table(table_data, colWidths=[1.5*inch] * col_count)
                        t.setStyle(TableStyle([
                            ('GRID', (0, 0), (-1, -1), 1, black),
                            ('BACKGROUND', (0, 0), (-1, 0), lightgrey),
                            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                            ('FONTSIZE', (0, 0), (-1, -1), 10),
                            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
                            ('TOPPADDING', (0, 0), (-1, -1), 12),
                        ]))
                        story.append(t)
                    elif section_type in ['essay', 'extended_response']:
                        for _ in range(8):
                            story.append(Paragraph("_" * 85, normal_style))
                    elif section_type == 'short_answer':
                        for _ in range(3):
                            story.append(Paragraph("_" * 85, normal_style))
                    elif section_type in ['multiple_choice', 'true_false']:
                        story.append(Paragraph("<b>Answer:</b> _____", normal_style))
                    else:
                        for _ in range(2):
                            story.append(Paragraph("_" * 85, normal_style))

                story.append(Spacer(1, 0.15*inch))
                question_num += 1

        # Rubric for teacher version
        if include_answers and assignment.get('rubric', {}).get('criteria'):
            story.append(PageBreak())
            story.append(Paragraph("<b>Grading Rubric</b>", heading_style))
            for criterion in assignment['rubric']['criteria']:
                story.append(Paragraph(
                    f"<b>{criterion.get('name', 'Criterion')}:</b> "
                    f"{criterion.get('points', 0)} points - {criterion.get('description', '')}",
                    normal_style
                ))
                story.append(Spacer(1, 0.05*inch))

        # Build PDF
        doc.build(story)

        # Open the file
        subprocess.run(['open', filepath])

        return jsonify({"status": "success", "path": filepath})

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error exporting assignment: {e}")
        return jsonify({"error": str(e)})


def _create_visual_for_question(question: dict, show_answer: bool = False):
    """Create a visual element (graph, number line, etc.) for a question.

    Returns a ReportLab Image with both width and height set to preserve aspect ratio.
    Supports all geometry types: triangle, rectangle, circle, trapezoid, parallelogram,
    regular_polygon, rectangular_prism, cylinder.
    """
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import numpy as np
        import math as _math
        from reportlab.lib.units import inch
        from reportlab.platypus import Image
        import io

        q_type = question.get('question_type', question.get('visual_type', ''))
        fig = None

        if q_type == 'number_line':
            fig, ax = plt.subplots(figsize=(7, 1.5))
            min_val = question.get('min_val', -10)
            max_val = question.get('max_val', 10)

            ax.axhline(y=0, color='black', linewidth=2)
            ax.set_xlim(min_val - 0.5, max_val + 0.5)
            ax.set_ylim(-0.5, 0.5)

            for i in range(int(min_val), int(max_val) + 1):
                ax.plot([i, i], [-0.1, 0.1], 'k-', linewidth=1.5)
                ax.text(i, -0.25, str(i), ha='center', fontsize=10)

            ax.annotate('', xy=(max_val + 0.3, 0), xytext=(max_val, 0),
                       arrowprops=dict(arrowstyle='->', color='black', lw=2))
            ax.annotate('', xy=(min_val - 0.3, 0), xytext=(min_val, 0),
                       arrowprops=dict(arrowstyle='->', color='black', lw=2))

            if show_answer and question.get('points_to_plot'):
                for pt in question['points_to_plot']:
                    ax.plot(pt, 0, 'ro', markersize=10)
            ax.axis('off')

        elif q_type == 'coordinate_plane':
            fig, ax = plt.subplots(figsize=(4.5, 4.5))
            x_range = question.get('x_range', (-6, 6))
            y_range = question.get('y_range', (-6, 6))

            ax.axhline(y=0, color='black', linewidth=1.5)
            ax.axvline(x=0, color='black', linewidth=1.5)
            ax.grid(True, linestyle='--', alpha=0.5)
            ax.set_xlim(x_range[0] - 0.5, x_range[1] + 0.5)
            ax.set_ylim(y_range[0] - 0.5, y_range[1] + 0.5)
            ax.set_xticks(range(x_range[0], x_range[1] + 1))
            ax.set_yticks(range(y_range[0], y_range[1] + 1))

            offset = (x_range[1] - x_range[0]) * 0.35
            ax.text(offset, offset, 'I', fontsize=14, color='gray', alpha=0.5)
            ax.text(-offset, offset, 'II', fontsize=14, color='gray', alpha=0.5)
            ax.text(-offset, -offset, 'III', fontsize=14, color='gray', alpha=0.5)
            ax.text(offset, -offset, 'IV', fontsize=14, color='gray', alpha=0.5)

            ax.set_xlabel('x')
            ax.set_ylabel('y')
            ax.set_aspect('equal')

            if show_answer and question.get('points_to_plot'):
                labels = question.get('point_labels', [])
                for i, pt in enumerate(question['points_to_plot']):
                    ax.plot(pt[0], pt[1], 'ro', markersize=10)
                    label = labels[i] if i < len(labels) else f"({pt[0]}, {pt[1]})"
                    ax.annotate(label, xy=pt, xytext=(5, 5), textcoords='offset points', fontsize=10)

        elif q_type in ('geometry', 'triangle', 'pythagorean', 'trig', 'angles', 'similarity'):
            fig, ax = plt.subplots(figsize=(4, 3))
            base = question.get('base', 6)
            height = question.get('height', 4)

            vertices = [(0, 0), (base, 0), (base/2, height)]
            triangle = plt.Polygon(vertices, fill=True, facecolor='lightblue',
                                  edgecolor='black', linewidth=2)
            ax.add_patch(triangle)
            ax.plot([base/2, base/2], [0, height], 'r--', linewidth=1.5)
            ax.text(base/2, -0.4, f'b = {base}', ha='center', fontsize=11)
            ax.text(base/2 + 0.3, height/2, f'h = {height}', ha='left', fontsize=11)
            ax.set_xlim(-1, base + 1)
            ax.set_ylim(-1, height + 1)
            ax.set_aspect('equal')
            ax.axis('off')

        elif q_type == 'rectangle':
            fig, ax = plt.subplots(figsize=(4, 3))
            base = question.get('base', question.get('width', 6))
            height = question.get('height', 4)

            rect = plt.Rectangle((0, 0), base, height, fill=True,
                                facecolor='#bbf7d0', edgecolor='#22c55e', linewidth=2)
            ax.add_patch(rect)
            ax.text(base / 2, -0.4, f'w = {base}', ha='center', fontsize=11)
            ax.text(base + 0.3, height / 2, f'h = {height}', ha='left', fontsize=11)
            ax.set_xlim(-1, base + 1.5)
            ax.set_ylim(-1, height + 1)
            ax.set_aspect('equal')
            ax.axis('off')

        elif q_type == 'circle':
            fig, ax = plt.subplots(figsize=(3.5, 3.5))
            radius = question.get('radius', 5)
            circle_patch = plt.Circle((0, 0), radius, fill=True,
                                      facecolor='#dbeafe', edgecolor='#2563eb', linewidth=2)
            ax.add_patch(circle_patch)
            ax.plot(0, 0, 'ko', markersize=4)
            ax.plot([0, radius], [0, 0], 'r-', linewidth=1.5)
            ax.text(radius / 2, radius * 0.08, f'r = {radius}', ha='center', fontsize=11, color='red')
            margin = radius * 0.3
            ax.set_xlim(-radius - margin, radius + margin)
            ax.set_ylim(-radius - margin, radius + margin)
            ax.set_aspect('equal')
            ax.axis('off')

        elif q_type == 'trapezoid':
            fig, ax = plt.subplots(figsize=(4, 3))
            top_base = question.get('top_base', 4)
            base = question.get('base', 8)
            height = question.get('height', 5)
            offset_x = (base - top_base) / 2
            vertices = [(offset_x, height), (offset_x + top_base, height), (base, 0), (0, 0)]
            trap = plt.Polygon(vertices, fill=True, facecolor='#e9d5ff', edgecolor='#a855f7', linewidth=2)
            ax.add_patch(trap)
            ax.text((offset_x + offset_x + top_base) / 2, height + 0.3, f'a = {top_base}', ha='center', fontsize=11, color='#a855f7')
            ax.text(base / 2, -0.4, f'b = {base}', ha='center', fontsize=11, color='#a855f7')
            ax.plot([base / 2, base / 2], [0, height], 'r--', linewidth=1.5)
            ax.text(base / 2 + 0.3, height / 2, f'h = {height}', ha='left', fontsize=11, color='red')
            ax.set_xlim(-1, base + 1)
            ax.set_ylim(-1, height + 1.5)
            ax.set_aspect('equal')
            ax.axis('off')

        elif q_type == 'parallelogram':
            fig, ax = plt.subplots(figsize=(4, 3))
            base = question.get('base', 7)
            height = question.get('height', 4)
            slant = 1.5
            vertices = [(slant, height), (base + slant, height), (base, 0), (0, 0)]
            para = plt.Polygon(vertices, fill=True, facecolor='#fbcfe8', edgecolor='#ec4899', linewidth=2)
            ax.add_patch(para)
            ax.text(base / 2, -0.4, f'b = {base}', ha='center', fontsize=11, color='#ec4899')
            ax.plot([slant, slant], [0, height], 'r--', linewidth=1.5)
            ax.text(slant + 0.3, height / 2, f'h = {height}', ha='left', fontsize=11, color='red')
            ax.set_xlim(-1, base + slant + 1)
            ax.set_ylim(-1, height + 1)
            ax.set_aspect('equal')
            ax.axis('off')

        elif q_type == 'regular_polygon':
            fig, ax = plt.subplots(figsize=(3.5, 3.5))
            n = max(3, min(12, question.get('sides', 6)))
            side_length = question.get('side_length', 4)
            R = 2.5
            vertices = []
            for i in range(n):
                angle = (2 * _math.pi * i) / n - _math.pi / 2
                vertices.append((R * _math.cos(angle), R * _math.sin(angle)))
            vertices.append(vertices[0])
            xs, ys = zip(*vertices)
            ax.fill(xs, ys, facecolor='#dbeafe', edgecolor='#3b82f6', linewidth=2)
            mid_x = (vertices[0][0] + vertices[1][0]) / 2
            mid_y = (vertices[0][1] + vertices[1][1]) / 2
            ax.plot([0, mid_x], [0, mid_y], 'r--', linewidth=1.5)
            ax.text(mid_x, mid_y - 0.4, f's = {side_length}', ha='center', fontsize=11, color='#3b82f6')
            ax.text(0, 0.2, f'n = {n}', ha='center', fontsize=10, color='gray')
            ax.set_xlim(-3.5, 3.5)
            ax.set_ylim(-3.5, 3.5)
            ax.set_aspect('equal')
            ax.axis('off')

        elif q_type == 'rectangular_prism':
            fig, ax = plt.subplots(figsize=(4, 3.5))
            l = question.get('base', 5)
            w = question.get('width', 3)
            h = question.get('height', 4)
            # Front face
            ax.add_patch(plt.Rectangle((0, 0), l, h, fill=True, facecolor='#bfdbfe', edgecolor='#3b82f6', linewidth=2))
            # Top face
            top_verts = [(0, h), (w * 0.5, h + w * 0.4), (l + w * 0.5, h + w * 0.4), (l, h)]
            ax.add_patch(plt.Polygon(top_verts, fill=True, facecolor='#93c5fd', edgecolor='#3b82f6', linewidth=2))
            # Right face
            right_verts = [(l, 0), (l + w * 0.5, w * 0.4), (l + w * 0.5, h + w * 0.4), (l, h)]
            ax.add_patch(plt.Polygon(right_verts, fill=True, facecolor='#60a5fa', edgecolor='#3b82f6', linewidth=2))
            ax.text(l / 2, -0.5, f'l = {l}', ha='center', fontsize=10)
            ax.text(-0.5, h / 2, f'h = {h}', ha='right', fontsize=10)
            ax.text(l + w * 0.3, h + w * 0.25, f'w = {w}', fontsize=10, color='#1d4ed8')
            ax.set_xlim(-1, l + w * 0.5 + 1)
            ax.set_ylim(-1, h + w * 0.4 + 1)
            ax.set_aspect('equal')
            ax.axis('off')

        elif q_type == 'cylinder':
            fig, ax = plt.subplots(figsize=(3.5, 4))
            radius = question.get('radius', 3)
            h = question.get('height', 7)
            from matplotlib.patches import Ellipse
            # Body
            ax.add_patch(plt.Rectangle((-radius, 0), 2 * radius, h, facecolor='#bbf7d0', edgecolor='none'))
            ax.plot([-radius, -radius], [0, h], color='#22c55e', linewidth=2)
            ax.plot([radius, radius], [0, h], color='#22c55e', linewidth=2)
            # Bottom ellipse
            ax.add_patch(Ellipse((0, 0), 2 * radius, radius * 0.6, facecolor='#86efac', edgecolor='#22c55e', linewidth=2))
            # Top ellipse
            ax.add_patch(Ellipse((0, h), 2 * radius, radius * 0.6, facecolor='#bbf7d0', edgecolor='#22c55e', linewidth=2))
            # Radius line
            ax.plot([0, radius], [h, h], 'r-', linewidth=2)
            ax.plot(0, h, 'ro', markersize=4)
            ax.text(radius / 2, h + radius * 0.2, f'r = {radius}', ha='center', fontsize=10, color='red')
            ax.text(radius + 0.3, h / 2, f'h = {h}', ha='left', fontsize=10, color='#1d4ed8')
            margin = radius * 0.5
            ax.set_xlim(-radius - margin, radius + margin + 1)
            ax.set_ylim(-radius * 0.3 - 0.5, h + radius * 0.3 + 0.5)
            ax.set_aspect('equal')
            ax.axis('off')

        elif q_type == 'box_plot':
            fig, ax = plt.subplots(figsize=(6, 2.5))
            data = question.get('data', [[50, 60, 70, 75, 80, 85, 90]])
            labels = question.get('data_labels', [f'Set {i+1}' for i in range(len(data))])
            bp = ax.boxplot(data, patch_artist=True, labels=labels)
            colors = plt.cm.Pastel1(np.linspace(0, 1, len(data)))
            for patch, color in zip(bp['boxes'], colors):
                patch.set_facecolor(color)
            ax.set_ylabel('Value')
            ax.grid(True, axis='y', linestyle='--', alpha=0.5)

        elif q_type == 'bar_chart':
            fig, ax = plt.subplots(figsize=(5, 3))
            categories = question.get('categories', ['A', 'B', 'C', 'D'])
            chart_data = question.get('chart_data', {})
            values = chart_data.get('values', question.get('values', [0, 0, 0, 0]))
            if not show_answer:
                values = [0] * len(categories)
            ax.bar(categories, values, color='steelblue', edgecolor='black')
            ax.set_ylabel(chart_data.get('y_label', question.get('y_label', 'Value')))
            ax.grid(True, axis='y', linestyle='--', alpha=0.5)

        elif q_type == 'function_graph':
            fig, ax = plt.subplots(figsize=(4.5, 3.5))
            x_range = question.get('x_range', (-10, 10))
            y_range = question.get('y_range', (-10, 10))
            ax.axhline(y=0, color='black', linewidth=0.8)
            ax.axvline(x=0, color='black', linewidth=0.8)
            ax.grid(True, linestyle='--', alpha=0.4)
            ax.set_xlim(x_range)
            ax.set_ylim(y_range)
            ax.set_xlabel('x')
            ax.set_ylabel('y')

            if show_answer and question.get('correct_expressions'):
                from sympy import sympify, lambdify, Symbol
                x_sym = Symbol('x')
                x_vals = np.linspace(x_range[0], x_range[1], 300)
                colors = ['#2563eb', '#dc2626', '#16a34a', '#9333ea']
                for idx, expr_str in enumerate(question['correct_expressions']):
                    try:
                        clean = expr_str.strip().replace('^', '**')
                        if clean.lower().startswith('y'):
                            clean = clean.split('=', 1)[-1].strip()
                        sym_expr = sympify(clean)
                        f = lambdify(x_sym, sym_expr, modules=['numpy'])
                        y_vals = f(x_vals)
                        if not hasattr(y_vals, '__len__'):
                            y_vals = np.full_like(x_vals, float(y_vals))
                        ax.plot(x_vals, y_vals, color=colors[idx % len(colors)], linewidth=2)
                    except Exception:
                        continue

        elif q_type == 'dot_plot':
            categories = question.get('categories', [])
            correct_dots = question.get('correct_dots', {})
            min_val = question.get('min_val', 0)
            max_val = question.get('max_val', 10)
            step = question.get('step', 1)
            items = categories if categories else [str(min_val + i * step) for i in range(int((max_val - min_val) / step) + 1)]
            fig, ax = plt.subplots(figsize=(6, 2.5))
            ax.axhline(y=0, color='black', linewidth=1.5)
            for idx, item in enumerate(items):
                ax.text(idx, -0.3, str(item), ha='center', fontsize=9)
                ax.plot([idx, idx], [-0.05, 0.05], 'k-', linewidth=1)
                if show_answer and correct_dots:
                    count = int(correct_dots.get(str(item), 0))
                    for d in range(count):
                        ax.plot(idx, 0.3 + d * 0.35, 'o', color='#6366f1', markersize=8)
            ax.set_xlim(-0.5, len(items) - 0.5)
            max_count = max(int(v) for v in correct_dots.values()) if correct_dots else 3
            ax.set_ylim(-0.7, 0.3 + max_count * 0.35 + 0.5)
            ax.axis('off')

        elif q_type == 'stem_and_leaf':
            data = question.get('data', [])
            correct_leaves = question.get('correct_leaves', {})
            fig, ax = plt.subplots(figsize=(4, 3))
            if data:
                stems = sorted(set(v // 10 for v in data))
                rows = []
                for s in stems:
                    leaves = sorted(v % 10 for v in data if v // 10 == s)
                    rows.append(f"  {s} | {' '.join(str(l) for l in leaves)}")
                text = "Stem | Leaf\n" + "-" * 20 + "\n" + "\n".join(rows)
                if show_answer:
                    ax.text(0.1, 0.5, text, transform=ax.transAxes, fontsize=12, fontfamily='monospace', va='center')
                else:
                    blank_rows = [f"  {s} |" for s in stems]
                    blank_text = "Stem | Leaf\n" + "-" * 20 + "\n" + "\n".join(blank_rows)
                    ax.text(0.1, 0.5, blank_text, transform=ax.transAxes, fontsize=12, fontfamily='monospace', va='center')
            ax.axis('off')

        elif q_type == 'unit_circle':
            fig, ax = plt.subplots(figsize=(5, 5))
            circle = plt.Circle((0, 0), 1, fill=False, color='#6366f1', linewidth=2)
            ax.add_patch(circle)
            ax.axhline(y=0, color='black', linewidth=1)
            ax.axvline(x=0, color='black', linewidth=1)
            key_degs = [0, 30, 45, 60, 90, 120, 135, 150, 180, 210, 225, 240, 270, 300, 315, 330]
            for d in key_degs:
                rad = _math.radians(d)
                px, py = _math.cos(rad), _math.sin(rad)
                ax.plot(px, py, 'o', color='#6366f1', markersize=4)
                ax.plot([0, px], [0, py], '--', color='rgba(99,102,241,0.2)', linewidth=0.5)
                if show_answer:
                    ax.annotate(f'{d}\u00b0', xy=(px, py), xytext=(px * 1.15, py * 1.15), fontsize=7, ha='center')
            ax.set_xlim(-1.4, 1.4)
            ax.set_ylim(-1.4, 1.4)
            ax.set_aspect('equal')
            ax.grid(True, linestyle='--', alpha=0.2)
            ax.set_title('Unit Circle', fontsize=12)

        elif q_type == 'transformations':
            fig, ax = plt.subplots(figsize=(5, 5))
            grid_range = question.get('grid_range', [-8, 8])
            ax.axhline(y=0, color='black', linewidth=1)
            ax.axvline(x=0, color='black', linewidth=1)
            ax.grid(True, linestyle='--', alpha=0.3)
            ax.set_xlim(grid_range[0] - 0.5, grid_range[1] + 0.5)
            ax.set_ylim(grid_range[0] - 0.5, grid_range[1] + 0.5)
            ax.set_aspect('equal')
            # Draw original shape
            orig = question.get('original_vertices', [[1, 1], [4, 1], [4, 3]])
            if orig:
                xs = [v[0] for v in orig] + [orig[0][0]]
                ys = [v[1] for v in orig] + [orig[0][1]]
                ax.fill(xs, ys, alpha=0.3, color='#6366f1')
                ax.plot(xs, ys, '-', color='#6366f1', linewidth=2)
                for i, (x, y) in enumerate(orig):
                    ax.annotate(chr(65 + i), (x, y), xytext=(5, 5), textcoords='offset points', fontsize=10, fontweight='bold', color='#6366f1')
            # Draw correct if showing answers
            if show_answer:
                correct_v = question.get('correct_vertices', [])
                if correct_v:
                    xs = [v[0] for v in correct_v] + [correct_v[0][0]]
                    ys = [v[1] for v in correct_v] + [correct_v[0][1]]
                    ax.fill(xs, ys, alpha=0.2, color='#ec4899')
                    ax.plot(xs, ys, '-', color='#ec4899', linewidth=2)

        elif q_type == 'fraction_model':
            denom = question.get('denominator', 4)
            model_type = question.get('model_type', 'area')
            correct_num = question.get('correct_numerator', 0)
            fig, ax = plt.subplots(figsize=(4, 2.5))
            if model_type == 'circle':
                for i in range(denom):
                    start = i * 360 / denom
                    end = (i + 1) * 360 / denom
                    from matplotlib.patches import Wedge
                    filled = show_answer and i < correct_num
                    color = '#6366f1' if filled else 'white'
                    wedge = Wedge((0, 0), 1, start - 90, end - 90, facecolor=color, edgecolor='black', linewidth=1.5, alpha=0.4 if filled else 1)
                    ax.add_patch(wedge)
                ax.set_xlim(-1.3, 1.3)
                ax.set_ylim(-1.3, 1.3)
            else:  # area/strip
                cell_w = 4 / denom
                for i in range(denom):
                    filled = show_answer and i < correct_num
                    color = '#6366f1' if filled else 'white'
                    ax.add_patch(plt.Rectangle((i * cell_w, 0), cell_w, 1.5, facecolor=color, edgecolor='black', linewidth=1.5, alpha=0.4 if filled else 1))
                ax.set_xlim(-0.3, 4.3)
                ax.set_ylim(-0.5, 2.2)
            ax.set_aspect('equal')
            ax.axis('off')
            if show_answer:
                ax.set_title(f'{correct_num}/{denom}', fontsize=14, color='#6366f1', fontweight='bold')

        elif q_type == 'probability_tree':
            fig, ax = plt.subplots(figsize=(6, 4))
            tree = question.get('tree', {})
            def draw_tree(node, x, y, dx, level=0):
                branches = node.get('branches', [])
                n = len(branches)
                if n == 0:
                    return
                dy_step = 2.0 / (2 ** level) if level < 3 else 0.5
                for i, branch in enumerate(branches):
                    offset = (i - (n - 1) / 2) * dy_step
                    nx, ny = x + dx, y + offset
                    ax.annotate('', xy=(nx, ny), xytext=(x, y),
                               arrowprops=dict(arrowstyle='->', color='#6366f1', lw=1.5))
                    prob_text = branch.get('probability', '')
                    if not branch.get('hidden', False) or show_answer:
                        ax.text((x + nx) / 2, (y + ny) / 2 + 0.15, prob_text, ha='center', fontsize=9, color='#f59e0b')
                    ax.text(nx + 0.05, ny, branch.get('label', ''), fontsize=10, fontweight='bold',
                           bbox=dict(boxstyle='round,pad=0.2', facecolor='#e0e7ff', edgecolor='#6366f1'))
                    draw_tree(branch, nx, ny, dx * 0.8, level + 1)
            if tree:
                ax.text(0.5, 0, tree.get('label', 'Start'), fontsize=11, fontweight='bold',
                       bbox=dict(boxstyle='round,pad=0.3', facecolor='#6366f1', edgecolor='none', alpha=0.8),
                       color='white', ha='center')
                draw_tree(tree, 0.5, 0, 2.0)
            ax.set_xlim(-0.5, 7)
            ax.set_ylim(-3, 3)
            ax.axis('off')

        elif q_type == 'tape_diagram':
            tapes = question.get('tapes', [])
            fig, ax = plt.subplots(figsize=(6, 1.5 + len(tapes) * 1.2))
            y_pos = 0
            max_total = max((t.get('total', sum(s.get('value', 1) for s in t.get('segments', []))) for t in tapes), default=10)
            for tape in tapes:
                label = tape.get('label', '')
                segments = tape.get('segments', [])
                total = tape.get('total', sum(s.get('value', 1) for s in segments))
                bar_width = 5 * (total / max_total)
                ax.text(-0.3, y_pos + 0.3, label, ha='right', fontsize=10, fontweight='600')
                x_pos = 0
                for seg in segments:
                    seg_w = bar_width * (seg.get('value', 1) / total)
                    color = seg.get('color', '#6366f1')
                    ax.add_patch(plt.Rectangle((x_pos, y_pos), seg_w, 0.6, facecolor=color, edgecolor='black', linewidth=1, alpha=0.3))
                    if show_answer or not seg.get('hidden', False):
                        ax.text(x_pos + seg_w / 2, y_pos + 0.3, str(seg.get('value', '')), ha='center', fontsize=10, fontweight='bold')
                    else:
                        ax.text(x_pos + seg_w / 2, y_pos + 0.3, '?', ha='center', fontsize=10, fontweight='bold', color='red')
                    x_pos += seg_w
                ax.text(x_pos + 0.2, y_pos + 0.3, f'= {total}' if not tape.get('totalHidden') or show_answer else '= ?', fontsize=10)
                y_pos -= 1.2
            ax.set_xlim(-1.5, 7)
            ax.set_ylim(y_pos - 0.5, 1)
            ax.axis('off')

        elif q_type == 'venn_diagram':
            fig, ax = plt.subplots(figsize=(5, 4))
            sets = question.get('sets', 2)
            labels = question.get('set_labels', ['Set A', 'Set B', 'Set C'])
            from matplotlib.patches import Circle as MplCircle
            if sets >= 3:
                circles = [
                    MplCircle((-0.5, 0.3), 1.2, alpha=0.15, color='#6366f1', linewidth=2),
                    MplCircle((0.5, 0.3), 1.2, alpha=0.15, color='#ec4899', linewidth=2),
                    MplCircle((0, -0.5), 1.2, alpha=0.15, color='#10b981', linewidth=2),
                ]
                label_pos = [(-1.2, 1.2), (1.2, 1.2), (0, -1.8)]
            else:
                circles = [
                    MplCircle((-0.5, 0), 1.2, alpha=0.15, color='#6366f1', linewidth=2),
                    MplCircle((0.5, 0), 1.2, alpha=0.15, color='#ec4899', linewidth=2),
                ]
                label_pos = [(-1.2, 1.2), (1.2, 1.2)]
            for i, c in enumerate(circles):
                ax.add_patch(c)
                c_edge = MplCircle(c.center, c.radius, fill=False, edgecolor=c.get_facecolor(), linewidth=2)
                ax.add_patch(c_edge)
                if i < len(labels):
                    ax.text(label_pos[i][0], label_pos[i][1], labels[i], ha='center', fontsize=11, fontweight='bold')
            # Show region values if answers visible
            if show_answer:
                regions = question.get('correct_values', question.get('regions', {}))
                if sets == 2:
                    pos_map = {'only_a': (-1, 0), 'a_and_b': (0, 0), 'only_b': (1, 0)}
                else:
                    pos_map = {'only_a': (-1, 0.4), 'only_b': (1, 0.4), 'only_c': (0, -1),
                              'a_and_b': (0, 0.4), 'a_and_c': (-0.5, -0.3), 'b_and_c': (0.5, -0.3), 'all': (0, 0)}
                for key, pos in pos_map.items():
                    val = regions.get(key, '')
                    if val:
                        ax.text(pos[0], pos[1], str(val), ha='center', fontsize=12, fontweight='bold')
            ax.set_xlim(-2.5, 2.5)
            ax.set_ylim(-2.5, 2.5)
            ax.set_aspect('equal')
            ax.axis('off')

        elif q_type in ['protractor', 'angle_protractor']:
            fig, ax = plt.subplots(figsize=(4, 3))
            given_angle = question.get('given_angle', 45)
            from matplotlib.patches import Arc, FancyArrowPatch
            # Draw protractor arc
            arc = Arc((0, 0), 3, 3, angle=0, theta1=0, theta2=180, color='#6366f1', linewidth=2)
            ax.add_patch(arc)
            # Tick marks
            for d in range(0, 181, 10):
                rad = _math.radians(d)
                r1, r2 = 1.4, 1.55
                ax.plot([r1 * _math.cos(rad), r2 * _math.cos(rad)], [r1 * _math.sin(rad), r2 * _math.sin(rad)], 'k-', linewidth=0.8)
                if d % 30 == 0:
                    ax.text(1.25 * _math.cos(rad), 1.25 * _math.sin(rad), f'{d}\u00b0', ha='center', fontsize=7)
            # Base ray
            ax.plot([0, 1.6], [0, 0], 'k-', linewidth=2)
            # Angle ray
            angle_rad = _math.radians(given_angle)
            ax.plot([0, 1.6 * _math.cos(angle_rad)], [0, 1.6 * _math.sin(angle_rad)], '-', color='#ec4899', linewidth=2.5)
            # Angle arc
            angle_arc = Arc((0, 0), 0.8, 0.8, angle=0, theta1=0, theta2=given_angle, color='#ec4899', linewidth=2)
            ax.add_patch(angle_arc)
            if show_answer:
                mid_rad = _math.radians(given_angle / 2)
                ax.text(0.5 * _math.cos(mid_rad), 0.5 * _math.sin(mid_rad), f'{given_angle}\u00b0', ha='center', fontsize=11, color='#ec4899', fontweight='bold')
            else:
                mid_rad = _math.radians(given_angle / 2)
                ax.text(0.5 * _math.cos(mid_rad), 0.5 * _math.sin(mid_rad), '?', ha='center', fontsize=14, color='#ec4899', fontweight='bold')
            ax.set_xlim(-1.8, 1.8)
            ax.set_ylim(-0.3, 1.8)
            ax.set_aspect('equal')
            ax.axis('off')

        elif q_type == 'histogram':
            fig, ax = plt.subplots(figsize=(5, 3))
            data = question.get('data', [])
            bins = question.get('bins', 10)
            if data:
                ax.hist(data, bins=bins, color='steelblue', edgecolor='black')
            ax.set_ylabel('Frequency')
            ax.grid(True, axis='y', linestyle='--', alpha=0.5)

        elif q_type == 'pie_chart':
            fig, ax = plt.subplots(figsize=(4, 4))
            chart_data = question.get('chart_data', {})
            categories = chart_data.get('categories', question.get('categories', ['A', 'B', 'C']))
            values = chart_data.get('values', question.get('values', [1, 1, 1]))
            colors = ['#6366f1', '#ec4899', '#10b981', '#f59e0b', '#3b82f6', '#ef4444']
            ax.pie(values, labels=categories, autopct='%1.0f%%', colors=colors[:len(values)])

        else:
            return None

        if fig is None:
            return None

        # Save figure and calculate proper dimensions for PDF
        plt.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='white')
        buf.seek(0)

        # Get the figure's aspect ratio to calculate proper height
        fig_w, fig_h = fig.get_size_inches()
        aspect_ratio = fig_h / fig_w
        plt.close(fig)

        # Determine target width based on type, capped to page width (7 inches usable)
        if q_type in ['coordinate_plane', 'unit_circle', 'transformations']:
            target_width = 3.5 * inch
        elif q_type in ['number_line', 'dot_plot']:
            target_width = 5.5 * inch
        elif q_type in ['box_plot', 'bar_chart', 'function_graph', 'probability_tree',
                         'tape_diagram', 'histogram', 'venn_diagram']:
            target_width = 4.5 * inch
        elif q_type in ['circle', 'regular_polygon', 'cylinder', 'pie_chart']:
            target_width = 3 * inch
        elif q_type in ['fraction_model', 'protractor', 'angle_protractor', 'stem_and_leaf']:
            target_width = 3.5 * inch
        else:
            target_width = 3.5 * inch

        # Calculate height preserving aspect ratio
        target_height = target_width * aspect_ratio

        # Cap height to avoid overflow (max ~5 inches)
        max_height = 5 * inch
        if target_height > max_height:
            target_height = max_height
            target_width = target_height / aspect_ratio

        return Image(buf, width=target_width, height=target_height)

    except Exception as e:
        print(f"Error creating visual: {e}")
        return None


# =============================================================================
# ASSESSMENT GENERATION
# =============================================================================

@planner_bp.route('/api/generate-assessment', methods=['POST'])
def generate_assessment():
    """
    Generate a standards-aligned assessment with DOK level distribution.

    Request body:
    {
        "standards": [{"code": "SS.8.A.1.1", "benchmark": "...", "dok": 2, ...}],
        "config": {
            "grade": "8",
            "subject": "US History",
            "teacher_name": "Mr. Smith"
        },
        "assessmentConfig": {
            "type": "quiz",  // quiz, test, benchmark, formative
            "title": "Chapter 5 Assessment",
            "totalQuestions": 15,
            "questionTypes": {
                "multiple_choice": 10,
                "short_answer": 3,
                "extended_response": 2
            },
            "dokDistribution": {
                "1": 3,   // 3 DOK 1 questions
                "2": 6,   // 6 DOK 2 questions
                "3": 4,   // 4 DOK 3 questions
                "4": 2    // 2 DOK 4 questions
            },
            "includeAnswerKey": true,
            "includeStandardsReference": true
        }
    }
    """
    data = request.json
    standards = data.get('standards', [])
    config = data.get('config', {})
    assessment_config = data.get('assessmentConfig', {})

    if not standards:
        return jsonify({"error": "No standards provided"})

    try:
        from openai import OpenAI
        from dotenv import load_dotenv

        app_dir = Path(__file__).parent.parent.parent
        load_dotenv(app_dir / '.env', override=True)
        api_key = os.getenv("OPENAI_API_KEY")

        if not api_key or api_key.strip() == "" or "your-key-here" in api_key:
            raise Exception("Missing or placeholder API Key")

        client = OpenAI(api_key=api_key)

        # Extract assessment configuration
        assessment_type = assessment_config.get('type', 'quiz')
        title = assessment_config.get('title', f'{config.get("subject", "Subject")} Assessment')
        total_questions = assessment_config.get('totalQuestions', 15)
        total_points = assessment_config.get('totalPoints', 30)
        question_types = assessment_config.get('questionTypes', {
            'multiple_choice': 10,
            'short_answer': 3,
            'extended_response': 2,
            'true_false': 0,
            'matching': 0,
            'math_equation': 0,
            'data_table': 0
        })
        points_per_type = assessment_config.get('pointsPerType', {
            'multiple_choice': 1,
            'short_answer': 2,
            'extended_response': 4,
            'true_false': 1,
            'matching': 1,
            'math_equation': 2,
            'data_table': 3
        })
        dok_distribution = assessment_config.get('dokDistribution', {
            '1': 3, '2': 6, '3': 4, '4': 2
        })
        include_answer_key = assessment_config.get('includeAnswerKey', True)
        include_standards_ref = assessment_config.get('includeStandardsReference', True)
        target_period = assessment_config.get('targetPeriod', '')
        section_categories = assessment_config.get('sectionCategories', {})

        # Get global AI notes from config
        global_ai_notes = config.get('globalAINotes', '')

        # Get content sources (lessons/assignments to base questions on)
        content_sources = data.get('contentSources', [])

        # Build content sources context
        source_content = ""
        if content_sources:
            source_content = "\n=== INSTRUCTIONAL CONTENT TO BASE QUESTIONS ON ===\n"
            source_content += "Generate questions that test the specific content, vocabulary, examples, and activities from these lessons/assignments:\n\n"

            for source in content_sources:
                if source.get('type') == 'lesson':
                    lesson = source.get('content', {})
                    source_content += f"--- LESSON: {lesson.get('title', 'Untitled')} ---\n"
                    source_content += f"Overview: {lesson.get('overview', '')}\n"

                    objectives = lesson.get('learning_objectives', [])
                    if objectives:
                        source_content += f"Learning Objectives: {', '.join(objectives)}\n"

                    questions = lesson.get('essential_questions', [])
                    if questions:
                        source_content += f"Essential Questions: {', '.join(questions)}\n"

                    # Include activities from each day
                    for day in lesson.get('days', []):
                        source_content += f"\nDay {day.get('day', '?')}: {day.get('focus', '')}\n"
                        for activity in day.get('activities', []):
                            source_content += f"  - {activity.get('name', '')}: {activity.get('description', '')}\n"

                    source_content += "\n"

                elif source.get('type') == 'assignment':
                    assignment = source.get('content', {})
                    source_content += f"--- ASSIGNMENT: {assignment.get('title', 'Untitled')} ---\n"
                    source_content += f"Instructions: {assignment.get('instructions', '')}\n"
                    for q in assignment.get('questions', []):
                        source_content += f"  - {q.get('marker', '')}: {q.get('prompt', '')}\n"
                    source_content += "\n"

            source_content += "=== END INSTRUCTIONAL CONTENT ===\n\n"
            source_content += "IMPORTANT: Questions must directly relate to the content above. Reference specific vocabulary, examples, and concepts from the lessons.\n\n"

        # Build standards context
        standards_context = []
        for std in standards:
            std_info = f"""
Standard: {std.get('code', 'N/A')}
Benchmark: {std.get('benchmark', 'N/A')}
DOK Level: {std.get('dok', 2)}
Topics: {', '.join(std.get('topics', []))}
Vocabulary: {', '.join(std.get('vocabulary', [])[:10])}
Learning Targets: {chr(10).join('- ' + lt for lt in std.get('learning_targets', [])[:3])}
Sample Assessment: {std.get('sample_assessment', 'N/A')}
"""
            standards_context.append(std_info)

        # DOK level descriptions for the prompt
        dok_descriptions = """
DOK LEVEL DESCRIPTIONS (Webb's Depth of Knowledge):

DOK 1 - Recall & Reproduction:
- Recall facts, terms, definitions
- Identify, recognize, list, name
- Simple one-step procedures
- Example: "What year did the Civil War begin?"

DOK 2 - Skills & Concepts:
- Compare, contrast, classify, organize
- Make observations, collect data
- Explain relationships, cause/effect
- Example: "Compare the economies of the North and South before the Civil War."

DOK 3 - Strategic Thinking:
- Analyze, evaluate, synthesize
- Draw conclusions, cite evidence
- Develop a logical argument
- Example: "Using evidence from the text, explain how economic differences contributed to sectional tensions."

DOK 4 - Extended Thinking:
- Design, create, connect across content
- Research, investigate over time
- Apply concepts to new situations
- Example: "Research and create a presentation analyzing how Civil War-era economic patterns continue to influence regional differences today."
"""

        # Question type instructions
        question_type_instructions = """
QUESTION TYPE FORMATS:

MULTIPLE CHOICE (type: "multiple_choice"):
{
    "number": 1,
    "question": "Question text here?",
    "dok": 2,
    "standard": "SS.8.A.1.1",
    "options": ["A) Option 1", "B) Option 2", "C) Option 3", "D) Option 4"],
    "answer": "B",
    "explanation": "Brief explanation of why B is correct",
    "points": 1
}

SHORT ANSWER (type: "short_answer"):
{
    "number": 5,
    "question": "Question requiring 2-3 sentence response",
    "dok": 2,
    "standard": "SS.8.A.1.2",
    "answer": "Expected answer or key points to include",
    "rubric": "2 pts: Complete answer with evidence. 1 pt: Partial answer. 0 pts: Incorrect/no answer",
    "points": 2
}

EXTENDED RESPONSE (type: "extended_response"):
{
    "number": 10,
    "question": "Complex question requiring paragraph response with analysis",
    "dok": 3,
    "standard": "SS.8.A.2.1",
    "answer": "Model response or key elements that should be included",
    "rubric": "4 pts: Thorough analysis with multiple pieces of evidence...",
    "points": 4
}

TRUE/FALSE (type: "true_false"):
{
    "number": 3,
    "question": "Statement to evaluate",
    "dok": 1,
    "standard": "SS.8.A.1.1",
    "answer": "True",
    "explanation": "Why this is true/false",
    "points": 1
}

MATCHING (type: "matching"):
{
    "number": 8,
    "question": "Match the terms to their definitions",
    "dok": 1,
    "standard": "SS.8.A.1.1",
    "terms": ["Term 1", "Term 2", "Term 3"],
    "definitions": ["Definition A", "Definition B", "Definition C"],
    "answer": {"Term 1": "Definition B", "Term 2": "Definition C", "Term 3": "Definition A"},
    "points": 3
}

MATH EQUATION (type: "math_equation"):
{
    "number": 12,
    "question": "Solve for x: 3x + 7 = 22",
    "question_type": "math_equation",
    "dok": 2,
    "standard": "MA.8.AR.2.1",
    "answer": "x = 5",
    "points": 2
}

DATA TABLE (type: "data_table"):
{
    "number": 15,
    "question": "Complete the table showing the relationship between x and y, where y = 2x + 1",
    "question_type": "data_table",
    "dok": 2,
    "standard": "MA.8.AR.1.1",
    "column_headers": ["x", "y"],
    "row_labels": ["1", "2", "3", "4", "5"],
    "expected_data": [["3"], ["5"], ["7"], ["9"], ["11"]],
    "points": 3
}
"""

        prompt = f"""You are an expert assessment developer creating a standards-aligned {assessment_type} for grade {config.get('grade', '8')} {config.get('subject', 'students')}.

{dok_descriptions}
{source_content}
STANDARDS TO ASSESS:
{''.join(standards_context)}

ASSESSMENT REQUIREMENTS:
- Title: {title}
- Type: {assessment_type.upper()}
- Total Questions: {total_questions}
- Target Total Points: {total_points}

QUESTION TYPE DISTRIBUTION (with point values per question):
{chr(10).join(f'- {qtype.replace("_", " ").title()}: {count} questions @ {points_per_type.get(qtype, 1)} points each' for qtype, count in question_types.items() if count > 0)}

DOK LEVEL DISTRIBUTION:
- DOK 1 (Recall): {dok_distribution.get('1', 0)} questions
- DOK 2 (Skills/Concepts): {dok_distribution.get('2', 0)} questions
- DOK 3 (Strategic Thinking): {dok_distribution.get('3', 0)} questions
- DOK 4 (Extended Thinking): {dok_distribution.get('4', 0)} questions

{question_type_instructions}

CRITICAL REQUIREMENTS:
1. EVERY question MUST include: "dok" (1-4), "standard" (code), "points", and appropriate answer format
2. STRICTLY use the point values specified above for each question type - this is not optional
3. Questions must DIRECTLY assess the benchmarks provided - not tangentially related content
4. DOK levels must match the cognitive demand - DOK 1 = recall, DOK 3 = analysis with evidence
5. Multiple choice distractors should be plausible but clearly incorrect
6. Include varied question stems (What, How, Why, Analyze, Compare, Evaluate)
7. Extended response questions need detailed rubrics with point breakdowns
8. All questions must be answerable based on the standards content
9. Use grade-appropriate vocabulary and complexity
10. The total_points field MUST equal exactly {total_points}
11. The portal has no drawing canvas. For questions that require hand-drawn work (diagrams, constructions, graphs), tell the student to "show your work on paper and upload a photo" using the image upload option. For most math/geometry, prefer using the interactive visual components (geometry renderer, coordinate plane, number line, protractor) instead of asking students to draw. Only use image upload when no interactive component fits.

SECTION CATEGORIES TO INCLUDE:
{_build_section_categories_prompt(section_categories, config.get('subject', ''))}

{f"TEACHER'S GLOBAL INSTRUCTIONS (MUST FOLLOW):" + chr(10) + global_ai_notes + chr(10) if global_ai_notes else ''}
{f"TARGET PERIOD FOR THIS ASSESSMENT: {target_period}" + chr(10) + "CRITICAL: You MUST apply any period-specific differentiation rules from the teacher instructions above to this period." + chr(10) + "- If the instructions indicate this period is advanced, use more challenging vocabulary, higher-level thinking, and complex scenarios" + chr(10) + "- If the instructions indicate this period is standard or lower level, use simpler vocabulary, more scaffolding, and clearer examples" + chr(10) + "- Adjust question complexity, reading level, and depth of knowledge based on the period designation" + chr(10) if target_period else ''}
Generate a complete assessment in this JSON format:
{{
    "title": "{title}",
    "type": "{assessment_type}",
    "grade": "{config.get('grade', '8')}",
    "subject": "{config.get('subject', 'Subject')}",
    "standards_assessed": ["SS.8.A.1.1", "SS.8.A.1.2"],
    "total_points": {total_points},
    "time_estimate": "45 minutes",
    "instructions": "Clear student instructions...",
    "sections": [
        {{
            "name": "Part A: Multiple Choice",
            "instructions": "Select the best answer for each question.",
            "questions": [...]
        }},
        {{
            "name": "Part B: Short Answer",
            "instructions": "Answer each question in 2-3 complete sentences.",
            "questions": [...]
        }}
    ],
    "answer_key": {{
        "1": {{"answer": "B", "explanation": "..."}},
        "2": {{"answer": "...", "key_points": ["point1", "point2"]}}
    }},
    "dok_summary": {{
        "dok_1_count": 3,
        "dok_2_count": 6,
        "dok_3_count": 4,
        "dok_4_count": 2
    }},
    "standards_alignment": {{
        "SS.8.A.1.1": [1, 3, 5, 8],
        "SS.8.A.1.2": [2, 4, 6, 7, 9, 10]
    }}
}}"""

        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are an expert assessment developer. Create rigorous, standards-aligned assessments. Return valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.7
        )

        content = completion.choices[0].message.content
        assessment = json.loads(content)
        _auto_upgrade_visual_types(assessment)
        _ensure_geometry_defaults(assessment)
        _ensure_data_table_defaults(assessment)
        _hydrate_math_visuals(assessment)

        # Add metadata for portal grading context
        assessment['generated_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
        assessment['teacher'] = config.get('teacher_name', '')
        assessment['grade_level'] = config.get('grade', '8')
        assessment['subject'] = config.get('subject', 'General')

        usage = _extract_usage(completion, "gpt-4o")
        _record_planner_cost(usage)
        return jsonify({"assessment": assessment, "method": "AI", "usage": usage})

    except Exception as e:
        error_msg = str(e)
        print(f"Assessment Generation Error: {error_msg}")
        return jsonify({"error": f"Failed to generate assessment: {error_msg}"}), 500


@planner_bp.route('/api/export-assessment', methods=['POST'])
def export_assessment():
    """Export assessment to Word document."""
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch

    data = request.json
    assessment = data.get('assessment', {})
    include_answer_key = data.get('includeAnswerKey', False)

    if not assessment:
        return jsonify({"error": "No assessment data provided"})

    try:
        from docx import Document
        from docx.shared import Inches, Pt
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        import tempfile
        import base64

        doc = Document()

        # Title
        title = doc.add_heading(assessment.get('title', 'Assessment'), 0)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER

        # Header info
        header_info = doc.add_paragraph()
        header_info.add_run(f"Subject: {assessment.get('subject', '')}").bold = True
        header_info.add_run(f"    Grade: {assessment.get('grade', '')}")
        header_info.add_run(f"    Time: {assessment.get('time_estimate', '')}")
        header_info.add_run(f"    Total Points: {assessment.get('total_points', '')}")

        # Student info line
        doc.add_paragraph("Name: _________________________    Date: _____________    Period: _____")

        # Instructions
        if assessment.get('instructions'):
            inst = doc.add_paragraph()
            inst.add_run("Instructions: ").bold = True
            inst.add_run(assessment.get('instructions'))

        doc.add_paragraph()  # Space

        # Sections
        for section in assessment.get('sections', []):
            # Section header
            sec_head = doc.add_heading(section.get('name', 'Section'), level=1)

            if section.get('instructions'):
                sec_inst = doc.add_paragraph()
                sec_inst.add_run(section.get('instructions')).italic = True

            # Questions
            for q in section.get('questions', []):
                q_para = doc.add_paragraph()
                q_num = q.get('number', '')
                q_text = q.get('question', '')
                q_points = q.get('points', 1)
                q_dok = q.get('dok', '')

                # Question number and text
                q_para.add_run(f"{q_num}. ").bold = True
                q_para.add_run(f"{q_text} ")
                q_para.add_run(f"({q_points} pt{'s' if q_points > 1 else ''})").italic = True

                # Multiple choice options
                if q.get('options'):
                    for opt in q.get('options', []):
                        opt_para = doc.add_paragraph(f"    {opt}")
                        opt_para.paragraph_format.space_before = Pt(2)
                        opt_para.paragraph_format.space_after = Pt(2)

                # Matching terms and definitions
                if q.get('terms') and q.get('definitions'):
                    doc.add_paragraph("Terms:")
                    for i, term in enumerate(q.get('terms', []), 1):
                        doc.add_paragraph(f"    {i}. {term}")
                    doc.add_paragraph("Definitions:")
                    for letter_idx, defn in enumerate(q.get('definitions', [])):
                        letter = chr(65 + letter_idx)  # A, B, C...
                        doc.add_paragraph(f"    {letter}. {defn}")

                # Answer lines for short answer/extended response
                q_type = q.get('type', section.get('type', ''))
                if q_type in ['short_answer', 'extended_response']:
                    lines = 3 if q_type == 'short_answer' else 8
                    for _ in range(lines):
                        doc.add_paragraph("_" * 70)

                doc.add_paragraph()  # Space between questions

        # Answer Key (separate page)
        if include_answer_key:
            doc.add_page_break()
            doc.add_heading("Answer Key", 0)

            answer_key = assessment.get('answer_key', {})
            for q_num, answer_data in sorted(answer_key.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 0):
                ans_para = doc.add_paragraph()
                ans_para.add_run(f"{q_num}. ").bold = True

                if isinstance(answer_data, dict):
                    ans_para.add_run(str(answer_data.get('answer', '')))
                    if answer_data.get('explanation'):
                        ans_para.add_run(f" - {answer_data.get('explanation')}")
                else:
                    ans_para.add_run(str(answer_data))

        # Save to temp file and encode
        with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as tmp:
            doc.save(tmp.name)
            tmp.seek(0)
            with open(tmp.name, 'rb') as f:
                doc_bytes = f.read()
            os.unlink(tmp.name)

        doc_base64 = base64.b64encode(doc_bytes).decode('utf-8')

        # Generate filename
        safe_title = ''.join(c if c.isalnum() or c in ' -_' else '' for c in assessment.get('title', 'Assessment'))
        filename = f"{safe_title.replace(' ', '_')}.docx"

        return jsonify({
            "document": doc_base64,
            "filename": filename,
            "format": "docx"
        })

    except Exception as e:
        print(f"Export error: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# ASSESSMENT PLATFORM TEMPLATES
# =============================================================================

TEMPLATES_DIR = os.path.expanduser("~/.graider_data/assessment_templates")


@planner_bp.route('/api/upload-assessment-template', methods=['POST'])
def upload_assessment_template():
    """Upload a sample template from an assessment platform (e.g., Wayground, Canvas)."""
    import uuid

    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files['file']
    platform = request.form.get('platform', 'custom')
    name = request.form.get('name', 'Untitled Template')

    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400

    # Create templates directory if it doesn't exist
    os.makedirs(TEMPLATES_DIR, exist_ok=True)

    # Generate unique ID
    template_id = str(uuid.uuid4())[:8]

    # Save the file
    ext = os.path.splitext(file.filename)[1].lower()
    filename = f"{template_id}_{platform}{ext}"
    filepath = os.path.join(TEMPLATES_DIR, filename)
    file.save(filepath)

    # Parse the template to understand its structure
    template_structure = parse_template_structure(filepath, ext)

    # Save metadata
    metadata = {
        "id": template_id,
        "name": name,
        "platform": platform,
        "filename": filename,
        "filepath": filepath,
        "original_filename": file.filename,
        "extension": ext,
        "structure": template_structure,
        "created_at": time.strftime('%Y-%m-%d %H:%M:%S')
    }

    metadata_path = os.path.join(TEMPLATES_DIR, f"{template_id}.meta.json")
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)

    return jsonify({
        "success": True,
        "template": metadata,
        "message": f"Template '{name}' uploaded successfully"
    })


def parse_template_structure(filepath, ext):
    """Parse a template file to understand its structure for export."""
    structure = {
        "columns": [],
        "format": ext,
        "sample_rows": []
    }

    try:
        if ext in ['.csv', '.txt']:
            import csv
            with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                rows = list(reader)
                if rows:
                    structure["columns"] = rows[0]
                    structure["sample_rows"] = rows[1:4]  # First 3 data rows

        elif ext in ['.xlsx', '.xls']:
            from openpyxl import load_workbook
            wb = load_workbook(filepath)
            ws = wb.active
            rows = list(ws.iter_rows(values_only=True))
            if rows:
                structure["columns"] = [str(c) if c else '' for c in rows[0]]
                structure["sample_rows"] = [[str(c) if c else '' for c in row] for row in rows[1:4]]

        elif ext == '.json':
            with open(filepath, 'r') as f:
                data = json.load(f)
                if isinstance(data, list) and data:
                    structure["columns"] = list(data[0].keys()) if isinstance(data[0], dict) else []
                    structure["sample_rows"] = data[:3]
                elif isinstance(data, dict):
                    structure["columns"] = list(data.keys())

    except Exception as e:
        structure["error"] = str(e)

    return structure


@planner_bp.route('/api/assessment-templates', methods=['GET'])
def get_assessment_templates():
    """Get all uploaded assessment templates."""
    templates = []

    if not os.path.exists(TEMPLATES_DIR):
        return jsonify({"templates": []})

    for f in os.listdir(TEMPLATES_DIR):
        if f.endswith('.meta.json'):
            try:
                with open(os.path.join(TEMPLATES_DIR, f), 'r') as mf:
                    metadata = json.load(mf)
                    templates.append(metadata)
            except:
                pass

    # Sort by creation date (newest first)
    templates.sort(key=lambda x: x.get('created_at', ''), reverse=True)

    return jsonify({"templates": templates})


@planner_bp.route('/api/assessment-template/<template_id>', methods=['DELETE'])
def delete_assessment_template(template_id):
    """Delete an assessment template."""
    if not os.path.exists(TEMPLATES_DIR):
        return jsonify({"error": "Template not found"}), 404

    # Find and delete metadata and file
    meta_path = os.path.join(TEMPLATES_DIR, f"{template_id}.meta.json")

    if not os.path.exists(meta_path):
        return jsonify({"error": "Template not found"}), 404

    try:
        with open(meta_path, 'r') as f:
            metadata = json.load(f)

        # Delete the template file
        if metadata.get('filepath') and os.path.exists(metadata['filepath']):
            os.remove(metadata['filepath'])

        # Delete metadata
        os.remove(meta_path)

        return jsonify({"success": True, "message": "Template deleted"})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@planner_bp.route('/api/export-assessment-platform', methods=['POST'])
def export_assessment_for_platform():
    """Export assessment in a specific platform's format."""
    data = request.json
    assessment = data.get('assessment', {})
    platform = data.get('platform', 'csv')
    template_id = data.get('templateId')

    if not assessment:
        return jsonify({"error": "No assessment data provided"}), 400

    try:
        import csv
        import io
        import base64

        # Get template structure if provided
        template_structure = None
        if template_id:
            meta_path = os.path.join(TEMPLATES_DIR, f"{template_id}.meta.json")
            if os.path.exists(meta_path):
                with open(meta_path, 'r') as f:
                    template_meta = json.load(f)
                    template_structure = template_meta.get('structure', {})

        # Flatten questions from all sections
        all_questions = []
        for section in assessment.get('sections', []):
            for q in section.get('questions', []):
                all_questions.append({
                    **q,
                    'section': section.get('name', '')
                })

        # Export based on platform
        if platform == 'wayground' or platform == 'csv':
            # Generic CSV format - can be customized based on template
            output = io.StringIO()

            # Determine columns based on template or default
            if template_structure and template_structure.get('columns'):
                columns = template_structure['columns']
            else:
                columns = ['Question Number', 'Question', 'Type', 'Options', 'Answer',
                          'Points', 'DOK Level', 'Standard', 'Section']

            writer = csv.writer(output)
            writer.writerow(columns)

            for q in all_questions:
                options = '|'.join(q.get('options', [])) if q.get('options') else ''
                answer = q.get('answer', '')
                if isinstance(answer, dict):
                    answer = str(answer)

                row = [
                    q.get('number', ''),
                    q.get('question', ''),
                    q.get('type', 'multiple_choice'),
                    options,
                    answer,
                    q.get('points', 1),
                    q.get('dok', 2),
                    q.get('standard', ''),
                    q.get('section', '')
                ]
                writer.writerow(row)

            content = output.getvalue()
            content_b64 = base64.b64encode(content.encode('utf-8')).decode('utf-8')

            safe_title = ''.join(c if c.isalnum() or c in ' -_' else '' for c in assessment.get('title', 'Assessment'))
            filename = f"{safe_title.replace(' ', '_')}_{platform}.csv"

            return jsonify({
                "document": content_b64,
                "filename": filename,
                "format": "csv",
                "mime_type": "text/csv"
            })

        elif platform == 'canvas_qti':
            # QTI format for Canvas
            # This is a simplified QTI - full implementation would be more complex
            qti_xml = generate_qti_xml(assessment, all_questions)
            content_b64 = base64.b64encode(qti_xml.encode('utf-8')).decode('utf-8')

            safe_title = ''.join(c if c.isalnum() or c in ' -_' else '' for c in assessment.get('title', 'Assessment'))
            filename = f"{safe_title.replace(' ', '_')}_qti.xml"

            return jsonify({
                "document": content_b64,
                "filename": filename,
                "format": "xml",
                "mime_type": "application/xml"
            })

        elif platform == 'kahoot':
            # Kahoot spreadsheet format
            output = io.StringIO()
            writer = csv.writer(output)

            # Kahoot format: Question, Answer 1, Answer 2, Answer 3, Answer 4, Time limit, Correct answer(s)
            writer.writerow(['Question', 'Answer 1', 'Answer 2', 'Answer 3', 'Answer 4',
                           'Time limit', 'Correct answer(s)'])

            for q in all_questions:
                if q.get('options'):
                    options = q.get('options', [])
                    # Clean options (remove A), B), etc. prefixes)
                    clean_options = []
                    for opt in options[:4]:
                        clean = opt.strip()
                        if len(clean) > 2 and clean[1] == ')':
                            clean = clean[2:].strip()
                        clean_options.append(clean)

                    # Pad to 4 options
                    while len(clean_options) < 4:
                        clean_options.append('')

                    # Determine correct answer number
                    correct = q.get('answer', 'A')
                    if isinstance(correct, str) and len(correct) == 1:
                        correct_num = ord(correct.upper()) - ord('A') + 1
                    else:
                        correct_num = 1

                    writer.writerow([
                        q.get('question', ''),
                        clean_options[0],
                        clean_options[1],
                        clean_options[2],
                        clean_options[3],
                        30,  # Default 30 second time limit
                        correct_num
                    ])

            content = output.getvalue()
            content_b64 = base64.b64encode(content.encode('utf-8')).decode('utf-8')

            safe_title = ''.join(c if c.isalnum() or c in ' -_' else '' for c in assessment.get('title', 'Assessment'))
            filename = f"{safe_title.replace(' ', '_')}_kahoot.csv"

            return jsonify({
                "document": content_b64,
                "filename": filename,
                "format": "csv",
                "mime_type": "text/csv"
            })

        elif platform == 'quizlet':
            # Quizlet import format: term<tab>definition (or question<tab>answer)
            output = io.StringIO()

            for q in all_questions:
                question = q.get('question', '')
                answer = q.get('answer', '')
                if isinstance(answer, dict):
                    answer = answer.get('answer', str(answer))
                output.write(f"{question}\t{answer}\n")

            content = output.getvalue()
            content_b64 = base64.b64encode(content.encode('utf-8')).decode('utf-8')

            safe_title = ''.join(c if c.isalnum() or c in ' -_' else '' for c in assessment.get('title', 'Assessment'))
            filename = f"{safe_title.replace(' ', '_')}_quizlet.txt"

            return jsonify({
                "document": content_b64,
                "filename": filename,
                "format": "txt",
                "mime_type": "text/plain"
            })

        elif platform == 'google_forms':
            # Google Forms compatible CSV
            output = io.StringIO()
            writer = csv.writer(output)

            writer.writerow(['Question', 'Question Type', 'Required', 'Option 1',
                           'Option 2', 'Option 3', 'Option 4', 'Correct Answer', 'Points'])

            for q in all_questions:
                q_type = q.get('type', 'multiple_choice')
                if q_type == 'multiple_choice':
                    gf_type = 'MULTIPLE_CHOICE'
                elif q_type == 'short_answer':
                    gf_type = 'SHORT_ANSWER'
                elif q_type == 'true_false':
                    gf_type = 'MULTIPLE_CHOICE'
                else:
                    gf_type = 'PARAGRAPH'

                options = q.get('options', ['', '', '', ''])
                while len(options) < 4:
                    options.append('')

                writer.writerow([
                    q.get('question', ''),
                    gf_type,
                    'TRUE',
                    options[0] if options else '',
                    options[1] if len(options) > 1 else '',
                    options[2] if len(options) > 2 else '',
                    options[3] if len(options) > 3 else '',
                    q.get('answer', ''),
                    q.get('points', 1)
                ])

            content = output.getvalue()
            content_b64 = base64.b64encode(content.encode('utf-8')).decode('utf-8')

            safe_title = ''.join(c if c.isalnum() or c in ' -_' else '' for c in assessment.get('title', 'Assessment'))
            filename = f"{safe_title.replace(' ', '_')}_google_forms.csv"

            return jsonify({
                "document": content_b64,
                "filename": filename,
                "format": "csv",
                "mime_type": "text/csv"
            })

        else:
            return jsonify({"error": f"Unknown platform: {platform}"}), 400

    except Exception as e:
        print(f"Platform export error: {e}")
        return jsonify({"error": str(e)}), 500


def generate_qti_xml(assessment, questions):
    """Generate QTI 1.2 XML for Canvas/LMS import."""
    title = assessment.get('title', 'Assessment')

    xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<questestinterop xmlns="http://www.imsglobal.org/xsd/ims_qtiasiv1p2">
  <assessment ident="{title.replace(' ', '_')}" title="{title}">
    <section ident="root_section">
'''

    for q in questions:
        q_id = f"q_{q.get('number', 1)}"
        q_text = q.get('question', '')
        q_type = q.get('type', 'multiple_choice')
        points = q.get('points', 1)

        if q_type == 'multiple_choice' and q.get('options'):
            xml += f'''      <item ident="{q_id}" title="Question {q.get('number', '')}">
        <itemmetadata>
          <qtimetadata>
            <qtimetadatafield>
              <fieldlabel>question_type</fieldlabel>
              <fieldentry>multiple_choice_question</fieldentry>
            </qtimetadatafield>
            <qtimetadatafield>
              <fieldlabel>points_possible</fieldlabel>
              <fieldentry>{points}</fieldentry>
            </qtimetadatafield>
          </qtimetadata>
        </itemmetadata>
        <presentation>
          <material>
            <mattext texttype="text/html">{q_text}</mattext>
          </material>
          <response_lid ident="response1" rcardinality="Single">
            <render_choice>
'''
            correct_answer = q.get('answer', 'A')
            for i, opt in enumerate(q.get('options', [])):
                opt_id = chr(65 + i)  # A, B, C, D
                opt_text = opt
                if len(opt) > 2 and opt[1] == ')':
                    opt_text = opt[2:].strip()
                xml += f'''              <response_label ident="{opt_id}">
                <material>
                  <mattext texttype="text/html">{opt_text}</mattext>
                </material>
              </response_label>
'''
            xml += f'''            </render_choice>
          </response_lid>
        </presentation>
        <resprocessing>
          <outcomes>
            <decvar maxvalue="100" minvalue="0" varname="SCORE" vartype="Decimal"/>
          </outcomes>
          <respcondition continue="No">
            <conditionvar>
              <varequal respident="response1">{correct_answer}</varequal>
            </conditionvar>
            <setvar action="Set" varname="SCORE">100</setvar>
          </respcondition>
        </resprocessing>
      </item>
'''

    xml += '''    </section>
  </assessment>
</questestinterop>'''

    return xml


@planner_bp.route('/api/grade-assessment-answers', methods=['POST'])
def grade_assessment_answers():
    """
    Grade student answers against the assessment using AI for open-ended questions.
    Returns detailed feedback for each question.
    """
    try:
        data = request.json
        assessment = data.get('assessment', {})
        answers = data.get('answers', {})

        if not assessment or not answers:
            return jsonify({"error": "Missing assessment or answers"}), 400

        results = {
            "questions": [],
            "score": 0,
            "total_points": 0,
            "percentage": 0,
            "feedback_summary": ""
        }

        # Collect questions that need AI grading (short answer, extended response)
        ai_grading_needed = []

        # Process each section and question
        for sIdx, section in enumerate(assessment.get('sections', [])):
            for qIdx, question in enumerate(section.get('questions', [])):
                answer_key = f"{sIdx}-{qIdx}"
                student_answer = answers.get(answer_key)
                q_type = question.get('type', 'multiple_choice')
                points = question.get('points', 1)
                correct_answer = question.get('answer')

                results["total_points"] += points

                question_result = {
                    "number": question.get('number', qIdx + 1),
                    "question": question.get('question', ''),
                    "type": q_type,
                    "student_answer": student_answer,
                    "correct_answer": correct_answer,
                    "points_possible": points,
                    "points_earned": 0,
                    "is_correct": False,
                    "feedback": ""
                }

                if student_answer is None or student_answer == "":
                    question_result["feedback"] = "No answer provided"
                    results["questions"].append(question_result)
                    continue

                # Grade based on question type
                if q_type == "multiple_choice":
                    # Check if answer matches (handle both index and letter formats)
                    options = question.get('options', [])
                    student_letter = None
                    if isinstance(student_answer, int) and student_answer < len(options):
                        student_letter = chr(65 + student_answer)  # Convert index to letter
                    elif isinstance(student_answer, str):
                        student_letter = student_answer.upper().strip()
                        if len(student_letter) > 1 and student_letter[1] == ')':
                            student_letter = student_letter[0]

                    correct_letter = correct_answer.upper().strip() if correct_answer else ""
                    if len(correct_letter) > 1 and correct_letter[1] == ')':
                        correct_letter = correct_letter[0]

                    is_correct = student_letter == correct_letter
                    question_result["is_correct"] = is_correct
                    question_result["points_earned"] = points if is_correct else 0
                    question_result["student_answer"] = f"{student_letter}) {options[ord(student_letter) - 65] if student_letter and ord(student_letter) - 65 < len(options) else student_answer}" if student_letter else student_answer
                    question_result["feedback"] = "Correct!" if is_correct else f"Incorrect. The correct answer is {correct_answer}."

                elif q_type == "true_false":
                    is_correct = str(student_answer).lower() == str(correct_answer).lower()
                    question_result["is_correct"] = is_correct
                    question_result["points_earned"] = points if is_correct else 0
                    explanation = question.get('explanation', '')
                    question_result["feedback"] = "Correct!" if is_correct else f"Incorrect. The answer is {correct_answer}. {explanation}"

                elif q_type == "matching":
                    # Check matching answers
                    correct_matches = question.get('answer', {})
                    terms = question.get('terms', [])
                    total_matches = len(terms)
                    correct_count = 0

                    match_details = []
                    for tIdx in range(total_matches):
                        match_key = f"{sIdx}-{qIdx}-match-{tIdx}"
                        student_match = answers.get(match_key, "")
                        term = terms[tIdx] if tIdx < len(terms) else f"Term {tIdx + 1}"

                        # Find correct letter for this term
                        correct_letter = None
                        definitions = question.get('definitions', [])
                        if term in correct_matches:
                            correct_def = correct_matches[term]
                            try:
                                def_idx = definitions.index(correct_def)
                                correct_letter = chr(65 + def_idx)
                            except ValueError:
                                correct_letter = None

                        is_match_correct = student_match.upper() == correct_letter if correct_letter else False
                        if is_match_correct:
                            correct_count += 1
                        match_details.append({
                            "term": term,
                            "student": student_match,
                            "correct": correct_letter,
                            "is_correct": is_match_correct
                        })

                    # Partial credit
                    earned = round(points * (correct_count / total_matches)) if total_matches > 0 else 0
                    question_result["points_earned"] = earned
                    question_result["is_correct"] = correct_count == total_matches
                    question_result["match_details"] = match_details
                    question_result["feedback"] = f"Got {correct_count}/{total_matches} matches correct."

                elif q_type in ["short_answer", "extended_response"]:
                    # Queue for AI grading
                    ai_grading_needed.append({
                        "index": len(results["questions"]),
                        "question": question,
                        "student_answer": student_answer,
                        "result": question_result
                    })

                results["questions"].append(question_result)

        # AI grading for open-ended questions
        grading_usage = {"model": "gpt-4o-mini", "input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "cost": 0}
        if ai_grading_needed:
            try:
                from openai import OpenAI
                client = OpenAI()

                for item in ai_grading_needed:
                    q = item["question"]
                    student_ans = item["student_answer"]
                    q_result = item["result"]
                    points = q.get('points', 1)

                    grading_prompt = f"""Grade this student answer for the following question.

Question: {q.get('question', '')}
Question Type: {q.get('type', 'short_answer')}
Points Possible: {points}
Correct/Model Answer: {q.get('answer', 'N/A')}
Rubric: {q.get('rubric', 'N/A')}
DOK Level: {q.get('dok', 'N/A')}
Standard: {q.get('standard', 'N/A')}

Student's Answer: {student_ans}

Evaluate the student's response and provide:
1. Points earned (0 to {points})
2. Brief feedback (2-3 sentences)
3. Whether the answer demonstrates understanding

Respond in JSON format:
{{"points_earned": <number>, "feedback": "<string>", "is_correct": <boolean>}}"""

                    response = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {"role": "system", "content": "You are a fair and helpful teacher grading student work. Be encouraging but accurate. Provide constructive feedback."},
                            {"role": "user", "content": grading_prompt}
                        ],
                        response_format={"type": "json_object"},
                        max_tokens=300
                    )

                    u = _extract_usage(response, "gpt-4o-mini")
                    if u:
                        for k in ["input_tokens", "output_tokens", "total_tokens", "cost"]:
                            grading_usage[k] += u[k]

                    ai_result = json.loads(response.choices[0].message.content)
                    q_result["points_earned"] = min(ai_result.get("points_earned", 0), points)
                    q_result["feedback"] = ai_result.get("feedback", "")
                    q_result["is_correct"] = ai_result.get("is_correct", False)

                    # Update in results
                    results["questions"][item["index"]] = q_result

            except Exception as e:
                print(f"AI grading error: {e}")
                # Fall back to basic comparison for failed AI grading
                for item in ai_grading_needed:
                    q_result = item["result"]
                    q_result["feedback"] = "Answer recorded. Manual review recommended."
                    q_result["points_earned"] = 0
                    results["questions"][item["index"]] = q_result

        # Calculate final score
        results["score"] = sum(q["points_earned"] for q in results["questions"])
        results["percentage"] = round((results["score"] / results["total_points"]) * 100) if results["total_points"] > 0 else 0

        # Generate summary feedback
        correct_count = sum(1 for q in results["questions"] if q["is_correct"])
        total_questions = len(results["questions"])
        results["feedback_summary"] = f"You answered {correct_count} out of {total_questions} questions correctly, earning {results['score']}/{results['total_points']} points ({results['percentage']}%)."

        grading_usage["cost"] = round(grading_usage["cost"], 6)
        grading_usage["cost_display"] = f"${grading_usage['cost']:.4f}"
        _record_planner_cost(grading_usage if grading_usage["total_tokens"] > 0 else None)
        return jsonify({"results": results, "usage": grading_usage if grading_usage["total_tokens"] > 0 else None})

    except Exception as e:
        print(f"Grade assessment error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@planner_bp.route('/api/planner/costs', methods=['GET'])
def get_planner_costs():
    """Return planner API cost summary."""
    try:
        with open(PLANNER_COSTS_FILE, 'r') as f:
            return jsonify(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return jsonify({"total": {"input_tokens": 0, "output_tokens": 0, "total_cost": 0, "api_calls": 0}, "daily": {}})
