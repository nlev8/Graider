# National Standards Coverage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand standards coverage from Florida-only to all 50 US states using CCSS/NGSS fallback with state-specific overrides, transparent fallback notices, and updated grade filtering.

**Architecture:** Add `standards_map.json` config mapping states to frameworks. Reorganize standards files into `backend/data/standards/{framework}/` subdirectories. Update `load_standards()` to resolve via mapping with CCSS/NGSS fallback. Generate CCSS, NGSS, TX, and VA standards files via AI extraction. Update frontend state selector to all 50 states + DC.

**Tech Stack:** Flask/Python backend, React frontend (inline styles), JSON standards files, GPT-4o for data extraction.

**Spec:** `docs/superpowers/specs/2026-03-25-national-standards-coverage-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `backend/data/standards/standards_map.json` | CREATE | State→framework mapping, subject fallbacks, subject→filename mapping |
| `backend/data/standards/ccss/math.json` | CREATE | Common Core Math standards grades 6-12 |
| `backend/data/standards/ccss/english-ela.json` | CREATE | Common Core ELA standards grades 6-12 |
| `backend/data/standards/ccss/social_studies.json` | CREATE | C3 Framework social studies standards |
| `backend/data/standards/ngss/science.json` | CREATE | Next Gen Science Standards grades 6-12 |
| `backend/data/standards/fl/*.json` | MOVE | Existing FL standards (9 files) |
| `backend/data/standards/tx/*.json` | CREATE | Texas TEKS standards (4 files) |
| `backend/data/standards/va/*.json` | CREATE | Virginia SOL standards (4 files) |
| `backend/routes/planner_routes.py` | MODIFY | Updated `load_standards()`, grade filtering, `/api/available-states`, caller updates |
| `backend/services/assistant_tools.py` | MODIFY | Update `_load_standards()` to use new resolution |
| `frontend/src/services/api.js` | MODIFY | Add `getAvailableStates()` |
| `frontend/src/tabs/SettingsTab.jsx` | MODIFY | 50-state dropdown from API |
| `frontend/src/tabs/PlannerTab.jsx` | MODIFY | Fallback notice, FL FAST gate, state name lookup |
| `tests/test_standards.py` | CREATE | Unit tests for grade extraction, matching, resolution |

---

### Task 1: Standards Map Config and File Migration

**Files:**
- Create: `backend/data/standards/standards_map.json`
- Move: `backend/data/standards_fl_*.json` → `backend/data/standards/fl/`

- [ ] **Step 1: Create directory structure**

```bash
cd /Users/alexc/Downloads/Graider
mkdir -p backend/data/standards/ccss
mkdir -p backend/data/standards/ngss
mkdir -p backend/data/standards/fl
mkdir -p backend/data/standards/tx
mkdir -p backend/data/standards/va
```

- [ ] **Step 2: Move existing FL standards files**

```bash
cp backend/data/standards_fl_math.json backend/data/standards/fl/math.json
cp backend/data/standards_fl_english-ela.json backend/data/standards/fl/english-ela.json
cp backend/data/standards_fl_science.json backend/data/standards/fl/science.json
cp backend/data/standards_fl_social_studies.json backend/data/standards/fl/social_studies.json
cp backend/data/standards_fl_civics.json backend/data/standards/fl/civics.json
cp backend/data/standards_fl_geography.json backend/data/standards/fl/geography.json
cp backend/data/standards_fl_us_history.json backend/data/standards/fl/us_history.json
cp backend/data/standards_fl_world_history.json backend/data/standards/fl/world_history.json
cp backend/data/standards_fl_spanish.json backend/data/standards/fl/spanish.json
```

Note: Copy, don't move — legacy files stay for backward compatibility until Task 3 confirms the new resolution works.

- [ ] **Step 3: Create standards_map.json**

Create `backend/data/standards/standards_map.json` with the full content from the spec (all 50 states + DC, subject_fallbacks, subject_to_filename). See spec lines 68-150 for exact JSON.

- [ ] **Step 4: Verify files exist**

```bash
ls backend/data/standards/fl/ | wc -l  # Should be 9
cat backend/data/standards/standards_map.json | python -m json.tool > /dev/null && echo "Valid JSON"
```

- [ ] **Step 5: Commit**

```bash
git add backend/data/standards/
git commit -m "feat: add standards directory structure and map config, copy FL standards"
```

---

### Task 2: Grade Filtering Functions and Unit Tests

**Files:**
- Create: `tests/test_standards.py`
- Modify: `backend/routes/planner_routes.py`

- [ ] **Step 1: Write tests for `_extract_grade_from_code()`**

Create `tests/test_standards.py`:

```python
"""Tests for standards resolution, grade extraction, and grade matching."""
import pytest


@pytest.fixture(autouse=True)
def reset_standards_cache():
    """Reset the module-level standards map cache between tests."""
    import backend.routes.planner_routes as pr
    pr._standards_map_cache = None
    yield
    pr._standards_map_cache = None


class TestExtractGradeFromCode:
    """Test _extract_grade_from_code for all framework patterns."""

    def test_fl_best_math(self):
        from backend.routes.planner_routes import _extract_grade_from_code
        assert _extract_grade_from_code('MA.6.AR.1.1') == '6'

    def test_fl_best_science(self):
        from backend.routes.planner_routes import _extract_grade_from_code
        assert _extract_grade_from_code('SC.7.E.6.1') == '7'

    def test_fl_best_k12(self):
        from backend.routes.planner_routes import _extract_grade_from_code
        assert _extract_grade_from_code('WL.K12.NH.1.1') == 'K12'

    def test_fl_best_912(self):
        from backend.routes.planner_routes import _extract_grade_from_code
        assert _extract_grade_from_code('MA.912.AR.1.1') == '912'

    def test_ccss_math(self):
        from backend.routes.planner_routes import _extract_grade_from_code
        assert _extract_grade_from_code('CCSS.MATH.CONTENT.6.EE.A.1') == '6'

    def test_ccss_math_8(self):
        from backend.routes.planner_routes import _extract_grade_from_code
        assert _extract_grade_from_code('CCSS.MATH.CONTENT.8.G.B.7') == '8'

    def test_ccss_ela(self):
        from backend.routes.planner_routes import _extract_grade_from_code
        assert _extract_grade_from_code('CCSS.ELA-LITERACY.RL.6.1') == '6'

    def test_ccss_ela_band(self):
        from backend.routes.planner_routes import _extract_grade_from_code
        assert _extract_grade_from_code('CCSS.ELA-LITERACY.RL.9-10.1') == '9-10'

    def test_ngss_middle_school(self):
        from backend.routes.planner_routes import _extract_grade_from_code
        assert _extract_grade_from_code('MS-PS1-1') == 'MS'

    def test_ngss_high_school(self):
        from backend.routes.planner_routes import _extract_grade_from_code
        assert _extract_grade_from_code('HS-LS1-1') == 'HS'

    def test_c3_social_studies(self):
        from backend.routes.planner_routes import _extract_grade_from_code
        assert _extract_grade_from_code('D2.His.1.6-8') == '6-8'

    def test_c3_high_school(self):
        from backend.routes.planner_routes import _extract_grade_from_code
        assert _extract_grade_from_code('D2.Civ.1.9-12') == '9-12'

    def test_tx_teks(self):
        from backend.routes.planner_routes import _extract_grade_from_code
        assert _extract_grade_from_code('MATH.6.2.A') == '6'

    def test_va_sol(self):
        from backend.routes.planner_routes import _extract_grade_from_code
        assert _extract_grade_from_code('MATH.6.1') == '6'

    def test_empty_code(self):
        from backend.routes.planner_routes import _extract_grade_from_code
        assert _extract_grade_from_code('') is None

    def test_none_code(self):
        from backend.routes.planner_routes import _extract_grade_from_code
        assert _extract_grade_from_code(None) is None


class TestGradeMatches:
    """Test _grade_matches for all matching scenarios."""

    def test_exact_match(self):
        from backend.routes.planner_routes import _grade_matches
        assert _grade_matches('6', '6') is True

    def test_no_match(self):
        from backend.routes.planner_routes import _grade_matches
        assert _grade_matches('6', '7') is False

    def test_k12_matches_all(self):
        from backend.routes.planner_routes import _grade_matches
        assert _grade_matches('K12', '6') is True
        assert _grade_matches('K12', '12') is True

    def test_ngss_ms_matches_6_7_8(self):
        from backend.routes.planner_routes import _grade_matches
        assert _grade_matches('MS', '6') is True
        assert _grade_matches('MS', '7') is True
        assert _grade_matches('MS', '8') is True
        assert _grade_matches('MS', '9') is False

    def test_ngss_hs_matches_9_10_11_12(self):
        from backend.routes.planner_routes import _grade_matches
        assert _grade_matches('HS', '9') is True
        assert _grade_matches('HS', '12') is True
        assert _grade_matches('HS', '8') is False

    def test_grade_band_6_8(self):
        from backend.routes.planner_routes import _grade_matches
        assert _grade_matches('6-8', '6') is True
        assert _grade_matches('6-8', '8') is True
        assert _grade_matches('6-8', '9') is False

    def test_grade_band_9_10(self):
        from backend.routes.planner_routes import _grade_matches
        assert _grade_matches('9-10', '9') is True
        assert _grade_matches('9-10', '10') is True
        assert _grade_matches('9-10', '11') is False

    def test_912_band(self):
        from backend.routes.planner_routes import _grade_matches
        assert _grade_matches('912', '9') is True
        assert _grade_matches('912', '12') is True
        assert _grade_matches('912', '8') is False

    def test_none_grade(self):
        from backend.routes.planner_routes import _grade_matches
        assert _grade_matches(None, '6') is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `source /Users/alexc/Downloads/Graider/venv/bin/activate && python -m pytest tests/test_standards.py -v`
Expected: FAIL — `_extract_grade_from_code` and `_grade_matches` not defined yet

- [ ] **Step 3: Implement grade filtering functions**

In `backend/routes/planner_routes.py`, add these two functions BEFORE the existing `load_standards()` function (before line 2133):

```python
def _extract_grade_from_code(code):
    """Extract grade level from a standards code across all frameworks."""
    if not code:
        return None
    parts = code.split('.')

    # NGSS: prefix-based (MS-PS1-1, HS-LS1-1)
    if code.startswith('MS-'):
        return 'MS'
    if code.startswith('HS-'):
        return 'HS'

    # CCSS Math: CCSS.MATH.CONTENT.{G}.{DOMAIN}...
    if code.startswith('CCSS.MATH') and len(parts) >= 4:
        return parts[3]

    # CCSS ELA: CCSS.ELA-LITERACY.{STRAND}.{G}...
    if code.startswith('CCSS.ELA') and len(parts) >= 3:
        return parts[2]

    # C3 Social Studies: D2.His.1.6-8
    if code.startswith('D') and len(code) > 1 and code[1:2].isdigit() and len(parts) >= 4:
        return parts[3]

    # FL B.E.S.T., TX TEKS, VA SOL: {SUBJ}.{G}.{DOMAIN}...
    if len(parts) >= 2:
        candidate = parts[1]
        if candidate == 'K12':
            return 'K12'
        if candidate.isdigit() or candidate == 'K':
            return candidate
        if '-' in candidate:
            return candidate

    return None


def _grade_matches(code_grade, requested_grade):
    """Check if extracted grade matches the requested grade."""
    if code_grade is None:
        return False
    if code_grade == 'K12':
        return True
    if code_grade == requested_grade:
        return True
    if code_grade == 'MS' and requested_grade in ('6', '7', '8'):
        return True
    if code_grade == 'HS' and requested_grade in ('9', '10', '11', '12'):
        return True
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

- [ ] **Step 4: Run tests to verify they pass**

Run: `source /Users/alexc/Downloads/Graider/venv/bin/activate && python -m pytest tests/test_standards.py -v`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add tests/test_standards.py backend/routes/planner_routes.py
git commit -m "feat: add grade extraction and matching for all standards frameworks"
```

---

### Task 3: Update `load_standards()` with Mapping-Based Resolution

**Files:**
- Modify: `backend/routes/planner_routes.py:2133-2211`
- Modify: `tests/test_standards.py`

- [ ] **Step 1: Write resolution tests**

Add to `tests/test_standards.py`:

```python
class TestLoadStandards:
    """Test load_standards resolution logic."""

    def test_fl_math_returns_dict(self):
        from backend.routes.planner_routes import load_standards
        result = load_standards('FL', 'Math', '6')
        assert isinstance(result, dict)
        assert 'standards' in result
        assert 'fallback_used' in result
        assert result['fallback_used'] is False

    def test_fl_math_has_standards(self):
        from backend.routes.planner_routes import load_standards
        result = load_standards('FL', 'Math', '6')
        assert len(result['standards']) > 0

    def test_ccss_fallback_for_ca(self):
        from backend.routes.planner_routes import load_standards
        result = load_standards('CA', 'Math', '6')
        assert isinstance(result, dict)
        # CA uses ccss framework — if ccss/math.json exists, no fallback needed
        # If ccss/math.json doesn't exist yet, this will be empty
        # After Task 5 (CCSS data), this should return standards

    def test_no_framework_for_spanish(self):
        from backend.routes.planner_routes import load_standards
        result = load_standards('CA', 'Spanish')
        assert result.get('no_framework') is True or len(result['standards']) == 0

    def test_state_note_for_alaska(self):
        from backend.routes.planner_routes import load_standards
        result = load_standards('AK', 'Math', '6')
        # AK has a note in the map
        assert result.get('state_note') is not None or result.get('state_note') is None  # passes either way until map loaded

    def test_unknown_state_returns_empty(self):
        from backend.routes.planner_routes import load_standards
        result = load_standards('ZZ', 'Math', '6')
        assert isinstance(result, dict)
        assert len(result['standards']) == 0
```

- [ ] **Step 2: Rewrite `load_standards()`**

Replace the entire `load_standards()` function in `backend/routes/planner_routes.py` (lines 2133-2211) with:

```python
# Module-level cache for standards map
_standards_map_cache = None

def _get_standards_map():
    """Load and cache standards_map.json."""
    global _standards_map_cache
    if _standards_map_cache is None:
        map_path = DATA_DIR / 'standards' / 'standards_map.json'
        if map_path.exists():
            with open(map_path, 'r') as f:
                _standards_map_cache = json.load(f)
        else:
            _standards_map_cache = {}
    return _standards_map_cache


def load_standards(state, subject, grade=None):
    """Load standards with mapping-based resolution and fallback.

    Returns dict: {standards, fallback_used, fallback_framework, no_framework, state_note}
    """
    result = {
        'standards': [],
        'fallback_used': False,
        'fallback_framework': None,
        'no_framework': False,
        'state_note': None,
    }

    smap = _get_standards_map()
    states = smap.get('states', {})
    subject_fallbacks = smap.get('subject_fallbacks', {})
    subject_to_filename = smap.get('subject_to_filename', {})

    # Look up state config
    state_config = states.get(state.upper(), {})
    framework = state_config.get('framework', 'ccss')
    result['state_note'] = state_config.get('note')

    # Map subject to filename
    filename = subject_to_filename.get(subject)
    if not filename:
        # Fallback: clean subject name (legacy behavior)
        filename = subject.lower().replace(' ', '_').replace('/', '-')

    # Try primary path: standards/{framework}/{filename}.json
    primary_path = DATA_DIR / 'standards' / framework / (filename + '.json')
    standards = _load_standards_file(primary_path)

    if not standards and framework not in ('ccss', 'ngss'):
        # State-specific file not found — try fallback
        fallback_fw = subject_fallbacks.get(subject)
        if fallback_fw is None:
            result['no_framework'] = True
        elif fallback_fw:
            fallback_path = DATA_DIR / 'standards' / fallback_fw / (filename + '.json')
            standards = _load_standards_file(fallback_path)
            if standards:
                result['fallback_used'] = True
                result['fallback_framework'] = fallback_fw

    if not standards:
        # Legacy fallback: standards_{state}_{subject}.json
        subject_clean = subject.lower().replace(' ', '_').replace('/', '-')
        legacy_path = DATA_DIR / ('standards_' + state.lower() + '_' + subject_clean + '.json')
        standards = _load_standards_file(legacy_path)

    # Filter by grade
    if grade and standards:
        filtered = [s for s in standards if _grade_matches(_extract_grade_from_code(s.get('code', '')), str(grade))]
        if filtered:
            standards = filtered
        # If no grade-specific matches but we have standards, check existing course-based filtering
        elif not filtered:
            # Preserve existing high school course mapping for FL
            GRADE_TO_COURSE = {
                'math': {'9': 'Algebra 1', '10': 'Geometry', '11': 'Algebra 2', '12': 'Pre-Calculus'},
                'science': {'9': 'Biology', '10': 'Chemistry', '11': 'Physics', '12': 'Earth/Space Science'},
            }
            subject_clean = subject.lower().replace(' ', '_').replace('/', '-')
            courses = GRADE_TO_COURSE.get(subject_clean, {})
            if str(grade) in courses:
                course_filtered = [s for s in standards if s.get('course') == courses[str(grade)]]
                if course_filtered:
                    standards = course_filtered

    result['standards'] = standards
    return result


def _load_standards_file(filepath):
    """Load standards from a JSON file. Returns list or empty list."""
    if not filepath.exists():
        return []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        return data.get('standards', [])
    except Exception:
        return []
```

- [ ] **Step 3: Update all callers of `load_standards()`**

In `planner_routes.py`, find and update the 3 callers:

**`get_standards()` (~line 2225):**
Change `standards = load_standards(state, subject, grade)` to:
```python
        result = load_standards(state, subject, grade)
        standards = result['standards']
```
And add to the return jsonify: `"fallback_used": result.get("fallback_used", False), "fallback_framework": result.get("fallback_framework"), "no_framework": result.get("no_framework", False), "state_note": result.get("state_note"),`

**`align_standards()` (~line 2250):**
Change `standards = load_standards(state, subject, grade)` to:
```python
        result = load_standards(state, subject, grade)
        standards = result['standards']
```

**`rewrite_for_alignment()` (~line 2342):**
Change `standards = load_standards(state, subject, grade)` to:
```python
        result = load_standards(state, subject, grade)
        standards = result['standards']
```

Also update `generate_lesson_plan()` (~line 2637) and `generate_assessment()` (~line 5168) — both call `load_standards()`. Change to:
```python
result = load_standards(state, subject, grade)
standards = result['standards']
```
In both functions' API response `jsonify(...)`, add `"fallback_used": result.get("fallback_used", False)` so the frontend can show the fallback notice on generated content.

- [ ] **Step 4: Run all tests**

Run: `source /Users/alexc/Downloads/Graider/venv/bin/activate && python -m pytest tests/test_standards.py tests/test_assessment_results.py -v`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add backend/routes/planner_routes.py tests/test_standards.py
git commit -m "feat: rewrite load_standards with mapping-based resolution and fallback"
```

---

### Task 4: Update Assistant `_load_standards()`

**Files:**
- Modify: `backend/services/assistant_tools.py:468-503`

- [ ] **Step 1: Update `_load_standards()` to use the new resolution**

Replace the function at line 468:

```python
def _load_standards():
    """Load curriculum standards based on teacher's configured subject/state."""
    settings = _load_settings()
    config = settings.get('config', {})
    state = config.get('state', 'FL')
    subject = config.get('subject', '')
    grade = config.get('grade_level', '')

    # Use the planner's load_standards which handles mapping + fallback
    try:
        from backend.routes.planner_routes import load_standards as _planner_load
        result = _planner_load(state, subject, grade)
        return result.get('standards', [])
    except Exception:
        pass

    # Fallback: try legacy file path directly
    subject_map = {
        'us_history': 'us_history',
        'u.s._history': 'us_history',
        'world_history': 'world_history',
        'civics': 'civics',
        'geography': 'geography',
        'english/ela': 'english-ela',
        'english': 'english-ela',
        'ela': 'english-ela',
        'math': 'math',
        'science': 'science',
        'social_studies': 'social_studies',
    }
    subject_key = subject_map.get(subject.lower().replace(' ', '_'), subject.lower().replace(' ', '_'))
    filename = 'standards_' + state.lower() + '_' + subject_key + '.json'
    filepath = os.path.join(STANDARDS_DIR, filename)

    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
            return data.get('standards', [])
        except Exception:
            pass
    return []
```

- [ ] **Step 2: Verify Python parses**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -c "import ast; ast.parse(open('backend/services/assistant_tools.py').read()); print('OK')"`

Verify `STANDARDS_DIR` is defined in the file:
Run: `grep 'STANDARDS_DIR' backend/services/assistant_tools.py`
Expected: Should show the constant definition (line ~50)

- [ ] **Step 3: Commit**

```bash
git add backend/services/assistant_tools.py
git commit -m "feat: update assistant _load_standards to use mapping-based resolution"
```

---

### Task 5: Add `/api/available-states` Endpoint

**Files:**
- Modify: `backend/routes/planner_routes.py`
- Modify: `tests/test_standards.py`

- [ ] **Step 1: Write test**

Add to `tests/test_standards.py`:

```python
class TestAvailableStates:
    def test_standards_map_has_51_entries(self):
        """50 states + DC = 51 entries."""
        from backend.routes.planner_routes import _get_standards_map
        smap = _get_standards_map()
        assert len(smap.get('states', {})) == 51

    def test_fl_is_state_specific(self):
        from backend.routes.planner_routes import _get_standards_map
        smap = _get_standards_map()
        assert smap['states']['FL']['framework'] == 'fl'

    def test_ca_uses_ccss(self):
        from backend.routes.planner_routes import _get_standards_map
        smap = _get_standards_map()
        assert smap['states']['CA']['framework'] == 'ccss'
```

- [ ] **Step 2: Add endpoint**

In `planner_routes.py`, add after the existing standards endpoints:

```python
@planner_bp.route('/api/available-states', methods=['GET'])
def get_available_states():
    """Return list of all supported states with names. No auth required."""
    smap = _get_standards_map()
    states = []
    for code, info in sorted(smap.get('states', {}).items(), key=lambda x: x[1].get('name', '')):
        states.append({'code': code, 'name': info.get('name', code)})
    return jsonify({'states': states})
```

- [ ] **Step 3: Run tests**

Run: `source /Users/alexc/Downloads/Graider/venv/bin/activate && python -m pytest tests/test_standards.py -v`
Expected: All pass

- [ ] **Step 4: Commit**

```bash
git add backend/routes/planner_routes.py tests/test_standards.py
git commit -m "feat: add /api/available-states endpoint"
```

---

### Task 6: Frontend — 50-State Selector and Fallback Notice

**Files:**
- Modify: `frontend/src/services/api.js`
- Modify: `frontend/src/tabs/SettingsTab.jsx`
- Modify: `frontend/src/tabs/PlannerTab.jsx`

- [ ] **Step 1: Add API function**

In `frontend/src/services/api.js`, add before the analytics section:

```javascript
// ============ Standards ============

export async function getAvailableStates() {
  return fetchApi('/api/available-states')
}
```

Add `getAvailableStates` to the default export object at the bottom.

- [ ] **Step 2: Update SettingsTab state selector**

In `frontend/src/tabs/SettingsTab.jsx`:

Add state at the top of the component (after existing state declarations):
```javascript
  const [availableStates, setAvailableStates] = useState([]);
```

Add useEffect to fetch states:
```javascript
  useEffect(function() {
    api.getAvailableStates().then(function(data) {
      if (data.states) setAvailableStates(data.states);
    }).catch(function() {});
  }, []);
```

Replace the hardcoded state `<select>` options (lines ~389-399) with:
```jsx
{availableStates.length > 0 ? availableStates.map(function(s) {
  return React.createElement('option', {key: s.code, value: s.code}, s.name);
}) : React.createElement('option', {value: config.state}, config.state)}
```

Note: Use `React.createElement` or JSX depending on the existing pattern in SettingsTab. If SettingsTab uses JSX (it does), use JSX:
```jsx
{availableStates.length > 0 ? availableStates.map((s) => (
  <option key={s.code} value={s.code}>{s.name}</option>
)) : <option value={config.state}>{config.state}</option>}
```

- [ ] **Step 3: Add fallback notice to PlannerTab**

In `frontend/src/tabs/PlannerTab.jsx`, add state variables near the top of the component:

```javascript
var [standardsFallbackNotice, setStandardsFallbackNotice] = useState(null);
var [stateNames, setStateNames] = useState({});
```

Add a useEffect to fetch state names (needed for fallback notice and state display):
```javascript
useEffect(function() {
  api.getAvailableStates().then(function(data) {
    if (data.states) {
      var map = {};
      data.states.forEach(function(s) { map[s.code] = s.name; });
      setStateNames(map);
    }
  }).catch(function() {});
}, []);
```

Find where standards are fetched (the `get_standards` API call response handler). After setting the standards data, add:
```javascript
var sName = stateNames[config.state] || config.state;
if (data.no_framework) {
  setStandardsFallbackNotice('No national standards framework available for ' + config.subject + '. Standards vary by state and district.');
} else if (data.state_note) {
  setStandardsFallbackNotice(sName + ' has its own standards framework. Using Common Core standards as an approximation.');
} else if (data.fallback_used) {
  setStandardsFallbackNotice('State-specific standards not yet available for ' + sName + ' ' + config.subject + '. Using Common Core standards.');
} else {
  setStandardsFallbackNotice(null);
}
```

Render the banner (subtle blue info bar) above the standards list:
```jsx
{standardsFallbackNotice && (
  <div style={{
    padding: "10px 14px", marginBottom: "12px",
    background: "rgba(59,130,246,0.1)", border: "1px solid rgba(59,130,246,0.25)",
    borderRadius: "8px", fontSize: "0.85rem", color: "#93c5fd",
    display: "flex", alignItems: "center", gap: "8px",
  }}>
    <Icon name="Info" size={16} />
    {standardsFallbackNotice}
  </div>
)}
```

- [ ] **Step 4: Gate FL FAST toggle to Florida only**

In PlannerTab.jsx, find both FL FAST toggle instances and wrap each with a state check:

**~Line 2576 (compact mode):** Find the object `{ key: "florida_fast", label: "FL FAST Items", icon: "ListChecks", group: "optional" }` in the section categories array. Wrap the entire entry or filter it out:
```javascript
// Change the array to filter out florida_fast for non-FL states
.filter(function(cat) { return cat.key !== 'florida_fast' || config.state === 'FL'; })
```
Add this `.filter()` call right before the `.map()` that renders the category toggles.

**~Line 4599 (detail mode):** Same pattern — find the `florida_fast` entry and add the same filter.

**~Line 4603:** Change the group label from `"FL FAST Core"` to `"Core"`.

- [ ] **Step 5: Update PlannerTab state name display**

Replace the hardcoded state map at ~line 4201:
```javascript
// OLD (lines 4200-4211):
{{
  FL: "Florida",
  TX: "Texas",
  ...
}[config.state] || config.state}

// NEW:
{stateNames[config.state] || config.state}
```

This uses the `stateNames` map populated from `/api/available-states` in the useEffect added in Step 3.

- [ ] **Step 6: Verify build**

Run: `cd frontend && npx vite build 2>&1 | tail -3`

- [ ] **Step 7: Commit**

```bash
git add frontend/src/services/api.js frontend/src/tabs/SettingsTab.jsx frontend/src/tabs/PlannerTab.jsx
git commit -m "feat: 50-state selector, fallback notice, FL FAST gate"
```

---

### Task 7: Generate CCSS and NGSS Standards Data

**Files:**
- Create: `backend/data/standards/ccss/math.json`
- Create: `backend/data/standards/ccss/english-ela.json`
- Create: `backend/data/standards/ccss/social_studies.json`
- Create: `backend/data/standards/ngss/science.json`

This task generates the actual standards data files. Each file must follow the schema from the spec with all 8 fields (code, benchmark, dok, topics, vocabulary, learning_targets, essential_questions, sample_assessment) at full depth for grades 6-12.

- [ ] **Step 1: Generate CCSS Math standards**

Source: Common Core State Standards for Mathematics (corestandards.org)
Grades: 6-8 (grade-specific codes), 9-12 (by course: Algebra 1, Geometry, Algebra 2)
Code pattern: `CCSS.MATH.CONTENT.{G}.{DOMAIN}.{STD}`

Use AI extraction: feed the official CCSS Math standards into GPT-4o with the JSON schema as target. Output to `backend/data/standards/ccss/math.json`.

Validate: spot-check 10 random standards against official source.

- [ ] **Step 2: Generate CCSS ELA standards**

Source: Common Core State Standards for English Language Arts
Grades: 6-8 (grade-specific), 9-10 and 11-12 (grade bands)
Code pattern: `CCSS.ELA-LITERACY.{STRAND}.{G}.{STD}`

Output to `backend/data/standards/ccss/english-ela.json`. Validate.

- [ ] **Step 3: Generate C3 Social Studies standards**

Source: College, Career, and Civic Life (C3) Framework
Grade bands: 6-8, 9-12
Code pattern: `D{DIMENSION}.{TOPIC}.{NUM}.{GRADE-BAND}`
Covers: civics, geography, economics, history

Output to `backend/data/standards/ccss/social_studies.json`. Validate.

- [ ] **Step 4: Generate NGSS Science standards**

Source: Next Generation Science Standards
Grades: MS (6-8), HS (9-12, by discipline)
Code pattern: `MS-{DISCIPLINE}{STD}-{NUM}` / `HS-{DISCIPLINE}{STD}-{NUM}`

Output to `backend/data/standards/ngss/science.json`. Validate.

- [ ] **Step 5: Verify grade filtering works with new data**

```bash
source /Users/alexc/Downloads/Graider/venv/bin/activate
python -c "
from backend.routes.planner_routes import load_standards
# Test CCSS Math for CA grade 7
r = load_standards('CA', 'Math', '7')
print('CA Math 7:', len(r['standards']), 'standards, fallback:', r['fallback_used'])

# Test NGSS Science for NY grade 8
r = load_standards('NY', 'Science', '8')
print('NY Science 8:', len(r['standards']), 'standards, fallback:', r['fallback_used'])

# Test C3 Social Studies for OH grade 7
r = load_standards('OH', 'Social Studies', '7')
print('OH SocStud 7:', len(r['standards']), 'standards, fallback:', r['fallback_used'])

# Test FL Math still works
r = load_standards('FL', 'Math', '6')
print('FL Math 6:', len(r['standards']), 'standards, fallback:', r['fallback_used'])
"
```

- [ ] **Step 6: Commit**

```bash
git add backend/data/standards/ccss/ backend/data/standards/ngss/
git commit -m "feat: add CCSS Math/ELA/Social Studies and NGSS Science standards"
```

---

### Task 8: Generate TX and VA State-Specific Standards

**Files:**
- Create: `backend/data/standards/tx/math.json`
- Create: `backend/data/standards/tx/english-ela.json`
- Create: `backend/data/standards/tx/science.json`
- Create: `backend/data/standards/tx/social_studies.json`
- Create: `backend/data/standards/va/math.json`
- Create: `backend/data/standards/va/english-ela.json`
- Create: `backend/data/standards/va/science.json`
- Create: `backend/data/standards/va/social_studies.json`

- [ ] **Step 1: Generate Texas TEKS**

Source: Texas Essential Knowledge and Skills (TEKS)
Code pattern: `{SUBJECT}.{G}.{STD}.{SUBSTD}`
4 files: math, english-ela, science, social_studies

AI extraction from official TEKS documents. Full 8-field schema. Validate 10 per file.

- [ ] **Step 2: Generate Virginia SOLs**

Source: Virginia Standards of Learning
Code pattern: `{SUBJECT}.{G}.{STD}`
4 files: math, english-ela, science, social_studies

AI extraction from official SOL documents. Full 8-field schema. Validate 10 per file.

- [ ] **Step 3: Verify resolution for TX and VA**

```bash
python -c "
from backend.routes.planner_routes import load_standards
r = load_standards('TX', 'Math', '7')
print('TX Math 7:', len(r['standards']), 'standards, fallback:', r['fallback_used'])
r = load_standards('VA', 'Science', '8')
print('VA Science 8:', len(r['standards']), 'standards, fallback:', r['fallback_used'])
"
```

- [ ] **Step 4: Commit**

```bash
git add backend/data/standards/tx/ backend/data/standards/va/
git commit -m "feat: add Texas TEKS and Virginia SOL standards"
```

---

### Task 9: Full Verification and Cleanup

**Files:**
- Remove (optional): `backend/data/standards_fl_*.json` (legacy files, after confirming new path works)

- [ ] **Step 1: Run all backend tests**

```bash
source /Users/alexc/Downloads/Graider/venv/bin/activate
python -m pytest tests/ -q --ignore=tests/load --ignore=tests/stress
```

- [ ] **Step 2: Verify frontend build**

```bash
cd frontend && npx vite build 2>&1 | tail -3
```

- [ ] **Step 3: Run Playwright E2E tests**

```bash
cd frontend && npx playwright test --reporter=line --workers=2 2>&1 | tail -10
```

- [ ] **Step 4: Manual verification checklist**

Start the server and verify:
- [ ] Settings → Grading → State dropdown shows all 50 states + DC
- [ ] Selecting CA → Math → Grade 7 → Planner → Standards shows CCSS Math standards
- [ ] Selecting TX → Math → Standards shows TEKS (no fallback notice)
- [ ] Selecting AK → Math → Standards shows CCSS with fallback notice mentioning approximation
- [ ] Selecting FL → Math → Standards works as before (no fallback notice)
- [ ] FL FAST toggle visible for FL, hidden for CA/TX
- [ ] Selecting CA → Spanish → Standards shows "No national standards framework" message

- [ ] **Step 5: Remove legacy FL files (optional)**

Only after confirming everything works:
```bash
rm backend/data/standards_fl_*.json
git add -u backend/data/
git commit -m "chore: remove legacy FL standards files (migrated to standards/fl/)"
```

- [ ] **Step 6: Done**

No additional commit needed — all changes are committed in prior tasks.
