# Student Save-and-Resume Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let students save in-progress assessments and resume later with server-side auto-save, timer enforcement, mark-for-review flags, and teacher end-attempt control.

**Architecture:** Add 3 columns to `student_submissions` (`draft_answers`, `marked_for_review`, `time_started_at`). New backend endpoints for draft save/get/submit/force-end. StudentPortal.jsx fetches draft on mount, auto-saves every 15 seconds, timer syncs from server. Teacher's results panel gets an "In Progress" section with End attempt buttons.

**Tech Stack:** Python/Flask, React (JSX), Supabase (Postgres JSONB + timestamptz)

**Spec:** `docs/superpowers/specs/2026-04-10-student-save-and-resume-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| Supabase SQL (manual) | **Run once** | Add columns to `student_submissions` |
| `backend/routes/student_account_routes.py` | **Modify** | Add 3 student draft endpoints (save, get, submit-draft); include `draft` status filter in dashboard |
| `backend/routes/student_portal_routes.py` | **Modify** | Add teacher end-attempt endpoint; include in-progress drafts in assessment results |
| `frontend/src/services/api.js` | **Modify** | Add `saveDraft`, `getDraft`, `submitDraft`, `endAttempt` helpers |
| `frontend/src/components/StudentPortal.jsx` | **Modify** | Fetch draft on mount, auto-save loop, manual save button, mark-for-review flags, review screen, server-synced timer |
| `frontend/src/App.jsx` | **Modify** | "In Progress" section with End attempt button in assessment results |

---

### Task 1: Supabase schema — add draft columns

**Files:**
- Manual SQL (run in Supabase dashboard)

- [ ] **Step 1: Run schema migration**

In the Supabase SQL Editor, run:

```sql
ALTER TABLE student_submissions 
  ADD COLUMN IF NOT EXISTS draft_answers JSONB,
  ADD COLUMN IF NOT EXISTS marked_for_review JSONB DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS time_started_at TIMESTAMPTZ;

-- Update status check constraint to include 'draft'
ALTER TABLE student_submissions DROP CONSTRAINT IF EXISTS student_submissions_status_check;
ALTER TABLE student_submissions ADD CONSTRAINT student_submissions_status_check
  CHECK (status IN ('draft', 'in_progress', 'submitted', 'grading', 'graded', 'returned', 'partial'));
