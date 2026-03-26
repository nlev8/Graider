"""
District Admin Setup Routes
============================
Password-protected endpoints for district-level SIS and AI configuration.
All config stored with teacher_id="system" via backend.storage.
"""
import logging
import os
import functools

from flask import Blueprint, request, jsonify, session
from werkzeug.security import generate_password_hash, check_password_hash

from backend.storage import save as storage_save, load as storage_load
from backend.utils.audit import audit_log
from backend.utils.errors import handle_route_errors

logger = logging.getLogger(__name__)

district_bp = Blueprint("district", __name__)

# Storage keys (teacher_id="system")
_KEY_PASSWORD_HASH = "district:password_hash"
_KEY_SIS_CONFIG = "district:sis_config"
_KEY_AI_KEYS = "district:ai_keys"


# ── Helpers ──────────────────────────────────────────────────────────────────

def _get_district_password_hash():
    """Get stored password hash; bootstrap from env var on first use."""
    stored = storage_load(_KEY_PASSWORD_HASH, "system")
    if stored and isinstance(stored, dict) and stored.get("hash"):
        return stored["hash"]

    # Bootstrap from env var
    env_pw = os.getenv("DISTRICT_ADMIN_PASSWORD")
    if env_pw:
        pw_hash = generate_password_hash(env_pw)
        storage_save(_KEY_PASSWORD_HASH, {"hash": pw_hash}, "system")
        logger.info("Bootstrapped district admin password from env var")
        return pw_hash

    return None


def _require_district_admin(f):
    """Decorator: require district admin session."""
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("district_admin"):
            return jsonify({"error": "District admin authentication required"}), 401
        return f(*args, **kwargs)
    return wrapper


# ── POST /api/district/auth ─────────────────────────────────────────────────

@district_bp.route("/api/district/auth", methods=["POST"])
@handle_route_errors
def district_auth():
    """Authenticate as district admin or set up initial password."""
    data = request.get_json(silent=True) or {}
    password = data.get("password", "")
    is_setup = data.get("setup", False)

    pw_hash = _get_district_password_hash()

    # No password configured yet
    if not pw_hash:
        if is_setup and password:
            if len(password) < 8:
                return jsonify({"error": "Password must be at least 8 characters"}), 400
            new_hash = generate_password_hash(password)
            storage_save(_KEY_PASSWORD_HASH, {"hash": new_hash}, "system")
            session["district_admin"] = True
            audit_log("district_admin_setup", "Initial password created", user="district_admin", teacher_id="system")
            return jsonify({"authenticated": True})
        return jsonify({"needs_setup": True})

    # Password exists — validate
    if not password:
        return jsonify({"error": "Password required"}), 400

    if not check_password_hash(pw_hash, password):
        audit_log("district_admin_auth_failed", "Invalid password attempt", user="district_admin", teacher_id="system")
        return jsonify({"error": "Invalid password"}), 403

    session["district_admin"] = True
    audit_log("district_admin_login", "District admin authenticated", user="district_admin", teacher_id="system")
    return jsonify({"authenticated": True})


# ── DELETE /api/district/auth ────────────────────────────────────────────────

@district_bp.route("/api/district/auth", methods=["DELETE"])
@handle_route_errors
def district_logout():
    """Clear district admin session."""
    session.pop("district_admin", None)
    return jsonify({"status": "logged_out"})


# ── POST /api/district/change-password ───────────────────────────────────────

