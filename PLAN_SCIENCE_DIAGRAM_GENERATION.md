# Science Diagram Generation — Full Lifecycle Implementation Plan

## Overview

Add AI-generated science diagrams to assessments and assignments using Gemini 3 Pro Image (Nano Banana Pro). Covers the complete lifecycle: generation → teacher preview → regeneration → PDF export → student portal → AI grading → analytics.

---

## Architecture

### Question Object Schema (New Fields)

```python
{
    "question": "Label the parts of the cell shown in the diagram below.",
    "question_type": "short_answer",
    "answer": "A=nucleus, B=mitochondria, C=cell membrane, D=chloroplast",
    "points": 4,
    "diagram": {                          # NEW — entire diagram block
        "image_b64": "<base64 png>",      # generated image data
        "prompt": "Labeled animal cell diagram showing nucleus (A), mitochondria (B), cell membrane (C), endoplasmic reticulum (D). Educational style, clean labels with arrows, white background, no color fills.",
        "source": "gemini",               # provenance tracking
        "model": "gemini-2.0-flash-preview-image-generation",
        "verified": false,                # teacher hasn't confirmed accuracy
        "generation_id": "uuid4"          # for cache/regen tracking
    },
    "warning": "AI-generated diagram — verify labels before publishing",
    "warning_severity": "warning"
}
```

**Why `diagram.prompt` does triple duty:**
1. **Regeneration** — re-send to Gemini (or edit and re-send)
2. **Grading context** — pass to grader so it knows what the diagram shows (avoids sending the actual image, saves tokens for portal grading)
3. **Validation** — teacher can read the prompt to understand what was intended

### Storage Strategy

**Base64 inline in JSON** — chosen over file storage because:
- Portable: assignment JSON is self-contained, no external dependencies
- Works with Railway's ephemeral filesystem
- No image-serving endpoint needed
- Typical science diagram: 50-150KB base64 (acceptable)
- Worst case: 10 diagram questions × 150KB = 1.5MB added to assignment JSON

### API Key

Requires `GOOGLE_API_KEY` environment variable (Gemini API key). Add to Railway env vars and `.env`.

---

## Phase 1: Gemini Image Generation Utility

### New file: `backend/utils/diagram_generator.py`

