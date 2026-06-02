"""
ClassLink OAuth2/OIDC SSO Routes
=================================
Mirrors the Clever SSO pattern (clever_routes.py) for ClassLink LaunchPad.

Endpoints:
  GET  /api/classlink/login-url  — Get ClassLink OAuth authorization URL
  GET  /api/classlink/callback   — OAuth callback (ClassLink redirects here)
  GET  /api/classlink/session    — Check ClassLink session status
  POST /api/classlink/logout     — Clear ClassLink session
"""

import hashlib
import hmac
import os
import time
import logging
import secrets

import jwt as pyjwt
import requests
import sentry_sdk
from flask import Blueprint, request, redirect, jsonify, session, g
import urllib.parse
from urllib.parse import urlencode

from backend.auth import resolve_classlink_user_id
from backend.routes.sso_admin import apply_sso_admin_designation
from backend.supabase_client import get_supabase
from backend.utils.audit import audit_log
from backend.utils.auth_decorators import require_teacher
from backend.utils.errors import handle_route_errors
from backend.utils.redaction import redact_email

from backend.services.classlink_oidc import (
    ClassLinkOIDCError,
    get_classlink_oidc_config,
    get_classlink_jwks_client,
)

logger = logging.getLogger(__name__)

classlink_bp = Blueprint('classlink', __name__)

# ClassLink OAuth2 endpoints
CLASSLINK_AUTH_URL = 'https://launchpad.classlink.com/oauth2/v2/auth'
CLASSLINK_TOKEN_URL = 'https://launchpad.classlink.com/oauth2/v2/token'
CLASSLINK_USERINFO_URL = 'https://nodeapi.classlink.com/v2/my/info'

CLASSLINK_SCOPES = 'profile oneroster email openid'


def _get_classlink_config():
    """Get ClassLink OAuth config from environment."""
    client_id = os.environ.get('CLASSLINK_CLIENT_ID', '')
    client_secret = os.environ.get('CLASSLINK_CLIENT_SECRET', '')
    redirect_uri = os.environ.get(
        'CLASSLINK_REDIRECT_URI',
        'https://app.graider.live/api/classlink/callback'
    )
    return client_id, client_secret, redirect_uri


def _classlink_guid(tenant_id, person_id):
    """Build the tenant-scoped ClassLink identity GUID.

    Format: ``classlink:{tenant}:{person}`` with each component percent-encoded
    so a literal ':' inside a component cannot create an ambiguous (colliding)
    GUID. Mirrors ClassLink's recommended TenantId+SourcedId globally-unique id.

    Returns None if either component is empty (caller MUST fail closed).
    """
    tenant = str(tenant_id or "").strip()
    person = str(person_id or "").strip()
    if not tenant or not person:
        return None
    return (
        "classlink:"
        + urllib.parse.quote(tenant, safe="")
        + ":"
        + urllib.parse.quote(person, safe="")
    )


def _classlink_roster_external_id(tenant_id, sourced_id):
    """Tenant-scoped roster external_id for ClassLink rows.

    Format: ``classlink:{quote(tenant)}:{quote(sourced_id)}`` — same encoding as
    ``_classlink_guid`` so a ':' inside a component cannot create a colliding key.
    Used on BOTH sides: the roster write (via normalize_roster builder) and the
    student-SSO lookup. Always returns a string (tolerant of empty components,
    matching normalize_roster).
    """
    tenant = urllib.parse.quote(str(tenant_id or "").strip(), safe="")
    sid = urllib.parse.quote(str(sourced_id or "").strip(), safe="")
    return f"classlink:{tenant}:{sid}"


# Short-lived auth codes for student ClassLink SSO (code -> {token, expires})
_pending_classlink_student_auth_codes = {}
_CLASSLINK_AUTH_CODE_TTL = 60  # seconds


def _create_classlink_student_auth_code(raw_token):
    """Mint a short-lived code the SPA exchanges for the real session token."""
    code = secrets.token_urlsafe(32)
    _pending_classlink_student_auth_codes[code] = {
        "token": raw_token, "expires": time.time() + _CLASSLINK_AUTH_CODE_TTL,
    }
    now = time.time()
    for k in [k for k, v in _pending_classlink_student_auth_codes.items() if v["expires"] < now]:
        del _pending_classlink_student_auth_codes[k]
    return code


# Short-lived selection tokens for the multi-enrollment picker.
_pending_classlink_class_selections = {}
_CLASSLINK_CLASS_SELECTION_TTL = 120  # seconds


