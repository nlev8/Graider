"""Tests for planner route functions and standards loading."""
import json
import pytest
import sys
import os
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.routes.planner_routes import (
    _extract_usage,
    _build_subject_boundary_prompt,
    load_standards,
)
from tests.conftest_routes import client, flask_app, mock_grading_state, grading_lock


# ---------------------------------------------------------------------------
# TestExtractUsage
# ---------------------------------------------------------------------------

class TestExtractUsage:
    """Tests for _extract_usage helper."""

    def test_valid_completion_returns_usage_dict(self):
        """Valid completion with usage returns dict with all expected keys."""
        mock_completion = MagicMock()
        mock_completion.usage.prompt_tokens = 100
        mock_completion.usage.completion_tokens = 50

        result = _extract_usage(mock_completion, model="gpt-4o")

        assert result is not None
        assert result["model"] == "gpt-4o"
        assert result["input_tokens"] == 100
        assert result["output_tokens"] == 50
        assert result["total_tokens"] == 150
        assert "cost" in result
        assert "cost_display" in result
        assert result["cost_display"].startswith("$")

    def test_missing_usage_returns_none(self):
        """Completion with usage=None returns None."""
        mock_completion = MagicMock()
        mock_completion.usage = None

        result = _extract_usage(mock_completion, model="gpt-4o")
        assert result is None

    def test_none_completion_returns_none(self):
        """None completion returns None."""
        result = _extract_usage(None, model="gpt-4o")
        assert result is None


# ---------------------------------------------------------------------------
# TestBuildSubjectBoundaryPrompt
# ---------------------------------------------------------------------------

class TestBuildSubjectBoundaryPrompt:
    """Tests for _build_subject_boundary_prompt helper."""

    def test_subject_and_grade_returns_constraint(self):
        """Subject + grade returns a constraint string containing both."""
        result = _build_subject_boundary_prompt("Science", "7")

        assert "Science" in result
        assert "7" in result
        assert "SUBJECT BOUNDARY CONSTRAINT" in result

    def test_with_standard_codes_includes_codes(self):
        """When standard codes provided, they appear in the output."""
        codes = ["SC.7.E.6.1", "SC.7.L.15.2"]
        result = _build_subject_boundary_prompt("Science", "7", standard_codes=codes)

        assert "SC.7.E.6.1" in result
        assert "SC.7.L.15.2" in result
        assert "Valid standard codes" in result

    def test_empty_subject_returns_empty_string(self):
        """Empty subject returns empty string."""
        assert _build_subject_boundary_prompt("", "7") == ''
        assert _build_subject_boundary_prompt(None, "7") == ''

    def test_empty_grade_returns_empty_string(self):
        """Empty grade returns empty string."""
        assert _build_subject_boundary_prompt("Science", "") == ''
        assert _build_subject_boundary_prompt("Science", None) == ''


# ---------------------------------------------------------------------------
# TestLoadStandards
# ---------------------------------------------------------------------------

@pytest.fixture
def standards_dir(tmp_path, monkeypatch):
    """Create a temporary standards data directory and patch DATA_DIR."""
    import backend.routes.planner_routes as pr
    monkeypatch.setattr(pr, 'DATA_DIR', tmp_path)
    return tmp_path


