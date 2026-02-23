# Cornell Notes Submission Portal — Implementation Plan

## Overview

Add a structured Cornell Notes submission mode to the student portal. Students join with a code (same flow as assessments), but instead of answering quiz questions, they fill in a structured Cornell Notes form with **Cue Column**, **Notes Column**, and **Summary** sections. Drafts autosave every 30 seconds. Teachers see completion progress and can grade with the existing Cornell Notes rubric pipeline.

---

## Architecture Summary

```
Student enters join code → Loads cornell_notes assessment type
  → Renders structured form (cues / notes / summary)
  → Autosaves draft every 30s to Supabase `drafts` table
  → Student clicks Submit → graded via existing Cornell rubric
  → Teacher sees progress dashboard (draft % / submitted / graded)
```

**No Word doc.** Students interact with a structured form. Export to `.docx` happens after submission for teacher records.

---

## Database Changes

### New Table: `drafts`

**File: `backend/database/supabase_schema.sql`**

Add after the `submissions` table block (after line 48):

```sql
-- ============================================
-- DRAFTS TABLE (Autosave for in-progress work)
-- ============================================
CREATE TABLE IF NOT EXISTS drafts (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    assessment_id UUID REFERENCES published_assessments(id) ON DELETE CASCADE,
    join_code VARCHAR(10) NOT NULL,
    student_name TEXT NOT NULL,
    answers JSONB NOT NULL DEFAULT '{}'::jsonb,
    progress_percent NUMERIC(5,2) DEFAULT 0,
    last_saved_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(join_code, student_name)  -- One draft per student per assessment
);

CREATE INDEX IF NOT EXISTS idx_drafts_join_code ON drafts(join_code);
CREATE INDEX IF NOT EXISTS idx_drafts_student ON drafts(student_name);

-- RLS for drafts
ALTER TABLE drafts ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Anyone can insert drafts" ON drafts
    FOR INSERT WITH CHECK (true);

CREATE POLICY "Anyone can update own drafts" ON drafts
    FOR UPDATE USING (true);

CREATE POLICY "Anyone can read drafts" ON drafts
    FOR SELECT USING (true);

CREATE POLICY "Service role has full access to drafts" ON drafts
    FOR ALL USING (auth.role() = 'service_role');
```

### Modify `published_assessments` Settings JSONB

No schema change needed — the existing `settings JSONB` column already supports arbitrary keys. We add:

```json
{
  "assessment_mode": "cornell_notes",
  "cornell_config": {
    "topic": "Chapter 5: The Civil War",
    "num_cue_rows": 10,
    "require_summary": true,
    "min_summary_words": 30,
    "vocabulary_terms": ["secession", "abolition", "confederacy"],
    "due_date": "2026-02-28T23:59:00Z"
  }
}
```

---

## Backend Changes

### File: `backend/routes/student_portal_routes.py`

#### 1. Add draft save endpoint (after line 525)

```python
@student_portal_bp.route('/api/student/save-draft/<code>', methods=['POST'])
def save_draft(code):
    """
    Autosave student draft. Upserts based on join_code + student_name.
    Called every 30 seconds from frontend.
    """
    try:
        db = get_supabase()
        code = code.upper()

        # Verify assessment exists and is active
        assessment_result = db.table('published_assessments').select('id, is_active').eq('join_code', code).execute()
        if not assessment_result.data:
            return jsonify({"error": "Assessment not found"}), 404
        if not assessment_result.data[0].get('is_active', True):
            return jsonify({"error": "Assessment is no longer active"}), 403

        data = request.json
        student_name = data.get('student_name', '').strip()
        answers = data.get('answers', {})
        progress_percent = data.get('progress_percent', 0)

        if not student_name:
            return jsonify({"error": "Student name required"}), 400

        assessment_id = assessment_result.data[0]['id']

        # Upsert: update if exists, insert if not
        existing = db.table('drafts').select('id').eq('join_code', code).ilike('student_name', student_name).execute()

        if existing.data:
            db.table('drafts').update({
                "answers": answers,
                "progress_percent": progress_percent,
                "last_saved_at": datetime.now().isoformat(),
            }).eq('id', existing.data[0]['id']).execute()
        else:
            db.table('drafts').insert({
                "assessment_id": assessment_id,
                "join_code": code,
                "student_name": student_name,
                "answers": answers,
                "progress_percent": progress_percent,
            }).execute()

        return jsonify({"success": True, "saved_at": datetime.now().isoformat()})

    except Exception as e:
        print(f"Save draft error: {e}")
        return jsonify({"error": str(e)}), 500


@student_portal_bp.route('/api/student/load-draft/<code>', methods=['POST'])
def load_draft(code):
    """Load a student's saved draft when they rejoin."""
    try:
        db = get_supabase()
        code = code.upper()

        data = request.json
        student_name = data.get('student_name', '').strip()

        if not student_name:
            return jsonify({"error": "Student name required"}), 400

        result = db.table('drafts').select('*').eq('join_code', code).ilike('student_name', student_name).execute()

        if result.data:
            draft = result.data[0]
            return jsonify({
                "has_draft": True,
                "answers": draft.get('answers', {}),
                "progress_percent": draft.get('progress_percent', 0),
                "last_saved_at": draft.get('last_saved_at'),
            })
        else:
            return jsonify({"has_draft": False})

    except Exception as e:
        print(f"Load draft error: {e}")
        return jsonify({"error": str(e)}), 500


@student_portal_bp.route('/api/teacher/assessment/<code>/drafts', methods=['GET'])
def get_assessment_drafts(code):
    """Get all drafts for an assessment (teacher progress dashboard)."""
    try:
        db = get_supabase()
        code = code.upper()

        result = db.table('drafts').select('*').eq('join_code', code).order('last_saved_at', desc=True).execute()

        drafts = [{
            "student_name": d.get('student_name'),
            "progress_percent": d.get('progress_percent', 0),
            "last_saved_at": d.get('last_saved_at'),
        } for d in result.data]

        return jsonify({"drafts": drafts})

    except Exception as e:
        print(f"Get drafts error: {e}")
        return jsonify({"error": str(e)}), 500
```