```python
"""AI diagram generation for science assessment questions using Gemini."""
import os
import json
import base64
import uuid
import re
from pathlib import Path


# Question text patterns that suggest a diagram would help
_DIAGRAM_TRIGGER_RE = re.compile(
    r'\b('
    r'label (the |each |all )?parts?'
    r'|identify (the |each )?(structure|organ|part|component|layer|section)'
    r'|refer to the (diagram|figure|image|illustration|model|picture)'
    r'|the (diagram|figure|image|illustration) (below |above )?(shows|represents|displays|illustrates)'
    r'|shown in the (diagram|figure|image|illustration)'
    r'|use the (diagram|figure|image|illustration)'
    r'|look at the (diagram|figure|model|picture|illustration)'
    r'|examine the (diagram|figure|model|cell|circuit|setup)'
    r'|observe the (diagram|figure|setup|experiment|apparatus)'
    r')\b',
    re.IGNORECASE,
)

# Science topics where diagrams add value even without explicit reference
_SCIENCE_DIAGRAM_TOPICS = re.compile(
    r'\b('
    r'cell (membrane|wall|diagram|structure|organelle)'
    r'|animal cell|plant cell|prokaryotic|eukaryotic'
    r'|food (web|chain|pyramid)|energy pyramid|trophic level'
    r'|water cycle|carbon cycle|nitrogen cycle|rock cycle'
    r'|solar system|phases of the moon|lunar phases'
    r'|layers of the earth|earth.s (crust|mantle|core)|tectonic plates?'
    r'|punnett square|genotype|phenotype|dominant.*recessive'
    r'|circuit (diagram|series|parallel)|resistor|capacitor|voltage'
    r'|atom(ic)? (model|structure)|electron (cloud|shell|orbital)'
    r'|periodic table|element|compound'
    r'|force diagram|free body|newton.s (first|second|third)'
    r'|wave (diagram|amplitude|frequency|wavelength)'
    r'|ph scale|acid.*base'
    r'|human (body|skeleton|digestive|circulatory|respiratory|nervous)'
    r'|photosynthesis|cellular respiration'
    r'|ecosystem|biome|habitat'
    r'|states of matter|phase change|melting|boiling|condensation'
    r')\b',
    re.IGNORECASE,
)

# Default diagram prompts by detected topic
_TOPIC_DIAGRAM_PROMPTS = {
    'animal_cell': 'Scientific diagram of an animal cell with labeled parts: nucleus, mitochondria, cell membrane, endoplasmic reticulum (rough and smooth), Golgi apparatus, ribosomes, lysosomes, cytoplasm. Clean educational style, white background, clear labeled arrows, no artistic embellishment.',
    'plant_cell': 'Scientific diagram of a plant cell with labeled parts: cell wall, cell membrane, nucleus, chloroplast, central vacuole, mitochondria, endoplasmic reticulum, Golgi apparatus, ribosomes, cytoplasm. Clean educational style, white background, clear labeled arrows.',
    'food_web': 'Scientific food web diagram showing producers (grass, algae), primary consumers (rabbit, grasshopper), secondary consumers (snake, frog), tertiary consumers (hawk, fox), and decomposers. Arrows show energy flow direction. Clean educational style, labeled organisms.',
    'water_cycle': 'Scientific diagram of the water cycle showing: evaporation, condensation, precipitation, collection, transpiration, runoff, groundwater flow. Clean labeled arrows on a landscape cross-section with ocean, mountains, and clouds. Educational style.',
    'solar_system': 'Diagram of the solar system showing all 8 planets in order from the Sun with labels: Mercury, Venus, Earth, Mars, Jupiter, Saturn, Uranus, Neptune. Relative size approximately correct. Educational style, clean labels.',
    'earth_layers': 'Cross-section diagram of Earth showing layers: inner core, outer core, mantle (upper and lower), crust. Include approximate temperatures and depths. Clean educational style with labels and arrows.',
    'punnett_square': 'A 2x2 Punnett square diagram with parent genotypes labeled on top and left side. Show clear grid lines and spaces for student to fill in offspring genotypes. Clean educational style.',
    'simple_circuit': 'Simple electrical circuit diagram showing a battery, wires, switch, and light bulb connected in series. Include standard circuit symbols. Clean educational style with labels.',
    'atom_model': 'Bohr model diagram of an atom showing nucleus (protons and neutrons) and electron shells/energy levels with electrons. Include labels for protons, neutrons, electrons, and shells. Clean educational style.',
    'wave_diagram': 'Labeled wave diagram showing: amplitude, wavelength, crest, trough, equilibrium/rest position. Two complete wave cycles. Clean educational style with measurement arrows.',
    'ph_scale': 'pH scale diagram from 0 to 14, color-coded from red (acidic) through green (neutral) to blue/purple (basic). Include common substance examples at key points (lemon juice, vinegar, water, baking soda, bleach). Clean educational style.',
    'photosynthesis': 'Diagram showing the process of photosynthesis in a chloroplast. Show inputs (water, CO2, sunlight) and outputs (glucose, oxygen). Include the chemical equation. Clean educational style with labeled arrows.',
    'states_of_matter': 'Diagram showing the three states of matter (solid, liquid, gas) with particle arrangement illustrations and labeled phase change arrows: melting, freezing, evaporation, condensation, sublimation, deposition. Clean educational style.',
}


def should_generate_diagram(question, subject=''):
    """Determine if a question would benefit from a generated diagram.

    Returns (should_generate: bool, topic_key: str or None, custom_prompt: str or None)
    """
    text = question.get('question', '')
    qt = question.get('question_type', question.get('type', ''))

    # Skip if question already has interactive visual data
    if qt in ('data_table', 'box_plot', 'dot_plot', 'stem_and_leaf', 'bar_chart',
              'coordinate_plane', 'function_graph', 'geometry', 'triangle',
              'rectangle', 'circle', 'trapezoid', 'number_line', 'protractor',
              'transformations', 'fraction_model', 'venn_diagram', 'probability_tree',
              'tape_diagram', 'unit_circle'):
        return False, None, None

    # Skip if already has a diagram
    if question.get('diagram'):
        return False, None, None

    # Skip non-science subjects
    subject_lower = subject.lower()
    is_science = any(kw in subject_lower for kw in [
        'science', 'biology', 'chemistry', 'physics', 'earth',
        'environmental', 'anatomy', 'ecology', 'stem',
    ])
    if not is_science:
        return False, None, None

    # Check 1: Question explicitly references a diagram/figure
    if _DIAGRAM_TRIGGER_RE.search(text):
        topic = _detect_topic(text)
        return True, topic, None

    # Check 2: Question involves a diagrammable science topic
    if _SCIENCE_DIAGRAM_TOPICS.search(text):
        topic = _detect_topic(text)
        return True, topic, None

    return False, None, None


def _detect_topic(text):
    """Detect the specific science topic from question text for prompt selection."""
    text_lower = text.lower()
    if any(w in text_lower for w in ['animal cell', 'cell membrane', 'organelle']):
        if 'plant' in text_lower or 'cell wall' in text_lower or 'chloroplast' in text_lower:
            return 'plant_cell'
        return 'animal_cell'
    if any(w in text_lower for w in ['food web', 'food chain', 'trophic', 'energy pyramid']):
        return 'food_web'
    if 'water cycle' in text_lower:
        return 'water_cycle'
    if any(w in text_lower for w in ['solar system', 'planet']):
        return 'solar_system'
    if any(w in text_lower for w in ['layers of the earth', 'crust', 'mantle', 'core']):
        return 'earth_layers'
    if any(w in text_lower for w in ['punnett', 'genotype', 'phenotype', 'dominant', 'recessive']):
        return 'punnett_square'
    if any(w in text_lower for w in ['circuit', 'resistor', 'voltage', 'current']):
        return 'simple_circuit'
    if any(w in text_lower for w in ['atom', 'electron', 'proton', 'neutron', 'bohr']):
        return 'atom_model'
    if any(w in text_lower for w in ['wave', 'amplitude', 'wavelength', 'frequency', 'crest', 'trough']):
        return 'wave_diagram'
    if any(w in text_lower for w in ['ph scale', 'acid', 'base', 'ph level']):
        return 'ph_scale'
    if any(w in text_lower for w in ['photosynthesis', 'chloroplast', 'chlorophyll']):
        return 'photosynthesis'
    if any(w in text_lower for w in ['states of matter', 'phase change', 'solid liquid gas']):
        return 'states_of_matter'
    return None


def generate_diagram(question, topic_key=None, custom_prompt=None):
    """Generate a diagram image using Gemini and attach it to the question.

    Args:
        question: The question dict to attach the diagram to.
        topic_key: Key into _TOPIC_DIAGRAM_PROMPTS for a standard diagram.
        custom_prompt: Override prompt for the image generation.

    Returns:
        dict with diagram data, or None on failure.
    """
    api_key = os.getenv('GOOGLE_API_KEY', '')
    if not api_key:
        print("⚠ GOOGLE_API_KEY not set — skipping diagram generation")
        return None

    # Build the image prompt
    if custom_prompt:
        image_prompt = custom_prompt
    elif topic_key and topic_key in _TOPIC_DIAGRAM_PROMPTS:
        image_prompt = _TOPIC_DIAGRAM_PROMPTS[topic_key]
    else:
        # Generate a custom prompt from the question text
        q_text = question.get('question', '')[:300]
        image_prompt = (
            f"Educational science diagram for this question: {q_text}. "
            f"Clean, labeled, scientific illustration style. White background. "
            f"Clear labels with arrows. No decorative elements. "
            f"Suitable for a printed assessment."
        )

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)

        response = client.models.generate_content(
            model="gemini-2.0-flash-preview-image-generation",
            contents=image_prompt,
            config=types.GenerateContentConfig(
                response_modalities=["TEXT", "IMAGE"],
            ),
        )

        # Extract image from response
        image_b64 = None
        for part in response.candidates[0].content.parts:
            if part.inline_data and part.inline_data.mime_type.startswith('image/'):
                image_b64 = base64.b64encode(part.inline_data.data).decode('utf-8')
                break

        if not image_b64:
            print("⚠ Gemini returned no image data")
            return None

        diagram = {
            "image_b64": image_b64,
            "prompt": image_prompt,
            "source": "gemini",
            "model": "gemini-2.0-flash-preview-image-generation",
            "verified": False,
            "generation_id": str(uuid.uuid4()),
        }

        # Attach to question
        question['diagram'] = diagram
        question['warning'] = "AI-generated diagram — verify accuracy before publishing"
        question['warning_severity'] = "warning"

        return diagram

    except Exception as e:
        print(f"⚠ Diagram generation failed (non-fatal): {e}")
        return None


def generate_diagrams_for_assignment(assignment, subject=''):
    """Scan all questions in an assignment and generate diagrams where needed.

    Args:
        assignment: The full assignment/assessment dict.
        subject: Subject string for relevance filtering.

    Returns:
        int: Number of diagrams generated.
    """
    count = 0
    for section in assignment.get('sections', []):
        for q in section.get('questions', []):
            should, topic, custom = should_generate_diagram(q, subject)
            if should:
                result = generate_diagram(q, topic, custom)
                if result:
                    count += 1
    return count


def regenerate_diagram(question, custom_prompt=None):
    """Regenerate just the diagram for a question (keep question text).

    Args:
        question: The question dict.
        custom_prompt: Optional new prompt (otherwise reuses existing).

    Returns:
        dict with new diagram data, or None on failure.
    """
    existing = question.get('diagram', {})
    prompt = custom_prompt or existing.get('prompt', '')
    if not prompt:
        return None

    # Clear old diagram before regenerating
    old_gen_id = existing.get('generation_id')
    result = generate_diagram(question, custom_prompt=prompt)
    if result:
        result['previous_generation_id'] = old_gen_id
    return result
```

