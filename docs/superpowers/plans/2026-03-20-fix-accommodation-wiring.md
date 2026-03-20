# Fix Accommodation Wiring Implementation Plan (v2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the broken accommodation pipeline so IEP/504 presets actually modify AI grading prompts for portal submissions (both join-code and Clever paths), and add delivery accommodations (extended time, large text, read-aloud, reduced distractions) to the student portal UI.

**Architecture:** Accommodation data is embedded in `published_assessments.settings.student_accommodations` (join-code) and `published_content.settings.student_accommodations` (class-based), keyed by student name. The fix: (1) add new functions that build AI prompts directly from preset IDs without needing a student_id lookup, (2) pass the `student_accommodations` dict to all three grading thread spawn sites, (3) add delivery presets that the frontend reads and applies as UI modifications. The Clever student flow (recently fixed) already uses `StudentPortal.jsx` for taking assessments, so delivery accommodations apply to both paths.

**Tech Stack:** Python/Flask (backend), React (frontend), Web Speech API (read-aloud)

**Spec:** `docs/superpowers/specs/2026-03-20-content-types-accommodations-assets-design.md`

**What was already fixed (prior commit `307ea04`):**
- `StudentPortal.jsx` accepts props from `StudentDashboard.jsx` (Clever path)
- `StudentDashboard.jsx` passes `preloadedSettings` to `StudentPortal`
- `get_student_content` normalizes `question_type` → `type`
- Class-based submissions use authenticated endpoint

## Clever Data Flow Verification

Both paths end up in `StudentPortal.jsx` — there is NO separate Clever assessment-taking component:

**Join-code:** Browser → `/join/CODE` → `StudentPortal` (standalone) → `GET /api/student/join/<code>` → response includes `student_accommodations` at top level

**Clever:** Browser → `/student` → `StudentApp` → `StudentDashboard` → click assignment → `GET /api/student/content/<id>` → response includes `settings.student_accommodations` → `StudentDashboard` passes `preloadedSettings` → `StudentPortal` merges into `assessment.student_accommodations` (line 52)

**Key Clever detail:** Preloaded students skip the "name" stage (go straight to "assessment"), so `handleStartAssessment()` is never called. This is why Task 3 adds a `useEffect` that detects accommodations on mount for preloaded students — without this, Clever students would never trigger accommodation detection even though the data is present.

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `backend/accommodations.py` | Modify | Add delivery presets, `build_prompt_from_presets()`, `build_prompt_from_student_accommodations()`, `get_delivery_accommodations()` |
| `backend/services/portal_grading.py` | Modify | Accept `student_accommodations` param, use new prompt builder |
| `backend/routes/student_portal_routes.py` | Modify | Pass `student_accommodations` to grading thread (join-code path) |
| `backend/routes/student_account_routes.py` | Modify | Extend `select` to include `settings`, pass accommodations to grading thread (class-based + teacher regrade) |
| `frontend/src/components/StudentPortal.jsx` | Modify | Apply delivery accommodations (extended time, large text, read-aloud, reduced distractions) |
| `tests/test_accommodation_wiring.py` | Create | Tests for new accommodation functions and wiring |

---

### Task 1: Add delivery presets and prompt builder functions to accommodations.py

**Files:**
- Modify: `backend/accommodations.py:189` (add delivery presets after `ell_support`), `:465+` (add new functions)
- Create: `tests/test_accommodation_wiring.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_accommodation_wiring.py`:

```python
"""Tests for accommodation prompt building from presets."""
import pytest


class TestBuildPromptFromPresets:
    """Test building accommodation prompts directly from preset data."""

    def test_builds_prompt_from_preset_ids(self):
        from backend.accommodations import build_prompt_from_presets
        result = build_prompt_from_presets(
            preset_ids=["simplified_language", "effort_focused"],
            custom_notes="",
        )
        assert "SIMPLIFIED LANGUAGE" in result
        assert "EFFORT-FOCUSED" in result

    def test_includes_custom_notes(self):
        from backend.accommodations import build_prompt_from_presets
        result = build_prompt_from_presets(
            preset_ids=[],
            custom_notes="This student needs extra time to process questions.",
        )
        assert "extra time to process" in result

    def test_empty_presets_returns_empty(self):
        from backend.accommodations import build_prompt_from_presets
        result = build_prompt_from_presets(preset_ids=[], custom_notes="")
        assert result == ""

    def test_unknown_preset_id_skipped(self):
        from backend.accommodations import build_prompt_from_presets
        result = build_prompt_from_presets(
            preset_ids=["simplified_language", "nonexistent_preset"],
            custom_notes="",
        )
        assert "SIMPLIFIED LANGUAGE" in result

    def test_delivery_presets_skipped_in_ai_prompt(self):
        """Delivery presets should NOT add AI instructions (they affect UI only)."""
        from backend.accommodations import build_prompt_from_presets
        result = build_prompt_from_presets(
            preset_ids=["extended_time_1_5x", "large_text"],
            custom_notes="",
        )
        assert result == ""

    def test_mixed_presets_only_include_ai_ones(self):
        from backend.accommodations import build_prompt_from_presets
        result = build_prompt_from_presets(
            preset_ids=["simplified_language", "extended_time_1_5x"],
            custom_notes="",
        )
        assert "SIMPLIFIED LANGUAGE" in result
        assert "extended_time" not in result.lower()

    def test_delivery_presets_exist(self):
        from backend.accommodations import DEFAULT_PRESETS
        assert "extended_time_1_5x" in DEFAULT_PRESETS
        assert "extended_time_2x" in DEFAULT_PRESETS
        assert "extended_time_unlimited" in DEFAULT_PRESETS
        assert "large_text" in DEFAULT_PRESETS
        assert "read_aloud" in DEFAULT_PRESETS
        assert "reduced_distractions" in DEFAULT_PRESETS

    def test_delivery_presets_have_delivery_type(self):
        from backend.accommodations import DEFAULT_PRESETS
        for key in ["extended_time_1_5x", "extended_time_2x", "extended_time_unlimited",
                     "large_text", "read_aloud", "reduced_distractions"]:
            assert DEFAULT_PRESETS[key].get("type") == "delivery"


class TestBuildPromptFromStudentAccommodations:
    """Test looking up a student by name from published accommodation dict."""

    def test_finds_student_by_exact_name(self):
        from backend.accommodations import build_prompt_from_student_accommodations
        accom = {"Jane Doe": {"presets": ["simplified_language"], "custom_notes": ""}}
        result = build_prompt_from_student_accommodations("Jane Doe", accom)
        assert "SIMPLIFIED LANGUAGE" in result

    def test_finds_student_case_insensitive(self):
        from backend.accommodations import build_prompt_from_student_accommodations
        accom = {"Jane Doe": {"presets": ["effort_focused"], "custom_notes": ""}}
        result = build_prompt_from_student_accommodations("jane doe", accom)
        assert "EFFORT-FOCUSED" in result

    def test_returns_empty_for_unknown_student(self):
        from backend.accommodations import build_prompt_from_student_accommodations
        result = build_prompt_from_student_accommodations(
            "Unknown", {"Jane Doe": {"presets": ["simplified_language"]}}
        )
        assert result == ""

    def test_returns_empty_for_none(self):
        from backend.accommodations import build_prompt_from_student_accommodations
        assert build_prompt_from_student_accommodations("Jane", None) == ""
        assert build_prompt_from_student_accommodations("Jane", {}) == ""


class TestGetDeliveryAccommodations:
    """Test extracting delivery preset IDs for frontend."""

    def test_extracts_delivery_presets(self):
        from backend.accommodations import get_delivery_accommodations
        accom = {
            "Jane Doe": {
                "presets": ["simplified_language", "extended_time_1_5x", "large_text"],
                "custom_notes": "",
            },
        }
        delivery = get_delivery_accommodations("Jane Doe", accom)
        assert "extended_time_1_5x" in delivery
        assert "large_text" in delivery
        assert "simplified_language" not in delivery

    def test_returns_empty_for_no_delivery(self):
        from backend.accommodations import get_delivery_accommodations
        accom = {"Jane Doe": {"presets": ["simplified_language"], "custom_notes": ""}}
        assert get_delivery_accommodations("Jane Doe", accom) == []

    def test_returns_empty_for_unknown_student(self):
        from backend.accommodations import get_delivery_accommodations
        assert get_delivery_accommodations("Unknown", {"Jane": {"presets": ["large_text"]}}) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_accommodation_wiring.py -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Add delivery presets to DEFAULT_PRESETS**

In `backend/accommodations.py`, after the closing `}` of the `ell_support` preset (line 189), before the closing `}` of `DEFAULT_PRESETS` (line 190), add:

```python
    # ── Delivery Accommodations (affect portal UI, not AI grading) ──
    "extended_time_1_5x": {
        "id": "extended_time_1_5x",
        "name": "Extended Time (1.5x)",
        "description": "50% additional time on timed assessments",
        "icon": "Clock",
        "type": "delivery",
        "time_multiplier": 1.5,
        "ai_instructions": "",
    },
    "extended_time_2x": {
        "id": "extended_time_2x",
        "name": "Extended Time (2x)",
        "description": "Double time on timed assessments",
        "icon": "Clock",
        "type": "delivery",
        "time_multiplier": 2.0,
        "ai_instructions": "",
    },
    "extended_time_unlimited": {
        "id": "extended_time_unlimited",
        "name": "Extended Time (Unlimited)",
        "description": "No time limit on timed assessments",
        "icon": "Clock",
        "type": "delivery",
        "time_multiplier": 0,
        "ai_instructions": "",
    },
    "large_text": {
        "id": "large_text",
        "name": "Large Text",
        "description": "Increase font size in student portal",
        "icon": "Type",
        "type": "delivery",
        "ai_instructions": "",
    },
    "read_aloud": {
        "id": "read_aloud",
        "name": "Read Aloud",
        "description": "Text-to-speech option for questions and answer choices",
        "icon": "Volume2",
        "type": "delivery",
        "ai_instructions": "",
    },
    "reduced_distractions": {
        "id": "reduced_distractions",
        "name": "Reduced Distractions",
        "description": "Simplified portal UI — hides progress bar and question count",
        "icon": "Eye",
        "type": "delivery",
        "ai_instructions": "",
    },
