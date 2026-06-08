"""
Clever OAuth + API client for Graider.
Handles SSO authentication and Secure Sync roster/IEP data.
"""
import csv
import hashlib
import io
import json
import os
import logging
from datetime import datetime
from urllib.parse import urlencode
from base64 import b64encode

import asyncio

import httpx
import sentry_sdk

from backend.utils.audit import audit_log

logger = logging.getLogger(__name__)

MAX_RETRIES = 5

CLEVER_AUTH_URL = "https://clever.com/oauth/authorize"
CLEVER_TOKEN_URL = "https://clever.com/oauth/tokens"
CLEVER_API_BASE = "https://api.clever.com"
CLEVER_API_VERSION = os.getenv("CLEVER_API_VERSION", "v3.0")

# Clever roles permitted to access the teacher dashboard (deny-by-default).
# A Clever `contact` is a parent/guardian and must NEVER reach teacher views —
# it would expose student data (FERPA). `school_admin` is a harmless legacy
# entry (Clever API v3 folds school admins into `staff`; see get_clever_user).
# The role is resolved from the /users/{id} `roles` object in get_clever_user;
# this allowlist gates both the SSO callback (login) and check_auth (session
# validation), so a non-educator can neither log in nor ride a stale cookie.
EDUCATOR_ROLES = frozenset({"teacher", "staff", "district_admin", "school_admin"})

# Graider data directories (same paths as settings_routes.py / storage.py)
GRAIDER_DATA_DIR = os.path.expanduser("~/.graider_data")
ROSTERS_DIR = os.path.join(GRAIDER_DATA_DIR, "rosters")
PERIODS_DIR = os.path.join(GRAIDER_DATA_DIR, "periods")


def get_clever_config():
    """Return Clever credentials from district config or environment."""
    # Check district-level config first
    try:
        from backend.storage import load
        district_cfg = load("district:sis_config", "system")
        if district_cfg and district_cfg.get("sis_type") == "clever":
            redirect_uri = district_cfg.get("redirect_uri") or os.getenv("CLEVER_REDIRECT_URI")
            return {
                "client_id": district_cfg.get("client_id"),
                "client_secret": district_cfg.get("client_secret"),
                "redirect_uri": redirect_uri,
            }
    except Exception as e:
        sentry_sdk.capture_exception(e)

    # Fall back to environment variables
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
                logger.error("Clever token exchange failed: status=%s", resp.status_code)
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

            # API v3.0: /me returns data.type="user" for EVERY record — the
            # role lives in the /users/{id} `roles` object instead. See
            # https://dev.clever.com/docs/migrating-to-api-30 ("The type field
            # on /me will now return 'user' for any user records"). Resolve the
            # real role from `roles`, preferring student (students are limited
            # to the student role per Clever) then the highest-privilege
            # non-student role so the district-admin gate (clever_routes.py
            # `type != 'district_admin'`) stays reachable for multi-role users.
            # Fall back to the /me type for API v2.x (where it IS the role) or
            # when `roles` is unexpectedly absent.
            roles = user_data.get("roles", {}) or {}
            if "student" in roles:
                user_type = "student"
            elif "district_admin" in roles:
                user_type = "district_admin"
            elif "teacher" in roles:
                user_type = "teacher"
            elif "staff" in roles:
                user_type = "staff"
            elif roles:
                user_type = next(iter(roles))

            audit_log(
                "CLEVER_USER_READ",
                f"clever_user_type={user_type}",
                teacher_id=str(user_id),
            )
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


async def _clever_get_with_retry(client, url, headers, label=""):
    """GET with exponential backoff on 429 (rate limit) and 5xx errors.

    Per Clever docs: 1,200 req/min per token, retry with backoff on 429/5xx,
    stop after MAX_RETRIES attempts.
    """
    resp = None
    for attempt in range(MAX_RETRIES):
        try:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                return resp
            if resp.status_code == 429:
                wait = 2 ** attempt
                logger.warning("Clever rate limited (%s), retrying in %ds (attempt %d/%d)",
                               label, wait, attempt + 1, MAX_RETRIES)
                await asyncio.sleep(wait)
                continue
            if resp.status_code >= 500:
                wait = 2 ** attempt
                logger.warning("Clever %d error (%s), retrying in %ds (attempt %d/%d)",
                               resp.status_code, label, wait, attempt + 1, MAX_RETRIES)
                await asyncio.sleep(wait)
                continue
            # 4xx (not 429) — don't retry
            logger.error("Clever API error (%s): %s %s", label, resp.status_code, resp.text[:200])
            return resp
        except httpx.HTTPError as e:
            wait = 2 ** attempt
            logger.warning("Clever HTTP error (%s): %s, retrying in %ds (attempt %d/%d)",
                           label, str(e), wait, attempt + 1, MAX_RETRIES)
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(wait)
                continue
            raise
    return resp  # Return last response after exhausting retries