def _public_classlink_candidates(candidates):
    """Browser-safe projection — strips the server-only `_student_row` (PII)."""
    return [
        {"class_id": c["class_id"], "name": c.get("name", ""), "subject": c.get("subject", "")}
        for c in candidates
    ]


def _create_classlink_class_selection(candidates):
    """Mint a short-lived token the student exchanges (with a chosen class_id)."""
    code = secrets.token_urlsafe(32)
    _pending_classlink_class_selections[code] = {
        "candidates": candidates, "expires": time.time() + _CLASSLINK_CLASS_SELECTION_TTL,
    }
    now = time.time()
    for k in [k for k, v in _pending_classlink_class_selections.items() if v["expires"] < now]:
        del _pending_classlink_class_selections[k]
    return code


def _mint_classlink_student_session(sb, student_row, chosen):
    """Insert a hashed student_sessions row and return {token, student, class}.

    Mirrors the Clever mint; duplicated (not shared) to keep the certified
    Clever path byte-identical (Class B blast-radius discipline)."""
    from datetime import datetime, timezone, timedelta

    raw_token = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    expires = datetime.now(tz=timezone.utc) + timedelta(hours=8)

    sb.table("student_sessions").insert({
        "student_id": student_row["id"],
        "class_id": chosen["class_id"],
        "session_token": token_hash,
        "expires_at": expires.isoformat(),
    }).execute()

    return {
        "token": raw_token,
        "student": {
            "first_name": student_row.get("first_name", ""),
            "last_name": student_row.get("last_name", ""),
            "email": student_row.get("email", ""),
            "student_id": student_row.get("student_id_number", ""),
            "period": student_row.get("period", ""),
        },
        "class": {"name": chosen.get("name", ""), "subject": chosen.get("subject", "")},
    }


def _create_classlink_student_session(tenant_id, person_id):
    """Resolve a rostered ClassLink student to their provisioned record and
    mint a session, tenant-scoped and FAIL-CLOSED.

    Returns {token,...} for a single enrollment, a needs_class_selection payload
    for multiple, or None when no provisioned row matches the tenant-scoped key
    (NO email fallback — that would risk a cross-tenant match)."""
    sb = get_supabase()
    if sb is None:
        logger.debug("Supabase not configured — cannot create ClassLink student session")
        return None

    try:
        key = _classlink_roster_external_id(tenant_id, person_id)
        res = sb.table("students").select("*").eq("student_id_number", key).execute()
        student_rows = list(res.data) if res and res.data else []
        if not student_rows:
            return None  # fail closed — no email fallback

        candidates = []
        seen = set()
        for srow in student_rows:
            srow_id = srow.get("id")
            if not srow_id:
                continue
            enroll = (
                sb.table("class_students")
                .select("class_id, classes(id, name, subject)")
                .eq("student_id", srow_id)
                .execute()
            )
            for er in (enroll.data if enroll and enroll.data else []):
                ci = er.get("classes") or {}
                cid = ci.get("id") or er.get("class_id")
                if not cid or cid in seen:
                    continue
                seen.add(cid)
                candidates.append({
                    "class_id": cid, "name": ci.get("name", ""),
                    "subject": ci.get("subject", ""), "_student_row": srow,
                })

        if not candidates:
            return None
        if len(candidates) > 1:
            selection_token = _create_classlink_class_selection(candidates)
            return {
                "status": "needs_class_selection",
                "classes": _public_classlink_candidates(candidates),
                "selection_token": selection_token,
            }
        chosen = candidates[0]
        return _mint_classlink_student_session(sb, chosen["_student_row"], chosen)
    except Exception as e:
        logger.warning("Failed to create ClassLink student session: %s", str(e))
        sentry_sdk.capture_exception(e)
        return None


def _extract_person_id(user_data):
    """Resolve the person component of the GUID from the ClassLink userinfo body.

    Precedence: OneRoster ``SourcedId`` (preferred — reconciles with rostering),
    then ``UserId``. NEVER falls back to the OIDC ``sub`` alone, which is not
    guaranteed to equal the OneRoster sourcedId. Returns None if absent (caller
    fails closed). When falling back to UserId, logs a warning (not silent).
    """
    sourced = str(user_data.get("SourcedId") or user_data.get("sourcedId") or "").strip()
    if sourced:
        return sourced
    user_id = str(user_data.get("UserId") or "").strip()
    if user_id:
        logger.warning("ClassLink userinfo has no SourcedId; using UserId as person id")
        return user_id
    return None