```

- [ ] **Step 2: Verify columns exist**

In Supabase dashboard → Table Editor → `student_submissions`. Confirm `draft_answers`, `marked_for_review`, `time_started_at` appear.

- [ ] **Step 3: No commit** — schema change only, no code files modified.

---

### Task 2: Backend — student draft endpoints

**Files:**
- Modify: `backend/routes/student_account_routes.py`

- [ ] **Step 1: Add save-draft endpoint**

At the end of `backend/routes/student_account_routes.py`, after the last student-facing function, add:

```python
@student_account_bp.route('/api/student/submission/<content_id>/draft', methods=['POST'])
@handle_route_errors
def save_submission_draft(content_id):
    """Save or update a draft submission for the authenticated student."""
    session_info = _validate_student_session()
    if not session_info:
        return jsonify({"error": "Invalid session"}), 401
    student_id, class_id = session_info

    try:
        db = _get_supabase()
        data = request.json or {}
        draft_answers = data.get('answers') or {}
        marked_for_review = data.get('marked_for_review') or []

        # Verify content belongs to this class
        content = db.table('published_content').select('id, settings').eq(
            'id', content_id
        ).eq('class_id', class_id).execute()
        if not content.data:
            return jsonify({"error": "Content not found"}), 404

        settings = content.data[0].get('settings') or {}
        time_limit_minutes = settings.get('time_limit_minutes')
        time_limit_seconds = int(time_limit_minutes) * 60 if time_limit_minutes else None

        # Check for existing submission
        existing = db.table('student_submissions').select('*').eq(
            'student_id', student_id
        ).eq('content_id', content_id).execute()

        if existing.data:
            row = existing.data[0]
            if row.get('status') in ('submitted', 'graded', 'grading', 'partial'):
                return jsonify({"error": "Already submitted"}), 409
            # Update existing draft
            db.table('student_submissions').update({
                'draft_answers': draft_answers,
                'marked_for_review': marked_for_review,
                'status': 'draft',
            }).eq('id', row['id']).execute()
            time_started_at = row.get('time_started_at')
        else:
            # Create new draft row
            now_iso = datetime.now(timezone.utc).isoformat()
            student_row = db.table('students').select(
                'first_name, last_name, student_id_number, period'
            ).eq('id', student_id).execute()
            sdata = student_row.data[0] if student_row.data else {}
            db.table('student_submissions').insert({
                'student_id': student_id,
                'content_id': content_id,
                'student_name': (sdata.get('first_name', '') + ' ' + sdata.get('last_name', '')).strip(),
                'student_id_number': sdata.get('student_id_number'),
                'period': sdata.get('period'),
                'status': 'draft',
                'draft_answers': draft_answers,
                'marked_for_review': marked_for_review,
                'time_started_at': now_iso,
            }).execute()
            time_started_at = now_iso

        # Calculate remaining time
        remaining_seconds = None
        if time_limit_seconds and time_started_at:
            started = datetime.fromisoformat(time_started_at.replace('Z', '+00:00'))
            elapsed = (datetime.now(timezone.utc) - started).total_seconds()
            remaining_seconds = max(0, int(time_limit_seconds - elapsed))

        return jsonify({
            "success": True,
            "time_started_at": time_started_at,
            "remaining_seconds": remaining_seconds,
            "time_limit_seconds": time_limit_seconds,
        })
    except Exception as e:
        _logger.exception("Save draft error")
        return jsonify({"error": "An internal error occurred"}), 500
```

Also make sure `datetime, timezone` is imported at the top of the file. If not, add: `from datetime import datetime, timezone`.

- [ ] **Step 2: Add get-draft endpoint**

Immediately after `save_submission_draft`, add:

```python
@student_account_bp.route('/api/student/submission/<content_id>/draft', methods=['GET'])
@handle_route_errors
def get_submission_draft(content_id):
    """Fetch an existing draft for resume."""
    session_info = _validate_student_session()
    if not session_info:
        return jsonify({"error": "Invalid session"}), 401
    student_id, class_id = session_info

    try:
        db = _get_supabase()

        # Verify content belongs to class
        content = db.table('published_content').select('id, settings').eq(
            'id', content_id
        ).eq('class_id', class_id).execute()
        if not content.data:
            return jsonify({"error": "Content not found"}), 404

        settings = content.data[0].get('settings') or {}
        time_limit_minutes = settings.get('time_limit_minutes')
        time_limit_seconds = int(time_limit_minutes) * 60 if time_limit_minutes else None

        # Find existing draft
        existing = db.table('student_submissions').select('*').eq(
            'student_id', student_id
        ).eq('content_id', content_id).eq('status', 'draft').execute()

        if not existing.data:
            return jsonify({"draft": None})

        row = existing.data[0]
        time_started_at = row.get('time_started_at')
        remaining_seconds = None
        if time_limit_seconds and time_started_at:
            started = datetime.fromisoformat(time_started_at.replace('Z', '+00:00'))
            elapsed = (datetime.now(timezone.utc) - started).total_seconds()
            remaining_seconds = max(0, int(time_limit_seconds - elapsed))

        return jsonify({
            "draft": {
                "answers": row.get('draft_answers') or {},
                "marked_for_review": row.get('marked_for_review') or [],
                "time_started_at": time_started_at,
                "remaining_seconds": remaining_seconds,
                "time_limit_seconds": time_limit_seconds,
            }
        })
    except Exception as e:
        _logger.exception("Get draft error")
        return jsonify({"error": "An internal error occurred"}), 500
```

- [ ] **Step 3: Run tests**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/ -x -q --ignore=tests/load --ignore=tests/stress 2>&1 | tail -5`
Expected: All pass