### Install dependency

```bash
pip install google-genai
# Add to requirements.txt: google-genai>=1.0.0
```

---

## Phase 2: Backend Pipeline Integration

### 2A. Wire into `_post_process_assignment()`

**File:** `backend/routes/planner_routes.py`

**At the top of the file (~line 5), add import:**

```python
# After: from pathlib import Path
from utils.diagram_generator import generate_diagrams_for_assignment, regenerate_diagram
```

**Modify `_post_process_assignment()` — add Phase 6 after point normalization (~line 175):**

```python
def _post_process_assignment(assignment, target_question_count=None, target_total_points=None, subject=''):
    # ... existing phases 1-5 ...

    # Phase 5: Normalize points (always runs)
    _normalize_points(assignment, target_total_points)

    # Phase 6: Generate diagrams for science questions (if GOOGLE_API_KEY set)
    if os.getenv('GOOGLE_API_KEY'):
        diagram_count = generate_diagrams_for_assignment(assignment, subject)
        if diagram_count:
            print(f"  📊 Generated {diagram_count} science diagram(s)")

    return assignment, extra_usage
```

**Update signature** — add `subject=''` parameter.

### 2B. Update all callers to pass `subject`

**Assessment endpoint (~line 4531):**
```python
# Change:
assessment, _ = _post_process_assignment(assessment, target_total_points=total_points)
# To:
assessment, _ = _post_process_assignment(
    assessment, target_total_points=total_points,
    subject=config.get('subject', '')
)
```

