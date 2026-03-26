"""
LTI 1.3 Core Module for Graider
================================
Implements:
  - RSA key management (generate/load from ~/.graider_lti/)
  - OIDC login initiation (build redirect URL)
  - JWT launch validation (validate id_token from platform)
  - Launch data extraction (user, roles, context, AGS endpoints)
  - AGS Client (create line items, post scores)
  - Platform config helpers (save/load/list/delete via backend.storage)
"""

import base64
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

import httpx
import jwt
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding

logger = logging.getLogger(__name__)

# Directory for LTI key material
LTI_KEY_DIR = os.path.expanduser("~/.graider_lti")
LTI_DIR = LTI_KEY_DIR  # backward-compat alias

# LTI 1.3 role URNs that indicate instructor
_INSTRUCTOR_ROLES = {
    "http://purl.imsglobal.org/vocab/lis/v2/membership#Instructor",
    "http://purl.imsglobal.org/vocab/lis/v2/membership#ContentDeveloper",
    "Instructor",
    "ContentDeveloper",
}

# AGS scopes requested for OAuth 2.0 client credentials
_AGS_SCOPES = (
    "https://purl.imsglobal.org/spec/lti-ags/scope/lineitem "
    "https://purl.imsglobal.org/spec/lti-ags/scope/score"
)

# LTI claim namespaces
_CLAIM_RESOURCE_LINK = "https://purl.imsglobal.org/spec/lti/claim/resource_link"
_CLAIM_ROLES = "https://purl.imsglobal.org/spec/lti/claim/roles"
_CLAIM_CONTEXT = "https://purl.imsglobal.org/spec/lti/claim/context"
_CLAIM_AGS = "https://purl.imsglobal.org/spec/lti-ags/claim/endpoint"
_CLAIM_MESSAGE_TYPE = "https://purl.imsglobal.org/spec/lti/claim/message_type"
_CLAIM_VERSION = "https://purl.imsglobal.org/spec/lti/claim/version"
_CLAIM_DEPLOYMENT_ID = "https://purl.imsglobal.org/spec/lti/claim/deployment_id"


# ══════════════════════════════════════════════════════════════
# RSA KEY MANAGEMENT
# ══════════════════════════════════════════════════════════════

def _iso_now():
    """Return current UTC timestamp as ISO 8601 string."""
    return datetime.now(tz=timezone.utc).isoformat()


def get_or_create_rsa_keypair():
    """Generate or load the tool's RSA 2048-bit key pair from ~/.graider_lti/.

    Returns:
        (private_pem: bytes, public_pem: bytes, kid: str)
    """
    os.makedirs(LTI_KEY_DIR, exist_ok=True)
    private_key_path = os.path.join(LTI_KEY_DIR, "private.pem")
    public_key_path = os.path.join(LTI_KEY_DIR, "public.pem")
    kid_path = os.path.join(LTI_KEY_DIR, "kid.txt")

    if (
        os.path.exists(private_key_path)
        and os.path.exists(public_key_path)
        and os.path.exists(kid_path)
    ):
        with open(private_key_path, "rb") as f:
            private_pem = f.read()
        with open(public_key_path, "rb") as f:
            public_pem = f.read()
        with open(kid_path, "r") as f:
            kid = f.read().strip()
        return private_pem, public_pem, kid

    # Generate new RSA key pair
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    public_key = private_key.public_key()

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    kid = str(uuid.uuid4())

    with open(private_key_path, "wb") as f:
        f.write(private_pem)
    os.chmod(private_key_path, 0o600)
    with open(public_key_path, "wb") as f:
        f.write(public_pem)
    with open(kid_path, "w") as f:
        f.write(kid)

    logger.info("Generated new RSA key pair with kid=%s", kid)
    return private_pem, public_pem, kid


