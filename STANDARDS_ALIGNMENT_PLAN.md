# Retroactive Standards Alignment — Detailed Implementation Plan

## Context
Teachers often have existing assignments created without explicit standards alignment. Graider already has document parsing, a Florida standards database, and AI infrastructure. This feature lets teachers click "Align to Standards" in the Builder tab after importing a document, and Graider identifies which standards it maps to — with optional AI-powered question rewrites.

---

## File 1: `backend/routes/planner_routes.py`

### Edit A: Add Endpoint `POST /api/align-document-to-standards`

**Location:** After line 2233 (after the `get_standards()` route), before line 2236 (`get_lesson_templates`)

**Insert after this existing code:**
```python
    # Fallback to empty if no data file exists
    return jsonify({"standards": [], "grade": grade, "subject": subject})
```

**New code to insert:**
```python


@planner_bp.route('/api/align-document-to-standards', methods=['POST'])
def align_document_to_standards():
    """Analyze a document and identify which standards it aligns to."""
    data = request.json
    doc_text = data.get('documentText', '')
    state = data.get('state', 'FL')
    grade = data.get('grade', '7')
    subject = data.get('subject', '')

    if not doc_text or not doc_text.strip():
        return jsonify({"error": "No document text provided"})
    if not subject:
        return jsonify({"error": "Subject is required. Set it in Settings."})

    # Reuse existing load_standards() (line 2140)
    standards = load_standards(state, subject, grade)
    if not standards:
        return jsonify({"error": f"No standards found for {state} {subject} grade {grade}. Check that a standards file exists in backend/data/."})

    # Build condensed standards reference for AI prompt (limit token usage)
    standards_ref = []
    for s in standards:
        standards_ref.append({
            "code": s.get("code", ""),
            "benchmark": s.get("benchmark", "")[:200],
            "topics": s.get("topics", []),
            "vocabulary": s.get("vocabulary", []),
            "dok": s.get("dok", ""),
        })

    try:
        from openai import OpenAI
        from backend.api_keys import get_api_key as _gak
        api_key = _gak('openai', getattr(g, 'user_id', 'local-dev'))

        if not api_key or api_key.strip() == "" or "your-key-here" in api_key:
            return jsonify({"error": "Missing or placeholder OpenAI API Key"})

        client = OpenAI(api_key=api_key)

        # Truncate document to fit in context with standards
        truncated_doc = doc_text[:8000]

        system_prompt = (
            "You are an expert curriculum alignment specialist. "
            "Analyze the educational document against the provided standards and return a detailed alignment analysis. "
            "Be specific about what content in the document maps to each standard. "
            "Only include standards with at least some relevance (confidence > 0.2). "
            "Sort matched_standards by confidence descending."
        )

        user_prompt = json.dumps({
            "task": "Analyze this educational document and identify which standards it aligns to.",
            "document_text": truncated_doc,
            "available_standards": standards_ref,
            "return_format": {
                "matched_standards": [{"code": "str", "benchmark": "str", "confidence": "float 0.0-1.0", "evidence": "brief quote or description from document", "alignment_notes": "what is well-covered vs missing"}],
                "unmatched_standards": ["standard codes not covered"],
                "overall_alignment_score": "float 0.0-1.0",
                "suggestions": ["improvement suggestion strings"],
                "question_analysis": [{"question_text": "truncated question", "aligned_standard": "code or null", "alignment_quality": "strong|partial|weak|none", "rewrite_suggestion": "optional string or null"}]
            }
        })

        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
        )

        result = json.loads(completion.choices[0].message.content)

        # Reuse existing cost tracking (lines 29, 46)
        usage = _extract_usage(completion, "gpt-4o")
        _record_planner_cost(usage)

        return jsonify({**result, "usage": usage})

    except Exception as e:
        return jsonify({"error": f"Standards alignment failed: {str(e)}"})


@planner_bp.route('/api/rewrite-for-alignment', methods=['POST'])
def rewrite_for_alignment():
    """Rewrite specific questions to better align with selected standards."""
    data = request.json
    questions = data.get('questions', [])
    doc_text = data.get('documentText', '')
    grade = data.get('grade', '7')
    subject = data.get('subject', '')
    state = data.get('state', 'FL')

    if not questions:
        return jsonify({"error": "No questions provided for rewriting"})

    # Load full standard details for context
    standards = load_standards(state, subject, grade)
    standards_by_code = {s.get("code"): s for s in standards} if standards else {}

    # Enrich questions with full standard details
    enriched_questions = []
    for q in questions:
        std_code = q.get('target_standard', '')
        std_detail = standards_by_code.get(std_code, {})
        enriched_questions.append({
            "original_text": q.get('original_text', ''),
            "target_standard_code": std_code,
            "target_benchmark": std_detail.get('benchmark', ''),
            "target_topics": std_detail.get('topics', []),
            "target_vocabulary": std_detail.get('vocabulary', []),
            "essential_questions": std_detail.get('essential_questions', []),
            "rewrite_goal": q.get('rewrite_goal', ''),
        })

    try:
        from openai import OpenAI
        from backend.api_keys import get_api_key as _gak
        api_key = _gak('openai', getattr(g, 'user_id', 'local-dev'))

        if not api_key or api_key.strip() == "" or "your-key-here" in api_key:
            return jsonify({"error": "Missing or placeholder OpenAI API Key"})

        client = OpenAI(api_key=api_key)

        system_prompt = (
            f"You are an expert curriculum specialist for grade {grade} {subject}. "
            "Rewrite the given questions to better align with the target standards. "
            "Preserve the general topic and difficulty level but adjust the focus, "
            "vocabulary, and cognitive demand to match the standard's benchmark. "
            "Keep the question appropriate for the grade level."
        )

        user_prompt = json.dumps({
            "task": "Rewrite each question to better align with its target standard.",
            "document_context": doc_text[:3000],
            "questions": enriched_questions,
            "return_format": {
                "rewrites": [{"original_text": "str", "rewritten_text": "str", "standard_code": "str", "change_explanation": "brief explanation of what changed and why"}]
            }
        })

        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
        )

        result = json.loads(completion.choices[0].message.content)

        usage = _extract_usage(completion, "gpt-4o-mini")
        _record_planner_cost(usage)

        return jsonify({**result, "usage": usage})

    except Exception as e:
        return jsonify({"error": f"Rewrite failed: {str(e)}"})
```

