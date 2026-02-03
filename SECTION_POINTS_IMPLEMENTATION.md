# Section-Based Point System - Implementation Guide

## Overview

Add point values to each assignment section so grading is explicitly tied to assignment structure. Missing a 20-point summary section = lose 20 points (no negotiation).

---

## File 1: `/Users/alexc/Downloads/Graider/frontend/src/App.jsx`

### Edit 1A: Add Assignment Templates (after markerLibrary constant, ~line 104)

```javascript
const ASSIGNMENT_TEMPLATES = {
  "Cornell Notes": {
    markers: [
      { start: "Questions/Terms", points: 40, type: "fill-blank", description: "Fill-in-the-blank and short answers" },
      { start: "Summary (Bottom Section)", points: 20, type: "written", description: "3-4 sentence summary" },
      { start: "Vocabulary", points: 25, type: "vocabulary", description: "Vocabulary definitions" },
    ],
    effortPoints: 15,
    description: "Standard Cornell Notes format with summary section"
  },
  "Worksheet - Fill-in-Blank Heavy": {
    markers: [
      { start: "Fill-in-the-blank", points: 50, type: "fill-blank", description: "Fill-in-the-blank questions" },
      { start: "Short Answer", points: 35, type: "written", description: "Written response questions" },
    ],
    effortPoints: 15,
    description: "Worksheet with mostly fill-in-the-blank"
  },
  "Worksheet - Written Heavy": {
    markers: [
      { start: "Questions", points: 30, type: "fill-blank", description: "Fill-in-the-blank and factual questions" },
      { start: "Written Response", points: 40, type: "written", description: "Paragraph responses" },
      { start: "Reflection", points: 15, type: "written", description: "Personal reflection" },
    ],
    effortPoints: 15,
    description: "Worksheet emphasizing written responses"
  },
  "Essay": {
    markers: [
      { start: "Thesis/Introduction", points: 20, type: "written", description: "Opening paragraph with thesis" },
      { start: "Body Paragraphs", points: 45, type: "written", description: "Supporting arguments" },
      { start: "Conclusion", points: 20, type: "written", description: "Summary and closing" },
    ],
    effortPoints: 15,
    description: "Standard essay format"
  },
  "Custom": {
    markers: [],
    effortPoints: 15,
    description: "Define your own sections and point values"
  }
};
```

---

### Edit 1B: Update assignment state (~line 869)

**FIND:**
```javascript
const [assignment, setAssignment] = useState({
  title: "",
  subject: "Social Studies",
  totalPoints: 100,
  instructions: "",
  questions: [],
  customMarkers: [],
  excludeMarkers: [],
  gradingNotes: "",
  responseSections: [],
  aliases: [],
  completionOnly: false,
  rubricType: "standard",
  customRubric: null,
});
```

**REPLACE WITH:**
```javascript
const [assignment, setAssignment] = useState({
  title: "",
  subject: "Social Studies",
  totalPoints: 100,
  instructions: "",
  questions: [],
  customMarkers: [],           // Now objects: { start: "Summary:", points: 20, type: "written" }
  excludeMarkers: [],
  gradingNotes: "",
  responseSections: [],
  aliases: [],
  completionOnly: false,
  rubricType: "standard",
  customRubric: null,
  sectionTemplate: "Custom",   // NEW: Track which template
  effortPoints: 15,            // NEW: Points for effort category
});
```

---

### Edit 1C: Add helper functions (after getMarkerText/getEndMarker ~line 2466)

```javascript
// Get marker points (default 10 if not specified)
const getMarkerPoints = (marker) => {
  if (typeof marker === 'string') return 10;
  return marker.points || 10;
};

// Get marker type (default "written")
const getMarkerType = (marker) => {
  if (typeof marker === 'string') return 'written';
  return marker.type || 'written';
};

// Calculate total points from markers
const calculateTotalPoints = (markers, effortPoints = 15) => {
  const markerTotal = (markers || []).reduce((sum, m) => sum + getMarkerPoints(m), 0);
  return markerTotal + effortPoints;
};
```

