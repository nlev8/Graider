"""Characterization tests for _try_parse_json_fallback (Wave 7 Slice 5 — grader decomposition).

Pins the LLM-JSON repair behavior BEFORE moving _try_parse_json_fallback into
backend/services/grader_json.py. Pure (json + re — no LLM / I/O / Flask). Used as
the fallback parser for Claude/Gemini/OpenAI-text responses. Imported via
`assignment_grader` (re-export shim).
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from assignment_grader import _try_parse_json_fallback as f


def test_valid_json_direct_parse():
    assert f('{"score": 8, "ok": true}') == {"score": 8, "ok": True}


def test_empty_or_none_returns_none():
    assert f("") is None
    assert f(None) is None


def test_strips_markdown_code_fence_with_lang():
    assert f('```json\n{"a": 1}\n```') == {"a": 1}


def test_strips_markdown_code_fence_no_lang():
    assert f('```\n{"b": 2}\n```') == {"b": 2}


def test_repairs_missing_comma_between_fields():
    assert f('{"a": 1\n"b": 2}') == {"a": 1, "b": 2}


def test_removes_parenthetical_after_quote():
    assert f('{"reason": "good" (great)}') == {"reason": "good"}


def test_unrecoverable_returns_none():
    assert f('this is not json at all {{{') is None
