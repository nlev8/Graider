"""Tests for the structured-event emit() helper.

emit() writes structured fields as JSON-encoded text inside the logger
record's `message` attribute — the fields are nested inside the outer
log line's `message` field after the JsonFormatter runs.
"""
from __future__ import annotations

import json
import logging

import pytest

from backend.observability.events import emit


def _capture_records(caplog):
    return [r for r in caplog.records if r.name.startswith("backend.observability.events")]


def test_emit_info_level_serializes_event_and_fields(caplog):
    with caplog.at_level(logging.INFO, logger="backend.observability.events"):
        emit("llm.call.start", model="gpt-4", tokens=0)

    records = _capture_records(caplog)
    assert len(records) == 1
    payload = json.loads(records[0].getMessage())
    assert payload == {"event": "llm.call.start", "model": "gpt-4", "tokens": 0}


def test_emit_warning_level(caplog):
    with caplog.at_level(logging.WARNING, logger="backend.observability.events"):
        emit("llm.call.error", level="warning", model="gpt-4", error_kind="rate_limit")

    records = _capture_records(caplog)
    assert len(records) == 1
    assert records[0].levelno == logging.WARNING
    payload = json.loads(records[0].getMessage())
    assert payload["event"] == "llm.call.error"
    assert payload["error_kind"] == "rate_limit"
    assert "level" not in payload  # level controls the logger level, not the payload


def test_emit_default_level_is_info(caplog):
    with caplog.at_level(logging.DEBUG, logger="backend.observability.events"):
        emit("test.event")

    records = _capture_records(caplog)
    assert len(records) == 1
    assert records[0].levelno == logging.INFO


def test_emit_unknown_level_raises():
    with pytest.raises(ValueError):
        emit("test.event", level="bogus")