---

## File 2: `frontend/src/services/api.js`

### Edit A: Add two API functions

**Location:** After line 277 (after `getStandards` function)

**Insert after this existing code:**
```javascript
export async function getStandards(config) {
  return fetchApi('/api/get-standards', {
    method: 'POST',
    body: JSON.stringify(config),
  })
}
```

**New code to insert:**
```javascript

export async function alignDocumentToStandards(data) {
  return fetchApi('/api/align-document-to-standards', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function rewriteForAlignment(data) {
  return fetchApi('/api/rewrite-for-alignment', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}
```

### Edit B: Add to default export object

**Location:** After line 1098 (`getStandards,`)

**Insert after this existing line:**
```javascript
  getStandards,
```

**New lines to insert:**
```javascript
  alignDocumentToStandards,
  rewriteForAlignment,
```

---

## File 3: `frontend/src/App.jsx`

### Edit A: Add state variables

**Location:** After line 1340 (`const [modelAnswersLoading, setModelAnswersLoading] = useState(false);`)

**Insert after this existing line:**
```javascript
  const [modelAnswersLoading, setModelAnswersLoading] = useState(false);
```

**New code to insert:**
```javascript
  const [standardsAlignment, setStandardsAlignment] = useState(null);
  const [alignmentLoading, setAlignmentLoading] = useState(false);
  const [rewriteLoading, setRewriteLoading] = useState(false);
```

### Edit B: Add handler functions

**Location:** After line 3763 (end of `handleGenerateModelAnswers`), before line 3765 (`const removeMarker`)

