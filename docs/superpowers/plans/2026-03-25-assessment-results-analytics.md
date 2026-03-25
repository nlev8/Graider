# Assessment Results & Analytics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add formative/summative labels to assessments, a dedicated Assessment Results section in the Results tab, and assessment data integration into Analytics with per-question item analysis.

**Architecture:** New `assessment_results_routes.py` backend file for the `/api/assessment-results` endpoint. Extend analytics endpoint with `source` filter. Frontend adds collapsible Assessment Results section to ResultsTab and Item Analysis panel to AnalyticsTab. Publish modal gets formative/summative toggle.

**Tech Stack:** Flask/Python backend, React frontend (inline styles, no CSS framework), Supabase for data, Lucide icons via `Icon` component.

**Spec:** `docs/superpowers/specs/2026-03-25-assessment-results-analytics-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `backend/routes/assessment_results_routes.py` | CREATE | `/api/assessment-results` endpoint — queries both publish paths, aggregates stats and question analysis |
| `backend/routes/__init__.py` | MODIFY | Register new blueprint |
| `backend/routes/student_portal_routes.py` | MODIFY | Store `assessment_category` in publish settings |
| `backend/routes/analytics_routes.py` | MODIFY | Add `source` filter, include assessment data |
| `tests/test_assessment_results.py` | CREATE | Backend tests for new endpoint |
| `frontend/src/services/api.js` | MODIFY | Add `getAssessmentResults()` |
| `frontend/src/App.jsx` | MODIFY | Add state, fetch, pass props, publish modal toggle |
| `frontend/src/tabs/ResultsTab.jsx` | MODIFY | Add collapsible Assessment Results section |
| `frontend/src/tabs/AnalyticsTab.jsx` | MODIFY | Add source filter, item analysis panel, category summary |
| `frontend/e2e/assessment-results.spec.js` | CREATE | E2E tests for assessment results |

---

### Task 1: Backend — Assessment Results Endpoint

**Files:**
- Create: `backend/routes/assessment_results_routes.py`
- Create: `tests/test_assessment_results.py`
- Modify: `backend/routes/__init__.py`

- [ ] **Step 1: Create the assessment results route file**

Create `backend/routes/assessment_results_routes.py`:

```python
"""
Assessment Results Routes for Graider.
Returns aggregated assessment results with per-question analysis.
Queries both join-code (published_assessments + submissions) and
class-based (published_content + student_submissions) paths.
"""
import logging
from flask import Blueprint, request, jsonify, g
from backend.supabase_client import get_supabase_or_raise as get_supabase
from backend.utils.auth_decorators import require_teacher
from backend.utils.errors import handle_route_errors

assessment_results_bp = Blueprint('assessment_results', __name__)
_logger = logging.getLogger(__name__)


def _compute_letter_grade(percentage):
    """Convert percentage to letter grade."""
    if percentage is None:
        return None
    if percentage >= 90:
        return 'A'
    if percentage >= 80:
        return 'B'
    if percentage >= 70:
        return 'C'
    if percentage >= 60:
        return 'D'
    return 'F'


