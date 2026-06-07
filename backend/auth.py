"""
Supabase JWT Authentication for Graider.
Validates Bearer tokens on all /api/ routes except public endpoints.
Supports both ES256 (JWKS) and HS256 (legacy secret) verification.
"""
import json
import os
import logging
import secrets
import time
import jwt
from jwt import PyJWKClient
from flask import request, jsonify, g, session

logger = logging.getLogger(__name__)

# VB8 #18: absolute (not sliding) cap on an SSO session's total lifetime.
# PERMANENT_SESSION_LIFETIME (8h) is an IDLE timeout that resets on every
# request — an actively-used session can therefore live indefinitely. This
# is the hard upper bound from initial SSO login, after which the session is
# rejected regardless of activity and the user must re-authenticate via the
# IdP. 12h comfortably covers a single school day while bounding a stolen
# cookie's useful window.
SSO_ABSOLUTE_SESSION_LIFETIME = 12 * 60 * 60  # seconds


def establish_sso_session():
    """Reset the Flask session for a fresh SSO login (Clever/ClassLink).

    Centralizes the security-relevant steps every SSO callback must perform:
      1. session.clear()       — drop any pre-existing/anonymous session data.
      2. rotate the server-side session id — anti-fixation: a sid an attacker
         planted in the victim's browser before login can no longer address
         the now-authenticated session. (No-op for the default signed-cookie
         backend, which has no server-side sid to fixate.)
      3. session.permanent = True — apply PERMANENT_SESSION_LIFETIME (idle cap).
      4. stamp sso_login_ts — the absolute-lifetime anchor enforced in
         check_auth via SSO_ABSOLUTE_SESSION_LIFETIME.
    """
    session.clear()
    # Rotate server-side sid if the backend uses one (flask_session). The
    # default SecureCookieSession has no `sid`, so guard with hasattr.
    if hasattr(session, "sid"):
        try:
            session.sid = secrets.token_urlsafe(32)
        except (AttributeError, TypeError):
            # Read-only/unsupported sid — non-fatal; clear() already dropped
            # any fixated data, so the residual risk is acceptable.
            logger.warning("SSO session sid rotation unsupported on this backend")
    session.permanent = True
    session["sso_login_ts"] = time.time()


def _sso_session_within_absolute_cap():
    """True iff the current SSO session's absolute lifetime has not elapsed.

    Fail-safe: a session with NO sso_login_ts (e.g. minted before VB8 #18, or
    tampered to drop the field) is treated as EXPIRED so the cap cannot be
    bypassed by omitting the stamp."""
    ts = session.get("sso_login_ts")
    if not isinstance(ts, (int, float)):
        return False
    return (time.time() - ts) <= SSO_ABSOLUTE_SESSION_LIFETIME

from backend.supabase_client import get_supabase as _get_supabase
from backend.utils.supabase_users import list_all_users
import sentry_sdk

# Clever → Supabase account linking (uses storage.py for Supabase persistence)
def load_clever_links():
    """Load all clever_id → supabase_user_id mappings."""
    try:
        from backend.storage import list_keys, load
        keys = list_keys('clever_link:', 'system')
        links = {}
        for key in keys:
            data = load(key, 'system')
            if data and isinstance(data, dict):
                clever_id = key[len('clever_link:'):]
                links[clever_id] = data.get('supabase_user_id', '')
        return links
    except Exception as e:
        # Fallback to legacy file if storage not available
        sentry_sdk.capture_exception(e)
        legacy_path = os.path.expanduser("~/.graider_data/clever_links.json")
        try:
            with open(legacy_path, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}


def save_clever_link(clever_id, supabase_user_id):
    """Persist a clever_id → supabase_user_id link."""
    try:
        from backend.storage import save
        save(f'clever_link:{clever_id}', {'supabase_user_id': supabase_user_id}, 'system')
    except Exception as e:
        # Fallback to legacy file
        sentry_sdk.capture_exception(e)
        legacy_path = os.path.expanduser("~/.graider_data/clever_links.json")
        links = load_clever_links()
        links[clever_id] = supabase_user_id
        os.makedirs(os.path.dirname(legacy_path), exist_ok=True)
        with open(legacy_path, 'w') as f:
            json.dump(links, f)
    logger.info("Linked Clever account %s to Supabase user %s", clever_id, supabase_user_id)


