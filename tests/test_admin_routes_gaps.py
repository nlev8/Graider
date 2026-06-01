"""Gap-fill unit tests for backend/routes/admin_routes.py.

Audit MAJOR #4 sprint follow-up to PR #297. Companion to existing
test_admin_routes.py which covers status, claim, and basic auth
failures. Targets the remaining ~182 uncovered LOC (53% baseline).

Endpoints + helpers covered
* /api/admin/teachers — happy path with discovery layers
* /api/admin/teacher/<id>/summary — full happy + 404 + 503 + Supabase
  partial-failure swallow
* /api/admin/activity — full happy with multi-teacher audit aggregation
  + per-teacher fail-silent
* _discover_teachers — happy 3-layer flow, Layer 1 SIS exception swallow,
  Layer 3 fallback exception swallow
* _discover_via_sis — non-oneroster early return, missing creds early
  return, no-school-match returns empty, full happy with email_map link
* _discover_fallback — no-supabase / no-data / system-row skip /
  email-as-key vs tid-as-key
* _build_email_map — no-supabase / no-data / non-dict data skipped
* _admin_claim_rate_limit_key — getattr exception fallback
* admin_overview — no-teachers no-data audit, score parse-fail (both
  paths), F grade boundary

Strategy: minimal Flask app + before_request that sets g.user_id from
the X-Test-Teacher-Id header (mirror of existing test_admin_routes.py).
storage_load/save patched per-test. _get_supabase patched at the route
module's import site.
"""
from __future__ import annotations

from unittest.mock import patch, MagicMock, AsyncMock

import pytest
from flask import Flask, g


@pytest.fixture
def app():
    from backend.routes.admin_routes import admin_bp
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret"
    app.config["RATELIMIT_ENABLED"] = False
    app.register_blueprint(admin_bp)
    return app


@pytest.fixture
def admin_client(app):
    """Test client that sets g.user_id from X-Test-Teacher-Id and
    auto-loads admin_role via storage_load (test must patch storage_load)."""
    @app.before_request
    def _set_user():
        from flask import request as r
        tid = r.headers.get("X-Test-Teacher-Id")
        if tid:
            g.user_id = tid

    return app.test_client()


def _admin_load(role_school="Lincoln High"):
    """Build a storage_load side_effect that returns admin_role for the
    requesting teacher and lets other keys pass through to None."""
    role = {"school": role_school, "manual_teachers": []}

    def loader(key, tid):
        if key.startswith("admin_role:"):
            return role
        return None

    return loader


# ──────────────────────────────────────────────────────────────────
# _admin_claim_rate_limit_key fallback
# ──────────────────────────────────────────────────────────────────


class TestRateLimitKey:
    def test_getattr_exception_falls_back_to_anon(self, app):
        """When `getattr(g, ...)` raises (no request context, etc.),
        the key falls back to ip|anon."""
        from backend.routes.admin_routes import _admin_claim_rate_limit_key
        with app.test_request_context():
            # No g.teacher_id or g.user_id set. Patch getattr to raise
            # to force the bare-except branch.
            with patch(
                "backend.routes.admin_routes.getattr",
                side_effect=Exception("getattr boom"),
            ):
                key = _admin_claim_rate_limit_key()
            assert key.endswith("|anon")


# ──────────────────────────────────────────────────────────────────
# _discover_teachers / _discover_via_sis / _discover_fallback /
# _build_email_map
# ──────────────────────────────────────────────────────────────────


