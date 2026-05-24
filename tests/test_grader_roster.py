"""Characterization tests for roster loading (Wave 7 — grader decomposition).

Pins load_roster's CSV-path behavior BEFORE moving it into backend/services/grader_roster.py.
print-heavy → the diagnostic prints become _logger calls on extraction (RETURN VALUES
unchanged — what this pins). The Excel branch is preserved by the verified print→logger-only
diff. Imported via `assignment_grader` (re-export shim).
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from assignment_grader import load_roster


def _csv(content):
    f = tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w")
    f.write(content)
    f.close()
    return f.name


def test_load_roster_csv_forward_and_reversed_keys():
    path = _csv("FirstName,LastName,StudentID,Email,Period\n"
                "Alice,Smith,12345,alice@x.edu,3\nBob,Jones,67890,bob@x.edu,4\n")
    try:
        out = load_roster(path)
        # each student gets a forward "first last" and reversed "last first" key
        assert set(out.keys()) == {"alice smith", "smith alice", "bob jones", "jones bob"}
        assert out["alice smith"] == {
            "student_id": "12345", "student_name": "Alice Smith", "first_name": "Alice",
            "last_name": "Smith", "email": "alice@x.edu", "period": "3"}
        assert out["smith alice"] == out["alice smith"]  # reversed key → same record
    finally:
        os.unlink(path)


def test_load_roster_missing_file_returns_empty():
    assert load_roster("/nonexistent/dir/roster.csv") == {}


def test_load_roster_alt_column_names():
    # alternate header spellings still parse (First Name / Last Name / Student ID / Class)
    path = _csv("First Name,Last Name,Student ID,Email,Class\nCara,Lee,999,c@x.edu,5\n")
    try:
        out = load_roster(path)
        assert out["cara lee"]["student_id"] == "999"
        assert out["cara lee"]["period"] == "5"
    finally:
        os.unlink(path)
