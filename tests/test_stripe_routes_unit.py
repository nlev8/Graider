"""Unit tests for backend/routes/stripe_routes.py.

Audit MAJOR #4 sprint follow-up to PR #292. Targets the 123 uncovered
LOC (22% baseline). Covers all 4 endpoints + 7 helpers:

* subscription_status (GET) — Clever-user, no Stripe key, no
  customer, active subscription
* create_checkout_session (POST) — invalid plan, missing price, happy
* create_portal_session (POST) — no customer, happy
* stripe_webhook (POST, public) — bad sig, bad payload, all 3 event
  types, invalid event types pass-through

Rule #11 fix in scope: line 216 referenced an undeclared `logger`
(module defines `_logger`). Test pins the corrected behavior.

Strategy: patch `backend.routes.stripe_routes.stripe` so neither
stripe.api_key nor any stripe.* method calls reach the real Stripe
network. _get_supabase patched at the module's import site too.
"""
from __future__ import annotations

import json
import os
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

import pytest


@pytest.fixture
def client():
    from backend.app import app
    from backend.extensions import limiter
    try:
        limiter.reset()
    except Exception:
        pass
    with app.test_client() as c:
        yield c


@pytest.fixture
def auth_headers():
    return {"X-Test-Teacher-Id": "user-1", "Content-Type": "application/json"}


@pytest.fixture(autouse=True)
def dev_env(monkeypatch):
    # FLASK_ENV=development → @require_teacher honors X-Test-Teacher-Id
    # STRIPE_SECRET_KEY default ON so _init_stripe returns True.
    monkeypatch.setenv("FLASK_ENV", "development")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_123")


# ──────────────────────────────────────────────────────────────────
# Helper-level tests (_init_stripe, _is_local_dev, etc.)
# ──────────────────────────────────────────────────────────────────


class TestInitStripe:
    def test_returns_false_without_key(self, monkeypatch):
        # Patch os.getenv directly within the route module so we don't
        # have to fight env-var hydration from .env loaders.
        with patch(
            "backend.routes.stripe_routes.os.getenv",
            side_effect=lambda k, *a, **kw: "" if k == "STRIPE_SECRET_KEY" else os.environ.get(k, *a),
        ):
            from backend.routes.stripe_routes import _init_stripe
            assert _init_stripe() is False

    def test_returns_true_and_sets_api_key(self, monkeypatch):
        monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_xyz")
        with patch("backend.routes.stripe_routes.stripe") as mock_stripe:
            from backend.routes.stripe_routes import _init_stripe
            assert _init_stripe() is True
            assert mock_stripe.api_key == "sk_test_xyz"


# ──────────────────────────────────────────────────────────────────
# /api/stripe/subscription-status (GET)
# ──────────────────────────────────────────────────────────────────