- [ ] **Step 4: Commit**

```bash
git add backend/routes/student_account_routes.py
git commit -m "feat: add student draft save/get endpoints"
```

---

### Task 3: Backend — teacher end-attempt + in-progress in results

**Files:**
- Modify: `backend/routes/student_portal_routes.py`

- [ ] **Step 1: Add end-attempt endpoint**

At the end of `backend/routes/student_portal_routes.py`, add:

```python
@student_portal_bp.route('/api/teacher/end-attempt/<submission_id>', methods=['POST'])
@require_teacher
@handle_route_errors
def end_student_attempt(submission_id):
    """Force-end a student's in-progress draft, converting it to a submitted row."""
    try:
        db = get_supabase()

        # Fetch the draft + verify teacher ownership via content_id -> class -> teacher
        sub = db.table('student_submissions').select('*').eq('id', submission_id).execute()
        if not sub.data:
            return jsonify({"error": "Submission not found"}), 404
        row = sub.data[0]

        if row.get('status') != 'draft':
            return jsonify({"error": "Not an in-progress draft"}), 400

        # Verify teacher owns the class this content belongs to
        content_id = row.get('content_id')
        content = db.table('published_content').select('teacher_id').eq('id', content_id).execute()
        if not content.data or content.data[0].get('teacher_id') != g.teacher_id:
            return jsonify({"error": "Not authorized"}), 403

        # Convert draft to submission
        db.table('student_submissions').update({
            'status': 'submitted',
            'answers': row.get('draft_answers') or {},
            'submitted_at': datetime.now(timezone.utc).isoformat(),
            'results': {'force_ended_by_teacher': True},
        }).eq('id', submission_id).execute()

        return jsonify({"success": True})
    except Exception as e:
        _logger.exception("End attempt error")
        return jsonify({"error": "An internal error occurred"}), 500
```

Ensure `datetime, timezone` is imported at the top of `student_portal_routes.py`. If not, add: `from datetime import datetime, timezone`.

- [ ] **Step 2: Add in-progress drafts to assessment results endpoint**

Find `get_assessment_results` in `student_portal_routes.py`. After the existing submissions query and before the return, add logic to fetch drafts for class-based content. Since this endpoint uses `join_code` for the join-code path, it only applies to `published_assessments`. For class-based drafts, we need a separate endpoint.

Add a new endpoint at the end of the file:

```python
@student_portal_bp.route('/api/teacher/content/<content_id>/in-progress', methods=['GET'])
@require_teacher
@handle_route_errors
def list_in_progress_drafts(content_id):
    """List students currently drafting a specific piece of class-based content."""
    try:
        db = get_supabase()

        # Verify teacher owns this content
        content = db.table('published_content').select('teacher_id, settings').eq('id', content_id).execute()
        if not content.data or content.data[0].get('teacher_id') != g.teacher_id:
            return jsonify({"error": "Not authorized"}), 403

        settings = content.data[0].get('settings') or {}
        time_limit_minutes = settings.get('time_limit_minutes')
        time_limit_seconds = int(time_limit_minutes) * 60 if time_limit_minutes else None

        drafts = db.table('student_submissions').select(
            'id, student_name, draft_answers, marked_for_review, time_started_at'
        ).eq('content_id', content_id).eq('status', 'draft').execute()

        now = datetime.now(timezone.utc)
        rows = []
        for d in drafts.data:
            answers = d.get('draft_answers') or {}
            answered_count = sum(1 for v in answers.values() if v not in (None, '', []))
            elapsed_seconds = 0
            remaining_seconds = None
            if d.get('time_started_at'):
                started = datetime.fromisoformat(d['time_started_at'].replace('Z', '+00:00'))
                elapsed_seconds = int((now - started).total_seconds())
                if time_limit_seconds:
                    remaining_seconds = max(0, time_limit_seconds - elapsed_seconds)
            rows.append({
                "submission_id": d['id'],
                "student_name": d.get('student_name'),
                "answered_count": answered_count,
                "elapsed_seconds": elapsed_seconds,
                "remaining_seconds": remaining_seconds,
            })

        return jsonify({"drafts": rows})
    except Exception as e:
        _logger.exception("List in-progress error")
        return jsonify({"error": "An internal error occurred"}), 500
```

