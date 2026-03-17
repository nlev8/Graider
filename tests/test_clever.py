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


# ---------------------------------------------------------------------------
# _safe_teacher_id — colon sanitization for filenames
# ---------------------------------------------------------------------------


class TestSafeTeacherId:
    def test_sanitizes_colon(self):
        assert clever._safe_teacher_id("clever:abc123") == "clever_abc123"

    def test_no_change_without_colon(self):
        assert clever._safe_teacher_id("local-dev") == "local-dev"

    def test_multiple_colons(self):
        assert clever._safe_teacher_id("a:b:c") == "a_b_c"


# ---------------------------------------------------------------------------
# persist_roster_as_csv — clever: prefix produces valid filenames
# ---------------------------------------------------------------------------


class TestPersistRosterCleverPrefix:
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
        import shutil
        if os.path.exists(clever.ROSTERS_DIR):
            shutil.rmtree(clever.ROSTERS_DIR)
        os.makedirs(clever.ROSTERS_DIR, exist_ok=True)
        yield

    def test_clever_prefix_creates_valid_filename(self):
        """clever:abc123 should produce clever_abc123 in filename, not clever:abc123."""
        students = self._make_students(["s1"])
        path = clever.persist_roster_as_csv(students, teacher_id="clever:abc123")
        assert os.path.exists(path)
        assert "clever_abc123" in os.path.basename(path)
        assert ":" not in os.path.basename(path)


# ---------------------------------------------------------------------------
# extract_parent_contacts
# ---------------------------------------------------------------------------


class TestExtractParentContacts:
    def test_basic_mapping(self):
        students = [{"data": {"id": "s1"}}, {"data": {"id": "s2"}}]
        contacts = [
            {
                "data": {
                    "email": "parent@test.com",
                    "phone": "555-1234",
                    "student_relationships": [{"student": "s1"}],
                }
            }
        ]
        result = clever.extract_parent_contacts(contacts, students)
        assert "s1" in result
        assert "parent@test.com" in result["s1"]["parent_emails"]
        assert "555-1234" in result["s1"]["parent_phones"]
        assert "s2" not in result

    def test_deduplicates_contacts(self):
        students = [{"data": {"id": "s1"}}]
        contacts = [
            {
                "data": {
                    "email": "same@test.com",
                    "phone": "",
                    "student_relationships": [{"student": "s1"}],
                }
            },
            {
                "data": {
                    "email": "same@test.com",
                    "phone": "",
                    "student_relationships": [{"student": "s1"}],
                }
            },
        ]
        result = clever.extract_parent_contacts(contacts, students)
        assert len(result["s1"]["parent_emails"]) == 1

    def test_filters_unknown_students(self):
        students = [{"data": {"id": "s1"}}]
        contacts = [
            {
                "data": {
                    "email": "parent@test.com",
                    "phone": "",
                    "student_relationships": [{"student": "unknown_id"}],
                }
            }
        ]
        result = clever.extract_parent_contacts(contacts, students)
        assert len(result) == 0


# ---------------------------------------------------------------------------
# persist_parent_contacts
# ---------------------------------------------------------------------------


class TestPersistParentContacts:
    @pytest.fixture(autouse=True)
    def _clean_dirs(self):
        contacts_file = os.path.join(clever.GRAIDER_DATA_DIR, "parent_contacts.json")
        if os.path.exists(contacts_file):
            os.remove(contacts_file)
        yield

    def test_creates_contacts_file(self):
        contact_map = {"s1": {"parent_emails": ["p@test.com"], "parent_phones": ["555"]}}
        clever.persist_parent_contacts(contact_map, "test")
        contacts_file = os.path.join(clever.GRAIDER_DATA_DIR, "parent_contacts.json")
        assert os.path.exists(contacts_file)
        with open(contacts_file) as f:
            data = json.load(f)
        assert "s1" in data

    def test_merges_with_existing(self):
        contacts_file = os.path.join(clever.GRAIDER_DATA_DIR, "parent_contacts.json")
        os.makedirs(os.path.dirname(contacts_file), exist_ok=True)
        with open(contacts_file, "w") as f:
            json.dump({"s1": {"parent_emails": ["existing@test.com"], "parent_phones": []}}, f)

        contact_map = {"s1": {"parent_emails": ["new@test.com"], "parent_phones": ["555"]}}
        clever.persist_parent_contacts(contact_map, "test")

        with open(contacts_file) as f:
            data = json.load(f)
        assert "existing@test.com" in data["s1"]["parent_emails"]
        assert "new@test.com" in data["s1"]["parent_emails"]
        assert "555" in data["s1"]["parent_phones"]


# ---------------------------------------------------------------------------
# delete_clever_data — full data deletion
# ---------------------------------------------------------------------------


