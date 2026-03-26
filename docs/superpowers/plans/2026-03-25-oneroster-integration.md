# OneRoster 1.1/1.2 REST API Integration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add OneRoster 1.1/1.2 REST API support as an alternative roster sync provider to Clever. Districts that use 1EdTech standards (e.g., Volusia County) can sync classes, students, enrollments, and demographics (IEP/ELL) from their SIS via OneRoster without requiring Clever.

**Architecture:** New `backend/oneroster.py` client module (mirrors `clever.py` structure). New `backend/routes/oneroster_routes.py` for configuration, sync, and session endpoints. Generalize `_sync_classes_to_db()` into a shared `backend/roster_sync.py` module used by both Clever and OneRoster. Add OneRoster configuration UI to Settings tab.

**Tech Stack:** Flask/Python backend, `httpx` for HTTP client (matches Clever), OAuth 2.0 client_credentials flow, Supabase for persistence, React frontend (inline styles).

**Spec:** Based on [OneRoster 1.1 Final Specification](https://www.imsglobal.org/oneroster-v11-final-specification) — REST Rostering + Demographics endpoints.

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `backend/oneroster.py` | CREATE | OneRoster REST API client — OAuth token management, roster fetch, data extraction |
| `backend/routes/oneroster_routes.py` | CREATE | `/api/oneroster/*` endpoints — config, sync, session, delete |
| `backend/roster_sync.py` | CREATE | Shared DB sync logic extracted from `clever_routes.py:_sync_classes_to_db()` |
| `backend/routes/clever_routes.py` | MODIFY | Replace `_sync_classes_to_db()` with import from `roster_sync.py` |
| `backend/auth.py` | MODIFY | Add OneRoster session support to `check_auth()` and public routes |
| `backend/routes/__init__.py` | MODIFY | Register `oneroster_bp` blueprint |
| `frontend/src/tabs/SettingsTab.jsx` | MODIFY | Add OneRoster configuration panel |
| `frontend/src/services/api.js` | MODIFY | Add OneRoster API functions |
| `tests/test_oneroster.py` | CREATE | Unit tests for OneRoster client |
| `tests/test_roster_sync.py` | CREATE | Unit tests for shared sync logic |

---

## Task 1: Extract Shared Roster Sync Logic

**Why first:** Both Clever and OneRoster need the same DB sync pipeline. Extract it before adding a second consumer.

**Files:**
- Create: `backend/roster_sync.py`
- Modify: `backend/routes/clever_routes.py`

- [ ] **Step 1: Create `backend/roster_sync.py`**

Extract the DB sync logic from `clever_routes.py` lines 85-246 into a provider-agnostic module. The function accepts normalized data (not Clever-specific format).

```python
"""
Provider-agnostic roster sync to Supabase.
Shared by Clever, OneRoster, and CSV import paths.
"""
import logging

logger = logging.getLogger(__name__)


def sync_roster_to_db(classes, students, enrollments, teacher_id, provider="manual"):
    """Upsert classes, students, and enrollments into Supabase.

    Args:
        classes: List of dicts with keys:
            - external_id (str): Provider-specific section/class ID
            - name (str): Class display name
            - subject (str): Subject area
            - grade_level (str): Grade level
        students: List of dicts with keys:
            - external_id (str): Provider-specific student ID
            - first_name (str)
            - last_name (str)
            - email (str, optional)
        enrollments: List of tuples (class_external_id, student_external_id)
        teacher_id: Graider teacher ID
        provider: Source identifier ("clever", "oneroster", "csv")

    Returns:
        dict with counts: {"classes": int, "students": int, "enrollments": int}
    """
    from backend.supabase_client import get_supabase as _get_supabase
    sb = _get_supabase()
    if sb is None:
        logger.debug("Supabase not configured — skipping roster DB sync")
        return {"classes": 0, "students": 0, "enrollments": 0}

    # --- Phase 1: Batch upsert classes ---
    class_payloads = []
    for cls in classes:
        class_payloads.append({
            "teacher_id": teacher_id,
            "name": cls["name"],
            "subject": cls.get("subject", ""),
            "grade_level": cls.get("grade_level", ""),
            "clever_section_id": cls["external_id"],  # Reuse existing column
            "is_active": True,
        })

    if not class_payloads:
        logger.info("Roster DB sync (%s): 0 classes, 0 students, 0 enrollments", provider)
        return {"classes": 0, "students": 0, "enrollments": 0}

    try:
        class_result = (
            sb.table("classes")
            .upsert(class_payloads, on_conflict="teacher_id,clever_section_id")
            .execute()
        )
    except Exception as e:
        logger.warning("Failed to batch-upsert classes (%s): %s", provider, str(e))
        return {"classes": 0, "students": 0, "enrollments": 0}

    class_rows = class_result.data if class_result and class_result.data else []
    if not class_rows:
        logger.warning("No class rows returned from batch upsert (%s)", provider)
        return {"classes": 0, "students": 0, "enrollments": 0}

    # Build external_id -> DB UUID map
    class_id_map = {}
    for row in class_rows:
        ext_id = row.get("clever_section_id", "")
        if ext_id and row.get("id"):
            class_id_map[ext_id] = row["id"]

    # --- Phase 2: Batch upsert students ---
    unique_students = {}
    for ext_id in set(s["external_id"] for s in students):
        stu = next(s for s in students if s["external_id"] == ext_id)
        unique_students[ext_id] = {
            "teacher_id": teacher_id,
            "student_id_number": ext_id,
            "first_name": stu.get("first_name", ""),
            "last_name": stu.get("last_name", ""),
            "email": stu.get("email", ""),
            "is_active": True,
        }

    if not unique_students:
        logger.info("Roster DB sync (%s): %d classes, 0 students, 0 enrollments", provider, len(class_id_map))
        return {"classes": len(class_id_map), "students": 0, "enrollments": 0}

    try:
        stu_result = (
            sb.table("students")
            .upsert(list(unique_students.values()), on_conflict="teacher_id,student_id_number")
            .execute()
        )
    except Exception as e:
        logger.warning("Failed to batch-upsert students (%s): %s", provider, str(e))
        return {"classes": len(class_id_map), "students": 0, "enrollments": 0}

    stu_rows = stu_result.data if stu_result and stu_result.data else []
    student_id_map = {}
    for row in stu_rows:
        sid = row.get("student_id_number", "")
        if sid and row.get("id"):
            student_id_map[sid] = row["id"]

    # --- Phase 3: Batch upsert enrollments ---
    enrollment_payloads = []
    for class_ext_id, student_ext_id in enrollments:
        class_db_id = class_id_map.get(class_ext_id)
        student_db_id = student_id_map.get(student_ext_id)
        if class_db_id and student_db_id:
            enrollment_payloads.append({"class_id": class_db_id, "student_id": student_db_id})

    synced_enrollments = 0
    if enrollment_payloads:
        try:
            sb.table("class_students").upsert(
                enrollment_payloads, on_conflict="class_id,student_id"
            ).execute()
            synced_enrollments = len(enrollment_payloads)
        except Exception as e:
            logger.warning("Failed to batch-upsert enrollments (%s): %s", provider, str(e))

    logger.info(
        "Roster DB sync (%s): %d classes, %d students, %d enrollments",
        provider, len(class_id_map), len(student_id_map), synced_enrollments,
    )
    return {
        "classes": len(class_id_map),
        "students": len(student_id_map),
        "enrollments": synced_enrollments,
    }
```

- [ ] **Step 2: Update `clever_routes.py` to use shared sync**

In `backend/routes/clever_routes.py`, replace the `_sync_classes_to_db()` function (lines 85-246) with a wrapper that normalizes Clever data and delegates to `roster_sync.sync_roster_to_db()`:

```python
# ADD at top of file (after existing imports, ~line 30):
from backend.roster_sync import sync_roster_to_db as _shared_sync_roster_to_db
```

Replace the entire `_sync_classes_to_db` function (lines 85-246) with:

```python
def _sync_classes_to_db(sections, students, teacher_id):
    """Normalize Clever data and delegate to shared roster sync.

    Adapts Clever's {data: {...}} wrapper format to the provider-agnostic
    format expected by roster_sync.sync_roster_to_db().
    """
    # Build student lookup
    student_map = {}
    for s in students:
        sd = s.get("data", s)
        sid = sd.get("id")
        if sid:
            student_map[sid] = sd

    # Normalize classes
    normalized_classes = []
    enrollment_pairs = []
    for section in sections:
        sec = section.get("data", section)
        clever_section_id = sec.get("id")
        if not clever_section_id:
            continue
        normalized_classes.append({
            "external_id": clever_section_id,
            "name": sec.get("name", ""),
            "subject": sec.get("subject", ""),
            "grade_level": sec.get("grade", ""),
        })
        for clever_student_id in sec.get("students", []):
            if clever_student_id in student_map:
                enrollment_pairs.append((clever_section_id, clever_student_id))

    # Normalize students
    normalized_students = []
    seen = set()
    for clever_id, sd in student_map.items():
        if clever_id not in seen:
            seen.add(clever_id)
            name = sd.get("name", {})
            normalized_students.append({
                "external_id": clever_id,
                "first_name": name.get("first", ""),
                "last_name": name.get("last", ""),
                "email": sd.get("email", ""),
            })

    _shared_sync_roster_to_db(
        normalized_classes, normalized_students, enrollment_pairs,
        teacher_id, provider="clever",
    )
```

---

## Task 2: OneRoster REST API Client

**Files:**
- Create: `backend/oneroster.py`
- Create: `tests/test_oneroster.py`

- [ ] **Step 1: Create `backend/oneroster.py`**

```python
"""
OneRoster 1.1/1.2 REST API client for Graider.
Handles OAuth 2.0 client_credentials authentication and roster data fetching.
Mirrors clever.py structure for consistency.
"""
import logging
import os
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

import httpx

logger = logging.getLogger(__name__)

MAX_RETRIES = 5
DEFAULT_PAGE_LIMIT = 100


class OneRosterClient:
    """OneRoster REST API client with OAuth 2.0 token management."""

    def __init__(self, base_url, client_id, client_secret, token_url=None):
        """
        Args:
            base_url: OneRoster API root (e.g., "https://sis.district.org/ims/oneroster/v1p1")
            client_id: OAuth 2.0 client ID
            client_secret: OAuth 2.0 client secret
            token_url: OAuth token endpoint (defaults to base_url + "/token")
        """
        self.base_url = base_url.rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_url = token_url or (self.base_url + "/token")
        self._access_token = None
        self._token_expires_at = None

    async def _ensure_token(self, client):
        """Obtain or refresh OAuth 2.0 bearer token via client_credentials grant."""
        if self._access_token and self._token_expires_at and datetime.now(timezone.utc) < self._token_expires_at:
            return

        resp = await client.post(
            self.token_url,
            data={"grant_type": "client_credentials"},
            auth=(self.client_id, self.client_secret),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp.raise_for_status()
        body = resp.json()
        self._access_token = body["access_token"]
        expires_in = body.get("expires_in", 3600)
        self._token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in - 60)
        logger.info("OneRoster OAuth token acquired, expires in %ds", expires_in)

    async def _get_with_retry(self, client, url, label=""):
        """GET with exponential backoff on 429/5xx (matches clever.py pattern)."""
        for attempt in range(MAX_RETRIES):
            await self._ensure_token(client)
            resp = await client.get(
                url,
                headers={"Authorization": f"Bearer {self._access_token}"},
            )
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code in (429, 500, 502, 503, 504):
                delay = 2 ** attempt
                logger.warning("OneRoster %s returned %d, retry %d/%d in %ds",
                               label, resp.status_code, attempt + 1, MAX_RETRIES, delay)
                import asyncio
                await asyncio.sleep(delay)
                continue
            if resp.status_code == 401:
                # Token expired mid-session — force refresh
                self._access_token = None
                continue
            # 4xx (not 401/429) — fail fast
            logger.error("OneRoster %s returned %d: %s", label, resp.status_code, resp.text[:500])
            return None
        logger.error("OneRoster %s: max retries exceeded", label)
        return None

    async def _get_paginated(self, client, path, resource_key, label=""):
        """Fetch all pages of a collection endpoint.

        Args:
            path: API path relative to base_url (e.g., "/classes")
            resource_key: JSON key containing the array (e.g., "classes")
            label: Logging label
        Returns:
            List of all resource objects across pages
        """
        all_items = []
        offset = 0
        while True:
            sep = "&" if "?" in path else "?"
            url = f"{self.base_url}{path}{sep}limit={DEFAULT_PAGE_LIMIT}&offset={offset}"
            body = await self._get_with_retry(client, url, label)
            if body is None:
                break
            items = body.get(resource_key, [])
            if not items:
                break
            all_items.extend(items)
            if len(items) < DEFAULT_PAGE_LIMIT:
                break
            offset += DEFAULT_PAGE_LIMIT
        logger.info("OneRoster fetched %d %s", len(all_items), label)
        return all_items

    async def fetch_roster(self, school_id=None):
        """Fetch classes, students, teachers, and enrollments.

        Args:
            school_id: Optional school sourcedId to scope the fetch

        Returns:
            dict with keys: classes, students, teachers, enrollments, demographics
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            if school_id:
                classes = await self._get_paginated(
                    client, f"/schools/{school_id}/classes", "classes", "classes")
                students = await self._get_paginated(
                    client, f"/schools/{school_id}/students", "users", "students")
                teachers = await self._get_paginated(
                    client, f"/schools/{school_id}/teachers", "users", "teachers")
                enrollments = await self._get_paginated(
                    client, f"/schools/{school_id}/enrollments", "enrollments", "enrollments")
            else:
                classes = await self._get_paginated(client, "/classes", "classes", "classes")
                students = await self._get_paginated(client, "/students", "users", "students")
                teachers = await self._get_paginated(client, "/teachers", "users", "teachers")
                enrollments = await self._get_paginated(client, "/enrollments", "enrollments", "enrollments")

            # Demographics (optional — may require roster-demographics.readonly scope)
            demographics = []
            try:
                demographics = await self._get_paginated(
                    client, "/demographics", "demographics", "demographics")
            except Exception:
                logger.info("OneRoster demographics not available (may require additional scope)")

            return {
                "classes": classes,
                "students": students,
                "teachers": teachers,
                "enrollments": enrollments,
                "demographics": demographics,
            }


def normalize_roster(raw):
    """Convert raw OneRoster API data to Graider's normalized format.

    Args:
        raw: dict from OneRosterClient.fetch_roster()

    Returns:
        tuple: (classes, students, enrollments, accommodations)
        - classes: list of {external_id, name, subject, grade_level}
        - students: list of {external_id, first_name, last_name, email}
        - enrollments: list of (class_external_id, student_external_id)
        - accommodations: dict of {external_id: {name, iep_status, ell_status, home_language, suggested_presets}}
    """
    # Normalize classes
    classes = []
    for cls in raw.get("classes", []):
        if cls.get("status") == "tobedeleted":
            continue
        classes.append({
            "external_id": cls["sourcedId"],
            "name": cls.get("title", ""),
            "subject": (cls.get("subjects") or [""])[0],
            "grade_level": (cls.get("grades") or [""])[0],
        })

    # Normalize students
    students = []
    student_ids = set()
    for user in raw.get("students", []):
        if user.get("status") == "tobedeleted":
            continue
        if user.get("role") not in ("student", None):
            continue
        sid = user["sourcedId"]
        if sid in student_ids:
            continue
        student_ids.add(sid)
        students.append({
            "external_id": sid,
            "first_name": user.get("givenName", ""),
            "last_name": user.get("familyName", ""),
            "email": user.get("email", ""),
        })

    # Normalize enrollments (student role only)
    enrollments = []
    for enr in raw.get("enrollments", []):
        if enr.get("status") == "tobedeleted":
            continue
        if enr.get("role") != "student":
            continue
        class_id = enr.get("class", {}) if isinstance(enr.get("class"), dict) else enr.get("class")
        user_id = enr.get("user", {}) if isinstance(enr.get("user"), dict) else enr.get("user")
        # Handle both sourcedId reference styles
        if isinstance(class_id, dict):
            class_id = class_id.get("sourcedId", "")
        if isinstance(user_id, dict):
            user_id = user_id.get("sourcedId", "")
        if class_id and user_id and user_id in student_ids:
            enrollments.append((class_id, user_id))

    # Extract accommodations from demographics
    accommodations = {}
    demo_map = {d["sourcedId"]: d for d in raw.get("demographics", []) if d.get("sourcedId")}
    for stu in students:
        demo = demo_map.get(stu["external_id"])
        if not demo:
            continue
        metadata = demo.get("metadata", {})
        iep_status = str(metadata.get("iep_status", "")).lower() in ("y", "yes", "true", "active")
        ell_status = str(metadata.get("ell_status", "")).lower() in ("y", "yes", "true", "active")
        home_language = metadata.get("home_language", "")

        if iep_status or ell_status:
            suggested = []
            if iep_status:
                suggested.extend(["simplified_language", "effort_focused", "modified_expectations"])
            if ell_status:
                suggested.append("ell_support")
            accommodations[stu["external_id"]] = {
                "name": f"{stu['first_name']} {stu['last_name']}",
                "iep_status": iep_status,
                "ell_status": ell_status,
                "home_language": home_language,
                "suggested_presets": suggested,
            }

    return classes, students, enrollments, accommodations


def get_oneroster_config(teacher_id=None):
    """Load OneRoster configuration from storage or environment.

    Resolution order:
    1. Per-teacher config (from Supabase teacher_data)
    2. Environment variables (ONEROSTER_BASE_URL, ONEROSTER_CLIENT_ID, ONEROSTER_CLIENT_SECRET)

    Returns:
        dict with keys: base_url, client_id, client_secret, token_url, school_id
        or None if not configured
    """
    # Try per-teacher config first
    if teacher_id:
        try:
            from backend.storage import load
            config = load("oneroster_config", teacher_id)
            if config and config.get("base_url") and config.get("client_id"):
                return config
        except Exception:
            pass

    # Fall back to environment
    base_url = os.getenv("ONEROSTER_BASE_URL")
    client_id = os.getenv("ONEROSTER_CLIENT_ID")
    client_secret = os.getenv("ONEROSTER_CLIENT_SECRET")
    if base_url and client_id and client_secret:
        return {
            "base_url": base_url,
            "client_id": client_id,
            "client_secret": client_secret,
            "token_url": os.getenv("ONEROSTER_TOKEN_URL"),
            "school_id": os.getenv("ONEROSTER_SCHOOL_ID"),
        }

    return None
```

- [ ] **Step 2: Create `tests/test_oneroster.py`**

```python
"""Unit tests for OneRoster client and data normalization."""
import pytest
from backend.oneroster import normalize_roster


def _make_raw_roster(classes=None, students=None, enrollments=None, demographics=None):
    return {
        "classes": classes or [],
        "students": students or [],
        "teachers": [],
        "enrollments": enrollments or [],
        "demographics": demographics or [],
    }


class TestNormalizeRoster:
    def test_empty_roster(self):
        classes, students, enrollments, accommodations = normalize_roster(_make_raw_roster())
        assert classes == []
        assert students == []
        assert enrollments == []
        assert accommodations == {}

    def test_basic_class_normalization(self):
        raw = _make_raw_roster(classes=[{
            "sourcedId": "cls-1",
            "title": "Algebra 1",
            "subjects": ["Math"],
            "grades": ["09"],
            "status": "active",
        }])
        classes, _, _, _ = normalize_roster(raw)
        assert len(classes) == 1
        assert classes[0]["external_id"] == "cls-1"
        assert classes[0]["name"] == "Algebra 1"
        assert classes[0]["subject"] == "Math"
        assert classes[0]["grade_level"] == "09"

    def test_skips_deleted_records(self):
        raw = _make_raw_roster(
            classes=[{"sourcedId": "c1", "title": "A", "status": "tobedeleted"}],
            students=[{"sourcedId": "s1", "givenName": "X", "familyName": "Y",
                        "role": "student", "status": "tobedeleted"}],
        )
        classes, students, _, _ = normalize_roster(raw)
        assert len(classes) == 0
        assert len(students) == 0

    def test_student_normalization(self):
        raw = _make_raw_roster(students=[{
            "sourcedId": "stu-1",
            "givenName": "Jane",
            "familyName": "Doe",
            "email": "jane@school.edu",
            "role": "student",
        }])
        _, students, _, _ = normalize_roster(raw)
        assert len(students) == 1
        assert students[0]["first_name"] == "Jane"
        assert students[0]["last_name"] == "Doe"

    def test_enrollment_normalization(self):
        raw = _make_raw_roster(
            classes=[{"sourcedId": "c1", "title": "Math"}],
            students=[{"sourcedId": "s1", "givenName": "A", "familyName": "B", "role": "student"}],
            enrollments=[{
                "sourcedId": "e1",
                "class": "c1",
                "user": "s1",
                "role": "student",
            }],
        )
        _, _, enrollments, _ = normalize_roster(raw)
        assert enrollments == [("c1", "s1")]

    def test_teacher_enrollments_excluded(self):
        raw = _make_raw_roster(
            enrollments=[{
                "sourcedId": "e1", "class": "c1", "user": "t1", "role": "teacher",
            }],
        )
        _, _, enrollments, _ = normalize_roster(raw)
        assert enrollments == []

    def test_iep_accommodation_extraction(self):
        raw = _make_raw_roster(
            students=[{"sourcedId": "s1", "givenName": "A", "familyName": "B", "role": "student"}],
            demographics=[{
                "sourcedId": "s1",
                "metadata": {"iep_status": "Y", "ell_status": "N"},
            }],
        )
        _, _, _, accommodations = normalize_roster(raw)
        assert "s1" in accommodations
        assert accommodations["s1"]["iep_status"] is True
        assert "simplified_language" in accommodations["s1"]["suggested_presets"]

    def test_ell_accommodation_extraction(self):
        raw = _make_raw_roster(
            students=[{"sourcedId": "s1", "givenName": "A", "familyName": "B", "role": "student"}],
            demographics=[{
                "sourcedId": "s1",
                "metadata": {"ell_status": "active", "home_language": "Spanish"},
            }],
        )
        _, _, _, accommodations = normalize_roster(raw)
        assert accommodations["s1"]["ell_status"] is True
        assert accommodations["s1"]["home_language"] == "Spanish"
        assert "ell_support" in accommodations["s1"]["suggested_presets"]
```

---

## Task 3: OneRoster Routes

**Files:**
- Create: `backend/routes/oneroster_routes.py`
- Modify: `backend/routes/__init__.py`
- Modify: `backend/auth.py`

- [ ] **Step 1: Create `backend/routes/oneroster_routes.py`**

```python
"""
OneRoster REST API integration routes.
Provides configuration, roster sync, and data management endpoints.
"""
import asyncio
import logging
import threading

from flask import Blueprint, request, jsonify, g

from backend.oneroster import OneRosterClient, normalize_roster, get_oneroster_config
from backend.roster_sync import sync_roster_to_db
from backend.accommodations import set_student_accommodation
from backend.utils.auth_decorators import require_teacher
from backend.utils.errors import handle_route_errors

oneroster_bp = Blueprint("oneroster", __name__)
logger = logging.getLogger(__name__)


def _run_async(coro):
    """Run async coroutine from sync Flask context (matches clever_routes pattern)."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ── Configuration ────────────────────────────────────────────────────────────

@oneroster_bp.route("/api/oneroster/config", methods=["GET"])
@require_teacher
@handle_route_errors
def get_config():
    """Check OneRoster configuration status (never exposes secrets)."""
    config = get_oneroster_config(g.teacher_id)
    if not config:
        return jsonify({"configured": False})
    return jsonify({
        "configured": True,
        "base_url": config.get("base_url", ""),
        "school_id": config.get("school_id", ""),
        "has_credentials": bool(config.get("client_id")),
    })


@oneroster_bp.route("/api/oneroster/config", methods=["POST"])
@require_teacher
@handle_route_errors
def save_config():
    """Save OneRoster connection configuration."""
    data = request.json or {}
    base_url = data.get("base_url", "").strip()
    client_id = data.get("client_id", "").strip()
    client_secret = data.get("client_secret", "").strip()
    token_url = data.get("token_url", "").strip() or None
    school_id = data.get("school_id", "").strip() or None

    if not base_url or not client_id or not client_secret:
        return jsonify({"error": "base_url, client_id, and client_secret are required"}), 400

    from backend.storage import save
    config = {
        "base_url": base_url,
        "client_id": client_id,
        "client_secret": client_secret,
        "token_url": token_url,
        "school_id": school_id,
    }
    save("oneroster_config", config, g.teacher_id)

    from backend.utils.audit import audit_log
    audit_log(g.teacher_id, "oneroster_config_saved", "OneRoster configuration updated")

    return jsonify({"status": "saved"})


# ── Connection Test ──────────────────────────────────────────────────────────

@oneroster_bp.route("/api/oneroster/test", methods=["POST"])
@require_teacher
@handle_route_errors
def test_connection():
    """Test OneRoster API connectivity and credentials."""
    config = get_oneroster_config(g.teacher_id)
    if not config:
        return jsonify({"error": "OneRoster not configured"}), 400

    client = OneRosterClient(
        base_url=config["base_url"],
        client_id=config["client_id"],
        client_secret=config["client_secret"],
        token_url=config.get("token_url"),
    )

    async def _test():
        async with __import__("httpx").AsyncClient(timeout=15.0) as http:
            await client._ensure_token(http)
            # Try fetching one class to verify access
            body = await client._get_with_retry(
                http,
                f"{client.base_url}/classes?limit=1&offset=0",
                "test",
            )
            return body is not None

    try:
        success = _run_async(_test())
        if success:
            return jsonify({"status": "connected"})
        return jsonify({"error": "Could not reach OneRoster API"}), 502
    except Exception as e:
        return jsonify({"error": f"Connection failed: {str(e)}"}), 502


# ── Roster Sync ──────────────────────────────────────────────────────────────

@oneroster_bp.route("/api/oneroster/sync-roster", methods=["POST"])
@require_teacher
@handle_route_errors
def sync_roster():
    """Fetch and sync roster from OneRoster API."""
    config = get_oneroster_config(g.teacher_id)
    if not config:
        return jsonify({"error": "OneRoster not configured"}), 400

    teacher_id = g.teacher_id

    client = OneRosterClient(
        base_url=config["base_url"],
        client_id=config["client_id"],
        client_secret=config["client_secret"],
        token_url=config.get("token_url"),
    )

    # Fetch roster data
    raw = _run_async(client.fetch_roster(school_id=config.get("school_id")))
    classes, students, enrollments, accommodations = normalize_roster(raw)

    # Sync to database
    counts = sync_roster_to_db(classes, students, enrollments, teacher_id, provider="oneroster")

    # Persist roster as CSV (same format as Clever, for file-based features)
    from backend.clever import persist_roster_as_csv, persist_sections_as_periods
    # Convert to Clever-compatible format for file persistence
    csv_students = []
    for s in students:
        csv_students.append({"data": {
            "id": s["external_id"],
            "name": {"first": s["first_name"], "last": s["last_name"]},
            "email": s.get("email", ""),
        }})
    persist_roster_as_csv(csv_students, teacher_id)

    csv_sections = []
    # Build student list per class from enrollments
    class_students_map = {}
    for cls_id, stu_id in enrollments:
        class_students_map.setdefault(cls_id, []).append(stu_id)
    for cls in classes:
        csv_sections.append({"data": {
            "id": cls["external_id"],
            "name": cls["name"],
            "subject": cls.get("subject", ""),
            "grade": cls.get("grade_level", ""),
            "students": class_students_map.get(cls["external_id"], []),
        }})
    persist_sections_as_periods(csv_sections, teacher_id)

    from backend.utils.audit import audit_log
    audit_log(teacher_id, "oneroster_roster_sync",
              f"Synced {counts['classes']} classes, {counts['students']} students, {counts['enrollments']} enrollments")

    return jsonify({
        "status": "synced",
        "counts": counts,
        "accommodation_suggestions": accommodations,
    })


# ── Apply Accommodations ─────────────────────────────────────────────────────

@oneroster_bp.route("/api/oneroster/apply-accommodations", methods=["POST"])
@require_teacher
@handle_route_errors
def apply_accommodations():
    """Apply IEP/ELL accommodation presets from OneRoster demographics.

    Body: {"accommodations": {"student_ext_id": {"suggested_presets": [...], "custom_notes": "..."}}}
    """
    data = request.json or {}
    accommodations = data.get("accommodations", {})
    if not accommodations:
        return jsonify({"error": "No accommodations provided"}), 400

    applied = 0
    errors = []
    for student_id, acc in accommodations.items():
        try:
            presets = acc.get("suggested_presets", [])
            notes = acc.get("custom_notes", "")
            name = acc.get("name", "")
            set_student_accommodation(student_id, presets, notes, name, g.teacher_id)
            applied += 1
        except Exception as e:
            errors.append(f"{student_id}: {str(e)}")

    from backend.utils.audit import audit_log
    audit_log(g.teacher_id, "oneroster_apply_accommodations",
              f"Applied accommodations for {applied} students")

    return jsonify({"applied": applied, "total": len(accommodations), "errors": errors})


# ── Data Deletion ─────────────────────────────────────────────────────────────

@oneroster_bp.route("/api/oneroster/delete-data", methods=["POST"])
@require_teacher
@handle_route_errors
def delete_data():
    """Delete all OneRoster-synced data for this teacher.

    Reuses Clever's file deletion logic (same file format) and
    clears OneRoster config from storage.
    """
    from backend.clever import delete_clever_data
    from backend.storage import save

    counts = delete_clever_data(g.teacher_id)

    # Also clear OneRoster config
    save("oneroster_config", None, g.teacher_id)

    from backend.utils.audit import audit_log
    audit_log(g.teacher_id, "oneroster_data_deletion", f"Deleted OneRoster data: {counts}")

    return jsonify({"status": "deleted", "counts": counts})
```

- [ ] **Step 2: Register blueprint in `backend/routes/__init__.py`**

Find the section where blueprints are registered (look for `clever_routes` import) and add:

```python
# ADD after the clever_routes import/register block:
from backend.routes.oneroster_routes import oneroster_bp
app.register_blueprint(oneroster_bp)
```

> **Note:** The exact location depends on how `__init__.py` registers blueprints. Find the pattern used for `clever_bp` and follow it.

- [ ] **Step 3: Add OneRoster routes to public prefixes in `backend/auth.py`**

The OneRoster endpoints all use `@require_teacher` (JWT auth), so no changes needed to `PUBLIC_PREFIXES` or `PUBLIC_EXACT`. However, verify that the `check_auth()` before_request hook correctly handles the `/api/oneroster/` prefix — it should already work since it falls through to Bearer token validation.

No code change needed here unless testing reveals auth issues.

---

## Task 4: Frontend — Settings UI

**Files:**
- Modify: `frontend/src/tabs/SettingsTab.jsx`
- Modify: `frontend/src/services/api.js`

- [ ] **Step 1: Add API functions in `frontend/src/services/api.js`**

Add these functions alongside the existing Clever API functions:

```javascript
// OneRoster Integration
export async function getOneRosterConfig() {
  const res = await fetch('/api/oneroster/config', { headers: authHeaders() });
  return res.json();
}

export async function saveOneRosterConfig(config) {
  const res = await fetch('/api/oneroster/config', {
    method: 'POST',
    headers: { ...authHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify(config),
  });
  return res.json();
}

export async function testOneRosterConnection() {
  const res = await fetch('/api/oneroster/test', {
    method: 'POST',
    headers: authHeaders(),
  });
  return res.json();
}

export async function syncOneRosterRoster() {
  const res = await fetch('/api/oneroster/sync-roster', {
    method: 'POST',
    headers: authHeaders(),
  });
  return res.json();
}

export async function applyOneRosterAccommodations(accommodations) {
  const res = await fetch('/api/oneroster/apply-accommodations', {
    method: 'POST',
    headers: { ...authHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify({ accommodations }),
  });
  return res.json();
}

export async function deleteOneRosterData() {
  const res = await fetch('/api/oneroster/delete-data', {
    method: 'POST',
    headers: authHeaders(),
  });
  return res.json();
}
```

- [ ] **Step 2: Add OneRoster config panel to `SettingsTab.jsx`**

Find the Clever integration section in `SettingsTab.jsx` and add a parallel OneRoster section below it. The section should include:

1. **Connection fields:** Base URL, Client ID, Client Secret, Token URL (optional), School ID (optional)
2. **Test Connection button** — calls `testOneRosterConnection()`
3. **Sync Roster button** — calls `syncOneRosterRoster()`, shows counts on success
4. **Accommodation suggestions** — if sync returns accommodations, show a "Review & Apply" panel (same UI pattern as Clever accommodations)
5. **Delete Data button** — calls `deleteOneRosterData()` with confirmation dialog

**UI Pattern:** Follow the existing Clever section's layout — collapsible card with a header icon, input fields with labels, action buttons with loading states. Use the same inline style patterns already in the file. Use `Icon` component for icons (same as rest of the app).

**State variables to add:**
```javascript
const [oneRosterConfig, setOneRosterConfig] = useState({ base_url: '', client_id: '', client_secret: '', token_url: '', school_id: '' });
const [oneRosterStatus, setOneRosterStatus] = useState(null); // null | 'connected' | 'error'
const [oneRosterSyncing, setOneRosterSyncing] = useState(false);
const [oneRosterAccommodations, setOneRosterAccommodations] = useState(null);
```

**On mount:** Call `getOneRosterConfig()` to populate existing config and show connection status.

> **Important:** Do NOT expose `client_secret` in the config GET response. The GET endpoint returns `has_credentials: true/false` — show "Credentials saved" badge instead of the actual secret. Only send the secret on POST (save).

---

## Task 5: Environment Variables & Documentation

- [ ] **Step 1: Add env vars to `.env.example` (if it exists) or document in CLAUDE.md**

Add to the Environment Variables section of `CLAUDE.md`:

```markdown
### OneRoster Integration (1EdTech)
- `ONEROSTER_BASE_URL` — OneRoster API root (e.g., `https://sis.district.org/ims/oneroster/v1p1`)
- `ONEROSTER_CLIENT_ID` — OAuth 2.0 client ID
- `ONEROSTER_CLIENT_SECRET` — OAuth 2.0 client secret
- `ONEROSTER_TOKEN_URL` — OAuth token endpoint (optional, defaults to `{base_url}/token`)
- `ONEROSTER_SCHOOL_ID` — School sourcedId to scope roster fetch (optional)
```

- [ ] **Step 2: Add OneRoster API endpoints to CLAUDE.md**

Add to the API Reference section:

```markdown
### OneRoster Integration (1EdTech)
- `GET /api/oneroster/config` — Check OneRoster configuration status
- `POST /api/oneroster/config` — Save OneRoster connection settings
- `POST /api/oneroster/test` — Test API connectivity
- `POST /api/oneroster/sync-roster` — Fetch and sync roster from OneRoster API
- `POST /api/oneroster/apply-accommodations` — Apply IEP/ELL presets from demographics
- `POST /api/oneroster/delete-data` — Delete all OneRoster-synced data
```

---

## Implementation Notes

### Database: No Schema Changes Required

The existing `classes.clever_section_id` column is reused to store OneRoster `sourcedId` values. The column name is Clever-specific but the data is just an external provider ID string. **Do NOT rename the column** — it would require a migration and break Clever sync. A future rename can be done as a separate task if desired.

### Provider Detection

Teachers can use Clever OR OneRoster (or neither). The system does not prevent configuring both, but only one roster source should be active at a time. The Settings UI should make this clear.

### IEP/ELL from OneRoster Demographics

OneRoster's demographics endpoint may or may not include IEP/ELL flags — this depends on the district's SIS configuration and the scopes granted. The `metadata` field is where districts typically put custom fields like `iep_status`. If demographics are unavailable or don't include these fields, the sync still works — teachers can manually set accommodations.

### File Persistence Compatibility

OneRoster reuses Clever's file persistence functions (`persist_roster_as_csv`, `persist_sections_as_periods`) by wrapping data in Clever's `{data: {...}}` format. This avoids duplicating file I/O logic and ensures features that read roster CSVs (grading thread, analytics) work without changes.

### Testing Strategy

1. `tests/test_oneroster.py` — Unit tests for `normalize_roster()` (no network calls)
2. `tests/test_roster_sync.py` — Unit tests for shared DB sync (mock Supabase)
3. `tests/test_oneroster_routes.py` — Route-level tests: auth decorators, audit logging, deletion, credential masking. Mirror existing Clever test patterns.
4. Manual E2E — Test against a OneRoster sandbox (Clever provides one, or use ClassLink's sandbox)

### Dependency: No New Packages

`httpx` is already in `requirements.txt` (used by Clever). OAuth 2.0 client_credentials is handled with raw HTTP — no additional OAuth library needed.

---

## Review Fixes (from plan review feedback)

### Fix 1: `delete_clever_data` Guard Relaxation

**Problem:** `delete_clever_data()` in `backend/clever.py` checks `teacher_id.startswith("clever:")` — OneRoster teachers won't have a `clever:` prefix, so deletion will 403.

**Solution:** Create a generalized `delete_roster_data(teacher_id)` function that handles deletion for both providers. It should:
1. Delete classes, class_students, students, roster CSVs, period files for the teacher
2. NOT check for a `clever:` prefix — all authenticated teachers can delete their own data
3. `delete_clever_data` calls `delete_roster_data` internally (backward compat)
4. OneRoster deletion endpoint calls `delete_roster_data` directly

**Implementation:** In Task 4 (`oneroster_routes.py`), change the delete endpoint:
```python
# Instead of: from backend.clever import delete_clever_data
# Use: from backend.clever import delete_roster_data
counts = delete_roster_data(g.teacher_id)
```

Add `delete_roster_data` to `backend/clever.py` as a wrapper that skips the `clever:` prefix check. The existing `delete_clever_data` should call it internally after its own prefix validation.

### Fix 2: Provider Exclusivity Enforcement

**Problem:** Teachers could sync both Clever and OneRoster simultaneously, overwriting `clever_section_id` and breaking Clever audit trails.

**Solution:** Hard gate at sync time. Before any roster sync (Clever or OneRoster), check if the other provider is already active:

```python
def _check_provider_exclusivity(teacher_id, current_provider):
    """Prevent simultaneous use of multiple roster providers."""
    db = get_supabase()
    # Check if classes exist with a different provider source
    classes = db.table('classes').select('id, clever_section_id').eq('teacher_id', teacher_id).execute()
    for cls in (classes.data or []):
        section_id = cls.get('clever_section_id', '')
        if not section_id:
            continue
        # Clever IDs start with a Clever-format ID, OneRoster IDs are UUIDs
        is_clever = not section_id.startswith('oneroster:')
        if current_provider == 'oneroster' and is_clever:
            return False, "Clever roster is active. Delete Clever data in Settings > Classroom before switching to OneRoster."
        if current_provider == 'clever' and section_id.startswith('oneroster:'):
            return False, "OneRoster roster is active. Delete OneRoster data before switching to Clever."
    return True, None
```

**Prefix convention:** OneRoster `sourcedId` values stored in `clever_section_id` should be prefixed with `oneroster:` to distinguish from Clever IDs. This makes provider detection deterministic.

**UI:** The OneRoster settings section should show a warning if Clever is active (and vice versa), with a "Switch Provider" button that first deletes the old data then enables the new config.

### Fix 3: OneRoster Section Filtering (Teacher-Scoped)

**Problem:** OneRoster API can return all sections in a district. Without filtering, sync could import off-roster sections, exposing data the teacher shouldn't see — a Clever compliance violation.

**Solution:** In Task 3 (`oneroster_client.py`), after fetching enrollments, filter sections to only those where the authenticated teacher is the instructor:

```python
async def get_teacher_sections(base_url, token, teacher_sourced_id):
    """Fetch only sections where this teacher is the instructor."""
    # Option A: Use teacher-scoped endpoint if available
    # GET /ims/oneroster/v1p1/teachers/{id}/classes
    url = f"{base_url}/ims/oneroster/v1p1/teachers/{teacher_sourced_id}/classes"

    # Option B: Fetch all classes and filter by teacher enrollment
    # This is the fallback if the teacher-scoped endpoint isn't supported
```

The plan's Task 3 Step 1 must explicitly:
1. Use the teacher-scoped endpoint (`/teachers/{id}/classes`) as primary
2. Fall back to fetching all classes + filtering by teacher enrollment
3. Log a warning if fallback is used (signals the district may need to enable the scoped endpoint)
4. NEVER return unfiltered sections to the sync pipeline

### Fix 4: Route-Level Tests

**Problem:** Testing covers normalization and shared sync but omits route-level auth, audit logging, and deletion tests.

**Solution:** Add `tests/test_oneroster_routes.py` with:
- `@require_teacher` enforcement (unauthenticated → 401)
- Audit log written on sync and deletion
- `GET /api/oneroster/credentials` returns `has_credentials` boolean, never the actual secret
- `POST /api/oneroster/delete-data` deletes classes + students + files
- Provider exclusivity check blocks dual-provider sync

These mirror the Clever test patterns and ensure compliance guarantees extend to OneRoster.

### Fix 5: Migration / Rollback for `_sync_classes_to_db` Extraction

**Problem:** Extracting shared sync logic from Clever-specific code is high blast radius. If Supabase writes regress, Clever sync breaks.

**Solution:** Before and after the extraction:

1. **Pre-extraction snapshot:** Run Clever sync for a test teacher, capture the resulting DB state (classes, class_students, students). Save as a JSON fixture.
2. **Post-extraction verification:** Run Clever sync again with the refactored code. Compare DB state to the fixture — must be identical.
3. **Rollback plan:** If extraction breaks Clever sync:
   - Revert the `_sync_classes_to_db` extraction commit
   - OneRoster routes call their own sync function (duplicated temporarily)
   - Re-attempt extraction in a follow-up PR with the fixture test as a gate

Add a test in `tests/test_roster_sync.py`:
```python
def test_clever_sync_unchanged_after_extraction():
    """Verify Clever sync produces identical DB state after _sync_classes_to_db extraction."""
    # Mock Supabase, run sync with Clever-format data
    # Assert: same classes, same students, same enrollments as before extraction
```