```

- [ ] **Step 4: Add new functions after `build_accommodation_prompt` (after line ~465)**

Add after the existing `build_accommodation_prompt` function in `backend/accommodations.py`:

```python
def _find_student_accommodation(student_name, student_accommodations):
    """Look up a student's accommodation by name (case-insensitive).

    Args:
        student_name: Student's full name
        student_accommodations: Dict from published content settings, keyed by name

    Returns:
        Accommodation dict or None.
    """
    if not student_name or not student_accommodations:
        return None

    # Exact match first
    accommodation = student_accommodations.get(student_name)
    if accommodation:
        return accommodation

    # Case-insensitive fallback
    normalized = student_name.strip().lower()
    for name, accom in student_accommodations.items():
        if name.strip().lower() == normalized:
            return accom

    return None


def build_prompt_from_presets(preset_ids, custom_notes="", teacher_id='local-dev'):
    """Build AI prompt instructions directly from preset IDs.

    Unlike build_accommodation_prompt() which looks up by student_id,
    this works with the preset list embedded in published content settings.
    Includes teacher's custom presets via load_presets().
    Skips delivery presets (they affect UI only, not AI grading).
    """
    if not preset_ids and not custom_notes:
        return ""

    presets = load_presets(teacher_id)

    # Filter to AI-affecting presets only (skip delivery presets)
    ai_preset_ids = [p for p in preset_ids if presets.get(p, {}).get("type") != "delivery"]

    if not ai_preset_ids and not custom_notes:
        return ""

    prompt_parts = [
        "",
        "═══════════════════════════════════════════════════════════",
        "ACCOMMODATION INSTRUCTIONS (Apply to all feedback below)",
        "═══════════════════════════════════════════════════════════",
        ""
    ]

    for preset_id in ai_preset_ids:
        preset = presets.get(preset_id)
        if preset and preset.get("ai_instructions"):
            prompt_parts.append(preset["ai_instructions"])
            prompt_parts.append("")

    if custom_notes:
        prompt_parts.append("ADDITIONAL ACCOMMODATION NOTES:")
        prompt_parts.append(custom_notes)
        prompt_parts.append("")

    prompt_parts.append("═══════════════════════════════════════════════════════════")
    prompt_parts.append("")

    return "\n".join(prompt_parts)


