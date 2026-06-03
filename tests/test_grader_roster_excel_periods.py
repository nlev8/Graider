"""PR7 hardening: real behavioral tests for grader_roster's Excel-parsing branch
and `build_roster_from_periods` (CSV period import) — paths the existing
`test_grader_roster.py` (CSV-only) never reaches.

Filesystem isolation (plan guard): `load_roster`'s Excel branch AND
`build_roster_from_periods` both read `~/.graider_data/periods`. A real such
directory exists on this machine and leaks live student records into the
result, making any un-isolated assertion non-deterministic. Every test here
monkeypatches `os.path.expanduser('~/.graider_data/periods')` to a tmp_path so
the period-supplement step is controlled (empty dir = no supplement, or a
fixture CSV we author). The real home directory is never touched.
"""
import json
import os
import sys

import openpyxl
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import backend.services.grader_roster as gr
from backend.services.grader_roster import load_roster, build_roster_from_periods


@pytest.fixture
def isolated_periods(tmp_path, monkeypatch):
    """Redirect ~/.graider_data/periods to an isolated, empty tmp dir.

    Returns the periods dir Path so a test can drop fixture CSVs into it.
    """
    periods = tmp_path / ".graider_data" / "periods"
    periods.mkdir(parents=True)
    real_expanduser = os.path.expanduser

    def fake_expanduser(path):
        if path == "~/.graider_data/periods":
            return str(periods)
        return real_expanduser(path)

    monkeypatch.setattr(gr.os.path, "expanduser", fake_expanduser)
    return periods


def _make_xlsx(tmp_path, rows, headers=None):
    headers = headers or ["Student", "Student ID", "Local ID", "Email", "Grade", "Team"]
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(headers)
    for r in rows:
        ws.append(r)
    path = tmp_path / "roster.xlsx"
    wb.save(str(path))
    return str(path)


# ── Excel branch of load_roster ───────────────────────────────────────────────


class TestLoadRosterExcel:
    def test_comma_name_forward_and_reversed_keys(self, tmp_path, isolated_periods):
        path = _make_xlsx(tmp_path, [
            ["Smith, Alice", "12345", "L1", "alice@x.edu", "7", "Period 3"],
        ])
        out = load_roster(path)
        assert out["alice smith"] == {
            "student_id": "12345", "student_name": "Alice Smith",
            "first_name": "Alice", "last_name": "Smith",
            "email": "alice@x.edu", "period": "Period 3"}
        # reversed key points at the SAME record object
        assert out["smith alice"] == out["alice smith"]

    def test_period_column_resolved_from_team_header(self, tmp_path, isolated_periods):
        # The header is "Team" — the period-column scan matches 'team'.
        path = _make_xlsx(tmp_path, [
            ["Jones, Bob", "678", "L2", "bob@x.edu", "8", "5th Hour"],
        ])
        out = load_roster(path)
        assert out["bob jones"]["period"] == "5th Hour"

    def test_hyphenated_last_name_adds_split_keys(self, tmp_path, isolated_periods):
        path = _make_xlsx(tmp_path, [
            ["Garcia-Lopez, Bob", "678", "L2", "bob@x.edu", "7", "Period 4"],
        ])
        out = load_roster(path)
        rec = out["bob garcia-lopez"]
        assert rec["last_name"] == "Garcia-Lopez"
        # hyphenated → also "Garcia" short key and space-separated variant
        assert out["bob garcia"] == rec
        assert out["bob garcia lopez"] == rec

    def test_semicolon_name_format(self, tmp_path, isolated_periods):
        path = _make_xlsx(tmp_path, [
            ["Doe; John", "111", "L9", "john@x.edu", "7", "Period 1"],
        ])
        out = load_roster(path)
        assert out["john doe"]["first_name"] == "John"
        assert out["john doe"]["last_name"] == "Doe"

    def test_apostrophe_name_adds_stripped_key(self, tmp_path, isolated_periods):
        path = _make_xlsx(tmp_path, [
            ["Chavarria, Andre'a", "5", "L5", "ac@x.edu", "7", "Period 2"],
        ])
        out = load_roster(path)
        # both the apostrophe and the stripped variant resolve to one record
        assert out["andre'a chavarria"]["student_id"] == "5"
        assert out["andrea chavarria"] == out["andre'a chavarria"]

    def test_missing_file_returns_empty(self):
        assert load_roster("/nonexistent/dir/roster.xlsx") == {}

    def test_empty_first_cell_row_skipped(self, tmp_path, isolated_periods):
        path = _make_xlsx(tmp_path, [
            [None, "000", "L0", "x@x.edu", "7", "Period 1"],
            ["Lee, Cara", "999", "L3", "cara@x.edu", "7", "Period 2"],
        ])
        out = load_roster(path)
        # only Cara's record survives; the None-name row is dropped
        assert out["cara lee"]["student_id"] == "999"
        # no spurious record from the skipped row
        assert all(rec["student_id"] != "000" for rec in out.values())


# ── build_roster_from_periods ─────────────────────────────────────────────────


