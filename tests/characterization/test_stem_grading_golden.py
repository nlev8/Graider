"""Characterization tests for backend/services/stem_grading.py.

Feathers' rule: stabilize behavior before refactor. Phase 3 will split
stem_grading.py (or a larger monolith it belongs to); these tests PIN
the current observable output of the public entry points so the split
can prove it preserved behavior.

For each fixture in fixtures/stem_grading/, re-run the captured input
and assert the output matches byte-for-byte.

Legitimate responses when a fixture breaks:
  1. The split introduced a regression — fix the split.
  2. The split intentionally changed the output — re-capture the fixture
     in the same commit as the split, with a commit message explaining
     the behavior change.
  3. The captured output was always wrong (latent bug fixed by the
     split) — same as 2, with a celebratory commit message.

NOT legitimate: silently editing a fixture to make a failing test pass.

This module assumes the SymPy version pinned in requirements.txt. If
SymPy is bumped, parse-error strings may shift slightly and fixtures
should be re-captured deliberately (run tests/characterization/
capture_stem_fixtures.py manually).
"""
import json
import pathlib

import pytest

FIXTURES_DIR = pathlib.Path(__file__).parent / "fixtures" / "stem_grading"


def _load_fixtures():
    return [
        (p.stem, json.loads(p.read_text()))
        for p in sorted(FIXTURES_DIR.glob("*.json"))
    ]


@pytest.mark.parametrize("name,fixture", _load_fixtures())
def test_stem_grading_characterization(name, fixture):
    """Re-run the captured input through the pinned stem_grading public
    surface and assert the output matches the captured golden byte-for-byte."""
    from backend.services import stem_grading

    fn = getattr(stem_grading, fixture["input"]["fn"])
    kwargs = fixture["input"]["kwargs"]
    out = fn(**kwargs)
    assert out == fixture["output"], f"Characterization drift in fixture {name}"
