"""Characterization tests for build_roster_from_periods (Wave 7 — grader decomposition).

Pins build_roster_from_periods behavior BEFORE appending it to backend/services/grader_roster.py.
File-I/O-only (no LLM): reads period CSVs from ~/.graider_data/periods/, derives lookup keys
(forward/reverse/apostrophe-stripped/compound/hyphenated) and email = {local_id}@vcs2go.net.
The two diagnostic prints become _logger calls on extraction (RETURN VALUES unchanged — what
these pin). HOME is monkeypatched to a tmp dir so the real expanduser path resolves into
isolated scratch space. Imported via `assignment_grader` (re-export shim).
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from assignment_grader import build_roster_from_periods


def _write_periods(tmp_path, filename, csv_text, meta=None):
    periods = tmp_path / ".graider_data" / "periods"
    periods.mkdir(parents=True, exist_ok=True)
    (periods / filename).write_text(csv_text, encoding="utf-8")
    if meta is not None:
        (periods / f"{filename}.meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return periods


def test_no_periods_dir_returns_empty(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert build_roster_from_periods() == {}


def test_forward_reverse_and_email_derivation(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    _write_periods(tmp_path, "Period_3.csv",
                   'Student,Student ID,Local ID\n"Smith, Alice",111,a111\n')

    roster = build_roster_from_periods()
    assert roster["alice smith"] == {
        "student_id": "111", "student_name": "Alice Smith", "first_name": "Alice",
        "last_name": "Smith", "email": "a111@vcs2go.net", "period": "Period 3",
    }
    assert roster["smith alice"] == roster["alice smith"]  # reverse key → same record


def test_compound_last_name_short_keys(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    _write_periods(tmp_path, "Period_5.csv",
                   'Student,Student ID,Local ID\n"Garcia Lopez, Bob",222,b222\n')

    roster = build_roster_from_periods()
    # full compound + reversed + first-part-of-last short keys all resolve to one record
    expected = {
        "student_id": "222", "student_name": "Bob Garcia Lopez", "first_name": "Bob",
        "last_name": "Garcia Lopez", "email": "b222@vcs2go.net", "period": "Period 5",
    }
    assert roster["bob garcia lopez"] == expected
    assert roster["garcia lopez bob"] == expected
    assert roster["bob garcia"] == expected      # compound short key
    assert roster["garcia bob"] == expected      # reversed short key


def test_meta_json_overrides_period_name(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    _write_periods(tmp_path, "Period_3.csv",
                   'Student,Student ID,Local ID\n"Smith, Alice",111,a111\n',
                   meta={"period_name": "3rd Period Honors"})

    roster = build_roster_from_periods()
    assert roster["alice smith"]["period"] == "3rd Period Honors"


def test_blank_local_id_yields_empty_email(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    _write_periods(tmp_path, "Period_1.csv",
                   'Student,Student ID,Local ID\n"Jones, Cara",333,\n')

    roster = build_roster_from_periods()
    assert roster["cara jones"]["email"] == ""