#### 2. Modify `get_assessment_for_student` (line 371)

In the response dict (around line 422), add `assessment_mode` to the returned settings:

**Find** (line 428-434):
```python
        return jsonify({
            "title": assessment.get('title'),
            "instructions": assessment.get('instructions'),
            "total_points": assessment.get('total_points'),
            "time_estimate": assessment.get('time_estimate'),
            "sections": sanitized_sections,
            "settings": {
                "time_limit_minutes": settings.get('time_limit_minutes'),
                "require_name": settings.get('require_name', True),
                "is_makeup": is_makeup,
                "restricted_students": restricted_students,
                "period": settings.get('period', ''),
            },
```

**Replace with:**
```python
        return jsonify({
            "title": assessment.get('title'),
            "instructions": assessment.get('instructions'),
            "total_points": assessment.get('total_points'),
            "time_estimate": assessment.get('time_estimate'),
            "sections": sanitized_sections,
            "settings": {
                "time_limit_minutes": settings.get('time_limit_minutes'),
                "require_name": settings.get('require_name', True),
                "is_makeup": is_makeup,
                "restricted_students": restricted_students,
                "period": settings.get('period', ''),
                "assessment_mode": settings.get('assessment_mode', 'standard'),
                "cornell_config": settings.get('cornell_config', {}),
            },
```

#### 3. Modify `submit_assessment` to clean up draft on submit (line 444)

**Find** (lines 487-498, inside the submission insert block):
```python
        # Insert submission
        submission_result = db.table('submissions').insert({
```

**Add BEFORE that line:**
```python
        # Delete draft now that student is submitting
        db.table('drafts').delete().eq('join_code', code).ilike('student_name', student_name).execute()

```

---

## Frontend Changes

### File: `frontend/src/services/api.js`

#### Add draft API functions (after line 633, after `submitStudentAssessment`)

```javascript
export async function saveDraft(joinCode, studentName, answers, progressPercent) {
  return fetchApi(`/api/student/save-draft/${joinCode}`, {
    method: 'POST',
    body: JSON.stringify({
      student_name: studentName,
      answers,
      progress_percent: progressPercent,
    }),
  })
}

export async function loadDraft(joinCode, studentName) {
  return fetchApi(`/api/student/load-draft/${joinCode}`, {
    method: 'POST',
    body: JSON.stringify({ student_name: studentName }),
  })
}

export async function getAssessmentDrafts(code) {
  return fetchApi(`/api/teacher/assessment/${code}/drafts`)
}
```

---

### File: `frontend/src/components/StudentPortal.jsx`

This is the largest set of changes. The portal needs to detect `assessment_mode === "cornell_notes"` and render a different UI.

#### 1. Add imports and state (top of file, after line 7)

**Find** (line 7):
```javascript
import MathInput from "./MathInput";
```

**Add after:**
```javascript
import * as api from "../services/api";
```

Wait — `api` is already imported on line 6. Good. No change needed.

#### 2. Add new state variables (after line 42)

**Find** (line 42):
```javascript
  const [studentAccommodation, setStudentAccommodation] = useState(null);
```

**Add after:**
```javascript
  const [draftStatus, setDraftStatus] = useState(""); // "", "saving", "saved", "error"
  const [lastSaved, setLastSaved] = useState(null);
  const [draftLoaded, setDraftLoaded] = useState(false);
```

