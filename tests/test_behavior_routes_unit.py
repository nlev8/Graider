"""Unit tests for backend/routes/behavior_routes.py.

Audit MAJOR #4 sprint follow-up to PR #286. Targets the 195 uncovered
LOC (17% baseline). Covers all 6 endpoints + 2 helpers:

  * POST   /api/behavior/session
  * GET    /api/behavior/data
  * GET    /api/behavior/events
  * DELETE /api/behavior/data
  * GET    /api/behavior/debug
  * GET    /api/behavior/roster

Strategy
--------
Flask test_client + chain-mocked Supabase client returning canned `data`
arrays. `_get_supabase` is patched per test (or per class) to return a
custom chain. PERIODS_DIR is monkeypatched to a `tmp_path` for the
roster CSV walker.

`@require_teacher` bypassed via FLASK_ENV=development + the
`X-Test-Teacher-Id` header convention.
`limiter.reset()` in fixture (Flask-Limiter is module-level).
"""
from __future__ import annotations

import json
from unittest.mock import patch, MagicMock

import pytest


@pytest.fixture
def client():
    from backend.app import app
    from backend.extensions import limiter
    try:
        limiter.reset()
    except Exception:  # noqa: BLE001  # broad catch: best-effort, failure tolerated
        pass
    with app.test_client() as c:
        yield c


@pytest.fixture
def auth_headers():
    return {"X-Test-Teacher-Id": "teach-1", "Content-Type": "application/json"}


@pytest.fixture(autouse=True)
def dev_env(monkeypatch):
    monkeypatch.setenv("FLASK_ENV", "development")


# ──────────────────────────────────────────────────────────────────
# Chain-mock helper
# ──────────────────────────────────────────────────────────────────


class FakeChain:
    """Stand-in for Supabase's fluent query builder.

    All chainable methods (table/select/eq/gte/lte/ilike/order/limit/
    insert/delete) return self. `execute()` returns a MagicMock whose
    `.data` attribute is the canned payload supplied by the test.

    The chain also records every call site so tests can assert which
    filters were applied without owning the underlying httpx layer.
    """

    def __init__(self, execute_data=None, execute_side_effect=None):
        self._execute_data = execute_data
        self._execute_side_effect = execute_side_effect
        self.calls: list[tuple[str, tuple, dict]] = []

    def _record(self, method, *args, **kwargs):
        self.calls.append((method, args, kwargs))
        return self

    def table(self, *args, **kwargs):
        return self._record("table", *args, **kwargs)

    def select(self, *args, **kwargs):
        return self._record("select", *args, **kwargs)

    def insert(self, *args, **kwargs):
        return self._record("insert", *args, **kwargs)

    def delete(self, *args, **kwargs):
        return self._record("delete", *args, **kwargs)

    def eq(self, *args, **kwargs):
        return self._record("eq", *args, **kwargs)

    def gte(self, *args, **kwargs):
        return self._record("gte", *args, **kwargs)

    def lte(self, *args, **kwargs):
        return self._record("lte", *args, **kwargs)

    def ilike(self, *args, **kwargs):
        return self._record("ilike", *args, **kwargs)

    def order(self, *args, **kwargs):
        return self._record("order", *args, **kwargs)

    def limit(self, *args, **kwargs):
        return self._record("limit", *args, **kwargs)

    def execute(self):
        self.calls.append(("execute", (), {}))
        if self._execute_side_effect is not None:
            raise self._execute_side_effect
        m = MagicMock()
        m.data = self._execute_data
        return m


def make_supabase(execute_data=None, execute_side_effect=None):
    chain = FakeChain(execute_data=execute_data,
                      execute_side_effect=execute_side_effect)
    sb = MagicMock()
    sb.table.side_effect = chain.table
    return sb, chain