def _run_classlink_roster_sync(teacher_id, tenant_id):
    """Synchronous ClassLink roster sync (OneRoster 1.1 endpoints).

    Writes tenant-scoped external_ids so ClassLink roster rows never collide
    with OneRoster rows or across tenants. Extracted from _trigger_roster_sync
    so it is unit-testable without a thread.
    """
    from backend.oneroster import OneRosterClient, normalize_roster, get_oneroster_config
    from backend.roster_sync import sync_roster_to_db
    import asyncio

    config = get_oneroster_config(teacher_id)
    if not config or not config.get('base_url') or not config.get('client_id') or not config.get('client_secret'):
        logger.info("No usable OneRoster config for %s, skipping post-login roster sync", teacher_id)
        return

    client = OneRosterClient(
        base_url=config['base_url'],
        client_id=config['client_id'],
        client_secret=config['client_secret'],
        token_url=config.get('token_url'),
    )
    loop = asyncio.new_event_loop()
    try:
        raw = loop.run_until_complete(client.fetch_roster(
            school_id=config.get('school_id'),
            teacher_sourced_id=config.get('teacher_sourced_id'),
        ))
    finally:
        loop.close()

    classes, students_norm, enrollments, _accommodations = normalize_roster(
        raw, external_id_for=lambda sid: _classlink_roster_external_id(tenant_id, sid)
    )
    enrollment_tuples = [
        (e["class_external_id"], e["student_external_id"]) for e in enrollments
    ]
    sync_roster_to_db(classes, students_norm, enrollment_tuples, teacher_id, provider="classlink")
    logger.info("Post-login ClassLink roster sync complete for %s", teacher_id)


def _trigger_roster_sync(teacher_id, tenant_id):
    """Trigger background ClassLink roster sync after login (OneRoster 1.1)."""
    import threading

    def _bg_sync():
        try:
            _run_classlink_roster_sync(teacher_id, tenant_id)
        except Exception as e:
            logger.warning("Post-login ClassLink roster sync failed for %s: %s", teacher_id, e)
            sentry_sdk.capture_exception(e)

    thread = threading.Thread(target=_bg_sync, daemon=True)
    thread.start()


# ── GET /api/classlink/login-url ──────────────────────────────────────

@classlink_bp.route('/api/classlink/login-url', methods=['GET'])
def classlink_login_url():
    """Return ClassLink OAuth authorization URL with CSRF state token and nonce."""
    client_id, _, redirect_uri = _get_classlink_config()
    if not client_id:
        # In redirect mode (top-level nav from the landing page) a JSON body
        # would render as a raw page; bounce to a friendly error instead.
        if request.args.get("redirect"):
            return redirect("/?classlink_error=not_configured")
        return jsonify({"error": "ClassLink SSO is not configured"}), 400

    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    session['classlink_oauth_state'] = state
    session['classlink_oauth_nonce'] = nonce
    session['classlink_oauth_initiated_by_us'] = True

    params = urlencode({
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': CLASSLINK_SCOPES,
        'state': state,
        'nonce': nonce,
    })
    auth_url = f"{CLASSLINK_AUTH_URL}?{params}"
    # ?redirect=1 → 302 straight to ClassLink instead of returning JSON. Used by
    # the cross-origin landing page (graider.live): a top-level navigation here
    # sets the session cookie (oauth_state/nonce/initiated_by_us) first-party for
    # app.graider.live — a cross-origin fetch would discard it, dropping the
    # initiated_by_us marker and the student→/join carve-out.
    if request.args.get("redirect"):
        return redirect(auth_url)
    return jsonify({"url": auth_url})


# ── GET /api/classlink/callback ───────────────────────────────────────

