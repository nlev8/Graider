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
            for m in ('select', 'eq', 'order'):
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

    def test_audit_query_uses_order_desc_and_limit(self):
        """The audit_log query MUST be ordered desc + bounded by a
        limit so it can never explode for a hot district."""
        from backend.routes.admin_routes import _enrich_teachers

        teachers = [{"user_id": f"t-{i}"} for i in range(20)]

        mock_sb, recorded = self._spy_supabase(
            classes_rows=[], class_students_rows=[],
            assessments_rows=[], audit_rows=[],
        )
        with patch("backend.routes.admin_routes._get_supabase",
                   return_value=mock_sb):
            _enrich_teachers(teachers)

        # Order applied to audit_log in desc direction
        order_targets = [args for args in recorded['order_args']
                         if args[0] == 'audit_log']
        assert order_targets, "Expected order() call on audit_log"
        assert order_targets[0][1] == 'timestamp'
        assert order_targets[0][2] is True  # desc=True

        # Limit applied — at least 500, scales with teacher count
        audit_limits = [args for args in recorded['limit_args']
                        if args[0] == 'audit_log']
        assert audit_limits, "Expected limit() call on audit_log"
        assert audit_limits[0][1] >= 500
        assert audit_limits[0][1] >= 20 * 5  # 100 (5× teacher count)

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
