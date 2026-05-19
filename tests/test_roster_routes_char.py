"""Characterization net for the student-history/roster route cluster.

Tier 2 Slice 3 PR3 pins the EXACT observed status + JSON contract of the six
routes in this cluster BEFORE the verbatim ``@app.route`` ->
``@roster_bp.route`` move, so the move can be proven zero-behavior-change:

  * ``GET  /api/student-history/<student_id>``  (get_student_history_api)
  * ``GET  /api/student-baseline/<student_id>`` (get_student_baseline_api)
  * ``POST /api/retranslate-feedback``          (retranslate_feedback)
  * ``POST /api/extract-student-from-image``    (extract_student_from_image)
  * ``POST /api/add-student-to-roster``         (add_student_to_roster)
  * ``GET  /api/list-periods``                  (list_periods)

Harness note (characterization discipline, pin reality, never assume).
The six routes are currently wired via bare ``@app.route`` decorators on the
``backend.app.app`` object. The ``client`` fixture in tests/conftest_routes.py
builds its app purely from ``register_routes(...)`` (pre-move that aggregator
does NOT include this cluster), so that fixture is NOT byte-identical across
the move and cannot characterize a zero-behavior-change relocation. The only
harness that yields byte-identical status+JSON both before and after the
verbatim move is the real ``backend.app.app`` object, because pre-move the
cluster is registered there via ``@app.route`` and post-move the cluster is
registered there via the blueprint ``register_routes()`` mounts (app.py calls
``register_routes`` on the same app), and the route bodies are byte-identical.
So the authed contract assertions run against ``backend.app.app`` with a
``before_request`` that authenticates a teacher (the current ``@app.route``
wiring named by Task 3.1 Step 1). Task 3.2 rewrites this file to the
suite-safe ``_fresh_blueprint_app`` pattern once the blueprint exists, while
keeping every pinned status+JSON value identical. The auth-missing case
reuses the canonical existing pattern (a Flask app with NO g.user_id
before_request, so the stacked ``@require_teacher`` rejects with the plain
401 envelope), byte-identical 401 JSON pre and post move.

PRE-EXISTING SHADOWING (faithfully preserved, pinned exactly as observed).
Two of the six URLs are already shadowed in production and were before this
PR: ``backend/routes/grading_routes.py`` registers
``GET /api/student-history/<student_id>`` (endpoint ``grading.get_student
_history``) and ``backend/routes/settings_routes.py`` registers
``GET /api/list-periods`` (endpoint ``settings.list_periods``). app.py calls
``register_routes()`` (mid-file, before the cluster's ``@app.route``
decorators), so Werkzeug's first-added-rule-wins matching makes the
grading/settings blueprint views the live production handlers and the app.py
cluster copies (``get_student_history_api`` / ``list_periods``) dead/shadowed
on the real app. The verbatim move does not touch grading_routes or
settings_routes, and ``roster_bp`` is registered AFTER both ``grading_bp``
and ``settings_bp`` in ``register_routes()``, so the moved copies stay
shadowed by exactly the same winners post-move: the production contract for
those two URLs is unchanged. This net therefore pins, for those two URLs, the
production winner (``grading``/``settings``) via the real-wiring harness
(``test_collided_urls_production_winner_unchanged`` / ``test_urls_unchanged``)
AND, separately, the moved app.py-cluster body in isolation (a fresh app
mounting only the cluster view) so the verbatim body itself is also proven
byte-identical. Both are pinned exactly as observed pre-move. This is the
same honest-note discipline PR2 applied to its pre-existing ``save_results``
NameError (issue #423): a verbatim relocation preserves pre-existing latent
conditions rather than fixing them.

Machine-variant field: production ``GET /api/list-periods`` is served by
``settings.list_periods``, which reads the developer's real
``~/.graider_data/periods`` directory; its body is machine-variant and is NOT
pinned by exact value. It is pinned by status 200, the ``periods`` key
presence, and the unchanged winning endpoint. The app.py cluster's own
``list_periods`` body IS pinned exactly, in isolation, against a hermetic tmp
periods directory (the route resolves the path from ``os.path.expanduser``,
monkeypatched to tmp), so the verbatim body is a true zero-behavior-change
proof without depending on machine state.
"""
import csv
import os

import pytest
from flask import Flask, g


