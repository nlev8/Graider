# OneRoster Grade Passback — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let teachers push graded scores and feedback comments to any OneRoster-compliant SIS with one click from the Results tab.

**Architecture:** Add gradebook methods (`create_line_item`, `create_result`) to the existing `OneRosterClient`, wrap them in a `oneroster_gradebook.py` service that handles lineItem mapping and batch result posting, expose via a new route, and add a "Sync to SIS" button in the existing `ExportGradesDropdown`.

**Tech Stack:** Python/Flask (backend), httpx (async HTTP), React (frontend), OneRoster 1.1/1.2 Gradebook API

**Spec:** `docs/superpowers/specs/2026-04-05-oneroster-grade-passback-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `backend/oneroster.py` | **Modify** | Add `create_line_item()`, `get_line_items()`, `create_result()` to `OneRosterClient` |
| `backend/services/oneroster_gradebook.py` | **Create** | `ensure_line_item()` + `post_results()` orchestration |
| `backend/routes/oneroster_routes.py` | **Modify** | Add `POST /api/oneroster/sync-grades` endpoint |
| `backend/routes/assessment_results_routes.py` | **Modify** | Include `student_id` in submission responses |
| `frontend/src/tabs/ResultsTab.jsx` | **Modify** | Add "Sync to SIS" dropdown item + handler |
| `frontend/src/services/api.js` | **Modify** | Add `syncOneRosterGrades()` function |
| `tests/test_oneroster_gradebook.py` | **Create** | Tests for gradebook service |
| `tests/test_oneroster_sync_grades.py` | **Create** | Tests for sync-grades route |

---

### Task 1: Add gradebook methods to OneRosterClient

**Files:**
- Modify: `backend/oneroster.py:51-82`
- Create: `tests/test_oneroster_gradebook.py`

- [ ] **Step 1: Write failing tests for the new client methods**

Create `tests/test_oneroster_gradebook.py`:

```python
"""Tests for OneRoster gradebook — client methods and service layer."""

import pytest
import httpx
import uuid

from unittest.mock import AsyncMock, patch, MagicMock

from backend.oneroster import OneRosterClient