class TestDiscoverTeachers:
    def test_full_three_layer_flow_with_all_sources(self):
        from backend.routes.admin_routes import _discover_teachers
        admin_role = {
            "school": "Lincoln HS",
            "manual_teachers": [
                {"email": "manual@x.com", "name": "Manual Teacher",
                 "user_id": "u-manual"},
            ],
        }

        # SIS layer returns one teacher; manual + fallback layers add
        # one each.
        def via_sis(role, tmap):
            tmap["sis@x.com"] = {
                "user_id": "u-sis", "name": "SIS Teacher",
                "email": "sis@x.com", "source": "sis",
            }

        with patch(
            "backend.routes.admin_routes._discover_via_sis",
            side_effect=via_sis,
        ), patch(
            "backend.routes.admin_routes._enrich_teachers",
        ):
            teachers = _discover_teachers(admin_role)
        emails = [t["email"] for t in teachers]
        # Both SIS and manual sources present (fallback skipped because
        # teacher_map already populated)
        assert "sis@x.com" in emails
        assert "manual@x.com" in emails

    def test_layer1_sis_exception_swallowed(self):
        from backend.routes.admin_routes import _discover_teachers
        admin_role = {"school": "X", "manual_teachers": []}
        with patch(
            "backend.routes.admin_routes._discover_via_sis",
            side_effect=RuntimeError("sis dead"),
        ), patch(
            "backend.routes.admin_routes._discover_fallback",
        ), patch(
            "backend.routes.admin_routes._enrich_teachers",
        ):
            # Must not raise; swallowed + sentry'd
            teachers = _discover_teachers(admin_role)
        assert isinstance(teachers, list)

    def test_layer3_fallback_runs_when_others_empty(self):
        from backend.routes.admin_routes import _discover_teachers
        admin_role = {"school": "X", "manual_teachers": []}

        def fallback(tmap):
            tmap["fb@x.com"] = {
                "user_id": "u-fb", "name": "FB Teacher",
                "email": "fb@x.com", "source": "fallback",
            }

        with patch(
            "backend.routes.admin_routes._discover_via_sis",
        ), patch(
            "backend.routes.admin_routes._discover_fallback",
            side_effect=fallback,
        ), patch(
            "backend.routes.admin_routes._enrich_teachers",
        ):
            teachers = _discover_teachers(admin_role)
        assert any(t["email"] == "fb@x.com" for t in teachers)

    def test_layer3_fallback_exception_swallowed(self):
        from backend.routes.admin_routes import _discover_teachers
        admin_role = {"school": "X", "manual_teachers": []}
        with patch(
            "backend.routes.admin_routes._discover_via_sis",
        ), patch(
            "backend.routes.admin_routes._discover_fallback",
            side_effect=RuntimeError("fallback dead"),
        ), patch(
            "backend.routes.admin_routes._enrich_teachers",
        ):
            teachers = _discover_teachers(admin_role)
        assert teachers == []