def build_prompt_from_student_accommodations(student_name, student_accommodations,
                                              teacher_id='local-dev'):
    """Look up a student by name in published accommodation dict and build AI prompt.

    Args:
        student_name: Student's full name as entered in the portal
        student_accommodations: Dict from published content settings, keyed by name
        teacher_id: For loading custom presets

    Returns:
        AI prompt string with accommodation instructions, or empty string.
    """
    accommodation = _find_student_accommodation(student_name, student_accommodations)
    if not accommodation:
        return ""

    return build_prompt_from_presets(
        preset_ids=accommodation.get("presets", []),
        custom_notes=accommodation.get("custom_notes", ""),
        teacher_id=teacher_id,
    )


def get_delivery_accommodations(student_name, student_accommodations):
    """Extract delivery-type preset IDs for a student.

    Returns list of delivery preset IDs (extended_time_1_5x, large_text, etc.)
    that the frontend should apply as UI modifications.
    """
    accommodation = _find_student_accommodation(student_name, student_accommodations)
    if not accommodation:
        return []

    return [
        p for p in accommodation.get("presets", [])
        if DEFAULT_PRESETS.get(p, {}).get("type") == "delivery"
    ]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_accommodation_wiring.py -v`
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add backend/accommodations.py tests/test_accommodation_wiring.py
git commit -m "feat: add delivery accommodation presets and direct prompt builders"
```

---

### Task 2: Wire accommodations into all three grading thread spawn sites

**Files:**
- Modify: `backend/services/portal_grading.py:178-207`
- Modify: `backend/routes/student_portal_routes.py:565-579`
- Modify: `backend/routes/student_account_routes.py:523-537` (teacher regrade), `:772` (extend select), `:849-863` (class-based submission)

- [ ] **Step 1: Update `run_portal_grading_thread` to accept and use student_accommodations**

In `backend/services/portal_grading.py`, replace lines 178-207:

Current:
```python
def run_portal_grading_thread(submission_id, assessment, answers, student_info,
                              teacher_config, teacher_id,
                              supabase_table="student_submissions"):
    ...
        # Build AI instruction string with all grading factors
        from backend.accommodations import build_accommodation_prompt

        accommodation_prompt = ""
        student_id = student_info.get("student_id", "")
        if student_id:
            try:
                accommodation_prompt = build_accommodation_prompt(student_id, teacher_id)
            except Exception:
                pass
```

Replace with:
```python
def run_portal_grading_thread(submission_id, assessment, answers, student_info,
                              teacher_config, teacher_id,
                              supabase_table="student_submissions",
                              student_accommodations=None):
    ...
        # Build AI instruction string with all grading factors
        accommodation_prompt = ""
        student_name = student_info.get("student_name", "")

        # Strategy 1: Use embedded accommodations from published content (works for both paths)
        if student_accommodations and student_name:
            try:
                from backend.accommodations import build_prompt_from_student_accommodations
                accommodation_prompt = build_prompt_from_student_accommodations(
                    student_name, student_accommodations, teacher_id
                )
            except Exception:
                pass

        # Strategy 2: Fall back to student_id lookup (works for class-based with roster data)
        if not accommodation_prompt:
            student_id = student_info.get("student_id", "")
            if student_id:
                try:
                    from backend.accommodations import build_accommodation_prompt
                    accommodation_prompt = build_accommodation_prompt(student_id, teacher_id)
                except Exception:
                    pass
```