def _compute_question_analysis(assessment_data, all_submissions):
    """Compute per-question stats from submissions.

    Returns list of question analysis objects with percent_correct
    and response_distribution for MC/TF questions.
    """
    sections = assessment_data.get('sections', [])
    questions = []
    for sIdx, section in enumerate(sections):
        for qIdx, q in enumerate(section.get('questions', [])):
            key = str(sIdx) + '-' + str(qIdx)
            q_type = q.get('type', 'multiple_choice')
            analysis = {
                'number': q.get('number', qIdx + 1),
                'question': q.get('question', ''),
                'type': q_type,
                'correct_answer': q.get('answer'),
                'points': q.get('points', 1),
            }

            if q_type in ('multiple_choice', 'true_false'):
                # Count responses
                correct_count = 0
                total_count = 0
                distribution = {}

                if q_type == 'multiple_choice':
                    options = q.get('options', [])
                    for i in range(len(options)):
                        letter = chr(65 + i)
                        distribution[letter] = {'count': 0, 'percent': 0, 'is_correct': False}
                    # Mark correct
                    correct_letter = str(q.get('answer', '')).upper().strip()
                    if len(correct_letter) > 1 and correct_letter[1:2] == ')':
                        correct_letter = correct_letter[0]
                    if correct_letter in distribution:
                        distribution[correct_letter]['is_correct'] = True
                else:
                    distribution = {
                        'True': {'count': 0, 'percent': 0, 'is_correct': False},
                        'False': {'count': 0, 'percent': 0, 'is_correct': False},
                    }
                    correct_val = str(q.get('answer', '')).strip()
                    if correct_val in distribution:
                        distribution[correct_val]['is_correct'] = True

                for sub in all_submissions:
                    answers = sub.get('answers', {}) or {}
                    student_ans = answers.get(key)
                    if student_ans is None:
                        continue
                    total_count += 1

                    if q_type == 'multiple_choice':
                        if isinstance(student_ans, int):
                            letter = chr(65 + student_ans)
                        else:
                            letter = str(student_ans).upper().strip()
                            if len(letter) > 1 and letter[1:2] == ')':
                                letter = letter[0]
                        if letter in distribution:
                            distribution[letter]['count'] += 1
                        if letter == correct_letter:
                            correct_count += 1
                    else:
                        val = str(student_ans).strip()
                        if val in distribution:
                            distribution[val]['count'] += 1
                        if val.lower() == correct_val.lower():
                            correct_count += 1

                # Compute percentages
                for k in distribution:
                    if total_count > 0:
                        distribution[k]['percent'] = round(distribution[k]['count'] / total_count * 100)

                analysis['percent_correct'] = round(correct_count / total_count * 100) if total_count > 0 else 0
                analysis['total_responses'] = total_count
                analysis['response_distribution'] = distribution

            elif q_type in ('short_answer', 'extended_response'):
                graded = 0
                pending = 0
                total_score = 0
                max_pts = q.get('points', 1)
                for sub in all_submissions:
                    results = sub.get('results', {}) or {}
                    q_results = results.get('questions', [])
                    # Find matching question result
                    for qr in q_results:
                        if qr.get('number') == q.get('number'):
                            if qr.get('points_earned') is not None:
                                graded += 1
                                total_score += qr.get('points_earned', 0)
                            else:
                                pending += 1
                            break
                    else:
                        pending += 1

                analysis['percent_correct'] = None
                analysis['graded_count'] = graded
                analysis['pending_count'] = pending
                analysis['average_score'] = round(total_score / graded, 1) if graded > 0 else None
                analysis['max_points'] = max_pts

            else:
                # Matching or other types
                correct_count = 0
                total_count = 0
                for sub in all_submissions:
                    results = sub.get('results', {}) or {}
                    for qr in results.get('questions', []):
                        if qr.get('number') == q.get('number'):
                            total_count += 1
                            if qr.get('is_correct'):
                                correct_count += 1
                            break
                analysis['percent_correct'] = round(correct_count / total_count * 100) if total_count > 0 else 0
                analysis['total_responses'] = total_count

            questions.append(analysis)

    return questions


