"""Tests for school admin routes.

Covers auth requirements, status, claim validation, and admin-only access.
"""
import pytest
from unittest.mock import patch, MagicMock
from flask import Flask, g


@pytest.fixture
def app():
    """Create a minimal Flask app with admin routes registered."""
    from backend.routes.admin_routes import admin_bp

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret"
    app.register_blueprint(admin_bp)
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def authed_app(app):
    """App with before_request that sets g.user_id from header."""
    @app.before_request
    def set_test_user():
        from flask import request
        teacher_id = request.headers.get("X-Test-Teacher-Id")
        if teacher_id:
            g.user_id = teacher_id

    return app


@pytest.fixture
def authed_client(authed_app):
    return authed_app.test_client()


# ── Status Tests ─────────────────────────────────────────────────────────

class TestAdminStatus:
    """Test GET /api/admin/status."""

    def test_status_requires_auth(self, client):
        """Status without auth returns 401."""
        resp = client.get("/api/admin/status")
        assert resp.status_code == 401

    def test_status_returns_false_for_non_admin(self, authed_client):
        """Non-admin teacher gets is_admin: false."""
        with patch("backend.routes.admin_routes.storage_load", return_value=None):
            resp = authed_client.get("/api/admin/status",
                                     headers={"X-Test-Teacher-Id": "teacher-123"})
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["is_admin"] is False

    def test_status_returns_true_for_admin(self, authed_client):
        """Admin teacher gets is_admin: true with school name."""
        admin_role = {"school": "Lincoln High", "claimed_at": "2026-03-20T00:00:00"}

        def mock_load(key, teacher_id):
            if key == "admin_role:teacher-123":
                return admin_role
            return None

        with patch("backend.routes.admin_routes.storage_load", side_effect=mock_load), \
             patch("backend.routes.admin_routes.audit_log"):
            resp = authed_client.get("/api/admin/status",
                                     headers={"X-Test-Teacher-Id": "teacher-123"})
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["is_admin"] is True
            assert data["school"] == "Lincoln High"


# ── Claim Tests ──────────────────────────────────────────────────────────