async def sync_roster(district_token):
    """Sync full roster from Clever using a district-app token.

    Returns dict: { "teachers": [...], "students": [...], "sections": [...] }
    Handles rate limiting (429) and server errors (5xx) with exponential backoff.
    """
    headers = {"Authorization": f"Bearer {district_token}"}
    result = {"teachers": [], "students": [], "sections": []}

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Fetch all users (paginated)
        for user_type in ["teachers", "students"]:
            url = f"{CLEVER_API_BASE}/{CLEVER_API_VERSION}/users?role={user_type[:-1]}"
            while url:
                try:
                    resp = await _clever_get_with_retry(client, url, headers, label=user_type)
                    if resp.status_code != 200:
                        logger.error("Clever roster fetch (%s) failed: %s", user_type, resp.status_code)
                        break
                    body = resp.json()
                    result[user_type].extend(body.get("data", []))
                    url = _next_page_url(body)
                except httpx.HTTPError as e:
                    logger.error("Clever roster fetch error (%s): %s", user_type, str(e))
                    sentry_sdk.capture_exception(e)
                    break

        # Fetch sections (class periods)
        url = f"{CLEVER_API_BASE}/{CLEVER_API_VERSION}/sections"
        while url:
            try:
                resp = await _clever_get_with_retry(client, url, headers, label="sections")
                if resp.status_code != 200:
                    break
                body = resp.json()
                result["sections"].extend(body.get("data", []))
                url = _next_page_url(body)
            except httpx.HTTPError as e:
                logger.error("Clever sections fetch error: %s", str(e))
                sentry_sdk.capture_exception(e)
                break

        # Fetch contacts/guardians (parent data)
        url = f"{CLEVER_API_BASE}/{CLEVER_API_VERSION}/users?role=contact"
        while url:
            try:
                resp = await _clever_get_with_retry(client, url, headers, label="contacts")
                if resp.status_code != 200:
                    break
                body = resp.json()
                result.setdefault("contacts", []).extend(body.get("data", []))
                url = _next_page_url(body)
            except httpx.HTTPError as e:
                logger.warning("Clever contacts fetch error (non-blocking): %s", str(e))
                sentry_sdk.capture_exception(e)
                break

    logger.info(
        "Clever roster sync: %d teachers, %d students, %d sections, %d contacts",
        len(result["teachers"]), len(result["students"]),
        len(result["sections"]), len(result.get("contacts", [])),
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


def _safe_teacher_id(teacher_id):
    """Sanitize teacher_id for use in filenames (colon is illegal on Windows)."""
    return teacher_id.replace(":", "_")


def persist_roster_as_csv(students, teacher_id="local-dev"):
    """Write Clever students to ROSTERS_DIR as CSV, matching manual upload format.

    Creates 'clever_roster_{teacher_id}.csv' with standard columns.
    Archives previously synced students who are no longer in the roster
    and restores students who reappear.
    """
    os.makedirs(ROSTERS_DIR, exist_ok=True)
    safe_id = _safe_teacher_id(teacher_id)
    filename = f"clever_roster_{safe_id}.csv"
    filepath = os.path.join(ROSTERS_DIR, filename)
    archive_path = os.path.join(ROSTERS_DIR, f"clever_roster_{safe_id}_archived.json")

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
        logger.info("Restored previously archived Clever student: %s",
                    hashlib.sha256(str(sid).encode()).hexdigest()[:8])
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
        logger.info("Archived Clever student no longer in roster: %s",
                    hashlib.sha256(str(sid).encode()).hexdigest()[:8])

    # Save archive file
    if archived:
        with open(archive_path, "w") as f:
            json.dump(archived, f, indent=2)
    elif os.path.exists(archive_path):
        os.remove(archive_path)

    # Load manual overrides (teacher edits that should survive sync)
    overrides_path = os.path.join(ROSTERS_DIR, f"clever_roster_{safe_id}_overrides.json")
    overrides = {}
    if os.path.exists(overrides_path):
        with open(overrides_path, "r") as f:
            try:
                overrides = json.load(f)
            except (json.JSONDecodeError, ValueError):
                overrides = {}

    # Write current roster (merging manual overrides where they exist)
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["student_id", "first_name", "last_name", "email", "grade", "iep_status", "ell_status"])
        for student in students:
            data = student.get("data", student)
            name = data.get("name", {})
            roles = data.get("roles", {})
            sr = roles.get("student", {})
            sid = data.get("id", "")

            # Apply manual overrides if teacher has edited this student
            student_overrides = overrides.get(sid, {})

            writer.writerow([
                sid,
                student_overrides.get("first_name", name.get("first", "")),
                student_overrides.get("last_name", name.get("last", "")),
                student_overrides.get("email", data.get("email", "")),
                student_overrides.get("grade", sr.get("grade", "")),
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


def extract_parent_contacts(contacts, students):
    """Map Clever contacts (guardians) to students for parent contact data.

    Returns dict keyed by student Clever ID:
    {
        "student_id": {
            "parent_emails": ["parent@email.com"],
            "parent_phones": ["555-1234"],
        }
    }
    """
    # Build student ID set for filtering
    student_ids = set()
    for s in students:
        data = s.get("data", s)
        student_ids.add(data.get("id", ""))

    result = {}
    for contact in contacts:
        data = contact.get("data", contact)
        email = data.get("email", "")
        phone = data.get("phone", "")
        relationships = data.get("student_relationships", [])

        for rel in relationships:
            sid = rel.get("student", "")
            if sid not in student_ids:
                continue
            entry = result.setdefault(sid, {"parent_emails": [], "parent_phones": []})
            if email and email not in entry["parent_emails"]:
                entry["parent_emails"].append(email)
            if phone and phone not in entry["parent_phones"]:
                entry["parent_phones"].append(phone)

    logger.info("Extracted parent contacts for %d students from %d contacts",
                len(result), len(contacts))
    return result


def persist_parent_contacts(contact_map, teacher_id="local-dev"):
    """Merge Clever parent contacts into a per-teacher contacts file.

    Files are scoped by teacher_id to prevent cross-teacher data access.
    Multi-tenant isolation is also handled by the Supabase storage layer.
    """
    safe_id = _safe_teacher_id(teacher_id)
    contacts_dir = os.path.join(GRAIDER_DATA_DIR, "contacts")
    os.makedirs(contacts_dir, exist_ok=True)
    contacts_file = os.path.join(contacts_dir, f"parent_contacts_{safe_id}.json")

    existing = {}
    if os.path.exists(contacts_file):
        try:
            with open(contacts_file, "r") as f:
                existing = json.load(f)
        except (json.JSONDecodeError, ValueError):
            existing = {}

    # Merge — Clever data supplements existing; don't overwrite manual entries
    for sid, data in contact_map.items():
        entry = existing.setdefault(sid, {"parent_emails": [], "parent_phones": []})
        for email in data.get("parent_emails", []):
            if email not in entry.get("parent_emails", []):
                entry.setdefault("parent_emails", []).append(email)
        for phone in data.get("parent_phones", []):
            if phone not in entry.get("parent_phones", []):
                entry.setdefault("parent_phones", []).append(phone)

    os.makedirs(os.path.dirname(contacts_file), exist_ok=True)
    with open(contacts_file, "w") as f:
        json.dump(existing, f, indent=2)

    logger.info("Persisted parent contacts: %d students total", len(existing))


def delete_clever_data(teacher_id="local-dev"):
    """Delete Clever-synced student data for a teacher (FERPA right-to-delete).

    Delegates roster rows + roster CSVs to the shared `delete_roster_data`, then
    purges the Clever-specific student/guardian-PII artifacts that the roster
    delete misses:
      - period/section files (PERIODS_DIR/clever_{section_id}.json[.meta.json]),
        scoped via the teacher's classes->clever_section_id mapping captured
        BEFORE delete_roster_data drops those class rows (the files are keyed by
        section_id, not teacher_id, so this is the only way to scope them);
      - the per-teacher parent-contact file (guardian emails/phones);
      - per-student history (scores) and accommodation mappings (IEP/ELL).

    Scope boundary: teacher-AUTHORED content (teacher_data assignment
    templates / settings / rubric, published_assessments) is intentionally NOT
    purged — a Clever data deletion targets student PII, not the educator's own
    work. A full account purge would be a separate, deliberate operation.

    Returns the delete_roster_data dict augmented with per-artifact counts.
    """
    from backend.roster_sync import delete_roster_data
    from backend import storage

    # Capture this teacher's Clever section_ids BEFORE delete_roster_data drops
    # the classes rows. Period files are keyed by section_id (no teacher_id), so
    # the class->section mapping is the only way to scope them to this teacher.
    section_ids = []
    sb = None
    try:
        from backend.supabase_client import get_supabase
        sb = get_supabase()
        if sb:
            res = (sb.table("classes").select("clever_section_id")
                   .eq("teacher_id", teacher_id).execute())
            section_ids = [c["clever_section_id"] for c in (res.data or [])
                           if c.get("clever_section_id")]
    except Exception as e:
        logger.warning("Could not enumerate Clever sections for deletion (%s): %s",
                       teacher_id, type(e).__name__)
        sentry_sdk.capture_exception(e)
        sb = None

    result = delete_roster_data(teacher_id)

    if sb is None:
        # Period files are section-keyed (no teacher_id in the filename), so
        # without the classes->section mapping we cannot safely scope them.
        # Surface the residual rather than silently leaving section-keyed PII on
        # disk; the operator can re-run the delete once the DB is reachable.
        logger.warning(
            "Clever delete for %s: Supabase unavailable — section-keyed period "
            "files could not be scoped and may persist; re-run when DB is reachable",
            teacher_id,
        )
        result["period_files_skipped"] = True

    # Period/section files (+ their .meta.json sidecars), scoped to this teacher.
    periods_removed = 0
    for sid in section_ids:
        for fname in (f"clever_{sid}.json", f"clever_{sid}.json.meta.json"):
            fpath = os.path.join(PERIODS_DIR, fname)
            try:
                if os.path.exists(fpath):
                    os.remove(fpath)
                    periods_removed += 1
            except OSError as e:
                logger.warning("Failed to delete period file %s: %s", fpath, e)
                sentry_sdk.capture_exception(e)
    result["period_files"] = periods_removed

    # Per-teacher parent-contact file (guardian PII).
    safe_id = _safe_teacher_id(teacher_id)
    contacts_file = os.path.join(GRAIDER_DATA_DIR, "contacts",
                                 f"parent_contacts_{safe_id}.json")
    result["parent_contact_files"] = 0
    try:
        if os.path.exists(contacts_file):
            os.remove(contacts_file)
            result["parent_contact_files"] = 1
    except OSError as e:
        logger.warning("Failed to delete parent-contact file %s: %s", contacts_file, e)
        sentry_sdk.capture_exception(e)

    # Per-student history (scores) — student PII, tenant-scoped storage.
    hist_deleted = 0
    try:
        for sid in storage.list_student_history(teacher_id):
            if storage.delete_student_history(teacher_id, sid):
                hist_deleted += 1
    except Exception as e:
        logger.warning("student_history deletion failed (%s): %s",
                       teacher_id, type(e).__name__)
        sentry_sdk.capture_exception(e)
    result["student_history"] = hist_deleted

    # Accommodation mappings (IEP/ELL flags) — student PII. Removes the teacher's
    # whole 'accommodations' blob; the students it maps to are being deleted.
    try:
        storage.delete("accommodations", teacher_id)
        result["accommodations"] = "deleted"
    except Exception as e:
        logger.warning("accommodations deletion failed (%s): %s",
                       teacher_id, type(e).__name__)
        sentry_sdk.capture_exception(e)
        result["accommodations"] = "error"

    # Scrub student PII embedded in this teacher's join-code published
    # assessments. settings.student_accommodations is {student_name: settings}
    # and settings.restricted_students is [student_name] — both are student PII
    # (and can carry Clever-sourced IEP/504 context). We UPDATE rather than
    # delete the rows: the assessment itself is the teacher's authored content,
    # but the embedded roster snapshot must not survive a FERPA delete.
    scrubbed = 0
    if sb is not None:
        try:
            rows = (sb.table("published_assessments").select("id,settings")
                    .eq("teacher_id", teacher_id).execute())
            for row in (rows.data or []):
                settings = row.get("settings") or {}
                if settings.get("student_accommodations") or settings.get("restricted_students"):
                    settings.pop("student_accommodations", None)
                    settings.pop("restricted_students", None)
                    (sb.table("published_assessments").update({"settings": settings})
                     .eq("id", row["id"]).execute())
                    scrubbed += 1
        except Exception as e:
            logger.warning("published_assessments PII scrub failed (%s): %s",
                           teacher_id, type(e).__name__)
            sentry_sdk.capture_exception(e)
    result["published_assessments_scrubbed"] = scrubbed

    return result