@assessment_results_bp.route('/api/assessment-results', methods=['GET'])
@require_teacher
@handle_route_errors
def get_assessment_results():
    """Return all assessments with aggregated results for the current teacher."""
    db = get_supabase()
    teacher_id = g.teacher_id

    # Audit log
    try:
        from backend.utils.audit import audit_log
        audit_log("VIEW_ASSESSMENT_RESULTS", "Teacher viewed assessment results", user="teacher", teacher_id=teacher_id)
    except Exception:
        pass

    assessments = []

    # 1. Join-code assessments (published_assessments + submissions)
    try:
        pa_result = db.table('published_assessments').select('*').eq('teacher_id', teacher_id).order('created_at', desc=True).execute()
        for pa in (pa_result.data or []):
            settings = pa.get('settings', {}) or {}
            content_type = settings.get('content_type', 'assessment')
            if content_type != 'assessment':
                continue

            join_code = pa.get('join_code', '')
            assessment_data = pa.get('assessment', {}) or {}

            # Fetch submissions for this assessment
            subs_result = db.table('submissions').select('*').eq('join_code', join_code).order('submitted_at', desc=True).execute()
            subs = subs_result.data or []

            # Compute stats
            scores = [s.get('percentage') for s in subs if s.get('percentage') is not None]
            times = [s.get('time_taken_seconds') for s in subs if s.get('time_taken_seconds')]
            pending = sum(1 for s in subs if s.get('score') is None)

            entry = {
                'id': pa.get('id'),
                'title': pa.get('title', assessment_data.get('title', 'Untitled')),
                'assessment_category': settings.get('assessment_category', 'formative'),
                'content_type': 'assessment',
                'source': 'join_code',
                'join_code': join_code,
                'period': settings.get('period', ''),
                'published_at': pa.get('created_at'),
                'is_active': pa.get('is_active', True),
                'stats': {
                    'total_submissions': len(subs),
                    'expected_submissions': None,
                    'average_score': round(sum(scores) / len(scores)) if scores else None,
                    'highest_score': max(scores) if scores else None,
                    'lowest_score': min(scores) if scores else None,
                    'average_time_seconds': round(sum(times) / len(times)) if times else None,
                    'pending_count': pending,
                    'graded_count': len(subs) - pending,
                },
                'submissions': [
                    {
                        'student_name': s.get('student_name', 'Anonymous'),
                        'score': s.get('score'),
                        'percentage': s.get('percentage'),
                        'letter_grade': _compute_letter_grade(s.get('percentage')),
                        'time_taken_seconds': s.get('time_taken_seconds'),
                        'submitted_at': s.get('submitted_at'),
                        'status': 'pending' if s.get('score') is None else 'graded',
                    }
                    for s in subs
                ],
                'question_analysis': _compute_question_analysis(assessment_data, subs),
            }
            assessments.append(entry)
    except Exception as e:
        _logger.warning("Error fetching join-code assessments: %s", str(e))

    # 2. Class-based assessments (published_content + student_submissions)
    try:
        pc_result = db.table('published_content').select('*').eq('teacher_id', teacher_id).eq('content_type', 'assessment').order('created_at', desc=True).execute()
        for pc in (pc_result.data or []):
            content_id = pc.get('id')
            settings = pc.get('settings', {}) or {}
            assessment_data = pc.get('content', {}) or {}

            # Fetch submissions
            subs_result = db.table('student_submissions').select('*').eq('content_id', content_id).order('submitted_at', desc=True).execute()
            subs = subs_result.data or []

            # Expected count from class enrollment
            expected = None
            class_id = pc.get('class_id')
            if class_id:
                try:
                    enrolled = db.table('class_students').select('id', count='exact').eq('class_id', class_id).execute()
                    expected = enrolled.count
                except Exception:
                    pass

            scores = [s.get('percentage') for s in subs if s.get('percentage') is not None]
            times = [s.get('time_taken_seconds') for s in subs if s.get('time_taken_seconds')]
            pending = sum(1 for s in subs if s.get('status') in ('submitted', 'partial'))

            entry = {
                'id': content_id,
                'title': pc.get('title', 'Untitled'),
                'assessment_category': settings.get('assessment_category', 'formative'),
                'content_type': 'assessment',
                'source': 'class_based',
                'join_code': pc.get('join_code', ''),
                'period': settings.get('period', '') or pc.get('period', ''),
                'published_at': pc.get('created_at'),
                'is_active': pc.get('is_active', True),
                'stats': {
                    'total_submissions': len(subs),
                    'expected_submissions': expected,
                    'average_score': round(sum(scores) / len(scores)) if scores else None,
                    'highest_score': max(scores) if scores else None,
                    'lowest_score': min(scores) if scores else None,
                    'average_time_seconds': round(sum(times) / len(times)) if times else None,
                    'pending_count': pending,
                    'graded_count': len(subs) - pending,
                },
                'submissions': [
                    {
                        'student_name': s.get('student_name', 'Anonymous'),
                        'score': s.get('score'),
                        'percentage': s.get('percentage'),
                        'letter_grade': _compute_letter_grade(s.get('percentage')),
                        'time_taken_seconds': s.get('time_taken_seconds'),
                        'submitted_at': s.get('submitted_at'),
                        'status': s.get('status', 'submitted'),
                    }
                    for s in subs
                ],
                'question_analysis': _compute_question_analysis(assessment_data, subs),
            }
            assessments.append(entry)
    except Exception as e:
        _logger.warning("Error fetching class-based assessments: %s", str(e))

    # Sort by published_at descending
    assessments.sort(key=lambda a: a.get('published_at') or '', reverse=True)

    # Filter by category if requested
    category = request.args.get('category')
    if category in ('formative', 'summative'):
        assessments = [a for a in assessments if a.get('assessment_category') == category]

    return jsonify({'assessments': assessments})
```

- [ ] **Step 2: Register the blueprint**

In `backend/routes/__init__.py`, add import and registration:

```python
from backend.routes.assessment_results_routes import assessment_results_bp
# In register_routes():
app.register_blueprint(assessment_results_bp)
```

- [ ] **Step 3: Write backend tests**

Create `tests/test_assessment_results.py` with tests for:
- Auth required (no teacher header → 401/200 in dev)
- Empty results for teacher with no assessments
- Returns assessment data with correct structure
- `category` filter works
- Letter grade computation
- Question analysis computation for MC, TF, short answer

- [ ] **Step 4: Run tests**

Run: `source venv/bin/activate && python -m pytest tests/test_assessment_results.py -v`
Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add backend/routes/assessment_results_routes.py backend/routes/__init__.py tests/test_assessment_results.py
git commit -m "feat: add /api/assessment-results endpoint with per-question analysis"
```