#### 3. Add autosave effect and draft loading (after line 49)

**Find** (line 49):
```javascript
  }, [urlCode]);
```

**Add after:**
```javascript

  // Autosave draft every 30 seconds
  useEffect(() => {
    if (stage !== "assessment" || !studentName || !joinCode) return;
    const isCornell = assessment?.settings?.assessment_mode === "cornell_notes";
    if (!isCornell) return;

    const interval = setInterval(async () => {
      const filledKeys = Object.keys(answers).filter(k => answers[k] && answers[k].trim && answers[k].trim() !== "");
      if (filledKeys.length === 0) return;

      setDraftStatus("saving");
      try {
        const progress = calculateCornellProgress(answers, assessment?.settings?.cornell_config);
        await api.saveDraft(joinCode, studentName, answers, progress);
        setDraftStatus("saved");
        setLastSaved(new Date());
        setTimeout(() => setDraftStatus(""), 3000);
      } catch (e) {
        setDraftStatus("error");
        setTimeout(() => setDraftStatus(""), 5000);
      }
    }, 30000);

    return () => clearInterval(interval);
  }, [stage, studentName, joinCode, answers, assessment]);

  // Load draft when entering assessment
  useEffect(() => {
    if (stage !== "assessment" || draftLoaded) return;
    const isCornell = assessment?.settings?.assessment_mode === "cornell_notes";
    if (!isCornell) return;

    (async () => {
      try {
        const result = await api.loadDraft(joinCode, studentName);
        if (result.has_draft && result.answers) {
          setAnswers(result.answers);
          setLastSaved(new Date(result.last_saved_at));
        }
      } catch (e) {
        // No draft found — that's fine
      }
      setDraftLoaded(true);
    })();
  }, [stage, draftLoaded]);

  // Calculate Cornell Notes completion percentage
  const calculateCornellProgress = (ans, config) => {
    if (!config) return 0;
    const numCues = config.num_cue_rows || 10;
    const requireSummary = config.require_summary !== false;
    const vocabTerms = config.vocabulary_terms || [];

    let filled = 0;
    let total = 0;

    // Cue column entries
    for (let i = 0; i < numCues; i++) {
      total += 2; // cue + note for each row
      if (ans[`cue-${i}`] && ans[`cue-${i}`].trim()) filled++;
      if (ans[`note-${i}`] && ans[`note-${i}`].trim()) filled++;
    }

    // Summary
    if (requireSummary) {
      total += 1;
      if (ans["summary"] && ans["summary"].trim()) filled++;
    }

    // Vocabulary
    for (let i = 0; i < vocabTerms.length; i++) {
      total += 1;
      if (ans[`vocab-${i}`] && ans[`vocab-${i}`].trim()) filled++;
    }

    return total > 0 ? Math.round((filled / total) * 100) : 0;
  };
```

#### 4. Add Cornell Notes renderer inside the assessment screen (line 327)

The key change is in the `if (stage === "assessment")` block. We check `assessment_mode` and render either the existing quiz UI or the new Cornell Notes form.

**Find** (line 327):
```javascript
  // ============ ASSESSMENT SCREEN ============
  if (stage === "assessment") {
    const totalQuestions = assessment?.sections?.reduce((sum, s) => sum + (s.questions?.length || 0), 0) || 0;
    const answeredCount = Object.keys(answers).filter((k) => answers[k] !== undefined && answers[k] !== "").length;
```

