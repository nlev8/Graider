# National Standards Coverage — Design Spec

## Goal

Expand standards coverage from Florida-only (9 files) to all 50 US states using Common Core (CCSS), Next Generation Science Standards (NGSS), and state-specific files. Transparent fallback when state-specific standards aren't available.

## Scope

**In scope:**
- Reorganize standards files into subdirectories by framework
- Standards mapping config (`standards_map.json`) for state→framework resolution
- CCSS standards files: Math, ELA, Social Studies (C3 Framework)
- NGSS standards file: Science
- State-specific files: TX (TEKS), VA (SOLs) — FL already exists
- Update `load_standards()` with mapping-based resolution and fallback logic
- All 50 states + DC in the frontend state selector
- Fallback notice in planner when using CCSS/NGSS instead of state-specific
- FL FAST toggle gated to Florida only (both render paths)
- All standards files at full depth: code, benchmark, DOK, topics, vocabulary, learning_targets, essential_questions, sample_assessment
- Fallback notice in assessment/lesson generation responses (not just standards listing)

**Out of scope:**
- Database-backed standards storage
- Admin UI for uploading/editing standards
- Standards for territories (PR, GU, VI, etc.)
- K-5 standards (Graider targets grades 6-12)
- Standards versioning or year tracking

## File Organization

```
backend/data/standards/
├── standards_map.json
├── ccss/
│   ├── math.json
│   ├── english-ela.json
│   └── social_studies.json      # C3 Framework (covers civics, geography, history)
├── ngss/
│   └── science.json
├── fl/
│   ├── math.json
│   ├── english-ela.json
│   ├── science.json
│   ├── social_studies.json
│   ├── civics.json
│   ├── geography.json
│   ├── us_history.json
│   ├── world_history.json
│   └── spanish.json
├── tx/
│   ├── math.json
│   ├── english-ela.json
│   ├── science.json
│   └── social_studies.json
└── va/
    ├── math.json
    ├── english-ela.json
    ├── science.json
    └── social_studies.json
```

Existing `backend/data/standards_fl_*.json` files are migrated to `standards/fl/` with the `standards_fl_` prefix dropped. Legacy flat file path checked as fallback during transition (using lowercase state code: `standards_fl_*`, not `standards_FL_*`).

## Standards Map Config

`backend/data/standards/standards_map.json`:

```json
{
  "states": {
    "AL": { "name": "Alabama", "framework": "ccss" },
    "AK": { "name": "Alaska", "framework": "ccss", "note": "Has own standards; CCSS used as approximation" },
    "AZ": { "name": "Arizona", "framework": "ccss" },
    "AR": { "name": "Arkansas", "framework": "ccss" },
    "CA": { "name": "California", "framework": "ccss" },
    "CO": { "name": "Colorado", "framework": "ccss" },
    "CT": { "name": "Connecticut", "framework": "ccss" },
    "DE": { "name": "Delaware", "framework": "ccss" },
    "FL": { "name": "Florida", "framework": "fl" },
    "GA": { "name": "Georgia", "framework": "ccss" },
    "HI": { "name": "Hawaii", "framework": "ccss" },
    "ID": { "name": "Idaho", "framework": "ccss" },
    "IL": { "name": "Illinois", "framework": "ccss" },
    "IN": { "name": "Indiana", "framework": "ccss", "note": "Has own standards; CCSS used as approximation" },
    "IA": { "name": "Iowa", "framework": "ccss" },
    "KS": { "name": "Kansas", "framework": "ccss" },
    "KY": { "name": "Kentucky", "framework": "ccss" },
    "LA": { "name": "Louisiana", "framework": "ccss" },
    "ME": { "name": "Maine", "framework": "ccss" },
    "MD": { "name": "Maryland", "framework": "ccss" },
    "MA": { "name": "Massachusetts", "framework": "ccss" },
    "MI": { "name": "Michigan", "framework": "ccss" },
    "MN": { "name": "Minnesota", "framework": "ccss", "note": "Adopted CCSS ELA only; CCSS Math used as approximation" },
    "MS": { "name": "Mississippi", "framework": "ccss" },
    "MO": { "name": "Missouri", "framework": "ccss" },
    "MT": { "name": "Montana", "framework": "ccss" },
    "NE": { "name": "Nebraska", "framework": "ccss", "note": "Has own standards; CCSS used as approximation" },
    "NV": { "name": "Nevada", "framework": "ccss" },
    "NH": { "name": "New Hampshire", "framework": "ccss" },
    "NJ": { "name": "New Jersey", "framework": "ccss" },
    "NM": { "name": "New Mexico", "framework": "ccss" },
    "NY": { "name": "New York", "framework": "ccss" },
    "NC": { "name": "North Carolina", "framework": "ccss" },
    "ND": { "name": "North Dakota", "framework": "ccss" },
    "OH": { "name": "Ohio", "framework": "ccss" },
    "OK": { "name": "Oklahoma", "framework": "ccss", "note": "Has own standards; CCSS used as approximation" },
    "OR": { "name": "Oregon", "framework": "ccss" },
    "PA": { "name": "Pennsylvania", "framework": "ccss" },
    "RI": { "name": "Rhode Island", "framework": "ccss" },
    "SC": { "name": "South Carolina", "framework": "ccss", "note": "Has own standards; CCSS used as approximation" },
    "SD": { "name": "South Dakota", "framework": "ccss" },
    "TN": { "name": "Tennessee", "framework": "ccss" },
    "TX": { "name": "Texas", "framework": "tx" },
    "UT": { "name": "Utah", "framework": "ccss" },
    "VT": { "name": "Vermont", "framework": "ccss" },
    "VA": { "name": "Virginia", "framework": "va" },
    "WA": { "name": "Washington", "framework": "ccss" },
    "WV": { "name": "West Virginia", "framework": "ccss" },
    "WI": { "name": "Wisconsin", "framework": "ccss" },
    "WY": { "name": "Wyoming", "framework": "ccss" },
    "DC": { "name": "District of Columbia", "framework": "ccss" }
  },
  "subject_fallbacks": {
    "Math": "ccss",
    "English/ELA": "ccss",
    "Science": "ngss",
    "Social Studies": "ccss",
    "US History": "ccss",
    "World History": "ccss",
    "Civics": "ccss",
    "Geography": "ccss",
    "Spanish": null,
    "French": null,
    "World Languages": null,
    "Other": null
  },
  "subject_to_filename": {
    "Math": "math",
    "English/ELA": "english-ela",
    "Science": "science",
    "Social Studies": "social_studies",
    "US History": "us_history",
    "World History": "world_history",
    "Civics": "civics",
    "Geography": "geography",
    "Spanish": "spanish",
    "French": "french",
    "World Languages": "world_languages"
  }
}
```

States with a `"note"` field have not formally adopted CCSS but use it as an approximation. The `note` value is included in the fallback notice shown to teachers from those states.

## Standards Resolution Logic

Updated `load_standards(state, subject, grade)` in `planner_routes.py`:

1. Load `standards_map.json` (cached in module-level variable per worker, loaded once on first call; server restart required after file changes)
2. Look up state → framework (e.g., `"TX"` → `"tx"`, `"CA"` → `"ccss"`)
3. Map subject to filename via `subject_to_filename` (e.g., `"English/ELA"` → `"english-ela"`)
4. Try to load `standards/{framework}/{filename}.json`
5. If not found and framework is state-specific, try fallback:
   - Look up `subject_fallbacks[subject]` (e.g., `"Math"` → `"ccss"`)
   - Try `standards/{fallback}/{filename}.json`
   - Set `fallback_used = True`, `fallback_framework = fallback`