class TestAdminClaim:
    """Test POST /api/admin/claim."""

    def test_claim_requires_auth(self, client):
        """Claim without auth returns 401."""
        resp = client.post("/api/admin/claim", json={"code": "ABC123"})
        assert resp.status_code == 401

    def test_claim_requires_code(self, authed_client):
        """Claim without code returns 400 (generic failure shape)."""
        resp = authed_client.post("/api/admin/claim", json={},
                                  headers={"X-Test-Teacher-Id": "teacher-123"})
        assert resp.status_code == 400

    def test_claim_invalid_code_returns_generic_400(self, authed_client):
        """Audit MAJOR #8 (Codex 2026-05-06): non-existent code returns
        the SAME generic 400 + error body as missing/expired/malformed,
        so the response shape carries zero validity signal."""
        with patch("backend.routes.admin_routes.storage_load", return_value=None):
            resp = authed_client.post("/api/admin/claim", json={"code": "BADCODE"},
                                      headers={"X-Test-Teacher-Id": "teacher-123"})
            assert resp.status_code == 400
            assert "Unable to claim invite" in resp.get_json()["error"]

    def test_claim_valid_code_succeeds(self, authed_client):
        """Claim with valid invite code creates admin role."""
        from datetime import datetime, timezone
        invite = {
            "school": "Lincoln High",
            "created_at": datetime.now(tz=timezone.utc).isoformat(),
            "manual_teachers": [],
        }

        def mock_load(key, teacher_id):
            if key == "admin_invite:VALID1":
                return invite
            return None

        with patch("backend.routes.admin_routes.storage_load", side_effect=mock_load), \
             patch("backend.routes.admin_routes.storage_save") as mock_save, \
             patch("backend.storage.delete") as mock_delete, \
             patch("backend.routes.admin_routes.audit_log"):
            resp = authed_client.post("/api/admin/claim", json={"code": "VALID1"},
                                      headers={"X-Test-Teacher-Id": "teacher-123"})
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["status"] == "claimed"
            assert data["school"] == "Lincoln High"
            # Verify admin_role was saved
            mock_save.assert_called_once()
            save_args = mock_save.call_args[0]
            assert save_args[0] == "admin_role:teacher-123"

    def test_claim_expired_code_returns_generic_400(self, authed_client):
        """Audit MAJOR #8: expired invite returns the same generic 400 +
        error shape as invalid/missing — no enumeration signal.

        Round-2 fold (Codex 2026-05-07): production invites use
        `expires_at`, not `created_at`. Test both fields."""
        # Production schema (expires_at) — past expiry
        invite_expired_new = {
            "school": "Lincoln High",
            "expires_at": "2026-03-01T00:00:00+00:00",  # past
        }
        with patch("backend.routes.admin_routes.storage_load",
                   side_effect=lambda key, teacher_id: invite_expired_new if "EXPNEW" in key else None):
            resp = authed_client.post("/api/admin/claim", json={"code": "EXPNEW"},
                                      headers={"X-Test-Teacher-Id": "teacher-123"})
            assert resp.status_code == 400
            assert "Unable to claim invite" in resp.get_json()["error"]

        # Legacy schema (created_at + 7-day TTL) — still rejected
        invite_expired_legacy = {
            "school": "Lincoln High",
            "created_at": "2026-03-01T00:00:00+00:00",  # past 7 days ago
        }
        with patch("backend.routes.admin_routes.storage_load",
                   side_effect=lambda key, teacher_id: invite_expired_legacy if "EXPLEG" in key else None):
            resp = authed_client.post("/api/admin/claim", json={"code": "EXPLEG"},
                                      headers={"X-Test-Teacher-Id": "teacher-123"})
            assert resp.status_code == 400
            assert "Unable to claim invite" in resp.get_json()["error"]

    def test_claim_with_production_schema_expires_at_field(self, authed_client):
        """Round-2 Codex MAJOR fold: producer (district_routes.py:450)
        writes `expires_at`. Pre-fix, admin_claim only read `created_at`,
        so production invites NEVER expired — Codex verified an invite
        with past expires_at returned 200 and granted admin role.

        This test reproduces the exact production data shape and
        asserts rejection (NOT 200). Expired-by-expires_at is the
        load-bearing assertion for closing the security hole."""
        from datetime import datetime, timezone, timedelta
        past = (datetime.now(tz=timezone.utc) - timedelta(days=1)).isoformat()
        invite = {
            "school": "Lincoln High",
            "manual_teachers": [],
            "expires_at": past,  # production producer's field
        }
        with patch("backend.routes.admin_routes.storage_load",
                   return_value=invite), \
             patch("backend.routes.admin_routes.storage_save") as save:
            resp = authed_client.post("/api/admin/claim", json={"code": "PROD-LEAKED"},
                                      headers={"X-Test-Teacher-Id": "teacher-123"})
            assert resp.status_code == 400, (
                f"Production-schema expired invite must be REJECTED. "
                f"Got status {resp.status_code}; admin role saved: {save.called}"
            )
            assert not save.called, "Admin role MUST NOT be saved for expired invite"

    def test_claim_with_future_expires_at_succeeds(self, authed_client):
        """Counterpart to the above: a non-expired production-schema
        invite (expires_at in future) must succeed."""
        from datetime import datetime, timezone, timedelta
        future = (datetime.now(tz=timezone.utc) + timedelta(days=1)).isoformat()
        invite = {
            "school": "Lincoln High",
            "manual_teachers": [],
            "expires_at": future,
        }
        with patch("backend.routes.admin_routes.storage_load",
                   return_value=invite), \
             patch("backend.routes.admin_routes.storage_save") as mock_save, \
             patch("backend.storage.delete"), \
             patch("backend.routes.admin_routes.audit_log"):
            resp = authed_client.post("/api/admin/claim", json={"code": "VALIDFUT"},
                                      headers={"X-Test-Teacher-Id": "teacher-123"})
            assert resp.status_code == 200
            assert resp.get_json()["status"] == "claimed"
            assert mock_save.called

    def test_claim_failure_shapes_are_indistinguishable(self, authed_client):
        """Audit MAJOR #8: missing code, invalid code, malformed invite,
        expired invite must ALL return byte-identical responses (same
        status code, same body) so an attacker can't distinguish them."""
        responses = []

        # 1. Empty code
        r1 = authed_client.post("/api/admin/claim", json={"code": ""},
                                headers={"X-Test-Teacher-Id": "t"})
        responses.append(("empty", r1.status_code, r1.get_json()))

        # 2. Non-existent code (storage_load returns None)
        with patch("backend.routes.admin_routes.storage_load", return_value=None):
            r2 = authed_client.post("/api/admin/claim", json={"code": "MISSING"},
                                    headers={"X-Test-Teacher-Id": "t"})
            responses.append(("missing", r2.status_code, r2.get_json()))

        # 3. Malformed invite shape (string instead of dict)
        with patch("backend.routes.admin_routes.storage_load", return_value="garbage"):
            r3 = authed_client.post("/api/admin/claim", json={"code": "MALFORMED"},
                                    headers={"X-Test-Teacher-Id": "t"})
            responses.append(("malformed", r3.status_code, r3.get_json()))

        # 4. Expired invite
        with patch("backend.routes.admin_routes.storage_load",
                   return_value={"school": "X", "created_at": "2026-03-01T00:00:00+00:00"}):
            r4 = authed_client.post("/api/admin/claim", json={"code": "EXPIRED"},
                                    headers={"X-Test-Teacher-Id": "t"})
            responses.append(("expired", r4.status_code, r4.get_json()))

        # 5. Bad created_at format (parse failure)
        with patch("backend.routes.admin_routes.storage_load",
                   return_value={"school": "X", "created_at": "garbage-date"}):
            r5 = authed_client.post("/api/admin/claim", json={"code": "BADDATE"},
                                    headers={"X-Test-Teacher-Id": "t"})
            responses.append(("bad-date", r5.status_code, r5.get_json()))

        # All 5 failure modes → IDENTICAL status code + body.
        statuses = {label: status for label, status, _ in responses}
        bodies = {label: body for label, _, body in responses}

        assert all(s == 400 for s in statuses.values()), (
            f"All admin-claim failures must return 400; got {statuses}"
        )
        unique_bodies = {tuple(sorted(b.items())) for b in bodies.values()}
        assert len(unique_bodies) == 1, (
            f"All admin-claim failure bodies must be byte-identical to "
            f"prevent enumeration; got {len(unique_bodies)} distinct shapes: {bodies}"
        )

    def test_claim_has_rate_limit_decorator(self):
        """Static-source pin (Audit MAJOR #8): the @limiter.limit decorator
        must remain on the admin_claim route with both per-(IP+user) and
        per-user-only keys (round-2 Codex MAJOR fold)."""
        from pathlib import Path

        src = Path(__file__).resolve().parent.parent / "backend/routes/admin_routes.py"
        text = src.read_text()
        assert "@limiter.limit(" in text, "admin_claim must carry @limiter.limit"
        assert '"10 per hour;5 per minute"' in text, (
            "admin_claim per-(IP+user) budget must remain '10 per hour;5 per minute'"
        )
        assert '"20 per hour"' in text, (
            "admin_claim per-user-only budget must remain '20 per hour' to cap "
            "a roaming-IP attacker. Round-2 Codex MAJOR fold (2026-05-07)."
        )
        # Custom key_func must hash IP+user together (not bare IP)
        assert "_admin_claim_rate_limit_key" in text, (
            "admin_claim must use _admin_claim_rate_limit_key (combines IP+user) "
            "instead of the default get_remote_address (IP-only)."
        )

    def test_claim_does_storage_call_even_for_empty_code(self):
        """Round-2 Codex MINOR fold: empty-code path must do a storage
        probe (with a sentinel that can never collide with a real key)
        so its wall-clock profile matches the valid-shape paths,
        eliminating timing-side-channel for the empty-vs-shaped
        code distinction."""
        from pathlib import Path
        src = Path(__file__).resolve().parent.parent / "backend/routes/admin_routes.py"
        text = src.read_text()
        assert "__timing_anchor_" in text, (
            "admin_claim must probe storage on the empty-code path to flatten "
            "the timing differential between empty and present-shape codes."
        )


