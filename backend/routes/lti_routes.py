"""
LTI 1.3 Routes for Graider
===========================
Endpoints for OIDC login initiation, launch callback, JWKS,
platform configuration, and AGS grade sync.
"""

import hmac
import logging
import os

from flask import Blueprint, g, jsonify, redirect, request, session

from backend.lti import (
    get_jwks,
    build_oidc_login_response,
    validate_launch_jwt,
    extract_launch_data,
    get_platform_config,
    save_platform_config,
    list_platform_configs,
    delete_platform_config,
    save_ags_context,
    get_ags_context,
    list_ags_contexts,
    save_lti_user_mapping,
    get_lti_user_mappings,
    match_scores_to_lti_users,
    AGSClient,
)
from backend.utils.auth_decorators import require_teacher
from backend.utils.errors import handle_route_errors
from backend.utils.audit import audit_log

logger = logging.getLogger(__name__)

lti_bp = Blueprint("lti", __name__)


def _get_tool_url():
    """Return the tool's base URL (no trailing slash).
    In production, set LTI_TOOL_URL=https://app.graider.live on Railway."""
    env_url = os.getenv("LTI_TOOL_URL")
    if env_url:
        return env_url.rstrip("/")
    # Auto-detect production from request host
    host = request.host_url.rstrip("/")
    if "graider.live" in host:
        return "https://app.graider.live"
    return host


# ══════════════════════════════════════════════════════════════
# PUBLIC ENDPOINTS (called by LMS platforms)
# ══════════════════════════════════════════════════════════════

@lti_bp.route("/api/lti/jwks", methods=["GET"])
@handle_route_errors
def lti_jwks():
    """Serve the tool's public JWKS document."""
    return jsonify(get_jwks())


@lti_bp.route("/api/lti/login", methods=["GET", "POST"])
@handle_route_errors
def lti_login():
    """OIDC login initiation — redirects to the platform's auth endpoint."""
    if request.method == "POST":
        params = {
            "iss": request.form.get("iss", ""),
            "login_hint": request.form.get("login_hint", ""),
            "target_link_uri": request.form.get("target_link_uri", ""),
            "lti_message_hint": request.form.get("lti_message_hint", ""),
            "client_id": request.form.get("client_id", ""),
        }
    else:
        params = {
            "iss": request.args.get("iss", ""),
            "login_hint": request.args.get("login_hint", ""),
            "target_link_uri": request.args.get("target_link_uri", ""),
            "lti_message_hint": request.args.get("lti_message_hint", ""),
            "client_id": request.args.get("client_id", ""),
        }

    issuer = params.get("iss")
    if not issuer:
        return jsonify({"error": "Missing iss parameter"}), 400

    # Look up platform config (try system-level since we don't know teacher yet)
    platform_config = get_platform_config(issuer)
    if not platform_config:
        return jsonify({"error": "Unregistered platform"}), 403

    tool_url = _get_tool_url()
    redirect_url, state, nonce = build_oidc_login_response(params, platform_config, tool_url)

    # Store state/nonce/issuer in Flask session for validation on launch callback
    session["lti_state"] = state
    session["lti_nonce"] = nonce
    session["lti_issuer"] = issuer

    return redirect(redirect_url)