class TestDiscoverViaSis:
    def test_no_sis_config_returns_immediately(self):
        from backend.routes.admin_routes import _discover_via_sis
        with patch(
            "backend.routes.admin_routes.storage_load",
            return_value=None,
        ):
            tmap = {}
            _discover_via_sis({"school": "X"}, tmap)
        assert tmap == {}

    def test_non_oneroster_provider_returns_immediately(self):
        from backend.routes.admin_routes import _discover_via_sis
        with patch(
            "backend.routes.admin_routes.storage_load",
            return_value={"sis_type": "clever"},
        ):
            tmap = {}
            _discover_via_sis({"school": "X"}, tmap)
        assert tmap == {}

    def test_missing_credentials_returns_immediately(self):
        from backend.routes.admin_routes import _discover_via_sis
        with patch(
            "backend.routes.admin_routes.storage_load",
            return_value={
                "sis_type": "oneroster",
                "base_url": "https://x.example",
                # missing client_id + secret
            },
        ):
            tmap = {}
            _discover_via_sis({"school": "X"}, tmap)
        assert tmap == {}

    def test_no_school_match_returns_empty(self):
        from backend.routes.admin_routes import _discover_via_sis
        # OneRoster returns schools but none matches the admin's school
        sis_config = {
            "sis_type": "oneroster",
            "base_url": "https://x.example",
            "client_id": "ci",
            "client_secret": "cs",
        }
        fake_client = MagicMock()
        fake_client.base_url = sis_config["base_url"]
        fake_client._ensure_token = AsyncMock()
        # First call: list of schools (none matches)
        # Second call would be the teachers fetch (won't be reached)
        fake_client._get_with_retry = AsyncMock(
            return_value=[{"name": "Other High", "sourcedId": "x"}],
        )

        with patch(
            "backend.routes.admin_routes.storage_load",
            return_value=sis_config,
        ), patch(
            "backend.oneroster.OneRosterClient",
            return_value=fake_client,
        ):
            tmap = {}
            _discover_via_sis({"school": "Lincoln HS"}, tmap)
        assert tmap == {}

    def test_happy_path_links_via_email_map(self):
        from backend.routes.admin_routes import _discover_via_sis
        sis_config = {
            "sis_type": "oneroster",
            "base_url": "https://x.example",
            "client_id": "ci",
            "client_secret": "cs",
        }
        # Two _get_with_retry calls: schools then teachers
        call_count = {"i": 0}
        responses = [
            [{"name": "Lincoln HS", "sourcedId": "school-1"}],
            [
                {"email": "linked@x.com",
                 "givenName": "L", "familyName": "T"},
                {"email": "",  # no email → skipped
                 "givenName": "X", "familyName": "Y"},
                {"email": "unlinked@x.com",
                 "givenName": "U", "familyName": "T"},
            ],
        ]

        async def fake_get(http, url, label=None):
            i = call_count["i"]
            call_count["i"] += 1
            return responses[i] if i < len(responses) else []

        fake_client = MagicMock()
        fake_client.base_url = sis_config["base_url"]
        fake_client._ensure_token = AsyncMock()
        fake_client._get_with_retry = fake_get

        with patch(
            "backend.routes.admin_routes.storage_load",
            return_value=sis_config,
        ), patch(
            "backend.oneroster.OneRosterClient",
            return_value=fake_client,
        ), patch(
            "backend.routes.admin_routes._build_email_map",
            return_value={"linked@x.com": "user-1"},
        ):
            tmap = {}
            _discover_via_sis({"school": "Lincoln HS"}, tmap)
        # Linked teacher gets the matched user_id
        assert tmap["linked@x.com"]["user_id"] == "user-1"
        assert tmap["linked@x.com"]["name"] == "L T"
        # Unlinked teacher has empty user_id but is still listed
        assert tmap["unlinked@x.com"]["user_id"] == ""
        # Empty-email entry skipped
        assert "" not in tmap


class TestDiscoverFallback:
    def test_no_supabase_returns_immediately(self):
        from backend.routes.admin_routes import _discover_fallback
        with patch(
            "backend.routes.admin_routes._get_supabase",
            return_value=None,
        ):
            tmap = {}
            _discover_fallback(tmap)
        assert tmap == {}

    def test_no_data_returns_immediately(self):
        from backend.routes.admin_routes import _discover_fallback
        sb = MagicMock()
        sb.table.return_value.select.return_value.eq.return_value.execute.return_value = (
            MagicMock(data=None)
        )
        with patch(
            "backend.routes.admin_routes._get_supabase", return_value=sb,
        ):
            tmap = {}
            _discover_fallback(tmap)
        assert tmap == {}

    def test_system_row_skipped(self):
        from backend.routes.admin_routes import _discover_fallback
        rows = [
            {"teacher_id": "system",
             "data": {"email": "system@x.com", "name": "Sys"}},
            {"teacher_id": "real-1",
             "data": {"email": "real@x.com", "name": "Real"}},
        ]
        sb = MagicMock()
        sb.table.return_value.select.return_value.eq.return_value.execute.return_value = (
            MagicMock(data=rows)
        )
        with patch(
            "backend.routes.admin_routes._get_supabase", return_value=sb,
        ):
            tmap = {}
            _discover_fallback(tmap)
        # System row dropped
        assert "system@x.com" not in tmap
        # Real teacher recorded under email key
        assert "real@x.com" in tmap

    def test_no_email_uses_tid_as_key(self):
        from backend.routes.admin_routes import _discover_fallback
        rows = [
            {"teacher_id": "anon-1", "data": {}},  # no email
        ]
        sb = MagicMock()
        sb.table.return_value.select.return_value.eq.return_value.execute.return_value = (
            MagicMock(data=rows)
        )
        with patch(
            "backend.routes.admin_routes._get_supabase", return_value=sb,
        ):
            tmap = {}
            _discover_fallback(tmap)
        # Falls back to teacher_id as the map key + name
        assert tmap["anon-1"]["user_id"] == "anon-1"
        assert tmap["anon-1"]["name"] == "anon-1"


