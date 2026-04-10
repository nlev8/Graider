# Phase 2 — Progress Rank Grid Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a per-class Progress Rank grid (students × standards, color-coded by mastery) inside the Analytics tab, activated by a new class selector.

**Architecture:** New backend endpoint aggregates `student_submissions.results.standards_mastery` rollups (shipped in Phase 1) on-demand per class. New frontend component renders the grid with attempt-mode toggle, struggling filter, and cell popovers. Analytics tab gets a class selector that toggles between existing content ("All Classes") and the new grid.

**Tech Stack:** Python/Flask (backend), React/JSX (frontend), Supabase (Postgres JSONB queries)

**Spec:** `docs/superpowers/specs/2026-04-10-phase2-progress-rank-grid-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `backend/routes/student_portal_routes.py` | **Modify** | Add `/api/teacher/class/<id>/progress-rank` endpoint + aggregation helper |
| `frontend/src/services/api.js` | **Modify** | Add `getClassProgressRank` helper |
| `frontend/src/tabs/ProgressRankGrid.jsx` | **Create** | New component rendering the grid, toggles, popover |
| `frontend/src/tabs/AnalyticsTab.jsx` | **Modify** | Add class selector at top, conditional render of ProgressRankGrid |

---

### Task 1: Backend aggregation helper

**Files:**
- Modify: `backend/routes/student_portal_routes.py`

- [ ] **Step 1: Add module-level mastery aggregation helper**

At the top of `backend/routes/student_portal_routes.py`, after the existing imports and helper functions, add:

```python
def _parse_ts(ts):
    """Parse an ISO timestamp string to a datetime for safe comparison.
    Returns datetime.min if parsing fails so unparseable timestamps sort last.
    """
    from datetime import datetime
    if not ts:
        return datetime.min
    try:
        return datetime.fromisoformat(ts.replace('Z', '+00:00'))
    except (ValueError, AttributeError):
        return datetime.min


def _select_submissions_by_mode(submissions_by_content, attempt_mode):
    """Given a dict of content_id -> list of submissions, return one selected
    submission per content based on attempt_mode.

    attempt_mode: 'latest' | 'best' | 'average'
    For 'average', returns all submissions; caller handles averaging.

    Tie-breaking:
    - 'latest': prefers higher attempt_number, then newer submitted_at (parsed)
    - 'best': prefers higher percentage, then newer submitted_at (parsed) on ties
    - 'average': no selection; all submissions used
    """
    selected = {}
    for content_id, subs in submissions_by_content.items():
        if not subs:
            continue
        if attempt_mode == 'best':
            # Tie-break: higher percentage, then newer submission
            best = max(subs, key=lambda s: (
                s.get('percentage') or 0,
                _parse_ts(s.get('submitted_at')),
                s.get('attempt_number') or 0,
            ))
            selected[content_id] = [best]
        elif attempt_mode == 'average':
            selected[content_id] = subs
        else:  # 'latest' (default)
            latest = max(subs, key=lambda s: (
                s.get('attempt_number') or 0,
                _parse_ts(s.get('submitted_at')),
            ))
            selected[content_id] = [latest]
    return selected