def resolve_clever_user_id(clever_id):
    """Resolve a clever_id to a linked Supabase user_id, or return clever:{id}."""
    links = load_clever_links()
    return links.get(clever_id, f"clever:{clever_id}")


# ClassLink → Supabase account linking (uses storage.py for Supabase persistence)
def load_classlink_links():
    """Load all classlink_guid → supabase_user_id mappings."""
    try:
        from backend.storage import list_keys, load
        keys = list_keys('classlink_link:', 'system')
        links = {}
        for key in keys:
            data = load(key, 'system')
            if data and isinstance(data, dict):
                guid = key[len('classlink_link:'):]
                links[guid] = data.get('supabase_user_id', '')
        return links
    except Exception as e:
        sentry_sdk.capture_exception(e)
        return {}


def save_classlink_link(guid, supabase_user_id):
    """Persist a classlink_guid → supabase_user_id link."""
    try:
        from backend.storage import save
        save(f'classlink_link:{guid}', {'supabase_user_id': supabase_user_id}, 'system')
    except Exception as e:
        sentry_sdk.capture_exception(e)
    logger.info("Linked ClassLink GUID to Supabase user %s", supabase_user_id)


def _is_sso_provisioned_user(user):
    """Return True if a Supabase user was itself provisioned via SSO
    (Clever/ClassLink), i.e. user_metadata.auth_source is set to one of our
    SSO sources.

    SECURITY (VB8 #13 — account takeover): an SSO login asserts only an email
    address; the email is NOT a proof of ownership of a *pre-existing*
    password (non-SSO) account. Auto-linking an SSO login to ANY account that
    happens to share the asserted email lets an attacker who can name a
    victim's email in an SSO IdP take over the victim's password account. We
    therefore only auto-link by email when the matched account is itself an
    SSO-provisioned account (no password the attacker could be hijacking).
    First-time provisioning (zero matches → create) is unaffected; password
    accounts simply fall through to the isolated legacy namespace (Clever) or
    fail closed (ClassLink), never silently merged.

    The provenance marker is read from **app_metadata**, NOT user_metadata:
    user_metadata (raw_user_meta_data) is client-settable at signUp via the
    PUBLIC anon key (`signUp({options:{data:{auth_source:'clever'}}})`), so a
    user_metadata-based check is a REVERSE-takeover bypass — an attacker self-
    provisions a password account tagged 'clever' for the victim's email, and a
    later real SSO login links to it (Codex VB8 verify, important). app_metadata
    (raw_app_meta_data) is settable ONLY by the service role (our admin
    create_user below), so it is a trustworthy server-set signal."""
    meta = getattr(user, "app_metadata", None) or {}
    try:
        return meta.get("auth_source") in ("clever", "classlink")
    except AttributeError:
        return False