class TestBuildEmailMap:
    def test_no_supabase(self):
        from backend.routes.admin_routes import _build_email_map
        with patch(
            "backend.routes.admin_routes._get_supabase",
            return_value=None,
        ):
            assert _build_email_map() == {}

    def test_no_data(self):
        from backend.routes.admin_routes import _build_email_map
        sb = MagicMock()
        sb.table.return_value.select.return_value.eq.return_value.execute.return_value = (
            MagicMock(data=None)
        )
        with patch(
            "backend.routes.admin_routes._get_supabase", return_value=sb,
        ):
            assert _build_email_map() == {}

    def test_non_dict_data_skipped(self):
        from backend.routes.admin_routes import _build_email_map
        rows = [
            {"teacher_id": "t-1", "data": "not a dict"},
            {"teacher_id": "t-2", "data": {"email": "OK@x.com"}},
        ]
        sb = MagicMock()
        sb.table.return_value.select.return_value.eq.return_value.execute.return_value = (
            MagicMock(data=rows)
        )
        with patch(
            "backend.routes.admin_routes._get_supabase", return_value=sb,
        ):
            result = _build_email_map()
        # Non-dict skipped; emails normalized to lowercase
        assert result == {"ok@x.com": "t-2"}


# ──────────────────────────────────────────────────────────────────
# _chunked_in_rows + claim datetime edge cases
# ──────────────────────────────────────────────────────────────────


class TestChunkedInRows:
    def test_empty_values_returns_empty_list(self):
        from backend.routes.admin_routes import _chunked_in_rows
        sb = MagicMock()
        result = _chunked_in_rows(sb, "table", "col", [], "*")
        assert result == []
        # Sb chain never hit
        sb.table.assert_not_called()


class TestAdminClaimDatetimeEdges:
    def test_naive_expires_at_treated_as_utc(self, admin_client):
        # expires_at without tz info → replace(tzinfo=utc) on line 124,
        # then comparison fires (this expires_at is in the past).
        invite = {
            "school": "X",
            "expires_at": "2020-01-01T00:00:00",  # naive datetime, past
            "manual_teachers": [],
        }

        def loader(key, tid):
            if key.startswith("admin_invite:"):
                return invite
            return None

        with patch(
            "backend.routes.admin_routes.storage_load",
            side_effect=loader,
        ):
            resp = admin_client.post(
                "/api/admin/claim",
                json={"code": "AAAAAA"},
                headers={"X-Test-Teacher-Id": "t-1"},
            )
        # Past expiration → generic 400
        assert resp.status_code == 400

    def test_malformed_expires_at_returns_generic_400(self, admin_client):
        invite = {
            "school": "X",
            "expires_at": "not-a-date",
            "manual_teachers": [],
        }

        def loader(key, tid):
            if key.startswith("admin_invite:"):
                return invite
            return None

        with patch(
            "backend.routes.admin_routes.storage_load",
            side_effect=loader,
        ):
            resp = admin_client.post(
                "/api/admin/claim",
                json={"code": "AAAAAA"},
                headers={"X-Test-Teacher-Id": "t-1"},
            )
        assert resp.status_code == 400

    def test_legacy_naive_created_at_uses_7_day_ttl(self, admin_client):
        # No expires_at → falls back to created_at + 7 days. Naive
        # datetime → replace(tzinfo=utc) on line 138, then > 7 days
        # comparison fires.
        invite = {
            "school": "X",
            "created_at": "2020-01-01T00:00:00",  # naive, > 7 days old
            "manual_teachers": [],
        }

        def loader(key, tid):
            if key.startswith("admin_invite:"):
                return invite
            return None

        with patch(
            "backend.routes.admin_routes.storage_load",
            side_effect=loader,
        ):
            resp = admin_client.post(
                "/api/admin/claim",
                json={"code": "AAAAAA"},
                headers={"X-Test-Teacher-Id": "t-1"},
            )
        assert resp.status_code == 400


