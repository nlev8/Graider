"""
Cross-tenant isolation contract for /api/confirm-send pending payload.

Codex round-6 (PR #246) caught that `confirm_send` had a Python scoping
bug: line 1486 read `g.user_id` BEFORE the inline `from flask import g`
at line 1509. Python treated `g` as a local for the whole function due
to the later import, so the per-teacher Supabase `pending_send` lookup
silently raised UnboundLocalError, was swallowed by the broad except,
and the route fell back to the SHARED `~/.graider_data/pending_send.json`
file — leaking pending send payloads across tenants.

Round-6 fold:
- Hoisted `g` to module-level import in `email_routes.py`.
- Removed the 5 redundant inline `from flask import g` statements.

These tests pin the per-teacher pending storage path so a future re-import
or scoping mistake can't silently regress to the shared fallback.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest


@pytest.fixture
def flask_app():
    """Minimal Flask app wrapping email_bp with g.user_id set."""
    from flask import Flask, g
    from backend.routes.email_routes import email_bp

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.secret_key = "test-secret"

    @app.before_request
    def _set_user_id():
        g.user_id = "teacher-alice"

    app.register_blueprint(email_bp)
    return app


# ──────────────────────────────────────────────────────────────────
# confirm_send reads per-teacher Supabase storage, not shared fallback
# ──────────────────────────────────────────────────────────────────


class TestConfirmSendPerTeacherStorage:
    def test_per_teacher_supabase_load_called_with_teacher_id(self, flask_app):
        """confirm_send MUST call storage.load(...) with the request's
        teacher_id, not fall through to the shared pending_send.json."""
        with patch("backend.storage.load") as mock_load, \
             patch("os.path.exists", return_value=False):
            mock_load.return_value = None  # No pending → 'No pending send' response

            client = flask_app.test_client()
            client.post("/api/confirm-send", json={})

        # storage.load called with teacher-alice (per-teacher), not with
        # 'local-dev' (which would indicate UnboundLocalError swallowed).
        assert mock_load.called, (
            "storage.load was never called — likely UnboundLocalError "
            "from `g` scope bug swallowed by broad except"
        )
        # First positional arg is the storage key, second is teacher_id
        first_call_kwargs = mock_load.call_args_list[0]
        args = first_call_kwargs.args
        # storage.load('pending_send', teacher_id) signature
        assert args[1] == "teacher-alice", (
            f"storage.load called with teacher_id={args[1]!r} "
            "(expected 'teacher-alice'). If 'local-dev', the route is "
            "falling back to default — likely UnboundLocalError on `g`."
        )

    def test_no_unbound_local_error_on_g_reference(self, flask_app):
        """Smoke test: confirm_send must not raise UnboundLocalError or
        NameError on the `g` reference. A 500 from the route handler with
        the expected error swallowed by handle_route_errors would be
        the failure mode."""
        with patch("backend.storage.load", return_value=None), \
             patch("os.path.exists", return_value=False):
            client = flask_app.test_client()
            resp = client.post("/api/confirm-send", json={})

        # If `g` scoping was broken, handle_route_errors would catch the
        # UnboundLocalError → 500 with generic error message.
        # Healthy path returns 200 (or expected business error like
        # 'No pending send').
        assert resp.status_code != 500, (
            f"Got 500 — likely UnboundLocalError on g. "
            f"Body: {resp.get_data(as_text=True)}"
        )

    def test_supabase_fallback_to_send_specific_keys_uses_teacher_id(self, flask_app):
        """When the generic 'pending_send' key is empty, confirm_send
        iterates send-specific keys (send_focus_comms, etc.). Each
        sub-key lookup must also use the per-teacher teacher_id."""
        from unittest.mock import MagicMock

        # First call returns None (pending_send empty), then return None
        # for all sub-keys to keep the test simple — we only care about
        # what teacher_id was passed.
        mock_load = MagicMock(return_value=None)

        with patch("backend.storage.load", mock_load), \
             patch("os.path.exists", return_value=False):
            client = flask_app.test_client()
            client.post("/api/confirm-send", json={})

        # All calls (initial + sub-key iterations) must pass teacher-alice
        for call in mock_load.call_args_list:
            args = call.args
            assert args[1] == "teacher-alice", (
                f"storage.load called with teacher_id={args[1]!r} on "
                f"key={args[0]!r}; per-teacher isolation broken."
            )