def resolve_classlink_user_id(guid, email, name=None):
    """Resolve a ClassLink tenant-scoped GUID to a real Supabase Auth user UUID.

    Link-or-create. Returns:
      - a previously linked UUID, or
      - the UUID of the single Supabase user whose email matches (and links it), or
      - a freshly created Supabase user's UUID (approved, auth_source=classlink), or
      - None (fail closed) on missing email, ambiguous (>1) email match, no Supabase
        client, or create failure that cannot be deterministically recovered.
    """
    email = (email or "").strip()
    if not email:
        logger.warning("ClassLink resolve: missing email; failing closed")
        return None

    linked = load_classlink_links().get(guid)
    if linked:
        return linked

    name = name or {}
    try:
        sb = _get_supabase()
        if not sb:
            logger.warning("ClassLink resolve: no Supabase client; failing closed")
            return None

        def _email_matches():
            return [
                u for u in list_all_users(sb)
                if getattr(u, 'email', None) and u.email.lower() == email.lower()
            ]

        matches = _email_matches()
        if len(matches) == 1:
            # VB8 #13: only auto-link to an SSO-provisioned account. A match
            # against a non-SSO (password) account is an unverified-email
            # takeover vector — fail closed (do not merge).
            if not _is_sso_provisioned_user(matches[0]):
                logger.warning(
                    "ClassLink resolve: email matches a non-SSO account — "
                    "refusing to auto-link (takeover guard); failing closed")
                return None
            save_classlink_link(guid, matches[0].id)
            return matches[0].id
        if len(matches) > 1:
            logger.warning("ClassLink resolve: %d users match email — failing closed", len(matches))
            return None

        try:
            res = sb.auth.admin.create_user({
                "email": email,
                "email_confirm": True,
                "password": secrets.token_urlsafe(32),
                "user_metadata": {
                    "first_name": name.get('first', ''),
                    "last_name": name.get('last', ''),
                },
                # SSO provenance AND approval live in app_metadata (service-role-
                # only, NOT client-settable) so _is_sso_provisioned_user and the
                # approval gate can trust them (VB8 #13 + VB10 self-approval).
                "app_metadata": {"auth_source": "classlink", "approved": True},
            })
            new_id = res.user.id
            save_classlink_link(guid, new_id)
            return new_id
        except Exception as create_err:
            # Concurrency: a parallel first-login may have created the user already.
            logger.warning("ClassLink resolve: create_user failed (%s); re-resolving by email", type(create_err).__name__)
            recheck = _email_matches()
            # Re-resolve only auto-links to an SSO-provisioned account
            # (the racer is our own create, which sets auth_source=classlink);
            # a non-SSO match here is still a takeover vector (VB8 #13).
            if len(recheck) == 1 and _is_sso_provisioned_user(recheck[0]):
                save_classlink_link(guid, recheck[0].id)
                return recheck[0].id
            return None
    except Exception as e:
        logger.warning("ClassLink resolve failed (non-fatal): %s", type(e).__name__)
        sentry_sdk.capture_exception(e)
        return None


def _claim_clever_text_data(clever_id, uuid):
    """Re-key the teacher's TEXT-keyed rows from clever:{id} -> uuid. Called
    ONLY on the create path (the UUID is brand-new, so a blind UPDATE cannot
    collide with a pre-existing (teacher_id, data_key) PK). Best-effort,
    non-fatal. NOTE: submissions has no teacher_id (it follows join_code), so
    it is intentionally excluded."""
    legacy = f"clever:{clever_id}"
    try:
        sb = _get_supabase()
        if not sb:
            return
        for table in ("teacher_data", "published_assessments", "student_history"):
            try:
                sb.table(table).update({"teacher_id": uuid}).eq("teacher_id", legacy).execute()
            except Exception as e:
                logger.warning("Clever data-claim on %s failed (non-fatal): %s", table, type(e).__name__)
                sentry_sdk.capture_exception(e)
    except Exception as e:
        logger.warning("Clever data-claim failed (non-fatal): %s", type(e).__name__)
        sentry_sdk.capture_exception(e)