@classlink_bp.route('/api/classlink/callback', methods=['GET'])
def classlink_callback():
    """Handle ClassLink OAuth callback — exchange code for token, fetch user."""
    error = request.args.get('error')
    if error:
        return redirect(f"/?classlink_error={error}")

    code = request.args.get('code')
    if not code:
        return redirect("/?classlink_error=no_code")

    # PEEK at OAuth-flow session markers without popping. Markers persist
    # until successful validation completes (cleared at the end of this
    # function). This prevents a rejected callback (wrong state, expired
    # token, nonce mismatch) from popping the markers and downgrading the
    # next callback in the same session to the permissive LaunchPad path —
    # which would otherwise allow an attacker to bypass CSRF defense by
    # triggering one rejected callback first. Markers are overwritten by a
    # fresh /api/classlink/login-url call or expire with the session.
    state = request.args.get('state', '')
    expected_state = session.get('classlink_oauth_state', '')
    expected_nonce = session.get('classlink_oauth_nonce', '')
    initiated_by_us = session.get('classlink_oauth_initiated_by_us', False)

    # Validate CSRF state (flow-aware)
    # Self-initiated flows (login-url was called) require strict state match.
    # LaunchPad-initiated flows (ClassLink redirects directly, no login-url call)
    # have no state requirement — id_token signature validation (below) is the
    # auth proof. This mirrors Clever's "Instant Login" pattern.
    if initiated_by_us:
        # Strict mode: state must be present and match exactly. Use
        # hmac.compare_digest for constant-time compare (issue #373).
        if not state or not hmac.compare_digest(
            state.encode("utf-8"),
            (expected_state or "").encode("utf-8"),
        ):
            # Log presence booleans only — state/nonce values are auth secrets
            # that should not be persisted in logs even on rejected requests.
            audit_log(
                "CLASSLINK_OAUTH_STATE_MISMATCH",
                "ClassLink state mismatch on self-initiated flow: "
                f"state_present={bool(state)} expected_present={bool(expected_state)}",
                user="anonymous",
                teacher_id="",
            )
            logger.warning(
                "ClassLink OAuth state mismatch (self-initiated): "
                "state_present=%s expected_present=%s",
                bool(state),
                bool(expected_state),
            )
            return redirect("/?classlink_error=state_mismatch")
    else:
        # Permissive mode: LaunchPad-initiated — id_token signature is the auth proof.
        # Only emit a warning + audit-log if both sides have state but they differ
        # (session pollution or attacker probe). Do NOT reject: LaunchPad is permissive.
        if expected_state and state and not hmac.compare_digest(
            state.encode("utf-8"), expected_state.encode("utf-8"),
        ):
            logger.warning(
                "ClassLink OAuth state mismatch (LaunchPad): "
                "state_present=%s expected_present=%s",
                bool(state),
                bool(expected_state),
            )
            audit_log(
                "CLASSLINK_OAUTH_LAUNCHPAD_STATE_MISMATCH",
                "unexpected state on LaunchPad-initiated flow: "
                f"state_present={bool(state)} expected_present={bool(expected_state)}",
                user="anonymous",
                teacher_id="",
            )

    client_id, client_secret, redirect_uri = _get_classlink_config()

    # Exchange code for token
    try:
        token_resp = requests.post(CLASSLINK_TOKEN_URL, data={
            'client_id': client_id,
            'client_secret': client_secret,
            'code': code,
            'redirect_uri': redirect_uri,
            'grant_type': 'authorization_code',
        }, timeout=15)

        if token_resp.status_code != 200:
            logger.error("ClassLink token exchange failed: %s %s",
                         token_resp.status_code, token_resp.text[:200])
            return redirect("/?classlink_error=token_failed")

        token_data = token_resp.json()
        access_token = token_data.get('access_token')
        if not access_token:
            return redirect("/?classlink_error=no_token")

        id_token = token_data.get('id_token')
        if not id_token:
            logger.warning("ClassLink token response missing id_token")
            return redirect("/?classlink_error=no_id_token")

    except Exception as e:
        logger.exception("ClassLink token exchange error: %s", e)
        return redirect("/?classlink_error=token_error")

    # Validate id_token: signature, iss, aud, exp
    # client_id is bound from the token-exchange block above; reuse it for audience.
    try:
        oidc_cfg = get_classlink_oidc_config()
        jwks_client = get_classlink_jwks_client()
        signing_key = jwks_client.get_signing_key_from_jwt(id_token)
        id_claims = pyjwt.decode(
            id_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=client_id,
            issuer=oidc_cfg.get("issuer"),
            leeway=10,
            options={
                # OIDC Core §2 lists the REQUIRED id_token claims as
                # iss/sub/aud/exp/iat (+ nonce when sent). `nbf` is NOT
                # required — real ClassLink id_tokens omit it. Requiring
                # it here caused `MissingRequiredClaimError` on every
                # ClassLink token (2026-05-28 incident, surfaced via
                # Better Stack: `Token is missing the "nbf" claim`).
                # pyjwt's `verify_nbf` default is True, so if a future
                # ClassLink build starts sending `nbf` it will still be
                # enforced — we just stop demanding it be present.
                "require": ["iat", "exp", "iss", "aud", "sub"],
                "verify_iat": True,
            },
        )
    except pyjwt.ExpiredSignatureError:
        logger.warning("ClassLink id_token expired")
        return redirect("/?classlink_error=oidc_expired")
    except (pyjwt.InvalidAudienceError, pyjwt.InvalidIssuerError) as e:
        logger.warning("ClassLink id_token claim mismatch: %s", e.__class__.__name__)
        return redirect("/?classlink_error=oidc_claim_mismatch")
    except (pyjwt.PyJWTError, ClassLinkOIDCError) as e:
        # Log BOTH the class name AND the wrapped payload (`%s` on `e` invokes
        # str(e)). pyjwt wraps several underlying failure modes (HTTP errors
        # from the JWKS fetch, TLS errors, signature errors, missing-key
        # errors) in a single `PyJWKClientConnectionError` / `PyJWTError`
        # surface — the wrapped payload is what distinguishes them. The 2026-05-28
        # incident in .claude/rules/workflow.md is exactly the case where the
        # wrapper class name was treated as load-bearing signal and the
        # wrapped `"HTTP Error 401: Unauthorized"` payload was lost.
        logger.warning(
            "ClassLink id_token validation failed: %s: %s",
            e.__class__.__name__, e,
        )
        sentry_sdk.capture_exception(e)
        return redirect("/?classlink_error=oidc_invalid")

    # iat sanity window: reject tokens minted >5 min in the future or >1 day stale.
    # Defense-in-depth against misconfigured ClassLink tenants issuing long-lived tokens.
    now_ts = time.time()
    iat = id_claims.get("iat", 0)
    if iat > now_ts + 300:
        logger.warning("ClassLink id_token iat is in the future")
        return redirect("/?classlink_error=oidc_invalid")
    if iat < now_ts - 86400:
        logger.warning("ClassLink id_token iat is more than 24h old")
        return redirect("/?classlink_error=oidc_invalid")

    # Nonce check (self-initiated flows only)
    # initiated_by_us and expected_nonce were peeked at the top of the
    # function; markers remain in session and are cleared on success below.
    if initiated_by_us:
        token_nonce = id_claims.get('nonce', '')
        if not token_nonce or not hmac.compare_digest(
            token_nonce.encode("utf-8"),
            (expected_nonce or "").encode("utf-8"),
        ):
            audit_log("CLASSLINK_OAUTH_NONCE_MISMATCH",
                      "ClassLink nonce mismatch on self-initiated flow",
                      user="anonymous", teacher_id="")
            logger.warning("ClassLink id_token nonce mismatch (self-initiated)")
            return redirect("/?classlink_error=nonce_mismatch")

    # Fetch user info (userinfo becomes fallback for non-OIDC fields like TenantId)
    try:
        user_resp = requests.get(CLASSLINK_USERINFO_URL, headers={
            'Authorization': f'Bearer {access_token}',
        }, timeout=15)

        if user_resp.status_code != 200:
            logger.error("ClassLink user info failed: %s", user_resp.status_code)
            return redirect("/?classlink_error=userinfo_failed")

        user_data = user_resp.json()
    except Exception as e:
        logger.exception("ClassLink user info error: %s", e)
        return redirect("/?classlink_error=userinfo_error")

    # OIDC Core: if userinfo carries a `sub`, it MUST equal the id_token `sub`
    # before we trust any other userinfo claim.
    userinfo_sub = str(user_data.get('sub', '') or '')
    if userinfo_sub and userinfo_sub != str(id_claims.get('sub', '') or ''):
        logger.warning("ClassLink userinfo sub does not match id_token sub")
        return redirect("/?classlink_error=identity_mismatch")

    # Standard OIDC fields prefer the signed id_token; ClassLink-specific fields
    # (TenantId, SourcedId, Role) come from userinfo.
    first_name = id_claims.get('given_name') or user_data.get('FirstName', '')
    last_name = id_claims.get('family_name') or user_data.get('LastName', '')
    email = id_claims.get('email') or user_data.get('Email', '')

    # Role may arrive as a string, a comma-separated string, or a list.
    raw_role = id_claims.get('Role') or user_data.get('Role') or ''
    if isinstance(raw_role, (list, tuple)):
        raw_role = raw_role[0] if raw_role else ''
    role = str(raw_role).split(',')[0].strip().lower()

    # Tenant-scoped identity (fail closed — never a non-scoped fallback).
    tenant_id = str(user_data.get('TenantId', '') or '').strip()
    if not tenant_id:
        logger.warning("ClassLink login rejected: userinfo missing TenantId")
        return redirect("/?classlink_error=missing_tenant")

    person_id = _extract_person_id(user_data)
    if not person_id:
        logger.warning("ClassLink login rejected: userinfo missing SourcedId/UserId")
        return redirect("/?classlink_error=missing_identity")

    guid = _classlink_guid(tenant_id, person_id)
    if not guid:
        return redirect("/?classlink_error=missing_identity")

    # Student login → resolve provisioned record, hand off to the student portal.
    if role == 'student':
        # Clear OAuth-flow markers (single-use enforcement on success).
        session.pop('classlink_oauth_state', None)
        session.pop('classlink_oauth_nonce', None)
        session.pop('classlink_oauth_initiated_by_us', None)

        # Homepage-button SSO carve-out.
        #
        # The Graider login screen has separate paths for teachers
        # (email/password, Google, Microsoft, "Log in with ClassLink",
        # "Log in with Clever") and students ("I'm a student — go to Student
        # Portal" link at the bottom). When `initiated_by_us=True`, the SSO
        # flow was kicked off by the homepage button — a teacher entry point.
        # A `role=student` arriving via that entry point clicked the wrong
        # button; the right UX is to land them DIRECTLY at /join (the
        # anonymous join-code portal), where the entire UI is a single
        # join-code input. No banner, no detour through the homepage's heavy
        # supabase auth bootstrap (which introduced a visible flicker per
        # operator validation on #598), no second login screen. Original
        # #598 bounced to "/?classlink_status=use_student_portal" with a blue
        # info banner; that worked but required the student to read +
        # navigate to a small link. /join is the actionable destination.
        #
        # LaunchPad-tile students arrive with `initiated_by_us=False` (we
        # never called login-url) and continue to the unchanged provisioning
        # path below. Production-realistic student SSO is unaffected.
        if initiated_by_us:
            logger.info(
                "ClassLink self-initiated student SSO routed to /join: "
                "tenant=%s", tenant_id,
            )
            return redirect("/join")

        student_session = _create_classlink_student_session(tenant_id, person_id)
        if student_session and student_session.get("status") == "needs_class_selection":
            params = urlencode({"classlink_select": "1", "sel": student_session["selection_token"]})
            return redirect("/student?" + params)
        if student_session:
            auth_code = _create_classlink_student_auth_code(student_session["token"])
            params = urlencode({"classlink": "1", "code": auth_code})
            return redirect("/student?" + params)

        # Fail closed — no provisioned row for this tenant-scoped identity.
        audit_log(
            "CLASSLINK_STUDENT_NOT_PROVISIONED",
            "ClassLink student has no provisioned roster row: "
            f"tenant={tenant_id} person_hash={hashlib.sha256(person_id.encode()).hexdigest()[:8]}",
            user="anonymous", teacher_id="",
        )
        return redirect("/student?classlink_error=not_provisioned")

    # Teacher/admin login
    session.clear()
    session.permanent = True

    # Resolve the tenant-scoped GUID to a real Supabase Auth UUID (link-or-create).
    graider_uuid = resolve_classlink_user_id(
        guid, email, {'first': first_name, 'last': last_name}
    )
    if not graider_uuid:
        return redirect("/?classlink_error=account_conflict")

    session['classlink_user'] = {
        'classlink_id': person_id,   # external identity (unchanged)
        'guid': guid,                # tenant-scoped GUID, kept for audit/debug
        'user_id': graider_uuid,     # real Supabase UUID → g.user_id / g.teacher_id
        'email': email,
        'name': {'first': first_name, 'last': last_name},
        'type': role or 'teacher',
        'tenant_id': tenant_id,
    }

    applied = apply_sso_admin_designation(email, graider_uuid, session)

    if applied == "district":
        audit_log("CLASSLINK_DISTRICT_ADMIN_LOGIN",
                  f"ClassLink district admin SSO login: {redact_email(email)}",
                  user="district_admin", teacher_id=graider_uuid)
        return redirect("/district")

    # Background roster sync (if OneRoster configured) — keyed by the UUID.
    _trigger_roster_sync(graider_uuid, tenant_id)

    audit_log(
        "CLASSLINK_SCHOOL_ADMIN_LOGIN" if applied == "school" else "CLASSLINK_LOGIN",
        (f"ClassLink school admin SSO login: {redact_email(email)}" if applied == "school"
         else f"ClassLink SSO login: {redact_email(email)}"),
        user=("admin" if applied == "school" else "teacher"), teacher_id=graider_uuid)

    return redirect("/?classlink_login=success")


