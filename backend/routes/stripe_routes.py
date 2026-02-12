"""
Stripe Subscription Routes for Graider.
Handles checkout sessions, customer portal, subscription status, and webhooks.
Uses Supabase user_metadata to store stripe_customer_id.
"""
import os
import stripe
from flask import Blueprint, request, jsonify, g

stripe_bp = Blueprint('stripe', __name__)

# Lazy Supabase admin client (same pattern as student_portal_routes.py)
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


def _init_stripe():
    """Set Stripe API key from environment. Returns True if configured."""
    key = os.getenv("STRIPE_SECRET_KEY")
    if not key:
        return False
    stripe.api_key = key
    return True


def _is_local_dev():
    """Check if running in localhost dev mode (no real Supabase user)."""
    return g.user_id == 'local-dev'


def _get_user_metadata(user_id):
    """Fetch user_metadata from Supabase auth.users for the given user."""
    if _is_local_dev():
        return {}
    sb = _get_supabase()
    res = sb.auth.admin.get_user_by_id(user_id)
    return res.user.user_metadata or {}


def _update_user_metadata(user_id, metadata_update):
    """Merge metadata_update into the user's user_metadata."""
    if _is_local_dev():
        return
    sb = _get_supabase()
    sb.auth.admin.update_user_by_id(user_id, {"user_metadata": metadata_update})


def _get_or_create_customer(user_id, user_email):
    """
    Get existing Stripe customer ID from user_metadata,
    or create a new Stripe customer and store the ID.
    """
    meta = _get_user_metadata(user_id)
    customer_id = meta.get("stripe_customer_id")
    if customer_id:
        return customer_id

    # For local dev, check if a Stripe customer already exists with this email
    if _is_local_dev():
        existing = stripe.Customer.list(email=user_email, limit=1)
        if existing.data:
            return existing.data[0].id

    customer = stripe.Customer.create(
        email=user_email,
        metadata={"supabase_user_id": user_id},
    )
    _update_user_metadata(user_id, {"stripe_customer_id": customer.id})
    return customer.id


@stripe_bp.route('/api/stripe/subscription-status', methods=['GET'])
def subscription_status():
    """Get the current user's subscription status from Stripe."""
    if not _init_stripe():
        return jsonify({"error": "Stripe not configured"}), 500

    try:
        user_id = g.user_id
        meta = _get_user_metadata(user_id)
        customer_id = meta.get("stripe_customer_id")

        if not customer_id:
            return jsonify({"status": "none"})

        subs = stripe.Subscription.list(
            customer=customer_id, status="all", limit=1
        )
        if not subs.data:
            return jsonify({"status": "none"})

        sub = subs.data[0]
        plan_interval = "unknown"
        if sub.get("items") and sub["items"]["data"]:
            plan_interval = sub["items"]["data"][0]["price"]["recurring"]["interval"]

        return jsonify({
            "status": sub["status"],
            "plan": plan_interval,
            "current_period_end": sub["current_period_end"],
            "cancel_at_period_end": sub["cancel_at_period_end"],
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@stripe_bp.route('/api/stripe/create-checkout-session', methods=['POST'])
def create_checkout_session():
    """Create a Stripe Checkout session for a new subscription."""
    if not _init_stripe():
        return jsonify({"error": "Stripe not configured"}), 500

    try:
        data = request.get_json()
        if not data or data.get("plan") not in ("monthly", "annual"):
            return jsonify({"error": "Invalid plan. Use 'monthly' or 'annual'."}), 400

        price_id = (
            os.getenv("STRIPE_PRICE_ID_MONTHLY")
            if data["plan"] == "monthly"
            else os.getenv("STRIPE_PRICE_ID_ANNUAL")
        )
        if not price_id:
            return jsonify({"error": f"Price ID not configured for {data['plan']} plan"}), 500

        customer_id = _get_or_create_customer(g.user_id, g.user_email)

        host = request.host_url.rstrip("/")
        session = stripe.checkout.Session.create(
            customer=customer_id,
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            allow_promotion_codes=True,
            success_url=host + "?billing=success",
            cancel_url=host + "?billing=cancel",
        )
        return jsonify({"checkout_url": session.url})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@stripe_bp.route('/api/stripe/create-portal-session', methods=['POST'])
def create_portal_session():
    """Create a Stripe Customer Portal session for subscription management."""
    if not _init_stripe():
        return jsonify({"error": "Stripe not configured"}), 500

    try:
        meta = _get_user_metadata(g.user_id)
        customer_id = meta.get("stripe_customer_id")
        if not customer_id:
            return jsonify({"error": "No Stripe customer found"}), 400

        host = request.host_url.rstrip("/")
        session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=host + "?billing=portal-return",
        )
        return jsonify({"portal_url": session.url})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@stripe_bp.route('/api/stripe/webhook', methods=['POST'])
def stripe_webhook():
    """
    Handle Stripe webhook events. PUBLIC endpoint (no JWT).
    Verified via Stripe-Signature header.
    """
    if not _init_stripe():
        return jsonify({"error": "Stripe not configured"}), 500

    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    if not webhook_secret:
        return jsonify({"error": "Webhook secret not configured"}), 500

    payload = request.get_data(as_text=True)
    sig_header = request.headers.get("Stripe-Signature")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except stripe.error.SignatureVerificationError:
        return jsonify({"error": "Invalid signature"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    event_type = event["type"]

    if event_type == "checkout.session.completed":
        session_obj = event["data"]["object"]
        customer_id = session_obj.get("customer")
        sub_id = session_obj.get("subscription")
        if customer_id and sub_id:
            _sync_subscription_metadata(customer_id, sub_id)

    elif event_type in (
        "customer.subscription.updated",
        "customer.subscription.deleted",
    ):
        sub_obj = event["data"]["object"]
        customer_id = sub_obj.get("customer")
        sub_id = sub_obj.get("id")
        if customer_id:
            _sync_subscription_metadata(customer_id, sub_id)

    return jsonify({"received": True}), 200


def _sync_subscription_metadata(customer_id, subscription_id):
    """
    Look up the Supabase user by stripe_customer_id and update
    their user_metadata with current subscription status.
    """
    try:
        sub = stripe.Subscription.retrieve(subscription_id)
        plan_interval = "unknown"
        if sub.get("items") and sub["items"]["data"]:
            plan_interval = sub["items"]["data"][0]["price"]["recurring"]["interval"]

        # Find user by customer ID in Supabase
        sb = _get_supabase()
        users = sb.auth.admin.list_users()
        target_user = None
        for u in users:
            meta = u.user_metadata or {}
            if meta.get("stripe_customer_id") == customer_id:
                target_user = u
                break

        if target_user:
            _update_user_metadata(target_user.id, {
                "subscription_status": sub["status"],
                "subscription_plan": plan_interval,
                "subscription_period_end": sub["current_period_end"],
                "subscription_cancel_at_period_end": sub["cancel_at_period_end"],
            })
    except Exception:
        pass  # Webhook must return 200; errors logged by Stripe retry
