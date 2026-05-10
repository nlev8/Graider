"""Gap-fill tests for backend/routes/analytics_routes.py helpers.

Audit MAJOR #4 sprint follow-up to PR #335. Targets the deterministic
helpers `_find_master_grades`, `_load_valid_assignment_names`, and
`_assignment_matches_config`. Coverage gain to be confirmed by CI.

Per dual-rate-limit precedent: test-only PR merging on green CI.
"""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest


MODULE = "backend.routes.analytics_routes"


# ──────────────────────────────────────────────────────────────────
# _find_master_grades
# ──────────────────────────────────────────────────────────────────


class TestFindMasterGrades:
    def test_no_settings_no_candidates_returns_none(
        self, tmp_path, monkeypatch,
    ):
        # No settings file, no master CSV in standard locations
        from backend.routes.analytics_routes import _find_master_grades

        monkeypatch.setenv("HOME", str(tmp_path))
        with patch(f"{MODULE}.os.path.expanduser",
                   side_effect=lambda p: p.replace(
                       "~", str(tmp_path),
                   )):
            assert _find_master_grades() is None

    def test_settings_output_folder_resolves(self, tmp_path, monkeypatch):
        from backend.routes.analytics_routes import _find_master_grades

        # Build settings file pointing to an output folder
        output_dir = tmp_path / "Results"
        output_dir.mkdir()
        master_path = output_dir / "master_grades.csv"
        master_path.write_text("Student Name,Score\nAlice,85\n")

        settings_file = tmp_path / ".graider_global_settings.json"
        settings_file.write_text(json.dumps({
            "output_folder": str(output_dir),
        }))

        with patch(f"{MODULE}.os.path.expanduser",
                   side_effect=lambda p: p.replace(
                       "~", str(tmp_path),
                   )):
            result = _find_master_grades()
        assert result == str(master_path)

    def test_settings_corrupt_falls_back_to_candidates(
        self, tmp_path, monkeypatch,
    ):
        from backend.routes.analytics_routes import _find_master_grades

        # Corrupt settings file
        settings_file = tmp_path / ".graider_global_settings.json"
        settings_file.write_text("{not valid json")

        # But candidate path exists
        graider_data = tmp_path / ".graider_data" / "output"
        graider_data.mkdir(parents=True)
        master_path = graider_data / "master_grades.csv"
        master_path.write_text("Student Name,Score\n")

        with patch(f"{MODULE}.os.path.expanduser",
                   side_effect=lambda p: p.replace(
                       "~", str(tmp_path),
                   )):
            result = _find_master_grades()
        # Falls back to candidate location
        assert result == str(master_path)

    def test_settings_output_folder_missing_csv_falls_back(
        self, tmp_path, monkeypatch,
    ):
        from backend.routes.analytics_routes import _find_master_grades

        # Settings file points to folder, but CSV isn't there;
        # fall back to candidates
        settings_file = tmp_path / ".graider_global_settings.json"
        settings_file.write_text(json.dumps({
            "output_folder": str(tmp_path / "nonexistent"),
        }))

        with patch(f"{MODULE}.os.path.expanduser",
                   side_effect=lambda p: p.replace(
                       "~", str(tmp_path),
                   )):
            assert _find_master_grades() is None


# ──────────────────────────────────────────────────────────────────
# _load_valid_assignment_names
# ──────────────────────────────────────────────────────────────────