6. If `subject_fallbacks[subject]` is `null` (Spanish, French, World Languages), set `no_framework = True`
7. If still not found, try legacy path `standards_{state.lower()}_{subject_clean}.json` (note: lowercase state code)
8. Return dict: `{ "standards": [...], "fallback_used": bool, "fallback_framework": str|null, "no_framework": bool, "state_note": str|null }`

### Caller Updates

The return type changes from a plain list to a dict. All three callers in `planner_routes.py` must be updated:

**`get_standards()` (~line 2225):**
```python
result = load_standards(state, subject, grade)
standards = result["standards"]
# ... existing logic using standards list ...
return jsonify({
    "standards": standards,
    "fallback_used": result.get("fallback_used", False),
    "fallback_framework": result.get("fallback_framework"),
    "no_framework": result.get("no_framework", False),
    "state_note": result.get("state_note"),
    # ... existing fields ...
})
```

**`align_standards()` (~line 2250):**
```python
result = load_standards(state, subject, grade)
standards = result["standards"]
if not standards:
    return jsonify({"error": "..."})
# ... existing iteration over standards list ...
```

**`rewrite_for_alignment()` (~line 2342):**
```python
result = load_standards(state, subject, grade)
standards = result["standards"]
input_standard_codes = {s.get("code"): s for s in standards}
```

**`generate_assessment()` and `generate_lesson_plan()`:** These also call `load_standards()`. Update them the same way — extract `result["standards"]` into the local variable. Include `fallback_used` in their API responses so the frontend can show the notice on generated content too.

## Standards JSON Schema

Every standard in every file must include all 8 fields:

```json
{
  "code": "CCSS.MATH.CONTENT.6.EE.A.1",
  "benchmark": "Write and evaluate numerical expressions involving whole-number exponents.",
  "topics": ["Exponents", "Numerical Expressions", "Order of Operations"],
  "dok": 2,
  "item_specs": "Students write and evaluate expressions with whole-number exponents, applying order of operations.",
  "essential_questions": [
    "How do exponents represent repeated multiplication?",
    "How do you evaluate expressions with exponents?"
  ],
  "learning_targets": [
    "I can write numerical expressions using exponents.",
    "I can evaluate expressions with whole-number exponents."
  ],
  "vocabulary": ["exponent", "base", "power", "evaluate", "numerical expression"],
  "sample_assessment": "Evaluate: 3^4 + 2 x 5. Show your work and explain each step."
}
```

Fields that cannot be determined from official sources should use reasonable defaults:
- `dok`: default `2` if not specified in source
- `item_specs`: derive from benchmark text if not explicitly in source
- `essential_questions`: generate from benchmark
- `sample_assessment`: generate aligned example

## Standards Data Generation

### CCSS (Math, ELA, Social Studies)
- Source: Common Core State Standards Initiative official documents
- Math: grades 6-12 (6-8 grade-specific, 9-12 by course: Algebra 1, Geometry, Algebra 2)
- ELA: grades 6-12 (6-8 grade-specific, 9-10 and 11-12 grade bands)
- Social Studies: C3 Framework (College, Career, and Civic Life) — covers civics, geography, economics, history

### NGSS (Science)
- Source: Next Generation Science Standards official documents
- Grades 6-8 (grade-specific), 9-12 (by discipline: Biology, Chemistry, Physics, Earth Science)

### State-Specific
- **FL**: Already complete (9 files, migrate to new path)
- **TX**: TEKS — Math, ELA, Science, Social Studies for grades 6-12
- **VA**: SOLs — Math, ELA, Science, Social Studies for grades 6-12

### Extraction Pipeline
1. Obtain official standards documents (PDF/web)
2. AI extraction: feed documents to GPT-4o with our JSON schema as target format
3. Output one JSON file per subject per framework
4. Validation: spot-check 10 random standards per file against official source
5. Grade filtering: ensure code patterns support grade extraction in `load_standards()`

### Grade Code Patterns by Framework