**Replace with:**
```javascript
  // ============ ASSESSMENT SCREEN ============
  if (stage === "assessment") {
    const isCornell = assessment?.settings?.assessment_mode === "cornell_notes";

    // ---- CORNELL NOTES MODE ----
    if (isCornell) {
      const config = assessment?.settings?.cornell_config || {};
      const numCues = config.num_cue_rows || 10;
      const vocabTerms = config.vocabulary_terms || [];
      const requireSummary = config.require_summary !== false;
      const progress = calculateCornellProgress(answers, config);

      return (
        <div style={containerStyle}>
          {/* Header */}
          <div style={{ position: "sticky", top: 0, background: "rgba(15, 15, 35, 0.95)", borderBottom: "1px solid rgba(255,255,255,0.1)", padding: "15px 20px", zIndex: 100 }}>
            <div style={{ maxWidth: "900px", margin: "0 auto", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div>
                <h1 style={{ fontSize: "1.2rem", fontWeight: 700, marginBottom: "4px" }}>{assessment?.title}</h1>
                <span style={{ fontSize: "0.9rem", color: "rgba(255,255,255,0.6)" }}>{studentName}</span>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: "15px" }}>
                {/* Progress bar */}
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <div style={{ width: "120px", height: "8px", background: "rgba(255,255,255,0.1)", borderRadius: "4px", overflow: "hidden" }}>
                    <div style={{ width: progress + "%", height: "100%", background: progress === 100 ? "#22c55e" : "#8b5cf6", borderRadius: "4px", transition: "width 0.3s ease" }} />
                  </div>
                  <span style={{ fontSize: "0.85rem", color: "rgba(255,255,255,0.6)" }}>{progress}%</span>
                </div>
                {/* Save status */}
                {draftStatus === "saving" && (
                  <span style={{ fontSize: "0.8rem", color: "#fbbf24" }}>Saving...</span>
                )}
                {draftStatus === "saved" && (
                  <span style={{ fontSize: "0.8rem", color: "#22c55e" }}>Saved</span>
                )}
                {draftStatus === "error" && (
                  <span style={{ fontSize: "0.8rem", color: "#ef4444" }}>Save failed</span>
                )}
                <button
                  onClick={handleSubmit}
                  disabled={loading}
                  style={{
                    ...buttonStyle,
                    width: "auto",
                    padding: "10px 20px",
                    fontSize: "1rem",
                    background: progress === 100 ? "linear-gradient(135deg, #22c55e, #16a34a)" : "linear-gradient(135deg, #8b5cf6, #6366f1)",
                  }}
                >
                  {loading ? "Submitting..." : "Submit"}
                  <Icon name="Send" />
                </button>
              </div>
            </div>
          </div>

          {/* Cornell Notes Form */}
          <div style={{ maxWidth: "900px", margin: "0 auto", padding: "30px 20px" }}>
            {/* Topic header */}
            {config.topic && (
              <div style={{ background: "rgba(34, 211, 238, 0.1)", border: "1px solid rgba(34, 211, 238, 0.3)", borderRadius: "10px", padding: "15px 20px", marginBottom: "25px" }}>
                <div style={{ fontSize: "0.85rem", color: "#22d3ee", fontWeight: 600, marginBottom: "4px" }}>Topic</div>
                <div style={{ fontSize: "1.1rem", fontWeight: 600 }}>{config.topic}</div>
              </div>
            )}

            {assessment?.instructions && (
              <div style={{ background: "rgba(99, 102, 241, 0.1)", border: "1px solid rgba(99, 102, 241, 0.3)", borderRadius: "8px", padding: "15px", marginBottom: "25px" }}>
                <strong>Instructions:</strong> {assessment.instructions}
              </div>
            )}

            {/* Cornell Notes Grid */}
            <div style={{
              ...cardStyle,
              maxWidth: "100%",
              padding: "0",
              overflow: "hidden",
              marginBottom: "25px",
            }}>
              {/* Column Headers */}
              <div style={{ display: "grid", gridTemplateColumns: "250px 1fr", borderBottom: "2px solid rgba(34, 211, 238, 0.4)" }}>
                <div style={{ padding: "12px 15px", background: "rgba(34, 211, 238, 0.15)", fontWeight: 700, color: "#22d3ee", fontSize: "0.95rem" }}>
                  Cue Column (Questions/Terms)
                </div>
                <div style={{ padding: "12px 15px", background: "rgba(139, 92, 246, 0.15)", fontWeight: 700, color: "#a78bfa", fontSize: "0.95rem" }}>
                  Notes
                </div>
              </div>

              {/* Note Rows */}
              {Array.from({ length: numCues }).map((_, i) => (
                <div key={i} style={{ display: "grid", gridTemplateColumns: "250px 1fr", borderBottom: "1px solid rgba(255,255,255,0.08)" }}>
                  <div style={{ padding: "8px 10px", borderRight: "1px solid rgba(255,255,255,0.1)" }}>
                    <textarea
                      value={answers[`cue-${i}`] || ""}
                      onChange={(e) => setAnswer(`cue-${i}`, e.target.value)}
                      placeholder={`Question or key term ${i + 1}...`}
                      rows={2}
                      style={{
                        width: "100%",
                        padding: "8px",
                        borderRadius: "6px",
                        border: "1px solid rgba(255,255,255,0.1)",
                        background: "rgba(0,0,0,0.2)",
                        color: "white",
                        fontSize: "0.9rem",
                        resize: "vertical",
                        fontFamily: "inherit",
                      }}
                    />
                  </div>
                  <div style={{ padding: "8px 10px" }}>
                    <textarea
                      value={answers[`note-${i}`] || ""}
                      onChange={(e) => setAnswer(`note-${i}`, e.target.value)}
                      placeholder={`Notes for row ${i + 1}...`}
                      rows={2}
                      style={{
                        width: "100%",
                        padding: "8px",
                        borderRadius: "6px",
                        border: "1px solid rgba(255,255,255,0.1)",
                        background: "rgba(0,0,0,0.2)",
                        color: "white",
                        fontSize: "0.9rem",
                        resize: "vertical",
                        fontFamily: "inherit",
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>

            {/* Summary Section */}
            {requireSummary && (
              <div style={{ ...cardStyle, maxWidth: "100%", marginBottom: "25px" }}>
                <div style={{ fontWeight: 700, fontSize: "1.1rem", marginBottom: "10px", color: "#22c55e" }}>
                  Summary
                </div>
                <p style={{ fontSize: "0.85rem", color: "rgba(255,255,255,0.5)", marginBottom: "12px" }}>
                  Write a {config.min_summary_words || 30}+ word summary synthesizing the main ideas from your notes.
                </p>
                <textarea
                  value={answers["summary"] || ""}
                  onChange={(e) => setAnswer("summary", e.target.value)}
                  placeholder="Summarize the main ideas in your own words..."
                  rows={5}
                  style={{
                    width: "100%",
                    padding: "12px",
                    borderRadius: "8px",
                    border: "1px solid rgba(255,255,255,0.2)",
                    background: "rgba(0,0,0,0.2)",
                    color: "white",
                    fontSize: "1rem",
                    resize: "vertical",
                    lineHeight: 1.6,
                    fontFamily: "inherit",
                  }}
                />
                {answers["summary"] && (
                  <div style={{ fontSize: "0.8rem", color: "rgba(255,255,255,0.4)", marginTop: "6px", textAlign: "right" }}>
                    {answers["summary"].trim().split(/\s+/).filter(Boolean).length} words
                  </div>
                )}
              </div>
            )}

            {/* Vocabulary Section */}
            {vocabTerms.length > 0 && (
              <div style={{ ...cardStyle, maxWidth: "100%", marginBottom: "25px" }}>
                <div style={{ fontWeight: 700, fontSize: "1.1rem", marginBottom: "15px", color: "#f59e0b" }}>
                  Vocabulary
                </div>
                {vocabTerms.map((term, i) => (
                  <div key={i} style={{ marginBottom: "12px" }}>
                    <label style={{ fontWeight: 600, fontSize: "0.95rem", marginBottom: "6px", display: "block" }}>
                      {term}
                    </label>
                    <input
                      type="text"
                      value={answers[`vocab-${i}`] || ""}
                      onChange={(e) => setAnswer(`vocab-${i}`, e.target.value)}
                      placeholder={`Define "${term}"...`}
                      style={{
                        width: "100%",
                        padding: "10px 12px",
                        borderRadius: "8px",
                        border: "1px solid rgba(255,255,255,0.15)",
                        background: "rgba(0,0,0,0.2)",
                        color: "white",
                        fontSize: "0.95rem",
                        fontFamily: "inherit",
                      }}
                    />
                  </div>
                ))}
              </div>
            )}

            {/* Last saved indicator */}
            {lastSaved && (
              <div style={{ textAlign: "center", fontSize: "0.8rem", color: "rgba(255,255,255,0.3)", marginBottom: "15px" }}>
                Last saved: {lastSaved.toLocaleTimeString()}
              </div>
            )}

            {/* Submit Button */}
            <div style={{ textAlign: "center", padding: "20px 0" }}>
              <button
                onClick={handleSubmit}
                disabled={loading}
                style={{
                  ...buttonStyle,
                  maxWidth: "300px",
                  margin: "0 auto",
                  background: "linear-gradient(135deg, #22c55e, #16a34a)",
                }}
              >
                {loading ? "Submitting..." : "Submit Cornell Notes"}
                <Icon name="Send" />
              </button>
            </div>
          </div>
        </div>
      );
    }

    // ---- STANDARD ASSESSMENT MODE (existing code) ----
    const totalQuestions = assessment?.sections?.reduce((sum, s) => sum + (s.questions?.length || 0), 0) || 0;
    const answeredCount = Object.keys(answers).filter((k) => answers[k] !== undefined && answers[k] !== "").length;
```