**Insert after this existing code:**
```javascript
  };

  const removeMarker = (marker, markerIndex) => {
```

**Replace with:**
```javascript
  };

  const handleAlignToStandards = async () => {
    var docText = importedDoc.text || (importedDoc.html ? importedDoc.html.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim() : '');
    if (!importedDoc || !docText) {
      addToast("Import the assignment document first", "warning");
      return;
    }
    if (!config.subject) {
      addToast("Set your subject in Settings first", "warning");
      return;
    }
    setAlignmentLoading(true);
    setStandardsAlignment(null);
    try {
      var data = await api.alignDocumentToStandards({
        documentText: docText,
        state: config.state || "FL",
        grade: config.grade_level || "7",
        subject: config.subject,
      });
      if (data.error) { addToast(data.error, "error"); return; }
      setStandardsAlignment(data);
      addToast((data.matched_standards || []).length + " standards identified", "success");
    } catch (err) {
      addToast("Alignment failed: " + err.message, "error");
    } finally {
      setAlignmentLoading(false);
    }
  };

  const handleRewriteForAlignment = async (questions) => {
    setRewriteLoading(true);
    try {
      var docText = importedDoc.text || '';
      var data = await api.rewriteForAlignment({
        questions: questions,
        documentText: docText,
        grade: config.grade_level || "7",
        subject: config.subject || "",
        state: config.state || "FL",
      });
      if (data.error) { addToast(data.error, "error"); return; }
      setStandardsAlignment(function(prev) {
        return Object.assign({}, prev, { rewrites: data.rewrites });
      });
      addToast((data.rewrites || []).length + " questions rewritten", "success");
    } catch (err) {
      addToast("Rewrite failed: " + err.message, "error");
    } finally {
      setRewriteLoading(false);
    }
  };

  const removeMarker = (marker, markerIndex) => {
```

### Edit C: Clear alignment on new doc import

**Location:** Inside `handleDocImport`, after `setImportedDoc(...)` and before `setLoadedAssignmentName("")`

**Find this existing code:**
```javascript
        setImportedDoc({
          text: data.text || "",
          html: data.html || "",
          filename: file.name,
          loading: false,
        });
        setLoadedAssignmentName("");
```

**Replace with:**
```javascript
        setImportedDoc({
          text: data.text || "",
          html: data.html || "",
          filename: file.name,
          loading: false,
        });
        setStandardsAlignment(null);
        setLoadedAssignmentName("");
```

### Edit D: Pass new props to BuilderTab

**Location:** After `handleGenerateModelAnswers={handleGenerateModelAnswers}` prop

**Insert after this existing line:**
```javascript
                  handleGenerateModelAnswers={handleGenerateModelAnswers}
```

**New lines to insert:**
```javascript
                  standardsAlignment={standardsAlignment}
                  alignmentLoading={alignmentLoading}
                  rewriteLoading={rewriteLoading}
                  handleAlignToStandards={handleAlignToStandards}
                  handleRewriteForAlignment={handleRewriteForAlignment}
```

---

## File 4: `frontend/src/tabs/BuilderTab.jsx`

### Edit A: Add new props to component signature

**Location:** After `modelAnswersLoading,` in the component props

**Insert after this existing line:**
```javascript
  modelAnswersLoading,
```

**New lines to insert:**
```javascript
  standardsAlignment,
  alignmentLoading,
  rewriteLoading,
  handleAlignToStandards,
  handleRewriteForAlignment,
```

### Edit B: Add UI — button and results panel

**Location:** After the closing of Model Answers section, before `{/* Grading Notes */}`

**Find this existing code:**
```jsx
                    )}

                    {/* Grading Notes */}
```