| Framework | Pattern | Example | Grade extraction |
|-----------|---------|---------|-----------------|
| CCSS Math | `CCSS.MATH.CONTENT.{G}.{DOMAIN}.{STD}` | `CCSS.MATH.CONTENT.6.EE.A.1` | `code.split('.')[3]` |
| CCSS ELA | `CCSS.ELA-LITERACY.{STRAND}.{G}.{STD}` | `CCSS.ELA-LITERACY.RL.6.1` | `code.split('.')[2]` |
| NGSS | `{PREFIX}-{DISCIPLINE}{STD}-{NUM}` | `MS-PS1-1` | Prefix: `MS`→6-8, `HS`→9-12 |
| C3 Social Studies | `D{DIMENSION}.{G-BAND}.{NUM}` | `D2.His.1.6-8` | Grade band after last `.` (e.g., `6-8`, `9-12`) |
| TX TEKS | `{SUBJECT}.{G}.{STD}.{SUBSTD}` | `MATH.6.2.A` | `code.split('.')[1]` |
| VA SOL | `{SUBJECT}.{G}.{STD}` | `MATH.6.1` | `code.split('.')[1]` |
| FL B.E.S.T. | `{SUBJ}.{G}.{DOMAIN}.{STD}.{SUBSTD}` | `MA.6.AR.1.1` | `code.split('.')[1]` |

### Updated Grade Filtering Algorithm

```python
def _extract_grade_from_code(code):
    """Extract grade level from a standards code across all frameworks."""
    if not code:
        return None
    parts = code.split('.')

    # NGSS: prefix-based (MS-PS1-1, HS-LS1-1)
    if code.startswith('MS-'):
        return 'MS'  # middle school, grades 6-8
    if code.startswith('HS-'):
        return 'HS'  # high school, grades 9-12

    # CCSS Math: CCSS.MATH.CONTENT.{G}.{DOMAIN}...
    if code.startswith('CCSS.MATH') and len(parts) >= 4:
        return parts[3]  # e.g., "6", "7", "8"

    # CCSS ELA: CCSS.ELA-LITERACY.{STRAND}.{G}...
    if code.startswith('CCSS.ELA') and len(parts) >= 3:
        return parts[2]  # e.g., "6", "9-10", "11-12"

    # C3 Social Studies: D2.His.1.6-8
    if code.startswith('D') and code[1:2].isdigit() and len(parts) >= 4:
        return parts[3]  # grade band like "6-8" or "9-12"

    # FL B.E.S.T., TX TEKS, VA SOL: {SUBJ}.{G}.{DOMAIN}...
    if len(parts) >= 2:
        candidate = parts[1]
        # K12 codes apply to all grades
        if candidate == 'K12':
            return 'K12'
        # Numeric grade (6, 7, 8) or high school band (912)
        if candidate.isdigit() or candidate == 'K':
            return candidate
        # Grade band like "6-8"
        if '-' in candidate:
            return candidate

    return None


def _grade_matches(code_grade, requested_grade):
    """Check if extracted grade matches the requested grade."""
    if code_grade is None:
        return False
    if code_grade == 'K12':
        return True  # applies to all grades
    if code_grade == requested_grade:
        return True
    # NGSS: MS matches grades 6-8, HS matches 9-12
    if code_grade == 'MS' and requested_grade in ('6', '7', '8'):
        return True
    if code_grade == 'HS' and requested_grade in ('9', '10', '11', '12'):
        return True
    # Grade bands: "6-8", "9-10", "11-12", "912"
    if '-' in str(code_grade):
        try:
            lo, hi = code_grade.split('-')
            req = int(requested_grade) if requested_grade.isdigit() else 0
            return int(lo) <= req <= int(hi)
        except (ValueError, IndexError):
            pass
    if code_grade == '912' and requested_grade in ('9', '10', '11', '12'):
        return True
    return False
```

This replaces the current inline grade filtering in `load_standards()` with framework-agnostic functions.

## Frontend Changes