class TestLoadValidAssignmentNames:
    def test_no_directory_returns_empty_set(self, tmp_path, monkeypatch):
        from backend.routes.analytics_routes import (
            _load_valid_assignment_names,
        )

        with patch(f"{MODULE}.os.path.expanduser",
                   side_effect=lambda p: p.replace(
                       "~", str(tmp_path),
                   )):
            result = _load_valid_assignment_names()
        assert result == set()

    def test_loads_titles_and_aliases(self, tmp_path, monkeypatch):
        from backend.routes.analytics_routes import (
            _load_valid_assignment_names,
        )

        assn_dir = tmp_path / ".graider_assignments"
        assn_dir.mkdir()
        # Two assignment configs
        (assn_dir / "Quiz_One.json").write_text(json.dumps({
            "title": "Quiz One: Constitution",
            "aliases": ["Q1", "Quiz 1 Constitution"],
        }))
        (assn_dir / "Essay_One.json").write_text(json.dumps({
            "title": "Essay One",
            "aliases": [],
        }))

        with patch(f"{MODULE}.os.path.expanduser",
                   side_effect=lambda p: p.replace(
                       "~", str(tmp_path),
                   )):
            result = _load_valid_assignment_names()

        # Should contain normalized titles, filenames, and aliases
        assert len(result) >= 4  # 2 titles + 2 filenames + 2 aliases (dedupe possible)
        # Verify some normalized names are in
        from backend.services.assistant_tools import _normalize_assignment_name
        assert _normalize_assignment_name("Quiz One: Constitution") in result
        assert _normalize_assignment_name("Essay One") in result
        assert _normalize_assignment_name("Q1") in result

    def test_corrupt_json_skipped_via_sentry(self, tmp_path, monkeypatch):
        from backend.routes.analytics_routes import (
            _load_valid_assignment_names,
        )

        assn_dir = tmp_path / ".graider_assignments"
        assn_dir.mkdir()
        # One valid + one corrupt
        (assn_dir / "Valid.json").write_text(json.dumps({
            "title": "Valid Assignment",
        }))
        (assn_dir / "Bad.json").write_text("{not valid json")

        with patch(f"{MODULE}.os.path.expanduser",
                   side_effect=lambda p: p.replace(
                       "~", str(tmp_path),
                   )), \
             patch(f"{MODULE}.sentry_sdk.capture_exception") as mock_sentry:
            result = _load_valid_assignment_names()

        # Valid assignment loaded; corrupt swallowed via sentry
        from backend.services.assistant_tools import _normalize_assignment_name
        assert _normalize_assignment_name("Valid Assignment") in result
        mock_sentry.assert_called_once()

    def test_non_json_files_skipped(self, tmp_path, monkeypatch):
        from backend.routes.analytics_routes import (
            _load_valid_assignment_names,
        )

        assn_dir = tmp_path / ".graider_assignments"
        assn_dir.mkdir()
        # Mixed file types
        (assn_dir / "config.json").write_text(json.dumps({
            "title": "JSON Config",
        }))
        (assn_dir / "readme.txt").write_text("not json")
        (assn_dir / "old.bak").write_text("backup")

        with patch(f"{MODULE}.os.path.expanduser",
                   side_effect=lambda p: p.replace(
                       "~", str(tmp_path),
                   )):
            result = _load_valid_assignment_names()

        # Only the .json file's content survives
        from backend.services.assistant_tools import _normalize_assignment_name
        assert _normalize_assignment_name("JSON Config") in result


# ──────────────────────────────────────────────────────────────────
# _assignment_matches_config
# ──────────────────────────────────────────────────────────────────


class TestAssignmentMatchesConfig:
    def test_exact_match_returns_true(self):
        from backend.routes.analytics_routes import (
            _assignment_matches_config,
        )
        from backend.services.assistant_tools import _normalize_assignment_name

        norm = _normalize_assignment_name("Quiz One")
        assert _assignment_matches_config(
            "Quiz One", {norm},
        ) is True

    def test_no_match_returns_false(self):
        from backend.routes.analytics_routes import (
            _assignment_matches_config,
        )
        # Short config name (<10 chars) — only exact match qualifies
        assert _assignment_matches_config(
            "Quiz Z", {"some other config"},
        ) is False

    def test_partial_match_long_config_in_assignment(self):
        # Lines 365-367: if config name >= 10 chars and is contained
        # in the assignment name (or vice versa), match
        from backend.routes.analytics_routes import (
            _assignment_matches_config,
        )

        # Config name contained in assignment name
        result = _assignment_matches_config(
            "Quiz One Constitution Review",
            {"quiz one constitution"},
        )
        assert result is True

    def test_partial_match_assignment_in_long_config(self):
        from backend.routes.analytics_routes import (
            _assignment_matches_config,
        )

        # Assignment name contained in long config name
        result = _assignment_matches_config(
            "constitution review",
            {"constitution review activity"},
        )
        assert result is True

    def test_short_config_no_partial_match(self):
        # Lines 366: len(valid) < 10 → partial match disabled,
        # only exact match would qualify
        from backend.routes.analytics_routes import (
            _assignment_matches_config,
        )

        # Short config (8 chars after normalization) — no partial
        result = _assignment_matches_config(
            "Quiz One Constitution",
            {"quiz one"},  # 8 chars, < 10
        )
        assert result is False

    def test_empty_valid_names_returns_false(self):
        from backend.routes.analytics_routes import (
            _assignment_matches_config,
        )
        assert _assignment_matches_config("Quiz One", set()) is False
