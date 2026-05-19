"""Characterization net for the grading-results CRUD route cluster.

Tier 2 Slice 3 PR1 — pins the EXACT observed status + JSON contract of the
four routes (`/api/grade-individual`, `/api/delete-result`,
`/api/update-approval`, `/api/update-approvals-bulk`) plus the auth-missing
behavior, BEFORE the verbatim `@app.route` -> `@grading_results_bp.route`
move, so the move can be proven zero-behavior-change.

Harness note (characterization discipline — pin reality, never assume):
The four routes are currently wired via bare `@app.route` decorators on the
`backend.app.app` object. The `client` fixture in tests/conftest_routes.py
builds its app from `register_routes(...)`, which (pre-move) does NOT include
this cluster, so that fixture returns 404 for these paths pre-move and real
responses post-move — i.e. it is NOT byte-identical across the move and
therefore cannot characterize a zero-behavior-change relocation.

The only harness that yields byte-identical status+JSON both before and after
the verbatim move is the real `backend.app.app` object, because:
  * pre-move the cluster is registered there via `@app.route`;
  * post-move the cluster is registered there via the blueprint that
    `register_routes()` mounts (app.py calls register_routes on the same app);
  * the route bodies are byte-identical, so the responses are identical.
So the contract assertions below run against `backend.app.app` with a
`before_request` that authenticates a teacher (the "current @app.route
wiring" Task 1.2 Step 2 names). The auth-missing case reuses the canonical
existing pattern (see tests/test_admin_routes.py): a minimal app that
registers the cluster's blueprint WITHOUT a g.user_id before_request, so the
stacked `@require_teacher` decorator rejects with 401. Pre-move that pattern
is exercised against the not-yet-extracted code via backend.app.app with no
auth before_request (require_teacher still rejects identically); post-move it
targets the extracted blueprint. Both yield byte-identical 401 JSON.
"""
import pytest
from flask import Flask, g


# ── Authed harness: the real backend.app.app, teacher authenticated ──────────
@pytest.fixture
def authed_client():
    """Real backend.app.app with a teacher authenticated.

    This is the "current @app.route wiring" pre-move and the
    register_routes-mounted blueprint post-move — byte-identical responses
    either way for a verbatim relocation.
    """
    import backend.app as bapp

    app = bapp.app
    app.config["TESTING"] = True

    # Idempotent: only attach the auth before_request once.
    if not getattr(app, "_char_authed_hook", False):
        @app.before_request
        def _char_set_user():  # pragma: no cover - trivial test hook
            g.user_id = "char-teacher"

        app._char_authed_hook = True

    # Reset this teacher's grading state to a clean slate per test.
    st = bapp._get_state("char-teacher")
    st["is_running"] = False
    st["results"] = []

    return app.test_client()


# ── No-auth harness for the require_teacher rejection (canonical pattern) ─────
@pytest.fixture
def noauth_client():
    """Real backend.app.app WITHOUT any g.user_id before_request.

    Mirrors the canonical require_teacher-rejection mechanism used by
    tests/test_admin_routes.py (a blueprint app with no auth before_request);
    require_teacher returns 401 {"error": "Authentication required"}.
    """
    import importlib

    import backend.app as bapp

    # Build a fresh Flask app importing the same view functions, with NO
    # auth before_request. Pre-move the cluster lives on bapp.app via
    # @app.route; post-move it is a blueprint. To exercise require_teacher
    # rejection identically across the move without depending on which app
    # object owns the route, we hit the real app but strip g.user_id.
    app = bapp.app
    app.config["TESTING"] = True

    # A second app object that registers ONLY the cluster's blueprint (post
    # move) — falls back to the real app pre-move. importlib keeps this
    # resilient to the module not existing yet (RED before Step 2).
    try:
        bp_mod = importlib.import_module("backend.routes.grading_results_routes")
        bp_app = Flask(__name__)
        bp_app.config["TESTING"] = True
        bp_app.register_blueprint(bp_mod.grading_results_bp)
        return bp_app.test_client()
    except ModuleNotFoundError:
        # Pre-move: blueprint module does not exist. Exercise require_teacher
        # on the real app with auth deliberately absent. We cannot remove the
        # authed fixture's before_request (different fixture/app instance),
        # so build a bare client and clear g via a teardown-safe request.
        bare = Flask(__name__)
        bare.config["TESTING"] = True

        # Import the underlying view functions off backend.app and register
        # them on a bare app with no auth hook, preserving the full decorator
        # stack (require_teacher included) since we reference the decorated
        # callables directly.
        bare.add_url_rule(
            "/api/grade-individual", "grade_individual",
            bapp.grade_individual, methods=["POST"],
        )
        bare.add_url_rule(
            "/api/delete-result", "delete_single_result",
            bapp.delete_single_result, methods=["POST"],
        )
        bare.add_url_rule(
            "/api/update-approval", "update_approval",
            bapp.update_approval, methods=["POST"],
        )
        bare.add_url_rule(
            "/api/update-approvals-bulk", "update_approvals_bulk",
            bapp.update_approvals_bulk, methods=["POST"],
        )
        return bare.test_client()