### State Selector (SettingsTab.jsx)

Replace hardcoded 10-state dropdown with all 50 states + DC. Load from a new endpoint:

**`GET /api/available-states`** — no auth required (public curriculum data, no student PII):
```json
{
  "states": [
    { "code": "AL", "name": "Alabama" },
    { "code": "AK", "name": "Alaska" },
    ...
  ]
}
```

SettingsTab fetches on mount and populates the dropdown. Sorted alphabetically by name.

### Fallback Notice (PlannerTab.jsx)

When `get_standards` API returns `fallback_used: true`, the planner shows an info banner:

- If state has a `note` field: "[State] has its own standards framework. Using Common Core standards as an approximation."
- Otherwise: "State-specific standards not yet available for [State] [Subject]. Using Common Core standards."
- For `no_framework: true` (Spanish, French, World Languages): "No national standards framework available for [Subject]. Standards vary by state and district."

Styled as a subtle info bar (blue background, not alarming). Shown above the standards list in the planner.

The fallback notice also appears in assessment/lesson generation responses when `fallback_used` is true, so teachers see it regardless of which feature they use.

### FL FAST Toggle

In PlannerTab.jsx, the "FL FAST Item Types" section category toggle appears in **two render paths**:
1. Line ~2576 (compact mode) — gate with `config.state === 'FL'`
2. Line ~4599 (detail mode) — gate with `config.state === 'FL'`

The group label `"FL FAST Core"` at line ~4603 should be renamed to `"Core"` for all states (the items in this group are not FL-specific, only the label is).

### PlannerTab State Display

The state display label in PlannerTab (~line 4201) currently has a hardcoded map of 10 state codes to names. Replace with lookup from the states data (fetched via `/api/available-states` or passed through config).

## Backend Changes

| File | Change |
|------|--------|
| `backend/routes/planner_routes.py` | Update `load_standards()` with mapping-based resolution + grade filtering, update all callers, add `/api/available-states` endpoint (no auth) |
| `backend/data/standards/standards_map.json` | NEW — state mapping config |
| `backend/data/standards/ccss/*.json` | NEW — Common Core standards files |
| `backend/data/standards/ngss/science.json` | NEW — NGSS standards |
| `backend/data/standards/tx/*.json` | NEW — Texas TEKS |
| `backend/data/standards/va/*.json` | NEW — Virginia SOLs |
| `backend/data/standards/fl/*.json` | MOVED — existing FL files |

## Frontend Changes

| File | Change |
|------|--------|
| `frontend/src/tabs/SettingsTab.jsx` | All 50 states + DC in dropdown, fetched from `/api/available-states` |
| `frontend/src/tabs/PlannerTab.jsx` | Fallback notice banner, FL FAST gate (both paths), group label fix, state name lookup |
| `frontend/src/services/api.js` | Add `getAvailableStates()` function |

## Backward Compatibility

- `load_standards()` checks new path first, then falls back to legacy `standards_{state.lower()}_{subject_clean}.json` (lowercase state code to match existing `standards_fl_*.json` files)
- No schema changes — standards JSON format identical
- Default state remains `"FL"`
- Existing FL teachers see identical behavior
- No database changes
- Standards map cached per-worker (Gunicorn); server restart required after config changes

## Test Impact

**New tests:**
- `_extract_grade_from_code()`: CCSS Math, CCSS ELA, NGSS, C3, TEKS, SOL, FL B.E.S.T. patterns
- `_grade_matches()`: exact match, NGSS MS/HS, grade bands, K12, 912
- `load_standards()` resolution: state-specific found, CCSS fallback, NGSS fallback, no_framework (null fallback), legacy fallback, no match
- Return type is dict with correct metadata fields
- `/api/available-states` returns all 50 states + DC, no auth required
- FL FAST toggle only visible for FL

**Existing tests unaffected:**
- All current planner tests (FL standards path unchanged via legacy fallback)
- All E2E tests (default state is FL)
