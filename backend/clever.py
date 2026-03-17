"""
Clever OAuth + API client for Graider.
Handles SSO authentication and Secure Sync roster/IEP data.
"""
import csv
import io
import json
import os
import logging
from datetime import datetime
from urllib.parse import urlencode
from base64 import b64encode

import httpx

logger = logging.getLogger(__name__)

CLEVER_AUTH_URL = "https://clever.com/oauth/authorize"
CLEVER_TOKEN_URL = "https://clever.com/oauth/tokens"
CLEVER_API_BASE = "https://api.clever.com"
CLEVER_API_VERSION = os.getenv("CLEVER_API_VERSION", "v3.0")

# Graider data directories (same paths as settings_routes.py / storage.py)
GRAIDER_DATA_DIR = os.path.expanduser("~/.graider_data")
ROSTERS_DIR = os.path.join(GRAIDER_DATA_DIR, "rosters")
PERIODS_DIR = os.path.join(GRAIDER_DATA_DIR, "periods")


def get_clever_config():
    """Return Clever credentials from environment."""
    client_id = os.getenv("CLEVER_CLIENT_ID")
    client_secret = os.getenv("CLEVER_CLIENT_SECRET")
    redirect_uri = os.getenv("CLEVER_REDIRECT_URI")
    if not all([client_id, client_secret, redirect_uri]):
        return None
    return {
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
    }


def get_authorize_url(state=None):
    """Build the Clever OAuth authorization URL."""
    config = get_clever_config()
    if not config:
        return None
    params = {
        "response_type": "code",
        "client_id": config["client_id"],
        "redirect_uri": config["redirect_uri"],
    }
    if state:
        params["state"] = state
    return f"{CLEVER_AUTH_URL}?{urlencode(params)}"


async def exchange_code_for_token(code):
    """Exchange an authorization code for an access token.

    Returns dict with 'access_token' or None on failure.
    """
    config = get_clever_config()
    if not config:
        return None

    # Clever requires Basic auth: base64(client_id:client_secret)
    credentials = b64encode(
        f"{config['client_id']}:{config['client_secret']}".encode()
    ).decode()

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.post(
                CLEVER_TOKEN_URL,
                headers={
                    "Authorization": f"Basic {credentials}",
                    "Content-Type": "application/json",
                },
                json={
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": config["redirect_uri"],
                },
            )
            if resp.status_code != 200:
                logger.error("Clever token exchange failed: %s %s", resp.status_code, resp.text)
                return None
            return resp.json()
        except httpx.HTTPError as e:
            logger.error("Clever token exchange error: %s", str(e))
            return None