class TestSubscriptionStatus:
    def test_clever_user_returns_district(self, client, auth_headers):
        # X-Test-Teacher-Id starts with "clever:" → district short-circuit
        headers = {**auth_headers, "X-Test-Teacher-Id": "clever:abc"}
        resp = client.get(
            "/api/stripe/subscription-status", headers=headers,
        )
        body = resp.get_json()
        assert body["status"] == "district"
        assert "billing handled" in body["message"].lower()

    def test_no_stripe_key_returns_500(self, client, auth_headers, monkeypatch):
        # Force `os.getenv("STRIPE_SECRET_KEY")` to return "" within
        # stripe_routes (config.py reloads .env on import; setenv alone
        # doesn't stick). All other env lookups pass through unchanged.
        monkeypatch.setattr(
            "backend.routes.stripe_routes.os.getenv",
            lambda k, *a, **kw: "" if k == "STRIPE_SECRET_KEY" else os.environ.get(k, *a),
        )
        resp = client.get(
            "/api/stripe/subscription-status", headers=auth_headers,
        )
        assert resp.status_code == 500
        assert "not configured" in resp.get_json()["error"]

    def test_no_customer_returns_status_none(self, client, auth_headers):
        # _get_user_metadata returns {} → no stripe_customer_id
        with patch(
            "backend.routes.stripe_routes._get_user_metadata",
            return_value={},
        ):
            resp = client.get(
                "/api/stripe/subscription-status", headers=auth_headers,
            )
        assert resp.get_json()["status"] == "none"

    def test_no_subscriptions_returns_status_none(
        self, client, auth_headers,
    ):
        with patch(
            "backend.routes.stripe_routes._get_user_metadata",
            return_value={"stripe_customer_id": "cus_123"},
        ), patch(
            "backend.routes.stripe_routes.stripe",
        ) as mock_stripe:
            mock_stripe.Subscription.list.return_value = SimpleNamespace(
                data=[],
            )
            resp = client.get(
                "/api/stripe/subscription-status", headers=auth_headers,
            )
        assert resp.get_json()["status"] == "none"

    def test_active_subscription_returns_full_status(
        self, client, auth_headers,
    ):
        sub = {
            "status": "active",
            "current_period_end": 1735689600,
            "cancel_at_period_end": False,
            "items": {
                "data": [
                    {"price": {"recurring": {"interval": "month"}}},
                ],
            },
        }
        # The test stub uses dict-like access via .get() and ["..."]
        # Wrap in a class that supports both styles + __getitem__.
        class FakeSub(dict):
            def get(self, k, default=None):  # type: ignore[override]
                return super().get(k, default)
        fake_sub = FakeSub(sub)
        with patch(
            "backend.routes.stripe_routes._get_user_metadata",
            return_value={"stripe_customer_id": "cus_123"},
        ), patch(
            "backend.routes.stripe_routes.stripe",
        ) as mock_stripe:
            mock_stripe.Subscription.list.return_value = SimpleNamespace(
                data=[fake_sub],
            )
            resp = client.get(
                "/api/stripe/subscription-status", headers=auth_headers,
            )
        body = resp.get_json()
        assert body["status"] == "active"
        assert body["plan"] == "month"
        assert body["current_period_end"] == 1735689600
        assert body["cancel_at_period_end"] is False

    def test_unexpected_exception_returns_500(self, client, auth_headers):
        with patch(
            "backend.routes.stripe_routes._get_user_metadata",
            side_effect=RuntimeError("supabase down"),
        ):
            resp = client.get(
                "/api/stripe/subscription-status", headers=auth_headers,
            )
        assert resp.status_code == 500


# ──────────────────────────────────────────────────────────────────
# /api/stripe/create-checkout-session (POST)
# ──────────────────────────────────────────────────────────────────