- [ ] **Step 2: Pass student_accommodations from join-code submission (student_portal_routes.py:565-579)**

Replace lines 565-579:

Current:
```python
            import threading
            thread = threading.Thread(
                target=run_portal_grading_thread,
                args=(
                    submission_id,
                    assessment,
                    answers,
                    {"student_name": student_name, "student_id": "", "email": ""},
                    teacher_config,
                    teacher_id,
                    "submissions",  # Join-code submissions use "submissions" table
                ),
                daemon=True,
            )
            thread.start()
```

Replace with:
```python
            # Get student accommodations from published assessment settings
            published_accommodations = assessment_data.get("settings", {}).get("student_accommodations", {})

            import threading
            thread = threading.Thread(
                target=run_portal_grading_thread,
                args=(
                    submission_id,
                    assessment,
                    answers,
                    {"student_name": student_name, "student_id": "", "email": ""},
                    teacher_config,
                    teacher_id,
                    "submissions",
                ),
                kwargs={"student_accommodations": published_accommodations},
                daemon=True,
            )
            thread.start()
```

- [ ] **Step 3: Extend class-based submission select to include settings (student_account_routes.py:772)**

Replace line 772:
```python
        pc = db.table('published_content').select('content, title, teacher_id').eq(
```

With:
```python
        pc = db.table('published_content').select('content, title, teacher_id, settings').eq(
```

- [ ] **Step 4: Pass student_accommodations from class-based submission (student_account_routes.py:849-863)**

Replace lines 847-863:

Current:
```python
            try:
                import threading
                grading_thread = threading.Thread(
                    target=run_portal_grading_thread,
                    args=(
                        submission_id,
                        assessment_content,
                        answers,
                        {
                            "student_name": student_name,
                            "student_id": s.get("student_id_number", ""),
                            "email": s.get("email", ""),
                        },
                        teacher_config,
                        teacher_id,
                        "student_submissions",
                    ),
                    daemon=True,
                )
```

Replace with:
```python
            try:
                # Get accommodations from published content settings (already fetched at line 772)
                published_accommodations = pc.data[0].get('settings', {}).get('student_accommodations', {}) if pc.data else {}

                import threading
                grading_thread = threading.Thread(
                    target=run_portal_grading_thread,
                    args=(
                        submission_id,
                        assessment_content,
                        answers,
                        {
                            "student_name": student_name,
                            "student_id": s.get("student_id_number", ""),
                            "email": s.get("email", ""),
                        },
                        teacher_config,
                        teacher_id,
                        "student_submissions",
                    ),
                    kwargs={"student_accommodations": published_accommodations},
                    daemon=True,
                )
```

- [ ] **Step 5: Pass student_accommodations from teacher regrade (student_account_routes.py:523-537)**

Replace lines 523-537:

Current:
```python
            import threading
            thread = threading.Thread(
                target=run_portal_grading_thread,
                args=(
                    submission_id,
                    assessment,
                    student_answers,
                    {"student_name": student_name, "student_id": student_id_number, "email": ""},
                    teacher_config,
                    teacher_id,
                    "student_submissions",
                ),
                daemon=True,
            )
            thread.start()
```

Replace with:
```python
            # Get accommodations from published content (content var already holds select('*') result)
            published_accommodations = content.data[0].get('settings', {}).get('student_accommodations', {}) if content.data else {}

            import threading
            thread = threading.Thread(
                target=run_portal_grading_thread,
                args=(
                    submission_id,
                    assessment,
                    student_answers,
                    {"student_name": student_name, "student_id": student_id_number, "email": ""},
                    teacher_config,
                    teacher_id,
                    "student_submissions",
                ),
                kwargs={"student_accommodations": published_accommodations},
                daemon=True,
            )
            thread.start()
```