---

### Edit 1D: Add Template Selector in Builder (before markers section, ~line 12600)

```javascript
{/* Section Template Selector */}
<div style={{ marginBottom: '20px', padding: '15px', background: 'rgba(59,130,246,0.1)', borderRadius: '8px' }}>
  <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '10px' }}>
    <Icon name="Layout" size={18} style={{ color: '#3b82f6' }} />
    <span style={{ fontWeight: '600' }}>Section Point Template</span>
  </div>
  <select
    value={assignment.sectionTemplate || 'Custom'}
    onChange={(e) => {
      const templateName = e.target.value;
      const template = ASSIGNMENT_TEMPLATES[templateName];
      if (template && templateName !== 'Custom') {
        setAssignment({
          ...assignment,
          sectionTemplate: templateName,
          customMarkers: template.markers.map(m => ({ ...m })),
          effortPoints: template.effortPoints || 15,
        });
      } else {
        setAssignment({ ...assignment, sectionTemplate: 'Custom' });
      }
    }}
    style={{ padding: '8px 12px', borderRadius: '6px', border: '1px solid #d1d5db', width: '100%', marginBottom: '8px' }}
  >
    {Object.keys(ASSIGNMENT_TEMPLATES).map(name => (
      <option key={name} value={name}>{name}</option>
    ))}
  </select>
  {assignment.sectionTemplate && ASSIGNMENT_TEMPLATES[assignment.sectionTemplate] && (
    <div style={{ fontSize: '12px', color: '#6b7280' }}>
      {ASSIGNMENT_TEMPLATES[assignment.sectionTemplate].description}
    </div>
  )}
  <div style={{ marginTop: '10px', padding: '8px', background: 'rgba(0,0,0,0.05)', borderRadius: '4px', fontSize: '13px' }}>
    <strong>Total Points:</strong> {calculateTotalPoints(assignment.customMarkers, assignment.effortPoints || 15)}
    {calculateTotalPoints(assignment.customMarkers, assignment.effortPoints || 15) !== 100 && (
      <span style={{ color: '#ef4444', marginLeft: '10px' }}>(Should equal 100)</span>
    )}
  </div>
</div>
```

---

### Edit 1E: Update Markers Display (~line 12702-12744)

**FIND the existing markers display and REPLACE WITH:**