@lti_bp.route("/api/lti/launch", methods=["POST"])
@handle_route_errors
def lti_launch():
    """LTI 1.3 launch callback — validates id_token and establishes session."""
    id_token = request.form.get("id_token", "")
    state = request.form.get("state", "")

    # Validate state matches session (constant-time, issue #373)
    expected_state = session.get("lti_state")
    if not expected_state or not hmac.compare_digest(
        state.encode("utf-8"), expected_state.encode("utf-8"),
    ):
        return jsonify({"error": "Invalid state parameter"}), 400

    issuer = session.get("lti_issuer", "")
    platform_config = get_platform_config(issuer)
    if not platform_config:
        return jsonify({"error": "Platform not found"}), 403

    # Validate JWT
    try:
        claims = validate_launch_jwt(id_token, platform_config)
    except ValueError as e:
        logger.warning("LTI launch JWT validation failed: %s", e)
        return jsonify({"error": "id_token validation failed"}), 400

    # Validate nonce (constant-time, issue #373)
    expected_nonce = session.get("lti_nonce")
    token_nonce = claims.get("nonce") or ""
    if not expected_nonce or not hmac.compare_digest(
        token_nonce.encode("utf-8"), expected_nonce.encode("utf-8"),
    ):
        return jsonify({"error": "Invalid nonce"}), 400

    # Extract launch data
    launch_data = extract_launch_data(claims)

    # Store launch data in session
    session["lti_launch"] = launch_data
    session["lti_user_id"] = launch_data.get("user_id")
    session["lti_is_instructor"] = launch_data.get("is_instructor", False)

    # Clear OIDC state from session
    session.pop("lti_state", None)
    session.pop("lti_nonce", None)

    # Resolve owner teacher ID
    owner_teacher_id = platform_config.get("_registered_by") or "system"

    # For instructor launches with AGS endpoint, save AGS context
    if launch_data.get("is_instructor") and launch_data.get("ags_endpoint"):
        context_id = launch_data.get("context_id", "")
        if context_id:
            save_ags_context(owner_teacher_id, issuer, context_id, {
                "ags_endpoint": launch_data.get("ags_endpoint"),
                "ags_lineitems_url": launch_data.get("ags_lineitems_url"),
                "ags_scores_url": launch_data.get("ags_scores_url"),
                "context_id": context_id,
                "context_title": launch_data.get("context_title", ""),
                "resource_link_id": launch_data.get("resource_link_id", ""),
                "platform_issuer": issuer,
            })

    # For student launches, save user mapping
    if not launch_data.get("is_instructor"):
        context_id = launch_data.get("context_id", "")
        lti_sub = launch_data.get("user_id", "")
        student_name = launch_data.get("name", "")
        email = launch_data.get("email")
        if context_id and lti_sub:
            save_lti_user_mapping(
                teacher_id=owner_teacher_id,
                platform_issuer=issuer,
                context_id=context_id,
                lti_sub=lti_sub,
                student_name=student_name,
                email=email,
            )

    # Redirect based on role
    if launch_data.get("is_instructor"):
        return redirect("/")
    else:
        return redirect("/student")


# ══════════════════════════════════════════════════════════════
# TEACHER-AUTHENTICATED ENDPOINTS
# ══════════════════════════════════════════════════════════════

@lti_bp.route("/api/lti/config", methods=["GET"])
@require_teacher
@handle_route_errors
def lti_config_get():
    """List registered platforms and tool config URLs."""
    tool_url = _get_tool_url()

    # Load platform configs for this teacher
    keys = list_platform_configs(g.teacher_id)
    platforms = []
    from backend import storage
    for key in (keys or []):
        config = storage.load(key, g.teacher_id)
        if config:
            # Never expose secrets — return safe fields only
            platforms.append({
                "issuer": config.get("issuer", ""),
                "client_id": config.get("client_id", ""),
                "auth_endpoint": config.get("auth_endpoint", ""),
                "jwks_uri": config.get("jwks_uri", ""),
                "token_url": config.get("token_url", ""),
            })

    return jsonify({
        "tool_config": {
            "oidc_login_url": tool_url + "/api/lti/login",
            "launch_url": tool_url + "/api/lti/launch",
            "jwks_url": tool_url + "/api/lti/jwks",
            "redirect_uri": tool_url + "/api/lti/launch",
        },
        "platforms": platforms,
    })


@lti_bp.route("/api/lti/config", methods=["POST"])
@require_teacher
@handle_route_errors
def lti_config_post():
    """Register a new LTI platform."""
    data = request.json or {}

    required_fields = ["issuer", "client_id", "auth_login_url", "auth_token_url", "jwks_url"]
    missing = [f for f in required_fields if not data.get(f)]
    if missing:
        return jsonify({"error": "Missing required fields: " + ", ".join(missing)}), 400

    issuer = data["issuer"]
    config = {
        "issuer": issuer,
        "client_id": data["client_id"],
        "auth_endpoint": data["auth_login_url"],
        "token_url": data["auth_token_url"],
        "jwks_uri": data["jwks_url"],
        "deployment_ids": list(data.get("deployment_ids") or []),
        "_registered_by": g.teacher_id,
    }

    save_platform_config(issuer, config, g.teacher_id)
    audit_log("lti_platform_registered", f"issuer={issuer}", teacher_id=g.teacher_id)

    return jsonify({"status": "ok", "issuer": issuer})