- [ ] **Step 3: Run tests**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/ -x -q --ignore=tests/load --ignore=tests/stress 2>&1 | tail -5`
Expected: All pass

- [ ] **Step 4: Commit**

```bash
git add backend/routes/student_portal_routes.py
git commit -m "feat: teacher end-attempt endpoint and in-progress drafts listing"
```

---

### Task 4: Frontend API helpers

**Files:**
- Modify: `frontend/src/services/api.js`

- [ ] **Step 1: Add draft API helpers**

At the end of `frontend/src/services/api.js`, add:

```javascript
export async function saveDraft(contentId, answers, markedForReview, studentToken) {
  return fetch('/api/student/submission/' + contentId + '/draft', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Student-Token': studentToken,
    },
    body: JSON.stringify({
      answers: answers,
      marked_for_review: markedForReview,
    }),
  }).then(function(r) { return r.json(); })
}

export async function getDraft(contentId, studentToken) {
  return fetch('/api/student/submission/' + contentId + '/draft', {
    headers: { 'X-Student-Token': studentToken },
  }).then(function(r) { return r.json(); })
}

export async function endStudentAttempt(submissionId) {
  return fetchApi('/api/teacher/end-attempt/' + submissionId, {
    method: 'POST',
  })
}

export async function getInProgressDrafts(contentId) {
  return fetchApi('/api/teacher/content/' + contentId + '/in-progress')
}
```

- [ ] **Step 2: Build and verify**

Run: `cd /Users/alexc/Downloads/Graider/frontend && npm run build 2>&1 | tail -3`
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
git add frontend/src/services/api.js
git commit -m "feat: add draft and end-attempt API helpers"
```

---

### Task 5: StudentPortal — draft resume + auto-save + manual save + mark for review

**Files:**
- Modify: `frontend/src/components/StudentPortal.jsx`

- [ ] **Step 1: Add new state variables**

In `StudentPortal.jsx`, find the existing state declarations (around line 37-44). After `const [lightMode, setLightMode] = ...`, add:

```javascript
  var [markedForReview, setMarkedForReview] = useState([]);
  var [lastSavedAt, setLastSavedAt] = useState(null);
  var [draftLoaded, setDraftLoaded] = useState(false);
  var [resumedFromDraft, setResumedFromDraft] = useState(false);
  var [savingDraft, setSavingDraft] = useState(false);
  var [serverRemainingSeconds, setServerRemainingSeconds] = useState(null);
```

- [ ] **Step 2: Fetch draft on mount**

After the existing useEffects (around line 60-80), add:

```javascript
  useEffect(function() {
    if (!contentId || !studentToken || draftLoaded) return;
    api.getDraft(contentId, studentToken).then(function(data) {
      if (data && data.draft) {
        setAnswers(data.draft.answers || {});
        setMarkedForReview(data.draft.marked_for_review || []);
        if (data.draft.remaining_seconds != null) {
          setServerRemainingSeconds(data.draft.remaining_seconds);
        }
        setResumedFromDraft(true);
      }
      setDraftLoaded(true);
    }).catch(function() { setDraftLoaded(true); });
  }, [contentId, studentToken]);
```

- [ ] **Step 3: Auto-save on answers change**

Add another useEffect after the draft-fetch one:

```javascript
  useEffect(function() {
    if (!contentId || !studentToken || !draftLoaded) return;
    if (Object.keys(answers).length === 0 && markedForReview.length === 0) return;
    var timer = setTimeout(function() {
      setSavingDraft(true);
      api.saveDraft(contentId, answers, markedForReview, studentToken).then(function(data) {
        if (data && data.success) {
          setLastSavedAt(Date.now());
          if (data.remaining_seconds != null) setServerRemainingSeconds(data.remaining_seconds);
        }
      }).catch(function() { /* silent — will retry on next change */ })
        .finally(function() { setSavingDraft(false); });
    }, 15000);
    return function() { clearTimeout(timer); };
  }, [answers, markedForReview, contentId, studentToken, draftLoaded]);
```

- [ ] **Step 4: Add manual save function**

In `StudentPortal.jsx`, near the other functions (e.g., after `setAnswer`), add:

```javascript
  var saveDraftNow = async function() {
    if (!contentId || !studentToken) return;
    setSavingDraft(true);
    try {
      var data = await api.saveDraft(contentId, answers, markedForReview, studentToken);
      if (data && data.success) {
        setLastSavedAt(Date.now());
        if (data.remaining_seconds != null) setServerRemainingSeconds(data.remaining_seconds);
        alert('Draft saved. You can close this tab and come back later.');
      }
    } catch (e) {
      alert('Failed to save draft: ' + e.message);
    } finally {
      setSavingDraft(false);
    }
  };

  var toggleMarkForReview = function(key) {
    setMarkedForReview(function(prev) {
      if (prev.indexOf(key) !== -1) return prev.filter(function(k) { return k !== key; });
      return prev.concat([key]);
    });
  };
```

- [ ] **Step 5: Add resume banner in render**

Inside the assessment-taking JSX (not the join/name/results screens), add a banner at the top when `resumedFromDraft` is true. Find the assessment screen's main container and add:

```jsx
        {resumedFromDraft && (
          <div style={{
            padding: "10px 16px", marginBottom: "16px",
            background: "var(--success-bg)", border: "1px solid var(--success-border)",
            borderRadius: "8px", fontSize: "0.85rem", color: "var(--text-primary)",
          }}>
            Resumed from draft — {Object.keys(answers).length} questions answered.
          </div>
        )}
```

- [ ] **Step 6: Add "Save for later" button next to Submit**

Find the Submit button in the assessment screen. Add a "Save for later" button before it:

```jsx
            <button
              type="button"
              onClick={saveDraftNow}
              disabled={savingDraft || !contentId}
              style={{ padding: "12px 24px", borderRadius: "10px", background: "var(--btn-secondary-bg)", border: "1px solid var(--glass-border)", color: "var(--text-primary)", fontSize: "1rem", cursor: "pointer", marginRight: "10px" }}
            >
              {savingDraft ? 'Saving...' : 'Save for later'}
            </button>
```

Note: only show this button for class-based attempts (`contentId` is truthy).

- [ ] **Step 7: Build and verify**

Run: `cd /Users/alexc/Downloads/Graider/frontend && npm run build 2>&1 | tail -3`
Expected: Build succeeds

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/StudentPortal.jsx
git commit -m "feat: student draft resume, auto-save, manual save in StudentPortal"
```

---

### Task 6: Teacher — In Progress section in assessment results

**Files:**
- Modify: `frontend/src/App.jsx`

- [ ] **Step 1: Add state for in-progress drafts**

In `App.jsx`, near the existing `selectedAssessmentResults` state (around line 2125), add:

```javascript
  const [inProgressDrafts, setInProgressDrafts] = useState([]);
```

- [ ] **Step 2: Fetch in-progress drafts when viewing results**

Find the `fetchAssessmentResults` function (around line 4873). At the end of the function (after setting `selectedAssessmentResults`), add:

```javascript
    // Also fetch in-progress drafts if this is class-based content
    if (joinCode && joinCode.indexOf('-') !== -1) {
      // This is a content_id (UUID format), not a join code
      try {
        var inProg = await api.getInProgressDrafts(joinCode);
        if (inProg.drafts) setInProgressDrafts(inProg.drafts);
      } catch (e) { /* ignore */ }
    } else {
      setInProgressDrafts([]);
    }