class TestBuildRosterFromPeriods:
    def test_parses_csv_with_meta_period_name(self, isolated_periods):
        (isolated_periods / "Period_5.csv").write_text(
            'Student,Student ID,Local ID\n'
            '"Doe, John",111,L9\n'
            '"Roe; Jane",222,L8\n'
        )
        (isolated_periods / "Period_5.csv.meta.json").write_text(
            json.dumps({"period_name": "5th Block"}))
        out = build_roster_from_periods()
        assert out["john doe"] == {
            "student_id": "111", "student_name": "John Doe",
            "first_name": "John", "last_name": "Doe",
            "email": "L9@vcs2go.net", "period": "5th Block"}
        # email is derived from local_id as {local_id}@vcs2go.net
        assert out["jane roe"]["email"] == "L8@vcs2go.net"
        assert out["jane roe"]["period"] == "5th Block"
        # reversed key present
        assert out["roe jane"] == out["jane roe"]

    def test_period_name_from_filename_when_no_meta(self, isolated_periods):
        # No .meta.json → period name derived from filename ("_" → " ").
        (isolated_periods / "Block_2.csv").write_text(
            'Student,Student ID,Local ID\n"Kim, Sam",333,L7\n"Park, Lee",444,L6\n')
        out = build_roster_from_periods()
        assert out["sam kim"]["period"] == "Block 2"

    def test_no_periods_dir_returns_empty(self, tmp_path, monkeypatch):
        # Point expanduser at a path that does NOT exist → empty dict, no crash.
        missing = tmp_path / "does_not_exist" / "periods"
        real = os.path.expanduser

        def fake(path):
            if path == "~/.graider_data/periods":
                return str(missing)
            return real(path)

        monkeypatch.setattr(gr.os.path, "expanduser", fake)
        assert build_roster_from_periods() == {}

    def test_row_without_name_skipped(self, isolated_periods):
        (isolated_periods / "P1.csv").write_text(
            'Student,Student ID,Local ID\n'
            ',555,L5\n'              # no name → skipped
            '"Ng, Amy",666,L4\n'
            '"Ho, Ben",777,L3\n'
        )
        out = build_roster_from_periods()
        assert "amy ng" in out and "ben ho" in out
        assert all(rec["student_id"] != "555" for rec in out.values())


# ── Period-supplement path inside load_roster (Excel + period CSVs) ───────────


class TestLoadRosterPeriodSupplement:
    def test_period_csv_fills_blank_period_and_adds_new_student(
            self, tmp_path, isolated_periods):
        # Excel roster: Alice with a BLANK period (empty Team cell).
        path = _make_xlsx(tmp_path, [
            ["Smith, Alice", "100", "L1", "a@x.edu", "7", ""],
        ])
        # Period CSV: re-lists Alice (period gets filled) and adds new Bob.
        (isolated_periods / "Period_3.csv").write_text(
            'Student,Student ID,Local ID\n'
            '"Smith, Alice",100,L1\n'
            '"Jones, Bob",200,L2\n'
        )
        out = load_roster(path)
        # Alice's missing period is backfilled from the period CSV filename.
        assert out["alice smith"]["period"] == "Period 3"
        # Bob, absent from Excel, is added by the supplement step.
        assert out["bob jones"] == {
            "student_id": "200", "student_name": "Bob Jones",
            "first_name": "Bob", "last_name": "Jones",
            "email": "L2@vcs2go.net", "period": "Period 3"}


# ── CSV apostrophe / compound-last-name key variants ──────────────────────────


class TestLoadRosterCsvKeyVariants:
    def _csv(self, tmp_path, content):
        p = tmp_path / "roster.csv"
        p.write_text(content)
        return str(p)

    def test_apostrophe_stripped_key_added(self, tmp_path, isolated_periods):
        path = self._csv(tmp_path,
                         "FirstName,LastName,StudentID,Email,Period\n"
                         "Da'Juan,Liverpool,1,d@x.edu,3\n")
        out = load_roster(path)
        # apostrophe-stripped lookup key resolves to the same record
        assert out["dajuan liverpool"]["student_id"] == "1"
        assert out["da'juan liverpool"] == out["dajuan liverpool"]

    def test_compound_last_name_short_key_added(self, tmp_path, isolated_periods):
        path = self._csv(tmp_path,
                         "FirstName,LastName,StudentID,Email,Period\n"
                         "Maria,Wilkins Reels,2,m@x.edu,4\n")
        out = load_roster(path)
        # full key AND first-part-of-last-name short key both resolve
        assert out["maria wilkins reels"]["student_id"] == "2"
        assert out["maria wilkins"] == out["maria wilkins reels"]

    def test_student_column_semicolon_last_first(self, tmp_path, isolated_periods):
        # No FirstName/LastName columns — a single "Student" column in
        # "Last; First" format is split into name parts.
        path = self._csv(tmp_path,
                         "Student,Student ID,Email,Class\n"
                         "Jones; Bob,34,b@x.edu,4\n")
        out = load_roster(path)
        assert out["bob jones"] == {
            "student_id": "34", "student_name": "Bob Jones",
            "first_name": "Bob", "last_name": "Jones",
            "email": "b@x.edu", "period": "4"}