def get_jwks():
    """Return the tool's public key as a JWKS document.

    Returns:
        dict with "keys" array containing one RSA JWK (kty, alg, use, kid, n, e).
    """
    _, public_pem, kid = get_or_create_rsa_keypair()

    from cryptography.hazmat.primitives.serialization import load_pem_public_key

    public_key = load_pem_public_key(public_pem)
    pub_numbers = public_key.public_numbers()

    def _int_to_base64url(n):
        length = (n.bit_length() + 7) // 8
        return base64.urlsafe_b64encode(n.to_bytes(length, "big")).rstrip(b"=").decode("ascii")

    return {
        "keys": [
            {
                "kty": "RSA",
                "alg": "RS256",
                "use": "sig",
                "kid": kid,
                "n": _int_to_base64url(pub_numbers.n),
                "e": _int_to_base64url(pub_numbers.e),
            }
        ]
    }


# ══════════════════════════════════════════════════════════════
# OIDC LOGIN INITIATION
# ══════════════════════════════════════════════════════════════

def build_oidc_login_response(params, platform_config, tool_url):
    """Build the redirect URL for OIDC login initiation.

    Args:
        params: dict of incoming OIDC login hint params (iss, login_hint,
                client_id, lti_message_hint, target_link_uri, etc.)
        platform_config: dict with platform settings (auth_endpoint, client_id, issuer)
        tool_url: base URL of the tool (e.g. https://app.graider.live)

    Returns:
        (redirect_url: str, state: str, nonce: str)
    """
    state = str(uuid.uuid4())
    nonce = str(uuid.uuid4())

    redirect_uri = f"{tool_url}/api/lti/launch"
    client_id = platform_config.get("client_id") or params.get("client_id", "")
    auth_endpoint = platform_config.get("auth_endpoint", "")

    query_params = {
        "scope": "openid",
        "response_type": "id_token",
        "response_mode": "form_post",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "login_hint": params.get("login_hint", ""),
        "state": state,
        "nonce": nonce,
        "prompt": "none",
    }

    lti_message_hint = params.get("lti_message_hint")
    if lti_message_hint:
        query_params["lti_message_hint"] = lti_message_hint

    redirect_url = f"{auth_endpoint}?{urlencode(query_params)}"
    return redirect_url, state, nonce


# ══════════════════════════════════════════════════════════════
# JWT LAUNCH VALIDATION
# ══════════════════════════════════════════════════════════════

def validate_launch_jwt(id_token, platform_config):
    """Validate an LTI 1.3 id_token from a platform.

    Fetches the platform's JWKS, verifies the JWT signature, and checks
    required LTI claims.

    Args:
        id_token: JWT string from the platform's form_post
        platform_config: dict with issuer, client_id, jwks_uri

    Returns:
        Decoded JWT claims dict.

    Raises:
        ValueError: if validation fails.
    """
    jwks_uri = platform_config.get("jwks_uri")
    client_id = platform_config.get("client_id")
    issuer = platform_config.get("issuer")

    if not jwks_uri:
        raise ValueError("platform_config missing jwks_uri")
    if not client_id:
        raise ValueError("platform_config missing client_id")
    if not issuer:
        raise ValueError("platform_config missing issuer")

    try:
        from jwt import PyJWKClient
        jwks_client = PyJWKClient(jwks_uri)
        signing_key = jwks_client.get_signing_key_from_jwt(id_token)
        claims = jwt.decode(
            id_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=client_id,
            issuer=issuer,
        )
    except jwt.ExpiredSignatureError:
        raise ValueError("id_token has expired")
    except jwt.InvalidAudienceError:
        raise ValueError(f"id_token audience does not match client_id={client_id}")
    except jwt.InvalidIssuerError:
        raise ValueError(f"id_token issuer does not match expected issuer={issuer}")
    except Exception as e:
        raise ValueError(f"JWT validation failed: {e}")

    # Validate required LTI claims
    message_type = claims.get(_CLAIM_MESSAGE_TYPE)
    if message_type != "LtiResourceLinkRequest":
        raise ValueError(f"Unexpected message_type: {message_type!r}")

    version = claims.get(_CLAIM_VERSION)
    if version != "1.3.0":
        raise ValueError(f"Unexpected LTI version: {version!r}")

    deployment_id = claims.get(_CLAIM_DEPLOYMENT_ID)
    if not deployment_id:
        raise ValueError("Missing deployment_id claim")

    return claims