# ──────────────────────────────────────────────────────────────────
# /api/admin/teachers (happy path with admin auth)
# ──────────────────────────────────────────────────────────────────


class TestAdminTeachersHappy:
    def test_returns_discovered_teachers(self, admin_client):
        with patch(
            "backend.routes.admin_routes.storage_load",
            side_effect=_admin_load(),
        ), patch(
            "backend.storage.load",
            side_effect=_admin_load(),
        ), patch(
            "backend.routes.admin_routes._discover_teachers",
            return_value=[{"user_id": "t-1", "email": "t1@x.com",
                           "name": "T One", "source": "manual"}],
        ), patch(
            "backend.routes.admin_routes.audit_log",
        ):
            resp = admin_client.get(
                "/api/admin/teachers",
                headers={"X-Test-Teacher-Id": "admin-1"},
            )
        body = resp.get_json()
        assert resp.status_code == 200
        assert len(body["teachers"]) == 1
        assert body["teachers"][0]["email"] == "t1@x.com"


# ──────────────────────────────────────────────────────────────────
# /api/admin/overview — score parse fails + F-grade
# ──────────────────────────────────────────────────────────────────


class TestAdminOverviewBranches:
    def test_no_supabase_returns_empty_overview(self, admin_client):
        with patch(
            "backend.routes.admin_routes.storage_load",
            side_effect=_admin_load(),
        ), patch(
            "backend.storage.load",
            side_effect=_admin_load(),
        ), patch(
            "backend.routes.admin_routes._discover_teachers",
            return_value=[{"user_id": "t-1", "email": "t1@x.com",
                           "name": "T1"}],
        ), patch(
            "backend.routes.admin_routes._get_supabase",
            return_value=None,
        ), patch(
            "backend.routes.admin_routes.audit_log",
        ):
            resp = admin_client.get(
                "/api/admin/overview",
                headers={"X-Test-Teacher-Id": "admin-1"},
            )
        body = resp.get_json()
        assert body["total_teachers"] == 1
        assert body["total_students"] == 0
        assert body["total_assessments"] == 0

    def test_d_grade_score_lands_in_distribution(self, admin_client):
        # Pin the elif score >= 60 branch (line 632) by including a
        # 65-score in the chunked rows.
        # PR #606 Task 1: admin_overview now delegates to compute_overview,
        # which pulls rows via _chunked_in_rows_capped (returns (rows, capped)).
        # Re-pointed from _chunked_in_rows to the actual internal the route
        # calls; dispatcher returns (rows, False) tuples to match the new
        # signature. Same captured branch (elif score >= 60 → D).
        responses = [
            [{"join_code": "JC1", "teacher_id": "t-1"}],
            [{"score": 65}],  # D grade
            [],  # classes
        ]
        call_count = {"i": 0}

        def chunk_dispatch(sb, table, column, values, select_cols,
                           order=None, limit=None):
            i = call_count["i"]
            call_count["i"] += 1
            return (responses[i] if i < len(responses) else [], False)

        sb = MagicMock()
        with patch(
            "backend.routes.admin_routes.storage_load",
            side_effect=_admin_load(),
        ), patch(
            "backend.storage.load",
            side_effect=_admin_load(),
        ), patch(
            "backend.routes.admin_routes._discover_teachers",
            return_value=[{"user_id": "t-1", "email": "t1@x.com",
                           "name": "T1"}],
        ), patch(
            "backend.routes.admin_routes._get_supabase",
            return_value=sb,
        ), patch(
            "backend.routes.admin_routes._chunked_in_rows_capped",
            side_effect=chunk_dispatch,
        ), patch(
            "backend.routes.admin_routes.audit_log",
        ):
            resp = admin_client.get(
                "/api/admin/overview",
                headers={"X-Test-Teacher-Id": "admin-1"},
            )
        assert resp.get_json()["grade_distribution"]["D"] == 1

    def test_overview_outer_exception_swallowed(self, admin_client):
        # Make the aggregation pull raise → compute_overview's outer except
        # logs + sentry, but returns the zeroed overview. PR #606 Task 1:
        # re-pointed from _chunked_in_rows to _chunked_in_rows_capped (the
        # internal compute_overview actually calls).
        sb = MagicMock()
        with patch(
            "backend.routes.admin_routes.storage_load",
            side_effect=_admin_load(),
        ), patch(
            "backend.storage.load",
            side_effect=_admin_load(),
        ), patch(
            "backend.routes.admin_routes._discover_teachers",
            return_value=[{"user_id": "t-1", "email": "t1@x.com",
                           "name": "T1"}],
        ), patch(
            "backend.routes.admin_routes._get_supabase",
            return_value=sb,
        ), patch(
            "backend.routes.admin_routes._chunked_in_rows_capped",
            side_effect=RuntimeError("aggregation died"),
        ), patch(
            "backend.routes.admin_routes.audit_log",
        ):
            resp = admin_client.get(
                "/api/admin/overview",
                headers={"X-Test-Teacher-Id": "admin-1"},
            )
        # Must not raise; returns the empty-state overview
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["total_teachers"] == 1
        assert body["total_students"] == 0

    def test_score_parse_failures_skipped_grade_distribution_F(
        self, admin_client,
    ):
        # Build chunked_in_rows side_effect that returns:
        # 1. PA rows (1 join code)
        # 2. submissions rows including unparseable score + F-grade score
        # 3. classes rows (1 class)
        # 4. class_students rows (2 enrollments)
        # 5. published_content rows (1 content)
        # 6. student_submissions rows (more F-grade scores + unparseable)
        responses = [
            [{"join_code": "JC1", "teacher_id": "t-1"}],
            [
                {"score": "not-a-number"},  # parse fail
                {"score": 50},               # F (< 60)
            ],
            [{"id": "cls-1", "teacher_id": "t-1"}],
            [{"class_id": "cls-1", "student_id": "s-1"},
             {"class_id": "cls-1", "student_id": "s-2"}],
            [{"id": "cont-1", "class_id": "cls-1"}],
            [
                {"score": object()},  # parse fail (TypeError)
                {"score": 45},         # another F
            ],
        ]
        call_count = {"i": 0}

        # PR #606 Task 1: route now calls _chunked_in_rows_capped (returns
        # (rows, capped)); dispatcher returns (rows, False) tuples.
        def chunk_dispatch(sb, table, column, values, select_cols,
                           order=None, limit=None):
            i = call_count["i"]
            call_count["i"] += 1
            return (responses[i] if i < len(responses) else [], False)

        sb = MagicMock()
        with patch(
            "backend.routes.admin_routes.storage_load",
            side_effect=_admin_load(),
        ), patch(
            "backend.storage.load",
            side_effect=_admin_load(),
        ), patch(
            "backend.routes.admin_routes._discover_teachers",
            return_value=[{"user_id": "t-1", "email": "t1@x.com",
                           "name": "T1"}],
        ), patch(
            "backend.routes.admin_routes._get_supabase",
            return_value=sb,
        ), patch(
            "backend.routes.admin_routes._chunked_in_rows_capped",
            side_effect=chunk_dispatch,
        ), patch(
            "backend.routes.admin_routes.audit_log",
        ):
            resp = admin_client.get(
                "/api/admin/overview",
                headers={"X-Test-Teacher-Id": "admin-1"},
            )
        body = resp.get_json()
        # Two F-grade scores landed; parse fails skipped
        assert body["grade_distribution"]["F"] == 2
        assert body["average_score"] is not None
        assert body["total_students"] == 2
        assert body["total_assessments"] == 2  # PA + PC


