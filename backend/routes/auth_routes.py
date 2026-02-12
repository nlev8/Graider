"""
Auth Routes for Graider.
Handles signup approval status checks and admin notification on new signups.
"""
import os
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
        return jsonify({"status": "skipped", "has_admin": bool(admin_email), "has_resend": bool(resend_key)})

    try:
        full_name = (first_name + " " + last_name).strip() or email
        supabase_url = os.getenv("SUPABASE_URL", "")
        # Extract project ref for dashboard link
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
                    "<h2>New Graider Signup</h2>"
                    "<p><strong>Name:</strong> " + full_name + "</p>"
                    "<p><strong>Email:</strong> " + email + "</p>"
                    "<p>To approve this user, go to the Supabase dashboard, "
                    "find the user, and set <code>approved: true</code> in their user_metadata.</p>"
                    '<p><a href="' + dashboard_link + '">Open Supabase Users</a></p>'
                ),
            },
            timeout=10,
        )
        logger.info("Signup notification sent for %s", email)
    except Exception as e:
        logger.error("Failed to send signup notification: %s", str(e))

    return jsonify({"status": "ok"})