# ══════════════════════════════════════════════════════════════
# LAUNCH DATA EXTRACTION
# ══════════════════════════════════════════════════════════════

def extract_launch_data(claims):
    """Extract structured launch data from validated JWT claims.

    Args:
        claims: decoded JWT dict from validate_launch_jwt()

    Returns:
        dict with user_id, name, email, given_name, family_name, roles,
        is_instructor, context_id, context_title, resource_link_id,
        resource_link_title, ags_endpoint, ags_lineitems_url, ags_scores_url,
        deployment_id, platform_issuer.
    """
    roles = claims.get(_CLAIM_ROLES, [])
    is_instructor = bool(set(roles) & _INSTRUCTOR_ROLES)

    resource_link = claims.get(_CLAIM_RESOURCE_LINK, {})
    context = claims.get(_CLAIM_CONTEXT, {})
    ags = claims.get(_CLAIM_AGS, {})

    return {
        "user_id": claims.get("sub"),
        "name": claims.get("name"),
        "email": claims.get("email"),
        "given_name": claims.get("given_name"),
        "family_name": claims.get("family_name"),
        "roles": roles,
        "is_instructor": is_instructor,
        "context_id": context.get("id"),
        "context_title": context.get("title"),
        "resource_link_id": resource_link.get("id"),
        "resource_link_title": resource_link.get("title"),
        "ags_endpoint": ags.get("lineitems"),
        "ags_lineitems_url": ags.get("lineitems"),
        "ags_scores_url": ags.get("scores"),
        "deployment_id": claims.get(_CLAIM_DEPLOYMENT_ID),
        "platform_issuer": claims.get("iss"),
    }


# ══════════════════════════════════════════════════════════════
# AGS CLIENT
# ══════════════════════════════════════════════════════════════

class AGSClient:
    """Assignment and Grade Services (AGS) client for LTI 1.3.

    Handles OAuth 2.0 client_credentials token acquisition and
    line item / score operations.
    """

    def __init__(self, platform_config, ags_endpoint):
        """
        Args:
            platform_config: dict with client_id, issuer, token_url
            ags_endpoint: lineitems URL from launch claims
        """
        self.platform_config = platform_config
        self.ags_endpoint = ags_endpoint
        self._access_token = None

    def _get_access_token(self):
        """Obtain an OAuth 2.0 access token via client_credentials + JWT assertion (RFC 7523).

        Returns:
            access_token string
        """
        private_pem, _, kid = get_or_create_rsa_keypair()
        client_id = self.platform_config.get("client_id")
        token_url = self.platform_config.get("token_url")
        issuer = self.platform_config.get("issuer", "")

        now = int(datetime.now(tz=timezone.utc).timestamp())
        assertion_claims = {
            "iss": client_id,
            "sub": client_id,
            "aud": token_url,
            "iat": now,
            "exp": now + 300,  # 5 minutes
            "jti": str(uuid.uuid4()),
        }

        client_assertion = jwt.encode(
            assertion_claims,
            private_pem,
            algorithm="RS256",
            headers={"kid": kid},
        )

        response = httpx.post(
            token_url,
            data={
                "grant_type": "client_credentials",
                "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
                "client_assertion": client_assertion,
                "scope": _AGS_SCOPES,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=15,
        )
        response.raise_for_status()
        token_data = response.json()
        self._access_token = token_data["access_token"]
        return self._access_token

    def create_lineitem(self, label, max_score, resource_link_id, tag=None):
        """Create a line item in the AGS endpoint.

        Args:
            label: display label for the line item
            max_score: maximum score (float)
            resource_link_id: LTI resource link ID to associate with
            tag: optional tag string

        Returns:
            Created line item dict (from platform response).
        """
        token = self._access_token or self._get_access_token()
        payload = {
            "scoreMaximum": max_score,
            "label": label,
            "resourceLinkId": resource_link_id,
        }
        if tag is not None:
            payload["tag"] = tag

        response = httpx.post(
            self.ags_endpoint,
            json=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/vnd.ims.lis.v2.lineitem+json",
            },
            timeout=15,
        )
        response.raise_for_status()
        return response.json()

    def post_score(self, lineitem_url, user_id, score, max_score, comment=None):
        """Post a score to a line item.

        Args:
            lineitem_url: URL of the line item (from create_lineitem or launch)
            user_id: LTI user ID (sub claim)
            score: achieved score (float)
            max_score: maximum possible score (float)
            comment: optional feedback comment string

        Returns:
            Platform response dict.
        """
        token = self._access_token or self._get_access_token()
        now_iso = datetime.now(tz=timezone.utc).isoformat()

        payload = {
            "userId": user_id,
            "scoreGiven": score,
            "scoreMaximum": max_score,
            "activityProgress": "Completed",
            "gradingProgress": "FullyGraded",
            "timestamp": now_iso,
        }
        if comment is not None:
            payload["comment"] = comment

        scores_url = lineitem_url.rstrip("/") + "/scores"
        try:
            response = httpx.post(
                scores_url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/vnd.ims.lis.v2.score+json",
                },
                timeout=15,
            )
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error("post_score failed for user=%s lineitem=%s: %s", user_id, lineitem_url, e)
            return False