```javascript
{/* Current Markers with Points */}
<div style={{ marginBottom: '15px' }}>
  <div style={{ fontWeight: '600', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '8px' }}>
    <Icon name="Target" size={16} />
    Grading Sections
  </div>
  {(assignment.customMarkers || []).length === 0 ? (
    <div style={{ color: '#9ca3af', fontSize: '13px', padding: '10px', background: 'rgba(0,0,0,0.03)', borderRadius: '6px' }}>
      No sections defined. Select a template above or highlight sections in the document.
    </div>
  ) : (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
      {assignment.customMarkers.map((marker, i) => (
        <div key={i} style={{
          display: 'flex', alignItems: 'center', gap: '8px', padding: '10px',
          background: 'rgba(251,191,36,0.15)', borderRadius: '6px', border: '1px solid rgba(251,191,36,0.3)'
        }}>
          <Icon name="Target" size={14} style={{ color: '#f59e0b', flexShrink: 0 }} />
          <input
            type="text"
            value={getMarkerText(marker)}
            onChange={(e) => {
              const updated = [...assignment.customMarkers];
              if (typeof updated[i] === 'string') {
                updated[i] = { start: e.target.value, points: 10, type: 'written' };
              } else {
                updated[i] = { ...updated[i], start: e.target.value };
              }
              setAssignment({ ...assignment, customMarkers: updated, sectionTemplate: 'Custom' });
            }}
            style={{ flex: 1, padding: '4px 8px', borderRadius: '4px', border: '1px solid #d1d5db', fontSize: '13px' }}
            placeholder="Section name..."
          />
          <input
            type="number"
            value={getMarkerPoints(marker)}
            onChange={(e) => {
              const updated = [...assignment.customMarkers];
              const pts = parseInt(e.target.value) || 0;
              if (typeof updated[i] === 'string') {
                updated[i] = { start: updated[i], points: pts, type: 'written' };
              } else {
                updated[i] = { ...updated[i], points: pts };
              }
              setAssignment({ ...assignment, customMarkers: updated, sectionTemplate: 'Custom' });
            }}
            style={{ width: '60px', padding: '4px 8px', borderRadius: '4px', border: '1px solid #d1d5db', textAlign: 'center', fontSize: '13px' }}
            min="0" max="100"
          />
          <span style={{ fontSize: '12px', color: '#6b7280' }}>pts</span>
          <select
            value={getMarkerType(marker)}
            onChange={(e) => {
              const updated = [...assignment.customMarkers];
              if (typeof updated[i] === 'string') {
                updated[i] = { start: updated[i], points: 10, type: e.target.value };
              } else {
                updated[i] = { ...updated[i], type: e.target.value };
              }
              setAssignment({ ...assignment, customMarkers: updated, sectionTemplate: 'Custom' });
            }}
            style={{ padding: '4px 8px', borderRadius: '4px', border: '1px solid #d1d5db', fontSize: '12px' }}
          >
            <option value="written">Written</option>
            <option value="fill-blank">Fill-blank</option>
            <option value="vocabulary">Vocabulary</option>
            <option value="matching">Matching</option>
          </select>
          <button
            onClick={() => {
              const updated = assignment.customMarkers.filter((_, idx) => idx !== i);
              setAssignment({ ...assignment, customMarkers: updated, sectionTemplate: 'Custom' });
            }}
            style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '4px', color: '#ef4444' }}
          >
            <Icon name="X" size={14} />
          </button>
        </div>
      ))}
      {/* Effort Points Row */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: '8px', padding: '10px',
        background: 'rgba(34,197,94,0.15)', borderRadius: '6px', border: '1px solid rgba(34,197,94,0.3)'
      }}>
        <Icon name="Star" size={14} style={{ color: '#22c55e', flexShrink: 0 }} />
        <span style={{ flex: 1, fontSize: '13px', fontWeight: '500' }}>Effort & Engagement</span>
        <input
          type="number"
          value={assignment.effortPoints || 15}
          onChange={(e) => setAssignment({ ...assignment, effortPoints: parseInt(e.target.value) || 0, sectionTemplate: 'Custom' })}
          style={{ width: '60px', padding: '4px 8px', borderRadius: '4px', border: '1px solid #d1d5db', textAlign: 'center', fontSize: '13px' }}
          min="0" max="30"
        />
        <span style={{ fontSize: '12px', color: '#6b7280' }}>pts</span>
        <div style={{ width: '90px' }}></div>
      </div>
    </div>
  )}
</div>
```

---

## File 2: `/Users/alexc/Downloads/Graider/assignment_grader.py`

### Edit 2A: Add build_section_rubric function (before grade_assignment, ~line 2100)

```python
def build_section_rubric(marker_config: list, effort_points: int = 15) -> str:
    """Build a section-based rubric from marker configuration."""
    if not marker_config:
        return ""  # Use default rubric

    rubric_lines = ["\nSECTION POINT VALUES:"]
    total = 0

    for m in marker_config:
        if isinstance(m, dict):
            name = m.get('start', 'Section')
            points = m.get('points', 10)
            section_type = m.get('type', 'written')
            rubric_lines.append(f"- {name}: {points} points ({section_type})")
            total += points
        elif isinstance(m, str):
            rubric_lines.append(f"- {m}: 10 points")
            total += 10

    rubric_lines.append(f"- Effort & Engagement: {effort_points} points")
    total += effort_points
    rubric_lines.append(f"\nTOTAL: {total} points")

    rubric_lines.append("""
SECTION GRADING RULES:
- Grade each section out of its assigned points
- BLANK SECTION = 0 POINTS (no exceptions, no partial credit for blank sections)
- For fill-blank: each correct answer worth proportional points
- For written: grade on quality, completeness, effort
- The SCORE should be the SUM of section points earned
""")

    return "\n".join(rubric_lines)
```