# ── Admin-Only Endpoint Tests ────────────────────────────────────────────

class TestAdminOnlyEndpoints:
    """Test that teachers/overview/activity/drill-down require admin."""

    def test_teachers_requires_admin(self, authed_client):
        """GET /api/admin/teachers without admin role returns 403."""
        with patch("backend.storage.load", return_value=None):
            resp = authed_client.get("/api/admin/teachers",
                                     headers={"X-Test-Teacher-Id": "teacher-123"})
            assert resp.status_code == 403

    def test_overview_requires_admin(self, authed_client):
        """GET /api/admin/overview without admin role returns 403."""
        with patch("backend.storage.load", return_value=None):
            resp = authed_client.get("/api/admin/overview",
                                     headers={"X-Test-Teacher-Id": "teacher-123"})
            assert resp.status_code == 403

    def test_activity_requires_admin(self, authed_client):
        """GET /api/admin/activity without admin role returns 403."""
        with patch("backend.storage.load", return_value=None):
            resp = authed_client.get("/api/admin/activity",
                                     headers={"X-Test-Teacher-Id": "teacher-123"})
            assert resp.status_code == 403

    def test_teacher_summary_requires_admin(self, authed_client):
        """GET /api/admin/teacher/<id>/summary without admin returns 403."""
        with patch("backend.storage.load", return_value=None):
            resp = authed_client.get("/api/admin/teacher/some-id/summary",
                                     headers={"X-Test-Teacher-Id": "teacher-123"})
            assert resp.status_code == 403

    def test_teachers_without_auth_returns_401(self, client):
        """GET /api/admin/teachers without any auth returns 401."""
        resp = client.get("/api/admin/teachers")
        assert resp.status_code == 401

    def test_overview_without_auth_returns_401(self, client):
        """GET /api/admin/overview without any auth returns 401."""
        resp = client.get("/api/admin/overview")
        assert resp.status_code == 401

    def test_activity_without_auth_returns_401(self, client):
        """GET /api/admin/activity without any auth returns 401."""
        resp = client.get("/api/admin/activity")
        assert resp.status_code == 401


