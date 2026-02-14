"""
Auth Routes for Graider.
Handles signup approval status checks, admin notification on new signups,
and one-click user approval via HMAC-signed links.
"""
import os
import hmac
import hashlib
import logging
import requests
from flask import Blueprint, request, jsonify, g

auth_bp = Blueprint('auth', __name__)
logger = logging.getLogger(__name__)

# Lazy Supabase admin client (same pattern as stripe_routes.py)
_supabase = None


def _get_supabase():
    """Get or create Supabase admin client for user metadata access."""
    global _supabase
    if _supabase is None:
        from supabase import create_client
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_KEY")
        if not url or not key:
            raise Exception("Supabase credentials not configured")
        _supabase = create_client(url, key)
    return _supabase


def _get_hmac_secret():
    """Get the secret used to sign approval links.

    Uses SUPABASE_JWT_SECRET — it's already a server-side secret in the env.
    """
    secret = os.getenv("SUPABASE_JWT_SECRET", "")
    if not secret:
        raise Exception("SUPABASE_JWT_SECRET not configured")
    return secret


def _sign_approval(user_id, email):
    """Generate HMAC signature for a user approval link."""
    secret = _get_hmac_secret()
    message = "approve:" + user_id + ":" + email
    return hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()


def _build_approve_url(user_id, email):
    """Build the one-click approval URL for the admin email."""
    from urllib.parse import quote
    token = _sign_approval(user_id, email)
    base = os.getenv("APP_URL", "https://app.graider.live")
    return (base + "/api/auth/approve-user?user_id=" + quote(user_id) +
            "&email=" + quote(email) + "&token=" + token)


@auth_bp.route('/api/auth/approve-user', methods=['GET', 'POST'])
def approve_user():
    """One-click user approval from admin notification email.

    PUBLIC endpoint — secured by HMAC token, not JWT.
    GET so it works as a simple link click from email.
    """
    user_id = request.args.get("user_id", "")
    email = request.args.get("email", "")
    token = request.args.get("token", "")

    if not user_id or not email or not token:
        return _approval_page("Missing parameters.", success=False)

    # Verify HMAC
    try:
        expected = _sign_approval(user_id, email)
    except Exception:
        return _approval_page("Server configuration error.", success=False)

    if not hmac.compare_digest(token, expected):
        return _approval_page("Invalid or expired approval link.", success=False)

    # Set approved: true in Supabase user metadata
    try:
        sb = _get_supabase()
        sb.auth.admin.update_user_by_id(user_id, {"user_metadata": {"approved": True}})
        logger.info("User approved: %s (%s)", email, user_id)
        return _approval_page(email + " has been approved!", success=True)
    except Exception as e:
        logger.error("Failed to approve user %s: %s", user_id, str(e))
        return _approval_page("Failed to approve user: " + str(e), success=False)


def _approval_page(message, success=True):
    """Return a simple branded HTML page for the approval result."""
    color = "#4ade80" if success else "#f87171"
    icon = "&#10003;" if success else "&#10007;"
    return (
        '<div style="max-width:480px;margin:80px auto;font-family:-apple-system,BlinkMacSystemFont,'
        "'Segoe UI',Roboto,sans-serif;text-align:center\">"
        '<div style="background:#1a1a2e;border-radius:16px;padding:40px 32px">'
        '<h1 style="color:#a5b4fc;font-size:2rem;font-weight:800;margin:0 0 24px">Graider</h1>'
        '<div style="font-size:3rem;color:' + color + ';margin:0 0 16px">' + icon + '</div>'
        '<p style="color:#ffffff;font-size:1.1rem;margin:0">' + message + '</p>'
        '</div></div>'
    ), 200, {"Content-Type": "text/html"}


@auth_bp.route('/api/auth/approval-status', methods=['GET'])
def approval_status():
    """
    Check if the current user is approved.
    Authenticated endpoint but exempt from the approval gate itself.
    On localhost, always returns approved.
    """
    try:
        # Localhost bypass
        if g.user_id == 'local-dev':
            return jsonify({"approved": True})

        sb = _get_supabase()
        res = sb.auth.admin.get_user_by_id(g.user_id)
        meta = res.user.user_metadata or {}

        return jsonify({
            "approved": meta.get("approved", False),
            "email": res.user.email,
            "first_name": meta.get("first_name", ""),
        })
    except Exception as e:
        logger.error("Error checking approval status: %s", str(e))
        return jsonify({"error": "Failed to check approval status"}), 500