**Assignment-from-lesson endpoint (~line 2595):**
```python
# Change:
assignment, extra_usage = _post_process_assignment(assignment, target_q, target_total_points=100)
# To:
assignment, extra_usage = _post_process_assignment(
    assignment, target_q, target_total_points=100,
    subject=config.get('subject', '')
)
```

**Both variation callers (~lines 2253, 2283):**
```python
# Change:
plan, extra_usage = _post_process_assignment(plan, target_q, target_total_points=100)
# To:
plan, extra_usage = _post_process_assignment(
    plan, target_q, target_total_points=100,
    subject=config.get('subject', '')
)
```

### 2C. Regeneration endpoint — generate diagram for replacement questions

**File:** `backend/routes/planner_routes.py`, `regenerate_questions()` (~line 5472)

After the post-processing pipeline for each new question, add diagram generation:

```python
                # Run through classification and hydration pipeline
                _classify_question_type(new_q)
                _hydrate_question(new_q)
                _validate_question(new_q)

                # Generate diagram if science question needs one
                if os.getenv('GOOGLE_API_KEY'):
                    from utils.diagram_generator import should_generate_diagram, generate_diagram
                    should, topic, custom = should_generate_diagram(new_q, subject)
                    if should:
                        generate_diagram(new_q, topic, custom)

                replacements.append({ ... })
```