---

### Edit 2B: Update format_extracted_for_grading (~line 733)

**FIND the function and ADD marker_config parameter:**

```python
def format_extracted_for_grading(extraction_result: dict, marker_config: list = None) -> str:
    """
    Format pre-extracted responses for the grading prompt.
    Includes section point values if provided.
    """
    if not extraction_result:
        return ""

    # Build marker points lookup
    marker_points = {}
    if marker_config:
        for m in marker_config:
            if isinstance(m, dict):
                marker_points[m.get('start', '').lower()] = m.get('points', 10)
            elif isinstance(m, str):
                marker_points[m.lower()] = 10

    result_parts = ["=" * 50]
    result_parts.append("VERIFIED STUDENT RESPONSES (extracted from document)")
    result_parts.append("=" * 50)
    result_parts.append("")

    responses = extraction_result.get("extracted_responses", [])
    for i, resp in enumerate(responses, 1):
        question = resp.get("question", "Unknown")
        answer = resp.get("answer", "")
        resp_type = resp.get("type", "unknown")

        # Look up points for this section
        points_str = ""
        for marker_key, pts in marker_points.items():
            if marker_key in question.lower():
                points_str = f" [{pts} points]"
                break

        result_parts.append(f"[{i}] {question}{points_str}")
        result_parts.append(f"    STUDENT ANSWER: \"{answer[:500]}{'...' if len(answer) > 500 else ''}\"")
        result_parts.append(f"    (Type: {resp_type})")
        result_parts.append("")

    # Blank questions with point losses
    blank = extraction_result.get("blank_questions", [])
    if blank:
        result_parts.append("UNANSWERED/BLANK SECTIONS (student loses these points):")
        for q in blank:
            points_str = ""
            for marker_key, pts in marker_points.items():
                if marker_key in q.lower():
                    points_str = f" [LOSES {pts} points]"
                    break
            result_parts.append(f"  • {q}{points_str}")
        result_parts.append("")

    answered = extraction_result.get("answered_questions", 0)
    total = extraction_result.get("total_questions", 0)
    result_parts.append(f"SUMMARY: {answered}/{total} sections completed.")

    return "\n".join(result_parts)
```

---

### Edit 2C: Update grade_assignment to use section rubric (~line 2380)

**FIND where prompt_text is constructed and ADD section rubric:**

```python
# Build section-aware rubric if marker config provided
section_rubric = ""
if custom_markers:
    # custom_markers now contains point values
    effort_pts = 15  # Default, could be passed as parameter
    section_rubric = build_section_rubric(custom_markers, effort_pts)

# In the prompt construction, add section_rubric:
prompt_text = f"""
{effective_rubric}

{section_rubric}

{ASSIGNMENT_INSTRUCTIONS}
...
"""
```

---

### Edit 2D: Update JSON output format in prompt (~line 2520-2560)

**ADD section_scores to expected JSON format:**

```python
Return your assessment as JSON:
{{
    "score": <total points - SUM of section scores>,
    "letter_grade": "<A/B/C/D/F>",
    "section_scores": {{
        "<section_name>": {{"earned": <pts>, "possible": <max>, "feedback": "<brief note>"}},
        "Effort & Engagement": {{"earned": <pts>, "possible": 15, "feedback": "<note>"}}
    }},
    "breakdown": {{
        "content_accuracy": <points out of 40>,
        "completeness": <points out of 25>,
        "writing_quality": <points out of 20>,
        "effort_engagement": <points out of 15>
    }},
    "feedback": "<overall feedback>",
    "student_responses": ["<answers>"],
    "unanswered_questions": ["<blank sections>"],
    ...
}}
```

---

## Verification

1. `python graider_app.py`
2. Builder tab → Select "Cornell Notes" template
3. Verify: Questions/Terms (40), Summary (20), Vocabulary (25), Effort (15) = 100 total
4. Grade an assignment with blank summary
5. Verify score reflects -20 for missing summary
6. Check results modal shows section breakdown