**Replace with:**
```jsx
                    )}

                    {/* Align to Standards */}
                    {importedDoc && (importedDoc.text || importedDoc.html) && (
                      <div style={{ marginTop: "12px", marginBottom: "20px" }}>
                        <button
                          className="btn btn-secondary"
                          onClick={handleAlignToStandards}
                          disabled={alignmentLoading}
                          style={{ display: "flex", alignItems: "center", gap: "6px" }}
                        >
                          {alignmentLoading
                            ? <><Icon name="Loader2" size={14} className="spinning" /> Analyzing Standards...</>
                            : <><Icon name="BookOpen" size={14} /> Align to Standards</>}
                        </button>

                        {standardsAlignment && (
                          <div style={{
                            marginTop: "15px",
                            padding: "20px",
                            background: "rgba(99,102,241,0.08)",
                            borderRadius: "12px",
                            border: "1px solid rgba(99,102,241,0.3)",
                          }}>
                            {/* Overall Score */}
                            <div style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: "15px" }}>
                              <h4 style={{ margin: 0, fontSize: "1rem" }}>Standards Alignment</h4>
                              <div style={{
                                flex: 1, height: "8px", background: "rgba(255,255,255,0.1)",
                                borderRadius: "4px", overflow: "hidden"
                              }}>
                                <div style={{
                                  width: Math.round((standardsAlignment.overall_alignment_score || 0) * 100) + "%",
                                  height: "100%",
                                  background: (standardsAlignment.overall_alignment_score || 0) > 0.7 ? "#4ade80"
                                    : (standardsAlignment.overall_alignment_score || 0) > 0.4 ? "#fbbf24" : "#ef4444",
                                  borderRadius: "4px",
                                  transition: "width 0.5s ease",
                                }} />
                              </div>
                              <span style={{ fontWeight: 600, minWidth: "40px", textAlign: "right" }}>
                                {Math.round((standardsAlignment.overall_alignment_score || 0) * 100)}%
                              </span>
                            </div>

                            {/* Matched Standards */}
                            {(standardsAlignment.matched_standards || []).map(function(std, idx) {
                              return (
                                <div key={std.code || idx} style={{
                                  padding: "10px 12px",
                                  background: "var(--input-bg)",
                                  borderRadius: "8px",
                                  marginBottom: "8px",
                                  borderLeft: "3px solid " + (std.confidence > 0.7 ? "#4ade80" : std.confidence > 0.4 ? "#fbbf24" : "#ef4444"),
                                }}>
                                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                                    <strong style={{ fontSize: "0.9rem" }}>{std.code}</strong>
                                    <span style={{
                                      fontSize: "0.8rem", fontWeight: 600,
                                      color: std.confidence > 0.7 ? "#4ade80" : std.confidence > 0.4 ? "#fbbf24" : "#ef4444",
                                    }}>{Math.round(std.confidence * 100)}% match</span>
                                  </div>
                                  <p style={{ fontSize: "0.85rem", margin: "4px 0", color: "var(--text-primary)" }}>{std.benchmark}</p>
                                  {std.evidence && (
                                    <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", margin: "2px 0" }}>
                                      <em>Evidence:</em> {std.evidence}
                                    </p>
                                  )}
                                  {std.alignment_notes && (
                                    <p style={{ fontSize: "0.8rem", color: "#fbbf24", margin: "2px 0" }}>{std.alignment_notes}</p>
                                  )}
                                </div>
                              );
                            })}

                            {/* Suggestions */}
                            {(standardsAlignment.suggestions || []).length > 0 && (
                              <div style={{ marginTop: "12px" }}>
                                <h5 style={{ margin: "0 0 8px", fontSize: "0.9rem" }}>Improvement Suggestions</h5>
                                <ul style={{ margin: 0, paddingLeft: "20px", fontSize: "0.85rem" }}>
                                  {standardsAlignment.suggestions.map(function(s, i) {
                                    return <li key={i} style={{ marginBottom: "4px" }}>{s}</li>;
                                  })}
                                </ul>
                              </div>
                            )}

                            {/* Question Analysis */}
                            {(standardsAlignment.question_analysis || []).filter(function(q) { return q.rewrite_suggestion; }).length > 0 && (
                              <div style={{ marginTop: "15px" }}>
                                <h5 style={{ margin: "0 0 8px", fontSize: "0.9rem" }}>Question-Level Analysis</h5>
                                {standardsAlignment.question_analysis.filter(function(q) { return q.rewrite_suggestion; }).map(function(q, i) {
                                  return (
                                    <div key={i} style={{
                                      padding: "10px 12px",
                                      background: "var(--input-bg)",
                                      borderRadius: "8px",
                                      marginBottom: "8px",
                                    }}>
                                      <p style={{ fontSize: "0.85rem", margin: "0 0 4px" }}>
                                        <strong>Q:</strong> {(q.question_text || "").substring(0, 120)}{(q.question_text || "").length > 120 ? "..." : ""}
                                      </p>
                                      <p style={{ fontSize: "0.8rem", margin: "2px 0", color: "var(--text-secondary)" }}>
                                        Aligned to: {q.aligned_standard || "None"} ({q.alignment_quality || "unknown"})
                                      </p>
                                      <p style={{ fontSize: "0.8rem", margin: "2px 0", color: "#fbbf24" }}>{q.rewrite_suggestion}</p>
                                      <button
                                        className="btn btn-secondary"
                                        onClick={function() {
                                          handleRewriteForAlignment([{
                                            original_text: q.question_text,
                                            target_standard: q.aligned_standard,
                                            rewrite_goal: q.rewrite_suggestion
                                          }]);
                                        }}
                                        disabled={rewriteLoading}
                                        style={{ fontSize: "0.8rem", padding: "4px 10px", marginTop: "6px" }}
                                      >
                                        {rewriteLoading ? "Rewriting..." : "Rewrite This Question"}
                                      </button>
                                    </div>
                                  );
                                })}
                              </div>
                            )}

                            {/* Rewrites */}
                            {standardsAlignment.rewrites && standardsAlignment.rewrites.length > 0 && (
                              <div style={{ marginTop: "15px" }}>
                                <h5 style={{ margin: "0 0 8px", fontSize: "0.9rem" }}>Rewritten Questions</h5>
                                {standardsAlignment.rewrites.map(function(r, i) {
                                  return (
                                    <div key={i} style={{
                                      padding: "10px 12px",
                                      background: "var(--input-bg)",
                                      borderRadius: "8px",
                                      marginBottom: "8px",
                                      borderLeft: "3px solid #4ade80",
                                    }}>
                                      <p style={{ fontSize: "0.8rem", margin: "0 0 4px", color: "var(--text-secondary)" }}>
                                        <strong>Original:</strong> {r.original_text}
                                      </p>
                                      <p style={{ fontSize: "0.85rem", margin: "4px 0", color: "#4ade80" }}>
                                        <strong>Rewritten:</strong> {r.rewritten_text}
                                      </p>
                                      <p style={{ fontSize: "0.8rem", margin: "2px 0", color: "var(--text-secondary)" }}>
                                        <em>{r.standard_code}:</em> {r.change_explanation}
                                      </p>
                                    </div>
                                  );
                                })}
                              </div>
                            )}

                            {/* Cost info */}
                            {standardsAlignment.usage && (
                              <p style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: "10px", textAlign: "right" }}>
                                {standardsAlignment.usage.cost_display || ""}
                              </p>
                            )}
                          </div>
                        )}
                      </div>
                    )}

                    {/* Grading Notes */}
```

---

## Verification

1. `cd frontend && npm run build` — no build errors
2. Start backend: `source venv/bin/activate && python -m backend.app`
3. Import a document in Builder tab
4. Set subject/grade in Settings (e.g., Civics, Grade 7)
5. Click "Align to Standards" — should show matched standards with confidence scores and overall alignment bar
6. Click "Rewrite This Question" on a weak-alignment question — should show before/after with explanation
7. Import a different document — alignment results should clear
8. Try with no subject set — should show warning toast "Set your subject in Settings first"
9. Try with blank document — should show warning toast "Import the assignment document first"
