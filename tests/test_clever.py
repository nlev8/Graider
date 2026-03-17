"""
Tests for Clever SSO + Secure Sync integration.
Covers: clever.py helper functions and persist/archive logic.
Zero network calls — all Clever API responses are mocked.
"""
import csv
import json
import os
import tempfile

import pytest

# Patch data dirs before importing clever module
_tmpdir = tempfile.mkdtemp()

import backend.clever as clever

# Override data directories to use temp dir
clever.GRAIDER_DATA_DIR = _tmpdir
clever.ROSTERS_DIR = os.path.join(_tmpdir, "rosters")
clever.PERIODS_DIR = os.path.join(_tmpdir, "periods")


# ---------------------------------------------------------------------------
# get_clever_config
# ---------------------------------------------------------------------------


class TestGetCleverConfig:
    def test_returns_none_when_missing(self, monkeypatch):
        monkeypatch.delenv("CLEVER_CLIENT_ID", raising=False)
        monkeypatch.delenv("CLEVER_CLIENT_SECRET", raising=False)
        monkeypatch.delenv("CLEVER_REDIRECT_URI", raising=False)
        assert clever.get_clever_config() is None

    def test_returns_config_when_set(self, monkeypatch):
        monkeypatch.setenv("CLEVER_CLIENT_ID", "id123")
        monkeypatch.setenv("CLEVER_CLIENT_SECRET", "secret456")
        monkeypatch.setenv("CLEVER_REDIRECT_URI", "http://localhost/callback")
        cfg = clever.get_clever_config()
        assert cfg is not None
        assert cfg["client_id"] == "id123"
        assert cfg["client_secret"] == "secret456"
        assert cfg["redirect_uri"] == "http://localhost/callback"

    def test_returns_none_when_partial(self, monkeypatch):
        monkeypatch.setenv("CLEVER_CLIENT_ID", "id123")
        monkeypatch.delenv("CLEVER_CLIENT_SECRET", raising=False)
        monkeypatch.delenv("CLEVER_REDIRECT_URI", raising=False)
        assert clever.get_clever_config() is None


# ---------------------------------------------------------------------------
# get_authorize_url
# ---------------------------------------------------------------------------


class TestGetAuthorizeUrl:
    def test_builds_url_with_state(self, monkeypatch):
        monkeypatch.setenv("CLEVER_CLIENT_ID", "id123")
        monkeypatch.setenv("CLEVER_CLIENT_SECRET", "secret456")
        monkeypatch.setenv("CLEVER_REDIRECT_URI", "http://localhost/callback")
        url = clever.get_authorize_url(state="abc")
        assert "clever.com/oauth/authorize" in url
        assert "client_id=id123" in url
        assert "state=abc" in url
        assert "response_type=code" in url

    def test_returns_none_without_config(self, monkeypatch):
        monkeypatch.delenv("CLEVER_CLIENT_ID", raising=False)
        assert clever.get_authorize_url() is None


# ---------------------------------------------------------------------------
# _next_page_url
# ---------------------------------------------------------------------------


class TestNextPageUrl:
    def test_extracts_next_link(self):
        body = {"links": [{"rel": "next", "uri": "/v3.0/users?page=2"}]}
        assert clever._next_page_url(body) == f"{clever.CLEVER_API_BASE}/v3.0/users?page=2"

    def test_returns_none_without_next(self):
        body = {"links": [{"rel": "self", "uri": "/v3.0/users"}]}
        assert clever._next_page_url(body) is None

    def test_returns_none_empty_links(self):
        assert clever._next_page_url({}) is None
        assert clever._next_page_url({"links": []}) is None

    def test_full_url_passthrough(self):
        body = {"links": [{"rel": "next", "uri": "https://api.clever.com/v3.0/users?page=3"}]}
        assert clever._next_page_url(body) == "https://api.clever.com/v3.0/users?page=3"


# ---------------------------------------------------------------------------
# extract_student_accommodations
# ---------------------------------------------------------------------------


