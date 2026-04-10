# Phase 1 Progress Tracking Foundation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Propagate question standards into graded results, capture per-question time tracking, and expose attempt history in the teacher UI as a foundation for Phase 2 progress reports.

**Architecture:** Add `question_times` JSONB column to `student_submissions`. Modify 3 grading pipeline paths to embed `standard` per question and compute `standards_mastery` rollups. Student portal tracks per-question elapsed time and sends with submission/draft saves. Teacher UI adds standard badges, standards summary card, and attempt history drawer. New endpoint to return all attempts for class-based content grouped by student.

**Tech Stack:** Python/Flask, React/JSX, Supabase (Postgres JSONB)

**Spec:** `docs/superpowers/specs/2026-04-10-phase1-progress-tracking-foundation-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| Supabase SQL (manual) | **Run once** | Add `question_times` column |
| `backend/services/grading_service.py` | **Modify** | Copy standard into question result dicts + build standards_mastery rollup |
| `backend/services/portal_grading.py` | **Modify** | Same for multipass grading path |
| `backend/routes/student_account_routes.py` | **Modify** | Accept/store `question_times` on submit and draft save |
| `backend/routes/student_portal_routes.py` | **Modify** | Add class-based submissions endpoint returning all attempts |
| `frontend/src/services/api.js` | **Modify** | Add helper for class-based submissions endpoint; update draft/submit helpers to accept question_times |
| `frontend/src/components/StudentPortal.jsx` | **Modify** | Track per-question elapsed time, send with submit/draft saves |
| `frontend/src/App.jsx` | **Modify** | Standard badges, summary card, attempt history drawer |

---

### Task 1: Supabase schema — add question_times column

**Files:**
- Manual SQL (run in Supabase dashboard)

- [ ] **Step 1: Run schema migration**

In the Supabase SQL Editor, run:

```sql
ALTER TABLE student_submissions
  ADD COLUMN IF NOT EXISTS question_times JSONB;
```

- [ ] **Step 2: Verify column exists**

In Supabase dashboard → Table Editor → `student_submissions`. Confirm `question_times` appears as a nullable JSONB column.

- [ ] **Step 3: No commit** — schema only, no code files modified.

---

### Task 2: Backend — embed standards in grade_student_submission and grade_instant_only

**Files:**
- Modify: `backend/services/grading_service.py`

- [ ] **Step 1: Add helper for standards_mastery rollup**

At the top of `backend/services/grading_service.py`, after the existing imports, add:

```python
def _build_standards_mastery(question_results):
    """Roll up per-question scores into a standards_mastery dict.

    Input: list of question result dicts (each may have a 'standard' key).
    Output: { standard_code: { points_earned, points_possible, question_count } }
    Questions without a 'standard' field are skipped.
    """
    mastery = {}
    for qr in question_results:
        code = qr.get('standard')
        if not code:
            continue
        bucket = mastery.setdefault(code, {
            'points_earned': 0,
            'points_possible': 0,
            'question_count': 0,
        })
        bucket['points_earned'] += qr.get('points_earned') or 0
        bucket['points_possible'] += qr.get('points_possible') or 0
        bucket['question_count'] += 1
    return mastery