> **Note**: The closing of this `if (isCornell)` block returns early, so the existing assessment code below it runs unchanged for standard assessments.

#### 5. Modify `handleStartAssessment` to also save draft on blur (line 80)

No changes needed to `handleStartAssessment`. The autosave `useEffect` handles everything once stage becomes `"assessment"`.

---

### File: `frontend/src/App.jsx` — Teacher Publish UI

#### 1. Add Cornell Notes as an assessment mode when publishing

The teacher already creates assessments in the Planner tab. We need to add a way to publish a Cornell Notes submission (not a quiz). This hooks into the existing publish flow.

**Find the publish assessment section in the Planner tab.** Search for `publish-assessment` or the publish button logic. The teacher needs a dropdown to pick `assessment_mode`.

In the publish dialog/modal, add a mode selector. The exact location depends on the existing publish UI, but the data shape passed to `/api/publish-assessment` needs:

```javascript
settings: {
  ...existingSettings,
  assessment_mode: "cornell_notes",  // or "standard" (default)
  cornell_config: {
    topic: "Chapter 5: The Civil War",
    num_cue_rows: 10,
    require_summary: true,
    min_summary_words: 30,
    vocabulary_terms: ["secession", "abolition"],
  }
}
```

This is a UI addition in the publish modal. The exact code depends on how the publish modal is currently structured in App.jsx (it calls `api.publishAssessment`). The key change:

**In the Planner tab's publish handler**, before calling the API, check if the teacher selected Cornell Notes mode and include the config:

```javascript
// In the publish handler
const publishSettings = {
  teacher_name: teacherName,
  period: selectedPeriod,
  // ... existing settings
  assessment_mode: assessmentMode,  // new state: "standard" or "cornell_notes"
  cornell_config: assessmentMode === "cornell_notes" ? {
    topic: cornellTopic,
    num_cue_rows: parseInt(cornellCueRows) || 10,
    require_summary: cornellRequireSummary,
    min_summary_words: parseInt(cornellMinSummaryWords) || 30,
    vocabulary_terms: cornellVocabTerms.split(",").map(t => t.trim()).filter(Boolean),
  } : undefined,
};
```

#### 2. Teacher progress dashboard for Cornell submissions

In the teacher's assessment results view, add a "Drafts" section showing in-progress students:

```javascript
// Fetch drafts alongside submissions
const draftsData = await api.getAssessmentDrafts(code);

// Render in results view
{draftsData?.drafts?.length > 0 && (
  <div style={{ marginBottom: "25px" }}>
    <h3>In Progress</h3>
    {draftsData.drafts.map((d, i) => (
      <div key={i} style={{ display: "flex", alignItems: "center", gap: "12px", padding: "10px", marginBottom: "8px", background: "rgba(255,255,255,0.03)", borderRadius: "8px" }}>
        <span style={{ fontWeight: 600, flex: 1 }}>{d.student_name}</span>
        <div style={{ width: "100px", height: "6px", background: "rgba(255,255,255,0.1)", borderRadius: "3px", overflow: "hidden" }}>
          <div style={{ width: d.progress_percent + "%", height: "100%", background: d.progress_percent >= 75 ? "#22c55e" : d.progress_percent >= 40 ? "#f59e0b" : "#ef4444", borderRadius: "3px" }} />
        </div>
        <span style={{ fontSize: "0.85rem", color: "rgba(255,255,255,0.5)", width: "45px", textAlign: "right" }}>
          {Math.round(d.progress_percent)}%
        </span>
        <span style={{ fontSize: "0.8rem", color: "rgba(255,255,255,0.3)" }}>
          {new Date(d.last_saved_at).toLocaleString()}
        </span>
      </div>
    ))}
  </div>
)}
```

---

## Grading Integration

### How Cornell Notes submissions get graded

When a student submits Cornell Notes, the `handleSubmit` in `StudentPortal.jsx` calls `api.submitStudentAssessment` which hits `/api/student/submit/<code>`. The `grade_student_submission` function receives `answers` in this shape:

```json
{
  "cue-0": "What caused the Civil War?",
  "note-0": "Tensions between North and South over slavery...",
  "cue-1": "What was secession?",
  "note-1": "Southern states leaving the Union...",
  "summary": "The Civil War was caused by...",
  "vocab-0": "The formal withdrawal of a state from the union",
  "vocab-1": "The movement to end slavery"
}
```

The current `grade_student_submission` iterates over `assessment.sections[].questions[]`. For Cornell Notes mode, the assessment published with `assessment_mode: "cornell_notes"` should include a single section with questions mapped from the structured fields.

#### Option A: Transform at submission time (recommended)

**In `student_portal_routes.py`, modify `submit_assessment`** (around line 483):

**Find** (line 483):
```python
        # Grade the assessment
        assessment = assessment_data.get('assessment', {})
        results = grade_student_submission(assessment, answers)
```

**Replace with:**
```python
        # Grade the assessment
        assessment = assessment_data.get('assessment', {})
        settings = assessment_data.get('settings', {})

        # For Cornell Notes mode, build a gradeable structure from the structured answers
        if settings.get('assessment_mode') == 'cornell_notes':
            cornell_config = settings.get('cornell_config', {})
            results = grade_cornell_submission(cornell_config, answers)
        else:
            results = grade_student_submission(assessment, answers)
```

#### New grading function for Cornell Notes

**Add to `student_portal_routes.py`** (after `grade_student_submission`, after line 727):

