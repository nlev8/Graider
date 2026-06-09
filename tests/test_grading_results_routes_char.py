"""Characterization net for the grading-results CRUD route cluster.

Tier 2 Slice 3 PR1 — pins the EXACT observed status + JSON contract of the
four routes (`/api/grade-individual`, `/api/delete-result`,
`/api/update-approval`, `/api/update-approvals-bulk`) plus the auth-missing
behavior, BEFORE the verbatim `@app.route` -> `@grading_results_bp.route`
move, so the move can be proven zero-behavior-change.

Harness note (characterization discipline — pin reality, never assume):
The four routes' EXACT contract (status + JSON, for every probed branch) was
captured against the real `backend.app.app` object BEFORE the move (commit
that adds this file). Those probed values — e.g. ``400 {"error":"No file
provided"}``, ``404 {"error":"Result not found"}``, ``500 {"error":"An
internal error occurred"}`` — are reproduced below as hard assertions.

Harness mechanics mirror the canonical existing route-char pattern
(tests/test_admin_routes.py): build a FRESH `flask.Flask` app per test and
register the extracted cluster blueprint on it (NEVER mutate the shared
`backend.app.app` singleton — touching `before_request` on it after another
suite test has issued a request raises Flask's "setup method can no longer be
called" error, making the net non-reproducible in the full suite). Post-move
the blueprint IS the canonical wiring `register_routes()` mounts, so a
fresh-app + `register_blueprint(grading_results_bp)` serves byte-identical
responses to the pre-move `@app.route` wiring (verified: the route bodies are
byte-identical, so identical inputs produce identical outputs). The authed
harness adds a `before_request` that sets `g.user_id`; the auth-missing
harness registers the same blueprint with NO such hook, so the stacked
`@require_teacher` rejects with ``401 {"error":"Authentication required"}``
(exact canonical require_teacher contract).
"""
import pytest
from flask import Flask, g

# flask_app (+ its fixture deps) from the shared route-test conftest, used by
# test_urls_unchanged to assert the URL map is unchanged post-extraction.
from tests.conftest_routes import (  # noqa: F401
    flask_app,
    grading_lock,
    mock_grading_state,
)


def _fresh_blueprint_app(*, with_auth):
    """Build a fresh Flask app with the extracted cluster blueprint mounted.

    Never mutates the shared backend.app.app singleton (suite-safe). Post-move
    the blueprint is the canonical wiring register_routes() mounts, so this
    serves byte-identical responses to the pre-move @app.route wiring.
    """
    from backend.routes.grading_results_routes import grading_results_bp

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(grading_results_bp)

    if with_auth:
        @app.before_request
        def _char_set_user():  # pragma: no cover - trivial test hook
            g.user_id = "char-teacher"

    return app


# ── Authed harness: fresh app + cluster blueprint, teacher authenticated ─────
@pytest.fixture
def authed_client():
    """Fresh-app blueprint harness with a teacher authenticated.

    Byte-identical responses to the pre-move @app.route wiring for this
    verbatim relocation (route bodies are byte-identical).
    """
    from backend.grading.state import _get_state

    app = _fresh_blueprint_app(with_auth=True)

    # Reset this teacher's real per-teacher grading state per test (the
    # blueprint reads _get_state from backend.grading.state directly).
    st = _get_state("char-teacher")
    st["is_running"] = False
    st["results"] = []

    return app.test_client()


# ── No-auth harness for the require_teacher rejection (canonical pattern) ─────
@pytest.fixture
def noauth_client():
    """Fresh-app blueprint harness WITHOUT any g.user_id before_request.

    Mirrors the canonical require_teacher-rejection mechanism used by
    tests/test_admin_routes.py (a blueprint app with no auth before_request);
    require_teacher returns 401 {"error": "Authentication required"}.
    """
    app = _fresh_blueprint_app(with_auth=False)
    return app.test_client()


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

    def test_real_file_reaches_grading_and_handles_error_result(self, authed_client):
        """A real image part flows past the guards and REACHES the grading
        helper. GH #423 fixed the latent NameError that previously made this a
        generic 500 *before* grading was ever invoked (the route's broad
        ``except`` caught the unresolved-name); the helper is now imported, so
        the route genuinely calls it. We mock the helper (no live OpenAI call)
        and pin the ERROR-result contract: a grading ``ERROR`` surfaces as a 500
        carrying the grader's feedback."""
        import io
        from unittest.mock import patch

        with patch(
            "backend.routes.grading_results_routes.grade_with_parallel_detection",
            return_value={"letter_grade": "ERROR", "feedback": "grading unavailable"},
        ) as mock_grade:
            r = authed_client.post(
                "/api/grade-individual",
                data={"file": (io.BytesIO(b"\x89PNG fake"), "scan.png")},
                content_type="multipart/form-data",
            )
        mock_grade.assert_called_once()  # reached grading — no NameError (GH #423)
        assert r.status_code == 500
        assert r.get_json() == {"error": "grading unavailable"}

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


# ── Blueprint extraction gates ───────────────────────────────────────────────
def test_blueprint_importable():
    from backend.routes.grading_results_routes import grading_results_bp
    assert grading_results_bp.name == 'grading_results'


def test_urls_unchanged(flask_app):  # flask_app from tests/conftest_routes.py
    rules = {r.rule for r in flask_app.url_map.iter_rules()}
    for u in ('/api/grade-individual', '/api/delete-result',
              '/api/update-approval', '/api/update-approvals-bulk'):
        assert u in rules