# ── _enrich_teachers Batched Query Tests ─────────────────────────────────


class TestEnrichTeachersBatched:
    """Closes audit MAJOR #11 (Codex 2026-05-06 / GH issue #218):
    `_enrich_teachers` used to make 4 Supabase queries PER teacher
    (N+1). With 50 teachers that's 200 round trips per dashboard load.

    Now it uses 4 batched .in_() queries TOTAL — independent of teacher
    count. These tests pin both the query-count contract AND the
    correctness of the per-teacher count aggregation.
    """

    def _spy_supabase(self, classes_rows, class_students_rows,
                      assessments_rows, audit_rows):
        """Create a Supabase mock that returns scripted data per table
        and records `.table(name)` calls so we can assert query count.
        """
        recorded = {
            'tables_called': [],  # list of table names in order
            'in__calls': [],      # (table, column, values_count) tuples
            'order_args': [],
            'limit_args': [],
        }
        responses = {
            'classes': classes_rows,
            'class_students': class_students_rows,
            'published_assessments': assessments_rows,
            'audit_log': audit_rows,
        }

        def table_factory(name):
            recorded['tables_called'].append(name)
            current_table = name
            chain = MagicMock()
            result = MagicMock()
            result.data = responses.get(name, [])
            for m in ('select', 'eq', 'order', 'range'):
                getattr(chain, m).return_value = chain

            def in_(col, vals):
                recorded['in__calls'].append((current_table, col, len(vals)))
                return chain

            def order(col, desc=False):
                recorded['order_args'].append((current_table, col, desc))
                return chain

            def limit(n):
                recorded['limit_args'].append((current_table, n))
                return chain

            chain.in_.side_effect = in_
            chain.order.side_effect = order
            chain.limit.side_effect = limit
            chain.execute.return_value = result
            return chain

        mock_sb = MagicMock()
        mock_sb.table.side_effect = table_factory
        return mock_sb, recorded

    def test_query_count_independent_of_teacher_count(self):
        """No matter how many teachers, each entity table is queried
        EXACTLY ONCE. Pre-fix this was 4 queries per teacher."""
        from backend.routes.admin_routes import _enrich_teachers

        # 10 teachers
        teachers = [{"user_id": f"t-{i}"} for i in range(10)]

        mock_sb, recorded = self._spy_supabase(
            classes_rows=[], class_students_rows=[],
            assessments_rows=[], audit_rows=[],
        )
        with patch("backend.routes.admin_routes._get_supabase",
                   return_value=mock_sb):
            _enrich_teachers(teachers)

        # Should call: classes, published_assessments, audit_log.
        # class_students is conditionally skipped when no class_ids.
        # All teachers default to 0/None in this empty case.
        from collections import Counter
        counts = Counter(recorded['tables_called'])
        assert counts['classes'] == 1, (
            f"classes table queried {counts['classes']}× (expected 1, "
            f"N+1 regression?)"
        )
        assert counts['published_assessments'] == 1
        assert counts['audit_log'] == 1
        assert counts['class_students'] == 0  # skipped when no classes
        # All teachers default to 0/None
        for t in teachers:
            assert t['classes_count'] == 0
            assert t['students_count'] == 0
            assert t['assessments_count'] == 0
            assert t['last_activity'] is None

    def test_query_count_with_classes(self):
        """When there ARE class_ids, class_students adds one MORE query
        (4 total), still independent of teacher count."""
        from backend.routes.admin_routes import _enrich_teachers

        teachers = [{"user_id": f"t-{i}"} for i in range(50)]

        mock_sb, recorded = self._spy_supabase(
            classes_rows=[
                {"id": "c-1", "teacher_id": "t-0"},
                {"id": "c-2", "teacher_id": "t-1"},
            ],
            class_students_rows=[],
            assessments_rows=[],
            audit_rows=[],
        )
        with patch("backend.routes.admin_routes._get_supabase",
                   return_value=mock_sb):
            _enrich_teachers(teachers)

        from collections import Counter
        counts = Counter(recorded['tables_called'])
        assert counts['classes'] == 1
        assert counts['class_students'] == 1
        assert counts['published_assessments'] == 1
        assert counts['audit_log'] == 1
        # CRUCIAL: 50 teachers + 4 entity queries = 4 queries TOTAL.
        # Pre-fix would have been 50 × 4 = 200.
        assert sum(counts.values()) == 4, (
            f"Expected exactly 4 queries; got {dict(counts)}"
        )

    def test_count_aggregation_per_teacher(self):
        """Each teacher gets the count of THEIR rows, not the total."""
        from backend.routes.admin_routes import _enrich_teachers

        teachers = [
            {"user_id": "alice"},
            {"user_id": "bob"},
            {"user_id": "carol"},
        ]
        mock_sb, _ = self._spy_supabase(
            classes_rows=[
                {"id": "c-a1", "teacher_id": "alice"},
                {"id": "c-a2", "teacher_id": "alice"},
                {"id": "c-b1", "teacher_id": "bob"},
                # carol has no classes
            ],
            class_students_rows=[
                {"class_id": "c-a1", "student_id": "s-1"},
                {"class_id": "c-a1", "student_id": "s-2"},
                {"class_id": "c-a2", "student_id": "s-3"},
                {"class_id": "c-b1", "student_id": "s-4"},
            ],
            assessments_rows=[
                {"id": "ass-1", "teacher_id": "alice"},
                {"id": "ass-2", "teacher_id": "bob"},
                {"id": "ass-3", "teacher_id": "bob"},
                {"id": "ass-4", "teacher_id": "bob"},
            ],
            audit_rows=[
                {"teacher_id": "bob", "timestamp": "2026-05-07T10:00:00Z"},
                {"teacher_id": "alice", "timestamp": "2026-05-07T09:00:00Z"},
                {"teacher_id": "alice", "timestamp": "2026-05-06T22:00:00Z"},
            ],
        )
        with patch("backend.routes.admin_routes._get_supabase",
                   return_value=mock_sb):
            _enrich_teachers(teachers)

        by_id = {t['user_id']: t for t in teachers}
        # Alice
        assert by_id['alice']['classes_count'] == 2
        assert by_id['alice']['students_count'] == 3
        assert by_id['alice']['assessments_count'] == 1
        # Last activity is the FIRST occurrence in desc order — for
        # Alice, that's the 09:00:00 row (more recent of her two).
        assert by_id['alice']['last_activity'] == "2026-05-07T09:00:00Z"
        # Bob
        assert by_id['bob']['classes_count'] == 1
        assert by_id['bob']['students_count'] == 1
        assert by_id['bob']['assessments_count'] == 3
        assert by_id['bob']['last_activity'] == "2026-05-07T10:00:00Z"
        # Carol — empty across all entities
        assert by_id['carol']['classes_count'] == 0
        assert by_id['carol']['students_count'] == 0
        assert by_id['carol']['assessments_count'] == 0
        assert by_id['carol']['last_activity'] is None

    def test_audit_query_uses_order_desc_and_bounded_range(self):
        """The audit_log query MUST be ordered desc + bounded by a
        range so it can never explode for a hot district. Round-3
        Codex HIGH fold: bounded via .range() (not .limit()) because
        the helper now paginates result rows internally."""
        from backend.routes.admin_routes import _enrich_teachers

        # Capture the range() args via a custom spy so we can assert
        # the ceiling is at least max(500, teacher_count * 5).
        teachers = [{"user_id": f"t-{i}"} for i in range(20)]

        recorded_range = []
        recorded_order = []

        def _table_factory(name):
            chain = MagicMock()
            result = MagicMock()
            result.data = []
            for m in ('select', 'eq', 'in_'):
                getattr(chain, m).return_value = chain

            def order(col, desc=False):
                recorded_order.append((name, col, desc))
                return chain

            def range_(start, end):
                recorded_range.append((name, start, end))
                return chain

            chain.order.side_effect = order
            chain.range.side_effect = range_
            chain.execute.return_value = result
            return chain

        mock_sb = MagicMock()
        mock_sb.table.side_effect = _table_factory

        with patch("backend.routes.admin_routes._get_supabase",
                   return_value=mock_sb):
            _enrich_teachers(teachers)

        # Order applied to audit_log in desc direction
        audit_order = [r for r in recorded_order if r[0] == 'audit_log']
        assert audit_order, "Expected order() call on audit_log"
        assert audit_order[0][1] == 'timestamp'
        assert audit_order[0][2] is True  # desc=True

        # Range applied — the audit_log path passes limit=AUDIT_TOP_N
        # to _chunked_in_rows. AUDIT_TOP_N = max(500, teacher_count*5)
        # so for 20 teachers AUDIT_TOP_N = 500. The helper requests
        # range(0, page_size-1) where page_size = min(1000, 500) = 500.
        audit_ranges = [r for r in recorded_range if r[0] == 'audit_log']
        assert audit_ranges, "Expected range() call on audit_log"
        # The first call's end-index must be at least 499 (500 rows).
        # 5*20=100, max(500, 100)=500, so end >= 499.
        assert audit_ranges[0][1] == 0
        assert audit_ranges[0][2] >= 499

    def test_handles_no_teachers_gracefully(self):
        """Empty teacher list does NOT issue any Supabase queries."""
        from backend.routes.admin_routes import _enrich_teachers

        teachers = []
        mock_sb, recorded = self._spy_supabase(
            classes_rows=[], class_students_rows=[],
            assessments_rows=[], audit_rows=[],
        )
        with patch("backend.routes.admin_routes._get_supabase",
                   return_value=mock_sb):
            _enrich_teachers(teachers)

        assert recorded['tables_called'] == [], (
            f"Empty teacher list must short-circuit; got "
            f"{recorded['tables_called']}"
        )

    def test_handles_teachers_without_user_id(self):
        """Teachers missing user_id default to zero counts and don't
        contaminate the batched queries."""
        from backend.routes.admin_routes import _enrich_teachers

        teachers = [
            {"user_id": "alice"},
            {"name": "stub-no-uid"},  # no user_id
            {"user_id": "bob"},
        ]
        mock_sb, _ = self._spy_supabase(
            classes_rows=[
                {"id": "c-1", "teacher_id": "alice"},
            ],
            class_students_rows=[
                {"class_id": "c-1", "student_id": "s-1"},
            ],
            assessments_rows=[],
            audit_rows=[],
        )
        with patch("backend.routes.admin_routes._get_supabase",
                   return_value=mock_sb):
            _enrich_teachers(teachers)

        # The user_id-less teacher gets zeros without raising.
        no_uid = teachers[1]
        assert no_uid['classes_count'] == 0
        assert no_uid['students_count'] == 0
        assert no_uid['assessments_count'] == 0
        assert no_uid['last_activity'] is None

    def test_supabase_failure_falls_back_to_zeros(self):
        """If the batched query path raises, every teacher still gets
        zeroed defaults — the dashboard never returns malformed JSON."""
        from backend.routes.admin_routes import _enrich_teachers

        teachers = [{"user_id": "alice"}, {"user_id": "bob"}]
        mock_sb = MagicMock()
        mock_sb.table.side_effect = Exception("simulated supabase failure")

        with patch("backend.routes.admin_routes._get_supabase",
                   return_value=mock_sb):
            _enrich_teachers(teachers)

        for t in teachers:
            assert t['classes_count'] == 0
            assert t['students_count'] == 0
            assert t['assessments_count'] == 0
            assert t['last_activity'] is None

    def test_mid_pipeline_failure_zeroes_partial_state(self):
        """Round-2 Codex MEDIUM fold: when the FIRST query succeeds
        but a LATER query raises, the PR contract says all teachers
        get zeros — not a mix of partial earlier counts + zero later
        counts. Pin the contract."""
        from backend.routes.admin_routes import _enrich_teachers

        teachers = [{"user_id": "alice"}, {"user_id": "bob"}]
        # The classes query succeeds with data; class_students raises.
        call_n = {'count': 0}

        def _table_factory(name):
            chain = MagicMock()
            result = MagicMock()
            for m in ('select', 'eq', 'in_', 'order', 'limit'):
                getattr(chain, m).return_value = chain
            if name == 'classes':
                result.data = [
                    {"id": "c-1", "teacher_id": "alice"},
                    {"id": "c-2", "teacher_id": "bob"},
                ]
                chain.execute.return_value = result
            elif name == 'class_students':
                # Mid-pipeline failure
                chain.execute.side_effect = Exception("simulated mid-failure")
            else:
                result.data = []
                chain.execute.return_value = result
            return chain

        mock_sb = MagicMock()
        mock_sb.table.side_effect = _table_factory

        with patch("backend.routes.admin_routes._get_supabase",
                   return_value=mock_sb):
            _enrich_teachers(teachers)

        # Even though `classes` succeeded with data, the partial state
        # is reset on exception and every teacher gets zeros.
        for t in teachers:
            assert t['classes_count'] == 0, (
                f"Mid-pipeline failure must zero partial classes_count; "
                f"got {t['classes_count']}"
            )
            assert t['students_count'] == 0
            assert t['assessments_count'] == 0
            assert t['last_activity'] is None

    def test_result_rows_paginated_past_supabase_1000_row_cap(self):
        """Round-3 Codex HIGH fold: Supabase imposes a default 1,000-row
        return cap on `select()`. _chunked_in_rows MUST paginate within
        each chunk via `.range(offset, offset+page_size-1)` or large
        result sets silently truncate.

        Simulate: classes table returns 2,500 rows in 3 pages (1000 +
        1000 + 500). Helper must fetch all 3 pages."""
        from backend.routes.admin_routes import (
            _chunked_in_rows, _PAGE_SIZE,
        )

        # Pre-build 3 page responses
        page_a = [{'id': f'r-{i}', 'teacher_id': 't-x'} for i in range(1000)]
        page_b = [{'id': f'r-{i}', 'teacher_id': 't-x'} for i in range(1000, 2000)]
        page_c = [{'id': f'r-{i}', 'teacher_id': 't-x'} for i in range(2000, 2500)]

        recorded_ranges = []
        page_n = {'count': 0}

        def _execute_pages(*_args, **_kwargs):
            page_n['count'] += 1
            result = MagicMock()
            if page_n['count'] == 1:
                result.data = page_a
            elif page_n['count'] == 2:
                result.data = page_b
            elif page_n['count'] == 3:
                result.data = page_c
            else:
                result.data = []
            return result

        chain = MagicMock()
        for m in ('select', 'eq', 'in_', 'order'):
            getattr(chain, m).return_value = chain

        def range_(start, end):
            recorded_ranges.append((start, end))
            return chain

        chain.range.side_effect = range_
        chain.execute.side_effect = _execute_pages

        mock_sb = MagicMock()
        mock_sb.table.return_value = chain

        # Single chunk of 1 value, no caller-supplied limit → uses
        # _HARD_CAP (100K) target. Should paginate until response
        # < page_size.
        rows = _chunked_in_rows(
            mock_sb, 'classes', 'teacher_id', ['t-x'], 'id, teacher_id',
        )

        assert len(rows) == 2500, (
            f"Expected all 2500 rows; got {len(rows)} (silent truncation?)"
        )
        # Ranges should be [0..999, 1000..1999, 2000..2999]
        assert recorded_ranges == [(0, 999), (1000, 1999), (2000, 2999)], (
            f"Expected paginated ranges; got {recorded_ranges}"
        )

    def test_in_query_chunked_for_large_teacher_list(self):
        """Round-2 Codex HIGH fold: PostgREST `.in_()` URL-encodes the
        value list. Long lists could exceed the URL limit. Pin the
        contract that values are chunked at _IN_CHUNK_SIZE so a
        large district doesn't fail."""
        from backend.routes.admin_routes import (
            _enrich_teachers, _IN_CHUNK_SIZE,
        )

        # 250 teachers — exceeds the 200-id chunk size, so the
        # classes/published_assessments/audit_log queries should each
        # be split into 2 chunks (200 + 50).
        teachers = [{"user_id": f"t-{i:04d}"} for i in range(250)]

        recorded = {'in__calls': []}

        def _table_factory(name):
            chain = MagicMock()
            result = MagicMock()
            result.data = []
            for m in ('select', 'eq', 'order', 'limit'):
                getattr(chain, m).return_value = chain

            def in_(col, vals):
                recorded['in__calls'].append((name, col, len(vals)))
                return chain

            chain.in_.side_effect = in_
            chain.execute.return_value = result
            return chain

        mock_sb = MagicMock()
        mock_sb.table.side_effect = _table_factory

        with patch("backend.routes.admin_routes._get_supabase",
                   return_value=mock_sb):
            _enrich_teachers(teachers)

        # Filter to .in_() calls on teacher_id (skip class_students which
        # uses class_id and is empty here).
        teacher_in_calls = [c for c in recorded['in__calls'] if c[1] == 'teacher_id']
        # 3 entities × 2 chunks each = 6 calls
        assert len(teacher_in_calls) == 6, (
            f"Expected 6 chunked .in_(teacher_id, ...) calls "
            f"(3 entities × 2 chunks of {_IN_CHUNK_SIZE}); got "
            f"{len(teacher_in_calls)}: {teacher_in_calls}"
        )
        # Every chunk must be <= _IN_CHUNK_SIZE
        for table, col, n in teacher_in_calls:
            assert n <= _IN_CHUNK_SIZE, (
                f"{table}.in_({col}, ...) had {n} values > limit "
                f"{_IN_CHUNK_SIZE} — would exceed PostgREST URL cap"
            )