# ── GET /api/classlink/session ────────────────────────────────────────

@classlink_bp.route('/api/classlink/session', methods=['GET'])
def classlink_session():
    """Check ClassLink session status."""
    cl_user = session.get('classlink_user')
    if not cl_user:
        return jsonify({"authenticated": False})

    return jsonify({
        "authenticated": True,
        "user_id": cl_user.get('user_id'),
        "classlink_id": cl_user.get('classlink_id'),
        "email": cl_user.get('email'),
        "name": cl_user.get('name'),
        "type": cl_user.get('type'),
        "tenant_id": cl_user.get('tenant_id'),
    })


# ── POST /api/classlink/logout ────────────────────────────────────────

@classlink_bp.route('/api/classlink/logout', methods=['POST'])
def classlink_logout():
    """Clear ClassLink session."""
    session.pop('classlink_user', None)
    return jsonify({"status": "logged_out"})


# ── POST /api/classlink/delete-data ──────────────────────────────────

@classlink_bp.route("/api/classlink/delete-data", methods=["POST"])
@require_teacher
@handle_route_errors
def classlink_delete_data():
    """Delete all ClassLink-sourced roster data for the current teacher and
    clear stored roster config (FERPA right-to-delete). teacher_id-scoped."""
    from backend.roster_sync import delete_roster_data
    from backend.storage import save as _storage_save

    teacher_id = g.teacher_id
    if getattr(g, 'auth_source', None) != 'classlink':
        return jsonify({"error": "Not a ClassLink user"}), 403

    deleted = delete_roster_data(teacher_id)
    _storage_save("oneroster_config", None, teacher_id)
    audit_log(
        "CLASSLINK_DATA_DELETED",
        f"Deleted {deleted.get('classes', 0)} classes, {deleted.get('students', 0)} students",
        teacher_id=teacher_id,
    )
    return jsonify({"status": "deleted", "counts": deleted})