async def get_clever_user(access_token):
    """Fetch the current user's identity from Clever.

    Returns dict with user info: {clever_id, type, name, email, district} or None.
    """
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            # Step 1: Get user identity from /me
            resp = await client.get(
                f"{CLEVER_API_BASE}/{CLEVER_API_VERSION}/me",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if resp.status_code != 200:
                logger.error("Clever /me failed: %s", resp.status_code)
                return None
            me_data = resp.json().get("data", {})

            user_id = me_data.get("id")
            user_type = me_data.get("type")  # "teacher", "student", "district_admin"

            # Step 2: Get full user profile
            resp2 = await client.get(
                f"{CLEVER_API_BASE}/{CLEVER_API_VERSION}/users/{user_id}",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if resp2.status_code != 200:
                logger.error("Clever user fetch failed: %s", resp2.status_code)
                return None
            user_data = resp2.json().get("data", {})

            return {
                "clever_id": user_id,
                "type": user_type,
                "name": user_data.get("name", {}),
                "email": user_data.get("email", ""),
                "district": user_data.get("district", ""),
                "roles": user_data.get("roles", {}),
            }
        except httpx.HTTPError as e:
            logger.error("Clever user fetch error: %s", str(e))
            return None


async def sync_roster(district_token):
    """Sync full roster from Clever using a district-app token.

    Returns dict: { "teachers": [...], "students": [...], "sections": [...] }
    """
    headers = {"Authorization": f"Bearer {district_token}"}
    result = {"teachers": [], "students": [], "sections": []}

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Fetch all users (paginated)
        for user_type in ["teachers", "students"]:
            url = f"{CLEVER_API_BASE}/{CLEVER_API_VERSION}/users?role={user_type[:-1]}"
            while url:
                try:
                    resp = await client.get(url, headers=headers)
                    if resp.status_code != 200:
                        logger.error("Clever roster fetch (%s) failed: %s", user_type, resp.status_code)
                        break
                    body = resp.json()
                    result[user_type].extend(body.get("data", []))
                    url = _next_page_url(body)
                except httpx.HTTPError as e:
                    logger.error("Clever roster fetch error (%s): %s", user_type, str(e))
                    break

        # Fetch sections (class periods)
        url = f"{CLEVER_API_BASE}/{CLEVER_API_VERSION}/sections"
        while url:
            try:
                resp = await client.get(url, headers=headers)
                if resp.status_code != 200:
                    break
                body = resp.json()
                result["sections"].extend(body.get("data", []))
                url = _next_page_url(body)
            except httpx.HTTPError as e:
                logger.error("Clever sections fetch error: %s", str(e))
                break

    logger.info(
        "Clever roster sync: %d teachers, %d students, %d sections",
        len(result["teachers"]), len(result["students"]), len(result["sections"]),
    )
    return result


def _next_page_url(body):
    """Extract the next page URL from a Clever API response."""
    for link in body.get("links", []):
        if link.get("rel") == "next":
            url = link.get("uri")
            if url and not url.startswith("http"):
                return f"{CLEVER_API_BASE}{url}"
            return url
    return None


def extract_student_accommodations(students):
    """Convert Clever student data into Graider accommodation mappings.

    Returns dict keyed by Clever student ID:
    {
        "abc123": {
            "name": "First Last",
            "iep_status": True,
            "ell_status": True,
            "home_language": "Spanish",
            "suggested_presets": ["simplified_language", "ell_support", ...],
        }
    }
    """
    accommodations = {}

    for student in students:
        data = student.get("data", student)  # Handle both wrapped and unwrapped
        roles = data.get("roles", {})
        student_role = roles.get("student", {})
        name = data.get("name", {})
        student_id = data.get("id", "")

        iep_status = student_role.get("iep_status", "")
        ell_status = student_role.get("ell_status", "")
        home_language = student_role.get("home_language", "")

        has_iep = str(iep_status).strip().lower() in ("y", "yes", "true", "active")
        has_ell = str(ell_status).strip().lower() in ("y", "yes", "true", "active")

        if not has_iep and not has_ell:
            continue

        # Suggest default presets based on flags
        suggested = []
        if has_iep:
            suggested.extend(["simplified_language", "modified_expectations", "extra_encouragement"])
        if has_ell:
            suggested.append("ell_support")

        accommodations[student_id] = {
            "name": f"{name.get('first', '')} {name.get('last', '')}".strip(),
            "iep_status": has_iep,
            "ell_status": has_ell,
            "home_language": home_language,
            "suggested_presets": suggested,
        }

    return accommodations


def map_sections_to_periods(sections):
    """Convert Clever sections into Graider class periods."""
    periods = []
    for section in sections:
        data = section.get("data", section)
        periods.append({
            "clever_section_id": data.get("id", ""),
            "name": data.get("name", ""),
            "subject": data.get("subject", ""),
            "grade": data.get("grade", ""),
            "teacher_clever_ids": data.get("teachers", []),
            "student_clever_ids": data.get("students", []),
            "period": data.get("period", ""),
            "term_id": data.get("term_id", ""),
        })
    return periods


def persist_roster_as_csv(students, teacher_id="local-dev"):
    """Write Clever students to ROSTERS_DIR as CSV, matching manual upload format.

    Creates 'clever_roster_{teacher_id}.csv' with standard columns.
    Archives previously synced students who are no longer in the roster
    and restores students who reappear.
    """
    os.makedirs(ROSTERS_DIR, exist_ok=True)
    filename = f"clever_roster_{teacher_id}.csv"
    filepath = os.path.join(ROSTERS_DIR, filename)
    archive_path = os.path.join(ROSTERS_DIR, f"clever_roster_{teacher_id}_archived.json")

    # Load previous archive (if any) to track removals/restores
    archived = {}
    if os.path.exists(archive_path):
        with open(archive_path, "r") as f:
            try:
                archived = json.load(f)
            except (json.JSONDecodeError, ValueError):
                archived = {}

    # Current Clever IDs in this sync
    current_ids = set()
    for student in students:
        data = student.get("data", student)
        current_ids.add(data.get("id", ""))

    # Restore any previously archived students who reappeared
    restored = [sid for sid in list(archived.keys()) if sid in current_ids]
    for sid in restored:
        logger.info("Restored previously archived Clever student: %s", sid)
        del archived[sid]

    # Load previous roster IDs to detect removals
    prev_ids = set()
    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                prev_ids.add(row.get("student_id", ""))

    # Archive students who were in previous roster but not in current sync
    newly_archived = prev_ids - current_ids - {""}
    for sid in newly_archived:
        archived[sid] = {"archived_at": datetime.now().isoformat(), "reason": "removed_from_clever"}
        logger.info("Archived Clever student no longer in roster: %s", sid)

    # Save archive file
    if archived:
        with open(archive_path, "w") as f:
            json.dump(archived, f, indent=2)
    elif os.path.exists(archive_path):
        os.remove(archive_path)

    # Write current roster
    with open(filepath, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["student_id", "first_name", "last_name", "email", "grade", "iep_status", "ell_status"])
        for student in students:
            data = student.get("data", student)
            name = data.get("name", {})
            roles = data.get("roles", {})
            sr = roles.get("student", {})
            writer.writerow([
                data.get("id", ""),
                name.get("first", ""),
                name.get("last", ""),
                data.get("email", ""),
                sr.get("grade", ""),
                sr.get("iep_status", ""),
                sr.get("ell_status", ""),
            ])

    # Write metadata file (same format as manual upload)
    metadata = {
        "filename": filename,
        "filepath": filepath,
        "headers": ["student_id", "first_name", "last_name", "email", "grade", "iep_status", "ell_status"],
        "row_count": len(students),
        "source": "clever",
        "column_mapping": {
            "student_id": "student_id",
            "first_name": "first_name",
            "last_name": "last_name",
        },
    }
    meta_path = os.path.join(ROSTERS_DIR, f"{filename}.meta.json")
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)

    logger.info("Persisted Clever roster: %s (%d students, %d archived, %d restored)",
                filepath, len(students), len(newly_archived), len(restored))
    return filepath


def persist_sections_as_periods(sections, teacher_id="local-dev"):
    """Write Clever sections to PERIODS_DIR as JSON, matching manual period format."""
    os.makedirs(PERIODS_DIR, exist_ok=True)
    periods = map_sections_to_periods(sections)

    for period in periods:
        section_id = period.get("clever_section_id", "unknown")
        filename = f"clever_{section_id}.json"
        filepath = os.path.join(PERIODS_DIR, filename)

        period_data = {
            "name": period.get("name", f"Period {period.get('period', '?')}"),
            "subject": period.get("subject", ""),
            "grade": period.get("grade", ""),
            "source": "clever",
            "clever_section_id": section_id,
            "students": period.get("student_clever_ids", []),
        }

        with open(filepath, "w") as f:
            json.dump(period_data, f, indent=2)

        meta = {
            "filename": filename,
            "filepath": filepath,
            "headers": ["name"],
            "row_count": len(period.get("student_clever_ids", [])),
            "source": "clever",
        }
        meta_path = os.path.join(PERIODS_DIR, f"{filename}.meta.json")
        with open(meta_path, "w") as f:
            json.dump(meta, f, indent=2)

    logger.info("Persisted %d Clever sections as periods", len(periods))
    return periods
