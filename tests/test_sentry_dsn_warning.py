"""init_sentry must make a missing SENTRY_DSN LOUD outside development.

Rubric dimension 7 (Debugging/Observability) level 8: "error tracking active in
prod". A deployed environment with no DSN means error tracking is silently off —
that absence should warn, not whisper at info. In explicit development it stays
quiet.
"""
import logging

import backend.observability.sentry as sentry_mod


def _reset():
    sentry_mod._initialized = False


def test_missing_dsn_outside_development_warns(monkeypatch, caplog):
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    monkeypatch.delenv("FLASK_ENV", raising=False)  # not development -> deployed-ish
    _reset()
    with caplog.at_level(logging.INFO, logger="backend.observability.sentry"):
        sentry_mod.init_sentry()
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert warnings, "missing DSN outside development should emit a WARNING"
    assert any("SENTRY_DSN" in r.message for r in warnings)


def test_missing_dsn_in_development_is_quiet(monkeypatch, caplog):
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    monkeypatch.setenv("FLASK_ENV", "development")
    _reset()
    with caplog.at_level(logging.INFO, logger="backend.observability.sentry"):
        sentry_mod.init_sentry()
    assert not [r for r in caplog.records if r.levelno == logging.WARNING], \
        "explicit development should not warn about a missing DSN"
    _reset()  # leave the module flag clean for other tests