### 2D. New endpoint: Regenerate diagram only

**File:** `backend/routes/planner_routes.py`

Add after the `regenerate_questions` endpoint (~line 5489):

```python
@planner_bp.route('/api/regenerate-diagram', methods=['POST'])
def regenerate_diagram_endpoint():
    """Regenerate just the diagram image for a question."""
    data = request.json
    question = data.get('question', {})
    custom_prompt = data.get('custom_prompt', None)

    if not question:
        return jsonify({"error": "No question provided"}), 400

    try:
        from utils.diagram_generator import regenerate_diagram
        result = regenerate_diagram(question, custom_prompt)
        if result:
            return jsonify({"diagram": result})
        return jsonify({"error": "Failed to generate diagram"}), 500
    except Exception as e:
        print(f"Diagram regeneration error: {e}")
        return jsonify({"error": str(e)}), 500
```

---

## Phase 3: PDF/Word Export

### 3A. Embed diagrams in Word export

**File:** `backend/routes/planner_routes.py`, `export_assessment()` (~line 4630)

After the question text line and before the options, add image rendering:

```python
                # Question number and text
                q_para.add_run(f"{q_num}. ").bold = True
                q_para.add_run(f"{q_text} ")
                q_para.add_run(f"({q_points} pt{'s' if q_points > 1 else ''})").italic = True

                # Diagram image (if present)
                if q.get('diagram') and q['diagram'].get('image_b64'):
                    import io
                    diagram_bytes = base64.b64decode(q['diagram']['image_b64'])
                    diagram_stream = io.BytesIO(diagram_bytes)
                    try:
                        doc.add_picture(diagram_stream, width=Inches(4.5))
                        last_paragraph = doc.paragraphs[-1]
                        last_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    except Exception as img_err:
                        print(f"⚠ Could not embed diagram in export: {img_err}")
                        doc.add_paragraph("[Diagram could not be rendered]").italic = True

                # Multiple choice options
                if q.get('options'):
```

### 3B. Also handle the assignment export endpoint

**File:** `backend/routes/planner_routes.py` — find `export-generated-assignment` endpoint and apply the same pattern. The diagram rendering code is identical.

---

## Phase 4: Frontend — Display Diagrams

### 4A. AssignmentPlayer.jsx — QuestionRenderer

**File:** `frontend/src/components/AssignmentPlayer.jsx` (~line 996)

After `RenderQuestionText` and before the warning badge, add diagram display:

```jsx
      <RenderQuestionText text={question.question} style={styles.questionText} />

      {/* AI-generated diagram */}
      {question.diagram?.image_b64 && (
        <div style={{
          margin: "12px 0",
          textAlign: "center",
          position: "relative",
        }}>
          <img
            src={`data:image/png;base64,${question.diagram.image_b64}`}
            alt={question.diagram.prompt || "Science diagram"}
            style={{
              maxWidth: "100%",
              maxHeight: "400px",
              borderRadius: "8px",
              border: "1px solid rgba(255,255,255,0.1)",
            }}
          />
          {!question.diagram.verified && !readOnly && (
            <div style={{
              position: "absolute",
              top: "8px",
              right: "8px",
              padding: "4px 8px",
              background: "rgba(245, 158, 11, 0.9)",
              borderRadius: "4px",
              fontSize: "0.7rem",
              fontWeight: 600,
              color: "#000",
            }}>
              AI-Generated — Verify
            </div>
          )}
        </div>
      )}

      {/* Quality warning badge */}
      {question.warning && (
```

### 4B. App.jsx — Assessment Preview

**File:** `frontend/src/App.jsx` (~line 23493, after question header div)

After the DOK badge closing div and before the warning badge, add diagram thumbnail:

```jsx
                                      </div>
                                      {/* Diagram preview */}
                                      {q.diagram?.image_b64 && (
                                        <div style={{
                                          margin: "8px 0",
                                          textAlign: "center",
                                          position: "relative",
                                        }}>
                                          <img
                                            src={`data:image/png;base64,${q.diagram.image_b64}`}
                                            alt="Question diagram"
                                            style={{
                                              maxWidth: "100%",
                                              maxHeight: "300px",
                                              borderRadius: "8px",
                                              border: "1px solid rgba(255,255,255,0.1)",
                                            }}
                                          />
                                          {!q.diagram.verified && (
                                            <div style={{
                                              display: "inline-flex",
                                              alignItems: "center",
                                              gap: "4px",
                                              marginTop: "4px",
                                              padding: "2px 8px",
                                              background: "rgba(245,158,11,0.15)",
                                              borderRadius: "6px",
                                              fontSize: "0.7rem",
                                              color: "#f59e0b",
                                            }}>
                                              <Icon name="AlertTriangle" size={12} />
                                              AI-generated — click to verify
                                            </div>
                                          )}
                                        </div>
                                      )}
                                      {/* Quality warning badge */}
```

### 4C. App.jsx — Regenerate Diagram Button

**File:** `frontend/src/App.jsx`

Add a "Regenerate Diagram" button inside the question card (in the edit mode toolbar area). This appears alongside the existing "Regenerate Question" button when a question has a diagram:

```jsx
// Inside the question card's action area (where edit/select checkboxes are)
{editMode && q.diagram && (
  <button
    onClick={async (e) => {
      e.stopPropagation();
      try {
        const data = await api.regenerateDiagram(q, null);
        if (data.diagram) {
          const copy = JSON.parse(JSON.stringify(generatedAssessment));
          copy.sections[sIdx].questions[qIdx].diagram = data.diagram;
          setGeneratedAssessment(copy);
          addToast("Diagram regenerated", "success");
        }
      } catch (err) {
        addToast("Diagram regeneration failed: " + err.message, "error");
      }
    }}
    style={{
      padding: "4px 10px",
      background: "rgba(59,130,246,0.15)",
      border: "1px solid rgba(59,130,246,0.3)",
      borderRadius: "6px",
      color: "#3b82f6",
      fontSize: "0.75rem",
      cursor: "pointer",
    }}
  >
    <Icon name="RefreshCw" size={12} /> Regen Diagram
  </button>
)}
```

### 4D. App.jsx — Diagram Verify Toggle

When teacher clicks the "AI-generated — click to verify" badge, toggle the `verified` flag:

```jsx
// Replace the verify badge with a clickable version:
onClick={() => {
  const copy = JSON.parse(JSON.stringify(generatedAssessment));
  copy.sections[sIdx].questions[qIdx].diagram.verified = true;
  setGeneratedAssessment(copy);
  addToast("Diagram marked as verified", "success");
}}
style={{ cursor: "pointer" }}
```

### 4E. api.js — New API function

**File:** `frontend/src/services/api.js`

Add after `regenerateQuestions`:

```javascript
export async function regenerateDiagram(question, customPrompt = null) {
  return fetchApi('/api/regenerate-diagram', {
    method: 'POST',
    body: JSON.stringify({ question, custom_prompt: customPrompt }),
  })
}
```

---

## Phase 5: AI Grading Integration

### 5A. Portal grading — Text context (no image needed)

**File:** `backend/routes/planner_routes.py`, `grade_assessment_answers()` (~line 5306)

When building the grading prompt for questions with diagrams, add the diagram description:

```python
                    # Current:
                    grading_prompt = f"""Grade this student answer for the following question.

Question: {q.get('question', '')}
...
Student's Answer: {student_ans}
"""

                    # Add diagram context:
                    diagram_context = ""
                    if q.get('diagram') and q['diagram'].get('prompt'):
                        diagram_context = f"""
DIAGRAM CONTEXT: The student was shown the following diagram alongside this question:
{q['diagram']['prompt']}
Consider this visual context when evaluating whether the student's answer is correct.
"""

                    grading_prompt = f"""Grade this student answer for the following question.

Question: {q.get('question', '')}
{diagram_context}
Question Type: {q.get('type', 'short_answer')}
Points Possible: {points}
Correct/Model Answer: {q.get('answer', 'N/A')}
...
Student's Answer: {student_ans}
"""
```

