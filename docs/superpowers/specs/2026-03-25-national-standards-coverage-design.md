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
- All 50 states in the frontend state selector
- Fallback notice in planner when using CCSS/NGSS instead of state-specific
- FL FAST toggle gated to Florida only
- All standards files at full depth: code, benchmark, DOK, topics, vocabulary, learning_targets, essential_questions, sample_assessment

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

Existing `backend/data/standards_fl_*.json` files are migrated to `standards/fl/` with the `standards_fl_` prefix dropped. Legacy flat file path checked as fallback during transition.

## Standards Map Config

`backend/data/standards/standards_map.json`:

```json
{
  "states": {
    "AL": { "name": "Alabama", "framework": "ccss" },
    "AK": { "name": "Alaska", "framework": "ccss" },
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
    "IN": { "name": "Indiana", "framework": "ccss" },
    "IA": { "name": "Iowa", "framework": "ccss" },
    "KS": { "name": "Kansas", "framework": "ccss" },
    "KY": { "name": "Kentucky", "framework": "ccss" },
    "LA": { "name": "Louisiana", "framework": "ccss" },
    "ME": { "name": "Maine", "framework": "ccss" },
    "MD": { "name": "Maryland", "framework": "ccss" },
    "MA": { "name": "Massachusetts", "framework": "ccss" },
    "MI": { "name": "Michigan", "framework": "ccss" },
    "MN": { "name": "Minnesota", "framework": "ccss" },
    "MS": { "name": "Mississippi", "framework": "ccss" },
    "MO": { "name": "Missouri", "framework": "ccss" },
    "MT": { "name": "Montana", "framework": "ccss" },
    "NE": { "name": "Nebraska", "framework": "ccss" },
    "NV": { "name": "Nevada", "framework": "ccss" },
    "NH": { "name": "New Hampshire", "framework": "ccss" },
    "NJ": { "name": "New Jersey", "framework": "ccss" },
    "NM": { "name": "New Mexico", "framework": "ccss" },
    "NY": { "name": "New York", "framework": "ccss" },
    "NC": { "name": "North Carolina", "framework": "ccss" },
    "ND": { "name": "North Dakota", "framework": "ccss" },
    "OH": { "name": "Ohio", "framework": "ccss" },
    "OK": { "name": "Oklahoma", "framework": "ccss" },
    "OR": { "name": "Oregon", "framework": "ccss" },
    "PA": { "name": "Pennsylvania", "framework": "ccss" },
    "RI": { "name": "Rhode Island", "framework": "ccss" },
    "SC": { "name": "South Carolina", "framework": "ccss" },
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

## Standards Resolution Logic

Updated `load_standards(state, subject, grade)` in `planner_routes.py`:

1. Load `standards_map.json` (cached in module-level variable, loaded once)
2. Look up state → framework (e.g., `"TX"` → `"tx"`, `"CA"` → `"ccss"`)
3. Map subject to filename (e.g., `"English/ELA"` → `"english-ela"`)
4. Try to load `standards/{framework}/{filename}.json`
5. If not found and framework is state-specific, try fallback:
   - Look up `subject_fallbacks[subject]` (e.g., `"Math"` → `"ccss"`)
   - Try `standards/{fallback}/{filename}.json`
   - Set `fallback_used = True`
6. If still not found, try legacy path `standards_{state}_{subject_clean}.json`
7. Return `{ "standards": [...], "fallback_used": bool, "fallback_framework": str|null }`

The return type changes from a plain list to a dict with metadata. Callers updated to handle both formats.

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
| CCSS Math | `CCSS.MATH.CONTENT.{G}.{DOMAIN}.{STD}` | `CCSS.MATH.CONTENT.6.EE.A.1` | Position after `CONTENT.` |
| CCSS ELA | `CCSS.ELA-LITERACY.{STRAND}.{G}.{STD}` | `CCSS.ELA-LITERACY.RL.6.1` | Position after strand |
| NGSS | `{G}-{DISCIPLINE}{STD}-{NUM}` | `MS-PS1-1` (middle school) | Prefix: `MS`=6-8, `HS`=9-12 |
| TX TEKS | `{SUBJECT}.{G}.{STD}.{SUBSTD}` | `MATH.6.2.A` | Position 2 |
| VA SOL | `{SUBJECT}.{G}.{STD}` | `MATH.6.1` | Position 2 |
| FL B.E.S.T. | `{SUBJ}.{G}.{DOMAIN}.{STD}.{SUBSTD}` | `MA.6.AR.1.1` | Position 2 |

`load_standards()` grade filtering logic must handle all patterns. The NGSS prefix-based pattern (`MS-`, `HS-`) needs special handling.

## Frontend Changes

### State Selector (SettingsTab.jsx)

Replace hardcoded 10-state dropdown with all 50 states + DC. Load from a new endpoint:

**`GET /api/available-states`** — returns list from `standards_map.json`:
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

When `load_standards()` returns `fallback_used: true`, the planner shows an info banner:

> "State-specific standards not yet available for [State] [Subject]. Using Common Core standards."

Styled as a subtle info bar (blue background, not alarming). Shown above the standards list in the planner.

The `get_standards` API endpoint returns the `fallback_used` and `fallback_framework` fields so the frontend can detect this.

### FL FAST Toggle

In PlannerTab.jsx, the "FL FAST Item Types" section category toggle (currently always visible for assessments) should only render when `config.state === 'FL'`.

### PlannerTab State Display

The state display label in PlannerTab (~line 4201) currently has a hardcoded map of 10 state codes to names. Replace with lookup from `standards_map.json` data (passed via config or fetched).

## Backend Changes

| File | Change |
|------|--------|
| `backend/routes/planner_routes.py` | Update `load_standards()` with mapping-based resolution, add `/api/available-states` endpoint |
| `backend/data/standards/standards_map.json` | NEW — state mapping config |
| `backend/data/standards/ccss/*.json` | NEW — Common Core standards files |
| `backend/data/standards/ngss/science.json` | NEW — NGSS standards |
| `backend/data/standards/tx/*.json` | NEW — Texas TEKS |
| `backend/data/standards/va/*.json` | NEW — Virginia SOLs |
| `backend/data/standards/fl/*.json` | MOVED — existing FL files |

## Frontend Changes

| File | Change |
|------|--------|
| `frontend/src/tabs/SettingsTab.jsx` | All 50 states in dropdown, fetched from API |
| `frontend/src/tabs/PlannerTab.jsx` | Fallback notice banner, FL FAST gate, state name lookup |

## Backward Compatibility

- `load_standards()` checks new path first, then falls back to legacy `standards_{state}_{subject}.json`
- No schema changes — standards JSON format identical
- Default state remains `"FL"`
- Existing FL teachers see identical behavior
- No database changes

## Test Impact

**New tests:**
- `load_standards()` resolution: state-specific found, CCSS fallback, NGSS fallback, legacy fallback, no match
- `/api/available-states` returns all 50 states + DC
- Grade filtering works for CCSS, NGSS, TEKS, SOL code patterns
- FL FAST toggle only visible for FL

**Existing tests unaffected:**
- All current planner tests (FL standards path unchanged via legacy fallback)
- All E2E tests (default state is FL)