# ──────────────────────────────────────────────────────────────────
# /api/admin/teacher/<id>/summary
# ──────────────────────────────────────────────────────────────────


class TestAdminTeacherSummary:
    def test_unknown_teacher_returns_404(self, admin_client):
        with patch(
            "backend.routes.admin_routes.storage_load",
            side_effect=_admin_load(),
        ), patch(
            "backend.storage.load",
            side_effect=_admin_load(),
        ), patch(
            "backend.routes.admin_routes._discover_teachers",
            return_value=[{"user_id": "t-1", "email": "t1@x.com",
                           "name": "T1"}],
        ):
            resp = admin_client.get(
                "/api/admin/teacher/UNKNOWN/summary",
                headers={"X-Test-Teacher-Id": "admin-1"},
            )
        assert resp.status_code == 404

    def test_no_supabase_returns_503(self, admin_client):
        with patch(
            "backend.routes.admin_routes.storage_load",
            side_effect=_admin_load(),
        ), patch(
            "backend.storage.load",
            side_effect=_admin_load(),
        ), patch(
            "backend.routes.admin_routes._discover_teachers",
            return_value=[{"user_id": "t-target", "email": "x@x.com"}],
        ), patch(
            "backend.routes.admin_routes._get_supabase",
            return_value=None,
        ):
            resp = admin_client.get(
                "/api/admin/teacher/t-target/summary",
                headers={"X-Test-Teacher-Id": "admin-1"},
            )
        assert resp.status_code == 503

    def test_full_happy_path(self, admin_client):
        # Build a Supabase whose chains cover classes/class_students/
        # published_assessments/submissions/audit_log queries.
        sb = MagicMock()

        def table_side_effect(name):
            chain = MagicMock()
            if name == "classes":
                chain.select.return_value.eq.return_value \
                    .execute.return_value = MagicMock(
                    data=[{"id": "cls-1", "name": "Math",
                           "subject": "Mathematics"}],
                )
            elif name == "class_students":
                chain.select.return_value.eq.return_value \
                    .execute.return_value = MagicMock(count=15, data=None)
            elif name == "published_assessments":
                chain.select.return_value.eq.return_value.order.return_value \
                    .limit.return_value.execute.return_value = MagicMock(
                    data=[{"title": "Quiz",
                           "join_code": "JC1",
                           "created_at": "2026-05-01"}],
                )
            elif name == "submissions":
                chain.select.return_value.eq.return_value \
                    .execute.return_value = MagicMock(
                    data=[{"score": 90}, {"score": 80}, {"score": "bad"}],
                )
            elif name == "audit_log":
                chain.select.return_value.eq.return_value.order.return_value \
                    .limit.return_value.execute.return_value = MagicMock(
                    data=[{"action": "X", "details": "y",
                           "timestamp": "2026-05-01"}],
                )
            return chain

        sb.table.side_effect = table_side_effect

        with patch(
            "backend.routes.admin_routes.storage_load",
            side_effect=_admin_load(),
        ), patch(
            "backend.storage.load",
            side_effect=_admin_load(),
        ), patch(
            "backend.routes.admin_routes._discover_teachers",
            return_value=[{"user_id": "t-target", "email": "x@x.com"}],
        ), patch(
            "backend.routes.admin_routes._get_supabase",
            return_value=sb,
        ), patch(
            "backend.routes.admin_routes.audit_log",
        ):
            resp = admin_client.get(
                "/api/admin/teacher/t-target/summary",
                headers={"X-Test-Teacher-Id": "admin-1"},
            )
        body = resp.get_json()
        assert resp.status_code == 200
        # 1 class with student_count from .count
        assert len(body["classes"]) == 1
        assert body["classes"][0]["student_count"] == 15
        # 1 recent assessment with avg_score (90 + 80) / 2 = 85.0
        assert len(body["recent_assessments"]) == 1
        assert body["recent_assessments"][0]["avg_score"] == 85.0
        # 1 audit row
        assert len(body["recent_activity"]) == 1

    def test_supabase_failure_swallowed(self, admin_client):
        sb = MagicMock()
        sb.table.side_effect = RuntimeError("supabase down")
        with patch(
            "backend.routes.admin_routes.storage_load",
            side_effect=_admin_load(),
        ), patch(
            "backend.storage.load",
            side_effect=_admin_load(),
        ), patch(
            "backend.routes.admin_routes._discover_teachers",
            return_value=[{"user_id": "t-target"}],
        ), patch(
            "backend.routes.admin_routes._get_supabase",
            return_value=sb,
        ), patch(
            "backend.routes.admin_routes.audit_log",
        ):
            resp = admin_client.get(
                "/api/admin/teacher/t-target/summary",
                headers={"X-Test-Teacher-Id": "admin-1"},
            )
        # Supabase failure swallowed → empty summary returned
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["classes"] == []
        assert body["recent_assessments"] == []