class TestLoadStandards:
    """Tests for load_standards function."""

    def test_dict_format_loads_correctly(self, standards_dir):
        """Dict format {'standards': [...]} loads correctly."""
        data = {
            "standards": [
                {"code": "SC.7.E.6.1", "description": "Earth structures"},
                {"code": "SC.7.L.15.2", "description": "Life science"},
            ]
        }
        filepath = standards_dir / "standards_fl_science.json"
        filepath.write_text(json.dumps(data))

        result = load_standards("FL", "Science")
        assert len(result) == 2
        assert result[0]["code"] == "SC.7.E.6.1"

    def test_array_format_loads_correctly(self, standards_dir):
        """Array format [...] loads correctly."""
        data = [
            {"code": "SC.7.E.6.1", "description": "Earth structures"},
        ]
        filepath = standards_dir / "standards_fl_science.json"
        filepath.write_text(json.dumps(data))

        result = load_standards("FL", "Science")
        assert len(result) == 1
        assert result[0]["code"] == "SC.7.E.6.1"

    def test_grade_filtering_by_code_pattern(self, standards_dir):
        """Grade filtering by code pattern (e.g., 'SC.7.E' matches grade 7)."""
        data = {
            "standards": [
                {"code": "SC.6.E.6.1", "description": "Grade 6 earth"},
                {"code": "SC.7.E.6.1", "description": "Grade 7 earth"},
                {"code": "SC.8.L.15.2", "description": "Grade 8 life"},
            ]
        }
        filepath = standards_dir / "standards_fl_science.json"
        filepath.write_text(json.dumps(data))

        result = load_standards("FL", "Science", grade="7")
        assert len(result) == 1
        assert result[0]["code"] == "SC.7.E.6.1"

    def test_k12_codes_included_for_any_grade(self, standards_dir):
        """K12 codes (e.g., WL.K12.NH.1.1) apply to all grades."""
        data = {
            "standards": [
                {"code": "WL.K12.NH.1.1", "description": "World languages"},
                {"code": "WL.3.S.1.1", "description": "Grade 3 specific"},
            ]
        }
        filepath = standards_dir / "standards_fl_world_languages.json"
        filepath.write_text(json.dumps(data))

        result = load_standards("FL", "World Languages", grade="7")
        # K12 code should be included, grade 3 should not
        assert len(result) == 1
        assert result[0]["code"] == "WL.K12.NH.1.1"

    def test_nonexistent_file_returns_empty_list(self, standards_dir):
        """Non-existent file returns empty list."""
        result = load_standards("FL", "Nonexistent Subject")
        assert result == []

    def test_grade_filtering_with_range(self, standards_dir):
        """File with grade range '6-8' matches requested grade 7."""
        data = {
            "grade": "6-8",
            "standards": [
                {"code": "ELA.R.1.1", "description": "Reading standard"},
            ]
        }
        filepath = standards_dir / "standards_fl_ela.json"
        filepath.write_text(json.dumps(data))

        # Code doesn't match grade pattern, but grade is in file range → return all
        result = load_standards("FL", "ELA", grade="7")
        assert len(result) == 1

    def test_912_course_mapping_filters_by_course(self, standards_dir):
        """912 codes filter by course field for high school grades."""
        data = {
            "standards": [
                {"code": "SC.912.L.14.1", "description": "Biology standard", "course": "Biology"},
                {"code": "SC.912.P.8.1", "description": "Chemistry standard", "course": "Chemistry"},
            ]
        }
        filepath = standards_dir / "standards_fl_science.json"
        filepath.write_text(json.dumps(data))

        # Grade 9 maps to Biology for science
        result = load_standards("FL", "Science", grade="9")
        assert len(result) == 1
        assert result[0]["course"] == "Biology"

    def test_no_grade_filter_returns_all(self, standards_dir):
        """No grade filter returns all standards."""
        data = {
            "standards": [
                {"code": "SC.6.E.6.1", "description": "Grade 6"},
                {"code": "SC.7.E.6.1", "description": "Grade 7"},
                {"code": "SC.8.L.15.2", "description": "Grade 8"},
            ]
        }
        filepath = standards_dir / "standards_fl_science.json"
        filepath.write_text(json.dumps(data))

        result = load_standards("FL", "Science")
        assert len(result) == 3

    def test_grade_not_in_file_range_returns_empty(self, standards_dir):
        """Grade not in file range returns empty list."""
        data = {
            "grade": "6-8",
            "standards": [
                {"code": "ELA.R.1.1", "description": "Reading standard"},
            ]
        }
        filepath = standards_dir / "standards_fl_ela.json"
        filepath.write_text(json.dumps(data))

        # Grade 11 is outside 6-8 range and no code matches
        result = load_standards("FL", "ELA", grade="11")
        assert result == []

    def test_subject_name_cleaning(self, standards_dir):
        """Subject with spaces and slashes gets cleaned for filename lookup."""
        data = [{"code": "SS.7.C.1.1", "description": "Civics standard"}]
        # "Social Studies / Civics" → "social_studies_-_civics"
        filepath = standards_dir / "standards_fl_social_studies_-_civics.json"
        filepath.write_text(json.dumps(data))

        result = load_standards("FL", "Social Studies / Civics")
        assert len(result) == 1


# ---------------------------------------------------------------------------
# TestGetStandardsRoute
# ---------------------------------------------------------------------------

class TestGetStandardsRoute:
    """Integration tests for POST /api/get-standards route."""

    def test_valid_subject_returns_standards(self, client, tmp_path, monkeypatch):
        """POST with valid subject returns standards array."""
        import backend.routes.planner_routes as pr
        monkeypatch.setattr(pr, 'DATA_DIR', tmp_path)

        data = {
            "standards": [
                {"code": "SC.7.E.6.1", "description": "Earth structures"},
            ]
        }
        filepath = tmp_path / "standards_fl_science.json"
        filepath.write_text(json.dumps(data))

        resp = client.post('/api/get-standards', json={
            "state": "FL", "subject": "Science", "grade": "7"
        })
        assert resp.status_code == 200
        body = resp.get_json()
        assert len(body["standards"]) == 1
        assert body["standards"][0]["code"] == "SC.7.E.6.1"

    def test_nonexistent_subject_returns_empty(self, client, tmp_path, monkeypatch):
        """Non-existent subject returns empty standards list."""
        import backend.routes.planner_routes as pr
        monkeypatch.setattr(pr, 'DATA_DIR', tmp_path)

        resp = client.post('/api/get-standards', json={
            "state": "FL", "subject": "Underwater Basket Weaving", "grade": "7"
        })
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["standards"] == []

    def test_response_includes_grade_and_subject(self, client, tmp_path, monkeypatch):
        """Response includes grade and subject fields."""
        import backend.routes.planner_routes as pr
        monkeypatch.setattr(pr, 'DATA_DIR', tmp_path)

        resp = client.post('/api/get-standards', json={
            "state": "FL", "subject": "Math", "grade": "8"
        })
        body = resp.get_json()
        assert body["grade"] == "8"
        assert body["subject"] == "Math"

    def test_default_values_used_when_fields_missing(self, client, tmp_path, monkeypatch):
        """Default values are used when request fields are missing."""
        import backend.routes.planner_routes as pr
        monkeypatch.setattr(pr, 'DATA_DIR', tmp_path)

        # Send empty JSON - should use defaults: state=FL, grade=7, subject=Civics
        resp = client.post('/api/get-standards', json={})
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["grade"] == "7"
        assert body["subject"] == "Civics"