# -- Authed harness: the real backend.app.app, teacher authenticated --------
@pytest.fixture
def authed_client():
    """Real backend.app.app with a teacher authenticated.

    This is the current ``@app.route`` wiring pre-move and the
    register_routes-mounted blueprint post-move, byte-identical responses
    either way for a verbatim relocation. char-teacher has no persisted
    Supabase data, so the per-teacher grading state stays a clean slate
    (suite-stable, machine-independent).
    """
    import backend.app as bapp

    app = bapp.app
    app.config["TESTING"] = True

    # Idempotent: only attach the auth before_request once.
    if not getattr(app, "_char_roster_authed_hook", False):
        @app.before_request
        def _char_set_user():  # pragma: no cover - trivial test hook
            g.user_id = "char-teacher"

        app._char_roster_authed_hook = True

    st = bapp._get_state("char-teacher")
    st["is_running"] = False
    st["results"] = []

    return app.test_client()


def _cluster_only_app(*, with_auth, periods_dir=None):
    """Fresh Flask app mounting ONLY the six app.py-cluster view functions.

    Used to pin each verbatim-moved body in isolation (no grading/settings
    blueprint collision), so the body itself is proven byte-identical
    pre/post move independent of registration-order shadowing. Pre-move the
    views come from ``backend.app``; Task 3.2 repoints this to
    ``backend.routes.roster_routes`` while keeping every pinned value
    identical.
    """
    import backend.app as bapp

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.add_url_rule(
        "/api/student-history/<student_id>", "ch_hist",
        bapp.get_student_history_api, methods=["GET"],
    )
    app.add_url_rule(
        "/api/student-baseline/<student_id>", "ch_base",
        bapp.get_student_baseline_api, methods=["GET"],
    )
    app.add_url_rule(
        "/api/retranslate-feedback", "ch_retr",
        bapp.retranslate_feedback, methods=["POST"],
    )
    app.add_url_rule(
        "/api/extract-student-from-image", "ch_extract",
        bapp.extract_student_from_image, methods=["POST"],
    )
    app.add_url_rule(
        "/api/add-student-to-roster", "ch_add",
        bapp.add_student_to_roster, methods=["POST"],
    )
    app.add_url_rule(
        "/api/list-periods", "ch_list",
        bapp.list_periods, methods=["GET"],
    )

    if with_auth:
        @app.before_request
        def _u():  # pragma: no cover - trivial test hook
            g.user_id = "char-teacher"

    return app


@pytest.fixture
def cluster_client():
    """Authed isolated-cluster client (no blueprint collision)."""
    return _cluster_only_app(with_auth=True).test_client()


@pytest.fixture
def noauth_cluster_client():
    """Isolated-cluster client WITHOUT any g.user_id before_request.

    Mirrors the canonical require_teacher-rejection mechanism: a Flask app
    with no auth before_request; the stacked ``@require_teacher`` returns the
    plain 401 {"error": "Authentication required"} (NOT the RFC 7807
    envelope: require_teacher short-circuits before handle_route_errors).
    """
    return _cluster_only_app(with_auth=False).test_client()


# A nonexistent student id: load_student_history returns a default empty
# history dict for it (NOT None), so get_student_history_api returns 200 with
# that empty structure. The grading.get_student_history production winner
# returns 404 for the same id. Both pinned below, exactly as observed.
_NX_ID = "nonexistent-char-xyz-zzz-id"


# == app.py cluster bodies in isolation (verbatim-move byte-identity) ========
class TestStudentHistoryClusterBody:
    def test_unknown_id_returns_empty_history_200(self, cluster_client):
        """app.py get_student_history_api: load_student_history returns a
        default empty-history dict (truthy) for an unknown id, so the
        ``if not history`` 404 branch is NOT taken -> 200 with the empty
        structure. Pinned exactly as observed pre-move."""
        r = cluster_client.get(f"/api/student-history/{_NX_ID}")
        assert r.status_code == 200
        body = r.get_json()
        assert body == {
            "student_id": _NX_ID,
            "assignments": [],
            "patterns": [],
            "skill_scores": {},
            "streaks": {},
            "last_updated": None,
        }

    def test_auth_missing_is_401(self, noauth_cluster_client):
        r = noauth_cluster_client.get(f"/api/student-history/{_NX_ID}")
        assert r.status_code == 401
        assert r.get_json() == {"error": "Authentication required"}


class TestStudentBaselineClusterBody:
    def test_insufficient_history_is_404(self, cluster_client):
        r = cluster_client.get(f"/api/student-baseline/{_NX_ID}")
        assert r.status_code == 404
        assert r.get_json() == {
            "error": "Insufficient history for baseline (need 3+ assignments)"
        }

    def test_auth_missing_is_401(self, noauth_cluster_client):
        r = noauth_cluster_client.get(f"/api/student-baseline/{_NX_ID}")
        assert r.status_code == 401
        assert r.get_json() == {"error": "Authentication required"}