---

### Task 2: Publish Flow — Assessment Category

**Files:**
- Modify: `backend/routes/student_portal_routes.py:68-80`
- Modify: `frontend/src/App.jsx:1974-1984,4532-4555`

- [ ] **Step 1: Backend — store assessment_category in publish settings**

In `backend/routes/student_portal_routes.py`, in the `publish_assessment` function, add `assessment_category` to `db_settings` dict (around line 73):

```python
assessment_category = settings.get('assessment_category', 'formative')
if assessment_category not in ('formative', 'summative'):
    assessment_category = 'formative'
```

Add to `db_settings`:
```python
"assessment_category": assessment_category,
```

Do the same in the class-based publish endpoint if it exists in `student_account_routes.py`.

- [ ] **Step 2: Frontend — add assessmentCategory to publishSettings**

In `App.jsx`, add `assessmentCategory: 'formative'` to the `publishSettings` state (~line 1974).

In the content type toggle handler (~line 4532), when `contentType === 'assessment'`, keep `assessmentCategory` as-is (let user choose). When switching to `assignment`, reset to `null`.

- [ ] **Step 3: Frontend — add formative/summative toggle to publish modal**

In the publish modal JSX in `App.jsx`, after the assessment/assignment toggle, add a formative/summative toggle. Only visible when `publishSettings.contentType === 'assessment'`. Two buttons: "Formative" (default, green) and "Summative" (red). Sets `publishSettings.assessmentCategory`.

Include `assessment_category: publishSettings.assessmentCategory` in the API call payload.

- [ ] **Step 4: Verify build**

Run: `cd frontend && npx vite build 2>&1 | tail -3`

- [ ] **Step 5: Commit**

```bash
git add backend/routes/student_portal_routes.py frontend/src/App.jsx
git commit -m "feat: add formative/summative assessment category to publish flow"
```

---

### Task 3: Frontend — Assessment Results Section in Results Tab