# ── POST /api/classlink/student-token ─────────────────────────────────

@classlink_bp.route("/api/classlink/student-token", methods=["POST"])
def classlink_exchange_student_auth_code():
    """Exchange a short-lived auth code for a student session token."""
    data = request.json or {}
    code = data.get("code", "")
    if not code or code not in _pending_classlink_student_auth_codes:
        return jsonify({"error": "Invalid or expired code"}), 401
    entry = _pending_classlink_student_auth_codes.pop(code)
    if time.time() > entry["expires"]:
        return jsonify({"error": "Code expired"}), 401
    return jsonify({"token": entry["token"]})


# ── GET,POST /api/classlink/select-class ──────────────────────────────

@classlink_bp.route("/api/classlink/select-class", methods=["GET", "POST"])
def classlink_select_class():
    """Multi-enrollment finalize. GET lists candidates (does not consume the
    token); POST mints the scoped session (single-use on success only)."""
    if request.method == "GET":
        token = request.args.get("selection_token", "")
    else:
        data = request.json or {}
        token = data.get("selection_token", "")
        class_id = data.get("class_id", "")

    entry = _pending_classlink_class_selections.get(token)
    if not entry:
        return jsonify({"error": "Invalid or expired selection"}), 401
    if time.time() > entry["expires"]:
        _pending_classlink_class_selections.pop(token, None)
        return jsonify({"error": "Selection expired"}), 401

    if request.method == "GET":
        return jsonify({"classes": _public_classlink_candidates(entry["candidates"])})

    chosen = next((c for c in entry["candidates"] if c["class_id"] == class_id), None)
    if chosen is None:
        return jsonify({"error": "Class not among offered choices"}), 400

    sb = get_supabase()
    if sb is None:
        return jsonify({"error": "Supabase not configured"}), 503

    session_info = _mint_classlink_student_session(sb, chosen["_student_row"], chosen)
    _pending_classlink_class_selections.pop(token, None)  # single-use, success only
    return jsonify({"token": session_info["token"]})
