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
from unittest.mock import patch

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
        contacts_file = os.path.join(clever.GRAIDER_DATA_DIR, "contacts", "parent_contacts_test.json")
        if os.path.exists(contacts_file):
            os.remove(contacts_file)
        yield

    def test_creates_contacts_file(self):
        contact_map = {"s1": {"parent_emails": ["p@test.com"], "parent_phones": ["555"]}}
        clever.persist_parent_contacts(contact_map, "test")
        contacts_file = os.path.join(clever.GRAIDER_DATA_DIR, "contacts", "parent_contacts_test.json")
        assert os.path.exists(contacts_file)
        with open(contacts_file) as f:
            data = json.load(f)
        assert "s1" in data

    def test_merges_with_existing(self):
        contacts_file = os.path.join(clever.GRAIDER_DATA_DIR, "contacts", "parent_contacts_test.json")
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
    """Tests for delete_clever_data which delegates to roster_sync.delete_roster_data.

    delete_roster_data returns: {"classes": int, "students": int, "enrollments": int, "roster_files": int}
    It handles Supabase record deletion and local roster CSV file cleanup.
    """

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
        # Mock Supabase (test teacher_id "clever:t1" is not a valid UUID) and
        # redirect roster_sync's data_dir to the test's temp dir so file
        # deletion finds the right paths
        _original_expanduser = os.path.expanduser

        def _test_expanduser(path):
            if path == "~/.graider_data":
                return clever.GRAIDER_DATA_DIR
            return _original_expanduser(path)

        with patch("backend.supabase_client.get_supabase", return_value=None), \
             patch("os.path.expanduser", side_effect=_test_expanduser):
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

    def test_handles_empty_state(self):
        """Deletion on clean state should not error."""
        result = clever.delete_clever_data("clever:t1")
        assert result["roster_files"] == 0
        assert result["classes"] == 0
        assert result["students"] == 0
        assert result["enrollments"] == 0

    def test_returns_expected_keys(self):
        """Return dict has the four keys from delete_roster_data."""
        result = clever.delete_clever_data("clever:t1")
        assert "classes" in result
        assert "students" in result
        assert "enrollments" in result
        assert "roster_files" in result

    def test_does_not_crash_with_no_supabase(self):
        """When Supabase is None, deletion completes without error."""
        clever.persist_roster_as_csv(self._make_students(["a"]), "clever:t1")
        # Supabase is already mocked to None in fixture
        result = clever.delete_clever_data("clever:t1")
        assert isinstance(result, dict)
        assert result["classes"] == 0  # no Supabase → no DB deletions

    def test_multiple_roster_files_all_deleted(self):
        """Multiple syncs create metadata files; all should be deleted."""
        clever.persist_roster_as_csv(self._make_students(["a", "b"]), "clever:t1")
        clever.persist_roster_as_csv(self._make_students(["a", "b", "c"]), "clever:t1")

        result = clever.delete_clever_data("clever:t1")
        assert result["roster_files"] >= 2

        import glob as globmod
        safe_id = clever._safe_teacher_id("clever:t1")
        remaining = globmod.glob(os.path.join(clever.ROSTERS_DIR, f"clever_roster_{safe_id}*"))
        assert len(remaining) == 0

    def test_does_not_delete_other_teacher_files(self):
        """Deletion for one teacher should not affect another teacher's roster."""
        clever.persist_roster_as_csv(self._make_students(["a"]), "clever:t1")
        clever.persist_roster_as_csv(self._make_students(["b"]), "clever:t2")

        clever.delete_clever_data("clever:t1")

        import glob as globmod
        safe_t2 = clever._safe_teacher_id("clever:t2")
        t2_files = globmod.glob(os.path.join(clever.ROSTERS_DIR, f"clever_roster_{safe_t2}*"))
        assert len(t2_files) >= 2  # t2's files should remain

    def test_corrupt_roster_does_not_crash(self):
        """Corrupt files in the roster dir should not crash deletion."""
        safe_id = clever._safe_teacher_id("clever:t1")
        corrupt_path = os.path.join(clever.ROSTERS_DIR, f"clever_roster_{safe_id}_corrupt.csv")
        with open(corrupt_path, "w") as f:
            f.write("{invalid data")
        # Should not raise
        result = clever.delete_clever_data("clever:t1")
        assert result["roster_files"] >= 1

    def test_deletes_period_and_contact_files_scoped_to_teacher(self):
        """FERPA right-to-delete: period files (section-keyed) + the guardian
        parent-contact file must be purged, scoped to THIS teacher's sections
        (another teacher's section period file must survive)."""
        import json as _json

        os.makedirs(clever.PERIODS_DIR, exist_ok=True)
        for sid in ("sec-1", "sec-2"):
            with open(os.path.join(clever.PERIODS_DIR, f"clever_{sid}.json"), "w") as f:
                _json.dump({"clever_section_id": sid, "source": "clever"}, f)
            with open(os.path.join(clever.PERIODS_DIR, f"clever_{sid}.json.meta.json"), "w") as f:
                _json.dump({"source": "clever"}, f)

        contacts_dir = os.path.join(clever.GRAIDER_DATA_DIR, "contacts")
        os.makedirs(contacts_dir, exist_ok=True)
        safe_id = clever._safe_teacher_id("clever:t1")
        contact_file = os.path.join(contacts_dir, f"parent_contacts_{safe_id}.json")
        with open(contact_file, "w") as f:
            _json.dump({"s1": {"parent_emails": ["guardian@home.edu"]}}, f)

        # Supabase reports teacher clever:t1 owns ONLY section sec-1.
        class _Q:
            def __init__(self, data):
                self._d = data

            def select(self, *a, **k):
                return self

            def eq(self, *a, **k):
                return self

            def in_(self, *a, **k):
                return self

            def delete(self, *a, **k):
                return self

            def execute(self):
                return type("R", (), {"data": self._d})()

        class _SB:
            def table(self, name):
                rows = [{"id": "c1", "clever_section_id": "sec-1"}] if name == "classes" else []
                return _Q(rows)

        with patch("backend.supabase_client.get_supabase", return_value=_SB()):
            result = clever.delete_clever_data("clever:t1")

        assert not os.path.exists(os.path.join(clever.PERIODS_DIR, "clever_sec-1.json"))
        assert not os.path.exists(os.path.join(clever.PERIODS_DIR, "clever_sec-1.json.meta.json"))
        assert os.path.exists(os.path.join(clever.PERIODS_DIR, "clever_sec-2.json")), \
            "another teacher's section period file must NOT be deleted"
        assert not os.path.exists(contact_file), "guardian parent-contact file must be deleted"
        assert result["period_files"] == 2  # sec-1 json + its .meta.json
        assert result["parent_contact_files"] == 1

    def test_deletes_student_pii_but_preserves_authored_content(self):
        """Student PII (per-student history + accommodation/IEP mappings) is
        purged via the storage layer, but teacher-AUTHORED content
        (teacher_data templates/settings, published_assessments) is
        intentionally NOT deleted — a Clever data deletion targets student data,
        not the educator's own work."""
        with patch("backend.storage.list_student_history", return_value=["s1", "s2"]) as m_list, \
             patch("backend.storage.delete_student_history", return_value=True) as m_delhist, \
             patch("backend.storage.delete", return_value=True) as m_del:
            result = clever.delete_clever_data("clever:t1")

        m_list.assert_called_once_with("clever:t1")
        assert m_delhist.call_count == 2
        assert {c.args[1] for c in m_delhist.call_args_list} == {"s1", "s2"}
        assert result["student_history"] == 2

        deleted_keys = {c.args[0] for c in m_del.call_args_list}
        assert deleted_keys == {"accommodations"}, (
            "scope boundary breached — only the student accommodations blob may "
            "be deleted; teacher_data / published_assessments must be preserved"
        )
        assert ("accommodations", "clever:t1") in [c.args for c in m_del.call_args_list]
        assert result["accommodations"] == "deleted"

    def test_period_cleanup_flagged_when_supabase_unavailable(self):
        """If Supabase is down we cannot scope section-keyed period files —
        the residual must be surfaced (period_files_skipped), not silent."""
        # Fixture already patches get_supabase -> None.
        with patch("backend.storage.list_student_history", return_value=[]), \
             patch("backend.storage.delete", return_value=True):
            result = clever.delete_clever_data("clever:t1")
        assert result.get("period_files_skipped") is True

    def test_scrubs_student_pii_from_published_assessments(self):
        """FERPA: join-code published_assessments embed student PII
        (settings.student_accommodations = {name: ...}, restricted_students =
        [name]). Deletion must SCRUB those fields while preserving the teacher's
        authored assessment + its non-PII config."""
        class _Q:
            def __init__(self, sb, table, data):
                self._sb, self._t, self._d = sb, table, data

            def select(self, *a, **k):
                return self

            def eq(self, *a, **k):
                return self

            def in_(self, *a, **k):
                return self

            def delete(self, *a, **k):
                return self

            def update(self, payload):
                self._sb.updates.append((self._t, payload))
                return self

            def execute(self):
                return type("R", (), {"data": self._d})()

        class _SB:
            def __init__(self, tables):
                self.tables, self.updates = tables, []

            def table(self, name):
                return _Q(self, name, self.tables.get(name, []))

        sb = _SB({
            "classes": [],
            "published_assessments": [{
                "id": "pa1",
                "settings": {
                    "student_accommodations": {"Jane Doe": {"extended_time": True}},
                    "restricted_students": ["Jane Doe"],
                    "time_limit_minutes": 30,  # authored config — must survive
                },
            }],
        })
        with patch("backend.supabase_client.get_supabase", return_value=sb), \
             patch("backend.storage.list_student_history", return_value=[]), \
             patch("backend.storage.delete", return_value=True):
            result = clever.delete_clever_data("clever:t1")

        pa_updates = [p for (t, p) in sb.updates if t == "published_assessments"]
        assert pa_updates, "published_assessments embedded PII was not scrubbed"
        scrubbed = pa_updates[0]["settings"]
        assert "student_accommodations" not in scrubbed
        assert "restricted_students" not in scrubbed
        assert scrubbed.get("time_limit_minutes") == 30, "authored config must be preserved"
        assert result["published_assessments_scrubbed"] == 1