```python
def grade_cornell_submission(cornell_config, answers):
    """
    Grade a Cornell Notes submission using AI.
    Evaluates: Content Accuracy (40%), Note Structure (25%),
    Summary Quality (20%), Effort & Completeness (15%).
    """
    num_cues = cornell_config.get('num_cue_rows', 10)
    vocab_terms = cornell_config.get('vocabulary_terms', [])
    topic = cornell_config.get('topic', 'Unknown topic')
    require_summary = cornell_config.get('require_summary', True)
    min_summary_words = cornell_config.get('min_summary_words', 30)

    # Build the student's notes as structured text
    notes_text = f"Topic: {topic}\n\n"
    notes_text += "CUE COLUMN | NOTES\n"
    notes_text += "-" * 50 + "\n"

    filled_rows = 0
    for i in range(num_cues):
        cue = answers.get(f'cue-{i}', '').strip()
        note = answers.get(f'note-{i}', '').strip()
        if cue or note:
            filled_rows += 1
            notes_text += f"{cue or '(empty)'} | {note or '(empty)'}\n"

    summary = answers.get('summary', '').strip()
    notes_text += f"\nSUMMARY:\n{summary or '(no summary provided)'}\n"

    vocab_text = ""
    vocab_correct = 0
    for i, term in enumerate(vocab_terms):
        definition = answers.get(f'vocab-{i}', '').strip()
        vocab_text += f"{term}: {definition or '(not defined)'}\n"

    # Calculate effort/completeness (15%)
    total_fields = num_cues * 2 + (1 if require_summary else 0) + len(vocab_terms)
    filled_fields = 0
    for i in range(num_cues):
        if answers.get(f'cue-{i}', '').strip(): filled_fields += 1
        if answers.get(f'note-{i}', '').strip(): filled_fields += 1
    if summary: filled_fields += 1
    for i in range(len(vocab_terms)):
        if answers.get(f'vocab-{i}', '').strip(): filled_fields += 1

    completeness = filled_fields / total_fields if total_fields > 0 else 0
    effort_score = round(15 * completeness, 1)

    # AI grading for content, structure, and summary
    total_points = 100
    results = {
        "questions": [],
        "score": 0,
        "total_points": total_points,
        "percentage": 0,
        "feedback_summary": ""
    }

    try:
        from openai import OpenAI
        client = OpenAI()

        grading_prompt = f"""Grade these Cornell Notes on the topic: "{topic}"

STUDENT'S NOTES:
{notes_text}

VOCABULARY DEFINITIONS:
{vocab_text}

Grade using these categories (total 100 points):
1. Content Accuracy (40 pts): Are notes factually correct? Do they capture key concepts?
2. Note Structure (25 pts): Are cues meaningful questions/terms? Are notes detailed enough? {filled_rows}/{num_cues} rows filled.
3. Summary Quality (20 pts): Does the summary synthesize main ideas? Word count: {len(summary.split()) if summary else 0} (minimum: {min_summary_words}).
4. Effort & Completeness is pre-calculated at {effort_score}/15 pts ({round(completeness * 100)}% fields filled).

Respond in JSON:
{{
  "content_accuracy": {{"score": <0-40>, "feedback": "<string>"}},
  "note_structure": {{"score": <0-25>, "feedback": "<string>"}},
  "summary_quality": {{"score": <0-20>, "feedback": "<string>"}},
  "vocabulary": {{"score": <0-10 bonus>, "feedback": "<string>"}},
  "overall_feedback": "<2-3 sentence summary>"
}}"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an encouraging teacher grading Cornell Notes. Be supportive but accurate. Evaluate whether the student captured the key ideas in an organized format."},
                {"role": "user", "content": grading_prompt}
            ],
            response_format={"type": "json_object"},
            max_tokens=600
        )

        ai_result = json.loads(response.choices[0].message.content)

        content_score = min(ai_result.get('content_accuracy', {}).get('score', 0), 40)
        structure_score = min(ai_result.get('note_structure', {}).get('score', 0), 25)
        summary_score = min(ai_result.get('summary_quality', {}).get('score', 0), 20)

        total_score = content_score + structure_score + summary_score + effort_score

        # Build question-style results for display
        results["questions"] = [
            {
                "number": 1,
                "question": "Content Accuracy",
                "points_possible": 40,
                "points_earned": content_score,
                "is_correct": content_score >= 28,
                "feedback": ai_result.get('content_accuracy', {}).get('feedback', ''),
                "student_answer": f"{filled_rows} rows of notes",
            },
            {
                "number": 2,
                "question": "Note Structure",
                "points_possible": 25,
                "points_earned": structure_score,
                "is_correct": structure_score >= 18,
                "feedback": ai_result.get('note_structure', {}).get('feedback', ''),
                "student_answer": f"Cue/Notes format",
            },
            {
                "number": 3,
                "question": "Summary Quality",
                "points_possible": 20,
                "points_earned": summary_score,
                "is_correct": summary_score >= 14,
                "feedback": ai_result.get('summary_quality', {}).get('feedback', ''),
                "student_answer": summary[:100] + "..." if len(summary) > 100 else summary or "(no summary)",
            },
            {
                "number": 4,
                "question": "Effort & Completeness",
                "points_possible": 15,
                "points_earned": effort_score,
                "is_correct": effort_score >= 10,
                "feedback": f"{round(completeness * 100)}% of fields completed.",
                "student_answer": f"{filled_fields}/{total_fields} fields filled",
            },
        ]

        results["score"] = round(total_score, 1)
        results["percentage"] = round(total_score)  # Already out of 100
        results["feedback_summary"] = ai_result.get('overall_feedback', '')

    except Exception as e:
        print(f"Cornell Notes AI grading error: {e}")
        # Fallback: grade on completeness only
        results["score"] = effort_score
        results["percentage"] = round(effort_score / 15 * 100)
        results["feedback_summary"] = "Your notes have been recorded. Your teacher will review them."
        results["questions"] = [{
            "number": 1,
            "question": "Effort & Completeness",
            "points_possible": 15,
            "points_earned": effort_score,
            "is_correct": effort_score >= 10,
            "feedback": f"{round(completeness * 100)}% complete. Teacher will review content.",
            "student_answer": f"{filled_fields}/{total_fields} fields",
        }]

    return results
```

