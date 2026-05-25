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

from backend.utils.audit import audit_log
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


def _trigger_roster_sync(teacher_id, tenant_id):
    """Trigger background OneRoster roster sync after ClassLink login.

    Uses existing OneRoster sync infrastructure — ClassLink's Roster Server
    exposes OneRoster 1.1 endpoints.
    """
    import threading

    def _bg_sync():
        try:
            from backend.oneroster import OneRosterClient, normalize_roster, get_oneroster_config
            from backend.roster_sync import sync_roster_to_db

            config = get_oneroster_config(teacher_id)
            if not config.get('base_url'):
                logger.info("No OneRoster config for %s, skipping post-login roster sync", teacher_id)
                return

            import asyncio
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

            classes, students_norm, enrollments, _accommodations = normalize_roster(raw)

            # sync_roster_to_db expects enrollment tuples, not dicts
            enrollment_tuples = [
                (e["class_external_id"], e["student_external_id"])
                for e in enrollments
            ]

            sync_roster_to_db(
                classes, students_norm, enrollment_tuples, teacher_id, provider="classlink"
            )
            logger.info("Post-login ClassLink roster sync complete for %s", teacher_id)
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
    return jsonify({"url": f"{CLASSLINK_AUTH_URL}?{params}"})


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
                "require": ["iat", "nbf", "exp", "iss", "aud", "sub"],
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
        logger.warning("ClassLink id_token validation failed: %s", e.__class__.__name__)
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

    # Student login → redirect to student portal
    if role == 'student':
        # Clear OAuth-flow markers (single-use enforcement on success).
        session.pop('classlink_oauth_state', None)
        session.pop('classlink_oauth_nonce', None)
        session.pop('classlink_oauth_initiated_by_us', None)
        session['classlink_student'] = {
            'classlink_id': person_id,
            'user_id': guid,
            'name': f"{first_name} {last_name}",
            'email': email,
            'tenant_id': tenant_id,
        }
        return redirect("/student?classlink_login=success")

    # Teacher/admin login
    session.clear()
    session.permanent = True

    session['classlink_user'] = {
        'classlink_id': person_id,
        'user_id': guid,
        'email': email,
        'name': {'first': first_name, 'last': last_name},
        'type': role or 'teacher',
        'tenant_id': tenant_id,
    }

    # Background roster sync (if OneRoster configured) — keyed by the GUID.
    _trigger_roster_sync(guid, tenant_id)

    audit_log("CLASSLINK_LOGIN", f"ClassLink SSO login: {redact_email(email)}",
              user="teacher", teacher_id=guid)

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
    session.pop('classlink_student', None)
    return jsonify({"status": "logged_out"})