def patch_supabase(execute_data=None, execute_side_effect=None):
    """Convenience: patch _get_supabase with a FakeChain. Returns the
    chain so the test can assert calls. Use as a context manager."""
    sb, chain = make_supabase(execute_data, execute_side_effect)
    p = patch(
        "backend.routes.behavior_routes._get_supabase",
        return_value=sb,
    )
    return p, chain


# ──────────────────────────────────────────────────────────────────
# Auth-failure path (g.user_id missing) — exercise via passing the
# decorator but having _get_teacher_id return None.
# ──────────────────────────────────────────────────────────────────


class TestUnauthenticated:
    """All endpoints return 401 when _get_teacher_id() yields None."""

    @pytest.fixture(autouse=True)
    def _no_teacher(self):
        with patch(
            "backend.routes.behavior_routes._get_teacher_id",
            return_value=None,
        ):
            yield

    def test_post_session_401(self, client, auth_headers):
        resp = client.post(
            "/api/behavior/session",
            data=json.dumps({"events": []}),
            headers=auth_headers,
        )
        assert resp.status_code == 401
        assert resp.get_json()["error"] == "Not authenticated"

    def test_get_data_401(self, client, auth_headers):
        resp = client.get("/api/behavior/data", headers=auth_headers)
        assert resp.status_code == 401

    def test_get_events_401(self, client, auth_headers):
        resp = client.get("/api/behavior/events", headers=auth_headers)
        assert resp.status_code == 401

    def test_delete_data_401(self, client, auth_headers):
        resp = client.delete(
            "/api/behavior/data?all=true",
            headers=auth_headers,
        )
        assert resp.status_code == 401

    def test_debug_401(self, client, auth_headers):
        resp = client.get("/api/behavior/debug", headers=auth_headers)
        # 200 status + warning payload — debug endpoint never 401s on
        # missing g.user_id; it returns a diagnostic body. The early
        # `if not teacher_id` branch in debug returns a 200 with
        # "Not authenticated" string in the error field. Confirm shape.
        body = resp.get_json()
        assert body.get("error") == "Not authenticated"
        assert body.get("g_user_id") == "missing"


# ──────────────────────────────────────────────────────────────────
# POST /api/behavior/session
# ──────────────────────────────────────────────────────────────────