@lti_bp.route("/api/lti/contexts", methods=["GET"])
@require_teacher
@handle_route_errors
def lti_contexts():
    """List AGS contexts with student counts."""
    keys = list_ags_contexts(g.teacher_id)
    contexts = []
    from backend import storage
    for key in (keys or []):
        ctx_data = storage.load(key, g.teacher_id)
        if ctx_data:
            # Fetch student count for this context
            platform_issuer = ctx_data.get("platform_issuer", "")
            context_id = ctx_data.get("context_id", "")
            mappings = get_lti_user_mappings(g.teacher_id, platform_issuer, context_id)
            ctx_data["student_count"] = len(mappings) if mappings else 0
            contexts.append(ctx_data)

    return jsonify({"contexts": contexts})


@lti_bp.route("/api/lti/config", methods=["DELETE"])
@require_teacher
@handle_route_errors
def lti_config_delete():
    """Delete a platform registration."""
    data = request.json or {}
    issuer = data.get("issuer", "")
    if not issuer:
        return jsonify({"error": "Missing issuer"}), 400

    delete_platform_config(issuer, g.teacher_id)
    audit_log("lti_platform_deleted", f"issuer={issuer}", teacher_id=g.teacher_id)

    return jsonify({"status": "ok"})


@lti_bp.route("/api/lti/sync-grades", methods=["POST"])
@require_teacher
@handle_route_errors
def lti_sync_grades():
    """Sync grades to the LMS via AGS.

    Two modes:
    - Auto-match: scores=[{student_name, score}] — resolves LTI user IDs via mappings
    - Direct: resolved_scores=[{user_id, score, comment}] — uses provided user IDs
    """
    data = request.json or {}

    platform_issuer = data.get("platform_issuer", "")
    context_id = data.get("context_id", "")
    lineitem_url = data.get("lineitem_url", "")
    label = data.get("label", "Graider Grade")
    max_score = float(data.get("max_score", 100))

    if not platform_issuer or not context_id:
        return jsonify({"error": "Missing platform_issuer or context_id"}), 400

    # Load AGS endpoint from persisted context (NOT from platform registration)
    ags_data = get_ags_context(g.teacher_id, platform_issuer, context_id)
    if not ags_data:
        return jsonify({"error": "No AGS context found for this platform/context"}), 404

    ags_endpoint = ags_data.get("ags_endpoint", "")
    if not ags_endpoint:
        return jsonify({"error": "AGS endpoint not available"}), 400

    # Load platform config for AGS client
    platform_config = get_platform_config(platform_issuer, g.teacher_id)
    if not platform_config:
        return jsonify({"error": "Platform not configured"}), 404

    # Build list of scores to post
    scores_to_post = []
    unmatched_students = []

    if data.get("resolved_scores"):
        # Direct mode — user IDs already provided
        scores_to_post = data["resolved_scores"]
    elif data.get("scores"):
        # Auto-match mode — resolve LTI user IDs via mappings
        user_mappings = get_lti_user_mappings(g.teacher_id, platform_issuer, context_id)
        matched, unmatched_students = match_scores_to_lti_users(data["scores"], user_mappings)
        for m in matched:
            scores_to_post.append({
                "user_id": m["lti_sub"],
                "score": m.get("score", 0),
                "comment": m.get("comment", ""),
            })
    else:
        return jsonify({"error": "Provide scores or resolved_scores"}), 400

    # Create AGS client
    ags_client = AGSClient(platform_config, ags_endpoint)

    # Create lineitem if not provided
    if not lineitem_url:
        resource_link_id = ags_data.get("resource_link_id", "")
        try:
            lineitem = ags_client.create_lineitem(label, max_score, resource_link_id)
            lineitem_url = lineitem.get("id", "")
        except Exception as e:
            logger.error("Failed to create lineitem: %s", e)
            return jsonify({"error": "Failed to create lineitem"}), 500

    # Post scores
    posted = 0
    errors = []
    for score_entry in scores_to_post:
        user_id = score_entry.get("user_id", "")
        score_val = float(score_entry.get("score", 0))
        comment = score_entry.get("comment")

        success = ags_client.post_score(lineitem_url, user_id, score_val, max_score, comment)
        if success:
            posted += 1
        else:
            errors.append(user_id)

    return jsonify({
        "posted": posted,
        "total": len(scores_to_post),
        "unmatched_students": unmatched_students,
        "errors": errors,
    })