```

Note: if your result flow uses `content_id` specifically, call it directly. If it uses `join_code`, adapt accordingly. The key is to call `api.getInProgressDrafts(contentId)` when a class-based assessment's results are viewed.

- [ ] **Step 3: Render in-progress section in results panel**

Find the assessment results panel JSX (around line 14019). Before the submissions list, add:

```jsx
              {inProgressDrafts.length > 0 && (
                <div className="glass-card" style={{ padding: "16px", marginBottom: "16px" }}>
                  <h4 style={{ fontSize: "0.95rem", fontWeight: 700, marginBottom: "10px", display: "flex", alignItems: "center", gap: "8px" }}>
                    <Icon name="Clock" size={16} />
                    In Progress ({inProgressDrafts.length})
                  </h4>
                  <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                    {inProgressDrafts.map(function(d) {
                      var elapsedMin = Math.floor((d.elapsed_seconds || 0) / 60);
                      return (
                        <div key={d.submission_id} style={{
                          display: "flex", alignItems: "center", justifyContent: "space-between",
                          padding: "10px 14px", borderRadius: "8px",
                          background: "var(--warning-bg)", border: "1px solid var(--warning-border)",
                        }}>
                          <div>
                            <div style={{ fontSize: "0.9rem", fontWeight: 600 }}>{d.student_name}</div>
                            <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                              {d.answered_count} questions answered {String.fromCharCode(8226)} {elapsedMin} min elapsed
                            </div>
                          </div>
                          <button
                            onClick={async function() {
                              if (!confirm('End ' + d.student_name + '\'s attempt? Their current answers will be submitted.')) return;
                              try {
                                var res = await api.endStudentAttempt(d.submission_id);
                                if (res.success) {
                                  addToast('Ended attempt for ' + d.student_name, 'success');
                                  setInProgressDrafts(function(prev) { return prev.filter(function(x) { return x.submission_id !== d.submission_id; }); });
                                } else {
                                  addToast(res.error || 'Failed to end attempt', 'error');
                                }
                              } catch (e) {
                                addToast('Failed: ' + e.message, 'error');
                              }
                            }}
                            className="btn btn-secondary"
                            style={{ padding: "6px 12px", fontSize: "0.75rem" }}
                          >
                            End attempt
                          </button>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
```

- [ ] **Step 4: Build and verify**

Run: `cd /Users/alexc/Downloads/Graider/frontend && npm run build 2>&1 | tail -3`
Expected: Build succeeds

- [ ] **Step 5: Manual test**

1. Log in as `test@graider.live` / `NEE4K3` at `localhost:3000/student`
2. Start an assignment, answer a few questions, close the tab
3. Reopen the student portal, click the same assignment → should show "Resumed from draft — X questions answered" banner and pre-populated answers
4. Click "Save for later" — should show success alert
5. In the teacher view, open the assessment results panel — should see "In Progress" section with the student's name and answered count
6. Click "End attempt" — student becomes a submitted row

- [ ] **Step 6: Commit**

```bash
git add frontend/src/App.jsx
git commit -m "feat: in-progress drafts section with end-attempt in assessment results"
```

---

## Summary

| Task | What | Risk |
|------|------|------|
| 1 | Supabase schema: add 3 columns + update status constraint | Low — additive columns, no data changes |
| 2 | Backend: student save-draft + get-draft endpoints | Medium — new business logic, time calculation |
| 3 | Backend: teacher end-attempt + in-progress list endpoints | Low — similar patterns to existing endpoints |
| 4 | Frontend API helpers | Low — mechanical |
| 5 | StudentPortal: draft resume, auto-save, manual save, review flags | Medium-High — touches core state flow |
| 6 | Teacher: in-progress section with end attempt | Low — additive UI |

**Total: 1 schema migration, 5 modified files, 5 commits.**

**Before:** Students lose all answers when they close the tab. No way to save-and-resume.
**After:** Auto-save every 15 seconds, manual save button, server-side timer, teacher visibility into in-progress attempts, teacher can force-end stuck attempts.