class TestSaveSession:
    def test_no_events_returns_error(self, client, auth_headers):
        resp = client.post(
            "/api/behavior/session",
            data=json.dumps({"events": [], "period": "P1"}),
            headers=auth_headers,
        )
        body = resp.get_json()
        assert body["error"] == "No events to save"

    def test_session_insert_failure_returns_error(self, client, auth_headers):
        # session_res.data is empty → session_id falsy → error path
        p, _chain = patch_supabase(execute_data=[])
        with p:
            resp = client.post(
                "/api/behavior/session",
                data=json.dumps({
                    "events": [{"student_name": "A", "type": "praise"}],
                    "period": "P2",
                    "date": "2026-05-09",
                }),
                headers=auth_headers,
            )
        assert resp.get_json()["error"] == "Failed to create session"

    def test_happy_path_saves_events(self, client, auth_headers):
        # Use a counter-based execute() that returns the session-id payload
        # for the FIRST call and an empty list for the second (the events
        # insert). Pins both the response shape AND the actual payloads
        # passed to .insert() so a regression that mismaps event fields
        # would surface here.
        sb = MagicMock()
        chain = FakeChain()
        sb.table.side_effect = chain.table
        call_count = {"n": 0}

        def per_call_execute(self):
            i = call_count["n"]
            call_count["n"] += 1
            self.calls.append(("execute", (), {}))
            m = MagicMock()
            m.data = [{"id": "sess-1"}] if i == 0 else []
            return m

        with patch.object(FakeChain, "execute", per_call_execute), patch(
            "backend.routes.behavior_routes._get_supabase",
            return_value=sb,
        ):
            resp = client.post(
                "/api/behavior/session",
                data=json.dumps({
                    "events": [
                        {
                            "student_name": "Jane Doe",
                            "type": "correction",
                            "note": "Talking",
                            "timestamp": "09:15",
                        },
                        {
                            "student_name": "John Smith",
                            "type": "praise",
                            "timestamp": "09:20",
                        },
                        # Empty student_name → skipped from event_rows
                        {"student_name": "", "type": "correction"},
                    ],
                    "period": "Period 3",
                    "date": "2026-05-09",
                }),
                headers=auth_headers,
            )

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["status"] == "success"
        assert body["message"] == "Saved 2 events"

        # Verify both insert payloads (Gemini round-1 critical fix).
        insert_calls = [c for c in chain.calls if c[0] == "insert"]
        assert len(insert_calls) == 2

        # 1) Session insert: dict with teacher_id + period + date + device
        session_payload = insert_calls[0][1][0]
        assert session_payload["teacher_id"] == "teach-1"
        assert session_payload["period"] == "Period 3"
        assert session_payload["date"] == "2026-05-09"
        assert session_payload["device"] == "web"
        assert session_payload["is_active"] is False

        # 2) Events insert: list of 2 dicts (blank-name skipped); each
        # carries the session_id + event_time built as date + "T" + ts + ":00"
        events_payload = insert_calls[1][1][0]
        assert len(events_payload) == 2
        jane = events_payload[0]
        assert jane["student_name"] == "Jane Doe"
        assert jane["type"] == "correction"
        assert jane["note"] == "Talking"
        assert jane["session_id"] == "sess-1"
        assert jane["teacher_id"] == "teach-1"
        assert jane["source"] == "manual"
        assert jane["event_time"] == "2026-05-09T09:15:00"
        john = events_payload[1]
        assert john["student_name"] == "John Smith"
        assert john["type"] == "praise"
        # Empty note coerced to None (production line 112)
        assert john["note"] is None

    def test_happy_path_omits_event_insert_when_only_blank_names(
        self, client, auth_headers,
    ):
        # event_rows ends up empty after filtering → second insert skipped
        sb = MagicMock()
        chain = FakeChain(execute_data=[{"id": "sess-2"}])
        sb.table.side_effect = chain.table

        with patch(
            "backend.routes.behavior_routes._get_supabase",
            return_value=sb,
        ):
            resp = client.post(
                "/api/behavior/session",
                data=json.dumps({
                    "events": [{"student_name": "", "type": "correction"}],
                    "period": "P4",
                }),
                headers=auth_headers,
            )

        assert resp.status_code == 200
        assert resp.get_json()["message"] == "Saved 0 events"

    def test_default_date_used_when_omitted(self, client, auth_headers):
        # When `date` is omitted, code uses datetime.now().strftime('%Y-%m-%d')
        sb = MagicMock()
        chain = FakeChain(execute_data=[{"id": "sess-3"}])
        sb.table.side_effect = chain.table

        with patch(
            "backend.routes.behavior_routes._get_supabase",
            return_value=sb,
        ):
            resp = client.post(
                "/api/behavior/session",
                data=json.dumps({
                    "events": [{"student_name": "X", "type": "praise"}],
                }),
                headers=auth_headers,
            )

        assert resp.status_code == 200


# ──────────────────────────────────────────────────────────────────
# GET /api/behavior/data
# ──────────────────────────────────────────────────────────────────