class TestOneRosterClientGradebook:
    """Tests for create_line_item, get_line_items, create_result on OneRosterClient."""

    def _make_client(self):
        c = OneRosterClient(
            base_url="https://sis.example.com/ims/oneroster/v1p1",
            client_id="test-id",
            client_secret="test-secret",
        )
        c._token = "fake-token"
        c._token_expires = 9999999999
        return c

    @pytest.mark.asyncio
    async def test_create_line_item_sends_post(self):
        client = self._make_client()
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {
            "lineItem": {
                "sourcedId": "li-abc-123",
                "title": "Unit 3 Assessment",
                "assignDate": "2026-04-05",
                "dueDate": "2026-04-05",
                "class": {"sourcedId": "cls-xyz"},
                "resultValueMin": 0.0,
                "resultValueMax": 100.0,
            }
        }

        with patch("httpx.AsyncClient") as MockClient:
            mock_http = AsyncMock()
            mock_http.post.return_value = mock_resp
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_http

            result = await client.create_line_item(
                title="Unit 3 Assessment",
                class_sourced_id="cls-xyz",
                max_score=100.0,
            )

            assert result["sourcedId"] == "li-abc-123"
            mock_http.post.assert_called_once()
            call_args = mock_http.post.call_args
            assert "/lineItems" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_create_result_sends_post(self):
        client = self._make_client()
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {"result": {"sourcedId": "res-001"}}

        with patch("httpx.AsyncClient") as MockClient:
            mock_http = AsyncMock()
            mock_http.post.return_value = mock_resp
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_http

            result = await client.create_result(
                line_item_id="li-abc-123",
                student_sourced_id="stu-001",
                score=85.0,
                max_score=100.0,
                comment="Good work on the essay portion.",
            )

            assert result["sourcedId"] == "res-001"
            mock_http.post.assert_called_once()
            call_args = mock_http.post.call_args
            assert "/lineItems/li-abc-123/results" in call_args[0][0]
            body = call_args[1].get("json") or call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("json")
            assert body["result"]["score"] == 85.0
            assert body["result"]["comment"] == "Good work on the essay portion."

    @pytest.mark.asyncio
    async def test_get_line_items_filters_by_class(self):
        client = self._make_client()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "lineItems": [
                {"sourcedId": "li-1", "title": "Quiz 1"},
                {"sourcedId": "li-2", "title": "Quiz 2"},
            ]
        }

        with patch("httpx.AsyncClient") as MockClient:
            mock_http = AsyncMock()
            mock_http.get.return_value = mock_resp
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_http

            items = await client.get_line_items(class_sourced_id="cls-xyz")

            assert len(items) == 2
            assert items[0]["sourcedId"] == "li-1"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_oneroster_gradebook.py -v`
Expected: FAIL — `OneRosterClient` has no `create_line_item`, `create_result`, or `get_line_items` methods

- [ ] **Step 3: Add `_post_with_retry` method to OneRosterClient**

In `backend/oneroster.py`, add after `_get_with_retry` (after line 82):

```python
    async def _post_with_retry(self, client, url, json_body, label=""):
        """POST with exponential backoff on 429/5xx, token refresh on 401."""
        for attempt in range(MAX_RETRIES):
            await self._ensure_token(client)
            headers = {
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
            }
            resp = await client.post(url, json=json_body, headers=headers)

            if resp.status_code in (200, 201):
                return resp.json()

            if resp.status_code == 401 and attempt < MAX_RETRIES - 1:
                logger.warning("401 on %s, refreshing token (attempt %d)", label or url, attempt + 1)
                self._token = None
                self._token_expires = 0
                continue

            if resp.status_code == 429 or resp.status_code >= 500:
                delay = min(2 ** attempt, 30)
                logger.warning(
                    "%d on %s, retrying in %ds (attempt %d/%d)",
                    resp.status_code, label or url, delay, attempt + 1, MAX_RETRIES,
                )
                await asyncio.sleep(delay)
                continue

            resp.raise_for_status()

        raise httpx.HTTPStatusError(
            f"Max retries exceeded for {label or url}",
            request=resp.request,
            response=resp,
        )
