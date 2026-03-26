"""Tests for backend.oneroster — normalize_roster() and get_oneroster_config()."""
import os
import pytest

from backend.oneroster import normalize_roster, get_oneroster_config


# ── normalize_roster ──────────────────────────────────────────


class TestNormalizeRosterEmpty:
    def test_empty_roster_returns_empty_lists(self):
        classes, students, enrollments, accommodations = normalize_roster({})
        assert classes == []
        assert students == []
        assert enrollments == []
        assert accommodations == []

    def test_empty_collections(self):
        raw = {"classes": [], "students": [], "enrollments": [], "demographics": []}
        classes, students, enrollments, accommodations = normalize_roster(raw)
        assert classes == []
        assert students == []
        assert enrollments == []
        assert accommodations == []


class TestNormalizeClasses:
    def test_basic_class_normalization(self):
        raw = {
            "classes": [
                {
                    "sourcedId": "cls-1",
                    "title": "Algebra I",
                    "subjects": ["Mathematics"],
                    "grades": ["09"],
                    "status": "active",
                }
            ],
            "students": [],
            "enrollments": [],
            "demographics": [],
        }
        classes, _, _, _ = normalize_roster(raw)
        assert len(classes) == 1
        assert classes[0]["external_id"] == "oneroster:cls-1"
        assert classes[0]["name"] == "Algebra I"
        assert classes[0]["subject"] == "Mathematics"
        assert classes[0]["grade_level"] == "09"

    def test_class_no_subjects_or_grades(self):
        raw = {
            "classes": [{"sourcedId": "cls-2", "title": "Study Hall"}],
            "students": [],
            "enrollments": [],
            "demographics": [],
        }
        classes, _, _, _ = normalize_roster(raw)
        assert classes[0]["subject"] is None
        assert classes[0]["grade_level"] is None

    def test_skips_deleted_classes(self):
        raw = {
            "classes": [
                {"sourcedId": "cls-1", "title": "Active", "status": "active"},
                {"sourcedId": "cls-2", "title": "Deleted", "status": "tobedeleted"},
            ],
            "students": [],
            "enrollments": [],
            "demographics": [],
        }
        classes, _, _, _ = normalize_roster(raw)
        assert len(classes) == 1
        assert classes[0]["name"] == "Active"


class TestNormalizeStudents:
    def test_basic_student_normalization(self):
        raw = {
            "classes": [],
            "students": [
                {
                    "sourcedId": "stu-1",
                    "givenName": "Jane",
                    "familyName": "Doe",
                    "email": "jane@school.edu",
                    "status": "active",
                }
            ],
            "enrollments": [],
            "demographics": [],
        }
        _, students, _, _ = normalize_roster(raw)
        assert len(students) == 1
        assert students[0]["external_id"] == "oneroster:stu-1"
        assert students[0]["first_name"] == "Jane"
        assert students[0]["last_name"] == "Doe"
        assert students[0]["email"] == "jane@school.edu"

    def test_skips_deleted_students(self):
        raw = {
            "classes": [],
            "students": [
                {"sourcedId": "stu-1", "givenName": "Active", "familyName": "Student"},
                {"sourcedId": "stu-2", "givenName": "Gone", "familyName": "Student", "status": "tobedeleted"},
            ],
            "enrollments": [],
            "demographics": [],
        }
        _, students, _, _ = normalize_roster(raw)
        assert len(students) == 1
        assert students[0]["first_name"] == "Active"

    def test_deduplicates_students_by_sourced_id(self):
        raw = {
            "classes": [],
            "students": [
                {"sourcedId": "stu-1", "givenName": "Jane", "familyName": "Doe", "email": "jane@school.edu"},
                {"sourcedId": "stu-1", "givenName": "Jane", "familyName": "Doe", "email": "jane2@school.edu"},
            ],
            "enrollments": [],
            "demographics": [],
        }
        _, students, _, _ = normalize_roster(raw)
        assert len(students) == 1
        assert students[0]["email"] == "jane@school.edu"


class TestNormalizeEnrollments:
    def test_student_enrollment_only(self):
        raw = {
            "classes": [],
            "students": [],
            "enrollments": [
                {
                    "role": "student",
                    "class": {"sourcedId": "cls-1"},
                    "user": {"sourcedId": "stu-1"},
                    "status": "active",
                },
                {
                    "role": "teacher",
                    "class": {"sourcedId": "cls-1"},
                    "user": {"sourcedId": "tch-1"},
                    "status": "active",
                },
            ],
            "demographics": [],
        }
        _, _, enrollments, _ = normalize_roster(raw)
        assert len(enrollments) == 1
        assert enrollments[0]["class_external_id"] == "oneroster:cls-1"
        assert enrollments[0]["student_external_id"] == "oneroster:stu-1"

    def test_enrollment_string_refs(self):
        """Some OneRoster implementations use string IDs instead of dicts."""
        raw = {
            "classes": [],
            "students": [],
            "enrollments": [
                {
                    "role": "student",
                    "class": "cls-1",
                    "user": "stu-1",
                    "status": "active",
                },
            ],
            "demographics": [],
        }
        _, _, enrollments, _ = normalize_roster(raw)
        assert len(enrollments) == 1
        assert enrollments[0]["class_external_id"] == "oneroster:cls-1"
        assert enrollments[0]["student_external_id"] == "oneroster:stu-1"

    def test_skips_deleted_enrollments(self):
        raw = {
            "classes": [],
            "students": [],
            "enrollments": [
                {
                    "role": "student",
                    "class": {"sourcedId": "cls-1"},
                    "user": {"sourcedId": "stu-1"},
                    "status": "tobedeleted",
                },
            ],
            "demographics": [],
        }
        _, _, enrollments, _ = normalize_roster(raw)
        assert len(enrollments) == 0


