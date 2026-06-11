"""Unit tests for backend/testing/fake_supabase.py and its env gate.

Hardening sprint PR5 (e2e de-skip wave 1): the `Frontend E2E Extended` CI
job spawns the real Flask backend with GRAIDER_FAKE_SUPABASE=1 so the
join-code publish/take/results flow runs hermetically (no live Supabase).
These tests pin:

  1. The gate: GRAIDER_FAKE_SUPABASE=1 only takes effect when FLASK_ENV is
     a dev/test value — anything else raises loudly (fail-closed; the fake
     must be impossible to enable in production by accident).
  2. The fake's postgrest-builder subset behaves like the real client for
     every chain the join-code path uses (see backend/routes/
     student_portal_routes.py and backend/services/submission_repository.py):
     select/eq/eq, ilike, in_, order(desc)/limit, insert, upsert(on_conflict),
     update().eq(), delete().eq(), single(), count='exact'.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from backend.testing.fake_supabase import FakeSupabaseClient, get_fake_supabase, reset_fake_supabase


# ──────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────


@pytest.fixture
def client():
    """A fresh, isolated fake client (not the process singleton)."""
    return FakeSupabaseClient()


@pytest.fixture
def reset_singletons():
    """Reset backend.supabase_client module singletons around a test."""
    from backend import supabase_client as mod

    saved_raw = mod._supabase_raw
    saved_resilient = mod._supabase_resilient
    mod._supabase_raw = None
    mod._supabase_resilient = None
    yield mod
    mod._supabase_raw = saved_raw
    mod._supabase_resilient = saved_resilient


# ──────────────────────────────────────────────────────────────────
# Env gate (backend/supabase_client.py)
# ──────────────────────────────────────────────────────────────────


class TestFakeGate:
    def test_gate_off_by_default(self, reset_singletons):
        """Without the flag, behavior is unchanged (None when unconfigured)."""
        from backend.supabase_client import get_raw_supabase

        env = {"GRAIDER_FAKE_SUPABASE": "", "SUPABASE_URL": "", "SUPABASE_SERVICE_KEY": ""}
        with patch.dict("os.environ", env):
            assert get_raw_supabase() is None

    def test_gate_returns_fake_in_development(self, reset_singletons):
        from backend.supabase_client import get_raw_supabase

        env = {"GRAIDER_FAKE_SUPABASE": "1", "FLASK_ENV": "development"}
        with patch.dict("os.environ", env):
            client = get_raw_supabase()
        assert isinstance(client, FakeSupabaseClient)

    def test_gate_raises_outside_dev(self, reset_singletons):
        """Fail-closed: the fake must never silently activate in prod."""
        from backend.supabase_client import get_raw_supabase

        env = {"GRAIDER_FAKE_SUPABASE": "1", "FLASK_ENV": "production"}
        with patch.dict("os.environ", env):
            with pytest.raises(RuntimeError, match="GRAIDER_FAKE_SUPABASE"):
                get_raw_supabase()

    def test_gate_raises_when_flask_env_unset(self, reset_singletons):
        from backend.supabase_client import get_raw_supabase

        env = {"GRAIDER_FAKE_SUPABASE": "1", "FLASK_ENV": ""}
        with patch.dict("os.environ", env):
            with pytest.raises(RuntimeError, match="GRAIDER_FAKE_SUPABASE"):
                get_raw_supabase()

    def test_gate_wins_over_real_credentials(self, reset_singletons):
        """A dev .env with real SUPABASE_URL must not defeat the fake flag
        (local `npx playwright test` runs load .env via load_dotenv)."""
        from backend.supabase_client import get_raw_supabase

        env = {
            "GRAIDER_FAKE_SUPABASE": "1",
            "FLASK_ENV": "development",
            "SUPABASE_URL": "https://real.supabase.co",
            "SUPABASE_SERVICE_KEY": "real-key",
        }
        with patch.dict("os.environ", env):
            client = get_raw_supabase()
        assert isinstance(client, FakeSupabaseClient)

    def test_resilient_wrapper_chains_through_fake(self, reset_singletons):
        """get_supabase() wraps the fake in ResilientClient; full chains work."""
        from backend.supabase_client import get_supabase

        env = {"GRAIDER_FAKE_SUPABASE": "1", "FLASK_ENV": "development"}
        with patch.dict("os.environ", env):
            db = get_supabase()
            db.table("published_assessments").upsert(
                {"id": "a1", "join_code": "ABC123", "teacher_id": "t1"},
                on_conflict="id",
            ).execute()
            result = (
                db.table("published_assessments")
                .select("*")
                .eq("join_code", "ABC123")
                .execute()
            )
        assert len(result.data) == 1
        assert result.data[0]["teacher_id"] == "t1"


# ──────────────────────────────────────────────────────────────────
# Builder behavior
# ──────────────────────────────────────────────────────────────────


class TestInsertSelect:
    def test_insert_and_select_eq(self, client):
        client.table("t").insert({"id": "1", "join_code": "AAA111", "x": 1}).execute()
        client.table("t").insert({"id": "2", "join_code": "BBB222", "x": 2}).execute()
        result = client.table("t").select("*").eq("join_code", "AAA111").execute()
        assert [r["id"] for r in result.data] == ["1"]

    def test_insert_fills_id_and_created_at(self, client):
        result = client.table("t").insert({"x": 1}).execute()
        row = result.data[0]
        assert row["id"]
        assert row["created_at"]

    def test_insert_list_of_rows(self, client):
        result = client.table("t").insert([{"x": 1}, {"x": 2}]).execute()
        assert len(result.data) == 2

    def test_chained_eq_filters_are_anded(self, client):
        client.table("t").insert({"join_code": "C1", "teacher_id": "t1"}).execute()
        client.table("t").insert({"join_code": "C1", "teacher_id": "t2"}).execute()
        result = (
            client.table("t").select("*").eq("join_code", "C1").eq("teacher_id", "t2").execute()
        )
        assert len(result.data) == 1
        assert result.data[0]["teacher_id"] == "t2"

    def test_returned_rows_are_copies(self, client):
        client.table("t").insert({"id": "1", "x": 1}).execute()
        result = client.table("t").select("*").eq("id", "1").execute()
        result.data[0]["x"] = 999
        again = client.table("t").select("*").eq("id", "1").execute()
        assert again.data[0]["x"] == 1

    def test_select_count_exact(self, client):
        client.table("t").insert({"k": "a"}).execute()
        client.table("t").insert({"k": "a"}).execute()
        result = client.table("t").select("id", count="exact").eq("k", "a").execute()
        assert result.count == 2


class TestUpsert:
    def test_upsert_inserts_when_no_conflict(self, client):
        client.table("t").upsert({"id": "1", "x": 1}, on_conflict="id").execute()
        assert len(client.table("t").select("*").execute().data) == 1

    def test_upsert_merges_on_conflict(self, client):
        client.table("t").upsert({"id": "1", "x": 1, "keep": "old"}, on_conflict="id").execute()
        client.table("t").upsert({"id": "1", "x": 2}, on_conflict="id").execute()
        rows = client.table("t").select("*").execute().data
        assert len(rows) == 1
        assert rows[0]["x"] == 2
        assert rows[0]["keep"] == "old"  # unprovided cols retain prior values


class TestUpdateDelete:
    def test_update_with_filters(self, client):
        client.table("t").insert({"join_code": "C1", "is_active": True}).execute()
        client.table("t").insert({"join_code": "C2", "is_active": True}).execute()
        client.table("t").update({"is_active": False}).eq("join_code", "C1").execute()
        rows = client.table("t").select("*").eq("join_code", "C1").execute().data
        assert rows[0]["is_active"] is False
        others = client.table("t").select("*").eq("join_code", "C2").execute().data
        assert others[0]["is_active"] is True

    def test_delete_with_filters(self, client):
        client.table("t").insert({"join_code": "C1"}).execute()
        client.table("t").insert({"join_code": "C2"}).execute()
        client.table("t").delete().eq("join_code", "C1").execute()
        remaining = client.table("t").select("*").execute().data
        assert [r["join_code"] for r in remaining] == ["C2"]


class TestFilters:
    def test_ilike_case_insensitive(self, client):
        client.table("s").insert({"student_name": "Alice Smith"}).execute()
        result = (
            client.table("s").select("*").ilike("student_name", "alice smith").execute()
        )
        assert len(result.data) == 1

    def test_ilike_escaped_pattern_chars(self, client):
        """_escape_ilike escapes % _ \\ — the fake must treat them literally."""
        client.table("s").insert({"student_name": "100% Bob_Jones"}).execute()
        result = (
            client.table("s").select("*").ilike("student_name", r"100\% bob\_jones").execute()
        )
        assert len(result.data) == 1

    def test_ilike_percent_wildcard(self, client):
        client.table("s").insert({"student_name": "Alice Smith"}).execute()
        result = client.table("s").select("*").ilike("student_name", "alice%").execute()
        assert len(result.data) == 1

    def test_ilike_no_match(self, client):
        client.table("s").insert({"student_name": "Alice"}).execute()
        result = client.table("s").select("*").ilike("student_name", "bob").execute()
        assert result.data == []

    def test_in_filter(self, client):
        client.table("t").insert({"k": "a"}).execute()
        client.table("t").insert({"k": "b"}).execute()
        client.table("t").insert({"k": "c"}).execute()
        result = client.table("t").select("*").in_("k", ["a", "c"]).execute()
        assert sorted(r["k"] for r in result.data) == ["a", "c"]

    def test_neq_filter(self, client):
        client.table("t").insert({"k": "a"}).execute()
        client.table("t").insert({"k": "b"}).execute()
        result = client.table("t").select("*").neq("k", "a").execute()
        assert [r["k"] for r in result.data] == ["b"]

    def test_gte_filter(self, client):
        client.table("t").insert({"n": 1}).execute()
        client.table("t").insert({"n": 5}).execute()
        result = client.table("t").select("*").gte("n", 3).execute()
        assert [r["n"] for r in result.data] == [5]


class TestModifiers:
    def test_order_desc_and_limit(self, client):
        client.table("t").insert({"created_at": "2026-01-01", "k": "old"}).execute()
        client.table("t").insert({"created_at": "2026-06-01", "k": "new"}).execute()
        result = (
            client.table("t").select("*").order("created_at", desc=True).limit(1).execute()
        )
        assert [r["k"] for r in result.data] == ["new"]

    def test_order_handles_none_values(self, client):
        client.table("t").insert({"submitted_at": None, "k": "a"}).execute()
        client.table("t").insert({"submitted_at": "2026-06-01", "k": "b"}).execute()
        result = client.table("t").select("*").order("submitted_at", desc=True).execute()
        assert len(result.data) == 2  # must not raise on None comparison

    def test_single_returns_dict(self, client):
        client.table("t").insert({"id": "1", "x": 9}).execute()
        result = client.table("t").select("*").eq("id", "1").single().execute()
        assert result.data["x"] == 9

    def test_single_raises_on_zero_rows(self, client):
        with pytest.raises(Exception):
            client.table("t").select("*").eq("id", "missing").single().execute()

    def test_maybe_single_returns_none_on_zero_rows(self, client):
        result = client.table("t").select("*").eq("id", "missing").maybe_single().execute()
        assert result.data is None


class TestSingleton:
    def test_get_fake_supabase_is_singleton(self):
        reset_fake_supabase()
        a = get_fake_supabase()
        b = get_fake_supabase()
        assert a is b
        reset_fake_supabase()
        c = get_fake_supabase()
        assert c is not a