# ──────────────────────────────────────────────────────────────────
# /api/admin/activity
# ──────────────────────────────────────────────────────────────────


class TestAdminActivity:
    def test_no_supabase_returns_empty(self, admin_client):
        with patch(
            "backend.routes.admin_routes.storage_load",
            side_effect=_admin_load(),
        ), patch(
            "backend.storage.load",
            side_effect=_admin_load(),
        ), patch(
            "backend.routes.admin_routes._discover_teachers",
            return_value=[{"user_id": "t-1", "name": "T1"}],
        ), patch(
            "backend.routes.admin_routes._get_supabase",
            return_value=None,
        ):
            resp = admin_client.get(
                "/api/admin/activity",
                headers={"X-Test-Teacher-Id": "admin-1"},
            )
        assert resp.get_json() == {"activity": []}

    def test_no_teacher_ids_returns_empty(self, admin_client):
        with patch(
            "backend.routes.admin_routes.storage_load",
            side_effect=_admin_load(),
        ), patch(
            "backend.storage.load",
            side_effect=_admin_load(),
        ), patch(
            "backend.routes.admin_routes._discover_teachers",
            return_value=[{"user_id": "", "name": "No-ID"}],
        ), patch(
            "backend.routes.admin_routes._get_supabase",
            return_value=MagicMock(),
        ):
            resp = admin_client.get(
                "/api/admin/activity",
                headers={"X-Test-Teacher-Id": "admin-1"},
            )
        assert resp.get_json() == {"activity": []}

    def test_full_aggregation_sorted_and_limited(self, admin_client):
        sb = MagicMock()

        def execute_side(*args, **kwargs):
            return MagicMock(data=[
                {"action": "A", "details": "d1",
                 "timestamp": "2026-05-02T00:00:00", "teacher_id": "t-1"},
                {"action": "B", "details": "d2",
                 "timestamp": "2026-05-01T00:00:00", "teacher_id": "t-1"},
            ])

        sb.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute = (
            execute_side
        )

        with patch(
            "backend.routes.admin_routes.storage_load",
            side_effect=_admin_load(),
        ), patch(
            "backend.storage.load",
            side_effect=_admin_load(),
        ), patch(
            "backend.routes.admin_routes._discover_teachers",
            return_value=[
                {"user_id": "t-1", "name": "Alice"},
                {"user_id": "t-2", "name": "Bob"},
            ],
        ), patch(
            "backend.routes.admin_routes._get_supabase",
            return_value=sb,
        ), patch(
            "backend.routes.admin_routes.audit_log",
        ):
            resp = admin_client.get(
                "/api/admin/activity",
                headers={"X-Test-Teacher-Id": "admin-1"},
            )
        body = resp.get_json()
        # 2 teachers × 2 entries each = 4, sorted desc by timestamp
        assert len(body["activity"]) == 4
        assert body["activity"][0]["timestamp"] == "2026-05-02T00:00:00"
        # teacher_name attached
        assert body["activity"][0]["teacher_name"] in ("Alice", "Bob")

    def test_per_teacher_failure_silent(self, admin_client):
        sb = MagicMock()
        sb.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.side_effect = (
            RuntimeError("audit query died")
        )
        with patch(
            "backend.routes.admin_routes.storage_load",
            side_effect=_admin_load(),
        ), patch(
            "backend.storage.load",
            side_effect=_admin_load(),
        ), patch(
            "backend.routes.admin_routes._discover_teachers",
            return_value=[{"user_id": "t-1", "name": "T1"}],
        ), patch(
            "backend.routes.admin_routes._get_supabase",
            return_value=sb,
        ), patch(
            "backend.routes.admin_routes.audit_log",
        ):
            resp = admin_client.get(
                "/api/admin/activity",
                headers={"X-Test-Teacher-Id": "admin-1"},
            )
        # Failure swallowed → empty list
        assert resp.get_json() == {"activity": []}