- [ ] **Step 6: Run all tests**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/ -k "clever or portal or accommodation" -q --ignore=tests/load`
Expected: All pass

- [ ] **Step 7: Commit**

```bash
git add backend/services/portal_grading.py backend/routes/student_portal_routes.py backend/routes/student_account_routes.py
git commit -m "fix: wire student accommodations into all three grading thread paths"
```

---

### Task 3: Add delivery accommodations to StudentPortal.jsx

Both join-code and Clever students use `StudentPortal.jsx` for taking assessments. Delivery accommodations are read from the `student_accommodations` data that's now available via both paths.

**Files:**
- Modify: `frontend/src/components/StudentPortal.jsx`

- [ ] **Step 1: Add delivery accommodation state and detection**

In `StudentPortal.jsx`, add state variable after the existing `studentAccommodation` state (around line 59):

```javascript
  const [deliveryAccommodations, setDeliveryAccommodations] = useState([]);
```

Update the accommodation detection in `handleStartAssessment` (around line 122-135). Replace the current accommodation check:

```javascript
    // Check if student has accommodations
    if (assessment?.student_accommodations) {
      const normalizedName = studentName.trim();
      const accommodation = assessment.student_accommodations[normalizedName];
      if (accommodation) {
        setStudentAccommodation(accommodation);
      }
```

With:
```javascript
    // Check if student has accommodations (case-insensitive name match)
    if (assessment?.student_accommodations) {
      var normalizedName = studentName.trim().toLowerCase();
      var matchedAccom = null;
      Object.entries(assessment.student_accommodations).forEach(function(entry) {
        if (entry[0].trim().toLowerCase() === normalizedName) {
          matchedAccom = entry[1];
        }
      });
      if (matchedAccom) {
        setStudentAccommodation(matchedAccom);
        var deliveryPresets = (matchedAccom.presets || []).filter(function(p) {
          return ["extended_time_1_5x", "extended_time_2x", "extended_time_unlimited",
                  "large_text", "read_aloud", "reduced_distractions"].indexOf(p) !== -1;
        });
        setDeliveryAccommodations(deliveryPresets);
      }
```

Also add a `useEffect` for the preloaded (Clever) path — after the existing preload useEffect (around line 70):
```javascript
  // Auto-detect accommodations for preloaded (Clever) students
  useEffect(() => {
    if (isPreloaded && preloadedStudentName && assessment && assessment.student_accommodations) {
      var normalizedName = preloadedStudentName.trim().toLowerCase();
      var matchedAccom = null;
      Object.entries(assessment.student_accommodations).forEach(function(entry) {
        if (entry[0].trim().toLowerCase() === normalizedName) {
          matchedAccom = entry[1];
        }
      });
      if (matchedAccom) {
        setStudentAccommodation(matchedAccom);
        var deliveryPresets = (matchedAccom.presets || []).filter(function(p) {
          return ["extended_time_1_5x", "extended_time_2x", "extended_time_unlimited",
                  "large_text", "read_aloud", "reduced_distractions"].indexOf(p) !== -1;
        });
        setDeliveryAccommodations(deliveryPresets);
      }
    }
  }, [isPreloaded, preloadedStudentName, assessment]);
```

- [ ] **Step 2: Apply extended time**

In the assessment stage, compute the effective time limit as a derived variable (do NOT mutate state):

At the top of the assessment stage rendering (around `if (stage === "assessment")`), add:
```javascript
    // Compute effective time limit with extended time accommodation
    var effectiveTimeLimit = assessment?.settings?.time_limit_minutes || null;
    if (effectiveTimeLimit && deliveryAccommodations.length > 0) {
      if (deliveryAccommodations.indexOf("extended_time_unlimited") !== -1) {
        effectiveTimeLimit = null;
      } else if (deliveryAccommodations.indexOf("extended_time_2x") !== -1) {
        effectiveTimeLimit = Math.round(effectiveTimeLimit * 2);
      } else if (deliveryAccommodations.indexOf("extended_time_1_5x") !== -1) {
        effectiveTimeLimit = Math.round(effectiveTimeLimit * 1.5);
      }
    }
```

Use `effectiveTimeLimit` wherever the timer displays instead of `assessment.settings.time_limit_minutes`.

- [ ] **Step 3: Apply large text**

At the top of the assessment stage, compute:
```javascript
    var isLargeText = deliveryAccommodations.indexOf("large_text") !== -1;
    var portalFontSize = isLargeText ? "1.2rem" : "1rem";
```

Apply `style={{ fontSize: portalFontSize }}` to the question rendering container.

- [ ] **Step 4: Apply read-aloud**

At the top of the assessment stage:
```javascript
    var isReadAloud = deliveryAccommodations.indexOf("read_aloud") !== -1;
```

After each question text rendering (around line 448, after `{q.question}`), add:
```javascript
                    {isReadAloud && (
                      <button
                        onClick={function() {
                          var utterance = new SpeechSynthesisUtterance(q.question);
                          utterance.rate = 0.9;
                          window.speechSynthesis.cancel();
                          window.speechSynthesis.speak(utterance);
                        }}
                        style={{
                          background: "none", border: "none", cursor: "pointer",
                          color: "rgba(99,102,241,0.8)", padding: "4px", marginLeft: "8px",
                          verticalAlign: "middle",
                        }}
                        title="Read aloud"
                      >
                        <Icon name="Volume2" size={18} />
                      </button>
                    )}
```

- [ ] **Step 5: Apply reduced distractions**

At the top of the assessment stage:
```javascript
    var isReducedDistractions = deliveryAccommodations.indexOf("reduced_distractions") !== -1;
```

Use `isReducedDistractions` to conditionally hide progress indicators (question count, progress bar). Show timer only when under 5 minutes remaining.

- [ ] **Step 6: Build frontend**

Run: `cd /Users/alexc/Downloads/Graider/frontend && npm run build`
Expected: Clean build

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/StudentPortal.jsx
git commit -m "feat: delivery accommodations in student portal (extended time, large text, read-aloud, reduced distractions)"
```

---

### Task 4: Full end-to-end verification

- [ ] **Step 1: Run all tests**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/ -k "clever or portal or accommodation" -v --ignore=tests/load`
Expected: All pass

- [ ] **Step 2: Build frontend**

Run: `cd /Users/alexc/Downloads/Graider/frontend && npm run build`
Expected: Clean build

- [ ] **Step 3: Verify imports**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -c "from backend.accommodations import build_prompt_from_presets, build_prompt_from_student_accommodations, get_delivery_accommodations, DEFAULT_PRESETS; delivery = [k for k in DEFAULT_PRESETS if DEFAULT_PRESETS[k].get('type') == 'delivery']; print('Delivery presets:', delivery); print('OK')"`
Expected: Lists 6 delivery presets + OK

- [ ] **Step 4: Manual test flow**

1. In Settings > Student Accommodations, assign a test student presets: `simplified_language` + `extended_time_1_5x`
2. Publish an assessment with time limit (10 minutes), selecting that student's period
3. **Join-code path**: Go to `/join/CODE`, enter the student's exact name
   - Verify: timer shows 15 minutes (1.5x extended), read-aloud button appears if enabled
   - Submit with written questions
   - Check Results tab — verify accommodation instructions were included in grading
4. **Clever path**: Log in as that student at `/student`, click the assignment
   - Verify: same accommodations apply (extended time, etc.)
   - Verify: "Back to Dashboard" button on results screen

- [ ] **Step 5: Commit**

```bash
git add backend/services/portal_grading.py backend/routes/student_portal_routes.py backend/routes/student_account_routes.py backend/accommodations.py frontend/src/components/StudentPortal.jsx tests/test_accommodation_wiring.py
git commit -m "feat: fix accommodation wiring — IEP presets apply to grading + delivery accommodations in portal"
```