class TestExtractStudentAccommodations:
    def _make_student(self, sid, iep="", ell="", lang="", first="Test", last="Student"):
        return {
            "data": {
                "id": sid,
                "name": {"first": first, "last": last},
                "roles": {"student": {"iep_status": iep, "ell_status": ell, "home_language": lang}},
            }
        }

    def test_iep_student(self):
        students = [self._make_student("s1", iep="Y")]
        result = clever.extract_student_accommodations(students)
        assert "s1" in result
        assert result["s1"]["iep_status"] is True
        assert "simplified_language" in result["s1"]["suggested_presets"]

    def test_ell_student(self):
        students = [self._make_student("s2", ell="active", lang="Spanish")]
        result = clever.extract_student_accommodations(students)
        assert "s2" in result
        assert result["s2"]["ell_status"] is True
        assert result["s2"]["home_language"] == "Spanish"
        assert "ell_support" in result["s2"]["suggested_presets"]

    def test_both_iep_and_ell(self):
        students = [self._make_student("s3", iep="true", ell="yes", lang="Vietnamese")]
        result = clever.extract_student_accommodations(students)
        assert "s3" in result
        assert result["s3"]["iep_status"] is True
        assert result["s3"]["ell_status"] is True
        presets = result["s3"]["suggested_presets"]
        assert "simplified_language" in presets
        assert "ell_support" in presets

    def test_no_flags_excluded(self):
        students = [self._make_student("s4", iep="", ell="")]
        result = clever.extract_student_accommodations(students)
        assert "s4" not in result

    def test_unwrapped_data(self):
        """Students without 'data' wrapper are handled."""
        student = {
            "id": "s5",
            "name": {"first": "A", "last": "B"},
            "roles": {"student": {"iep_status": "Y"}},
        }
        result = clever.extract_student_accommodations([student])
        assert "s5" in result


# ---------------------------------------------------------------------------
# map_sections_to_periods
# ---------------------------------------------------------------------------


class TestMapSectionsToPeriods:
    def test_basic_mapping(self):
        sections = [
            {
                "data": {
                    "id": "sec1",
                    "name": "Math 101",
                    "subject": "Math",
                    "grade": "7",
                    "teachers": ["t1"],
                    "students": ["s1", "s2"],
                    "period": "3",
                    "term_id": "term1",
                }
            }
        ]
        result = clever.map_sections_to_periods(sections)
        assert len(result) == 1
        p = result[0]
        assert p["clever_section_id"] == "sec1"
        assert p["name"] == "Math 101"
        assert p["student_clever_ids"] == ["s1", "s2"]

    def test_empty_sections(self):
        assert clever.map_sections_to_periods([]) == []


# ---------------------------------------------------------------------------
# persist_roster_as_csv — initial sync, archive, restore, overrides, UTF-8
# ---------------------------------------------------------------------------