# ══════════════════════════════════════════════════════════════
# PLATFORM CONFIG HELPERS
# ══════════════════════════════════════════════════════════════

def _platform_key(platform_issuer):
    """Build storage key for a platform config."""
    # Sanitize issuer to be safe as a key suffix
    safe = platform_issuer.replace("://", "_").replace("/", "_").replace(".", "_")
    return f"lti_platform:{safe}"


_SYSTEM_TEACHER_ID = "system"


def get_platform_config(platform_issuer, teacher_id=None):
    """Load a platform config from storage.

    Tries per-teacher config first; falls back to system-level config if not found.

    Args:
        platform_issuer: issuer URL string (used as identifier)
        teacher_id: teacher's ID for storage scoping (optional)

    Returns:
        platform config dict, or None if not found.
    """
    from backend import storage
    key = _platform_key(platform_issuer)
    if teacher_id:
        result = storage.load(key, teacher_id)
        if result is not None:
            return result
    # Fall back to system-level config
    return storage.load(key, _SYSTEM_TEACHER_ID)


def save_platform_config(platform_issuer, config, teacher_id=None):
    """Save a platform config to storage.

    Args:
        platform_issuer: issuer URL string
        config: dict with client_id, issuer, jwks_uri, auth_endpoint, token_url, etc.
        teacher_id: teacher's ID for storage scoping (optional; uses system if None)

    Returns:
        True on success.
    """
    from backend import storage
    tid = teacher_id or _SYSTEM_TEACHER_ID
    return storage.save(_platform_key(platform_issuer), config, tid)


def list_platform_configs(teacher_id=None):
    """List all platform configs for a teacher (or system).

    Args:
        teacher_id: teacher's ID for storage scoping (optional)

    Returns:
        list of data_key strings matching 'lti_platform:' prefix.
    """
    from backend import storage
    tid = teacher_id or _SYSTEM_TEACHER_ID
    return storage.list_keys("lti_platform:", tid)


def delete_platform_config(platform_issuer, teacher_id=None):
    """Delete a platform config from storage.

    Args:
        platform_issuer: issuer URL string
        teacher_id: teacher's ID for storage scoping (optional)

    Returns:
        True on success.
    """
    from backend import storage
    tid = teacher_id or _SYSTEM_TEACHER_ID
    return storage.delete(_platform_key(platform_issuer), tid)


# ══════════════════════════════════════════════════════════════
# AGS CONTEXT PERSISTENCE
# ══════════════════════════════════════════════════════════════