class TestDeleteCleverData:
    def _make_students(self, ids):
        return [
            {
                "data": {
                    "id": sid,
                    "name": {"first": f"F{sid}", "last": f"L{sid}"},
                    "email": f"{sid}@school.edu",
                    "roles": {"student": {"grade": "8", "iep_status": "", "ell_status": ""}},
                }
            }
            for sid in ids
        ]

    @pytest.fixture(autouse=True)
    def _clean_dirs(self):
        import shutil
        for d in [clever.ROSTERS_DIR, clever.PERIODS_DIR]:
            if os.path.exists(d):
                shutil.rmtree(d)
            os.makedirs(d, exist_ok=True)
        # Clean contacts, accommodations, ELL
        for f in [
            os.path.join(clever.GRAIDER_DATA_DIR, "parent_contacts.json"),
            os.path.join(clever.GRAIDER_DATA_DIR, "ell_students.json"),
        ]:
            if os.path.exists(f):
                os.remove(f)
        accomm_dir = os.path.join(clever.GRAIDER_DATA_DIR, "accommodations")
        if os.path.exists(accomm_dir):
            shutil.rmtree(accomm_dir)
        os.makedirs(accomm_dir, exist_ok=True)
        yield

    def test_deletes_roster_files(self):
        clever.persist_roster_as_csv(self._make_students(["a", "b"]), "clever:t1")
        import glob as globmod
        safe_id = clever._safe_teacher_id("clever:t1")
        files_before = globmod.glob(os.path.join(clever.ROSTERS_DIR, f"clever_roster_{safe_id}*"))
        assert len(files_before) >= 2  # CSV + metadata

        result = clever.delete_clever_data("clever:t1")
        files_after = globmod.glob(os.path.join(clever.ROSTERS_DIR, f"clever_roster_{safe_id}*"))
        assert len(files_after) == 0
        assert result["roster_files"] >= 2

    def test_deletes_period_files(self):
        sections = [
            {
                "data": {
                    "id": "sec1", "name": "Math", "subject": "Math",
                    "grade": "7", "teachers": ["t1"], "students": ["s1"],
                    "period": "1", "term_id": "t",
                }
            }
        ]
        clever.persist_sections_as_periods(sections, "clever:t1")
        result = clever.delete_clever_data("clever:t1")
        assert result["period_files"] >= 2  # JSON + metadata

    def test_removes_only_clever_students_from_contacts(self):
        """Deletion should only remove students found in the Clever roster, not all contacts."""
        # Create roster with students a, b
        clever.persist_roster_as_csv(self._make_students(["a", "b"]), "clever:t1")
        # Create contacts for a (Clever), b (Clever), and manual_student (manual)
        contacts_file = os.path.join(clever.GRAIDER_DATA_DIR, "parent_contacts.json")
        with open(contacts_file, "w") as f:
            json.dump({
                "a": {"parent_emails": ["pa@t.com"], "parent_phones": []},
                "b": {"parent_emails": ["pb@t.com"], "parent_phones": []},
                "manual_student": {"parent_emails": ["pm@t.com"], "parent_phones": []},
            }, f)

        result = clever.delete_clever_data("clever:t1")
        assert result["contacts_removed"] == 2  # a and b removed
        with open(contacts_file) as f:
            remaining = json.load(f)
        assert "manual_student" in remaining  # manual entry preserved
        assert "a" not in remaining
        assert "b" not in remaining

    def test_removes_only_clever_students_from_accommodations(self):
        """Deletion should only remove Clever-sourced students from accommodations."""
        clever.persist_roster_as_csv(self._make_students(["a"]), "clever:t1")
        accomm_file = os.path.join(clever.GRAIDER_DATA_DIR, "accommodations", "student_accommodations.json")
        with open(accomm_file, "w") as f:
            json.dump({
                "a": {"presets": ["simplified_language"]},
                "manual_student": {"presets": ["extra_encouragement"]},
            }, f)

        result = clever.delete_clever_data("clever:t1")
        assert result["accommodations_removed"] == 1
        with open(accomm_file) as f:
            remaining = json.load(f)
        assert "manual_student" in remaining
        assert "a" not in remaining

    def test_removes_ell_entries(self):
        """Deletion should remove ELL entries for Clever students only."""
        clever.persist_roster_as_csv(self._make_students(["a"]), "clever:t1")
        ell_file = os.path.join(clever.GRAIDER_DATA_DIR, "ell_students.json")
        with open(ell_file, "w") as f:
            json.dump({
                "a": {"language": "Spanish"},
                "manual_student": {"language": "French"},
            }, f)

        result = clever.delete_clever_data("clever:t1")
        assert result["ell_removed"] == 1
        with open(ell_file) as f:
            remaining = json.load(f)
        assert "manual_student" in remaining
        assert "a" not in remaining

    def test_handles_empty_state(self):
        """Deletion on clean state should not error."""
        result = clever.delete_clever_data("clever:t1")
        assert result["roster_files"] == 0
        assert result["period_files"] == 0
        assert result["contacts_removed"] == 0
        assert result["accommodations_removed"] == 0
        assert result["ell_removed"] == 0

    def test_handles_corrupt_json_files(self):
        """Corrupt JSON should not crash deletion."""
        clever.persist_roster_as_csv(self._make_students(["a"]), "clever:t1")
        # Write corrupt contacts
        contacts_file = os.path.join(clever.GRAIDER_DATA_DIR, "parent_contacts.json")
        with open(contacts_file, "w") as f:
            f.write("{invalid json")
        # Should not raise
        result = clever.delete_clever_data("clever:t1")
        assert result["contacts_removed"] == 0  # couldn't parse, but didn't crash

    def test_collects_ids_from_period_files(self):
        """Student IDs should be collected from period files too."""
        # Create period with student "p1" (no roster file for this teacher)
        sections = [
            {
                "data": {
                    "id": "sec1", "name": "Math", "subject": "Math",
                    "grade": "7", "teachers": ["t1"], "students": ["p1"],
                    "period": "1", "term_id": "t",
                }
            }
        ]
        clever.persist_sections_as_periods(sections, "clever:t1")
        # Add contacts for p1
        contacts_file = os.path.join(clever.GRAIDER_DATA_DIR, "parent_contacts.json")
        with open(contacts_file, "w") as f:
            json.dump({"p1": {"parent_emails": ["parent@t.com"], "parent_phones": []}}, f)

        result = clever.delete_clever_data("clever:t1")
        assert result["contacts_removed"] == 1