def resolve_clever_user_id_or_create(clever_id, email, name=None):
    """Resolve a Clever id to a real Supabase Auth UUID (link-or-create), but
    FAIL OPEN to the legacy clever:{id} namespace on any non-resolution. Unlike
    resolve_classlink_user_id (which fails closed), Clever has live unlinked
    users and clever:{id} is an isolated namespace, so falling back never blocks
    login or merges into a wrong account. Returns (id, outcome) where outcome is
    one of: 'linked' | 'matched' | 'created' | 'ambiguous_legacy' |
    'transient_legacy' | 'create_failed_legacy'. UUID outcomes -> real UUID;
    *_legacy outcomes -> f'clever:{clever_id}'. The 'created' path also re-keys
    the teacher's TEXT-keyed data via _claim_clever_text_data."""
    legacy = f"clever:{clever_id}"

    linked = load_clever_links().get(clever_id)
    if linked:
        return linked, "linked"

    email = (email or "").strip()
    if not email:
        logger.warning("Clever resolve: missing email; failing open to legacy")
        return legacy, "transient_legacy"

    name = name or {}
    try:
        sb = _get_supabase()
        if not sb:
            logger.warning("Clever resolve: no Supabase client; failing open to legacy")
            return legacy, "transient_legacy"

        def _email_matches():
            return [
                u for u in list_all_users(sb)
                if getattr(u, 'email', None) and u.email.lower() == email.lower()
            ]

        matches = _email_matches()
        if len(matches) == 1:
            # VB8 #13: only auto-link to an SSO-provisioned account. A single
            # match against a non-SSO (password) account is an unverified-email
            # takeover vector — fail OPEN to the isolated clever:{id} namespace
            # (never merge into the victim's password account).
            if not _is_sso_provisioned_user(matches[0]):
                logger.warning(
                    "Clever resolve: email matches a non-SSO account — refusing "
                    "to auto-link (takeover guard); failing open to legacy")
                return legacy, "unverified_email_legacy"
            save_clever_link(clever_id, matches[0].id)
            return matches[0].id, "matched"
        if len(matches) > 1:
            logger.warning("Clever resolve: %d users match email — failing open to legacy", len(matches))
            return legacy, "ambiguous_legacy"

        try:
            res = sb.auth.admin.create_user({
                "email": email,
                "email_confirm": True,
                "password": secrets.token_urlsafe(32),
                "user_metadata": {
                    "first_name": name.get('first', ''),
                    "last_name": name.get('last', ''),
                },
                # SSO provenance AND approval live in app_metadata (service-role-
                # only, NOT client-settable) so _is_sso_provisioned_user and the
                # approval gate can trust them (VB8 #13 + VB10 self-approval).
                "app_metadata": {"auth_source": "clever", "approved": True},
            })
            new_id = getattr(getattr(res, "user", None), "id", None)
            if not new_id:
                logger.warning("Clever resolve: create_user returned no user id; failing open")
                return legacy, "create_failed_legacy"
            save_clever_link(clever_id, new_id)
            _claim_clever_text_data(clever_id, new_id)
            return new_id, "created"
        except Exception as create_err:
            logger.warning("Clever resolve: create_user failed (%s); re-resolving by email",
                           type(create_err).__name__)
            recheck = _email_matches()
            # Re-resolve only auto-links to an SSO-provisioned account
            # (the racer is our own create, which sets auth_source=clever);
            # a non-SSO match here is still a takeover vector (VB8 #13).
            if len(recheck) == 1 and _is_sso_provisioned_user(recheck[0]):
                save_clever_link(clever_id, recheck[0].id)
                return recheck[0].id, "matched"
            return legacy, "create_failed_legacy"
    except Exception as e:
        logger.warning("Clever resolve failed (non-fatal): %s", type(e).__name__)
        sentry_sdk.capture_exception(e)
        return legacy, "transient_legacy"


# Routes that don't require authentication
# SECURITY: Be explicit — only list endpoints that truly need to be public.
# Student dashboard/content endpoints use X-Student-Token (not JWT) for their own auth.
PUBLIC_PREFIXES = [
    '/api/student/join/',         # Anonymous join-code portal (GET assessment by code)
    '/api/student/submit/',       # Anonymous submission (join-code path, POST)
    '/api/student/class-submit/', # Class-based authenticated submission (X-Student-Token, not JWT)
    '/api/clever/',            # Clever OAuth flow (callback must be unauthenticated)
    '/api/classlink/',         # ClassLink OAuth flow (callback must be unauthenticated)
    '/api/lti/',               # LTI OIDC login, launch callback, JWKS (platform-initiated)
    '/api/district/',           # District admin setup (session-based auth, not JWT)
    '/api/sync/',               # Periodic sync webhook (auth via PERIODIC_SYNC_SECRET header)
]

PUBLIC_EXACT = [
    '/api/status',              # Grading status polling (used before auth check completes)
    '/api/stripe/webhook',      # Stripe webhook (verified via Stripe-Signature header)
    '/api/auth/notify-signup',  # Public signup notification (no JWT needed)
    '/api/auth/approve-user',   # One-click approval from admin email (HMAC-protected)
    '/api/student/login',       # Student email+code login (creates session token)
    '/api/student/session',     # Session validation (uses X-Student-Token)
    '/api/student/dashboard',   # Student dashboard (uses X-Student-Token, not JWT)
    '/api/student/shared-media', # Shared media access (public via join code)
]