class TestCreateCheckoutSession:
    def test_no_stripe_key_returns_500(
        self, client, auth_headers, monkeypatch,
    ):
        # Force `os.getenv("STRIPE_SECRET_KEY")` to return "" within
        # stripe_routes (config.py reloads .env on import; setenv alone
        # doesn't stick). All other env lookups pass through unchanged.
        monkeypatch.setattr(
            "backend.routes.stripe_routes.os.getenv",
            lambda k, *a, **kw: "" if k == "STRIPE_SECRET_KEY" else os.environ.get(k, *a),
        )
        resp = client.post(
            "/api/stripe/create-checkout-session",
            data=json.dumps({"plan": "monthly"}),
            headers=auth_headers,
        )
        assert resp.status_code == 500

    def test_invalid_plan_returns_400(self, client, auth_headers):
        resp = client.post(
            "/api/stripe/create-checkout-session",
            data=json.dumps({"plan": "weekly"}),
            headers=auth_headers,
        )
        assert resp.status_code == 400
        assert "Invalid plan" in resp.get_json()["error"]

    def test_no_body_returns_400(self, client, auth_headers):
        # request.get_json returns None → falls through invalid-plan check
        resp = client.post(
            "/api/stripe/create-checkout-session",
            data="{}",  # parses to {} not None
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_missing_price_id_returns_500(
        self, client, auth_headers, monkeypatch,
    ):
        monkeypatch.delenv("STRIPE_PRICE_ID_MONTHLY", raising=False)
        monkeypatch.delenv("STRIPE_PRICE_ID_ANNUAL", raising=False)
        resp = client.post(
            "/api/stripe/create-checkout-session",
            data=json.dumps({"plan": "monthly"}),
            headers=auth_headers,
        )
        assert resp.status_code == 500
        assert "Price ID not configured" in resp.get_json()["error"]

    def test_happy_path_returns_checkout_url(
        self, client, auth_headers, monkeypatch,
    ):
        monkeypatch.setenv("STRIPE_PRICE_ID_MONTHLY", "price_monthly_123")

        with patch(
            "backend.routes.stripe_routes._get_or_create_customer",
            return_value="cus_999",
        ), patch(
            "backend.routes.stripe_routes.stripe",
        ) as mock_stripe:
            fake_session = MagicMock()
            fake_session.url = "https://checkout.stripe.com/pay/cs_test_xyz"
            mock_stripe.checkout.Session.create.return_value = fake_session
            resp = client.post(
                "/api/stripe/create-checkout-session",
                data=json.dumps({"plan": "monthly"}),
                headers=auth_headers,
            )
        body = resp.get_json()
        assert body["checkout_url"].endswith("cs_test_xyz")

    def test_annual_plan_uses_annual_price_id(
        self, client, auth_headers, monkeypatch,
    ):
        monkeypatch.setenv("STRIPE_PRICE_ID_ANNUAL", "price_annual_999")
        with patch(
            "backend.routes.stripe_routes._get_or_create_customer",
            return_value="cus_888",
        ), patch(
            "backend.routes.stripe_routes.stripe",
        ) as mock_stripe:
            fake_session = MagicMock()
            fake_session.url = "https://checkout/yearly"
            mock_stripe.checkout.Session.create.return_value = fake_session
            client.post(
                "/api/stripe/create-checkout-session",
                data=json.dumps({"plan": "annual"}),
                headers=auth_headers,
            )
        # Inspect line_items kwarg
        kwargs = mock_stripe.checkout.Session.create.call_args.kwargs
        assert kwargs["line_items"][0]["price"] == "price_annual_999"

    def test_stripe_create_failure_returns_500(
        self, client, auth_headers, monkeypatch,
    ):
        monkeypatch.setenv("STRIPE_PRICE_ID_MONTHLY", "p_m")
        with patch(
            "backend.routes.stripe_routes._get_or_create_customer",
            return_value="cus_x",
        ), patch(
            "backend.routes.stripe_routes.stripe",
        ) as mock_stripe:
            mock_stripe.checkout.Session.create.side_effect = (
                RuntimeError("api down")
            )
            resp = client.post(
                "/api/stripe/create-checkout-session",
                data=json.dumps({"plan": "monthly"}),
                headers=auth_headers,
            )
        assert resp.status_code == 500


# ──────────────────────────────────────────────────────────────────
# /api/stripe/create-portal-session (POST)
# ──────────────────────────────────────────────────────────────────


class TestCreatePortalSession:
    def test_no_stripe_key_returns_500(
        self, client, auth_headers, monkeypatch,
    ):
        # Force `os.getenv("STRIPE_SECRET_KEY")` to return "" within
        # stripe_routes (config.py reloads .env on import; setenv alone
        # doesn't stick). All other env lookups pass through unchanged.
        monkeypatch.setattr(
            "backend.routes.stripe_routes.os.getenv",
            lambda k, *a, **kw: "" if k == "STRIPE_SECRET_KEY" else os.environ.get(k, *a),
        )
        resp = client.post(
            "/api/stripe/create-portal-session",
            data=json.dumps({}),
            headers=auth_headers,
        )
        assert resp.status_code == 500

    def test_no_customer_returns_400(self, client, auth_headers):
        with patch(
            "backend.routes.stripe_routes._get_user_metadata",
            return_value={},
        ):
            resp = client.post(
                "/api/stripe/create-portal-session",
                data=json.dumps({}),
                headers=auth_headers,
            )
        assert resp.status_code == 400
        assert "No Stripe customer" in resp.get_json()["error"]

    def test_happy_path_returns_portal_url(self, client, auth_headers):
        with patch(
            "backend.routes.stripe_routes._get_user_metadata",
            return_value={"stripe_customer_id": "cus_777"},
        ), patch(
            "backend.routes.stripe_routes.stripe",
        ) as mock_stripe:
            fake_session = MagicMock()
            fake_session.url = "https://billing.stripe.com/portal/abc"
            mock_stripe.billing_portal.Session.create.return_value = (
                fake_session
            )
            resp = client.post(
                "/api/stripe/create-portal-session",
                data=json.dumps({}),
                headers=auth_headers,
            )
        body = resp.get_json()
        assert "billing.stripe.com" in body["portal_url"]

    def test_stripe_create_failure_returns_500(self, client, auth_headers):
        with patch(
            "backend.routes.stripe_routes._get_user_metadata",
            return_value={"stripe_customer_id": "cus_X"},
        ), patch(
            "backend.routes.stripe_routes.stripe",
        ) as mock_stripe:
            mock_stripe.billing_portal.Session.create.side_effect = (
                RuntimeError("api error")
            )
            resp = client.post(
                "/api/stripe/create-portal-session",
                data=json.dumps({}),
                headers=auth_headers,
            )
        assert resp.status_code == 500


# ──────────────────────────────────────────────────────────────────
# /api/stripe/webhook (POST, public)
# ──────────────────────────────────────────────────────────────────


class TestWebhook:
    def test_no_stripe_key_returns_500(self, client, monkeypatch):
        # Force `os.getenv("STRIPE_SECRET_KEY")` to return "" within
        # stripe_routes (config.py reloads .env on import; setenv alone
        # doesn't stick). All other env lookups pass through unchanged.
        monkeypatch.setattr(
            "backend.routes.stripe_routes.os.getenv",
            lambda k, *a, **kw: "" if k == "STRIPE_SECRET_KEY" else os.environ.get(k, *a),
        )
        resp = client.post(
            "/api/stripe/webhook",
            data="{}",
            headers={"Stripe-Signature": "sig"},
        )
        assert resp.status_code == 500

    def test_no_webhook_secret_returns_500(
        self, client, monkeypatch,
    ):
        monkeypatch.delenv("STRIPE_WEBHOOK_SECRET", raising=False)
        resp = client.post(
            "/api/stripe/webhook",
            data="{}",
            headers={"Stripe-Signature": "sig"},
        )
        assert resp.status_code == 500
        assert "Webhook secret" in resp.get_json()["error"]

    def test_invalid_signature_returns_400(
        self, client, monkeypatch,
    ):
        monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_x")
        with patch(
            "backend.routes.stripe_routes.stripe",
        ) as mock_stripe:
            mock_stripe.error.SignatureVerificationError = (
                # Real type for the except clause
                type("SVE", (Exception,), {})
            )
            mock_stripe.Webhook.construct_event.side_effect = (
                mock_stripe.error.SignatureVerificationError("bad sig")
            )
            resp = client.post(
                "/api/stripe/webhook",
                data="{}",
                headers={"Stripe-Signature": "bad"},
            )
        assert resp.status_code == 400
        assert "Invalid signature" in resp.get_json()["error"]

    def test_invalid_payload_returns_400(self, client, monkeypatch):
        # Pin the Rule-#11 fix: production line 216 used to reference
        # an undeclared `logger`, producing a NameError that 500'd
        # out of @handle_route_errors. With the fix it logs via _logger
        # and returns the documented 400.
        monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_x")
        with patch(
            "backend.routes.stripe_routes.stripe",
        ) as mock_stripe:
            # SignatureVerificationError must exist for the except clause
            # to work; set it to an arbitrary class so non-matching
            # exceptions hit the generic except.
            mock_stripe.error.SignatureVerificationError = (
                type("SVE", (Exception,), {})
            )
            mock_stripe.Webhook.construct_event.side_effect = (
                ValueError("malformed JSON")
            )
            resp = client.post(
                "/api/stripe/webhook",
                data="not json",
                headers={"Stripe-Signature": "any"},
            )
        # Pre-fix, this would have been 500 (NameError). Post-fix → 400.
        assert resp.status_code == 400
        assert "Invalid webhook payload" in resp.get_json()["error"]

    def test_checkout_session_completed_syncs_metadata(
        self, client, monkeypatch,
    ):
        monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_x")
        sync_mock = MagicMock()
        with patch(
            "backend.routes.stripe_routes.stripe",
        ) as mock_stripe, patch(
            "backend.routes.stripe_routes._sync_subscription_metadata",
            sync_mock,
        ):
            mock_stripe.error.SignatureVerificationError = (
                type("SVE", (Exception,), {})
            )
            mock_stripe.Webhook.construct_event.return_value = {
                "type": "checkout.session.completed",
                "data": {"object": {
                    "customer": "cus_42",
                    "subscription": "sub_42",
                }},
            }
            resp = client.post(
                "/api/stripe/webhook",
                data="{}",
                headers={"Stripe-Signature": "ok"},
            )
        assert resp.status_code == 200
        assert resp.get_json()["received"] is True
        sync_mock.assert_called_once_with("cus_42", "sub_42")

    def test_subscription_updated_syncs_metadata(
        self, client, monkeypatch,
    ):
        monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_x")
        sync_mock = MagicMock()
        with patch(
            "backend.routes.stripe_routes.stripe",
        ) as mock_stripe, patch(
            "backend.routes.stripe_routes._sync_subscription_metadata",
            sync_mock,
        ):
            mock_stripe.error.SignatureVerificationError = (
                type("SVE", (Exception,), {})
            )
            mock_stripe.Webhook.construct_event.return_value = {
                "type": "customer.subscription.updated",
                "data": {"object": {
                    "customer": "cus_55",
                    "id": "sub_55",
                }},
            }
            resp = client.post(
                "/api/stripe/webhook",
                data="{}",
                headers={"Stripe-Signature": "ok"},
            )
        assert resp.status_code == 200
        sync_mock.assert_called_once_with("cus_55", "sub_55")

    def test_subscription_deleted_syncs_metadata(
        self, client, monkeypatch,
    ):
        monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_x")
        sync_mock = MagicMock()
        with patch(
            "backend.routes.stripe_routes.stripe",
        ) as mock_stripe, patch(
            "backend.routes.stripe_routes._sync_subscription_metadata",
            sync_mock,
        ):
            mock_stripe.error.SignatureVerificationError = (
                type("SVE", (Exception,), {})
            )
            mock_stripe.Webhook.construct_event.return_value = {
                "type": "customer.subscription.deleted",
                "data": {"object": {
                    "customer": "cus_66",
                    "id": "sub_66",
                }},
            }
            resp = client.post(
                "/api/stripe/webhook",
                data="{}",
                headers={"Stripe-Signature": "ok"},
            )
        assert resp.status_code == 200
        sync_mock.assert_called_once_with("cus_66", "sub_66")

    def test_unknown_event_type_passes_through(self, client, monkeypatch):
        monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_x")
        sync_mock = MagicMock()
        with patch(
            "backend.routes.stripe_routes.stripe",
        ) as mock_stripe, patch(
            "backend.routes.stripe_routes._sync_subscription_metadata",
            sync_mock,
        ):
            mock_stripe.error.SignatureVerificationError = (
                type("SVE", (Exception,), {})
            )
            mock_stripe.Webhook.construct_event.return_value = {
                "type": "some.other.event",
                "data": {"object": {}},
            }
            resp = client.post(
                "/api/stripe/webhook",
                data="{}",
                headers={"Stripe-Signature": "ok"},
            )
        assert resp.status_code == 200
        # Sync helper NOT called for unknown event types
        sync_mock.assert_not_called()


# ──────────────────────────────────────────────────────────────────
# Helpers: _get_user_metadata, _update_user_metadata,
# _get_or_create_customer, _sync_subscription_metadata
# ──────────────────────────────────────────────────────────────────


class TestGetUserMetadata:
    def test_local_dev_returns_empty_dict(self, monkeypatch):
        # _is_local_dev returns True when g.user_id == 'local-dev'
        from flask import Flask, g
        app = Flask(__name__)
        with app.test_request_context():
            g.user_id = "local-dev"
            from backend.routes.stripe_routes import _get_user_metadata
            assert _get_user_metadata("local-dev") == {}

    def test_clever_user_returns_empty_dict(self, monkeypatch):
        from flask import Flask, g
        app = Flask(__name__)
        with app.test_request_context():
            g.user_id = "clever:abc"
            from backend.routes.stripe_routes import _get_user_metadata
            assert _get_user_metadata("clever:abc") == {}

    def test_supabase_user_returns_metadata(self):
        from flask import Flask, g
        app = Flask(__name__)
        sb = MagicMock()
        sb.auth.admin.get_user_by_id.return_value = SimpleNamespace(
            user=SimpleNamespace(
                user_metadata={"stripe_customer_id": "cus_x"},
            ),
        )
        with app.test_request_context(), patch(
            "backend.routes.stripe_routes._get_supabase",
            return_value=sb,
        ):
            g.user_id = "real-user"
            from backend.routes.stripe_routes import _get_user_metadata
            assert _get_user_metadata("real-user") == {
                "stripe_customer_id": "cus_x",
            }


class TestUpdateUserMetadata:
    def test_local_dev_no_op(self):
        from flask import Flask, g
        app = Flask(__name__)
        sb_mock = MagicMock()
        with app.test_request_context(), patch(
            "backend.routes.stripe_routes._get_supabase",
            return_value=sb_mock,
        ):
            g.user_id = "local-dev"
            from backend.routes.stripe_routes import _update_user_metadata
            _update_user_metadata("local-dev", {"x": "y"})
        sb_mock.auth.admin.update_user_by_id.assert_not_called()

    def test_clever_no_op(self):
        from flask import Flask, g
        app = Flask(__name__)
        sb_mock = MagicMock()
        with app.test_request_context(), patch(
            "backend.routes.stripe_routes._get_supabase",
            return_value=sb_mock,
        ):
            g.user_id = "clever:abc"
            from backend.routes.stripe_routes import _update_user_metadata
            _update_user_metadata("clever:abc", {"x": "y"})
        sb_mock.auth.admin.update_user_by_id.assert_not_called()

    def test_real_user_updates_metadata(self):
        from flask import Flask, g
        app = Flask(__name__)
        sb = MagicMock()
        with app.test_request_context(), patch(
            "backend.routes.stripe_routes._get_supabase",
            return_value=sb,
        ):
            g.user_id = "real-user"
            from backend.routes.stripe_routes import _update_user_metadata
            _update_user_metadata("real-user", {"foo": "bar"})
        sb.auth.admin.update_user_by_id.assert_called_once_with(
            "real-user", {"user_metadata": {"foo": "bar"}},
        )


class TestGetOrCreateCustomer:
    def test_existing_customer_returned(self):
        from flask import Flask, g
        app = Flask(__name__)
        with app.test_request_context(), patch(
            "backend.routes.stripe_routes._get_user_metadata",
            return_value={"stripe_customer_id": "cus_existing"},
        ):
            g.user_id = "user-1"
            from backend.routes.stripe_routes import _get_or_create_customer
            assert _get_or_create_customer("user-1", "u@x.com") == "cus_existing"

    def test_local_dev_finds_existing_by_email(self):
        from flask import Flask, g
        app = Flask(__name__)
        existing_customer = MagicMock(); existing_customer.id = "cus_local"
        with app.test_request_context(), patch(
            "backend.routes.stripe_routes._get_user_metadata",
            return_value={},
        ), patch(
            "backend.routes.stripe_routes.stripe",
        ) as mock_stripe:
            mock_stripe.Customer.list.return_value = SimpleNamespace(
                data=[existing_customer],
            )
            g.user_id = "local-dev"
            from backend.routes.stripe_routes import _get_or_create_customer
            assert _get_or_create_customer("local-dev", "u@x.com") == "cus_local"

    def test_local_dev_creates_when_email_not_found(self):
        from flask import Flask, g
        app = Flask(__name__)
        new_customer = MagicMock(); new_customer.id = "cus_new"
        with app.test_request_context(), patch(
            "backend.routes.stripe_routes._get_user_metadata",
            return_value={},
        ), patch(
            "backend.routes.stripe_routes._update_user_metadata",
        ), patch(
            "backend.routes.stripe_routes.stripe",
        ) as mock_stripe:
            mock_stripe.Customer.list.return_value = SimpleNamespace(data=[])
            mock_stripe.Customer.create.return_value = new_customer
            g.user_id = "local-dev"
            from backend.routes.stripe_routes import _get_or_create_customer
            assert _get_or_create_customer("local-dev", "u@x.com") == "cus_new"

    def test_real_user_creates_and_persists(self):
        from flask import Flask, g
        app = Flask(__name__)
        new_customer = MagicMock(); new_customer.id = "cus_realnew"
        update_mock = MagicMock()
        with app.test_request_context(), patch(
            "backend.routes.stripe_routes._get_user_metadata",
            return_value={},
        ), patch(
            "backend.routes.stripe_routes._update_user_metadata",
            update_mock,
        ), patch(
            "backend.routes.stripe_routes.stripe",
        ) as mock_stripe:
            mock_stripe.Customer.create.return_value = new_customer
            g.user_id = "real-user"
            from backend.routes.stripe_routes import _get_or_create_customer
            assert _get_or_create_customer("real-user", "u@x.com") == "cus_realnew"
        update_mock.assert_called_once_with(
            "real-user", {"stripe_customer_id": "cus_realnew"},
        )


class TestSyncSubscriptionMetadata:
    def test_finds_user_by_customer_id_and_updates(self):
        # Mock Subscription.retrieve, sb.auth.admin.list_users, and
        # _update_user_metadata. Verify the update payload carries all
        # 4 subscription fields.
        sub_data = {
            "status": "active",
            "current_period_end": 1735689600,
            "cancel_at_period_end": False,
            "items": {
                "data": [
                    {"price": {"recurring": {"interval": "year"}}},
                ],
            },
        }

        class FakeSub(dict):
            pass

        target = SimpleNamespace(
            id="user-target",
            user_metadata={"stripe_customer_id": "cus_match"},
        )
        other = SimpleNamespace(
            id="user-other",
            user_metadata={"stripe_customer_id": "cus_other"},
        )

        sb = MagicMock()
        sb.auth.admin.list_users.return_value = [other, target]

        update_mock = MagicMock()
        with patch(
            "backend.routes.stripe_routes.stripe",
        ) as mock_stripe, patch(
            "backend.routes.stripe_routes._get_supabase",
            return_value=sb,
        ), patch(
            "backend.routes.stripe_routes._update_user_metadata",
            update_mock,
        ):
            mock_stripe.Subscription.retrieve.return_value = FakeSub(sub_data)
            from backend.routes.stripe_routes import (
                _sync_subscription_metadata,
            )
            _sync_subscription_metadata("cus_match", "sub_42")

        update_mock.assert_called_once()
        args = update_mock.call_args.args
        assert args[0] == "user-target"
        payload = args[1]
        assert payload["subscription_status"] == "active"
        assert payload["subscription_plan"] == "year"
        assert payload["subscription_period_end"] == 1735689600
        assert payload["subscription_cancel_at_period_end"] is False

    def test_no_matching_user_silently_succeeds(self):
        sub_data = {
            "status": "active",
            "current_period_end": 1,
            "cancel_at_period_end": False,
            "items": {"data": [{"price": {"recurring": {"interval": "m"}}}]},
        }

        class FakeSub(dict):
            pass

        sb = MagicMock()
        sb.auth.admin.list_users.return_value = [
            SimpleNamespace(
                id="other", user_metadata={"stripe_customer_id": "cus_x"},
            ),
        ]
        update_mock = MagicMock()
        with patch(
            "backend.routes.stripe_routes.stripe",
        ) as mock_stripe, patch(
            "backend.routes.stripe_routes._get_supabase",
            return_value=sb,
        ), patch(
            "backend.routes.stripe_routes._update_user_metadata",
            update_mock,
        ):
            mock_stripe.Subscription.retrieve.return_value = FakeSub(sub_data)
            from backend.routes.stripe_routes import (
                _sync_subscription_metadata,
            )
            _sync_subscription_metadata("cus_no_match", "sub_99")
        update_mock.assert_not_called()

    def test_exception_swallowed_and_sentry_called(self):
        # When Subscription.retrieve raises, the helper swallows + reports.
        with patch(
            "backend.routes.stripe_routes.stripe",
        ) as mock_stripe, patch(
            "backend.routes.stripe_routes.sentry_sdk.capture_exception",
        ) as sentry_mock:
            mock_stripe.Subscription.retrieve.side_effect = (
                RuntimeError("api dead")
            )
            from backend.routes.stripe_routes import (
                _sync_subscription_metadata,
            )
            # Must not raise
            _sync_subscription_metadata("cus_x", "sub_x")
        assert sentry_mock.called


# ──────────────────────────────────────────────────────────────────
# Rule #11 regression: line 216 must reference _logger (not `logger`)
# ──────────────────────────────────────────────────────────────────


class TestRuleEleven:
    def test_webhook_invalid_payload_uses_logger_not_namerror(self):
        """Pin: PR #293 fixed an undeclared `logger` reference at
        L216 that would NameError on non-signature webhook errors,
        bubbling through @handle_route_errors as 500. Test asserts
        the source uses _logger, so a future revert surfaces in CI."""
        import inspect
        from backend.routes import stripe_routes
        src = inspect.getsource(stripe_routes.stripe_webhook)
        # The bug was a bare `logger.error(...)` call. Verify there
        # are no more bare-logger references in this function.
        # (Look for `logger.` not preceded by underscore.)
        import re
        bare_logger = re.search(r"(?<![_\w])logger\.", src)
        assert bare_logger is None, (
            f"Bare `logger.` reference reintroduced at: "
            f"{src[max(0, bare_logger.start()-30):bare_logger.start()+30]}"
        )