# ── admin_overview Route Integration Tests (Round-3 Codex MEDIUM fold) ───


class TestAdminOverviewBatched:
    """Round-3 Codex MEDIUM fold: pin the admin_overview route's
    batched data flow. Pre-fix the route was N+1+M; post-fix it's
    ≤6 chunked .in_() queries. These tests verify both the query
    count contract AND the aggregate correctness end-to-end."""

    def _scripted_supabase(self, table_responses):
        """Mock Supabase that returns per-table response data and
        records each .table() call. Supports the new range-paginated
        result fetch loop by always returning the configured rows
        as a single page (response < _PAGE_SIZE so loop breaks)."""
        recorded = {'tables_called': []}

        def table_factory(name):
            recorded['tables_called'].append(name)
            chain = MagicMock()
            result = MagicMock()
            result.data = table_responses.get(name, [])
            for m in ('select', 'eq', 'in_', 'order', 'range', 'limit'):
                getattr(chain, m).return_value = chain
            chain.execute.return_value = result
            return chain

        mock_sb = MagicMock()
        mock_sb.table.side_effect = table_factory
        return mock_sb, recorded

    def test_overview_aggregates_across_both_publish_paths(
        self, authed_client,
    ):
        """admin_overview must sum total_assessments across BOTH the
        join-code (published_assessments) AND class-based
        (published_content) paths, plus aggregate scores from BOTH
        submissions tables."""
        # 3 teachers under admin scope
        teachers = [
            {"user_id": "alice"},
            {"user_id": "bob"},
            {"user_id": "carol"},
        ]
        admin_role = {"school": "Test High", "claimed_at": "2026-03-20T00:00:00"}

        table_responses = {
            'classes': [
                {"id": "cls-a", "teacher_id": "alice"},
                {"id": "cls-b", "teacher_id": "bob"},
            ],
            'class_students': [
                {"class_id": "cls-a", "student_id": "s-1"},
                {"class_id": "cls-a", "student_id": "s-2"},
                {"class_id": "cls-b", "student_id": "s-3"},
            ],
            'published_assessments': [
                {"id": "pa-1", "join_code": "AAA111", "teacher_id": "alice"},
                {"id": "pa-2", "join_code": "BBB222", "teacher_id": "bob"},
            ],
            'submissions': [
                {"score": 85},
                {"score": 90},
            ],
            'published_content': [
                {"id": "pc-1", "class_id": "cls-a"},
                {"id": "pc-2", "class_id": "cls-b"},
            ],
            'student_submissions': [
                {"score": 75},
                {"score": 95},
            ],
            'audit_log': [],
        }

        mock_sb, recorded = self._scripted_supabase(table_responses)

        def mock_load(key, teacher_id):
            if key.startswith("admin_role:"):
                return admin_role
            return None

        # Prime the _discover_teachers path: admin_overview reads admin
        # scope from g.admin_role, which is the dict returned by
        # storage_load("admin_role:<teacher_id>"). _discover_teachers
        # calls storage_load("teachers_index") via a hardcoded key.
        # We mock _discover_teachers directly to return the test list.
        with patch("backend.storage.load",
                   side_effect=lambda k, ns: admin_role if k.startswith("admin_role:") else None), \
             patch("backend.routes.admin_routes._discover_teachers",
                   return_value=teachers), \
             patch("backend.routes.admin_routes._get_supabase",
                   return_value=mock_sb), \
             patch("backend.routes.admin_routes.audit_log"):
            resp = authed_client.get(
                "/api/admin/overview",
                headers={"X-Test-Teacher-Id": "admin-x"},
            )

        assert resp.status_code == 200, resp.get_data(as_text=True)
        data = resp.get_json()
        # 3 teachers in scope
        assert data["total_teachers"] == 3
        # Both publish paths counted: 2 published_assessments + 2
        # published_content = 4 total assessments
        assert data["total_assessments"] == 4
        # Students = enrollment row count (3 rows in fixture)
        assert data["total_students"] == 3
        # average_score = (85 + 90 + 75 + 95) / 4 = 86.25 → 86.2 via
        # Python's banker's rounding (round-half-to-even)
        assert data["average_score"] == 86.2
        # Grade distribution: 85=B, 90=A, 75=C, 95=A
        gd = data["grade_distribution"]
        assert gd["A"] == 2
        assert gd["B"] == 1
        assert gd["C"] == 1
        assert gd["D"] == 0
        assert gd["F"] == 0

    def test_overview_uses_batched_queries_not_per_teacher(
        self, authed_client,
    ):
        """50 teachers should yield ≤6 distinct table.()-name calls
        (each table queried once or zero times), NOT 50× anything."""
        teachers = [{"user_id": f"t-{i}"} for i in range(50)]
        admin_role = {"school": "S", "claimed_at": "2026-03-20T00:00:00"}

        # Empty rows everywhere — we only care about query count.
        mock_sb, recorded = self._scripted_supabase({})

        def mock_load(key, teacher_id):
            if key.startswith("admin_role:"):
                return admin_role
            return None

        with patch("backend.storage.load",
                   side_effect=lambda k, ns: admin_role if k.startswith("admin_role:") else None), \
             patch("backend.routes.admin_routes._discover_teachers",
                   return_value=teachers), \
             patch("backend.routes.admin_routes._get_supabase",
                   return_value=mock_sb), \
             patch("backend.routes.admin_routes.audit_log"):
            resp = authed_client.get(
                "/api/admin/overview",
                headers={"X-Test-Teacher-Id": "admin-x"},
            )

        assert resp.status_code == 200
        from collections import Counter
        counts = Counter(recorded['tables_called'])
        # With empty results, the route only queries:
        # - published_assessments (1 chunk of 50 ids)
        # - classes (1 chunk of 50 ids)
        # submissions, class_students, published_content,
        # student_submissions all skipped because the prior result is
        # empty (no join_codes, no class_ids).
        # CRUCIAL: no table queried more than 1 time despite 50 teachers.
        for table, count in counts.items():
            assert count <= 1, (
                f"{table} queried {count}× — should be ≤1 (50 teachers, "
                f"batched queries should be independent of teacher count)"
            )
        # Total queries should be small — much less than 50.
        assert sum(counts.values()) <= 6, (
            f"Total queries {sum(counts.values())} > 6; got {dict(counts)}"
        )