def _aggregate_mastery_for_student(selected_submissions_by_content, content_titles, attempt_mode):
    """Aggregate standards_mastery across submissions into a per-standard dict.

    Input: { content_id: [submission, ...] } (one per content unless attempt_mode=='average')
    Output: { standard_code: { percentage, points_earned, points_possible, question_count, contributing_submissions } }
    """
    from collections import defaultdict
    totals = defaultdict(lambda: {
        'points_earned': 0.0,
        'points_possible': 0.0,
        'question_count': 0,
        'contributing_submissions': [],
    })

    for content_id, subs in selected_submissions_by_content.items():
        if not subs:
            continue
        if attempt_mode == 'average' and len(subs) > 1:
            # Average each standard's percentage across attempts, then scale
            per_standard_avg = defaultdict(lambda: {'pct_sum': 0.0, 'count': 0, 'pts_poss': 0, 'q_count': 0, 'attempts': []})
            for sub in subs:
                results = sub.get('results') or {}
                mastery = results.get('standards_mastery') or {}
                for code, m in mastery.items():
                    if not m or not m.get('points_possible'):
                        continue
                    pct = (m.get('points_earned', 0) / m['points_possible']) * 100
                    per_standard_avg[code]['pct_sum'] += pct
                    per_standard_avg[code]['count'] += 1
                    per_standard_avg[code]['pts_poss'] = m.get('points_possible', 0)
                    per_standard_avg[code]['q_count'] = m.get('question_count', 0)
                    per_standard_avg[code]['attempts'].append({
                        'submission_id': sub.get('id'),
                        'attempt_number': sub.get('attempt_number', 1),
                        'points_earned': m.get('points_earned', 0),
                        'points_possible': m['points_possible'],
                    })
            for code, agg in per_standard_avg.items():
                avg_pct = agg['pct_sum'] / agg['count']
                totals[code]['points_earned'] += (avg_pct / 100.0) * agg['pts_poss']
                totals[code]['points_possible'] += agg['pts_poss']
                totals[code]['question_count'] += agg['q_count']
                # In average mode, record each contributing attempt individually
                for a in agg['attempts']:
                    totals[code]['contributing_submissions'].append({
                        'submission_id': a['submission_id'],
                        'title': content_titles.get(content_id, ''),
                        'points_earned': a['points_earned'],
                        'points_possible': a['points_possible'],
                        'attempt_number': a['attempt_number'],
                    })
        else:
            for sub in subs:
                results = sub.get('results') or {}
                mastery = results.get('standards_mastery') or {}
                for code, m in mastery.items():
                    if not m or not m.get('points_possible'):
                        continue
                    totals[code]['points_earned'] += m.get('points_earned', 0)
                    totals[code]['points_possible'] += m['points_possible']
                    totals[code]['question_count'] += m.get('question_count', 0)
                    totals[code]['contributing_submissions'].append({
                        'submission_id': sub.get('id'),
                        'title': content_titles.get(content_id, ''),
                        'points_earned': m.get('points_earned', 0),
                        'points_possible': m['points_possible'],
                        'attempt_number': sub.get('attempt_number', 1),
                    })

    # Compute final percentages and cap contributing_submissions at 10 (most recent first)
    result = {}
    for code, t in totals.items():
        pct = round((t['points_earned'] / t['points_possible']) * 100, 1) if t['points_possible'] > 0 else 0
        # Sort contributing submissions by attempt_number desc before capping
        contributing = sorted(
            t['contributing_submissions'],
            key=lambda c: c.get('attempt_number') or 0,
            reverse=True,
        )[:10]
        result[code] = {
            'percentage': pct,
            'points_earned': round(t['points_earned'], 2),
            'points_possible': t['points_possible'],
            'question_count': t['question_count'],
            'contributing_submissions': contributing,
        }
    return result