@auth_bp.route('/api/auth/notify-signup', methods=['POST'])
def notify_signup():
    """
    PUBLIC endpoint — no JWT required.
    Sends admin notification email via Resend when a new user signs up.
    Fire-and-forget: errors are logged but don't fail the response.
    """
    data = request.get_json()
    if not data or not data.get("email"):
        return jsonify({"error": "Missing email"}), 400

    email = data["email"]
    first_name = data.get("first_name", "")
    last_name = data.get("last_name", "")

    admin_email = os.getenv("ADMIN_EMAIL")
    resend_key = os.getenv("RESEND_API_KEY")

    if not admin_email or not resend_key:
        logger.warning("ADMIN_EMAIL or RESEND_API_KEY not configured, skipping signup notification")
        return jsonify({"status": "skipped"})

    try:
        full_name = (first_name + " " + last_name).strip() or email

        # Look up the Supabase user ID so we can build the approval link.
        # The user was just created, so we search by email via admin API.
        approve_html = ""
        try:
            sb = _get_supabase()
            # List users filtered by email (admin API)
            users_resp = sb.auth.admin.list_users()
            user_id = None
            for u in users_resp:
                if getattr(u, 'email', '') == email:
                    user_id = u.id
                    break
            if user_id:
                approve_url = _build_approve_url(user_id, email)
                approve_html = (
                    '<p style="margin:24px 0 8px">'
                    '<a href="' + approve_url + '" style="display:inline-block;'
                    'background:#6366f1;color:#ffffff;text-decoration:none;'
                    'padding:14px 36px;border-radius:12px;font-weight:600;'
                    'font-size:1rem">Approve ' + first_name + '</a></p>'
                    '<p style="color:#6b7280;font-size:0.8rem">'
                    'This link is single-use and tied to this account.</p>'
                )
            else:
                logger.warning("Could not find user_id for %s to build approval link", email)
        except Exception as lookup_err:
            logger.warning("Could not build approval link: %s", str(lookup_err))

        supabase_url = os.getenv("SUPABASE_URL", "")
        project_ref = supabase_url.replace("https://", "").split(".")[0] if supabase_url else ""
        dashboard_link = (
            "https://supabase.com/dashboard/project/" + project_ref + "/auth/users"
            if project_ref else "https://supabase.com/dashboard"
        )

        requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": "Bearer " + resend_key,
                "Content-Type": "application/json",
            },
            json={
                "from": "Graider <noreply@notifications.graider.live>",
                "to": [admin_email],
                "subject": "New Graider Signup: " + full_name,
                "html": (
                    '<div style="max-width:480px;margin:40px auto;font-family:-apple-system,'
                    "BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif\">"
                    '<div style="background:#1a1a2e;border-radius:16px;padding:40px 32px;text-align:center">'
                    '<h1 style="color:#a5b4fc;font-size:2rem;font-weight:800;margin:0 0 24px">Graider</h1>'
                    '<h2 style="color:#ffffff;font-size:1.25rem;margin:0 0 16px">New Signup</h2>'
                    '<p style="color:#9ca3af;font-size:0.95rem;line-height:1.6;margin:0 0 8px">'
                    '<strong style="color:#ffffff">' + full_name + '</strong></p>'
                    '<p style="color:#9ca3af;font-size:0.95rem;margin:0 0 24px">' + email + '</p>'
                    + approve_html +
                    '<p style="margin:16px 0 0"><a href="' + dashboard_link + '" '
                    'style="color:#6b7280;font-size:0.85rem;text-decoration:underline">'
                    'View in Supabase Dashboard</a></p>'
                    '</div></div>'
                ),
            },
            timeout=10,
        )
        logger.info("Signup notification sent for %s", email)
    except Exception as e:
        logger.error("Failed to send signup notification: %s", str(e))

    return jsonify({"status": "ok"})
