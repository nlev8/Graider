"""VB11: the Stripe backfill must NOT promote a forged user_metadata binding.

The backfill moves `stripe_customer_id` from the (client-settable) user_metadata
into the (service-role-only) app_metadata for existing customers. The trap Codex
flagged: blindly copying user_metadata.stripe_customer_id would let an attacker
who pre-seeded `user_metadata.stripe_customer_id = cus_VICTIM` get that malicious
binding promoted into trusted app_metadata — reopening the VB11 hijack.

The fix validates each candidate against Stripe's authoritative binding
(`customer.metadata.supabase_user_id == user.id`, stamped by the server at
customer creation) before promoting it. These tests pin that property.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


def _run_backfill(monkeypatch, users, customers, apply=True):
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "svc-key")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_123")
    import stripe

    def _retrieve(cid):
        if cid not in customers:
            raise Exception(f"No such customer: {cid}")
        return customers[cid]

    sb = MagicMock()
    argv = ["backfill"] + (["--apply"] if apply else [])
    with patch("backend.supabase_client.get_supabase_or_raise", return_value=sb), \
         patch("backend.utils.supabase_users.list_all_users", return_value=users), \
         patch.object(stripe.Customer, "retrieve", side_effect=_retrieve), \
         patch("sys.argv", argv):
        from backend.scripts.backfill_stripe_to_app_metadata import main
        rc = main()
    return sb, rc


def test_backfill_rejects_forged_user_metadata_binding(monkeypatch):
    # Attacker pre-seeded user_metadata.stripe_customer_id = victim's customer.
    attacker = SimpleNamespace(
        id="attacker-uid", email="attacker@x.com",
        user_metadata={"stripe_customer_id": "cus_VICTIM"}, app_metadata={},
    )
    # Stripe says cus_VICTIM is bound to the victim, NOT the attacker.
    victim_customer = SimpleNamespace(metadata={"supabase_user_id": "victim-uid"})

    sb, rc = _run_backfill(monkeypatch, [attacker], {"cus_VICTIM": victim_customer})

    sb.auth.admin.update_user_by_id.assert_not_called()  # forged binding NOT promoted
    assert rc == 0


def test_backfill_promotes_stripe_validated_binding(monkeypatch):
    owner = SimpleNamespace(
        id="owner-uid", email="owner@x.com",
        user_metadata={"stripe_customer_id": "cus_OWN"}, app_metadata={},
    )
    own_customer = SimpleNamespace(metadata={"supabase_user_id": "owner-uid"})

    sb, rc = _run_backfill(monkeypatch, [owner], {"cus_OWN": own_customer})

    sb.auth.admin.update_user_by_id.assert_called_once_with(
        "owner-uid", {"app_metadata": {"stripe_customer_id": "cus_OWN"}},
    )
    assert rc == 0


def test_backfill_skips_when_already_in_app_metadata(monkeypatch):
    already = SimpleNamespace(
        id="u", email="u@x.com",
        user_metadata={"stripe_customer_id": "cus_X"},
        app_metadata={"stripe_customer_id": "cus_X"},
    )
    sb, rc = _run_backfill(monkeypatch, [already], {})
    sb.auth.admin.update_user_by_id.assert_not_called()  # idempotent
    assert rc == 0