class TestRetranslateFeedbackClusterBody:
    def test_no_feedback_is_200_error(self, cluster_client):
        """Empty english_feedback -> 200 with the fixed error envelope (the
        route returns jsonify({...}) with no status code -> default 200)."""
        r = cluster_client.post("/api/retranslate-feedback", json={})
        assert r.status_code == 200
        assert r.get_json() == {"error": "No feedback provided"}

    def test_blank_feedback_is_200_error(self, cluster_client):
        r = cluster_client.post(
            "/api/retranslate-feedback",
            json={"english_feedback": "", "target_language": "spanish"},
        )
        assert r.status_code == 200
        assert r.get_json() == {"error": "No feedback provided"}

    def test_auth_missing_is_401(self, noauth_cluster_client):
        r = noauth_cluster_client.post("/api/retranslate-feedback", json={})
        assert r.status_code == 401
        assert r.get_json() == {"error": "Authentication required"}


class TestExtractStudentFromImageClusterBody:
    def test_no_image_is_200_error(self, cluster_client):
        r = cluster_client.post("/api/extract-student-from-image", json={})
        assert r.status_code == 200
        assert r.get_json() == {"error": "No image provided"}

    def test_empty_image_is_200_error(self, cluster_client):
        r = cluster_client.post(
            "/api/extract-student-from-image", json={"image": ""}
        )
        assert r.status_code == 200
        assert r.get_json() == {"error": "No image provided"}

    def test_auth_missing_is_401(self, noauth_cluster_client):
        r = noauth_cluster_client.post(
            "/api/extract-student-from-image", json={}
        )
        assert r.status_code == 401
        assert r.get_json() == {"error": "Authentication required"}


class TestAddStudentToRosterClusterBody:
    def test_no_period_is_200_error(self, cluster_client):
        r = cluster_client.post("/api/add-student-to-roster", json={})
        assert r.status_code == 200
        assert r.get_json() == {"error": "Period is required"}

    def test_blank_period_is_200_error(self, cluster_client):
        r = cluster_client.post(
            "/api/add-student-to-roster",
            json={"student": {"first_name": "A", "last_name": "B"},
                  "period": ""},
        )
        assert r.status_code == 200
        assert r.get_json() == {"error": "Period is required"}

    def test_missing_names_is_200_error(self, cluster_client):
        r = cluster_client.post(
            "/api/add-student-to-roster",
            json={"student": {"first_name": "", "last_name": ""},
                  "period": "9"},
        )
        assert r.status_code == 200
        assert r.get_json() == {
            "error": "First name and last name are required"
        }

    def test_happy_add_writes_period_csv(
        self, cluster_client, tmp_path, monkeypatch
    ):
        """A valid add to a fresh period -> 200 success; the route creates
        the period CSV and appends the student. periods_dir is repointed to a
        hermetic tmp dir (the route resolves it via os.path.expanduser),
        making the assertion machine-independent while exercising the real
        write path. expanduser on the periods path returns tmp; any other
        path passes through unchanged so unrelated logic is untouched."""
        periods = tmp_path / "periods"
        periods.mkdir()
        real_expanduser = os.path.expanduser

        def fake_expanduser(p):
            if p == "~/.graider_data/periods":
                return str(periods)
            return real_expanduser(p)

        monkeypatch.setattr(os.path, "expanduser", fake_expanduser)
        r = cluster_client.post(
            "/api/add-student-to-roster",
            json={
                "student": {"first_name": "Char", "last_name": "Tester",
                            "student_id": "S1", "grade": "07"},
                "period": "3",
            },
        )
        assert r.status_code == 200
        body = r.get_json()
        assert body["success"] is True
        assert body["message"] == "Added Char Tester to Period 3"
        assert body["student_name"] == "Tester; Char"
        assert body["period_file"] == str(periods / "Period 3.csv")
        rows = list(csv.reader((periods / "Period 3.csv").open()))
        assert rows[0] == [
            "Student", "Student ID", "Local ID", "Grade",
            "Local Student ID", "Team",
        ]
        assert rows[1] == ["Tester; Char", "S1", "S1", "07", "S1", ""]

    def test_duplicate_add_is_200_error(
        self, cluster_client, tmp_path, monkeypatch
    ):
        """Adding the same student twice -> the second is the fixed
        already-exists error (pins the dedupe branch of the same body)."""
        periods = tmp_path / "periods"
        periods.mkdir()
        real_expanduser = os.path.expanduser

        def fake_expanduser(p):
            if p == "~/.graider_data/periods":
                return str(periods)
            return real_expanduser(p)

        monkeypatch.setattr(os.path, "expanduser", fake_expanduser)
        payload = {
            "student": {"first_name": "Dup", "last_name": "Kid"},
            "period": "4",
        }
        first = cluster_client.post(
            "/api/add-student-to-roster", json=payload
        )
        assert first.status_code == 200
        assert first.get_json()["success"] is True
        second = cluster_client.post(
            "/api/add-student-to-roster", json=payload
        )
        assert second.status_code == 200
        assert second.get_json() == {
            "error": "Student 'Kid; Dup' already exists in Period 4"
        }

    def test_auth_missing_is_401(self, noauth_cluster_client):
        r = noauth_cluster_client.post(
            "/api/add-student-to-roster", json={}
        )
        assert r.status_code == 401
        assert r.get_json() == {"error": "Authentication required"}