This is cheap (text-only) and sufficient for portal-based grading because the student typed a text answer about the diagram.

### 5B. File-upload grading — Multimodal (image needed)

**File:** `assignment_grader.py`, `grade_per_question()` (~line 4153)

For uploaded-file grading where the student may have annotated or drawn on the diagram, the grading call needs to be multimodal.

**Add parameter to function signature:**
```python
def grade_per_question(question: str, student_answer: str, expected_answer: str,
                       points: int, grade_level: str, subject: str,
                       teacher_instructions: str, grading_style: str,
                       ai_model: str = 'gpt-4o',
                       ai_provider: str = 'openai',
                       response_type: str = 'marker_response',
                       section_name: str = '', section_type: str = 'written',
                       token_tracker: 'TokenTracker' = None,
                       diagram_context: str = '',        # NEW
                       student_image_b64: str = None,    # NEW
                       diagram_image_b64: str = None,    # NEW
                       ) -> dict:
```

**In the prompt construction (~line 4274), add diagram context:**
```python
# After: {teacher_instructions}
# Add:
{f"DIAGRAM CONTEXT: The student was shown this diagram: {diagram_context}" if diagram_context else ""}
```

**In the OpenAI API call, switch to multimodal when images present:**
```python
# Current text-only call:
messages = [
    {"role": "system", "content": system_prompt},
    {"role": "user", "content": grading_prompt}
]

# New multimodal-aware call:
if student_image_b64 or diagram_image_b64:
    content_parts = [{"type": "text", "text": grading_prompt}]
    if diagram_image_b64:
        content_parts.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{diagram_image_b64}"}
        })
    if student_image_b64:
        content_parts.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{student_image_b64}"}
        })
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": content_parts}
    ]
else:
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": grading_prompt}
    ]
```

### 5C. Pass diagram data through the grading pipeline

**File:** `backend/app.py`, in the grading thread (~line 1075-1285)

When building `file_ai_notes` for assignments that contain diagrams:
```python
# After existing accommodation/history/period context:
if assignment_config and assignment_config.get('sections'):
    has_diagrams = any(
        q.get('diagram') for s in assignment_config.get('sections', [])
        for q in s.get('questions', [])
    )
    if has_diagrams:
        file_ai_notes += """

DIAGRAM-BASED QUESTIONS:
This assignment contains questions with AI-generated science diagrams.
When grading student responses about diagrams:
- Accept correct identification of labeled parts even if wording differs from answer key
- Give partial credit for partially correct labeling
- If the student references the diagram correctly but uses different terminology, consider it correct
- For questions asking students to draw/annotate diagrams, grade based on the uploaded image
"""
```

---

## Phase 6: Frontend — Regeneration Flow Updates

### 6A. Preserve diagram data during question regeneration

**File:** `frontend/src/App.jsx`, `regenerateSelectedQuestions()` (~line 4672)

When merging replacement questions, the new question from the backend will already have a diagram if the backend generated one. But we need to handle the case where the old question had a diagram and the new one doesn't:

```javascript
      (data.replacements || []).forEach((r) => {
        const section = copy.sections[r.section_index];
        if (section?.questions?.[r.question_index]) {
          const oldQ = section.questions[r.question_index];
          // Preserve the original question number
          r.question.number = oldQ.number;
          // If old question had a verified diagram and new doesn't, keep it
          // (teacher verified it, don't throw it away)
          if (oldQ.diagram?.verified && !r.question.diagram) {
            r.question.diagram = oldQ.diagram;
          }
          section.questions[r.question_index] = r.question;
        }
      });
```

### 6B. QuestionEditOverlay — diagram prompt editing

**File:** `frontend/src/components/QuestionEditOverlay.jsx`

In the edit form (when `isEditing` is true), add a field for the diagram prompt so teachers can refine what diagram is generated:

```jsx
{/* After existing edit fields, before save/cancel buttons */}
{question.diagram && (
  <div style={{ marginTop: "10px" }}>
    <label style={{ fontSize: "0.8rem", color: "var(--text-secondary)", display: "block", marginBottom: "4px" }}>
      Diagram Prompt (edit to regenerate a different diagram)
    </label>
    <textarea
      defaultValue={question.diagram.prompt || ""}
      onBlur={(e) => {
        // Store updated prompt for when teacher saves
        question._editedDiagramPrompt = e.target.value;
      }}
      style={{
        width: "100%",
        minHeight: "60px",
        padding: "8px",
        borderRadius: "6px",
        border: "1px solid rgba(255,255,255,0.1)",
        background: "rgba(0,0,0,0.2)",
        color: "var(--text-primary)",
        fontSize: "0.85rem",
        resize: "vertical",
      }}
    />
  </div>
)}
```

When saving the edit, if the prompt changed, trigger diagram regeneration.

---

## Phase 7: Analytics

### Minimal changes needed

The existing analytics pipeline tracks scores per question. Diagram questions are graded the same way (points earned / points possible), so no schema changes are needed.

**Optional enhancement:** Add a `has_diagram` flag to question-level analytics so teachers can compare performance on diagram-based vs text-only questions:

```python
# In the results processing:
question_result["has_diagram"] = bool(q.get('diagram'))
```

---

## Implementation Order

| Phase | Description | Estimated Effort | Dependencies |
|-------|-------------|-----------------|--------------|
| **1** | `diagram_generator.py` utility | Medium | `google-genai` package, `GOOGLE_API_KEY` |
| **2A-2B** | Wire into post-processing pipeline | Small | Phase 1 |
| **2C-2D** | Regeneration endpoints | Small | Phase 1 |
| **3** | PDF/Word export with images | Small | Phase 1 |
| **4A-4B** | Frontend diagram display | Small | Phase 2 |
| **4C-4E** | Regen diagram button + API | Small | Phase 2D |
| **5A** | Portal grading with diagram context | Small | Phase 2 |
| **5B-5C** | Multimodal file-upload grading | Medium | Phase 2 |
| **6** | Regeneration flow updates | Small | Phase 4 |
| **7** | Analytics tagging | Trivial | Phase 5 |

**Suggested build order:** 1 → 2A → 4A → 3 → 2C → 4C → 5A → 5B → 6 → 7

---

## Environment Setup

```bash
# .env additions:
GOOGLE_API_KEY=your-gemini-api-key-here

# requirements.txt addition:
google-genai>=1.0.0

# Install:
source venv/bin/activate && pip install google-genai
```

---

## Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| Diagram has wrong labels | Warning badge + teacher verify flow. Diagram is NOT shown to students until teacher marks `verified: true` (optional strictness) |
| Base64 bloats JSON | Typical diagram is 50-150KB. Cap at 10 diagrams per assignment = 1.5MB max. Acceptable for current scale |
| Gemini API rate limits | Diagrams generated sequentially (not parallel) with 0.5s delay. Typical assessment generates 2-5 diagrams |
| Gemini API unavailable | Graceful fallback: `generate_diagram()` returns None, question renders without diagram, warning says "Diagram could not be generated" |
| Cost | Gemini Flash image generation ~$0.002-0.004/image. 5 diagrams = ~$0.01-0.02 per assessment. Negligible |
| Student can't see diagram in portal | Image rendered as base64 `<img>` — works in all browsers, no external dependency |
| PDF export diagram sizing | Fixed at `Inches(4.5)` width, aspect ratio preserved by python-docx. Page breaks handled by Word's layout engine |

---

## Testing Checklist

- [ ] Generate a science assessment → diagrams appear on relevant questions
- [ ] Generate a non-science assessment → no diagrams generated
- [ ] Diagram warning badge shows "AI-generated — verify"
- [ ] Click verify badge → warning clears
- [ ] Regenerate diagram button → new image appears
- [ ] Export to Word → diagrams embedded correctly
- [ ] Portal student view → diagram displays above answer input
- [ ] Grade portal answers → diagram context in grading prompt
- [ ] Upload handwritten file → multimodal grading includes diagram
- [ ] Edit diagram prompt → regenerate produces different diagram
- [ ] No `GOOGLE_API_KEY` → graceful skip, no errors
- [ ] `cd frontend && npm run build` succeeds