# Student endpoints that use prefix matching (X-Student-Token auth, not JWT)
PUBLIC_PREFIXES += [
    '/api/student/content/',    # Class-based content access (uses X-Student-Token)
]

# JWKS client for ES256 verification (cached, refreshes automatically)
_jwks_client = None


def _get_jwks_client():
    """Lazy-init JWKS client from Supabase URL."""
    global _jwks_client
    if _jwks_client is None:
        supabase_url = os.getenv('SUPABASE_URL')
        if supabase_url:
            jwks_url = f"{supabase_url}/auth/v1/.well-known/jwks.json"
            _jwks_client = PyJWKClient(jwks_url)
    return _jwks_client


def get_jwt_secret():
    """Get the Supabase JWT secret from environment (HS256 fallback)."""
    secret = os.getenv('SUPABASE_JWT_SECRET')
    if not secret:
        raise RuntimeError('SUPABASE_JWT_SECRET not configured')
    return secret


def validate_token(token):
    """
    Validate a Supabase JWT and return the decoded payload.
    Tries ES256 (JWKS) first, falls back to HS256 (legacy secret).
    Returns None if invalid.
    """
    # Try ES256 via JWKS first
    jwks = _get_jwks_client()
    if jwks:
        try:
            signing_key = jwks.get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=['ES256'],
                audience='authenticated',
            )
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError as e:
            logger.warning("ES256 validation failed, trying HS256: %s", type(e).__name__)
        except jwt.PyJWKClientError as e:
            # VB8 #16: JWKS fetch/network failure (e.g. WAF 401, TLS, DNS) is a
            # PyJWTError but NOT an InvalidTokenError, so it would otherwise
            # escape and 500 the auth hook. Fall through to the HS256 fallback.
            logger.warning("JWKS fetch failed, trying HS256: %s", type(e).__name__)

    # Fallback: HS256 with legacy secret
    try:
        payload = jwt.decode(
            token,
            get_jwt_secret(),
            algorithms=['HS256'],
            audience='authenticated',
        )
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def is_public_route(path):
    """Check if a route is public (no auth required)."""
    if path in PUBLIC_EXACT:
        return True
    for prefix in PUBLIC_PREFIXES:
        if path.startswith(prefix):
            return True
    return False