**Files:**
- Modify: `frontend/src/services/api.js`
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/tabs/ResultsTab.jsx`

- [ ] **Step 1: Add API function**

In `frontend/src/services/api.js`, add:

```javascript
export async function getAssessmentResults(category) {
  var url = '/api/assessment-results'
  if (category) url += '?category=' + category
  return fetchApi(url)
}
```

- [ ] **Step 2: Add state and fetch in App.jsx**

Add state:
```javascript
const [assessmentResults, setAssessmentResults] = useState([])
```

Add fetch in a useEffect (similar to portalSubmissions pattern at line 1391):
```javascript
// Fetch assessment results periodically
useEffect(() => {
  if (!userApproved) return
  var fetchAssessments = async function() {
    try {
      var data = await api.getAssessmentResults()
      setAssessmentResults(data.assessments || [])
    } catch (e) {}
  }
  fetchAssessments()
  var interval = setInterval(fetchAssessments, 30000)
  return function() { clearInterval(interval) }
}, [userApproved])
```

Pass to ResultsTab:
```jsx
<ResultsTab ... assessmentResults={assessmentResults} />
```

Also pass to AnalyticsTab for later use.

- [ ] **Step 3: Build Assessment Results section in ResultsTab**

Add to the top of ResultsTab, before existing results content:

- Collapsible section with purple header: chevron + "Assessment Results" + count badge
- Filter tabs: All / Formative / Summative (local state)
- Table with columns: Assessment, Type, Submissions, Avg Score, Status, View Details
- "View Details" toggles an expanded inline panel showing:
  - Summary stats bar
  - Student scores table (sortable)
  - Per-question breakdown (collapsible)
- Use Lucide `Icon` component (import from `../components/Icon`)
- Support light/dark mode via existing theme patterns

- [ ] **Step 4: Make Assignment Results collapsible too**

Wrap existing results content in a collapsible section with header: chevron + "Assignment Results" + count badge.

- [ ] **Step 5: Verify build**

Run: `cd frontend && npx vite build 2>&1 | tail -3`

- [ ] **Step 6: Commit**

```bash
git add frontend/src/services/api.js frontend/src/App.jsx frontend/src/tabs/ResultsTab.jsx
git commit -m "feat: add collapsible Assessment Results section to Results tab"
```

---

### Task 4: Analytics — Source Filter and Assessment Data Merge

**Files:**
- Modify: `backend/routes/analytics_routes.py`
- Modify: `frontend/src/tabs/AnalyticsTab.jsx`

- [ ] **Step 1: Backend — add source filter to analytics endpoint**

In `backend/routes/analytics_routes.py`, in `get_analytics()`:

Add `source` query parameter:
```python
source = request.args.get('source', 'all')  # all | assignments | assessments
```

When `source` is `all` or `assessments`:
- Query `published_assessments` + `submissions` for the teacher
- Query `published_content` (assessments) + `student_submissions`
- Merge assessment scores into `all_grades`, `student_progress`, `class_stats`
- Add `assessment_stats` and `assessment_category_summary` to response

When `source` is `assignments`:
- Existing behavior, no changes

- [ ] **Step 2: Backend — add assessment_stats and category_summary to response**

Add to analytics response:
```python
response['assessment_stats'] = [
    {
        'name': title,
        'category': category,
        'average': avg_score,
        'count': submission_count,
        'highest': max_score,
        'lowest': min_score,
    }
    for each assessment
]
response['assessment_category_summary'] = {
    'formative_average': formative_avg,
    'formative_count': formative_count,
    'summative_average': summative_avg,
    'summative_count': summative_count,
}
```

- [ ] **Step 3: Frontend — add source filter toggle to AnalyticsTab**

Add filter toggle at top of AnalyticsTab: "All / Assignments / Assessments"
- State: `analyticsSource` with values `'all' | 'assignments' | 'assessments'`
- Pass to API call: `api.getAnalytics(period, source)`
- Three styled buttons, active state highlighted

- [ ] **Step 4: Frontend — add Formative vs Summative summary card**

Small card in the analytics overview area:
- "Formative Avg: X%" and "Summative Avg: Y%"
- Only shown when assessment data exists
- Use data from `assessment_category_summary` in response

- [ ] **Step 5: Verify build and run backend tests**

Run: `cd frontend && npx vite build 2>&1 | tail -3`
Run: `source venv/bin/activate && python -m pytest tests/ -q --ignore=tests/load --ignore=tests/stress`

- [ ] **Step 6: Commit**

```bash
git add backend/routes/analytics_routes.py frontend/src/tabs/AnalyticsTab.jsx frontend/src/services/api.js
git commit -m "feat: merge assessment data into Analytics with source filter and category summary"
```

---

### Task 5: Analytics — Item Analysis Panel

**Files:**
- Modify: `frontend/src/tabs/AnalyticsTab.jsx`

- [ ] **Step 1: Add Item Analysis panel component**

New section in AnalyticsTab, below existing charts. Only visible when assessment data exists.

Components:
- Assessment selector dropdown (lists assessments with results)
- Horizontal bar chart showing % correct per question
  - Color: green (>80%), amber (50-80%), red (<50%)
- Click handler on bars to expand answer distribution
  - MC: shows each option with count + percent, correct marked
  - TF: shows True/False split
  - Short answer: shows graded/pending/avg score

Data source: `assessmentResults` prop passed from App.jsx (same data used in Results tab).

- [ ] **Step 2: Verify build**

Run: `cd frontend && npx vite build 2>&1 | tail -3`

- [ ] **Step 3: Commit**

```bash
git add frontend/src/tabs/AnalyticsTab.jsx
git commit -m "feat: add Item Analysis panel to Analytics with per-question breakdown"
```

---

### Task 6: E2E Tests and Full Verification

**Files:**
- Create: `frontend/e2e/assessment-results.spec.js`

- [ ] **Step 1: Create E2E tests**

Test coverage:
- `/api/assessment-results` returns data for published assessments
- Assessment category filter works
- Question analysis includes correct distributions
- Analytics source filter returns assessment data

Use existing test patterns from `api-endpoints.spec.js` — publish an assessment, submit answers, then verify the results endpoint returns correct aggregations.

- [ ] **Step 2: Run full Playwright suite**

Run: `cd frontend && npx playwright test --reporter=dot --workers=1`
Expected: All tests pass (including new ones)

- [ ] **Step 3: Run full backend tests**

Run: `source venv/bin/activate && python -m pytest tests/ -q --ignore=tests/load --ignore=tests/stress`
Expected: All tests pass

- [ ] **Step 4: Commit**

```bash
git add frontend/e2e/assessment-results.spec.js
git commit -m "test: add E2E tests for assessment results and analytics integration"
```
