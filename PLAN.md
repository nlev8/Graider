# Deterministic Assignment Generation Pipeline Refactor

## Context

The current assignment generation pipeline relies on GPT-4o to make structural decisions (question_type, visual parameters, field population) that it frequently gets wrong — empty data tables, hardcoded geometry dimensions, wrong question types, ignored question counts. We've accumulated 7+ sequential post-processing fixup functions that patch AI mistakes reactively. This refactor separates content generation (what AI is good at) from structure/rendering decisions (what deterministic code should handle).

**Single file change:** `backend/routes/planner_routes.py`

---

## Architecture: 4-Phase Pipeline

Replace the current 7 chained post-processing calls at 5 call sites with one unified function:

```python
def _post_process_assignment(assignment, target_question_count=None):
    """Single-pass deterministic post-processing pipeline."""
    for section in assignment.get('sections', []):
        for q in section.get('questions', []):
            _classify_question_type(q, section)   # Phase 1
            _hydrate_question(q)                   # Phase 2
            _validate_question(q)                  # Phase 3
    if target_question_count:
        assignment, _ = _enforce_question_count(assignment, target_question_count)
    return assignment, None
```

---

## Step 1: Introduce `_post_process_assignment()` wrapper (consolidation only)

**What:** Create the unified function that calls the existing 7 functions. Replace all 5 call sites. Zero behavior change.

**Replace these 5 call sites** (each has ~6 lines of chained calls):
- Lines ~2109-2114 (direct assignment, variations path)
- Lines ~2142-2147 (direct assignment, main path)
- Lines ~2597-2602 (from-lesson path)
- Lines ~4108-4113 (assessment path, line added during from-lesson)
- Lines ~4135-4140 (assessment path, main)

**Each site currently looks like:**
```python
_auto_upgrade_visual_types(plan)
_auto_correct_geometry_types(plan)
_ensure_geometry_defaults(plan)
_ensure_data_table_defaults(plan)
_ensure_fast_defaults(plan)
_hydrate_math_visuals(plan)
```

**Replace with:**
```python
plan, extra_usage = _post_process_assignment(plan, target_q)
```

**New function (~30 lines, add at line ~135):**
```python
def _post_process_assignment(assignment, target_question_count=None):
    """Unified post-processing pipeline. Replaces 7 chained function calls."""
    if not assignment or not isinstance(assignment, dict):
        return assignment, None
    _auto_upgrade_visual_types(assignment)
    _auto_correct_geometry_types(assignment)
    _ensure_geometry_defaults(assignment)
    _ensure_data_table_defaults(assignment)
    _ensure_fast_defaults(assignment)
    _hydrate_math_visuals(assignment)
    extra_usage = None
    if target_question_count is not None:
        assignment, extra_usage = _enforce_question_count(assignment, target_question_count)
    return assignment, extra_usage
```

---

## Step 2: Add `_classify_question_type()` — deterministic type assignment

**What:** New function (~90 lines) that assigns `question_type` based on text analysis and structural fields. Replaces the scattered logic in `_auto_upgrade_visual_types` (line 141) and `_auto_correct_geometry_types` (line 428).

**Add at line ~140 (before current `_auto_upgrade_visual_types`):**

```python
# Types where the AI's classification is trusted (complex structural content)
_TRUSTED_AI_TYPES = frozenset({
    'data_table', 'box_plot', 'dot_plot', 'stem_and_leaf', 'bar_chart',
    'transformations', 'fraction_model', 'probability_tree',
    'tape_diagram', 'venn_diagram', 'protractor', 'angle_protractor',
    'unit_circle', 'multiselect', 'multi_part', 'grid_match',
    'inline_dropdown',
})

def _classify_question_type(q, section=None):
    """Deterministic question type classification. Assigns question_type
    based on text analysis and structural fields. Runs ONCE per question.

    Priority order:
    1. Preserve AI-specified type for trusted complex types
    2. Structural detection (options → MC, terms → matching, etc.)
    3. Geometry detection (shape + mode keywords)
    4. Graphing detection (equation patterns)
    5. Math equation detection
    6. Extended response detection
    7. Section type hint fallback
    8. Default → short_answer
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

    # Phase 7: Clear bad AI geometry type
    if ai_type in _ALL_GEOMETRY_TYPES:
        q['question_type'] = 'short_answer'
        return

    # Default
    q['question_type'] = ai_type if ai_type else 'short_answer'
```