@district_bp.route("/api/district/change-password", methods=["POST"])
@_require_district_admin
@handle_route_errors
def district_change_password():
    """Change district admin password."""
    data = request.get_json(silent=True) or {}
    current_password = data.get("current_password", "")
    new_password = data.get("new_password", "")

    if not current_password or not new_password:
        return jsonify({"error": "Both current_password and new_password required"}), 400

    if len(new_password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400

    pw_hash = _get_district_password_hash()
    if not pw_hash or not check_password_hash(pw_hash, current_password):
        return jsonify({"error": "Current password is incorrect"}), 403

    new_hash = generate_password_hash(new_password)
    storage_save(_KEY_PASSWORD_HASH, {"hash": new_hash}, "system")
    audit_log("district_admin_password_changed", "Password rotated", user="district_admin", teacher_id="system")
    return jsonify({"status": "password_changed"})


# ── GET /api/district/config-status ──────────────────────────────────────────

@district_bp.route("/api/district/config-status", methods=["GET"])
@handle_route_errors
def district_config_status():
    """Public endpoint: returns high-level config status (no secrets)."""
    sis_config = storage_load(_KEY_SIS_CONFIG, "system")
    ai_keys = storage_load(_KEY_AI_KEYS, "system")

    sis_provider = None
    if sis_config and isinstance(sis_config, dict):
        sis_provider = sis_config.get("sis_type")

    has_ai_keys = False
    if ai_keys and isinstance(ai_keys, dict):
        has_ai_keys = bool(ai_keys.get("openai_api_key") or ai_keys.get("anthropic_api_key"))

    return jsonify({
        "sis_provider": sis_provider,
        "has_ai_keys": has_ai_keys,
    })


# ── GET /api/district/config ────────────────────────────────────────────────

@district_bp.route("/api/district/config", methods=["GET"])
@_require_district_admin
@handle_route_errors
def district_get_config():
    """Return full config with masked secrets."""
    sis_config = storage_load(_KEY_SIS_CONFIG, "system") or {}
    ai_keys = storage_load(_KEY_AI_KEYS, "system") or {}

    return jsonify({
        "sis": {
            "sis_type": sis_config.get("sis_type"),
            "client_id": sis_config.get("client_id", ""),
            "has_client_secret": bool(sis_config.get("client_secret")),
            "base_url": sis_config.get("base_url", ""),
            "token_url": sis_config.get("token_url", ""),
            "school_id": sis_config.get("school_id", ""),
            "teacher_sourced_id": sis_config.get("teacher_sourced_id", ""),
            "redirect_uri": sis_config.get("redirect_uri", ""),
            "district_token": sis_config.get("district_token", ""),
            "has_district_token": bool(sis_config.get("district_token")),
        },
        "ai_keys": {
            "has_openai_key": bool(ai_keys.get("openai_api_key")),
            "has_anthropic_key": bool(ai_keys.get("anthropic_api_key")),
        },
    })


# ── POST /api/district/config ───────────────────────────────────────────────

@district_bp.route("/api/district/config", methods=["POST"])
@_require_district_admin
@handle_route_errors
def district_save_config():
    """Save SIS and AI key configuration."""
    data = request.get_json(silent=True) or {}
    sis_data = data.get("sis", {})
    ai_data = data.get("ai_keys", {})

    # ── SIS config ──
    if sis_data:
        sis_type = sis_data.get("sis_type")
        if sis_type not in ("clever", "oneroster"):
            return jsonify({"error": "sis_type must be 'clever' or 'oneroster'"}), 400

        if not sis_data.get("client_id") and not sis_data.get("client_secret"):
            # Allow saving type-only if no credentials provided yet
            pass
        elif not sis_data.get("client_id"):
            return jsonify({"error": "client_id is required"}), 400

        existing_sis = storage_load(_KEY_SIS_CONFIG, "system") or {}

        merged = {"sis_type": sis_type}
        # Merge fields with rules: empty string = keep existing, None = clear
        for field in ("client_id", "client_secret", "base_url", "token_url",
                      "school_id", "teacher_sourced_id", "redirect_uri", "district_token"):
            new_val = sis_data.get(field)
            if new_val is None:
                # Explicit null = clear
                continue
            elif new_val == "":
                # Empty string = keep existing
                old_val = existing_sis.get(field, "")
                if old_val:
                    merged[field] = old_val
            else:
                merged[field] = new_val

        storage_save(_KEY_SIS_CONFIG, merged, "system")
        audit_log("district_sis_config_saved", f"SIS type: {sis_type}", user="district_admin", teacher_id="system")

    # ── AI keys ──
    if ai_data:
        existing_ai = storage_load(_KEY_AI_KEYS, "system") or {}

        for key_name in ("openai_api_key", "anthropic_api_key"):
            new_val = ai_data.get(key_name)
            if new_val is None:
                # Explicit null = delete
                existing_ai.pop(key_name, None)
            elif new_val == "":
                # Empty string = keep existing
                pass
            else:
                existing_ai[key_name] = new_val

        storage_save(_KEY_AI_KEYS, existing_ai, "system")
        audit_log("district_ai_keys_saved", "AI keys updated", user="district_admin", teacher_id="system")

    return jsonify({"status": "saved"})


# ── POST /api/district/test-connection ───────────────────────────────────────

@district_bp.route("/api/district/test-connection", methods=["POST"])
@_require_district_admin
@handle_route_errors
def district_test_connection():
    """Test SIS connectivity."""
    sis_config = storage_load(_KEY_SIS_CONFIG, "system")
    if not sis_config or not isinstance(sis_config, dict):
        return jsonify({"error": "SIS not configured"}), 400

    sis_type = sis_config.get("sis_type")

    if sis_type == "clever":
        # For Clever, validate config format (OAuth flow tested at login time)
        if sis_config.get("client_id") and sis_config.get("client_secret"):
            return jsonify({"status": "config_valid", "message": "Clever credentials present. Connection tested during OAuth login."})
        return jsonify({"error": "Clever client_id and client_secret required"}), 400

    if sis_type == "oneroster":
        # Test OneRoster connectivity
        base_url = sis_config.get("base_url")
        client_id = sis_config.get("client_id")
        client_secret = sis_config.get("client_secret")

        if not all([base_url, client_id, client_secret]):
            return jsonify({"error": "OneRoster requires base_url, client_id, and client_secret"}), 400

        try:
            import asyncio
            from backend.oneroster import OneRosterClient

            client = OneRosterClient(
                base_url=base_url,
                client_id=client_id,
                client_secret=client_secret,
                token_url=sis_config.get("token_url"),
            )

            async def _test():
                async with __import__("httpx").AsyncClient(timeout=15.0) as http:
                    await client._ensure_token(http)
                    url = f"{client.base_url}/classes?limit=1"
                    return await client._get_with_retry(http, url, label="district-test-connection")

            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(_test())
            finally:
                loop.close()

            return jsonify({"status": "connected"})
        except Exception as e:
            logger.warning("District OneRoster connection test failed: %s", str(e))
            return jsonify({"error": f"Connection failed: {str(e)}"}), 502

    return jsonify({"error": f"Unknown SIS type: {sis_type}"}), 400
