"""
OneRoster 1.1/1.2 REST API client for Graider.
Handles OAuth 2.0 client_credentials flow and roster synchronization.
"""
import asyncio
import logging
import os
import time

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
        """Obtain or refresh OAuth bearer token via client_credentials grant."""
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


def normalize_roster(raw):
    """Convert raw OneRoster API data to Graider's normalized format.

    Args:
        raw: dict with keys classes, students, enrollments, demographics

    Returns:
        tuple: (classes, students, enrollments, accommodations)
    """
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
            "external_id": f"oneroster:{c.get('sourcedId', '')}",
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
            "external_id": f"oneroster:{sid}",
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
            "class_external_id": f"oneroster:{class_id}",
            "student_external_id": f"oneroster:{user_id}",
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
                "student_external_id": f"oneroster:{sid}",
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