class TestAccommodations:
    def test_iep_accommodation_from_demographics(self):
        raw = {
            "classes": [],
            "students": [
                {"sourcedId": "stu-1", "givenName": "Jane", "familyName": "Doe"},
            ],
            "enrollments": [],
            "demographics": [
                {
                    "sourcedId": "stu-1",
                    "metadata": {"iep_status": "active"},
                },
            ],
        }
        _, _, _, accommodations = normalize_roster(raw)
        assert len(accommodations) == 1
        assert accommodations[0]["student_external_id"] == "oneroster:stu-1"
        assert accommodations[0]["iep_status"] == "active"

    def test_ell_accommodation_with_home_language(self):
        raw = {
            "classes": [],
            "students": [
                {"sourcedId": "stu-2", "givenName": "Carlos", "familyName": "Garcia"},
            ],
            "enrollments": [],
            "demographics": [
                {
                    "sourcedId": "stu-2",
                    "metadata": {
                        "ell_status": "active",
                        "home_language": "Spanish",
                    },
                },
            ],
        }
        _, _, _, accommodations = normalize_roster(raw)
        assert len(accommodations) == 1
        assert accommodations[0]["ell_status"] == "active"
        assert accommodations[0]["home_language"] == "Spanish"

    def test_camel_case_metadata_keys(self):
        """Some providers use camelCase instead of snake_case."""
        raw = {
            "classes": [],
            "students": [
                {"sourcedId": "stu-3", "givenName": "Pat", "familyName": "Kim"},
            ],
            "enrollments": [],
            "demographics": [
                {
                    "sourcedId": "stu-3",
                    "metadata": {"iepStatus": "active", "ellStatus": "monitor"},
                },
            ],
        }
        _, _, _, accommodations = normalize_roster(raw)
        assert len(accommodations) == 1
        assert accommodations[0]["iep_status"] == "active"
        assert accommodations[0]["ell_status"] == "monitor"

    def test_no_accommodations_without_demographics(self):
        raw = {
            "classes": [],
            "students": [
                {"sourcedId": "stu-1", "givenName": "Jane", "familyName": "Doe"},
            ],
            "enrollments": [],
            "demographics": [],
        }
        _, _, _, accommodations = normalize_roster(raw)
        assert len(accommodations) == 0


class TestExternalIdPrefix:
    def test_all_ids_get_oneroster_prefix(self):
        raw = {
            "classes": [{"sourcedId": "cls-1", "title": "Math"}],
            "students": [{"sourcedId": "stu-1", "givenName": "A", "familyName": "B"}],
            "enrollments": [
                {
                    "role": "student",
                    "class": {"sourcedId": "cls-1"},
                    "user": {"sourcedId": "stu-1"},
                }
            ],
            "demographics": [],
        }
        classes, students, enrollments, _ = normalize_roster(raw)
        assert classes[0]["external_id"].startswith("oneroster:")
        assert students[0]["external_id"].startswith("oneroster:")
        assert enrollments[0]["class_external_id"].startswith("oneroster:")
        assert enrollments[0]["student_external_id"].startswith("oneroster:")


# ── get_oneroster_config ──────────────────────────────────────


class TestGetOneRosterConfig:
    def test_returns_none_when_no_config(self, monkeypatch):
        monkeypatch.delenv("ONEROSTER_BASE_URL", raising=False)
        monkeypatch.delenv("ONEROSTER_CLIENT_ID", raising=False)
        monkeypatch.delenv("ONEROSTER_CLIENT_SECRET", raising=False)
        result = get_oneroster_config()
        assert result is None

    def test_returns_env_var_config(self, monkeypatch):
        monkeypatch.setenv("ONEROSTER_BASE_URL", "https://api.example.com")
        monkeypatch.setenv("ONEROSTER_CLIENT_ID", "my-id")
        monkeypatch.setenv("ONEROSTER_CLIENT_SECRET", "my-secret")
        monkeypatch.setenv("ONEROSTER_TOKEN_URL", "https://auth.example.com/token")
        monkeypatch.setenv("ONEROSTER_SCHOOL_ID", "school-42")

        result = get_oneroster_config()
        assert result is not None
        assert result["base_url"] == "https://api.example.com"
        assert result["client_id"] == "my-id"
        assert result["client_secret"] == "my-secret"
        assert result["token_url"] == "https://auth.example.com/token"
        assert result["school_id"] == "school-42"

    def test_returns_none_when_partial_env(self, monkeypatch):
        monkeypatch.setenv("ONEROSTER_BASE_URL", "https://api.example.com")
        monkeypatch.delenv("ONEROSTER_CLIENT_ID", raising=False)
        monkeypatch.delenv("ONEROSTER_CLIENT_SECRET", raising=False)
        result = get_oneroster_config()
        assert result is None
