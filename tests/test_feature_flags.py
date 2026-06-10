"""Unit tests for backend/feature_flags.py (hardening sprint Wave 1, PR3).

Contract (plan doc docs/superpowers/plans/2026-06-09-hardening-sprint-to-85.md PR3):
- flag_enabled(name, default=False) reads env var FLAG_<NAME> (name upper-cased).
- Truthy values: 1/true/yes/on (case-insensitive).
- Falsy values: 0/false/no/off (case-insensitive).
- Unset → the `default` parameter (which itself defaults to False).
- Unrecognized value → log a warning, fall back to the default.
"""
import logging

import pytest

from backend.feature_flags import flag_enabled


ENV_VAR = "FLAG_TEST_FLAG"


class TestEnvVarNaming:
    def test_name_is_uppercased_and_prefixed(self, monkeypatch):
        monkeypatch.setenv("FLAG_CLEVER_ROSTER_SYNC", "true")
        assert flag_enabled("clever_roster_sync") is True

    def test_already_uppercase_name(self, monkeypatch):
        monkeypatch.setenv("FLAG_CLEVER_ROSTER_SYNC", "true")
        assert flag_enabled("CLEVER_ROSTER_SYNC") is True


class TestTruthyValues:
    @pytest.mark.parametrize("value", [
        "1", "true", "yes", "on", "TRUE", "Yes", "ON", "True",
    ])
    def test_truthy(self, monkeypatch, value):
        monkeypatch.setenv(ENV_VAR, value)
        assert flag_enabled("test_flag") is True

    @pytest.mark.parametrize("value", ["1", "true"])
    def test_truthy_overrides_default_false(self, monkeypatch, value):
        monkeypatch.setenv(ENV_VAR, value)
        assert flag_enabled("test_flag", default=False) is True


class TestFalsyValues:
    @pytest.mark.parametrize("value", [
        "0", "false", "no", "off", "FALSE", "No", "OFF", "False",
    ])
    def test_falsy(self, monkeypatch, value):
        monkeypatch.setenv(ENV_VAR, value)
        assert flag_enabled("test_flag", default=True) is False

    @pytest.mark.parametrize("value", ["0", "false"])
    def test_falsy_overrides_default_true(self, monkeypatch, value):
        monkeypatch.setenv(ENV_VAR, value)
        assert flag_enabled("test_flag", default=True) is False


class TestUnset:
    def test_unset_returns_default_false(self, monkeypatch):
        monkeypatch.delenv(ENV_VAR, raising=False)
        assert flag_enabled("test_flag") is False

    def test_unset_returns_explicit_default_true(self, monkeypatch):
        monkeypatch.delenv(ENV_VAR, raising=False)
        assert flag_enabled("test_flag", default=True) is True

    def test_unset_no_warning_logged(self, monkeypatch, caplog):
        monkeypatch.delenv(ENV_VAR, raising=False)
        with caplog.at_level(logging.WARNING, logger="backend.feature_flags"):
            flag_enabled("test_flag")
        assert caplog.records == []


class TestUnrecognizedValues:
    @pytest.mark.parametrize("value", ["maybe", "2", "enabled", "truthy"])
    def test_unrecognized_falls_back_to_default_false(
            self, monkeypatch, caplog, value):
        monkeypatch.setenv(ENV_VAR, value)
        with caplog.at_level(logging.WARNING, logger="backend.feature_flags"):
            assert flag_enabled("test_flag", default=False) is False
        assert any(ENV_VAR in r.getMessage() for r in caplog.records), (
            "expected a warning naming the env var")

    def test_unrecognized_falls_back_to_default_true(self, monkeypatch, caplog):
        monkeypatch.setenv(ENV_VAR, "maybe")
        with caplog.at_level(logging.WARNING, logger="backend.feature_flags"):
            assert flag_enabled("test_flag", default=True) is True
        assert len(caplog.records) == 1
        assert caplog.records[0].levelno == logging.WARNING

    def test_whitespace_around_recognized_value_is_tolerated(self, monkeypatch):
        monkeypatch.setenv(ENV_VAR, "  true  ")
        assert flag_enabled("test_flag") is True

    def test_empty_string_treated_as_unset_no_warning(self, monkeypatch, caplog):
        # `FLAG_X=` in a .env file yields "" — treat as unset, not a typo.
        monkeypatch.setenv(ENV_VAR, "")
        with caplog.at_level(logging.WARNING, logger="backend.feature_flags"):
            assert flag_enabled("test_flag", default=True) is True
            assert flag_enabled("test_flag", default=False) is False
        assert caplog.records == []
