# Student Portal Resources — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Resources section to the student portal so teachers can share study guides, flashcards, and slide decks with their classes, and students can view/download them.

**Architecture:** Reuse the existing `published_content` table with new content_type values (`study_guide`, `flashcards`, `slide_deck`). Add a "Share with class" button to each generated material in the Tools tab. Add a "Resources" section to the student dashboard that lists shared materials grouped by type. Students click to view (study guides, flashcards) or download (slide decks). No new tables — just new content_type values flowing through the existing publish-to-class pipeline.

**Tech Stack:** Existing Flask endpoints, Supabase `published_content` table, StudentDashboard.jsx

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `backend/routes/student_account_routes.py` | **Modify** | Add `/api/student/resources` endpoint (list resources for student's class) |
| `frontend/src/components/StudentDashboard.jsx` | **Modify** | Add Resources section with view/download per type |
| `frontend/src/App.jsx` | **Modify** | Add "Share with class" button to study guide, flashcard, and slide deck results |
| `tests/test_student_resources.py` | **Create** | Tests for resource listing + sharing |

---

### Task 1: Backend — student resources endpoint

**Files:**
- Modify: `backend/routes/student_account_routes.py`
- Create: `tests/test_student_resources.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_student_resources.py`:

```python
"""Tests for student portal resources — publish + list + view."""

import json
import os
import pytest
from unittest.mock import patch, MagicMock
from flask import Flask


def _mock_supabase(published_content_data):
    """Mock Supabase that returns published content."""
    mock_sb = MagicMock()

    def table_router(name):
        mock_table = MagicMock()
        result = MagicMock()
        if name == 'published_content':
            result.data = published_content_data
        else:
            result.data = []
        for method in ('select', 'eq', 'neq', 'ilike', 'like', 'order',
                       'limit', 'offset', 'gt', 'gte', 'lt', 'lte', 'in_',
                       'insert', 'update', 'delete'):
            getattr(mock_table, method).return_value = mock_table
        mock_table.execute.return_value = result
        return mock_table

    mock_sb.table = table_router
    return mock_sb


def _make_app():
    """Create a minimal Flask app with student account routes."""
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test'
    app.config['RATELIMIT_ENABLED'] = False

    from backend.extensions import limiter
    limiter.init_app(app)

    from backend.routes.student_account_routes import student_account_bp
    app.register_blueprint(student_account_bp)
    return app


def _mock_supabase_with_session_and_content(session_data, content_data):
    """Mock Supabase that validates student session then returns published content."""
    mock_sb = MagicMock()

    def table_router(name):
        mock_table = MagicMock()
        result = MagicMock()
        if name == 'student_sessions':
            result.data = session_data
        elif name == 'published_content':
            result.data = content_data
        else:
            result.data = []
        for method in ('select', 'eq', 'neq', 'ilike', 'like', 'order',
                       'limit', 'offset', 'gt', 'gte', 'lt', 'lte', 'in_',
                       'insert', 'update', 'delete'):
            getattr(mock_table, method).return_value = mock_table
        mock_table.execute.return_value = result
        return mock_table

    mock_sb.table = table_router
    return mock_sb


VALID_SESSION = [{"student_id": "student-1", "class_id": "class-1"}]

MIXED_CONTENT = [
    {"id": "res-1", "title": "Unit 3 Study Guide", "content_type": "study_guide",
     "created_at": "2026-04-04T10:00:00", "is_active": True, "settings": {}},
    {"id": "res-2", "title": "Vocab Flashcards", "content_type": "flashcards",
     "created_at": "2026-04-04T11:00:00", "is_active": True, "settings": {}},
    {"id": "res-3", "title": "Chapter 5 Slides", "content_type": "slide_deck",
     "created_at": "2026-04-04T12:00:00", "is_active": True, "settings": {}},
    {"id": "res-4", "title": "Chapter 5 Quiz", "content_type": "assessment",
     "created_at": "2026-04-04T09:00:00", "is_active": True, "settings": {}},
]


class TestStudentResources:
    def test_returns_only_resource_types(self):
        """Should return study_guide/flashcards/slide_deck but NOT assessments."""
        app = _make_app()
        with app.test_client() as client:
            with patch('backend.routes.student_account_routes.get_supabase',
                       return_value=_mock_supabase_with_session_and_content(VALID_SESSION, MIXED_CONTENT)):
                resp = client.get('/api/student/resources',
                                  headers={"X-Student-Token": "valid-token"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["resources"]) == 3
        types = [r["content_type"] for r in data["resources"]]
        assert "assessment" not in types
        assert "study_guide" in types
        assert "flashcards" in types
        assert "slide_deck" in types

    def test_rejects_missing_token(self):
        """Should return 401 without student token."""
        app = _make_app()
        with app.test_client() as client:
            resp = client.get('/api/student/resources')
        assert resp.status_code == 401

    def test_rejects_invalid_session(self):
        """Should return 401 with expired/invalid session."""
        app = _make_app()
        with app.test_client() as client:
            with patch('backend.routes.student_account_routes.get_supabase',
                       return_value=_mock_supabase_with_session_and_content([], MIXED_CONTENT)):
                resp = client.get('/api/student/resources',
                                  headers={"X-Student-Token": "expired-token"})
        assert resp.status_code == 401

    def test_returns_empty_when_no_resources(self):
        """Should return empty list when only assessments published."""
        assessments_only = [
            {"id": "a1", "title": "Quiz", "content_type": "assessment",
             "created_at": "2026-04-04T09:00:00", "is_active": True, "settings": {}},
        ]
        app = _make_app()
        with app.test_client() as client:
            with patch('backend.routes.student_account_routes.get_supabase',
                       return_value=_mock_supabase_with_session_and_content(VALID_SESSION, assessments_only)):
                resp = client.get('/api/student/resources',
                                  headers={"X-Student-Token": "valid-token"})
        data = resp.get_json()
        assert data["resources"] == []


class TestStudentResourceContent:
    def test_returns_resource_content(self):
        """Should return full resource content for a valid resource ID."""
        resource_data = [{
            "id": "res-1", "title": "Study Guide", "content_type": "study_guide",
            "content": {"sections": [{"heading": "Key Concepts", "content": ["Point 1"]}]},
            "settings": {}, "is_active": True,
        }]
        app = _make_app()
        with app.test_client() as client:
            with patch('backend.routes.student_account_routes.get_supabase',
                       return_value=_mock_supabase_with_session_and_content(VALID_SESSION, resource_data)):
                resp = client.get('/api/student/resource/res-1',
                                  headers={"X-Student-Token": "valid-token"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["resource"]["title"] == "Study Guide"
        assert "sections" in data["resource"]["content"]

    def test_rejects_assessment_as_resource(self):
        """Should return 400 when requesting an assessment via resource endpoint."""
        assessment_data = [{
            "id": "a1", "title": "Quiz", "content_type": "assessment",
            "content": {}, "settings": {}, "is_active": True,
        }]
        app = _make_app()
        with app.test_client() as client:
            with patch('backend.routes.student_account_routes.get_supabase',
                       return_value=_mock_supabase_with_session_and_content(VALID_SESSION, assessment_data)):
                resp = client.get('/api/student/resource/a1',
                                  headers={"X-Student-Token": "valid-token"})
        assert resp.status_code == 400

    def test_returns_404_for_missing_resource(self):
        """Should return 404 when resource doesn't exist."""
        app = _make_app()
        with app.test_client() as client:
            with patch('backend.routes.student_account_routes.get_supabase',
                       return_value=_mock_supabase_with_session_and_content(VALID_SESSION, [])):
                resp = client.get('/api/student/resource/nonexistent',
                                  headers={"X-Student-Token": "valid-token"})
        assert resp.status_code == 404
```

- [ ] **Step 2: Implement the student resources endpoint**

In `backend/routes/student_account_routes.py`, add after the existing `/api/student/dashboard` endpoint:

```python
RESOURCE_CONTENT_TYPES = ['study_guide', 'flashcards', 'slide_deck']


@student_account_bp.route('/api/student/resources', methods=['GET'])
def student_resources():
    """List resources (study guides, flashcards, slide decks) published to student's class.

    Uses X-Student-Token header for auth (same as student dashboard).
    Returns only resource-type content, not assessments/assignments.
    """
    token = request.headers.get('X-Student-Token', '')
    if not token:
        return jsonify({"error": "Student token required"}), 401

    try:
        from backend.supabase_client import get_supabase
        sb = get_supabase()
        if not sb:
            return jsonify({"resources": []})

        # Validate student session
        session_result = sb.table('student_sessions').select(
            'student_id, class_id'
        ).eq('token_hash', _hash_token(token)).gt(
            'expires_at', _now_iso()
        ).execute()

        if not session_result.data:
            return jsonify({"error": "Invalid or expired session"}), 401

        class_id = session_result.data[0]['class_id']

        # Get published resources for this class
        content_result = sb.table('published_content').select(
            'id, title, content_type, created_at, settings'
        ).eq('class_id', class_id).eq('is_active', True).order(
            'created_at', desc=True
        ).execute()

        resources = []
        for item in (content_result.data or []):
            if item.get('content_type') in RESOURCE_CONTENT_TYPES:
                resources.append({
                    "id": item['id'],
                    "title": item.get('title', 'Untitled'),
                    "content_type": item['content_type'],
                    "created_at": item.get('created_at', ''),
                })

        return jsonify({"resources": resources})

    except Exception as e:
        logger.exception("Student resources error")
        return jsonify({"error": "Failed to load resources"}), 500
```

Note: `_hash_token` and `_now_iso` are existing helper functions in the file. Search for them to confirm the exact names used. If they don't exist as standalone functions, check how `/api/student/dashboard` validates the token and mirror that pattern exactly.

- [ ] **Step 3: Add resource content endpoint**

Add after the resources list endpoint:

```python
@student_account_bp.route('/api/student/resource/<content_id>', methods=['GET'])
def student_resource_content(content_id):
    """Get full resource content for viewing/downloading.

    Returns the content JSON for study guides/flashcards, or the
    slide deck data for download.
    """
    token = request.headers.get('X-Student-Token', '')
    if not token:
        return jsonify({"error": "Student token required"}), 401

    try:
        from backend.supabase_client import get_supabase
        sb = get_supabase()
        if not sb:
            return jsonify({"error": "Not available"}), 500

        # Validate student session
        session_result = sb.table('student_sessions').select(
            'student_id, class_id'
        ).eq('token_hash', _hash_token(token)).gt(
            'expires_at', _now_iso()
        ).execute()

        if not session_result.data:
            return jsonify({"error": "Invalid or expired session"}), 401

        class_id = session_result.data[0]['class_id']

        # Get the resource — must belong to student's class
        content_result = sb.table('published_content').select(
            'id, title, content_type, content, settings'
        ).eq('id', content_id).eq('class_id', class_id).eq(
            'is_active', True
        ).execute()

        if not content_result.data:
            return jsonify({"error": "Resource not found"}), 404

        item = content_result.data[0]
        if item.get('content_type') not in RESOURCE_CONTENT_TYPES:
            return jsonify({"error": "Not a resource"}), 400

        return jsonify({
            "resource": {
                "id": item['id'],
                "title": item.get('title', 'Untitled'),
                "content_type": item['content_type'],
                "content": item.get('content', {}),
            }
        })

    except Exception as e:
        logger.exception("Student resource content error")
        return jsonify({"error": "Failed to load resource"}), 500
```

- [ ] **Step 4: Run tests**

```bash
cd /Users/alexc/Downloads/Graider && source venv/bin/activate
python -m pytest tests/test_student_resources.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/routes/student_account_routes.py tests/test_student_resources.py
git commit -m "feat: add student resources endpoints (list + view study guides/flashcards/slides)"
```

---

### Task 2: Teacher-side — "Share with class" buttons

**Files:**
- Modify: `frontend/src/App.jsx`

- [ ] **Step 1: Add share function**

Find the study guide state variables (search for `const [studyGuide`). Add nearby:

```javascript
  async function shareWithClass(content, contentType, title) {
    if (!teacherClasses || teacherClasses.length === 0) {
      addToast('No classes found. Sync your roster first.', 'warning');
      return;
    }
    // If one class, publish directly. If multiple, let teacher pick.
    var targetClass = teacherClasses[0];
    if (teacherClasses.length > 1) {
      // Simple prompt — could be a modal later
      var classNames = teacherClasses.map(function(c, i) { return (i + 1) + '. ' + c.name; }).join(String.fromCharCode(10));
      var choice = prompt('Which class?' + String.fromCharCode(10) + classNames + String.fromCharCode(10) + 'Enter number:');
      if (!choice) return;
      var idx = parseInt(choice) - 1;
      if (idx < 0 || idx >= teacherClasses.length) { addToast('Invalid choice', 'error'); return; }
      targetClass = teacherClasses[idx];
    }
    try {
      var resp = await fetch('/api/publish-to-class', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          class_id: targetClass.id,
          content: content,
          content_type: contentType,
          title: title,
        }),
      });
      var data = await resp.json();
      if (data.error) {
        addToast(data.error, 'error');
      } else {
        addToast('Shared "' + title + '" with ' + targetClass.name, 'success');
      }
    } catch (err) {
      addToast('Failed to share: ' + err.message, 'error');
    }
  }
```

- [ ] **Step 2: Add "Share with class" button to Study Guide results**

Find the study guide Export DOCX / Export PDF buttons (search for `Export DOCX` near the study guide section). Add a Share button after the export buttons:

```javascript
                              <button
                                onClick={function() { shareWithClass(studyGuide, 'study_guide', studyGuide.title || 'Study Guide'); }}
                                className="btn btn-secondary"
                                style={{ padding: "8px 16px" }}
                              >
                                <Icon name="Share2" size={16} /> Share with Class
                              </button>
```

- [ ] **Step 3: Add "Share with class" button to Flashcard results**

Find the flashcard Export PDF / Export DOCX buttons. Add after them:

```javascript
                              <button
                                onClick={function() { shareWithClass(flashcards, 'flashcards', flashcards.title || 'Flashcards'); }}
                                className="btn btn-secondary"
                                style={{ padding: "8px 16px" }}
                              >
                                <Icon name="Share2" size={16} /> Share with Class
                              </button>
```

- [ ] **Step 4: Add "Share with class" button to Slide Deck results**

Find the slide deck Download PowerPoint button. Add after it:

```javascript
                              <button
                                onClick={function() { shareWithClass(slideDeck, 'slide_deck', slideDeck.title || 'Slide Deck'); }}
                                className="btn btn-secondary"
                                style={{ padding: "8px 16px" }}
                              >
                                <Icon name="Share2" size={16} /> Share with Class
                              </button>
```

- [ ] **Step 5: Build and commit**

```bash
cd /Users/alexc/Downloads/Graider/frontend && npm run build
cd .. && git add frontend/src/App.jsx
git commit -m "feat: add Share with Class buttons to study guide, flashcards, and slide deck"
```

---

### Task 3: Student Dashboard — Resources section

**Files:**
- Modify: `frontend/src/components/StudentDashboard.jsx`

- [ ] **Step 1: Read the current StudentDashboard**

Read `frontend/src/components/StudentDashboard.jsx` to understand the current structure. Find where "Your Assignments" section is rendered.

- [ ] **Step 2: Add resources state and fetch**

Add state variables and fetch resources on mount:

```javascript
  const [resources, setResources] = useState([]);
  const [resourcesLoading, setResourcesLoading] = useState(true);
  const [selectedResource, setSelectedResource] = useState(null);

  useEffect(function() {
    var token = localStorage.getItem('student_token');
    if (!token) return;
    fetch('/api/student/resources', {
      headers: { 'X-Student-Token': token }
    })
      .then(function(r) { return r.json(); })
      .then(function(data) {
        setResources(data.resources || []);
        setResourcesLoading(false);
      })
      .catch(function() { setResourcesLoading(false); });
  }, []);
```

- [ ] **Step 3: Add Resources section below assignments**

After the existing assignments list, add:

```javascript
          {/* Resources Section */}
          {resources.length > 0 && (
            <div style={{ marginTop: "24px" }}>
              <h3 style={{ fontSize: "1.1rem", fontWeight: 600, marginBottom: "12px", display: "flex", alignItems: "center", gap: "8px" }}>
                <span style={{ fontSize: "1.2rem" }}>{String.fromCharCode(128218)}</span>
                Study Materials
              </h3>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(250px, 1fr))", gap: "12px" }}>
                {resources.map(function(res) {
                  var icon = res.content_type === 'study_guide' ? String.fromCharCode(128214)
                    : res.content_type === 'flashcards' ? String.fromCharCode(128196)
                    : res.content_type === 'slide_deck' ? String.fromCharCode(128253)
                    : String.fromCharCode(128196);
                  var typeLabel = res.content_type === 'study_guide' ? 'Study Guide'
                    : res.content_type === 'flashcards' ? 'Flashcards'
                    : res.content_type === 'slide_deck' ? 'Slide Deck'
                    : res.content_type;
                  return (
                    <div
                      key={res.id}
                      onClick={function() {
                        var token = localStorage.getItem('student_token');
                        fetch('/api/student/resource/' + res.id, {
                          headers: { 'X-Student-Token': token }
                        })
                          .then(function(r) { return r.json(); })
                          .then(function(data) {
                            if (data.resource) {
                              setSelectedResource(data.resource);
                            }
                          })
                          .catch(function() {});
                      }}
                      style={{
                        padding: "16px",
                        borderRadius: "12px",
                        border: "1px solid var(--border)",
                        background: "var(--glass-bg)",
                        cursor: "pointer",
                        transition: "transform 0.1s",
                      }}
                    >
                      <div style={{ fontSize: "1.5rem", marginBottom: "8px" }}>{icon}</div>
                      <div style={{ fontSize: "0.9rem", fontWeight: 600 }}>{res.title}</div>
                      <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: "4px" }}>{typeLabel}</div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Resource Viewer Modal */}
          {selectedResource && (
            <div style={{
              position: "fixed", top: 0, left: 0, right: 0, bottom: 0,
              background: "rgba(0,0,0,0.5)", display: "flex", alignItems: "center",
              justifyContent: "center", zIndex: 1000, padding: "20px",
            }} onClick={function() { setSelectedResource(null); }}>
              <div
                style={{
                  background: "var(--bg-primary)", borderRadius: "16px",
                  padding: "24px", maxWidth: "700px", width: "100%",
                  maxHeight: "80vh", overflowY: "auto",
                }}
                onClick={function(e) { e.stopPropagation(); }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
                  <h3 style={{ fontSize: "1.2rem", fontWeight: 700 }}>{selectedResource.title}</h3>
                  <button onClick={function() { setSelectedResource(null); }} style={{ background: "none", border: "none", fontSize: "1.5rem", cursor: "pointer", color: "var(--text-secondary)" }}>{String.fromCharCode(10005)}</button>
                </div>

                {selectedResource.content_type === 'study_guide' && selectedResource.content && (
                  <div>
                    {(selectedResource.content.sections || []).map(function(section, si) {
                      return (
                        <div key={si} style={{ marginBottom: "16px" }}>
                          <h4 style={{ fontSize: "0.95rem", fontWeight: 600, color: "var(--text-primary)", marginBottom: "8px" }}>{section.heading}</h4>
                          {section.content && section.content.map(function(point, pi) {
                            return <p key={pi} style={{ fontSize: "0.85rem", marginBottom: "4px", paddingLeft: "12px" }}>{String.fromCharCode(8226)} {point}</p>;
                          })}
                          {section.terms && section.terms.map(function(item, ti) {
                            return <p key={ti} style={{ fontSize: "0.85rem", marginBottom: "4px", paddingLeft: "12px" }}><strong>{item.term}:</strong> {item.definition}</p>;
                          })}
                          {section.questions && section.questions.map(function(qa, qi) {
                            return (
                              <div key={qi} style={{ marginBottom: "8px", paddingLeft: "12px" }}>
                                <p style={{ fontSize: "0.85rem", fontWeight: 600 }}>{qi + 1}. {qa.question}</p>
                                <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", paddingLeft: "16px" }}>Answer: {qa.answer}</p>
                              </div>
                            );
                          })}
                        </div>
                      );
                    })}
                  </div>
                )}

                {selectedResource.content_type === 'flashcards' && selectedResource.content && (
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(250px, 1fr))", gap: "12px" }}>
                    {(selectedResource.content.cards || []).map(function(card, ci) {
                      return (
                        <div key={ci} style={{ padding: "16px", borderRadius: "10px", border: "1px solid var(--border)", background: "var(--input-bg)" }}>
                          <div style={{ fontSize: "0.95rem", fontWeight: 700, marginBottom: "8px" }}>{card.term}</div>
                          <div style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>{card.definition}</div>
                        </div>
                      );
                    })}
                  </div>
                )}

                {selectedResource.content_type === 'slide_deck' && (
                  <div style={{ textAlign: "center", padding: "20px" }}>
                    <p style={{ fontSize: "0.9rem", color: "var(--text-secondary)", marginBottom: "12px" }}>
                      This slide deck contains {(selectedResource.content.slides || []).length} slides.
                    </p>
                    <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>
                      Download the PowerPoint file from your teacher to view the full presentation.
                    </p>
                  </div>
                )}
              </div>
            </div>
          )}
```

- [ ] **Step 4: Build and commit**

```bash
cd /Users/alexc/Downloads/Graider/frontend && npm run build
cd .. && git add frontend/src/components/StudentDashboard.jsx
git commit -m "feat: add Resources section to student dashboard with viewer modal"
```

---

## Summary

| Task | What | Files | Risk |
|------|------|-------|------|
| 1 | Student resources endpoints (list + view) | Modify `student_account_routes.py`, create tests | Low — new endpoints, reuses published_content |
| 2 | "Share with class" buttons on Tools tab | Modify `App.jsx` | Low — adds buttons, uses existing publish-to-class |
| 3 | Resources section in StudentDashboard | Modify `StudentDashboard.jsx` | Low — adds section below assignments |

**Total: 2 new endpoints, 3 "Share with class" buttons, 1 student resources section with viewer modal, 7 Flask test-client tests.**

**How it works end-to-end:**
1. Teacher generates a study guide / flashcards / slide deck in the Planner Tools tab
2. Clicks "Share with Class" → selects a class → resource published to `published_content`
3. Student logs into student portal → sees "Study Materials" section below assignments
4. Clicks a resource → modal opens with rendered content (study guide sections, flashcard grid, slide deck info)
