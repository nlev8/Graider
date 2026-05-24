"""Characterization tests for writing-profile persistence (Wave 7 — grader decomposition).

Pins update_writing_profile / get_writing_profile behavior BEFORE moving them into
backend/services/writing_profile.py. These are file-I/O-only helpers (no LLM) that maintain
a running-average writing profile per student under ~/.graider_data/student_history/. The one
diagnostic print in update_writing_profile becomes a _logger call on extraction (RETURN VALUES +
written JSON unchanged — what these tests pin). HOME is monkeypatched to a tmp dir so the real
expanduser path resolves into isolated scratch space. Imported via `assignment_grader`
(re-export shim) so the tests stay valid through extraction.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from assignment_grader import get_writing_profile, update_writing_profile

# A fixed style dict → fully deterministic golden (no analyze_writing_style randomness).
_STYLE_1 = {
    "avg_word_length": 4.5,
    "avg_sentence_length": 12.0,
    "complexity_score": 30.0,
    "academic_word_count": 3,
    "uses_contractions": True,
}
_STYLE_2 = {
    "avg_word_length": 5.5,
    "avg_sentence_length": 8.0,
    "complexity_score": 50.0,
    "academic_word_count": 7,
    "uses_contractions": False,
}


def test_first_submission_seeds_profile_directly(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    update_writing_profile("stu-1", _STYLE_1, student_name="Alice Smith")

    history_file = tmp_path / ".graider_data" / "student_history" / "stu-1.json"
    assert history_file.exists()
    history = json.loads(history_file.read_text())
    assert history["student_id"] == "stu-1"
    assert history["name"] == "Alice Smith"
    assert history["assignments"] == []
    assert history["writing_profile"] == {
        "avg_word_length": 4.5,
        "avg_sentence_length": 12.0,
        "avg_complexity_score": 30.0,
        "avg_academic_words": 3,
        "uses_contractions": True,
        "sample_count": 1,
    }
    assert "last_updated" in history  # timestamp present (value is non-deterministic)


def test_second_submission_running_average(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    update_writing_profile("stu-2", _STYLE_1)
    update_writing_profile("stu-2", _STYLE_2)

    profile = get_writing_profile("stu-2")
    assert profile == {
        "avg_word_length": 5.0,        # (4.5 + 5.5) / 2
        "avg_sentence_length": 10.0,   # (12.0 + 8.0) / 2
        "avg_complexity_score": 40.0,  # (30.0 + 50.0) / 2
        "avg_academic_words": 5.0,     # (3 + 7) / 2
        "uses_contractions": True,     # True OR False → True (sticky)
        "sample_count": 2,
    }


def test_get_writing_profile_none_when_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert get_writing_profile("never-seen") is None
    assert get_writing_profile(None) is None


def test_update_noops_on_empty_style_or_missing_id(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    update_writing_profile("stu-3", {})        # empty style → no-op
    update_writing_profile(None, _STYLE_1)     # no id → no-op
    hist_dir = tmp_path / ".graider_data" / "student_history"
    assert not hist_dir.exists()               # nothing written