```

- [ ] **Step 4: Add `create_line_item`, `get_line_items`, `create_result` methods**

In `backend/oneroster.py`, add after `fetch_roster` method (before `normalize_roster`):

```python
    async def create_line_item(self, title, class_sourced_id, max_score, due_date=None):
        """Create a lineItem (assignment) in the SIS gradebook.

        Returns the created lineItem dict with sourcedId.
        """
        import uuid as _uuid
        from datetime import date as _date

        sourced_id = str(_uuid.uuid4())
        today = (due_date or _date.today()).isoformat()
        body = {
            "lineItem": {
                "sourcedId": sourced_id,
                "title": title,
                "assignDate": today,
                "dueDate": today,
                "class": {"sourcedId": class_sourced_id, "type": "class"},
                "resultValueMin": 0.0,
                "resultValueMax": float(max_score),
                "category": {"sourcedId": "graider-auto", "title": "Graider"},
            }
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            data = await self._post_with_retry(
                client,
                f"{self.base_url}/lineItems",
                body,
                label="create_line_item",
            )
        return data.get("lineItem", data)

    async def get_line_items(self, class_sourced_id):
        """Fetch lineItems for a class.

        Returns list of lineItem dicts.
        """
        path = f"/lineItems?filter=classSourcedId%3D%27{class_sourced_id}%27"
        async with httpx.AsyncClient(timeout=30.0) as client:
            data = await self._get_with_retry(
                client,
                f"{self.base_url}{path}",
                label="get_line_items",
            )
        return data.get("lineItems", [])

    async def create_result(self, line_item_id, student_sourced_id, score, max_score, comment=""):
        """Post a student result (score + comment) to a lineItem.

        Returns the created result dict.
        """
        import uuid as _uuid
        from datetime import date as _date

        body = {
            "result": {
                "sourcedId": str(_uuid.uuid4()),
                "lineItemSourcedId": line_item_id,
                "studentSourcedId": student_sourced_id,
                "scoreStatus": "fully graded",
                "score": float(score),
                "scoreDate": _date.today().isoformat(),
                "comment": comment or "",
            }
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            data = await self._post_with_retry(
                client,
                f"{self.base_url}/lineItems/{line_item_id}/results",
                body,
                label="create_result",
            )
        return data.get("result", data)
```

- [ ] **Step 5: Run tests**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_oneroster_gradebook.py -v`
Expected: All 3 tests PASS

- [ ] **Step 6: Commit**

```bash
git add backend/oneroster.py tests/test_oneroster_gradebook.py
git commit -m "feat: add OneRoster gradebook methods (lineItems + results)"
```

---

### Task 2: Create the gradebook service

**Files:**
- Create: `backend/services/oneroster_gradebook.py`
- Modify: `tests/test_oneroster_gradebook.py`

- [ ] **Step 1: Write failing tests for the service layer**

Append to `tests/test_oneroster_gradebook.py`:

```python
from backend.services.oneroster_gradebook import ensure_line_item, post_results


class TestEnsureLineItem:
    """Tests for ensure_line_item — create-once-then-update pattern."""

    def test_creates_new_line_item_when_no_mapping(self):
        mock_client = MagicMock()
        mock_client.create_line_item = AsyncMock(return_value={
            "sourcedId": "li-new-001",
            "title": "Unit Test Quiz",
        })

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            ensure_line_item(
                client=mock_client,
                teacher_id="teacher-abc",
                assessment_id="assess-123",
                title="Unit Test Quiz",
                total_points=50.0,
                class_sourced_id="cls-xyz",
            )
        )

        assert result == "li-new-001"
        mock_client.create_line_item.assert_called_once_with(
            title="Unit Test Quiz",
            class_sourced_id="cls-xyz",
            max_score=50.0,
        )

    def test_returns_existing_line_item_from_mapping(self):
        mock_client = MagicMock()

        with patch("backend.services.oneroster_gradebook.load") as mock_load:
            mock_load.return_value = {
                "assess-123": {
                    "line_item_id": "li-existing-999",
                    "class_sourced_id": "cls-xyz",
                }
            }

            import asyncio
            result = asyncio.get_event_loop().run_until_complete(
                ensure_line_item(
                    client=mock_client,
                    teacher_id="teacher-abc",
                    assessment_id="assess-123",
                    title="Unit Test Quiz",
                    total_points=50.0,
                    class_sourced_id="cls-xyz",
                )
            )

            assert result == "li-existing-999"
            mock_client.create_line_item.assert_not_called()


class TestPostResults:
    """Tests for post_results — batch score posting."""

    def test_posts_scores_and_collects_results(self):
        mock_client = MagicMock()
        mock_client.create_result = AsyncMock(return_value={"sourcedId": "res-001"})

        scores = [
            {"student_sourced_id": "stu-001", "score": 85.0, "max_score": 100.0, "comment": "Good work"},
            {"student_sourced_id": "stu-002", "score": 92.0, "max_score": 100.0, "comment": "Excellent"},
        ]

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            post_results(mock_client, "li-abc", scores)
        )

        assert result["synced"] == 2
        assert result["failed"] == 0
        assert result["skipped"] == 0
        assert mock_client.create_result.call_count == 2

    def test_skips_students_without_sourced_id(self):
        mock_client = MagicMock()
        mock_client.create_result = AsyncMock(return_value={"sourcedId": "res-001"})

        scores = [
            {"student_sourced_id": "stu-001", "score": 85.0, "max_score": 100.0, "comment": ""},
            {"student_sourced_id": "", "score": 70.0, "max_score": 100.0, "comment": ""},
            {"student_sourced_id": None, "score": 60.0, "max_score": 100.0, "comment": ""},
        ]

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            post_results(mock_client, "li-abc", scores)
        )

        assert result["synced"] == 1
        assert result["skipped"] == 2
        assert mock_client.create_result.call_count == 1

    def test_collects_errors_without_stopping(self):
        mock_client = MagicMock()
        mock_client.create_result = AsyncMock(
            side_effect=[
                {"sourcedId": "res-001"},
                Exception("SIS rejected score"),
                {"sourcedId": "res-003"},
            ]
        )

        scores = [
            {"student_sourced_id": "stu-001", "score": 85.0, "max_score": 100.0, "comment": ""},
            {"student_sourced_id": "stu-002", "score": 92.0, "max_score": 100.0, "comment": ""},
            {"student_sourced_id": "stu-003", "score": 78.0, "max_score": 100.0, "comment": ""},
        ]

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            post_results(mock_client, "li-abc", scores)
        )

        assert result["synced"] == 2
        assert result["failed"] == 1
        assert len(result["errors"]) == 1
        assert "stu-002" in result["errors"][0]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_oneroster_gradebook.py::TestEnsureLineItem -v`
Expected: FAIL — module `backend.services.oneroster_gradebook` does not exist

- [ ] **Step 3: Create the gradebook service**

Create `backend/services/oneroster_gradebook.py`:

```python
"""OneRoster Gradebook service — lineItem management and result posting.

Handles the create-once-then-update pattern for pushing scores to any
OneRoster-compliant SIS gradebook.
"""

import logging
from datetime import datetime, timezone

from backend.storage import load, save

logger = logging.getLogger(__name__)

MAPPING_KEY = "oneroster_line_items"


async def ensure_line_item(client, teacher_id, assessment_id, title, total_points, class_sourced_id):
    """Get or create a lineItem in the SIS for this assessment.

    Checks stored mapping first. If no mapping exists, creates the lineItem
    via OneRoster API and stores the mapping for future syncs.

    Returns the lineItem sourcedId (str).
    """
    mappings = load(MAPPING_KEY, teacher_id) or {}

    existing = mappings.get(assessment_id)
    if existing and existing.get("line_item_id"):
        logger.info("Reusing existing lineItem %s for assessment %s", existing["line_item_id"], assessment_id)
        return existing["line_item_id"]

    logger.info("Creating new lineItem for assessment %s in class %s", assessment_id, class_sourced_id)
    line_item = await client.create_line_item(
        title=title,
        class_sourced_id=class_sourced_id,
        max_score=total_points,
    )

    line_item_id = line_item.get("sourcedId", line_item.get("id", ""))
    mappings[assessment_id] = {
        "line_item_id": line_item_id,
        "class_sourced_id": class_sourced_id,
        "title": title,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    save(MAPPING_KEY, mappings, teacher_id)

    return line_item_id


async def post_results(client, line_item_id, scores):
    """Post student scores to a lineItem.

    Args:
        client: OneRosterClient instance
        line_item_id: sourcedId of the lineItem to post scores to
        scores: list of dicts with keys:
            - student_sourced_id (str): OneRoster sourcedId of the student
            - score (float): points earned
            - max_score (float): maximum possible points
            - comment (str): feedback text

    Returns dict with keys: synced, skipped, failed, errors
    """
    synced = 0
    skipped = 0
    failed = 0
    errors = []

    for entry in scores:
        sid = entry.get("student_sourced_id")
        if not sid:
            skipped += 1
            continue

        try:
            await client.create_result(
                line_item_id=line_item_id,
                student_sourced_id=sid,
                score=entry["score"],
                max_score=entry["max_score"],
                comment=entry.get("comment", ""),
            )
            synced += 1
        except Exception as e:
            failed += 1
            errors.append(f"Student {sid}: {str(e)}")
            logger.warning("Failed to post result for student %s: %s", sid, e)

    return {"synced": synced, "skipped": skipped, "failed": failed, "errors": errors}
```

- [ ] **Step 4: Run tests**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_oneroster_gradebook.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/services/oneroster_gradebook.py tests/test_oneroster_gradebook.py
git commit -m "feat: OneRoster gradebook service (ensure_line_item + post_results)"
```

---

### Task 3: Add the sync-grades route

**Files:**
- Modify: `backend/routes/oneroster_routes.py:298+`
- Create: `tests/test_oneroster_sync_grades.py`

- [ ] **Step 1: Write failing tests for the route**

Create `tests/test_oneroster_sync_grades.py`:

```python
"""Tests for POST /api/oneroster/sync-grades route."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock


@pytest.fixture
def client():
    from backend.app import app
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c


@pytest.fixture
def auth_headers():
    return {"Content-Type": "application/json", "Authorization": "Bearer test-token"}


class TestSyncGradesRoute:

    @patch("backend.routes.oneroster_routes.get_oneroster_config")
    def test_returns_error_when_oneroster_not_configured(self, mock_config, client, auth_headers):
        mock_config.return_value = None

        with patch("backend.routes.oneroster_routes.g") as mock_g:
            mock_g.teacher_id = "teacher-abc"
            resp = client.post("/api/oneroster/sync-grades", json={
                "assessment_id": "assess-123",
                "title": "Quiz 1",
                "total_points": 100,
                "class_sourced_id": "cls-xyz",
                "scores": [],
            }, headers=auth_headers)

        data = resp.get_json()
        assert "not configured" in data.get("error", "").lower() or resp.status_code in (400, 401, 500)

    @patch("backend.routes.oneroster_routes.post_results")
    @patch("backend.routes.oneroster_routes.ensure_line_item")
    @patch("backend.routes.oneroster_routes.get_oneroster_config")
    def test_returns_sync_counts_on_success(self, mock_config, mock_ensure, mock_post, client, auth_headers):
        mock_config.return_value = {
            "base_url": "https://sis.example.com/ims/oneroster/v1p1",
            "client_id": "test-id",
            "client_secret": "test-secret",
        }
        mock_ensure.return_value = "li-abc-123"
        mock_post.return_value = {"synced": 3, "skipped": 1, "failed": 0, "errors": []}

        with patch("backend.routes.oneroster_routes.g") as mock_g:
            mock_g.teacher_id = "teacher-abc"
            resp = client.post("/api/oneroster/sync-grades", json={
                "assessment_id": "assess-123",
                "title": "Quiz 1",
                "total_points": 100,
                "class_sourced_id": "cls-xyz",
                "scores": [
                    {"student_sourced_id": "stu-1", "score": 90, "max_score": 100, "comment": "Great"},
                ],
            }, headers=auth_headers)

        data = resp.get_json()
        assert data.get("synced") == 3
        assert data.get("skipped") == 1

    @patch("backend.routes.oneroster_routes.get_oneroster_config")
    def test_returns_error_when_missing_required_fields(self, mock_config, client, auth_headers):
        mock_config.return_value = {
            "base_url": "https://sis.example.com",
            "client_id": "test-id",
            "client_secret": "test-secret",
        }

        with patch("backend.routes.oneroster_routes.g") as mock_g:
            mock_g.teacher_id = "teacher-abc"
            resp = client.post("/api/oneroster/sync-grades", json={
                "scores": [],
            }, headers=auth_headers)

        data = resp.get_json()
        assert "error" in data or resp.status_code == 400
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_oneroster_sync_grades.py -v`
Expected: FAIL — route does not exist

- [ ] **Step 3: Add the sync-grades endpoint**

In `backend/routes/oneroster_routes.py`, add these imports at the top (after line 13):

```python
from backend.services.oneroster_gradebook import ensure_line_item, post_results
```

Then add the endpoint at the end of the file (after the `delete_data` route):

```python
# ── POST /api/oneroster/sync-grades ───────────────────────────────────────

@oneroster_bp.route("/api/oneroster/sync-grades", methods=["POST"])
@require_teacher
@handle_route_errors
def sync_grades():
    """Push graded scores + comments to SIS via OneRoster Gradebook API."""
    teacher_id = g.teacher_id
    cfg = get_oneroster_config(teacher_id)
    if not cfg or not cfg.get("base_url"):
        return jsonify({"error": "OneRoster not configured. Set up SIS connection in District Portal first."}), 400

    data = request.json or {}
    assessment_id = data.get("assessment_id")
    title = data.get("title")
    total_points = data.get("total_points")
    class_sourced_id = data.get("class_sourced_id")
    scores = data.get("scores", [])

    if not assessment_id or not title or not total_points or not class_sourced_id:
        return jsonify({"error": "Missing required fields: assessment_id, title, total_points, class_sourced_id"}), 400

    if not scores:
        return jsonify({"error": "No scores to sync"}), 400

    client = OneRosterClient(
        base_url=cfg["base_url"],
        client_id=cfg["client_id"],
        client_secret=cfg["client_secret"],
        token_url=cfg.get("token_url"),
    )

    try:
        line_item_id = _run_async(ensure_line_item(
            client=client,
            teacher_id=teacher_id,
            assessment_id=assessment_id,
            title=title,
            total_points=float(total_points),
            class_sourced_id=class_sourced_id,
        ))
    except Exception as e:
        logger.error("Failed to create/find lineItem: %s", e)
        return jsonify({"error": f"Failed to create assignment in SIS: {str(e)}"}), 500

    try:
        result = _run_async(post_results(client, line_item_id, scores))
    except Exception as e:
        logger.error("Failed to post results: %s", e)
        return jsonify({"error": f"Failed to post scores: {str(e)}"}), 500

    return jsonify({
        "status": "success",
        "line_item_id": line_item_id,
        "synced": result["synced"],
        "skipped": result["skipped"],
        "failed": result["failed"],
        "errors": result["errors"],
    })
```

- [ ] **Step 4: Run tests**

Run: `cd /Users/alexc/Downloads/Graider && source venv/bin/activate && python -m pytest tests/test_oneroster_sync_grades.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/routes/oneroster_routes.py tests/test_oneroster_sync_grades.py
git commit -m "feat: add POST /api/oneroster/sync-grades endpoint"
```

---

### Task 4: Include student_id in assessment results response

**Files:**
- Modify: `backend/routes/assessment_results_routes.py:216-227,280-289`

- [ ] **Step 1: Add student_id to join-code submission responses**

In `backend/routes/assessment_results_routes.py`, find the submissions list comprehension for join-code assessments (around line 216):

Change:
```python
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
```

To:
```python
                'submissions': [
                    {
                        'student_name': s.get('student_name', 'Anonymous'),
                        'student_id': s.get('student_id', ''),
                        'student_id_number': s.get('student_id_number', ''),
                        'score': s.get('score'),
                        'percentage': s.get('percentage'),
                        'letter_grade': _compute_letter_grade(s.get('percentage')),
                        'time_taken_seconds': s.get('time_taken_seconds'),
                        'submitted_at': s.get('submitted_at'),
                        'status': 'pending' if s.get('score') is None else 'graded',
                    }
                    for s in subs
                ],
```

- [ ] **Step 2: Add student_id to class-based submission responses**

Find the class-based submissions list comprehension (around line 280):

Change:
```python
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
```

To:
```python
                'submissions': [
                    {
                        'student_name': s.get('student_name', 'Anonymous'),
                        'student_id': s.get('student_id', ''),
                        'student_id_number': s.get('student_id_number', ''),
                        'score': s.get('score'),
                        'percentage': s.get('percentage'),
                        'letter_grade': _compute_letter_grade(s.get('percentage')),
                        'time_taken_seconds': s.get('time_taken_seconds'),
                        'submitted_at': s.get('submitted_at'),
                        'status': s.get('status', 'submitted'),
                    }
```

- [ ] **Step 3: Look up student_id_number for class-based submissions**

Class-based submissions (`student_submissions` table) have `student_id` but not `student_id_number`. We need to join with the `students` table. Find the Supabase query at line 243:

Change:
```python
            subs_result = db.table('student_submissions').select('*').eq('content_id', content_id).order('submitted_at', desc=True).execute()
```

To:
```python
            subs_result = db.table('student_submissions').select('*, students(student_id_number)').eq('content_id', content_id).order('submitted_at', desc=True).execute()
```

Then update the class-based submission dict to extract the nested student_id_number:

```python
                        'student_id_number': (s.get('students') or {}).get('student_id_number', '') if isinstance(s.get('students'), dict) else s.get('student_id_number', ''),
```

- [ ] **Step 4: Commit**

```bash
git add backend/routes/assessment_results_routes.py
git commit -m "feat: include student_id in assessment results for grade sync"
```

---

### Task 5: Frontend — add "Sync to SIS" to ExportGradesDropdown

**Files:**
- Modify: `frontend/src/services/api.js:366+`
- Modify: `frontend/src/tabs/ResultsTab.jsx:97-220`

- [ ] **Step 1: Add the API function**

In `frontend/src/services/api.js`, add after the `exportLmsCsv` function (search for `exportLmsCsv` to find the right location):

```javascript
export async function syncOneRosterGrades(data) {
  track('grades_synced', { type: 'oneroster', score_count: data.scores ? data.scores.length : 0 })
  return fetchApi('/api/oneroster/sync-grades', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}
```

Also add `syncOneRosterGrades` to the default export object at the bottom of the file.

- [ ] **Step 2: Add the handler and dropdown item to ExportGradesDropdown**

In `frontend/src/tabs/ResultsTab.jsx`, inside the `ExportGradesDropdown` function, add a new state and handler after `handleLmsExport` (around line 182):

```javascript
  var _sisLoading = useState(false)
  var sisLoading = _sisLoading[0]
  var setSisLoading = _sisLoading[1]

  async function handleOneRosterSync() {
    setOpen(false)
    setSisLoading(true)
    try {
      var resultsToSync = getFilteredResults()
      var assignment = getAssignment()
      var scores = resultsToSync.map(function(r) {
        var sid = r.student_id_number || ''
        if (sid.startsWith('oneroster:')) {
          sid = sid.substring('oneroster:'.length)
        } else {
          sid = ''
        }
        return {
          student_sourced_id: sid,
          score: r.score || 0,
          max_score: r.total_points || 100,
          comment: r.feedback_summary || r.feedback || '',
        }
      })
      var res = await api.syncOneRosterGrades({
        assessment_id: resultsAssignmentFilter || assignment,
        title: assignment,
        total_points: (resultsToSync[0] && resultsToSync[0].total_points) || 100,
        class_sourced_id: (resultsToSync[0] && resultsToSync[0].class_sourced_id) || '',
        scores: scores,
      })
      if (res.error) {
        addToast(res.error, "error")
      } else {
        var msg = "Synced " + res.synced + " grade" + (res.synced !== 1 ? "s" : "") + " to SIS"
        if (res.skipped > 0) msg += ", " + res.skipped + " skipped (no SIS match)"
        if (res.failed > 0) msg += ", " + res.failed + " failed"
        addToast(msg, res.failed > 0 ? "warning" : "success")
      }
    } catch (err) {
      addToast("SIS sync error: " + err.message, "error")
    } finally {
      setSisLoading(false)
    }
  }
```

Update the `loading` variable to include `sisLoading`:

```javascript
  var loading = batchExportLoading || lmsLoading || sisLoading
```

Then add the dropdown item in the JSX, after the Focus items and before the Canvas item (around line 215):

```javascript
          {(config || {}).sis_type === 'oneroster' && (<>
          <DropdownItem onClick={handleOneRosterSync} icon="RefreshCw" label="Sync to SIS" />
          <div style={{ height: "1px", background: "var(--glass-border)", margin: "2px 0" }} />
          </>)}
```

- [ ] **Step 3: Build and test**

```bash
cd /Users/alexc/Downloads/Graider/frontend && npm run build
```

Expected: Build succeeds with no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/services/api.js frontend/src/tabs/ResultsTab.jsx backend/static/
git commit -m "feat: add Sync to SIS button in Export Grades dropdown (OneRoster)"
```

---

### Task 6: Wire up assessment results "Sync to SIS" button

**Files:**
- Modify: `frontend/src/tabs/ResultsTab.jsx`

The Export Grades dropdown from Task 5 covers file-based grading results. Assessment results (portal submissions) are displayed in a separate section of the Results tab. We need a "Sync to SIS" button there too.

- [ ] **Step 1: Find the assessment results action area**

In `frontend/src/tabs/ResultsTab.jsx`, find where individual assessment result cards are rendered (the section with assessment stats, around where `filteredAssessments.map` is called). Look for existing action buttons on each assessment card.

- [ ] **Step 2: Add a Sync to SIS button on each assessment card**

Add a "Sync to SIS" button next to existing assessment actions, gated on `(config || {}).sis_type === 'oneroster'`. The handler should:

1. Collect submissions from the assessment's `submissions` array
2. Map each to `{student_sourced_id, score, max_score, comment}` — extracting the OneRoster sourcedId from `student_id_number` (strip `oneroster:` prefix)
3. Call `api.syncOneRosterGrades()` with the assessment's `id` as `assessment_id`, `title`, `stats.total_points`, and the mapped scores
4. Show a toast with results

```javascript
{(config || {}).sis_type === 'oneroster' && (
  <button
    onClick={async function() {
      try {
        var scores = (assessment.submissions || []).map(function(s) {
          var sid = s.student_id_number || ''
          if (sid.startsWith('oneroster:')) sid = sid.substring('oneroster:'.length)
          else sid = ''
          return {
            student_sourced_id: sid,
            score: s.score || 0,
            max_score: s.total_points || assessment.stats.total_points || 100,
            comment: s.feedback_summary || '',
          }
        })
        var res = await api.syncOneRosterGrades({
          assessment_id: assessment.id,
          title: assessment.title,
          total_points: assessment.stats.total_points || 100,
          class_sourced_id: assessment.class_sourced_id || '',
          scores: scores,
        })
        if (res.error) {
          addToast(res.error, "error")
        } else {
          var msg = "Synced " + res.synced + " grade" + (res.synced !== 1 ? "s" : "") + " to SIS"
          if (res.skipped > 0) msg += ", " + res.skipped + " skipped"
          addToast(msg, res.failed > 0 ? "warning" : "success")
        }
      } catch (err) {
        addToast("SIS sync error: " + err.message, "error")
      }
    }}
    className="btn btn-secondary"
    style={{ padding: "4px 10px", fontSize: "0.78rem" }}
    title="Push grades and comments to SIS gradebook"
  >
    <Icon name="RefreshCw" size={14} /> Sync to SIS
  </button>
)}
```

- [ ] **Step 3: Build and test**

```bash
cd /Users/alexc/Downloads/Graider/frontend && npm run build
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/tabs/ResultsTab.jsx backend/static/
git commit -m "feat: add Sync to SIS button on assessment result cards"
```

---

## Summary

| Task | What | Files | Risk |
|------|------|-------|------|
| 1 | OneRoster client gradebook methods | `oneroster.py`, tests | Low — additive, no existing code changed |
| 2 | Gradebook service (ensure_line_item + post_results) | New `oneroster_gradebook.py`, tests | Low — new file, well-isolated |
| 3 | POST /api/oneroster/sync-grades route | `oneroster_routes.py`, tests | Low — additive endpoint |
| 4 | Include student_id in assessment results | `assessment_results_routes.py` | Low — additive fields |
| 5 | Frontend: Sync to SIS in Export Grades dropdown | `ResultsTab.jsx`, `api.js` | Medium — UI change |
| 6 | Frontend: Sync to SIS on assessment cards | `ResultsTab.jsx` | Medium — UI change |

**Total: 3 backend files modified, 2 new files created, 10 tests, 2 UI additions.**

**Before:** Teacher exports CSV, manually imports into SIS gradebook.
**After:** Teacher clicks "Sync to SIS" — scores and feedback comments land in the SIS gradebook via OneRoster API.
