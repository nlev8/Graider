"""
Lesson Planner API routes for Graider.
Handles standards retrieval and lesson plan generation/export.
"""
import os
import sys
import json
import time
import math
import re
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
        'florida_fast': {
            'name': 'FL FAST Item Types',
            'instruction': 'Generate Florida FAST-style items. Use "multiselect" (select all that apply with options array and correct indices array), "multi_part" (compound Part A/B with parts array where each part has its own question_type, options, answer, and points), "grid_match" (matrix matching with row_labels, column_labels, and correct 2D one-hot array), "inline_dropdown" (cloze with {0},{1} placeholders in question text and dropdowns array with options and correct index). These mirror the actual FAST test format.',
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

# Patterns for common theorem setups to detect over-determined or inconsistent values
_TANGENT_SECANT_RE = _re.compile(
    r'tangent.*(?:external|outside).*?(\d+(?:\.\d+)?).*?(?:whole|secant).*?(\d+(?:\.\d+)?)',
    _re.IGNORECASE | _re.DOTALL,
)
_CHORD_CHORD_RE = _re.compile(
    r'chord.*?(\d+(?:\.\d+)?)\s*[×*·]\s*(\d+(?:\.\d+)?)\s*=\s*(\d+(?:\.\d+)?)\s*[×*·]\s*(\d+(?:\.\d+)?)',
    _re.IGNORECASE,
)
_PYTHAGOREAN_RE = _re.compile(
    r'(?:right\s+triangle|hypotenuse|legs?).*?(\d+(?:\.\d+)?).*?(\d+(?:\.\d+)?).*?(\d+(?:\.\d+)?)',
    _re.IGNORECASE | _re.DOTALL,
)


def _validate_question_quality(assignment, subject=None, grade=None, valid_standard_codes=None):
    """Phase 3c: Run deterministic quality checks on every question.

    Returns a list of warning dicts: [{section_idx, question_idx, issue, severity}]
    Attaches 'warning' and 'warning_severity' fields to flagged questions.
    """
    warnings = []
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

    # CHECK 16: Missing standard field (required for subject enforcement)
    if valid_standard_codes and not q.get('standard'):
        issues.append({
            'issue': 'Missing standard code — cannot verify subject alignment',
            'severity': 'warning',
        })

    return issues


def _auto_fix_flagged_questions(assignment, warnings, subject=None, grade=None,
                                valid_standard_codes=None):
    """Attempt AI-powered fixes for flagged questions.

    Uses gpt-4o-mini to review and fix problematic questions in a single batch.
    Only called when deterministic checks flag issues.
    """
    # Collect questions with errors (not just warnings)
    error_items = [w for w in warnings if w['severity'] == 'error']
    if not error_items:
        return  # Only auto-fix errors; warnings are shown to teacher

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
        from openai import OpenAI
        api_key = os.getenv('OPENAI_API_KEY', '')
        if not api_key or api_key.startswith('your-'):
            return
        client = OpenAI(api_key=api_key)

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

        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You fix assessment questions. Return valid JSON only."},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
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
    - Under target: duplicates existing questions with adjusted numbering.
    Returns (assignment, None) — no extra usage since this is pure logic.
    """
    sections = assignment.get('sections', [])
    if not sections:
        return assignment, None

    current = _count_questions(assignment)
    if current == target:
        return assignment, None

    # ── Over target: trim from largest sections first ──
    while current > target:
        largest = max(sections, key=lambda s: len(s.get('questions', [])))
        qs = largest.get('questions', [])
        if not qs:
            break
        qs.pop()  # remove last question
        current -= 1

    # ── Under target: duplicate existing questions into smallest sections ──
    # Build a pool of all existing questions to cycle through
    pool = []
    for s in sections:
        for q in s.get('questions', []):
            pool.append(q)
    if not pool:
        return assignment, None

    pool_idx = 0
    while current < target:
        # Pick the source question to duplicate (cycle through pool)
        source = pool[pool_idx % len(pool)]
        pool_idx += 1

        # Create a copy with updated number
        import copy
        new_q = copy.deepcopy(source)
        new_q['number'] = current + 1

        # Add to the smallest section to keep distribution even
        smallest = min(sections, key=lambda s: len(s.get('questions', [])))
        smallest.setdefault('questions', []).append(new_q)
        current += 1

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

    _subject = config.get('subject', '').strip()
    _grade = config.get('grade', '').strip()
    if not _subject or not _grade:
        from flask import current_app
        current_app.logger.warning(
            f"Brainstorm requested without subject/grade: subject={_subject!r}, grade={_grade!r}")

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

        subject_boundary = _build_subject_boundary_prompt(
            config.get('subject', ''), config.get('grade', ''))

        prompt = f"""You are an expert curriculum developer brainstorming lesson plan ideas for a {config.get('grade', '7')}th grade {config.get('subject', 'Social Studies')} class.
{subject_boundary}
{support_docs}

STANDARDS TO COVER (every idea MUST directly address these specific standards):
{standards_text}

IMPORTANT: Read the benchmark text, vocabulary, and learning targets above carefully. Every lesson idea must be DIRECTLY about the specific topic described in the standard(s). Do NOT generate ideas about other topics, time periods, or standards — ONLY the ones listed above.

TEACHER'S ADDITIONAL REQUIREMENTS:
{config.get('requirements', '').strip() or 'None specified'}
NOTE: If the teacher specified additional requirements above, EVERY idea must reflect those requirements. For example, if the teacher says "focus on consequences of the Mexican American War", then all 6 ideas must center on consequences specifically — not just mention the topic generally.
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

    _subject = config.get('subject', '').strip()
    _grade = config.get('grade', '').strip()
    if not _subject or not _grade:
        from flask import current_app
        current_app.logger.warning(
            f"Lesson plan requested without subject/grade: subject={_subject!r}, grade={_grade!r}")

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

        # Build subject boundary constraint for prompt injection
        subject_boundary = _build_subject_boundary_prompt(
            config.get('subject', ''), config.get('grade', ''))

        # Build content-type-specific prompt, JSON structure, and instructions
        common_header = f"""You are an expert curriculum developer creating a COMPLETE, READY-TO-USE {content_type} for a {config.get('grade', '7')}th grade {config.get('subject', 'Civics')} class.
{subject_boundary}
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
            total_q = config.get('totalQuestions', 10)
            per_section = config.get('questionsPerSection', 0)
            # Compute per-section distribution from enabled categories
            enabled_cats = [k for k, v in assignment_section_cats.items() if v] if assignment_section_cats else ['multiple_choice', 'short_answer']
            num_sections = max(len(enabled_cats), 1)
            if per_section > 0:
                per_sec = per_section
            else:
                per_sec = max(total_q // num_sections, 2)
                remainder = total_q - (per_sec * num_sections)
            question_target = f"\nQUESTION COUNT: Generate exactly {total_q} questions total."
            question_target += f" Distribute them across your sections — aim for {per_sec} questions per section."
            question_target += f" You MUST have at least {total_q} questions in the final JSON.\n"

            prompt = common_header + f"""
Create a complete, ready-to-use assignment that directly assesses the standards listed above.
The assignment should be appropriate for grade {config.get('grade', '7')} students.
{question_target}
{assignment_sections_block}
CRITICAL REQUIREMENTS:
1. THE ASSIGNMENT MUST BE 100% SELF-CONTAINED — every resource referenced (tables, charts, reading passages, data) MUST be included in the JSON
2. For Math: use REAL numbers and actual problems, not placeholders
3. Include clear, specific answer keys for every question
4. ONLY include section types that the teacher has enabled above — do NOT add vocabulary or matching sections unless explicitly enabled
5. All questions must be answerable based on the standards content
6. For math/computation questions: SELF-CHECK that all given numeric values are consistent. Verify the numbers satisfy any stated theorem or formula BEFORE including the question. Never give more numeric values than needed to solve the problem.
7. Every question must be solvable with ONLY the given information — no hidden assumptions or missing data.
8. For ELA/reading questions: If a question asks students to analyze, cite, or refer to a passage/text/excerpt, the FULL passage MUST be included in the "question" field. NEVER reference a passage that is not embedded. "According to the passage..." is only valid if the passage text precedes it in the question field.
9. For science questions: Use ONE consistent unit system (metric or imperial) per question unless the question is explicitly about unit conversion. All numeric values must be physically possible (no negative mass, no temperatures below absolute zero, no pH outside 0-14).

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

QUESTION TYPE GUIDANCE:
- For most questions, DO NOT set question_type — the system assigns it automatically from your text and structure.
- Write geometry dimensions clearly in question text: "Find the area of a triangle with base 8 cm and height 5 cm"
- Write equations clearly: "Graph y = 2x + 1 on the coordinate plane"
- For multiple choice, include "options" array. For matching, include "terms" and "definitions".
- ONLY set question_type explicitly for these complex types that need structured data:
  data_table (include headers, row_labels, expected_data with ALL values filled, editable_columns for calculation tables),
  box_plot (include data array), dot_plot (include data),
  stem_and_leaf (include data), bar_chart (include chart_data),
  transformations (include original_vertices, transformation_type, transform_params),
  fraction_model (include model_type, denominator, correct_numerator),
  probability_tree, tape_diagram, venn_diagram,
  protractor (include mode, target_angle),
  multiselect (include options, correct indices),
  multi_part (include parts array),
  grid_match (include row_labels, column_labels, correct matrix),
  inline_dropdown (include dropdowns array)

Make the questions SPECIFIC with real content tied to the standards. Include a variety of question types. For STEM subjects, include geometry and graphing questions with dimensions in the question text.

"""

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
                if content_type == 'Assignment':
                    target_q = config.get('totalQuestions', 10)
                    lp_std_codes = [s.split(':')[0].strip() for s in selected_standards if ':' in s]
                    plan, extra_usage = _post_process_assignment(
                        plan, target_q, target_total_points=100,
                        subject=config.get('subject'), grade=config.get('grade'),
                        valid_standard_codes=lp_std_codes if lp_std_codes else None)
                    if extra_usage:
                        for k in ["input_tokens", "output_tokens", "total_tokens", "cost"]:
                            total_usage[k] += extra_usage.get(k, 0)
                else:
                    if plan.get('days') and plan.get('sections'):
                        del plan['sections']
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

        if content_type == 'Assignment':
            target_q = config.get('totalQuestions', 10)
            lp_std_codes = [s.split(':')[0].strip() for s in selected_standards if ':' in s]
            plan, extra_usage = _post_process_assignment(
                plan, target_q, target_total_points=100,
                subject=config.get('subject'), grade=config.get('grade'),
                valid_standard_codes=lp_std_codes if lp_std_codes else None)
        else:
            extra_usage = None
            # Strip stray sections/questions from non-assignment types so
            # the frontend never misidentifies a lesson plan as an assignment
            if plan.get('days') and plan.get('sections'):
                del plan['sections']

        usage = _extract_usage(completion, "gpt-4o")
        usage = _merge_usage(usage, extra_usage)
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

    _subject = config.get('subject', '').strip()
    _grade = config.get('grade', '').strip()
    if not _subject or not _grade:
        from flask import current_app
        current_app.logger.warning(
            f"Assignment-from-lesson requested without subject/grade: subject={_subject!r}, grade={_grade!r}")

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

        subject_boundary = _build_subject_boundary_prompt(
            config.get('subject', ''), config.get('grade', ''))

        prompt = f"""You are an expert teacher creating an assessment/assignment based on a lesson plan.
{subject_boundary}
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
{_build_question_count_instruction(config)}

Create a complete, ready-to-use assignment that:
1. Directly assesses the lesson objectives
2. Uses the vocabulary and key concepts from the lesson
3. Aligns with the essential questions
4. Is appropriate for grade {config.get('grade', '7')} students

CRITICAL REQUIREMENTS:
- THE ASSIGNMENT MUST BE 100% SELF-CONTAINED. Every resource referenced in the instructions (tables, charts, data sets, reading passages, maps, diagrams, timelines, primary sources) MUST be fully included in the assignment JSON. NEVER tell students to "complete the data table" or "analyze the chart" without providing the actual table data or chart data in the question object. If a question references a table, include "expected_data" with headers and pre-filled data. If it references a reading passage, include the full passage text in the question field.
- For data_table questions: ALWAYS include "column_headers" (array of header strings), "row_labels" (array of row labels), and "expected_data" (2D array with ALL correct numeric/text values — NEVER leave cells empty or use placeholders). For calculation tables where some columns are GIVEN and others are for the student to CALCULATE, include "editable_columns" (array of 0-based column indices the student fills in). Given columns will be pre-filled for the student.
- CRITICAL: NEVER put table data as plain text or markdown pipes (| x | y |) inside the "question" string. If a question involves a table, use question_type "data_table" with structured data fields. Tables rendered as text are unreadable.
- For Math: Use REAL numbers and actual problems (e.g., "Solve: 3/4 + 1/2 = ?"), not placeholders
- All questions must be answerable based on the lesson content
- Include clear, specific answer keys
- Word problems should use realistic scenarios (shopping, cooking, sports) not fictional games or apps
- Avoid vague or overly complex language for the grade level
- NEVER use vague instructions like "analyze the data" without providing the data inline
- For math/computation questions: SELF-CHECK that all given numeric values are consistent. If a problem states theorem values (e.g., tangent squared = external times whole), verify the numbers satisfy the equation BEFORE including the question. Never give more numeric values than needed to solve the problem (over-determined systems confuse students).
- Word problems must clearly map to a single geometric/algebraic setup. Avoid mixing 2D circle theorems with 3D physical scenarios (towers, cables) unless the mapping is explicit and unambiguous.
- Every question must be solvable with ONLY the given information — no hidden assumptions or missing data required.
- For ELA/reading questions: If a question asks students to analyze, cite, or refer to a passage/text/excerpt, the FULL passage MUST be included in the "question" field. NEVER say "according to the passage" or "refer to the text" without embedding the actual passage text before the question. Quotations longer than one sentence must include attribution (author or source).
- For science questions: Use ONE consistent unit system (metric or imperial) per question — do NOT mix systems unless the question is explicitly about unit conversion. All values must be physically plausible (no negative mass, no temperatures below absolute zero, no pH outside 0-14, no percentages above 100% for concentrations/efficiency).

QUESTION TYPE GUIDANCE:
- For most questions, DO NOT set question_type — the system assigns it automatically from your text and structure.
- Write geometry dimensions clearly in question text: "Find the area of a triangle with base 8 cm and height 5 cm"
- Write equations clearly: "Graph y = 2x + 1 on the coordinate plane"
- For multiple choice, include "options" array. For matching, include "terms" and "definitions".
- For data_table: ONLY use when students must FILL IN values. Include "column_headers", "row_labels", "expected_data" (2D array with ALL correct values — NEVER leave cells empty). For calculation tables where some columns are GIVEN data and others are for the student to CALCULATE, also include "editable_columns" (array of column indices the student fills in). Columns NOT in editable_columns will be pre-filled for the student.
- ONLY set question_type explicitly for these complex types that need structured data:
  data_table (include headers, row_labels, expected_data, editable_columns),
  box_plot (include data array), dot_plot (include data),
  stem_and_leaf (include data), bar_chart (include chart_data),
  transformations (include original_vertices, transformation_type, transform_params),
  fraction_model (include model_type, denominator, correct_numerator),
  probability_tree, tape_diagram, venn_diagram,
  protractor (include mode, target_angle),
  multiselect (include options, correct indices),
  multi_part (include parts array),
  grid_match (include row_labels, column_labels, correct matrix),
  inline_dropdown (include dropdowns array)
- Students CANNOT draw/sketch. Use interactive components or ask them to upload a photo of handwritten work.
- NEVER say "View the graph" or "See the diagram" — the system renders visuals from data fields.

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
                    "expected_data": [[1, 2], [3, 4]],  // for data_table type — ALL cells must have real values
                    "editable_columns": [1],  // for data_table calculation tables — column indices students fill in
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

For MATH subjects:
- Include at least one "math_equation" section where students solve and write expressions
- Write geometry dimensions in text: "Find the area of a triangle with base 8 cm and height 5 cm"
- Write equations in text: "Graph y = 2x + 1 on the coordinate plane"

For ELA / READING subjects:
- Passage-based questions MUST embed the full passage in the "question" field BEFORE the question prompt.
  Example MC question JSON:
  {{"question": "Read the following passage:\\n\\nThe morning sun crept over the rooftops, casting long shadows across the empty schoolyard. Maria clutched her notebook and hesitated at the gate. Three years in this country and the words still tangled on her tongue like knots in wet rope. But today was different. Today she had a story to tell.\\n\\nThe author uses the simile 'like knots in wet rope' to convey that Maria —", "options": ["A) is frustrated by the rainy weather", "B) struggles to express herself in English", "C) is nervous about her school assignment", "D) feels tangled in a difficult situation"], "answer": "B", "dok": 2, "points": 1}}
- For vocabulary-in-context questions, include the sentence with the target word:
  {{"question": "In the sentence 'The committee voted to ratify the new policy despite vocal opposition,' what does the word 'ratify' most likely mean?", "options": ["A) reject", "B) formally approve", "C) discuss publicly", "D) delay indefinitely"], "answer": "B", "dok": 2, "points": 1}}
- Extended response must give the source text first, then the prompt with a rubric:
  {{"question": "Read the following excerpt from Frederick Douglass's 'Narrative of the Life of Frederick Douglass':\\n\\n'I did not, when a slave, understand the deep meaning of those rude and apparently incoherent songs. I was myself within the circle; and neither saw nor heard as those without might see and hear.'\\n\\nExplain how Douglass uses contrast to develop his central idea about the experience of slavery. Use at least two pieces of textual evidence to support your analysis.", "answer": "Strong response addresses Douglass's contrast between inside/outside perspective, quotes specific language, and explains how the rhetorical strategy develops the theme of misunderstanding slavery from the outside.", "dok": 3, "points": 4}}
- For matching sections, use literary/rhetorical terms:
  {{"question": "Match each literary device to its correct definition.", "terms": ["Metaphor", "Alliteration", "Foreshadowing", "Irony"], "definitions": ["Repetition of initial consonant sounds", "A hint about future events in a story", "A comparison without using like or as", "A contrast between expectation and reality"], "answer": {{"Metaphor": "A comparison without using like or as", "Alliteration": "Repetition of initial consonant sounds", "Foreshadowing": "A hint about future events in a story", "Irony": "A contrast between expectation and reality"}}, "dok": 1, "points": 2}}

For SCIENCE subjects:
The portal has interactive visual components — use them instead of referencing diagrams/figures.
NEVER say "refer to the diagram" or "look at the figure." Use structured data fields and the system renders the visual.

- DATA TABLE (question_type: "data_table") — for lab data, measurements, classification, calculations:
  Calculation table (some columns given, student calculates others):
  {{"question": "A student measured the time for a ball to roll down ramps of different heights. Complete the data table by calculating average speed (distance ÷ time) for each trial.", "question_type": "data_table", "column_headers": ["Ramp Height (cm)", "Distance (m)", "Time (s)", "Avg Speed (m/s)"], "row_labels": ["Trial 1", "Trial 2", "Trial 3", "Trial 4"], "expected_data": [[10, 2.0, 4.0, 0.50], [20, 2.0, 2.8, 0.71], [30, 2.0, 2.3, 0.87], [40, 2.0, 2.0, 1.00]], "editable_columns": [3], "answer": "speed = distance / time", "dok": 2, "points": 3}}

  Classification table:
  {{"question": "Classify each substance as an element, compound, or mixture.", "question_type": "data_table", "column_headers": ["Substance", "Classification", "Reasoning"], "row_labels": ["Oxygen (O₂)", "Water (H₂O)", "Salt water", "Iron (Fe)"], "expected_data": [["Oxygen (O₂)", "Element", "Single type of atom"], ["Water (H₂O)", "Compound", "Two elements chemically bonded"], ["Salt water", "Mixture", "Separable by evaporation"], ["Iron (Fe)", "Element", "Single type of atom"]], "answer": "See expected_data", "dok": 2, "points": 3}}

- BAR CHART (question_type: "bar_chart") — for comparing measurements, experiment results:
  {{"question": "The bar chart shows average monthly rainfall in Jacksonville, FL. Which month had the greatest increase compared to the previous month?", "question_type": "bar_chart", "chart_data": {{"labels": ["Jan", "Feb", "Mar", "Apr", "May", "Jun"], "values": [3.3, 3.0, 3.9, 2.8, 3.6, 5.7], "title": "Average Monthly Rainfall (inches)"}}, "answer": "June (increased 2.1 inches from May)", "dok": 2, "points": 2}}

- DOT PLOT (question_type: "dot_plot") — for frequency distributions, repeated measurements:
  {{"question": "A student measured 15 leaf lengths (cm): 5, 6, 6, 7, 7, 7, 8, 8, 8, 8, 9, 9, 9, 10, 10. Create a dot plot showing the frequency of each length.", "question_type": "dot_plot", "minVal": 4, "maxVal": 11, "step": 1, "correct_dots": {{"5": 1, "6": 2, "7": 3, "8": 4, "9": 3, "10": 2}}, "answer": "Roughly normal distribution centered at 8 cm", "dok": 2, "points": 2}}

- BOX PLOT (question_type: "box_plot") — for data spread, comparing datasets:
  {{"question": "Calculate the five-number summary for each class's test scores.", "question_type": "box_plot", "data": [[65, 70, 72, 75, 78, 80, 82, 85, 88, 92], [55, 60, 68, 72, 75, 75, 80, 85, 90, 95]], "data_labels": ["Class A", "Class B"], "expected_values": {{"Class A": {{"min": 65, "q1": 72, "median": 79, "q3": 85, "max": 92}}, "Class B": {{"min": 55, "q1": 68, "median": 75, "q3": 85, "max": 95}}}}, "answer": "Class B has greater spread (range 40 vs 27) but lower median", "dok": 3, "points": 3}}

- COORDINATE PLANE (question_type: "coordinate_plane") — for plotting experimental data:
  {{"question": "A student recorded distance (m) over time (s): (0,0), (1,2), (2,4), (3,6), (4,8). Plot these points. What relationship do they show?", "question_type": "coordinate_plane", "x_range": [0, 6], "y_range": [0, 10], "points_to_plot": [[0,0], [1,2], [2,4], [3,6], [4,8]], "answer": "Linear/proportional — constant speed of 2 m/s", "dok": 2, "points": 3}}

- FUNCTION GRAPH (question_type: "function_graph") — for graphing physics equations:
  {{"question": "A ball thrown upward has height h = 20t - 5t². Graph this function. When does it reach maximum height?", "question_type": "function_graph", "x_range": [0, 5], "y_range": [0, 25], "correct_expressions": ["20x - 5x^2"], "answer": "Maximum height at t = 2 seconds (h = 20 m)", "dok": 3, "points": 3}}

- NUMBER LINE (question_type: "number_line") — for pH scale, temperature, ordering:
  {{"question": "Place these substances on the pH scale: lemon juice (pH 2), pure water (pH 7), baking soda (pH 9), stomach acid (pH 1.5), bleach (pH 13).", "question_type": "number_line", "min_val": 0, "max_val": 14, "points_to_plot": [1.5, 2, 7, 9, 13], "answer": "Stomach acid (1.5), lemon juice (2), water (7), baking soda (9), bleach (13)", "dok": 1, "points": 2}}

- VENN DIAGRAM (question_type: "venn_diagram") — for classification, comparing:
  {{"question": "Classify these characteristics as Plant Cells Only, Animal Cells Only, or Both: cell wall, cell membrane, chloroplasts, mitochondria, nucleus, large central vacuole, lysosomes, cytoplasm.", "question_type": "venn_diagram", "sets": 2, "labels": ["Plant Cells Only", "Animal Cells Only"], "mode": "element", "answer": "Plant Only: cell wall, chloroplasts, large central vacuole. Animal Only: lysosomes. Both: cell membrane, mitochondria, nucleus, cytoplasm", "dok": 2, "points": 3}}

- Experiment-based MC (describe full setup, no diagram references):
  {{"question": "A student places three identical plants in separate rooms. Plant A receives 12 hours of sunlight, Plant B receives 6 hours, and Plant C receives 0 hours. All plants receive the same water and soil. After 2 weeks, the student measures each plant's height. What is the independent variable?", "options": ["A) The height of the plants", "B) The amount of water given", "C) The number of hours of sunlight", "D) The type of plant used"], "answer": "C", "dok": 2, "points": 1}}

- Calculation with units (metric preferred for FL science):
  {{"question": "A block with a mass of 2.5 kg is pushed with a force of 10 N. Using F = ma, calculate the acceleration. Show your work.", "answer": "a = F/m = 10 N / 2.5 kg = 4 m/s²", "dok": 2, "points": 2}}

CRITICAL RULES FOR SCIENCE:
- Use ONE unit system per question (metric preferred). All values must be physically plausible.
- NEVER reference a diagram, figure, or image. Use the interactive components above instead.
- For classification → use data_table or venn_diagram
- For data analysis → use bar_chart, dot_plot, box_plot, or data_table
- For graphing relationships → use coordinate_plane or function_graph
- For ordering/scales → use number_line

For SOCIAL STUDIES / HISTORY subjects:
- Primary source questions MUST embed the source text, not reference it externally:
  {{"question": "Read the following excerpt from the Declaration of Independence (1776):\\n\\n'We hold these truths to be self-evident, that all men are created equal, that they are endowed by their Creator with certain unalienable Rights, that among these are Life, Liberty and the pursuit of Happiness. — That to secure these rights, Governments are instituted among Men, deriving their just powers from the consent of the governed.'\\n\\nBased on this excerpt, which Enlightenment idea MOST influenced the founders?", "options": ["A) Divine right of kings", "B) Social contract theory", "C) Mercantilism", "D) Manifest destiny"], "answer": "B", "dok": 2, "points": 1}}
- Cause-and-effect questions should be specific, not vague:
  {{"question": "Which event was a DIRECT cause of the United States entering World War I in 1917?", "options": ["A) The assassination of Archduke Franz Ferdinand", "B) Germany's unrestricted submarine warfare against American ships", "C) The Treaty of Versailles", "D) The formation of the League of Nations"], "answer": "B", "dok": 2, "points": 1}}
- Extended response with document analysis:
  {{"question": "Read the following quote from President Abraham Lincoln's Gettysburg Address (1863):\\n\\n'Four score and seven years ago our fathers brought forth on this continent, a new nation, conceived in Liberty, and dedicated to the proposition that all men are created equal. Now we are engaged in a great civil war, testing whether that nation, or any nation so conceived and so dedicated, can long endure.'\\n\\nExplain how Lincoln connects the founding ideals of the United States to the purpose of the Civil War. In your response, identify at least one specific founding ideal Lincoln references and explain why he believed the war was necessary to preserve it.", "answer": "Strong response identifies equality and/or liberty as founding ideals, explains Lincoln frames the Civil War as a test of whether democratic self-government can survive, and connects the 'proposition that all men are created equal' to the broader struggle over slavery and union.", "dok": 3, "points": 4}}
- Matching for key terms/events:
  {{"question": "Match each amendment to the right it protects.", "terms": ["1st Amendment", "2nd Amendment", "4th Amendment", "5th Amendment"], "definitions": ["Right to bear arms", "Freedom of speech, religion, and press", "Protection against self-incrimination", "Protection against unreasonable searches"], "answer": {{"1st Amendment": "Freedom of speech, religion, and press", "2nd Amendment": "Right to bear arms", "4th Amendment": "Protection against unreasonable searches", "5th Amendment": "Protection against self-incrimination"}}, "dok": 1, "points": 2}}

For GEOGRAPHY subjects:
- Include a "coordinates" section for map/location questions
- Location-based questions should test real places with coordinates:
  {{"question": "What is the capital city located nearest to the coordinates 30.4°N, 84.3°W?", "answer": "Tallahassee, Florida", "dok": 1, "points": 1}}
- Map analysis with data_table for comparison:
  {{"question": "Complete the table comparing physical features of Florida's five geographic regions.", "question_type": "data_table", "column_headers": ["Region", "Major Landform", "Elevation Range", "Key Water Feature"], "row_labels": ["Northwest", "Northeast", "Central", "Southwest", "Southeast"], "expected_data": [["Northwest", "Rolling hills", "50-100 m", "Apalachicola River"], ["Northeast", "Coastal plains", "0-30 m", "St. Johns River"], ["Central", "Lake region", "20-50 m", "Lake Okeechobee"], ["Southwest", "Low coastal plain", "0-15 m", "Everglades"], ["Southeast", "Coastal ridge", "0-5 m", "Biscayne Bay"]], "answer": "Students identify correct landforms, elevation ranges, and water features for each region", "dok": 2, "points": 3}}
{f'''
TEACHER ADDITIONAL REQUIREMENTS (MUST FOLLOW — every question/activity must reflect these):
{config.get('requirements', '').strip()}
''' if config.get('requirements', '').strip() else ''}
{f'''
TEACHER'S ADDITIONAL INSTRUCTIONS (MUST FOLLOW):
{config.get('globalAINotes', '')}
''' if config.get('globalAINotes') else ''}
Make the questions specific to the lesson content. Include a variety of question types appropriate for the assignment type.

"""

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
        target_q = config.get('totalQuestions', 10)
        assignment, extra_usage = _post_process_assignment(
            assignment, target_q, target_total_points=100,
            subject=config.get('subject'), grade=config.get('grade'))
        # Embed context for portal grading (so AI grading has full 18-factor access)
        assignment['grade_level'] = config.get('grade', config.get('grade_level', '7'))
        assignment['subject'] = config.get('subject', 'General')
        usage = _extract_usage(completion, "gpt-4o")
        usage = _merge_usage(usage, extra_usage)
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

                # Question text — detect and render inline markdown tables
                pts_text = f" ({q_points} pts)" if q_points else ""
                table_parts = _split_markdown_table(q_text)
                if table_parts:
                    # Text before table
                    before_text = table_parts['before'].strip()
                    combined_before = f"<b>Question {q_number}:</b> {before_text}{pts_text}" if before_text else f"<b>Question {q_number}:</b>{pts_text}"
                    story.append(Paragraph(combined_before, normal_style))
                    story.append(Spacer(1, 0.05*inch))
                    # Render the table
                    md_table = table_parts['table']
                    t_data = [md_table['headers']] + md_table['rows']
                    col_count = len(md_table['headers'])
                    col_w = min(1.2*inch, (6.5*inch) / max(col_count, 1))
                    from reportlab.lib import colors as rl_colors
                    tbl = Table(t_data, colWidths=[col_w]*col_count)
                    tbl.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), rl_colors.Color(0.9, 0.9, 0.95)),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, -1), 9),
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('GRID', (0, 0), (-1, -1), 0.5, rl_colors.Color(0.6, 0.6, 0.6)),
                        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                        ('TOPPADDING', (0, 0), (-1, -1), 4),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                    ]))
                    story.append(tbl)
                    # Text after table
                    if table_parts.get('after', '').strip():
                        story.append(Paragraph(table_parts['after'].strip(), normal_style))
                    story.append(Spacer(1, 0.05*inch))
                else:
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

    _subject = config.get('subject', '').strip()
    _grade = config.get('grade', '').strip()
    if not _subject or not _grade:
        from flask import current_app
        current_app.logger.warning(
            f"Assessment requested without subject/grade: subject={_subject!r}, grade={_grade!r}")

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
- Math example: "What is the value of 3² + 4²?"
- ELA example: "What is the definition of a metaphor?"
- Science example: "What is the chemical symbol for water?"
- Social Studies example: "What year did the Civil War begin?"

DOK 2 - Skills & Concepts:
- Compare, contrast, classify, organize
- Make observations, collect data
- Explain relationships, cause/effect
- Math example: "Compare the slopes of y = 2x + 1 and y = 3x - 4. Which line is steeper?"
- ELA example: "How does the author's use of dialogue in paragraph 3 reveal the character's motivation?"
- Science example: "Based on the data table, describe the relationship between ramp height and average speed."
- Social Studies example: "Compare the economies of the North and South before the Civil War."

DOK 3 - Strategic Thinking:
- Analyze, evaluate, synthesize
- Draw conclusions, cite evidence
- Develop a logical argument
- Math example: "A store offers 20% off plus an additional 10% at checkout. A customer claims this is the same as 30% off. Use mathematics to prove or disprove this claim."
- ELA example: "Using evidence from the text, analyze how the author's word choice creates a tone of urgency in the final paragraph."
- Science example: "Design an experiment to test whether salt concentration affects the boiling point of water. Identify your variables and explain your procedure."
- Social Studies example: "Using evidence from both documents, explain how economic differences contributed to sectional tensions leading to the Civil War."

DOK 4 - Extended Thinking:
- Design, create, connect across content
- Research, investigate over time
- Apply concepts to new situations
- Math example: "Design a budget for a school fundraiser that must raise at least $500. Include revenue projections, expenses, and a break-even analysis with supporting calculations."
- ELA example: "Write an argumentative essay evaluating whether social media has a net positive or negative effect on teen literacy. Cite at least three sources."
- Science example: "Propose a solution to reduce nutrient runoff in Florida's waterways. Explain the science behind your solution and predict its environmental impact."
- Social Studies example: "Analyze how Civil War-era economic patterns continue to influence regional differences in the United States today. Support your argument with historical and modern evidence."
"""

        # Question type instructions
        question_type_instructions = """
QUESTION TYPE GUIDANCE:
- For most questions, DO NOT set question_type — the system assigns it from your text and structure.
- Include "options" for multiple choice, "terms"/"definitions" for matching.
- Write geometry dimensions clearly in text: "Find the area of a triangle with base 8 cm and height 5 cm"
- Write equations clearly: "Graph y = 2x + 1 on the coordinate plane"
- ONLY set question_type explicitly for complex types needing structured data:
  data_table (include column_headers, row_labels, expected_data with ALL values, editable_columns for calculation tables),
  box_plot (include data), dot_plot (include data), stem_and_leaf (include data),
  bar_chart (include chart_data), transformations, fraction_model, probability_tree,
  tape_diagram, venn_diagram, protractor,
  multiselect (include options + correct indices array),
  multi_part (include parts array with label, question_type, question, options, answer),
  grid_match (include row_labels, column_labels, correct 2D array),
  inline_dropdown (include dropdowns array with options + correct index)
- Every question MUST include: "dok" (1-4), "standard" (code), "points", and answer.
"""

        # Build subject-specific question examples
        subject_lower = config.get('subject', '').lower()
        subject_question_examples = ""
        if any(kw in subject_lower for kw in ['ela', 'english', 'reading', 'language arts', 'literature', 'writing']):
            subject_question_examples = """
SUBJECT-SPECIFIC QUESTION EXAMPLES (ELA/Reading — follow these patterns):

Passage-based MC (MUST embed the full passage):
{"question": "Read the following passage:\\n\\nThe morning sun crept over the rooftops, casting long shadows across the empty schoolyard. Maria clutched her notebook and hesitated at the gate. Three years in this country and the words still tangled on her tongue like knots in wet rope. But today was different. Today she had a story to tell.\\n\\nThe author uses the simile 'like knots in wet rope' to convey that Maria —", "options": ["A) is frustrated by the rainy weather", "B) struggles to express herself in English", "C) is nervous about her school assignment", "D) feels tangled in a difficult situation"], "answer": "B", "dok": 2, "points": 1}

Vocabulary in context:
{"question": "In the sentence 'The committee voted to ratify the new policy despite vocal opposition,' what does 'ratify' most likely mean?", "options": ["A) reject", "B) formally approve", "C) discuss publicly", "D) delay indefinitely"], "answer": "B", "dok": 2, "points": 1}

Extended response with source text:
{"question": "Read the following excerpt from Frederick Douglass's 'Narrative of the Life of Frederick Douglass':\\n\\n'I did not, when a slave, understand the deep meaning of those rude and apparently incoherent songs. I was myself within the circle; and neither saw nor heard as those without might see and hear.'\\n\\nExplain how Douglass uses contrast to develop his central idea about the experience of slavery. Use at least two pieces of textual evidence.", "answer": "Strong response addresses inside/outside perspective contrast, quotes specific language, explains how the strategy develops the theme.", "dok": 3, "points": 4}

Matching (literary/rhetorical terms):
{"question": "Match each literary device to its definition.", "terms": ["Metaphor", "Alliteration", "Foreshadowing", "Irony"], "definitions": ["Repetition of initial consonant sounds", "A hint about future events", "A comparison without like or as", "A contrast between expectation and reality"], "dok": 1, "points": 2}

CRITICAL: EVERY passage-based question must have the passage text INSIDE the question field. Never say 'according to the passage' without providing it.
"""
        elif any(kw in subject_lower for kw in ['science', 'biology', 'chemistry', 'physics', 'earth', 'environmental']):
            subject_question_examples = """
SUBJECT-SPECIFIC QUESTION EXAMPLES (Science — follow these patterns):

The portal has interactive visual components you MUST use instead of asking students to "look at a diagram."
NEVER reference a figure, diagram, or image that isn't provided as structured data. Use the components below.

=== DATA TABLE (question_type: "data_table") ===
Use for: lab data, experiment results, classification, measurements, calculations.
Students see headers and row labels and fill in the values.

Lab data collection (calculation table — given columns pre-filled, student calculates others):
{"question": "A student measured the time it takes for a ball to roll down ramps of different heights. Complete the data table by calculating the average speed (distance ÷ time) for each trial.", "question_type": "data_table", "column_headers": ["Ramp Height (cm)", "Distance (m)", "Time (s)", "Avg Speed (m/s)"], "row_labels": ["Trial 1", "Trial 2", "Trial 3", "Trial 4"], "expected_data": [[10, 2.0, 4.0, 0.50], [20, 2.0, 2.8, 0.71], [30, 2.0, 2.3, 0.87], [40, 2.0, 2.0, 1.00]], "editable_columns": [3], "answer": "Students calculate speed = distance / time for each trial", "dok": 2, "points": 3}

Classification table:
{"question": "Classify each substance as an element, compound, or mixture by completing the table.", "question_type": "data_table", "column_headers": ["Substance", "Classification", "Reasoning"], "row_labels": ["Oxygen (O₂)", "Water (H₂O)", "Salt water", "Iron (Fe)", "Carbon dioxide (CO₂)"], "expected_data": [["Oxygen (O₂)", "Element", "Single type of atom"], ["Water (H₂O)", "Compound", "Two elements chemically bonded"], ["Salt water", "Mixture", "Can be separated by evaporation"], ["Iron (Fe)", "Element", "Single type of atom"], ["Carbon dioxide (CO₂)", "Compound", "Two elements chemically bonded"]], "answer": "See expected_data", "dok": 2, "points": 3}

=== BAR CHART (question_type: "bar_chart") ===
Use for: comparing measurements, experiment results, population data, rainfall, temperatures.
The chart displays automatically from the data — students answer a text question about it.

{"question": "The bar chart shows the average monthly rainfall in Jacksonville, FL from January to June. Which month had the greatest increase in rainfall compared to the previous month? Explain your reasoning.", "question_type": "bar_chart", "chart_data": {"labels": ["Jan", "Feb", "Mar", "Apr", "May", "Jun"], "values": [3.3, 3.0, 3.9, 2.8, 3.6, 5.7], "title": "Average Monthly Rainfall (inches)"}, "answer": "June — increased by 2.1 inches from May (5.7 - 3.6 = 2.1), the largest single-month increase", "dok": 2, "points": 2}

=== DOT PLOT (question_type: "dot_plot") ===
Use for: frequency distributions, repeated measurements, class survey data.
Students click to place dots above values on a number line.

{"question": "A student measured the length of 15 leaves from a tree (in cm): 5, 6, 6, 7, 7, 7, 8, 8, 8, 8, 9, 9, 9, 10, 10. Create a dot plot showing the frequency of each leaf length.", "question_type": "dot_plot", "minVal": 4, "maxVal": 11, "step": 1, "correct_dots": {"5": 1, "6": 2, "7": 3, "8": 4, "9": 3, "10": 2}, "answer": "Dot plot shows a roughly normal distribution centered at 8 cm", "dok": 2, "points": 2}

=== BOX PLOT (question_type: "box_plot") ===
Use for: data spread analysis, comparing datasets, identifying outliers.
Students fill in the five-number summary values.

{"question": "The following data shows test scores for two classes. Calculate the five-number summary (min, Q1, median, Q3, max) for each class and compare their distributions.", "question_type": "box_plot", "data": [[65, 70, 72, 75, 78, 80, 82, 85, 88, 92], [55, 60, 68, 72, 75, 75, 80, 85, 90, 95]], "data_labels": ["Class A", "Class B"], "expected_values": {"Class A": {"min": 65, "q1": 72, "median": 79, "q3": 85, "max": 92}, "Class B": {"min": 55, "q1": 68, "median": 75, "q3": 85, "max": 95}}, "answer": "Class B has greater spread (range 40 vs 27) but lower median (75 vs 79)", "dok": 3, "points": 3}

=== COORDINATE PLANE (question_type: "coordinate_plane") ===
Use for: plotting experimental data points, graphing relationships, distance/position.
Students click to place points on an x-y grid.

{"question": "A student recorded the distance (m) a toy car traveled over time (s): (0,0), (1,2), (2,4), (3,6), (4,8). Plot these data points on the coordinate plane. What type of relationship do the data show?", "question_type": "coordinate_plane", "x_range": [0, 6], "y_range": [0, 10], "points_to_plot": [[0,0], [1,2], [2,4], [3,6], [4,8]], "answer": "Linear/proportional relationship — distance increases by 2 m every second (constant speed of 2 m/s)", "dok": 2, "points": 3}

=== FUNCTION GRAPH (question_type: "function_graph") ===
Use for: graphing physics equations, linear relationships, exponential growth/decay.
Students type equations and see them graphed live.

{"question": "A ball is thrown upward with an initial velocity of 20 m/s. Its height (in meters) over time can be modeled by h = 20t - 5t². Graph this function. At what time does the ball reach its maximum height?", "question_type": "function_graph", "x_range": [0, 5], "y_range": [0, 25], "correct_expressions": ["20x - 5x^2"], "answer": "Maximum height at t = 2 seconds (h = 20 meters)", "dok": 3, "points": 3}

=== NUMBER LINE (question_type: "number_line") ===
Use for: pH scale, temperature, timelines, ordering values.
Students click to place points on a linear scale.

{"question": "Place the following substances on the pH scale based on their approximate pH values: lemon juice (pH 2), pure water (pH 7), baking soda (pH 9), stomach acid (pH 1.5), bleach (pH 13).", "question_type": "number_line", "min_val": 0, "max_val": 14, "points_to_plot": [1.5, 2, 7, 9, 13], "answer": "Stomach acid (1.5), lemon juice (2), pure water (7), baking soda (9), bleach (13)", "dok": 1, "points": 2}

=== VENN DIAGRAM (question_type: "venn_diagram") ===
Use for: classification, comparing organisms/elements/processes, set relationships.
Students fill in values or labels in overlapping regions.

{"question": "Use the Venn diagram to classify the following characteristics as belonging to Plant Cells Only, Animal Cells Only, or Both: cell wall, cell membrane, chloroplasts, mitochondria, nucleus, large central vacuole, lysosomes, cytoplasm.", "question_type": "venn_diagram", "sets": 2, "labels": ["Plant Cells Only", "Animal Cells Only"], "mode": "element", "answer": "Plant Only: cell wall, chloroplasts, large central vacuole. Animal Only: lysosomes. Both: cell membrane, mitochondria, nucleus, cytoplasm", "dok": 2, "points": 3}

=== STANDARD TYPES (no special question_type needed) ===

Experiment-based MC (describe the full setup):
{"question": "A student places three identical plants in separate rooms. Plant A receives 12 hours of sunlight, Plant B receives 6 hours, and Plant C receives 0 hours. All plants receive the same amount of water and soil. After 2 weeks, the student measures the height of each plant. What is the independent variable in this experiment?", "options": ["A) The height of the plants", "B) The amount of water given", "C) The number of hours of sunlight", "D) The type of plant used"], "answer": "C", "dok": 2, "points": 1}

Calculation with units (use metric, show work):
{"question": "A block with a mass of 2.5 kg is pushed with a force of 10 N across a frictionless surface. Using Newton's second law (F = ma), calculate the acceleration of the block. Show your work.", "answer": "a = F/m = 10 N / 2.5 kg = 4 m/s²", "dok": 2, "points": 2}

Vocabulary matching (science terms):
{"question": "Match each term to its correct definition.", "terms": ["Independent variable", "Dependent variable", "Control group", "Hypothesis"], "definitions": ["The group that does not receive the experimental treatment", "The factor that is measured in an experiment", "A testable prediction about the outcome", "The factor that the scientist changes on purpose"], "answer": {"Independent variable": "The factor that the scientist changes on purpose", "Dependent variable": "The factor that is measured in an experiment", "Control group": "The group that does not receive the experimental treatment", "Hypothesis": "A testable prediction about the outcome"}, "dok": 1, "points": 2}

CRITICAL RULES FOR SCIENCE QUESTIONS:
- Use ONE consistent unit system per question (metric preferred for FL science). All values must be physically plausible.
- NEVER reference a diagram, figure, image, or illustration. Use the interactive components above instead.
- For classification tasks, use data_table or venn_diagram — not "draw a chart" or "create a diagram."
- For data analysis, ALWAYS include the actual data using bar_chart, dot_plot, box_plot, or data_table.
- For graphing relationships, use coordinate_plane (plotting points) or function_graph (typing equations).
- For ordering/scales, use number_line.
"""
        elif any(kw in subject_lower for kw in ['social studies', 'history', 'civics', 'government', 'economics', 'world history', 'us history', 'american history']):
            subject_question_examples = """
SUBJECT-SPECIFIC QUESTION EXAMPLES (Social Studies/History — follow these patterns):

Primary source MC (MUST embed the source text):
{"question": "Read the following excerpt from the Declaration of Independence (1776):\\n\\n'We hold these truths to be self-evident, that all men are created equal, that they are endowed by their Creator with certain unalienable Rights, that among these are Life, Liberty and the pursuit of Happiness. — That to secure these rights, Governments are instituted among Men, deriving their just powers from the consent of the governed.'\\n\\nWhich Enlightenment idea MOST influenced the founders?", "options": ["A) Divine right of kings", "B) Social contract theory", "C) Mercantilism", "D) Manifest destiny"], "answer": "B", "dok": 2, "points": 1}

Cause-and-effect MC (be specific, not vague):
{"question": "Which event was a DIRECT cause of the United States entering World War I in 1917?", "options": ["A) The assassination of Archduke Franz Ferdinand", "B) Germany's unrestricted submarine warfare against American ships", "C) The Treaty of Versailles", "D) The formation of the League of Nations"], "answer": "B", "dok": 2, "points": 1}

Document-based extended response:
{"question": "Read the following quote from Lincoln's Gettysburg Address (1863):\\n\\n'Four score and seven years ago our fathers brought forth on this continent, a new nation, conceived in Liberty, and dedicated to the proposition that all men are created equal. Now we are engaged in a great civil war, testing whether that nation, or any nation so conceived and so dedicated, can long endure.'\\n\\nExplain how Lincoln connects the founding ideals to the purpose of the Civil War. Identify at least one founding ideal and explain why Lincoln believed the war was necessary to preserve it.", "answer": "Strong response identifies equality/liberty as founding ideals, explains Lincoln frames the war as a test of democratic self-government, connects 'all men are created equal' to the struggle over slavery.", "dok": 3, "points": 4}

Amendment matching:
{"question": "Match each amendment to the right it protects.", "terms": ["1st Amendment", "2nd Amendment", "4th Amendment", "5th Amendment"], "definitions": ["Right to bear arms", "Freedom of speech, religion, and press", "Protection against self-incrimination", "Protection against unreasonable searches"], "dok": 1, "points": 2}

CRITICAL: Primary source and document-based questions MUST embed the full source text in the question field. Never reference a document that isn't provided inline.
"""
        elif any(kw in subject_lower for kw in ['geography', 'world geography']):
            subject_question_examples = """
SUBJECT-SPECIFIC QUESTION EXAMPLES (Geography — follow these patterns):

Location/coordinates question:
{"question": "What is the capital city located nearest to the coordinates 30.4°N, 84.3°W?", "answer": "Tallahassee, Florida", "dok": 1, "points": 1}

Region comparison data table:
{"question": "Complete the table comparing physical features of Florida's geographic regions.", "question_type": "data_table", "column_headers": ["Region", "Major Landform", "Elevation Range", "Key Water Feature"], "row_labels": ["Northwest", "Central", "Southeast"], "expected_data": [["Northwest", "Rolling hills", "50-100 m", "Apalachicola River"], ["Central", "Lake region", "20-50 m", "Lake Okeechobee"], ["Southeast", "Coastal ridge", "0-5 m", "Biscayne Bay"]], "answer": "Students identify correct landforms, elevations, and water features", "dok": 2, "points": 3}

Map analysis MC:
{"question": "A geographer is studying population density along Florida's coast. Which factor BEST explains why population density is higher on the southeastern coast than the northwestern coast?", "options": ["A) The southeastern coast has more rainfall", "B) The southeastern coast has warmer average winter temperatures and established tourism infrastructure", "C) The northwestern coast has more hurricanes", "D) The southeastern coast was settled first by European colonists"], "answer": "B", "dok": 3, "points": 1}

CRITICAL: Include real geographic data and coordinates. Use the portal's interactive coordinate_plane or data_table components rather than asking students to draw maps.
"""
        # For math or unrecognized subjects, no extra examples needed (math already has them in question_type_instructions)

        input_standard_codes = [s.get('code', '') for s in standards if s.get('code')]
        subject_boundary = _build_subject_boundary_prompt(
            config.get('subject', ''), config.get('grade', ''), input_standard_codes)

        prompt = f"""You are an expert assessment developer creating a standards-aligned {assessment_type} for grade {config.get('grade', '8')} {config.get('subject', 'students')}.
{subject_boundary}
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
{subject_question_examples}
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
12. NEVER generate project, activity, or tool-based prompts. Students complete this assessment entirely within the online portal. Do NOT ask students to use external tools (Canva, Google Slides, PowerPoint, Desmos, GeoGebra, etc.), create physical products (posters, infographics, models, presentations, brochures, dioramas), collaborate with classmates, or perform tasks that cannot be answered with text, numbers, or the portal's interactive components. Every question must be directly answerable on screen.
13. For math/computation questions: SELF-CHECK that all given numeric values are consistent. If a problem states theorem values (e.g., tangent squared = external times whole), verify the numbers satisfy the equation BEFORE including the question. Never give more numeric values than needed to solve the problem (over-determined systems confuse students).
14. Word problems must clearly map to a single geometric/algebraic setup. Avoid mixing 2D circle theorems with 3D physical scenarios (towers, cables) unless the mapping is explicit and unambiguous.
15. Every question must be solvable with ONLY the given information — no hidden assumptions or missing data required.
16. For ELA/reading questions: If a question asks students to analyze, cite, or refer to a passage/text/excerpt, the FULL passage MUST be included in the "question" field. NEVER say "according to the passage" or "refer to the text" without embedding the actual passage text before the question. Quotations longer than one sentence must include attribution (author or source).
17. For science questions: Use ONE consistent unit system (metric or imperial) per question — do NOT mix systems unless the question is explicitly about unit conversion. All values must be physically plausible (no negative mass, no temperatures below absolute zero, no pH outside 0-14, no percentages above 100% for concentrations/efficiency). If referencing a figure, diagram, or lab setup, include the data in structured fields — never reference a visual that doesn't exist.

SECTION CATEGORIES TO INCLUDE:
{_build_section_categories_prompt(section_categories, config.get('subject', ''))}

{f"TEACHER'S ADDITIONAL REQUIREMENTS (MUST FOLLOW — every question must reflect these):" + chr(10) + config.get('requirements', '').strip() + chr(10) if config.get('requirements', '').strip() else ''}
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
        assessment, _ = _post_process_assignment(
            assessment, target_total_points=total_points,
            subject=config.get('subject'), grade=config.get('grade'),
            valid_standard_codes=input_standard_codes)

        # Collect any quality warnings attached to questions
        quality_warnings = []
        for sIdx, section in enumerate(assessment.get('sections', [])):
            for qIdx, q in enumerate(section.get('questions', [])):
                if q.get('warning'):
                    quality_warnings.append({
                        "section_index": sIdx,
                        "question_index": qIdx,
                        "issue": q['warning'],
                        "severity": q.get('warning_severity', 'warning'),
                    })

        # Add metadata for portal grading context
        assessment['generated_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
        assessment['teacher'] = config.get('teacher_name', '')
        assessment['grade_level'] = config.get('grade', '8')
        assessment['subject'] = config.get('subject', 'General')

        usage = _extract_usage(completion, "gpt-4o")
        _record_planner_cost(usage)
        result = {"assessment": assessment, "method": "AI", "usage": usage}
        if quality_warnings:
            result["warnings"] = quality_warnings
        return jsonify(result)

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


@planner_bp.route('/api/regenerate-questions', methods=['POST'])
def regenerate_questions():
    """Regenerate specific questions in an assessment/assignment using AI.

    Expects:
      questions_to_replace: [{section_index, question_index, question_type, points, dok, standard}, ...]
      existing_questions: [str, ...] — question texts to avoid duplicating
      config: {grade, subject, globalAINotes}
    Returns:
      replacements: [{section_index, question_index, question: {...}}, ...]
      usage: cost/token info
    """
    data = request.json
    questions_to_replace = data.get('questions_to_replace', [])
    existing_questions = data.get('existing_questions', [])
    config = data.get('config', {})

    if not questions_to_replace:
        return jsonify({"error": "No questions specified for regeneration"}), 400

    _subject = config.get('subject', '').strip()
    _grade = config.get('grade', config.get('grade_level', '')).strip()
    if not _subject or not _grade:
        from flask import current_app
        current_app.logger.warning(
            f"Regenerate requested without subject/grade: subject={_subject!r}, grade={_grade!r}")

    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        grade = config.get('grade', '')
        subject = config.get('subject', '')
        global_notes = config.get('globalAINotes', '')

        # Build replacement specs
        specs = []
        for i, q in enumerate(questions_to_replace):
            spec = f"{i + 1}. Type: {q.get('question_type', 'short_answer')}"
            if q.get('points'):
                spec += f", Points: {q['points']}"
            if q.get('dok'):
                spec += f", DOK level: {q['dok']}"
            if q.get('standard'):
                spec += f", Standard: {q['standard']}"
            specs.append(spec)

        existing_list = "\n".join(f"- {q}" for q in existing_questions[:50]) if existing_questions else "None"

        regen_standard_codes = list(set(
            q.get('standard', '') for q in questions_to_replace if q.get('standard')
        ))
        subject_boundary = _build_subject_boundary_prompt(subject, grade, regen_standard_codes)

        prompt = f"""Generate {len(questions_to_replace)} replacement question(s) for a grade {grade} {subject} assessment.
{subject_boundary}
Each replacement must match the specified type, DOK level, and point value exactly.
DO NOT duplicate any of these existing questions:
{existing_list}

{f'Teacher instructions: {global_notes}' if global_notes else ''}
{f"Teacher's additional requirements (MUST reflect in every question): {config.get('requirements', '').strip()}" if config.get('requirements', '').strip() else ''}

Replacement specifications:
{chr(10).join(specs)}

Return a JSON object with a "questions" array. Each element must include:
- "question": the question text
- "answer": the correct answer
- "points": point value
- "question_type": exact type as specified
- "dok": DOK level as specified
- "number": sequential number starting from 1

For multiple_choice questions, include an "options" array of 4 strings (A) through D) format.
For true_false questions, answer must be "True" or "False".
For matching questions, include "terms" and "definitions" arrays.
For math questions, include step-by-step solution in the answer.

Make questions grade-appropriate, clear, and assessable by AI grading systems."""

        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are an expert assessment developer. Generate high-quality assessment questions that are clear, unambiguous, and appropriate for AI-based grading. Always return valid JSON."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.8,
        )

        content = completion.choices[0].message.content
        result = json.loads(content)
        new_questions = result.get('questions', [])

        # Post-process each replacement through the standard pipeline
        replacements = []
        for i, q_spec in enumerate(questions_to_replace):
            if i < len(new_questions):
                new_q = new_questions[i]
                # Preserve DOK and standard from original spec
                new_q['dok'] = q_spec.get('dok', new_q.get('dok', 1))
                new_q['standard'] = q_spec.get('standard', new_q.get('standard', ''))
                # Run through classification and hydration pipeline
                _classify_question_type(new_q)
                _hydrate_question(new_q)
                _validate_question(new_q)
                replacements.append({
                    "section_index": q_spec['section_index'],
                    "question_index": q_spec['question_index'],
                    "question": new_q,
                })

        usage = _extract_usage(completion, "gpt-4o")
        _record_planner_cost(usage)

        return jsonify({"replacements": replacements, "usage": usage})

    except Exception as e:
        print(f"Regenerate questions error: {e}")
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