```

- [ ] **Step 2: Run tests to ensure imports still work**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/ -x -q --ignore=tests/load --ignore=tests/stress 2>&1 | tail -5`
Expected: All pass (we only added helper functions, didn't change existing behavior)

- [ ] **Step 3: Commit**

```bash
git add backend/routes/student_portal_routes.py
git commit -m "feat: add progress-rank aggregation helpers in student_portal_routes"
```

---

### Task 2: Backend endpoint

**Files:**
- Modify: `backend/routes/student_portal_routes.py`

- [ ] **Step 1: Add the endpoint**

At the END of `backend/routes/student_portal_routes.py`, after the existing teacher endpoints, add:

```python
@student_portal_bp.route('/api/teacher/class/<class_id>/progress-rank', methods=['GET'])
@require_teacher
@handle_route_errors
def get_class_progress_rank(class_id):
    """Return a class-scoped progress rank grid aggregating standards_mastery
    across all graded submissions for students in the class.

    Query params:
      attempt_mode: 'latest' (default) | 'best' | 'average'
    """
    try:
        db = get_supabase()

        attempt_mode = request.args.get('attempt_mode', 'latest')
        if attempt_mode not in ('latest', 'best', 'average'):
            attempt_mode = 'latest'

        # Verify class ownership
        cls = db.table('classes').select('id, name, teacher_id').eq('id', class_id).execute()
        if not cls.data or cls.data[0].get('teacher_id') != g.teacher_id:
            return jsonify({"error": "Not authorized"}), 403
        class_name = cls.data[0].get('name')

        # Fetch class roster — query students directly by joining via class_students
        # Two-step query avoids Supabase foreign-table alias ambiguity
        enrollments = db.table('class_students').select('student_id').eq('class_id', class_id).execute()
        student_ids = [row['student_id'] for row in (enrollments.data or []) if row.get('student_id')]

        student_records = []
        if student_ids:
            students_rows = db.table('students').select(
                'id, first_name, last_name'
            ).in_('id', student_ids).execute()
            for sdata in students_rows.data or []:
                student_records.append({
                    'student_id': sdata.get('id'),
                    'student_name': ((sdata.get('first_name') or '') + ' ' + (sdata.get('last_name') or '')).strip(),
                })
            # Sort alphabetically by name for stable grid order
            student_records.sort(key=lambda s: s['student_name'].lower())

        if not student_records:
            return jsonify({
                "class_id": class_id,
                "class_name": class_name,
                "attempt_mode": attempt_mode,
                "standards": [],
                "students": [],
            })

        # Fetch all published_content for this class (assessments/assignments only)
        content = db.table('published_content').select(
            'id, title, content_type'
        ).eq('class_id', class_id).in_('content_type', ['assessment', 'assignment']).execute()

        content_ids = [c['id'] for c in content.data or []]
        content_titles = {c['id']: c.get('title', '') for c in content.data or []}

        if not content_ids:
            return jsonify({
                "class_id": class_id,
                "class_name": class_name,
                "attempt_mode": attempt_mode,
                "standards": [],
                "students": [{'student_id': s['student_id'], 'student_name': s['student_name'], 'mastery': {}} for s in student_records],
            })

        # Fetch all non-draft submissions for those contents, ordered for deterministic selection
        # Select only columns we need to keep payload bounded
        subs = db.table('student_submissions').select(
            'id, student_id, content_id, attempt_number, submitted_at, percentage, results, status'
        ).in_('content_id', content_ids).neq('status', 'draft').order(
            'submitted_at', desc=True
        ).execute()

        # Group submissions by (student_id, content_id)
        from collections import defaultdict
        subs_by_student_content = defaultdict(lambda: defaultdict(list))
        all_standards_in_class = set()  # Union across the whole class — used for columns
        for s in subs.data or []:
            sid = s.get('student_id')
            cid = s.get('content_id')
            if sid and cid:
                subs_by_student_content[sid][cid].append(s)
                # Track every standard seen anywhere in the class for column union
                results = s.get('results') or {}
                mastery = results.get('standards_mastery') or {}
                for code in mastery.keys():
                    if code:
                        all_standards_in_class.add(code)

        # Build per-student mastery
        students_output = []
        for student in student_records:
            sid = student['student_id']
            by_content = subs_by_student_content.get(sid, {})
            selected = _select_submissions_by_mode(by_content, attempt_mode)
            mastery = _aggregate_mastery_for_student(selected, content_titles, attempt_mode)
            students_output.append({
                'student_id': sid,
                'student_name': student['student_name'],
                'mastery': mastery,
            })

        return jsonify({
            "class_id": class_id,
            "class_name": class_name,
            "attempt_mode": attempt_mode,
            "standards": sorted(all_standards_in_class),  # Class-wide union, not just aggregated students
            "students": students_output,
        })
    except Exception as e:
        _logger.exception("Progress rank error")
        return jsonify({"error": "An internal error occurred"}), 500
```

- [ ] **Step 2: Run tests**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/ -x -q --ignore=tests/load --ignore=tests/stress 2>&1 | tail -5`
Expected: All pass

- [ ] **Step 3: Commit**

```bash
git add backend/routes/student_portal_routes.py
git commit -m "feat: add class progress-rank endpoint with attempt-mode aggregation"
```

---

### Task 3: Frontend API helper

**Files:**
- Modify: `frontend/src/services/api.js`

- [ ] **Step 1: Add helper function**

At the end of `frontend/src/services/api.js`, add:

```javascript
export async function getClassProgressRank(classId, attemptMode) {
  var mode = attemptMode || 'latest';
  return fetchApi('/api/teacher/class/' + classId + '/progress-rank?attempt_mode=' + mode);
}
```

- [ ] **Step 2: Build**

Run: `cd /Users/alexc/Downloads/Graider/frontend && npm run build 2>&1 | tail -3`
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
git add frontend/src/services/api.js
git commit -m "feat: add getClassProgressRank API helper"
```

---

### Task 4: ProgressRankGrid component

**Files:**
- Create: `frontend/src/tabs/ProgressRankGrid.jsx`

- [ ] **Step 1: Create the component file**

Create `frontend/src/tabs/ProgressRankGrid.jsx` with:

```jsx
import React, { useState, useEffect } from "react";
import Icon from "../components/Icon";
import * as api from "../services/api";

function masteryColor(pct) {
  if (pct == null) return { bg: "var(--glass-bg)", text: "var(--text-muted)", label: "—" };
  if (pct >= 85) return { bg: "rgba(34,197,94,0.15)", text: "var(--success)", label: pct + "%" };
  if (pct >= 70) return { bg: "rgba(234,179,8,0.15)", text: "var(--warning)", label: pct + "%" };
  return { bg: "rgba(239,68,68,0.15)", text: "var(--danger)", label: pct + "%" };
}

export default function ProgressRankGrid({ classId }) {
  var [data, setData] = useState(null);
  var [loading, setLoading] = useState(true);
  var [error, setError] = useState(null);
  var [attemptMode, setAttemptMode] = useState('latest');
  var [strugglingOnly, setStrugglingOnly] = useState(false);
  var [selectedCell, setSelectedCell] = useState(null);

  useEffect(function() {
    if (!classId) return;
    var cancelled = false;
    setLoading(true);
    setError(null);
    api.getClassProgressRank(classId, attemptMode)
      .then(function(res) {
        if (cancelled) return;
        if (!res) {
          setError('No response from server');
          setData(null);
        } else if (res.error) {
          setError(res.error);
          setData(null);
        } else if (!res.students) {
          setError('Unexpected response format');
          setData(null);
        } else {
          setData(res);
        }
      })
      .catch(function(e) {
        if (cancelled) return;
        var msg = e && e.message ? e.message : 'Failed to load progress rank';
        setError(msg);
        setData(null);
      })
      .finally(function() {
        if (!cancelled) setLoading(false);
      });
    return function() { cancelled = true; };
  }, [classId, attemptMode]);

  if (loading) {
    return (
      <div className="glass-card" style={{ padding: "40px", textAlign: "center" }}>
        <div style={{ display: "inline-block", width: "32px", height: "32px", border: "3px solid var(--glass-border)", borderTopColor: "var(--accent-primary)", borderRadius: "50%", animation: "spin 0.8s linear infinite" }} />
        <p style={{ marginTop: "16px", color: "var(--text-secondary)" }}>Loading progress rank...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="glass-card" style={{ padding: "40px", textAlign: "center" }}>
        <p style={{ color: "var(--danger)" }}>{error}</p>
      </div>
    );
  }

  if (!data) return null;

  var standards = data.standards || [];
  var students = data.students || [];

  // Filter struggling students
  var displayStudents = strugglingOnly
    ? students.filter(function(s) {
        var mastery = s.mastery || {};
        return Object.keys(mastery).some(function(code) {
          var m = mastery[code];
          return m && m.percentage != null && m.percentage < 70;
        });
      })
    : students;

  var btnStyle = function(active) {
    return {
      padding: "6px 14px",
      borderRadius: "8px",
      border: "1px solid " + (active ? "var(--accent-primary)" : "var(--glass-border)"),
      background: active ? "rgba(99,102,241,0.15)" : "var(--glass-bg)",
      color: active ? "var(--accent-primary)" : "var(--text-secondary)",
      fontSize: "0.85rem",
      fontWeight: 600,
      cursor: "pointer",
    };
  };

  return (
    <div className="glass-card" style={{ padding: "20px" }}>
      <h3 style={{ fontSize: "1.1rem", fontWeight: 700, marginBottom: "4px" }}>
        Progress Rank {String.fromCharCode(8212)} {data.class_name}
      </h3>
      <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginBottom: "16px" }}>
        {students.length} students {String.fromCharCode(8226)} {standards.length} standards assessed
      </p>

      {/* Controls */}
      <div style={{ display: "flex", gap: "16px", alignItems: "center", marginBottom: "16px", flexWrap: "wrap" }}>
        <div style={{ display: "flex", gap: "4px" }}>
          <button onClick={function() { setAttemptMode('latest'); }} style={btnStyle(attemptMode === 'latest')}>Latest</button>
          <button onClick={function() { setAttemptMode('best'); }} style={btnStyle(attemptMode === 'best')}>Best</button>
          <button onClick={function() { setAttemptMode('average'); }} style={btnStyle(attemptMode === 'average')}>Average</button>
        </div>
        <div style={{ display: "flex", gap: "4px" }}>
          <button onClick={function() { setStrugglingOnly(false); }} style={btnStyle(!strugglingOnly)}>All Students</button>
          <button onClick={function() { setStrugglingOnly(true); }} style={btnStyle(strugglingOnly)}>Struggling Only</button>
        </div>
      </div>

      {standards.length === 0 ? (
        <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem", padding: "20px", textAlign: "center" }}>
          No standards-tagged assessments yet. Generate an assessment with standards to populate this grid.
        </p>
      ) : (
        <div style={{ overflowX: "auto", border: "1px solid var(--glass-border)", borderRadius: "8px" }}>
          <table style={{ borderCollapse: "collapse", width: "100%", minWidth: "600px" }}>
            <thead>
              <tr>
                <th style={{ position: "sticky", left: 0, background: "var(--card-bg)", zIndex: 2, padding: "10px 14px", textAlign: "left", fontSize: "0.8rem", fontWeight: 700, borderBottom: "1px solid var(--glass-border)", minWidth: "180px" }}>
                  Student
                </th>
                {standards.map(function(code) {
                  return (
                    <th key={code} style={{ padding: "10px 8px", fontSize: "0.7rem", fontFamily: "monospace", fontWeight: 700, borderBottom: "1px solid var(--glass-border)", borderLeft: "1px solid var(--glass-border)", minWidth: "90px", textAlign: "center" }}>
                      {code}
                    </th>
                  );
                })}
              </tr>
            </thead>
            <tbody>
              {displayStudents.map(function(student) {
                return (
                  <tr key={student.student_id}>
                    <td style={{ position: "sticky", left: 0, background: "var(--card-bg)", zIndex: 1, padding: "10px 14px", fontSize: "0.85rem", fontWeight: 600, borderBottom: "1px solid var(--glass-border)" }}>
                      {student.student_name}
                    </td>
                    {standards.map(function(code) {
                      var m = student.mastery[code];
                      var color = masteryColor(m ? m.percentage : null);
                      var clickable = !!m;
                      return (
                        <td
                          key={code}
                          onClick={function() { if (clickable) setSelectedCell({ student: student, standard: code, mastery: m }); }}
                          style={{
                            padding: "10px 8px",
                            textAlign: "center",
                            borderBottom: "1px solid var(--glass-border)",
                            borderLeft: "1px solid var(--glass-border)",
                            background: color.bg,
                            color: color.text,
                            fontSize: "0.8rem",
                            fontWeight: 600,
                            cursor: clickable ? "pointer" : "default",
                          }}
                          title={clickable ? "Click to see contributing submissions" : "No data"}
                        >
                          {color.label}
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Cell popover */}
      {selectedCell && (
        <div
          style={{
            position: "fixed", top: 0, left: 0, right: 0, bottom: 0,
            background: "var(--modal-bg)", display: "flex", alignItems: "center",
            justifyContent: "center", zIndex: 9999, padding: "20px",
          }}
          onClick={function() { setSelectedCell(null); }}
        >
          <div
            className="glass-card"
            style={{ maxWidth: "500px", width: "100%", padding: "24px", borderRadius: "16px" }}
            onClick={function(e) { e.stopPropagation(); }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "12px" }}>
              <div>
                <h4 style={{ fontSize: "1rem", fontWeight: 700 }}>{selectedCell.student.student_name}</h4>
                <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", fontFamily: "monospace" }}>{selectedCell.standard}</p>
              </div>
              <button onClick={function() { setSelectedCell(null); }} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--text-secondary)", fontSize: "1.2rem" }}>
                {String.fromCharCode(10005)}
              </button>
            </div>
            <div style={{ fontSize: "0.85rem", marginBottom: "10px" }}>
              Mastery: <strong>{selectedCell.mastery.percentage}%</strong> ({selectedCell.mastery.points_earned}/{selectedCell.mastery.points_possible} pts across {selectedCell.mastery.question_count} questions)
            </div>
            <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "6px" }}>
              Contributing submissions
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: "6px", maxHeight: "300px", overflowY: "auto" }}>
              {(selectedCell.mastery.contributing_submissions || []).map(function(c, i) {
                return (
                  <div key={i} style={{ padding: "8px 12px", background: "var(--glass-bg)", borderRadius: "6px", fontSize: "0.8rem" }}>
                    <div style={{ fontWeight: 600 }}>{c.title}</div>
                    <div style={{ color: "var(--text-secondary)", fontSize: "0.75rem" }}>
                      {c.attempt_number ? 'Attempt ' + c.attempt_number + ' ' + String.fromCharCode(8226) + ' ' : ''}
                      {c.points_earned}/{c.points_possible} pts
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Build**

Run: `cd /Users/alexc/Downloads/Graider/frontend && npm run build 2>&1 | tail -3`
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
git add frontend/src/tabs/ProgressRankGrid.jsx
git commit -m "feat: add ProgressRankGrid component for class mastery view"
```

---

### Task 5: Integrate into AnalyticsTab

**Files:**
- Modify: `frontend/src/tabs/AnalyticsTab.jsx`
- Modify: `frontend/src/App.jsx` (pass new `teacherClasses` prop)
- Modify: `frontend/src/components/StudentApp.jsx` (no — unrelated)

- [ ] **Step 1: Add import**

In `frontend/src/tabs/AnalyticsTab.jsx`, add this import near the other imports at the top:

```javascript
import ProgressRankGrid from "./ProgressRankGrid";
```

- [ ] **Step 2: Add teacherClasses prop to AnalyticsTab**

Find the AnalyticsTab function signature at the top of the component (around line 2360):

```javascript
export default React.memo(function AnalyticsTab({
  config,
  status,
  periods,
  sortedPeriods,
  savedAssignments,
  savedAssignmentData,
  addToast,
  assessmentResults,
}) {
```

Add `teacherClasses` to the destructured props:

```javascript
export default React.memo(function AnalyticsTab({
  config,
  status,
  periods,
  sortedPeriods,
  savedAssignments,
  savedAssignmentData,
  addToast,
  assessmentResults,
  teacherClasses,
}) {
```

- [ ] **Step 3: Pass teacherClasses from App.jsx to AnalyticsTab**

In `frontend/src/App.jsx`, find the `<AnalyticsTab` rendering (around line 9752). Add `teacherClasses={teacherClasses}` to the props:

```jsx
                  <AnalyticsTab
                    config={config}
                    status={status}
                    periods={periods}
                    sortedPeriods={sortedPeriods}
                    savedAssignments={savedAssignments}
                    savedAssignmentData={savedAssignmentData}
                    addToast={addToast}
                    assessmentResults={assessmentResults}
                    teacherClasses={teacherClasses}
                  />
```

`teacherClasses` is already declared in App.jsx state at line ~2110 (`const [teacherClasses, setTeacherClasses] = useState([]);`) and populated via `fetchTeacherClasses()`.

- [ ] **Step 4: Ensure teacherClasses is fetched when Analytics tab is active**

In `frontend/src/App.jsx`, find where `fetchTeacherClasses` is called. It's currently called on planner dashboard mount and after publishing. Add a new useEffect to fetch it when the analytics tab becomes active:

```javascript
  useEffect(function() {
    if (activeTab === "analytics" && teacherClasses.length === 0) {
      fetchTeacherClasses();
    }
  }, [activeTab]);
```

Place this near the other `activeTab` effects. This ensures the Analytics tab has classes available without forcing an extra fetch when we already have them.

- [ ] **Step 5: Add class selector state in AnalyticsTab**

Inside the `AnalyticsTab` component (after `export default React.memo(function AnalyticsTab({...}) {`, around line 2382 after the other state declarations), add:

```javascript
  // --- Class selector state (Phase 2: Progress Rank grid) ---
  var [selectedClassForGrid, setSelectedClassForGrid] = useState('all');
```

No fetch — we receive `teacherClasses` as a prop from App.jsx.

- [ ] **Step 6: Wrap existing return with class selector + conditional**

Find the top-level `return (` statement at line ~2535. The current structure is:

```jsx
  return (
                <div data-tutorial="analytics-card" className="fade-in">
                  {analyticsLoading ? (
                    ...existing analytics content...
                  )}
                </div>
```

Replace the outer return with:

```jsx
  return (
                <div data-tutorial="analytics-card" className="fade-in">
                  {/* Class selector — Phase 2 Progress Rank grid entry point */}
                  <div className="glass-card" style={{ padding: "14px 20px", marginBottom: "16px", display: "flex", alignItems: "center", gap: "12px" }}>
                    <label style={{ fontSize: "0.85rem", fontWeight: 600, color: "var(--text-secondary)" }}>Class:</label>
                    <select
                      value={selectedClassForGrid}
                      onChange={function(e) { setSelectedClassForGrid(e.target.value); }}
                      className="input"
                      style={{ padding: "6px 12px", fontSize: "0.9rem", minWidth: "200px" }}
                    >
                      <option value="all">All Classes</option>
                      {(teacherClasses || []).map(function(c) {
                        return <option key={c.id} value={c.id}>{c.name}</option>;
                      })}
                    </select>
                  </div>

                  {selectedClassForGrid !== 'all' ? (
                    <ProgressRankGrid classId={selectedClassForGrid} />
                  ) : analyticsLoading ? (
                    <div
                      className="glass-card"
                      style={{ padding: "80px", textAlign: "center" }}
                    >
                      <div style={{ display: "inline-block", width: "40px", height: "40px", border: "3px solid var(--glass-border)", borderTopColor: "var(--accent-primary)", borderRadius: "50%", animation: "spin 0.8s linear infinite" }} />
                      <h2 style={{ marginTop: "20px", fontSize: "1.3rem", fontWeight: 600 }}>
                        Generating Analytics...
                      </h2>
                      <p style={{ color: "var(--text-secondary)", marginTop: "8px", fontSize: "0.9rem" }}>
                        Crunching the numbers
                      </p>
                    </div>
                  ) : (
```

**IMPORTANT:** The existing return's content after `{analyticsLoading ? (... loading div ...) : (` needs to stay inside the `: (` branch of the new ternary. Don't delete existing content — the new structure is: selector + class card, then conditional (Grid | Loading | existing content). The closing paren for the existing content's ternary, and the closing `</div>` of the `fade-in` wrapper, stay exactly as they were.

Read the file first around line 2535-2560 to understand the exact existing structure, then carefully insert the new class selector card and the `selectedClassForGrid !== 'all' ? <ProgressRankGrid /> : ` branch, preserving everything else.

- [ ] **Step 7: Build**

Run: `cd /Users/alexc/Downloads/Graider/frontend && npm run build 2>&1 | tail -3`
Expected: Build succeeds

- [ ] **Step 8: Manual test**

1. Go to Analytics tab → verify existing content still loads (no class selected)
2. Pick a class from the dropdown → verify ProgressRankGrid renders
3. Verify the existing Analytics content is hidden while a class is selected
4. Toggle attempt mode buttons → verify grid refetches
5. Toggle struggling filter → verify students filter correctly
6. Click a cell with data → verify popover shows contributing submissions
7. Pick "All Classes" again → verify original Analytics content returns

- [ ] **Step 9: Commit**

```bash
git add frontend/src/tabs/AnalyticsTab.jsx frontend/src/App.jsx
git commit -m "feat: add class selector and Progress Rank grid to Analytics tab"
```

---

## Summary

| Task | What | Risk |
|------|------|------|
| 1 | Backend aggregation helpers | Low — pure functions, no integration |
| 2 | Backend endpoint | Medium — multi-table query, ownership check |
| 3 | Frontend API helper | Low — mechanical |
| 4 | ProgressRankGrid component (new) | Medium — new component, lots of JSX |
| 5 | AnalyticsTab integration | Medium — wrapping existing tab return without breaking it |

**Total: 3 modified files, 1 new file, 5 commits.**

**Before:** Analytics tab only shows cross-class charts. No way to see a single class's per-standard mastery.
**After:** Teacher picks a class → Progress Rank grid appears with students × standards color-coded matrix, attempt-mode toggle, struggling filter, and cell popovers showing contributing submissions.