def init_auth(app):
    """
    Register the before_request auth hook on the Flask app.
    Call this BEFORE registering blueprints.
    """
    @app.before_request
    def set_request_id():
        """Generate a unique request ID for correlation across logs."""
        import uuid
        g.request_id = str(uuid.uuid4())[:8]

    @app.before_request
    def check_auth():
        # Skip auth on localhost ONLY if no JWT is present.
        # Behind a reverse proxy (Railway/gunicorn), request.host may resolve
        # to localhost even on production, so always prefer JWT when available.
        host = request.host.split(':')[0]
        has_bearer = request.headers.get('Authorization', '').startswith('Bearer ')
        is_dev = os.getenv('FLASK_ENV', '').lower() in ('development', 'dev')
        if is_dev and host in ('localhost', '127.0.0.1') and not has_bearer:
            # Allow test harness to simulate multiple teachers via header
            g.user_id = request.headers.get('X-Test-Teacher-Id',
                                            os.getenv('DEV_USER_ID', 'local-dev'))
            g.user_email = os.getenv('DEV_EMAIL', 'dev@localhost')
            # Issue #353: flag the request as a dev-shim teacher so
            # downstream gates (e.g. `approval_status`) can bypass
            # Supabase user-lookup paths that 500 in CI for any non-
            # 'local-dev' teacher_id. Was previously detectable only
            # via the literal `g.user_id == 'local-dev'` check.
            g.is_dev_shim = True
            return None

        # Clever SSO session (cookie-based, set during OAuth callback).
        # Prefer the UUID resolved + stored at callback (clever_user['user_id']);
        # fall back to the cheap resolver for pre-existing sessions.
        clever_user = session.get('clever_user') if hasattr(session, 'get') else None
        if clever_user and not has_bearer:
            # VB8 #18: absolute-lifetime cap. Past the cap (or a legacy session
            # with no stamp), drop the SSO session and fall through to the
            # standard 401 — the user must re-authenticate via Clever.
            if not _sso_session_within_absolute_cap():
                logger.info("Clever SSO session past absolute cap — clearing")
                session.clear()
            else:
                g.user_id = clever_user.get('user_id') or resolve_clever_user_id(clever_user['clever_id'])
                g.teacher_id = g.user_id
                g.user_email = clever_user.get('email', '')
                g.auth_source = 'clever'
                g.district_id = clever_user.get('district', '')
                return None

        # ClassLink SSO session — `user_id` is the resolved Supabase Auth UUID
        # (set at the OAuth callback by resolve_classlink_user_id); the
        # tenant-scoped GUID is kept separately in `guid`. Read user_id
        # verbatim into g.user_id/g.teacher_id.
        classlink_user = session.get('classlink_user') if hasattr(session, 'get') else None
        if classlink_user and not has_bearer:
            # VB8 #18: absolute-lifetime cap (see Clever branch above).
            if not _sso_session_within_absolute_cap():
                logger.info("ClassLink SSO session past absolute cap — clearing")
                session.clear()
            else:
                g.user_id = classlink_user.get('user_id', '')
                g.teacher_id = g.user_id
                g.user_email = classlink_user.get('email', '')
                g.auth_source = 'classlink'
                g.district_id = classlink_user.get('tenant_id', '')
                return None

        # Skip non-API routes (static files, index.html, etc.)
        if not request.path.startswith('/api/'):
            return None

        # Skip public routes
        if is_public_route(request.path):
            return None

        # Extract token from Authorization header
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Authentication required'}), 401

        token = auth_header[7:]  # Strip 'Bearer '
        payload = validate_token(token)
        if payload is None:
            return jsonify({'error': 'Invalid or expired token'}), 401

        # Attach user info to Flask's g object for use in route handlers
        g.user_id = payload.get('sub')
        g.user_email = payload.get('email', '')
        # Phase 4.5: raw JWT stashed here so get_request_supabase()
        # (in backend/supabase_client_scoped.py) can mint a per-user
        # Supabase client. This attr is ONLY set on the validated
        # Bearer-JWT path — never on Clever/ClassLink/student/dev.
        g.supabase_jwt = token

        # Approval gate — skip for the approval-status endpoint itself
        if request.path != '/api/auth/approval-status':
            # Clever/ClassLink users are district-approved by definition — skip gate
            if getattr(g, 'auth_source', None) in ('clever', 'classlink'):
                return None

            # VB10: approval is read from app_metadata, NOT user_metadata.
            # user_metadata (raw_user_meta_data) is client-settable at signUp
            # via the PUBLIC anon key (signUp({options:{data:{approved:true}}})),
            # so trusting it lets a user self-approve and bypass the manual
            # onboarding gate. app_metadata is service-role-only (set by the
            # admin approve endpoint), so it's the trustworthy source.
            app_meta = payload.get('app_metadata', {})
            if not app_meta.get('approved'):
                # JWT metadata may be stale — check Supabase admin API as fallback
                try:
                    sb = _get_supabase()
                    if sb:
                        res = sb.auth.admin.get_user_by_id(g.user_id)
                        fresh_meta = (res.user.app_metadata or {}) if res and res.user else {}
                        if fresh_meta.get('approved'):
                            # User is actually approved, JWT is just stale
                            logger.info("User %s approved via admin API fallback (stale JWT)", g.user_email)
                            return None  # Allow request
                except Exception as e:
                    logger.warning("Admin API approval fallback failed: %s", str(e))
                    sentry_sdk.capture_exception(e)

                return jsonify({
                    'error': 'Account pending approval',
                    'code': 'NOT_APPROVED',
                }), 403