---

## Publishing Flow (Teacher)

### How does a teacher publish a Cornell Notes assignment?

Two options:

**Option 1 — Quick Publish from Planner (Recommended for MVP)**

Add a "Cornell Notes" button next to the existing assessment generation in the Planner tab. When clicked, a modal appears:

```
┌──────────────────────────────────────────┐
│ Publish Cornell Notes Assignment         │
├──────────────────────────────────────────┤
│ Topic: [Chapter 5: The Civil War      ]  │
│ Number of rows: [10]                     │
│ Require summary: [x]                     │
│ Min summary words: [30]                  │
│                                          │
│ Vocabulary terms (comma-separated):      │
│ [secession, abolition, confederacy    ]  │
│                                          │
│ Period: [3rd Period  v]                   │
│                                          │
│ [Publish]  [Cancel]                      │
└──────────────────────────────────────────┘
```

This calls `/api/publish-assessment` with `assessment_mode: "cornell_notes"` in settings.

The assessment JSONB can be minimal:
```json
{
  "title": "Cornell Notes: Chapter 5",
  "instructions": "Take notes on Chapter 5 using Cornell format.",
  "total_points": 100,
  "sections": []
}
```

The actual structure comes from `cornell_config` in settings.

---

## File Change Summary

| File | Action | Lines Changed |
|------|--------|---------------|
| `backend/database/supabase_schema.sql` | Add `drafts` table | ~25 new lines |
| `backend/routes/student_portal_routes.py` | Add 3 endpoints + cornell grader | ~200 new lines, 2 edits |
| `frontend/src/services/api.js` | Add 3 API functions | ~25 new lines |
| `frontend/src/components/StudentPortal.jsx` | Add Cornell mode + autosave | ~250 new lines, 1 edit |
| `frontend/src/App.jsx` | Add publish modal for Cornell | ~80 new lines |

**Total: ~580 new lines, 3 existing-line edits.**

---

## Implementation Order

1. **Database** — Run the `drafts` table SQL in Supabase
2. **Backend routes** — Add draft endpoints + cornell grader to `student_portal_routes.py`
3. **Backend settings passthrough** — Edit `get_assessment_for_student` to return `assessment_mode`
4. **Frontend API** — Add `saveDraft`, `loadDraft`, `getAssessmentDrafts` to `api.js`
5. **Student Portal** — Add Cornell Notes UI + autosave to `StudentPortal.jsx`
6. **Teacher Publish** — Add Cornell Notes publish modal to `App.jsx`
7. **Test** — Publish a Cornell Notes assignment, join as student, verify autosave + grading

---

## Edge Cases Handled

- **Student closes browser mid-notes** — Draft autosaved, loads on rejoin
- **Student submits with empty fields** — Completeness score reflects it, AI grades what's there
- **Multiple students same name** — `UNIQUE(join_code, student_name)` prevents conflicting drafts; same duplicate-check logic as existing submissions
- **Teacher deactivates while student is working** — Save-draft endpoint checks `is_active`; submit endpoint checks `is_active`
- **No OpenAI API key** — Fallback to completeness-only grading with teacher review flag
- **Summary too short** — AI prompt includes word count; grader factors it into summary score
- **Draft exists but student already submitted** — Draft deleted on submit; if they try again, duplicate submission check catches it