class TestPersistRosterAsCsv:
    def _make_students(self, ids):
        return [
            {
                "data": {
                    "id": sid,
                    "name": {"first": f"First{sid}", "last": f"Last{sid}"},
                    "email": f"{sid}@school.edu",
                    "roles": {"student": {"grade": "8", "iep_status": "", "ell_status": ""}},
                }
            }
            for sid in ids
        ]

    @pytest.fixture(autouse=True)
    def _clean_dirs(self):
        """Reset rosters dir before each test."""
        import shutil
        if os.path.exists(clever.ROSTERS_DIR):
            shutil.rmtree(clever.ROSTERS_DIR)
        os.makedirs(clever.ROSTERS_DIR, exist_ok=True)
        yield

    def test_initial_sync(self):
        students = self._make_students(["a", "b", "c"])
        path = clever.persist_roster_as_csv(students, teacher_id="test")
        assert os.path.exists(path)

        with open(path, "r") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 3
        ids = {r["student_id"] for r in rows}
        assert ids == {"a", "b", "c"}

    def test_archive_removed_students(self):
        # First sync with a, b, c
        clever.persist_roster_as_csv(self._make_students(["a", "b", "c"]), teacher_id="test")
        # Second sync removes c
        clever.persist_roster_as_csv(self._make_students(["a", "b"]), teacher_id="test")

        archive_path = os.path.join(clever.ROSTERS_DIR, "clever_roster_test_archived.json")
        assert os.path.exists(archive_path)
        with open(archive_path) as f:
            archived = json.load(f)
        assert "c" in archived
        assert archived["c"]["reason"] == "removed_from_clever"

    def test_restore_archived_student(self):
        # Sync a, b, c → remove c → re-add c
        clever.persist_roster_as_csv(self._make_students(["a", "b", "c"]), teacher_id="test")
        clever.persist_roster_as_csv(self._make_students(["a", "b"]), teacher_id="test")
        clever.persist_roster_as_csv(self._make_students(["a", "b", "c"]), teacher_id="test")

        archive_path = os.path.join(clever.ROSTERS_DIR, "clever_roster_test_archived.json")
        # Archive should be cleaned up since no one is archived
        assert not os.path.exists(archive_path)

    def test_manual_overrides_preserved(self):
        overrides_path = os.path.join(clever.ROSTERS_DIR, "clever_roster_test_overrides.json")
        with open(overrides_path, "w") as f:
            json.dump({"a": {"first_name": "CustomFirst", "last_name": "CustomLast"}}, f)

        students = self._make_students(["a", "b"])
        path = clever.persist_roster_as_csv(students, teacher_id="test")

        with open(path, "r") as f:
            reader = csv.DictReader(f)
            rows = {r["student_id"]: r for r in reader}

        assert rows["a"]["first_name"] == "CustomFirst"
        assert rows["a"]["last_name"] == "CustomLast"
        # b should be unaffected
        assert rows["b"]["first_name"] == "Firstb"

    def test_utf8_names(self):
        students = [
            {
                "data": {
                    "id": "u1",
                    "name": {"first": "María", "last": "González"},
                    "email": "maria@school.edu",
                    "roles": {"student": {"grade": "7"}},
                }
            }
        ]
        path = clever.persist_roster_as_csv(students, teacher_id="test")
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            row = next(reader)
        assert row["first_name"] == "María"
        assert row["last_name"] == "González"

    def test_metadata_file_created(self):
        students = self._make_students(["a"])
        path = clever.persist_roster_as_csv(students, teacher_id="test")
        meta_path = path + ".meta.json"
        assert os.path.exists(meta_path)
        with open(meta_path) as f:
            meta = json.load(f)
        assert meta["source"] == "clever"
        assert meta["row_count"] == 1


# ---------------------------------------------------------------------------
# persist_sections_as_periods
# ---------------------------------------------------------------------------


class TestPersistSectionsAsPeriods:
    @pytest.fixture(autouse=True)
    def _clean_dirs(self):
        import shutil
        if os.path.exists(clever.PERIODS_DIR):
            shutil.rmtree(clever.PERIODS_DIR)
        os.makedirs(clever.PERIODS_DIR, exist_ok=True)
        yield

    def test_creates_period_files(self):
        sections = [
            {
                "data": {
                    "id": "sec1",
                    "name": "English 9",
                    "subject": "English",
                    "grade": "9",
                    "teachers": ["t1"],
                    "students": ["s1", "s2"],
                    "period": "2",
                    "term_id": "term1",
                }
            }
        ]
        result = clever.persist_sections_as_periods(sections, teacher_id="test")
        assert len(result) == 1

        filepath = os.path.join(clever.PERIODS_DIR, "clever_sec1.json")
        assert os.path.exists(filepath)
        with open(filepath) as f:
            data = json.load(f)
        assert data["name"] == "English 9"
        assert data["source"] == "clever"
        assert data["students"] == ["s1", "s2"]

        # Metadata file
        meta_path = filepath + ".meta.json"
        assert os.path.exists(meta_path)