def save_ags_context(teacher_id, platform_issuer, context_id, ags_data):
    """Persist AGS endpoint data for a given platform + context.

    Args:
        teacher_id: teacher's ID for storage scoping
        platform_issuer: issuer URL string
        context_id: LTI context ID (course/class)
        ags_data: dict containing AGS endpoint URLs and scopes

    Returns:
        True on success.
    """
    from backend import storage
    key = f"lti_ags:{platform_issuer}:{context_id}"
    return storage.save(key, ags_data, teacher_id)


def get_ags_context(teacher_id, platform_issuer, context_id):
    """Load AGS endpoint data for a given platform + context.

    Args:
        teacher_id: teacher's ID for storage scoping
        platform_issuer: issuer URL string
        context_id: LTI context ID

    Returns:
        AGS data dict, or None if not found.
    """
    from backend import storage
    key = f"lti_ags:{platform_issuer}:{context_id}"
    return storage.load(key, teacher_id)


def list_ags_contexts(teacher_id):
    """List all saved AGS contexts for a teacher.

    Args:
        teacher_id: teacher's ID for storage scoping

    Returns:
        list of data_key strings matching 'lti_ags:' prefix.
    """
    from backend import storage
    return storage.list_keys("lti_ags:", teacher_id)


# ══════════════════════════════════════════════════════════════
# LTI USER MAPPING
# ══════════════════════════════════════════════════════════════

def save_lti_user_mapping(teacher_id, platform_issuer, context_id, lti_sub, student_name, email=None):
    """Persist a mapping from LTI sub to Graider student identity.

    Args:
        teacher_id: teacher's ID for storage scoping
        platform_issuer: issuer URL string
        context_id: LTI context ID
        lti_sub: LTI user subject (sub claim)
        student_name: student's display name
        email: student email (optional)

    Returns:
        True on success.
    """
    from backend import storage
    key = f"lti_user:{platform_issuer}:{context_id}:{lti_sub}"
    data = {
        "lti_sub": lti_sub,
        "student_name": student_name,
        "email": email,
        "platform_issuer": platform_issuer,
        "context_id": context_id,
        "updated_at": _iso_now(),
    }
    return storage.save(key, data, teacher_id)


def get_lti_user_mappings(teacher_id, platform_issuer, context_id):
    """Load all LTI user mappings for a given platform + context.

    Args:
        teacher_id: teacher's ID for storage scoping
        platform_issuer: issuer URL string
        context_id: LTI context ID

    Returns:
        list of user mapping dicts (each has lti_sub, student_name, email).
    """
    from backend import storage
    prefix = f"lti_user:{platform_issuer}:{context_id}:"
    keys = storage.list_keys(prefix, teacher_id)
    mappings = []
    for key in (keys or []):
        data = storage.load(key, teacher_id)
        if data:
            mappings.append(data)
    return mappings


def match_scores_to_lti_users(scores, user_mappings):
    """Match grading score records to LTI user mappings.

    Matches by student_name (case-insensitive) or email.

    Args:
        scores: list of dicts with at least 'student_name' and optionally 'email'
        user_mappings: list of dicts from get_lti_user_mappings()
            (each has 'student_name', 'email', 'lti_sub')

    Returns:
        (matched: list of dicts merging score + lti_sub,
         unmatched_names: list of student name strings that had no mapping)
    """
    matched = []
    unmatched_names = []

    # Build lookup indices for fast matching
    name_index = {}
    email_index = {}
    for mapping in user_mappings:
        name = (mapping.get("student_name") or "").strip().lower()
        if name:
            name_index[name] = mapping
        em = (mapping.get("email") or "").strip().lower()
        if em:
            email_index[em] = mapping

    for score in scores:
        score_name = (score.get("student_name") or "").strip().lower()
        score_email = (score.get("email") or "").strip().lower()

        mapping = None
        if score_name and score_name in name_index:
            mapping = name_index[score_name]
        elif score_email and score_email in email_index:
            mapping = email_index[score_email]

        if mapping:
            matched.append({**score, "lti_sub": mapping["lti_sub"]})
        else:
            unmatched_names.append(score.get("student_name", ""))

    return matched, unmatched_names