**Wire into `_post_process_assignment`:** Add `_classify_question_type(q, section)` as the first call in the per-question loop. The existing `_auto_upgrade_visual_types` and `_auto_correct_geometry_types` become no-ops (they check `question_type` which is now already correct).

---

## Step 3: Add `_validate_question()` — schema enforcement

**What:** New function (~50 lines) that checks required fields per type and downgrades broken questions to `short_answer`.

**Add after `_classify_question_type`:**

```python
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
    # Geometry types — base requirements filled by _hydrate_question
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
```

**Wire into `_post_process_assignment`:** Add as Phase 3, after hydration.

---

## Step 4: Consolidate hydration into `_hydrate_question()`

**What:** Merge logic from `_ensure_geometry_defaults`, `_ensure_data_table_defaults`, `_ensure_fast_defaults`, and `_hydrate_math_visuals` into one dispatch function (~200 lines).

**Structure:**

```python
def _hydrate_question(q):
    """Populate rendering fields based on question_type. Deterministic — no AI calls."""
    qt = q.get('question_type', 'short_answer')

    # --- Geometry types ---
    if qt in _ALL_GEOMETRY_TYPES or qt in ('pythagorean', 'angles', 'similarity', 'trig'):
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
        # Extract points from text if not provided
        return

    # --- Number line ---
    if qt == 'number_line':
        q.setdefault('min_val', -10)
        q.setdefault('max_val', 10)
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
        q.setdefault('mode', 'measure')
        if q.get('target_angle'):
            q.setdefault('answer', str(q['target_angle']))
        return

    # --- FAST types ---
    if qt == 'multiselect':
        correct = q.get('correct', [])
        q['correct'] = [int(c) for c in correct if isinstance(c, (int, float))]
    elif qt == 'multi_part':
        for part in q.get('parts', []):
            part.setdefault('question_type', 'multiple_choice')
    elif qt == 'grid_match':
        _hydrate_grid_match(q)
    elif qt == 'inline_dropdown':
        _hydrate_inline_dropdown(q)
```

**Sub-functions** (extracted from existing code — no new logic):

- `_hydrate_geometry(q, qt)` — from `_ensure_geometry_defaults` + `_hydrate_math_visuals` geometry section + `_extract_dimensions_from_text` + `_extract_pythagorean_sides` + `_compute_geometry_answer`
- `_hydrate_data_table(q)` — from `_ensure_data_table_defaults` (field mapping, analysis detection, initial_data creation)
- `_hydrate_box_plot(q)` — from `_hydrate_math_visuals` box_plot section (5-number summary computation)
- `_hydrate_dot_plot(q)` — from `_hydrate_math_visuals` dot_plot section (frequency counting)
- `_hydrate_stem_and_leaf(q)` — from `_hydrate_math_visuals` stem_and_leaf section
- `_hydrate_transformations(q)` — from `_hydrate_math_visuals` transformations section (vertex computation)
- `_hydrate_fraction_model(q)` — from `_hydrate_math_visuals` fraction_model section
- `_hydrate_unit_circle(q)` — from `_hydrate_math_visuals` unit_circle section
- `_hydrate_grid_match(q)` — from `_ensure_fast_defaults` grid_match section
- `_hydrate_inline_dropdown(q)` — from `_ensure_fast_defaults` inline_dropdown section

---

## Step 5: Simplify AI prompts

**What:** Remove the massive visual type documentation from all 3 generation prompts. The AI no longer needs to know how to populate visual fields — just write good question text.

**Direct Assignment prompt (lines ~1828-1937):**
Remove the ~100 lines of "VISUAL/GRAPHICAL QUESTION TYPES" documentation. Replace with:

```
QUESTION TYPE GUIDANCE:
- For most questions, DO NOT set question_type — the system assigns it from your text.
- Write geometry dimensions clearly in question text: "Find the area of a triangle with base 8 cm and height 5 cm"
- Write equations clearly: "Graph y = 2x + 1 on the coordinate plane"
- ONLY set question_type explicitly for these complex types:
  data_table (include headers, row_labels, expected_data),
  box_plot (include data array), dot_plot (include data),
  stem_and_leaf (include data), bar_chart (include chart_data),
  transformations, fraction_model, probability_tree, tape_diagram,
  venn_diagram, protractor, multiselect, multi_part, grid_match,
  inline_dropdown
```

**From-Lesson prompt (lines ~2335-2584):**
Same simplification — remove the SPECIAL STEM QUESTION TYPES and VISUAL/GRAPHICAL QUESTION TYPES blocks (~200 lines). Replace with the same guidance above.

**Assessment prompt (lines ~3890-4121):**
Remove the QUESTION TYPE FORMATS section (~130 lines). Replace with simplified guidance.

---

## Step 6: Remove dead code

Delete the now-unused standalone functions:
- `_auto_upgrade_visual_types()` (lines 141-264, ~124 lines)
- `_auto_correct_geometry_types()` (lines 428-503, ~76 lines)
- `_ensure_geometry_defaults()` (lines 899-912, ~14 lines)
- `_ensure_data_table_defaults()` (lines 915-961, ~47 lines)
- `_ensure_fast_defaults()` (lines 964-1008, ~45 lines)
- `_hydrate_math_visuals()` (lines 1121-1305, ~185 lines)

**Net reduction:** ~490 lines removed, ~340 lines added = ~150 line reduction

---

## Existing functions to KEEP as-is

These are solid building blocks reused by the new pipeline:

| Function | Lines | Used by |
|---|---|---|
| `_detect_primary_shape(text)` | 333-376 | `_classify_question_type` |
| `_detect_mode(text)` | 379-386 | `_classify_question_type` |
| `_is_identification_question(text)` | 388-401 | `_classify_question_type` |
| `_infer_shape_answer(text)` | 403-425 | `_classify_question_type` |
| `_looks_like_graphing_question(text)` | 506-519 | `_classify_question_type` |
| `_extract_equations_from_text(text)` | 521-551 | `_classify_question_type`, `_hydrate_question` |
| `_extract_dimensions_from_text(q)` | 613-706 | `_hydrate_geometry` |
| `_extract_pythagorean_sides(q, text, unit)` | 708-778 | `_hydrate_geometry` |
| `_GEOMETRY_DEFAULTS` | 781-795 | `_hydrate_geometry` |
| `_compute_geometry_answer(qt, q)` | 1011-1118 | `_hydrate_geometry` |
| `_enforce_question_count()` | 820-880 | `_post_process_assignment` |
| `_count_questions()` | 812-818 | `_enforce_question_count` |
| `_build_question_count_instruction()` | 798-810 | prompt construction |
| `_build_section_categories_prompt()` | exists | prompt construction |
| `_split_markdown_table()` | 554-610 | PDF export |

---

## Implementation Order

1. **Step 1** — Wrapper consolidation (zero behavior change, mechanical refactor)
2. **Step 2** — Classifier (new function, wired in; old functions become redundant)
3. **Step 3** — Validator (additive safety net)
4. **Step 4** — Hydration consolidation (merge 4 functions into dispatch)
5. **Step 5** — Prompt simplification (reduce token usage, cleaner AI output)
6. **Step 6** — Dead code removal (cleanup)

Each step can be committed and tested independently.

---

## Verification

1. Generate a Math assignment (direct path) with 12 questions — verify exact count, geometry visuals render, function graphs work
2. Generate a Science assignment from lesson — verify data_table, box_plot render with real data
3. Generate an Assessment with FAST item types — verify multiselect, grid_match, inline_dropdown
4. Check that "analyze this table" questions become short_answer (not empty data_table)
5. Check that pythagorean questions show correct side values from question text
6. Check that angle-mode triangles render with correct proportions
7. `cd frontend && npm run build` succeeds