class TestListPeriodsClusterBody:
    def test_empty_periods_dir_is_200_empty_list(
        self, cluster_client, tmp_path, monkeypatch
    ):
        """app.py list_periods against a hermetic empty periods dir -> 200
        with an empty periods list. Pins the verbatim body's deterministic
        empty branch independent of machine state."""
        periods = tmp_path / "periods"
        periods.mkdir()
        real_expanduser = os.path.expanduser

        def fake_expanduser(p):
            if p == "~/.graider_data/periods":
                return str(periods)
            return real_expanduser(p)

        monkeypatch.setattr(os.path, "expanduser", fake_expanduser)
        r = cluster_client.get("/api/list-periods")
        assert r.status_code == 200
        assert r.get_json() == {"periods": []}

    def test_periods_dir_with_csv_reports_count(
        self, cluster_client, tmp_path, monkeypatch
    ):
        """A hermetic periods dir with one CSV -> 200; the route's own
        ``{name,file,student_count}`` shape, count = lines minus header.
        Pins the populated branch of the same byte-identical body."""
        periods = tmp_path / "periods"
        periods.mkdir()
        (periods / "Period 7.csv").write_text(
            "Student,Student ID\nA;B,1\nC;D,2\n"
        )
        real_expanduser = os.path.expanduser

        def fake_expanduser(p):
            if p == "~/.graider_data/periods":
                return str(periods)
            return real_expanduser(p)

        monkeypatch.setattr(os.path, "expanduser", fake_expanduser)
        r = cluster_client.get("/api/list-periods")
        assert r.status_code == 200
        assert r.get_json() == {
            "periods": [
                {"name": "Period 7", "file": "Period 7.csv",
                 "student_count": 2}
            ]
        }

    def test_auth_missing_is_401(self, noauth_cluster_client):
        r = noauth_cluster_client.get("/api/list-periods")
        assert r.status_code == 401
        assert r.get_json() == {"error": "Authentication required"}


# == Production-faithful contract on the real register_routes wiring =========
class TestProductionContract:
    """The four app.py-only routes are production-live and served by the
    cluster body on the real backend.app.app; the two collided URLs are
    served by the grading/settings blueprint winners. All pinned exactly as
    observed pre-move; all unchanged by the verbatim move (it does not touch
    grading_routes/settings_routes and roster_bp registers after both)."""

    def test_student_history_collided_winner_is_grading_404(
        self, authed_client
    ):
        """On the real app, GET /api/student-history/<id> is served by the
        first-registered rule = grading.get_student_history (registered via
        register_routes before the app.py @app.route). For an unknown id it
        returns the grading view's 404, NOT the app.py cluster's 200 empty
        history. Pinned exactly; unchanged post-move."""
        r = authed_client.get(f"/api/student-history/{_NX_ID}")
        assert r.status_code == 404
        assert r.get_json() == {"error": "Student history not found"}

    def test_student_baseline_is_404(self, authed_client):
        r = authed_client.get(f"/api/student-baseline/{_NX_ID}")
        assert r.status_code == 404
        assert r.get_json() == {
            "error": "Insufficient history for baseline (need 3+ assignments)"
        }

    def test_retranslate_no_feedback_is_200_error(self, authed_client):
        r = authed_client.post("/api/retranslate-feedback", json={})
        assert r.status_code == 200
        assert r.get_json() == {"error": "No feedback provided"}

    def test_extract_no_image_is_200_error(self, authed_client):
        r = authed_client.post("/api/extract-student-from-image", json={})
        assert r.status_code == 200
        assert r.get_json() == {"error": "No image provided"}

    def test_add_student_no_period_is_200_error(self, authed_client):
        r = authed_client.post("/api/add-student-to-roster", json={})
        assert r.status_code == 200
        assert r.get_json() == {"error": "Period is required"}

    def test_list_periods_collided_winner_is_settings_200(
        self, authed_client
    ):
        """On the real app, GET /api/list-periods is served by the
        first-registered rule = settings.list_periods. Its body reads the
        developer's real periods dir (machine-variant), so pin only status
        200 and the periods key presence. Unchanged post-move (roster_bp
        registers after settings_bp, so it stays shadowed by the same
        winner)."""
        r = authed_client.get("/api/list-periods")
        assert r.status_code == 200
        assert "periods" in r.get_json()
