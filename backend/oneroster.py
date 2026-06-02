"""
OneRoster 1.1/1.2 REST API client for Graider.
Handles OAuth 2.0 client_credentials flow and roster synchronization.
"""
import asyncio
import logging
import os
import time
import uuid
from datetime import date

import httpx

logger = logging.getLogger(__name__)

MAX_RETRIES = 5
DEFAULT_PAGE_LIMIT = 100


class OneRosterClient:
    """OAuth 2.0 client_credentials REST client for OneRoster APIs."""

    def __init__(self, base_url, client_id, client_secret, token_url=None):
        self.base_url = base_url.rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_url = token_url or f"{self.base_url}/oauth/token"
        self._token = None
        self._token_expires = 0

    async def _ensure_token(self, client):
        """Obtain or refresh OAuth bearer token via client_credentials grant.

        Sends credentials via BOTH HTTP Basic auth header AND form-body fields.
        Per RFC 6749 §2.3.1, the spec allows either channel and recommends
        Basic for clients that can support it; in practice OneRoster vendors
        disagree on which they accept. ClassLink's Roster Server rejects
        body-only credentials with `401 UNAUTHORIZED – the Request requires
        authorization`; other vendors only accept body. Sending both makes
        the client work against the union of vendor implementations.
        """
        if self._token and time.time() < self._token_expires - 30:
            return

        logger.info("Requesting OAuth token from %s", self.token_url)
        resp = await client.post(
            self.token_url,
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            auth=(self.client_id, self.client_secret),
        )
        resp.raise_for_status()
        data = resp.json()
        self._token = data.get("access_token")
        expires_in = data.get("expires_in", 3600)
        self._token_expires = time.time() + expires_in
        logger.info("OAuth token obtained, expires in %ds", expires_in)

    async def _get_with_retry(self, client, url, label=""):
        """GET with exponential backoff on 429/5xx, token refresh on 401."""
        for attempt in range(MAX_RETRIES):
            await self._ensure_token(client)
            headers = {"Authorization": f"Bearer {self._token}"}
            resp = await client.get(url, headers=headers)

            if resp.status_code == 200:
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

    async def _post_with_retry(self, client, url, json_body, label=""):
        """POST with exponential backoff on 429/5xx, token refresh on 401.

        Accepts HTTP 200 and 201 as success. Returns parsed JSON body.
        """
        for attempt in range(MAX_RETRIES):
            await self._ensure_token(client)
            headers = {"Authorization": f"Bearer {self._token}"}
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

    async def _get_paginated(self, client, path, resource_key, label=""):
        """Fetch all pages of a OneRoster collection endpoint."""
        all_items = []
        offset = 0

        while True:
            separator = "&" if "?" in path else "?"
            url = f"{self.base_url}{path}{separator}limit={DEFAULT_PAGE_LIMIT}&offset={offset}"
            data = await self._get_with_retry(client, url, label=label or path)

            items = data.get(resource_key, [])
            if not items:
                break

            all_items.extend(items)
            logger.debug("%s: fetched %d items (total %d)", label or path, len(items), len(all_items))

            if len(items) < DEFAULT_PAGE_LIMIT:
                break
            offset += DEFAULT_PAGE_LIMIT

        return all_items

    async def fetch_roster(self, school_id=None, teacher_sourced_id=None):
        """Fetch classes, students, teachers, enrollments, and demographics.

        If teacher_sourced_id is provided, fetches only that teacher's classes
        via /teachers/{id}/classes. Otherwise fetches all classes and filters
        by teacher enrollment.

        Returns dict with keys: classes, students, teachers, enrollments, demographics
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            await self._ensure_token(client)

            # Fetch classes
            if teacher_sourced_id:
                classes = await self._get_paginated(
                    client,
                    f"/teachers/{teacher_sourced_id}/classes",
                    "classes",
                    label="teacher-classes",
                )
            else:
                classes = await self._get_paginated(
                    client, "/classes", "classes", label="classes"
                )

            # Apply school filter if provided
            if school_id:
                classes = [
                    c for c in classes
                    if c.get("school", {}).get("sourcedId") == school_id
                    or any(
                        s.get("sourcedId") == school_id
                        for s in c.get("schools", [])
                        if isinstance(s, dict)
                    )
                ]

            # Fetch enrollments, students, teachers in parallel
            enrollments_task = self._get_paginated(
                client, "/enrollments", "enrollments", label="enrollments"
            )
            students_task = self._get_paginated(
                client, "/students", "students", label="students"
            )
            teachers_task = self._get_paginated(
                client, "/teachers", "teachers", label="teachers"
            )

            enrollments, students, teachers = await asyncio.gather(
                enrollments_task, students_task, teachers_task
            )

            # Fallback: the /students and /teachers convenience endpoints are
            # optional in OneRoster, and some servers (e.g. ClassLink Roster
            # Server) leave them empty while populating the canonical /users
            # collection (each user carries a `role`). When either comes back
            # empty, derive it from /users by role so rostering still works.
            if not students or not teachers:
                try:
                    users = await self._get_paginated(
                        client, "/users", "users", label="users"
                    )
                    if not students:
                        students = [
                            u for u in users
                            if (u.get("role") or "").lower() == "student"
                        ]
                    if not teachers:
                        teachers = [
                            u for u in users
                            if (u.get("role") or "").lower() == "teacher"
                        ]
                except Exception as e:
                    logger.info("Users fallback fetch failed: %s", e)

            # Demographics are optional (some providers don't support them)
            demographics = []
            try:
                demographics = await self._get_paginated(
                    client, "/demographics", "demographics", label="demographics"
                )
            except Exception as e:
                logger.info("Demographics fetch failed (optional): %s", e)

            return {
                "classes": classes,
                "students": students,
                "teachers": teachers,
                "enrollments": enrollments,
                "demographics": demographics,
            }


    async def create_line_item(self, title, class_sourced_id, max_score, due_date=None):
        """Create a gradebook line item (assignment) in the OneRoster SIS.

        Args:
            title: Human-readable name for the assignment.
            class_sourced_id: The OneRoster sourcedId of the class.
            max_score: Maximum possible score (resultValueMax).
            due_date: Optional ISO 8601 date string (e.g. '2026-04-10').

        Returns:
            The lineItem dict from the SIS response.
        """
        sourced_id = str(uuid.uuid4())
        today = due_date if due_date is not None else date.today().isoformat()
        payload_item = {
            "sourcedId": sourced_id,
            "status": "active",
            "title": title,
            "assignDate": today,
            "dueDate": today,
            "class": {"sourcedId": class_sourced_id, "type": "class"},
            "resultValueMin": 0.0,
            "resultValueMax": float(max_score),
            "category": {"sourcedId": "graider-auto", "title": "Graider"},
        }

        json_body = {"lineItem": payload_item}
        url = f"{self.base_url}/lineItems"

        async with httpx.AsyncClient(timeout=30.0) as client:
            data = await self._post_with_retry(client, url, json_body, label="create_line_item")
            return data.get("lineItem", data)

    async def get_line_items(self, class_sourced_id):
        """Fetch all line items for a class from the OneRoster SIS.

        Args:
            class_sourced_id: The OneRoster sourcedId of the class.

        Returns:
            List of lineItem dicts (may be empty).
        """
        url = f"{self.base_url}/lineItems?filter=classSourcedId='{class_sourced_id}'"

        async with httpx.AsyncClient(timeout=30.0) as client:
            data = await self._get_with_retry(client, url, label="get_line_items")
            return data.get("lineItems", [])

    async def create_result(self, line_item_id, student_sourced_id, score, max_score, comment=""):
        """Post a student score result to the OneRoster SIS.

        Args:
            line_item_id: The OneRoster sourcedId of the line item.
            student_sourced_id: The OneRoster sourcedId of the student.
            score: The student's raw score.
            max_score: The maximum possible score (used for scoreScale context).
            comment: Optional feedback comment (defaults to "").

        Returns:
            The result dict from the SIS response.
        """
        sourced_id = str(uuid.uuid4())
        score_date = date.today().isoformat()

        json_body = {
            "result": {
                "sourcedId": sourced_id,
                "status": "active",
                "lineItem": {"sourcedId": line_item_id},
                "student": {"sourcedId": student_sourced_id},
                "score": float(score),
                "scoreDate": score_date,
                "scoreStatus": "fully graded",
                "comment": comment,
            }
        }
        url = f"{self.base_url}/lineItems/{line_item_id}/results"

        async with httpx.AsyncClient(timeout=30.0) as client:
            data = await self._post_with_retry(client, url, json_body, label="create_result")
            return data.get("result", data)


def normalize_roster(raw, external_id_for=None):
    """Convert raw OneRoster API data to Graider's normalized format.

    Args:
        raw: dict with keys classes, students, enrollments, demographics
        external_id_for: optional callable ``(sourcedId: str) -> str`` that
            builds the external_id string for a given sourcedId.  Applied to
            all five external_id sites (class, student, enrollment.class,
            enrollment.student, accommodation.student).  Defaults to
            ``lambda sid: f"oneroster:{sid}"`` so OneRoster and Clever callers
            remain byte-identical without passing this argument.

    Returns:
        tuple: (classes, students, enrollments, accommodations)
    """
    if external_id_for is None:
        def external_id_for(sid):
            return f"oneroster:{sid}"

    # Build demographics lookup by sourcedId
    demo_by_id = {}
    for d in raw.get("demographics", []):
        sid = d.get("sourcedId")
        if sid:
            demo_by_id[sid] = d

    # Normalize classes
    classes = []
    for c in raw.get("classes", []):
        if c.get("status") == "tobedeleted":
            continue
        subjects = c.get("subjects", [])
        grades = c.get("grades", [])
        classes.append({
            "external_id": external_id_for(c.get('sourcedId', '')),
            "name": c.get("title", ""),
            "subject": subjects[0] if subjects else None,
            "grade_level": grades[0] if grades else None,
        })

    # Normalize students — deduplicate by sourcedId
    seen_student_ids = set()
    students = []
    for s in raw.get("students", []):
        if s.get("status") == "tobedeleted":
            continue
        sid = s.get("sourcedId", "")
        if sid in seen_student_ids:
            continue
        seen_student_ids.add(sid)
        students.append({
            "external_id": external_id_for(sid),
            "first_name": s.get("givenName", ""),
            "last_name": s.get("familyName", ""),
            "email": s.get("email", ""),
        })

    # Normalize enrollments — student role only
    enrollments = []
    for e in raw.get("enrollments", []):
        if e.get("status") == "tobedeleted":
            continue
        if e.get("role") != "student":
            continue

        # Handle both dict refs ({sourcedId: "..."}) and string refs
        class_ref = e.get("class", {})
        user_ref = e.get("user", {})
        if isinstance(class_ref, dict):
            class_id = class_ref.get("sourcedId", "")
        else:
            class_id = str(class_ref) if class_ref else ""
        if isinstance(user_ref, dict):
            user_id = user_ref.get("sourcedId", "")
        else:
            user_id = str(user_ref) if user_ref else ""

        enrollments.append({
            "class_external_id": external_id_for(class_id),
            "student_external_id": external_id_for(user_id),
        })

    # Extract accommodations from demographics
    accommodations = []
    for s in raw.get("students", []):
        sid = s.get("sourcedId", "")
        if s.get("status") == "tobedeleted":
            continue

        # Demographics may be linked via userProfiles or direct sourcedId match
        demo = demo_by_id.get(sid, {})
        metadata = demo.get("metadata", {})

        iep_status = metadata.get("iep_status") or metadata.get("iepStatus")
        ell_status = metadata.get("ell_status") or metadata.get("ellStatus")
        home_language = metadata.get("home_language") or metadata.get("homeLanguage")

        if iep_status or ell_status:
            acc = {
                "student_external_id": external_id_for(sid),
            }
            if iep_status:
                acc["iep_status"] = iep_status
            if ell_status:
                acc["ell_status"] = ell_status
                if home_language:
                    acc["home_language"] = home_language
            accommodations.append(acc)

    return classes, students, enrollments, accommodations


def get_oneroster_config(teacher_id=None):
    """Load OneRoster configuration.

    Checks per-teacher config first (from Supabase storage), then falls back
    to environment variables.

    Returns dict with base_url, client_id, client_secret, token_url, school_id
    or None if not configured.
    """
    # Try per-teacher config from storage
    if teacher_id:
        try:
            from backend.storage import load
            stored = load("oneroster_config", teacher_id)
            if stored and stored.get("base_url") and stored.get("client_id"):
                return {
                    "base_url": stored.get("base_url"),
                    "client_id": stored.get("client_id"),
                    "client_secret": stored.get("client_secret"),
                    "token_url": stored.get("token_url"),
                    "school_id": stored.get("school_id"),
                    "teacher_sourced_id": stored.get("teacher_sourced_id"),
                }
        except Exception as e:
            logger.debug("Could not load per-teacher OneRoster config: %s", e)

    # Try district-level config from storage
    try:
        from backend.storage import load
        district_cfg = load("district:sis_config", "system")
        if district_cfg and district_cfg.get("sis_type") == "oneroster":
            teacher_sourced_id = None
            if teacher_id:
                try:
                    teacher_sourced_id = load("oneroster_teacher_id", teacher_id)
                except Exception:
                    pass
            return {
                "base_url": district_cfg.get("base_url"),
                "client_id": district_cfg.get("client_id"),
                "client_secret": district_cfg.get("client_secret"),
                "token_url": district_cfg.get("token_url"),
                "school_id": district_cfg.get("school_id"),
                "teacher_sourced_id": teacher_sourced_id,
                "_source": "district",
            }
    except Exception as e:
        logger.debug("Could not load district OneRoster config: %s", e)

    # Fall back to environment variables
    base_url = os.getenv("ONEROSTER_BASE_URL")
    client_id = os.getenv("ONEROSTER_CLIENT_ID")
    client_secret = os.getenv("ONEROSTER_CLIENT_SECRET")

    if not base_url or not client_id or not client_secret:
        return None

    return {
        "base_url": base_url,
        "client_id": client_id,
        "client_secret": client_secret,
        "token_url": os.getenv("ONEROSTER_TOKEN_URL"),
        "school_id": os.getenv("ONEROSTER_SCHOOL_ID"),
        "teacher_sourced_id": None,
    }