```

- [ ] **Step 2: Copy standard into question_result in grade_student_submission**

In `backend/services/grading_service.py`, find `grade_student_submission` (line 112). Locate where `question_result = {` is built (line 138). The dict has keys `number, question, type, student_answer, correct_answer, points_possible, points_earned, is_correct, feedback`.

Add `'standard': q.get('standard')` to that dict. The source question `q` is the iteration variable (confirm by reading the surrounding loop). If the variable is named differently, use the correct name.

Also find any OTHER `question_result = {` assembly in the same function (there may be a second block for the "graded case") and add the same field.

- [ ] **Step 3: Compute standards_mastery at end of grade_student_submission**

Just before `grade_student_submission` returns `results`, add:

```python
    results['standards_mastery'] = _build_standards_mastery(results.get('questions', []))
```

- [ ] **Step 4: Copy standard into question_result in grade_instant_only**

In the same file, find `grade_instant_only` (line 258). It also has multiple `question_result = {` blocks (lines 282, the written-question block, the no-answer block, and the MC/TF graded block). Add `'standard': q.get('standard')` to EACH of those dict literals.

- [ ] **Step 5: Compute standards_mastery at end of grade_instant_only**

Before `grade_instant_only` returns its results dict, add:

```python
    results['standards_mastery'] = _build_standards_mastery(results.get('questions', []))
```

- [ ] **Step 6: Run tests**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/ -x -q --ignore=tests/load --ignore=tests/stress 2>&1 | tail -5`
Expected: All pass. If any test asserts specific result shape, it will still pass because we're ADDING fields, not changing existing ones.

- [ ] **Step 7: Commit**

```bash
git add backend/services/grading_service.py
git commit -m "feat: embed standard per question and standards_mastery rollup in grading_service"
```

---

### Task 3: Backend — embed standards in portal_grading.py multipass path

**Files:**
- Modify: `backend/services/portal_grading.py`

- [ ] **Step 1: Import the helper**

In `backend/services/portal_grading.py`, at the top with other imports from grading_service, add:

```python
from backend.services.grading_service import _build_standards_mastery
```

If there's no existing import from grading_service, add this import line near the other backend imports.

- [ ] **Step 2: Copy standard into per_question_scores entries**

In `run_portal_grading_thread` (line 205), find where `per_question_scores` is built. There are 3 places to update:
- Line ~358-366: written questions appended
- Line ~369-376: written questions error case
- Line ~423-431: instant (MC/TF/matching) questions appended

In each of these blocks, the source question is available as `q` (confirm by reading the loop at line 309). Add `'standard': q.get('standard')` to each dict literal being appended to `per_question_scores`.

- [ ] **Step 3: Compute standards_mastery before the DB update**

Find the `sb.table(supabase_table).update({"results": {...}, ...}).eq("id", submission_id).execute()` call (around line 499-512). BEFORE that update call, compute:

```python
    standards_mastery = _build_standards_mastery(per_question_scores)
```

Then include `"standards_mastery": standards_mastery` inside the `results` dict in the update call.

- [ ] **Step 4: Run tests**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/ -x -q --ignore=tests/load --ignore=tests/stress 2>&1 | tail -5`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add backend/services/portal_grading.py
git commit -m "feat: embed standard per question and standards_mastery in portal grading"
```

---

### Task 4: Backend — accept question_times on submit and draft save

**Files:**
- Modify: `backend/routes/student_account_routes.py`

- [ ] **Step 1: Accept question_times in submit_student_work**

In `backend/routes/student_account_routes.py`, find `submit_student_work(content_id)` (line 736). After the line `answers = data.get('answers', {})` (line 747), add:

```python
    question_times = data.get('question_times') or {}
```

- [ ] **Step 2: Store question_times in the submission row**

In the same function, find where `submission_row` is built (around lines 795-817) and where it's inserted via `db.table('student_submissions').insert(submission_row).execute()` (line 820).

Add `'question_times': question_times,` to the `submission_row` dict. If `submission_row` is constructed across multiple lines/blocks, add the field in the final assembled dict before the insert call.

- [ ] **Step 3: Accept question_times in save_submission_draft**

Find `save_submission_draft(content_id)` (line 1215). After `draft_answers = data.get('answers') or {}` (line 1225), add:

```python
        question_times = data.get('question_times') or {}
```

- [ ] **Step 4: Store question_times on draft update and insert**

In the same function, find the two places the row is written: the `.update({...})` call (existing draft update) and the `.insert({...})` call (new draft creation).

In BOTH calls, add `'question_times': question_times,` to the dict.

- [ ] **Step 5: Run tests**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/ -x -q --ignore=tests/load --ignore=tests/stress 2>&1 | tail -5`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add backend/routes/student_account_routes.py
git commit -m "feat: accept and store per-question time tracking on submit and draft save"
```

---

### Task 5: Backend — class-based submissions endpoint with all attempts

**Files:**
- Modify: `backend/routes/student_portal_routes.py`

- [ ] **Step 1: Add list-submissions endpoint**

At the END of `backend/routes/student_portal_routes.py` (after the `list_in_progress_drafts` endpoint added in the save-and-resume work), add:

```python
@student_portal_bp.route('/api/teacher/content/<content_id>/submissions', methods=['GET'])
@require_teacher
@handle_route_errors
def list_content_submissions(content_id):
    """List all submissions (all attempts per student) for a class-based assessment."""
    try:
        db = get_supabase()

        # Verify teacher owns this content
        content = db.table('published_content').select('teacher_id, title, content, settings').eq('id', content_id).execute()
        if not content.data or content.data[0].get('teacher_id') != g.teacher_id:
            return jsonify({"error": "Not authorized"}), 403

        # Fetch all submissions for this content (excluding drafts)
        submissions = db.table('student_submissions').select('*').eq(
            'content_id', content_id
        ).neq('status', 'draft').order('student_id', desc=False).order('attempt_number', desc=False).execute()

        # Group by student
        groups = {}
        for s in submissions.data:
            sid = s.get('student_id') or s.get('student_name')
            if sid not in groups:
                groups[sid] = {
                    'student_id': s.get('student_id'),
                    'student_name': s.get('student_name'),
                    'student_id_number': s.get('student_id_number'),
                    'period': s.get('period'),
                    'attempts': [],
                }
            groups[sid]['attempts'].append({
                'submission_id': s.get('id'),
                'attempt_number': s.get('attempt_number', 1),
                'score': s.get('score'),
                'total_points': s.get('total_points'),
                'percentage': s.get('percentage'),
                'letter_grade': s.get('letter_grade'),
                'status': s.get('status'),
                'time_taken_seconds': s.get('time_taken_seconds'),
                'question_times': s.get('question_times'),
                'submitted_at': s.get('submitted_at'),
                'results': s.get('results'),
            })

        return jsonify({
            "content_id": content_id,
            "title": content.data[0].get('title'),
            "content": content.data[0].get('content'),
            "students": list(groups.values()),
        })
    except Exception as e:
        _logger.exception("List content submissions error")
        return jsonify({"error": "An internal error occurred"}), 500
```

- [ ] **Step 2: Run tests**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/ -x -q --ignore=tests/load --ignore=tests/stress 2>&1 | tail -5`
Expected: All pass

- [ ] **Step 3: Commit**

```bash
git add backend/routes/student_portal_routes.py
git commit -m "feat: class-based submissions endpoint with all attempts grouped by student"
```

---

### Task 6: Frontend API helpers — question_times support + content submissions

**Files:**
- Modify: `frontend/src/services/api.js`

- [ ] **Step 1: Update saveDraft to accept question_times**

Find `saveDraft` in `frontend/src/services/api.js`. Its current signature is `saveDraft(contentId, answers, markedForReview, studentToken)`. Replace it with:

```javascript
export async function saveDraft(contentId, answers, markedForReview, questionTimes, studentToken) {
  return fetch('/api/student/submission/' + contentId + '/draft', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Student-Token': studentToken,
    },
    body: JSON.stringify({
      answers: answers,
      marked_for_review: markedForReview,
      question_times: questionTimes || {},
    }),
  }).then(function(r) { return r.json(); })
}
```

- [ ] **Step 2: Add content submissions helper**

At the end of the file, add:

```javascript
export async function getContentSubmissions(contentId) {
  return fetchApi('/api/teacher/content/' + contentId + '/submissions')
}
```

- [ ] **Step 3: Build and verify**

Run: `cd /Users/alexc/Downloads/Graider/frontend && npm run build 2>&1 | tail -3`
Expected: Build succeeds (even though callers don't pass questionTimes yet — function still works because it's a new parameter in the middle; callers will be updated in Task 7)

Note: Adding a parameter in the middle breaks existing callers. Actually, the cleaner approach is to append it at the end. Re-read the function and move `questionTimes` to the LAST position before `studentToken`:

Actually the shown signature has `questionTimes` before `studentToken`. This is intentional to match the call site update pattern. If the existing call site passes `(contentId, answers, markedForReview, studentToken)`, the new signature will break it until Task 7 updates the call site. That's fine within a single commit workflow — make sure Task 7 runs before testing in the browser.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/services/api.js
git commit -m "feat: add question_times to saveDraft and getContentSubmissions helper"
```

---

### Task 7: StudentPortal — capture per-question time + send with submit and draft saves

**Files:**
- Modify: `frontend/src/components/StudentPortal.jsx`

- [ ] **Step 1: Add state variables**

Find the existing state declarations. After `const [answers, setAnswers] = useState({});` (line 37), add:

```javascript
  var [questionTimes, setQuestionTimes] = useState({});
  var [activeQuestionKey, setActiveQuestionKey] = useState(null);
  var [activeQuestionStartedAt, setActiveQuestionStartedAt] = useState(null);
```

- [ ] **Step 2: Wrap setAnswer to track time**

Find `const setAnswer = (key, value) => { setAnswers((prev) => ({ ...prev, [key]: value })); };` (around line 264).

Replace with:

```javascript
  const setAnswer = (key, value) => {
    var now = Date.now();
    if (activeQuestionKey && activeQuestionKey !== key && activeQuestionStartedAt) {
      var elapsed = Math.round((now - activeQuestionStartedAt) / 1000);
      setQuestionTimes(function(prev) {
        var next = Object.assign({}, prev);
        next[activeQuestionKey] = (next[activeQuestionKey] || 0) + elapsed;
        return next;
      });
    }
    if (activeQuestionKey !== key) {
      setActiveQuestionKey(key);
      setActiveQuestionStartedAt(now);
    } else if (!activeQuestionStartedAt) {
      setActiveQuestionStartedAt(now);
    }
    setAnswers((prev) => ({ ...prev, [key]: value }));
  };
```

- [ ] **Step 3: Include question_times in submit POST**

Find the existing submit fetch body (line ~210) that looks like:

```javascript
        body: JSON.stringify({ answers: answers, time_taken_seconds: timeTaken }),
```

Before this fetch, finalize the current question's time:

```javascript
      // Finalize current question time before submit
      var finalTimes = Object.assign({}, questionTimes);
      if (activeQuestionKey && activeQuestionStartedAt) {
        var finalElapsed = Math.round((Date.now() - activeQuestionStartedAt) / 1000);
        finalTimes[activeQuestionKey] = (finalTimes[activeQuestionKey] || 0) + finalElapsed;
      }
```

Then change the fetch body to:

```javascript
        body: JSON.stringify({ answers: answers, time_taken_seconds: timeTaken, question_times: finalTimes }),
```

- [ ] **Step 4: Update saveDraft calls to pass questionTimes**

Find BOTH `api.saveDraft(contentId, answers, markedForReview, studentToken)` calls (lines ~110 in the auto-save useEffect and ~272 in `saveDraftNow`).

Update each call to:

```javascript
api.saveDraft(contentId, answers, markedForReview, questionTimes, studentToken)
```

- [ ] **Step 5: Hydrate questionTimes from draft on resume**

Find the draft-fetch useEffect that calls `api.getDraft`. Inside the `.then` block, after populating `answers` and `markedForReview`, add:

```javascript
        if (data.draft.question_times) {
          setQuestionTimes(data.draft.question_times);
        }
```

Note: the backend needs to return `question_times` in the draft response. It already stores the column (Task 4), but if `get_submission_draft` in `student_account_routes.py` doesn't currently include `question_times` in its response, add it there now:

In `backend/routes/student_account_routes.py`, find `get_submission_draft`. In the returned `"draft"` dict, add:

```python
                "question_times": row.get('question_times') or {},
```

If this requires touching the backend file, commit it with the frontend changes (Task 7 commit message will cover both).

- [ ] **Step 6: Build and verify**

Run: `cd /Users/alexc/Downloads/Graider/frontend && npm run build 2>&1 | tail -3`
Expected: Build succeeds

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/StudentPortal.jsx backend/routes/student_account_routes.py
git commit -m "feat: capture and send per-question time tracking in StudentPortal"
```

---

### Task 8: App.jsx — standard badges + standards summary card + attempt history drawer

**Files:**
- Modify: `frontend/src/App.jsx`

- [ ] **Step 1: Add state for attempt drawer**

Near the `selectedAssessmentResults` state (line 2125), add:

```javascript
  const [attemptDrawerStudent, setAttemptDrawerStudent] = useState(null);
  const [contentSubmissionsGroups, setContentSubmissionsGroups] = useState([]);
```

- [ ] **Step 2: Add fetch function for class-based submissions**

Near `fetchAssessmentResults` (line 4874), add a new function:

```javascript
  const fetchContentSubmissions = async (contentId) => {
    try {
      var data = await api.getContentSubmissions(contentId);
      if (data && data.students) {
        setContentSubmissionsGroups(data.students);
      } else {
        setContentSubmissionsGroups([]);
      }
    } catch (e) {
      console.error("Error loading content submissions:", e);
      setContentSubmissionsGroups([]);
    }
  };
```

- [ ] **Step 3: Call fetchContentSubmissions alongside fetchAssessmentResults**

Inside `fetchAssessmentResults`, after `setSelectedAssessmentResults({...})`, check if the identifier is a UUID (class-based content vs join code). Add:

```javascript
      if (joinCode && joinCode.length > 10) {
        fetchContentSubmissions(joinCode);
      } else {
        setContentSubmissionsGroups([]);
      }
```

- [ ] **Step 4: Add Standards Summary Card above submissions list**

Find the assessment results panel where `selectedAssessmentResults.submissions` is first rendered. Above the submissions list, add a conditional render:

```jsx
              {selectedAssessmentResults && selectedAssessmentResults.submissions && selectedAssessmentResults.submissions.length > 0 && (() => {
                // Build class averages per standard from standards_mastery in each submission
                var byStandard = {};
                selectedAssessmentResults.submissions.forEach(function(sub) {
                  var mastery = sub.results && sub.results.standards_mastery;
                  if (!mastery) return;
                  Object.keys(mastery).forEach(function(code) {
                    var m = mastery[code];
                    if (!byStandard[code]) byStandard[code] = { earned: 0, possible: 0, question_count: m.question_count };
                    byStandard[code].earned += m.points_earned || 0;
                    byStandard[code].possible += m.points_possible || 0;
                  });
                });
                var codes = Object.keys(byStandard);
                if (codes.length === 0) return null;
                return (
                  <div className="glass-card" style={{ padding: "16px", marginBottom: "16px" }}>
                    <h4 style={{ fontSize: "0.95rem", fontWeight: 700, marginBottom: "10px", display: "flex", alignItems: "center", gap: "8px" }}>
                      <Icon name="Target" size={16} />
                      Standards in this Assessment ({codes.length})
                    </h4>
                    <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                      {codes.map(function(code) {
                        var s = byStandard[code];
                        var pct = s.possible > 0 ? Math.round((s.earned / s.possible) * 100) : 0;
                        var barColor = pct >= 80 ? "var(--success)" : pct >= 60 ? "var(--warning)" : "var(--danger)";
                        return (
                          <div key={code} style={{ display: "flex", alignItems: "center", gap: "12px", padding: "8px 12px", borderRadius: "8px", background: "var(--glass-bg)" }}>
                            <div style={{ fontSize: "0.8rem", fontWeight: 600, fontFamily: "monospace", minWidth: "100px" }}>{code}</div>
                            <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", minWidth: "70px" }}>{s.question_count} Q{s.question_count === 1 ? '' : 's'}</div>
                            <div style={{ flex: 1, height: "6px", background: "var(--glass-bg)", borderRadius: "3px", overflow: "hidden", border: "1px solid var(--glass-border)" }}>
                              <div style={{ width: pct + "%", height: "100%", background: barColor, transition: "width 0.3s" }} />
                            </div>
                            <div style={{ fontSize: "0.8rem", fontWeight: 600, minWidth: "50px", textAlign: "right" }}>{pct}%</div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                );
              })()}
```

- [ ] **Step 5: Add "Attempt X of Y" label and drawer trigger on submission rows**

Find the submissions list map (around line 14138: `selectedAssessmentResults.submissions.map((submission, idx) => (`).

Inside the rendered row for each submission, near the student name/score display, add:

```jsx
                              {(() => {
                                var group = contentSubmissionsGroups.find(function(g) { return g.student_id === submission.student_id || g.student_name === submission.student_name; });
                                if (!group || group.attempts.length <= 1) return null;
                                var curAttempt = (submission.results && submission.results.attempt_number) || submission.attempt_number || 1;
                                return (
                                  <button
                                    onClick={function(e) { e.stopPropagation(); setAttemptDrawerStudent(group); }}
                                    style={{ fontSize: "0.7rem", padding: "3px 8px", borderRadius: "10px", background: "var(--glass-bg)", border: "1px solid var(--glass-border)", color: "var(--text-secondary)", cursor: "pointer", marginLeft: "8px" }}
                                    title="View all attempts"
                                  >
                                    Attempt {curAttempt} of {group.attempts.length}
                                  </button>
                                );
                              })()}
```

- [ ] **Step 6: Add attempt history drawer**

At the end of the App component's JSX (near other modals), add:

```jsx
      {/* Attempt History Drawer */}
      {attemptDrawerStudent && (
        <div
          style={{
            position: "fixed", top: 0, left: 0, right: 0, bottom: 0,
            background: "var(--modal-bg)", display: "flex", alignItems: "center",
            justifyContent: "flex-end", zIndex: 9998, padding: "20px",
          }}
          onClick={function() { setAttemptDrawerStudent(null); }}
        >
          <div
            className="glass-card"
            style={{ width: "100%", maxWidth: "500px", maxHeight: "90vh", overflowY: "auto", padding: "24px", borderRadius: "16px" }}
            onClick={function(e) { e.stopPropagation(); }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
              <h3 style={{ fontSize: "1.1rem", fontWeight: 700 }}>
                {attemptDrawerStudent.student_name}
              </h3>
              <button
                onClick={function() { setAttemptDrawerStudent(null); }}
                style={{ background: "none", border: "none", cursor: "pointer", color: "var(--text-secondary)", fontSize: "1.2rem" }}
              >
                {String.fromCharCode(10005)}
              </button>
            </div>
            <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginBottom: "16px" }}>
              {attemptDrawerStudent.attempts.length} attempts
            </p>
            <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
              {attemptDrawerStudent.attempts.map(function(a) {
                var submittedDate = a.submitted_at ? new Date(a.submitted_at).toLocaleString() : '—';
                var timeMin = a.time_taken_seconds ? Math.floor(a.time_taken_seconds / 60) + 'm ' + (a.time_taken_seconds % 60) + 's' : '—';
                var pct = a.percentage != null ? Math.round(a.percentage) + '%' : '—';
                return (
                  <div key={a.submission_id} style={{ padding: "12px 14px", borderRadius: "10px", background: "var(--glass-bg)", border: "1px solid var(--glass-border)" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
                      <div style={{ fontWeight: 600, fontSize: "0.9rem" }}>Attempt {a.attempt_number}</div>
                      <div style={{ fontSize: "0.9rem", fontWeight: 600 }}>{pct}</div>
                    </div>
                    <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                      Submitted {submittedDate} {String.fromCharCode(8226)} {timeMin}
                    </div>
                    {a.score != null && (
                      <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: "2px" }}>
                        Score: {a.score} / {a.total_points}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}
```

- [ ] **Step 7: Add per-question standard badges in graded submission detail view**

Find where individual graded questions are rendered inside a submission's detail view. Look for the rendering of `results.questions[i]` or similar (likely inside the existing submission detail expansion).

Where each question is rendered, if `q.standard` is present, show a small badge:

```jsx
                {q.standard && (
                  <span style={{ fontSize: "0.65rem", padding: "2px 6px", borderRadius: "4px", background: "var(--glass-bg)", color: "var(--text-secondary)", fontFamily: "monospace", marginLeft: "8px" }}>
                    {q.standard}
                  </span>
                )}
```

Place this next to the question number or points display.

- [ ] **Step 8: Build and verify**

Run: `cd /Users/alexc/Downloads/Graider/frontend && npm run build 2>&1 | tail -3`
Expected: Build succeeds

- [ ] **Step 9: Manual test**

1. Generate a new assessment in the Planner (so questions have `standard` field)
2. Publish it to a class via "Share with Class"
3. Log in as student, take the assessment, submit
4. In the teacher view, open the assessment's results panel
5. Verify the Standards summary card appears at the top with class averages
6. Expand a submission detail — each question should show its standard code badge
7. Re-submit as the same student (or use another test student), verify "Attempt X of Y" label appears and clicking it opens the drawer

- [ ] **Step 10: Commit**

```bash
git add frontend/src/App.jsx
git commit -m "feat: standards summary card, per-question badges, attempt history drawer"
```

---

## Summary

| Task | What | Risk |
|------|------|------|
| 1 | Schema: `question_times` column | Low — additive column |
| 2 | grading_service.py: standard per question + rollup | Medium — touches core grading, but additive |
| 3 | portal_grading.py: same for multipass | Medium — additive fields in results JSONB |
| 4 | student_account_routes.py: accept question_times | Low — new field in request body |
| 5 | student_portal_routes.py: class-based submissions endpoint | Low — new endpoint |
| 6 | api.js: helpers updated | Low — mechanical |
| 7 | StudentPortal.jsx: per-question time capture | Medium — touches answer flow |
| 8 | App.jsx: badges, summary, drawer | Medium — multi-component UI |

**Total: 1 schema migration, 7 modified files, 7 commits.**

**Before:** No standards tracking on submissions, no per-question timing, no attempt history UI.
**After:** Every graded question has its standard, class mastery per standard visible in results panel, teachers can see all past attempts per student, students' per-question time is captured for Phase 2 reports.