class TestGetData:
    def test_aggregates_by_student_date_period_type(
        self, client, auth_headers,
    ):
        rows = [
            # Jane Doe — 2 corrections same period+date
            {
                "student_name": "Jane Doe", "type": "correction",
                "note": "Talking", "transcript": "",
                "event_time": "2026-05-09T09:15:00Z", "source": "manual",
                "behavior_sessions": {"period": "P3", "date": "2026-05-09"},
            },
            {
                "student_name": "Jane Doe", "type": "correction",
                "note": "Talking",  # Duplicate note — not appended twice
                "transcript": "Said hi",
                "event_time": "2026-05-09T09:20:00Z", "source": "manual",
                "behavior_sessions": {"period": "P3", "date": "2026-05-09"},
            },
            # Jane Doe — 1 praise same period+date (different type entry)
            {
                "student_name": "Jane Doe", "type": "praise",
                "note": "", "transcript": "",
                "event_time": "2026-05-09T09:30:00Z", "source": "manual",
                "behavior_sessions": {"period": "P3", "date": "2026-05-09"},
            },
            # John Smith — 1 correction
            {
                "student_name": "John Smith", "type": "correction",
                "note": "Late", "transcript": "",
                "event_time": "bad-time-format",  # Triggers parse-fail branch
                "source": "manual",
                "behavior_sessions": {"period": "P3", "date": "2026-05-09"},
            },
        ]
        p, _ = patch_supabase(execute_data=rows)
        with p:
            resp = client.get("/api/behavior/data", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["status"] == "success"
        students = body["data"]
        assert "jane_doe" in students
        jane = students["jane_doe"]
        assert jane["name"] == "Jane Doe"
        assert jane["total_corrections"] == 2
        assert jane["total_praise"] == 1
        # Two distinct entries: one for type=correction, one for praise
        assert len(jane["entries"]) == 2
        correction_entry = next(e for e in jane["entries"]
                                if e["type"] == "correction")
        # Note "Talking" appears only once (deduped)
        assert correction_entry["notes"] == ["Talking"]
        assert "Said hi" in correction_entry["transcripts"]
        # Two parsed timestamps + skipped one = 2 entries in timestamps
        assert correction_entry["timestamps"] == ["09:15", "09:20"]
        # John Smith — bad event_time → no timestamp entries
        john = students["john_smith"]
        assert john["entries"][0]["timestamps"] == []

    def test_filters_passed_through_to_query(self, client, auth_headers):
        # Pin EXACT filter args, not just method names. A refactor that
        # filtered by the wrong column (e.g. event_time instead of
        # behavior_sessions.date) would surface here.
        p, chain = patch_supabase(execute_data=[])
        with p:
            resp = client.get(
                "/api/behavior/data?date_from=2026-01-01&date_to=2026-12-31"
                "&period=P1&student_name=jane",
                headers=auth_headers,
            )
        assert resp.status_code == 200
        assert ("gte", ("behavior_sessions.date", "2026-01-01"), {}) in chain.calls
        assert ("lte", ("behavior_sessions.date", "2026-12-31"), {}) in chain.calls
        assert ("eq", ("behavior_sessions.period", "P1"), {}) in chain.calls
        assert ("eq", ("teacher_id", "teach-1"), {}) in chain.calls

    def test_student_name_filter_substring_match(
        self, client, auth_headers,
    ):
        rows = [
            {"student_name": "Jane Doe", "type": "praise", "note": "",
             "transcript": "", "event_time": "", "source": "manual",
             "behavior_sessions": {"period": "P1", "date": "d"}},
            {"student_name": "John Smith", "type": "praise", "note": "",
             "transcript": "", "event_time": "", "source": "manual",
             "behavior_sessions": {"period": "P1", "date": "d"}},
        ]
        p, _ = patch_supabase(execute_data=rows)
        with p:
            resp = client.get(
                "/api/behavior/data?student_name=jane",
                headers=auth_headers,
            )
        body = resp.get_json()
        # Only Jane survives the substring filter
        assert "jane_doe" in body["data"]
        assert "john_smith" not in body["data"]

    def test_supabase_query_exception_returns_empty(
        self, client, auth_headers,
    ):
        # When the query raises, the route logs + returns empty dict
        p, _ = patch_supabase(execute_side_effect=RuntimeError("boom"))
        with p:
            resp = client.get("/api/behavior/data", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["status"] == "success"
        assert body["data"] == {}


# ──────────────────────────────────────────────────────────────────
# GET /api/behavior/events
# ──────────────────────────────────────────────────────────────────


class TestGetEvents:
    def test_happy_path_returns_flat_event_list(
        self, client, auth_headers,
    ):
        rows = [
            {
                "id": "e1", "student_name": "Jane Doe",
                "type": "correction", "note": None, "transcript": None,
                "source": None, "event_time": "2026-05-09T09:15:00",
                "behavior_sessions": {"period": "P3", "date": "2026-05-09"},
            },
            {
                "id": "e2", "student_name": "John Smith",
                "type": "praise", "note": "Good answer",
                "transcript": "Yes", "source": "voice",
                "event_time": "2026-05-09T09:20:00",
                "behavior_sessions": {"period": "P3", "date": "2026-05-09"},
            },
        ]
        p, _ = patch_supabase(execute_data=rows)
        with p:
            resp = client.get("/api/behavior/events", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["status"] == "success"
        assert body["data"]["total"] == 2
        events = body["data"]["events"]
        # Defaults filled in for missing fields
        e1 = next(e for e in events if e["id"] == "e1")
        assert e1["note"] == ""
        assert e1["transcript"] == ""
        assert e1["source"] == "manual"
        assert e1["period"] == "P3"

    def test_limit_clamped_to_max_200(self, client, auth_headers):
        p, chain = patch_supabase(execute_data=[])
        with p:
            client.get(
                "/api/behavior/events?limit=999",
                headers=auth_headers,
            )
        # Find the limit call args
        limit_calls = [c for c in chain.calls if c[0] == "limit"]
        assert limit_calls
        assert limit_calls[0][1] == (200,)

    def test_invalid_limit_falls_back_to_default(
        self, client, auth_headers,
    ):
        p, chain = patch_supabase(execute_data=[])
        with p:
            client.get(
                "/api/behavior/events?limit=not-a-number",
                headers=auth_headers,
            )
        limit_calls = [c for c in chain.calls if c[0] == "limit"]
        assert limit_calls
        assert limit_calls[0][1] == (50,)

    def test_filter_chain_applied(self, client, auth_headers):
        # Pin EXACT filter args + the order/limit chain (route uses
        # .order('event_time', desc=True).limit(50) by default).
        p, chain = patch_supabase(execute_data=[])
        with p:
            client.get(
                "/api/behavior/events?date_from=2026-01-01"
                "&date_to=2026-12-31&period=P2&student_name=smith",
                headers=auth_headers,
            )
        assert ("gte", ("behavior_sessions.date", "2026-01-01"), {}) in chain.calls
        assert ("lte", ("behavior_sessions.date", "2026-12-31"), {}) in chain.calls
        assert ("eq", ("behavior_sessions.period", "P2"), {}) in chain.calls
        assert ("eq", ("teacher_id", "teach-1"), {}) in chain.calls
        assert ("order", ("event_time",), {"desc": True}) in chain.calls

    def test_student_filter_substring_drops_non_match(
        self, client, auth_headers,
    ):
        rows = [
            {"id": "e1", "student_name": "Alice",
             "type": "praise", "note": "", "transcript": "",
             "source": "manual", "event_time": "",
             "behavior_sessions": {"period": "", "date": ""}},
            {"id": "e2", "student_name": "Bob",
             "type": "praise", "note": "", "transcript": "",
             "source": "manual", "event_time": "",
             "behavior_sessions": {"period": "", "date": ""}},
        ]
        p, _ = patch_supabase(execute_data=rows)
        with p:
            resp = client.get(
                "/api/behavior/events?student_name=alice",
                headers=auth_headers,
            )
        body = resp.get_json()
        assert body["data"]["total"] == 1
        assert body["data"]["events"][0]["student_name"] == "Alice"

    def test_query_exception_returns_empty_list(
        self, client, auth_headers,
    ):
        p, _ = patch_supabase(execute_side_effect=ValueError("query failed"))
        with p:
            resp = client.get(
                "/api/behavior/events",
                headers=auth_headers,
            )
        body = resp.get_json()
        assert body["data"]["events"] == []
        assert body["data"]["total"] == 0


# ──────────────────────────────────────────────────────────────────
# DELETE /api/behavior/data
# ──────────────────────────────────────────────────────────────────


class TestDeleteData:
    def test_clear_all_executes_session_delete(self, client, auth_headers):
        p, chain = patch_supabase(execute_data=[])
        with p:
            resp = client.delete(
                "/api/behavior/data?all=true",
                headers=auth_headers,
            )
        assert resp.status_code == 200
        assert "All behavior data cleared" in resp.get_json()["message"]
        # Session-table delete chain ran (delete + eq + execute)
        methods = [c[0] for c in chain.calls]
        assert "delete" in methods
        assert methods.count("eq") >= 1

    def test_per_student_uses_ilike_with_underscore_to_space(
        self, client, auth_headers,
    ):
        # student_id "john_smith" becomes "john smith" via underscore→space
        # and is passed to ilike() (no wildcards to escape in this name).
        p, chain = patch_supabase(execute_data=[])
        with p:
            resp = client.delete(
                "/api/behavior/data?student_id=john_smith",
                headers=auth_headers,
            )
        assert resp.status_code == 200
        assert "john_smith" in resp.get_json()["message"]
        ilike_calls = [c for c in chain.calls if c[0] == "ilike"]
        assert ilike_calls
        assert ilike_calls[0][1] == ("student_name", "john smith")

    def test_per_student_escapes_percent_wildcard(
        self, client, auth_headers,
    ):
        # Pin the Rule-#11 fix: a `%` in student_id MUST be escaped before
        # reaching ilike(), otherwise the query matches every student under
        # this teacher and deletes their data wholesale.
        p, chain = patch_supabase(execute_data=[])
        with p:
            resp = client.delete(
                "/api/behavior/data?student_id=%25",  # URL-encoded "%"
                headers=auth_headers,
            )
        assert resp.status_code == 200
        ilike_calls = [c for c in chain.calls if c[0] == "ilike"]
        assert ilike_calls
        # Production must escape the wildcard
        assert ilike_calls[0][1] == ("student_name", "\\%")

    def test_per_student_escapes_backslash(
        self, client, auth_headers,
    ):
        # A literal backslash in student_id should be doubled before being
        # passed to ilike() so the % escape itself stays unambiguous.
        p, chain = patch_supabase(execute_data=[])
        with p:
            resp = client.delete(
                "/api/behavior/data?student_id=%5C%25",  # "\%"
                headers=auth_headers,
            )
        assert resp.status_code == 200
        ilike_calls = [c for c in chain.calls if c[0] == "ilike"]
        assert ilike_calls
        # Backslash → \\, percent → \% → final string is "\\\\\\%"
        assert ilike_calls[0][1] == ("student_name", "\\\\\\%")

    def test_no_args_returns_error_without_supabase_call(
        self, client, auth_headers,
    ):
        # Per Rule #11 cleanup: validation now fires BEFORE _get_supabase()
        # so the early-error branch never instantiates a client.
        with patch(
            "backend.routes.behavior_routes._get_supabase",
        ) as mock_sb:
            resp = client.delete(
                "/api/behavior/data",
                headers=auth_headers,
            )
        body = resp.get_json()
        assert body["error"] == "Specify student_id or all=true"
        # _get_supabase should NOT have been called
        assert mock_sb.call_count == 0


# ──────────────────────────────────────────────────────────────────
# GET /api/behavior/debug
# ──────────────────────────────────────────────────────────────────


class TestDebug:
    def test_supabase_unconfigured_returns_warning(
        self, client, auth_headers,
    ):
        with patch(
            "backend.routes.behavior_routes._get_supabase",
            side_effect=RuntimeError("not configured"),
        ):
            resp = client.get("/api/behavior/debug", headers=auth_headers)
        body = resp.get_json()
        assert body["warning"] == "Supabase not configured"
        assert body["total_sessions"] == 0
        assert body["total_events"] == 0

    def test_happy_path_aggregates_counts_and_recent(
        self, client, auth_headers,
    ):
        # Two execute() calls are made (sessions then events). FakeChain
        # returns the same canned data each time. Use a side-effect-free
        # multi-call fake.
        sessions = [{"id": f"s{i}", "period": f"P{i}",
                     "date": "2026-05-09", "device": "web"}
                    for i in range(7)]
        events = [{"id": f"e{i}", "student_name": f"Name {i}",
                   "type": "correction",
                   "event_time": f"2026-05-09T09:{i:02d}:00"}
                  for i in range(15)]

        # Different responses per execute() call — alternate via a counter
        responses = [sessions, events]
        call_count = {"n": 0}

        def fake_execute(self):
            i = call_count["n"]
            call_count["n"] += 1
            m = MagicMock()
            m.data = responses[i] if i < len(responses) else []
            return m

        with patch.object(FakeChain, "execute", fake_execute):
            p, _ = patch_supabase()  # data ignored due to override
            with p:
                resp = client.get(
                    "/api/behavior/debug",
                    headers=auth_headers,
                )

        body = resp.get_json()
        assert body["teacher_id"] == "teach-1"
        assert body["total_sessions"] == 7
        assert body["total_events"] == 15
        # Recent-sessions clipped to 5
        assert len(body["recent_sessions"]) == 5
        # Recent-events clipped to 10 + flattened shape
        assert len(body["recent_events"]) == 10
        assert body["recent_events"][0]["name"] == "Name 0"
        assert body["recent_events"][0]["type"] == "correction"
        # Unique student_names sorted
        assert body["student_names"] == sorted(set(
            f"Name {i}" for i in range(15)
        ))

    def test_session_query_exception_resilient(
        self, client, auth_headers,
    ):
        # First execute() (sessions) raises, second (events) succeeds.
        call_count = {"n": 0}

        def fake_execute(self):
            i = call_count["n"]
            call_count["n"] += 1
            if i == 0:
                raise RuntimeError("sessions table down")
            m = MagicMock()
            m.data = [{"id": "e1", "student_name": "Z",
                       "type": "praise", "event_time": "2026-05-09T08:00:00"}]
            return m

        with patch.object(FakeChain, "execute", fake_execute):
            p, _ = patch_supabase()
            with p:
                resp = client.get(
                    "/api/behavior/debug",
                    headers=auth_headers,
                )
        body = resp.get_json()
        assert body["total_sessions"] == 0
        assert body["total_events"] == 1

    def test_event_query_exception_resilient(
        self, client, auth_headers,
    ):
        # Inverse: sessions OK, events raise
        call_count = {"n": 0}

        def fake_execute(self):
            i = call_count["n"]
            call_count["n"] += 1
            if i == 1:
                raise RuntimeError("events table down")
            m = MagicMock()
            m.data = [{"id": "s1", "period": "P", "date": "d", "device": "w"}]
            return m

        with patch.object(FakeChain, "execute", fake_execute):
            p, _ = patch_supabase()
            with p:
                resp = client.get(
                    "/api/behavior/debug",
                    headers=auth_headers,
                )
        body = resp.get_json()
        assert body["total_sessions"] == 1
        assert body["total_events"] == 0
        assert body["student_names"] == []


# ──────────────────────────────────────────────────────────────────
# GET /api/behavior/roster
# ──────────────────────────────────────────────────────────────────


class TestRoster:
    def test_periods_dir_missing_returns_empty(
        self, client, auth_headers, monkeypatch, tmp_path,
    ):
        # Point PERIODS_DIR at a path that doesn't exist
        missing = tmp_path / "no-such-periods"
        monkeypatch.setattr(
            "backend.routes.behavior_routes.PERIODS_DIR", str(missing),
        )
        resp = client.get("/api/behavior/roster", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_csv_with_meta_uses_period_name_from_meta(
        self, client, auth_headers, monkeypatch, tmp_path,
    ):
        d = tmp_path / "periods"
        d.mkdir()
        # Roster CSV with mixed name formats
        csv_path = d / "p1.csv"
        csv_path.write_text(
            'Student,Student ID\n'
            '"Doe;Jane",sid-1\n'      # semicolon split → "Jane Doe"
            '"Smith,John",sid-2\n'    # comma split → "John Smith"
            '"Single Name",sid-3\n'   # passthrough
            '"",sid-4\n'              # empty name → skipped
        )
        # Meta file overrides the period name
        meta_path = d / "p1.csv.meta.json"
        meta_path.write_text(json.dumps({"period_name": "Pretty Name"}))

        monkeypatch.setattr(
            "backend.routes.behavior_routes.PERIODS_DIR", str(d),
        )
        resp = client.get("/api/behavior/roster", headers=auth_headers)
        assert resp.status_code == 200
        roster = resp.get_json()
        assert len(roster) == 3
        names = [r["name"] for r in roster]
        assert "Jane Doe" in names
        assert "John Smith" in names
        assert "Single Name" in names
        # All carry the meta-supplied period name
        assert all(r["period"] == "Pretty Name" for r in roster)
        # Student IDs preserved
        assert any(r["student_id"] == "sid-1" for r in roster)

    def test_csv_without_meta_falls_back_to_filename(
        self, client, auth_headers, monkeypatch, tmp_path,
    ):
        d = tmp_path / "periods"
        d.mkdir()
        csv_path = d / "block_2.csv"
        csv_path.write_text('Student,Student ID\nKid Name,id-9\n')

        monkeypatch.setattr(
            "backend.routes.behavior_routes.PERIODS_DIR", str(d),
        )
        resp = client.get("/api/behavior/roster", headers=auth_headers)
        roster = resp.get_json()
        assert len(roster) == 1
        # filename underscores become spaces in fallback
        assert roster[0]["period"] == "block 2"

    def test_meta_json_parse_error_still_loads_csv(
        self, client, auth_headers, monkeypatch, tmp_path,
    ):
        d = tmp_path / "periods"
        d.mkdir()
        csv_path = d / "p1.csv"
        csv_path.write_text('Student,Student ID\nA Person,id-1\n')
        # Malformed JSON in meta — should be caught + sentry'd
        meta_path = d / "p1.csv.meta.json"
        meta_path.write_text("{ not valid json")

        monkeypatch.setattr(
            "backend.routes.behavior_routes.PERIODS_DIR", str(d),
        )
        resp = client.get("/api/behavior/roster", headers=auth_headers)
        roster = resp.get_json()
        # CSV still parses; meta defaults to filename-derived period
        assert len(roster) == 1
        assert roster[0]["period"] == "p1"

    def test_csv_open_error_swallowed(
        self, client, auth_headers, monkeypatch, tmp_path,
    ):
        # Create a CSV file that exists but raises on open via patch
        d = tmp_path / "periods"
        d.mkdir()
        (d / "broken.csv").write_text("Student,Student ID\n")
        # Also create a working CSV so we know one survives
        (d / "ok.csv").write_text(
            'Student,Student ID\nWorks,id-w\n'
        )

        monkeypatch.setattr(
            "backend.routes.behavior_routes.PERIODS_DIR", str(d),
        )
        # Make broken.csv raise IOError on open
        real_open = open

        def selective_open(path, *args, **kwargs):
            if str(path).endswith("broken.csv"):
                raise IOError("disk gone")
            return real_open(path, *args, **kwargs)

        with patch("builtins.open", side_effect=selective_open):
            resp = client.get(
                "/api/behavior/roster", headers=auth_headers,
            )
        roster = resp.get_json()
        # broken.csv silently skipped; ok.csv loaded
        assert len(roster) == 1
        assert roster[0]["name"] == "Works"