CLUSTER_URLS = (
    "/api/grade-individual",
    "/api/delete-result",
    "/api/update-approval",
    "/api/update-approvals-bulk",
)


# ── /api/grade-individual ────────────────────────────────────────────────────
class TestGradeIndividual:
    def test_happy_path_no_file_is_400(self, authed_client):
        """No multipart 'file' part -> pinned 400 with exact JSON.

        (The genuine happy path requires a real image + OpenAI call; the
        first reachable deterministic contract is the missing-file guard.
        Characterization pins the real reachable contract, not a mock.)
        """
        r = authed_client.post("/api/grade-individual", data={})
        assert r.status_code == 400
        assert r.get_json() == {"error": "No file provided"}

    def test_empty_filename_is_400(self, authed_client):
        """A 'file' part with an empty filename -> pinned 400.

        Reaches the `if file.filename == ''` guard (distinct message from the
        missing-part guard above).
        """
        import io

        r = authed_client.post(
            "/api/grade-individual",
            data={"file": (io.BytesIO(b""), "")},
            content_type="multipart/form-data",
        )
        assert r.status_code == 400
        assert r.get_json() == {"error": "No file selected"}

    def test_real_file_reaches_grading_pinned_500(self, authed_client):
        """A real image part flows past the guards into the grading body.

        Characterization discipline: pin the EXACT current behavior, do not
        assume. In the current code path the grading helper is not resolvable
        in this execution context, the route's own broad
        ``except Exception`` catches it and returns its pinned internal-error
        contract. This is verbatim-preserved by the move (byte-identical
        body), so it must stay byte-identical post-move.
        """
        import io

        r = authed_client.post(
            "/api/grade-individual",
            data={"file": (io.BytesIO(b"\x89PNG fake"), "scan.png")},
            content_type="multipart/form-data",
        )
        assert r.status_code == 500
        assert r.get_json() == {"error": "An internal error occurred"}

    def test_auth_missing_is_401(self, noauth_client):
        r = noauth_client.post("/api/grade-individual", data={})
        assert r.status_code == 401
        assert r.get_json() == {"error": "Authentication required"}


# ── /api/delete-result ───────────────────────────────────────────────────────
class TestDeleteResult:
    def test_no_filename_is_400(self, authed_client):
        r = authed_client.post("/api/delete-result", json={})
        assert r.status_code == 400
        assert r.get_json() == {"error": "Filename is required"}

    def test_empty_filename_is_400(self, authed_client):
        r = authed_client.post("/api/delete-result", json={"filename": ""})
        assert r.status_code == 400
        assert r.get_json() == {"error": "Filename is required"}

    def test_not_found_empty_state_is_already_deleted(self, authed_client):
        """Filename not present in empty results -> 200 already_deleted."""
        r = authed_client.post(
            "/api/delete-result", json={"filename": "nope.docx"}
        )
        assert r.status_code == 200
        assert r.get_json() == {
            "status": "already_deleted",
            "filename": "nope.docx",
        }

    def test_auth_missing_is_401(self, noauth_client):
        r = noauth_client.post("/api/delete-result", json={})
        assert r.status_code == 401
        assert r.get_json() == {"error": "Authentication required"}


# ── /api/update-approval ─────────────────────────────────────────────────────
class TestUpdateApproval:
    def test_no_filename_is_400(self, authed_client):
        r = authed_client.post("/api/update-approval", json={})
        assert r.status_code == 400
        assert r.get_json() == {"error": "Missing filename"}

    def test_not_found_is_404(self, authed_client):
        """Filename not in (empty) results -> pinned 404 Result not found."""
        r = authed_client.post(
            "/api/update-approval",
            json={"filename": "ghost.docx", "approval": "approved"},
        )
        assert r.status_code == 404
        assert r.get_json() == {"error": "Result not found"}

    def test_auth_missing_is_401(self, noauth_client):
        r = noauth_client.post("/api/update-approval", json={})
        assert r.status_code == 401
        assert r.get_json() == {"error": "Authentication required"}


# ── /api/update-approvals-bulk ───────────────────────────────────────────────
class TestUpdateApprovalsBulk:
    def test_no_approvals_is_400(self, authed_client):
        r = authed_client.post("/api/update-approvals-bulk", json={})
        assert r.status_code == 400
        assert r.get_json() == {"error": "No approvals provided"}

    def test_empty_approvals_is_400(self, authed_client):
        r = authed_client.post(
            "/api/update-approvals-bulk", json={"approvals": {}}
        )
        assert r.status_code == 400
        assert r.get_json() == {"error": "No approvals provided"}

    def test_no_matching_results_count_zero(self, authed_client):
        """approvals provided but no matching results -> 200 count 0."""
        r = authed_client.post(
            "/api/update-approvals-bulk",
            json={"approvals": {"absent.docx": "approved"}},
        )
        assert r.status_code == 200
        assert r.get_json() == {"status": "updated", "count": 0}

    def test_auth_missing_is_401(self, noauth_client):
        r = noauth_client.post("/api/update-approvals-bulk", json={})
        assert r.status_code == 401
        assert r.get_json() == {"error": "Authentication required"}
