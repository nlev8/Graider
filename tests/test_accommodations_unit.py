"""Unit tests for backend/accommodations.py.

Audit MAJOR #4 sprint follow-up to PR #298. Targets the 177 uncovered
LOC (35% baseline → ~99%). Module manages FERPA-compliant IEP/504
accommodation presets + per-student mappings, with dual-write storage
(Supabase via storage layer + local JSON file fallback).

Functions covered (~13)
* load_presets — storage hit / file fallback / corrupt-json swallow
* save_preset — storage path + file path + auto-id from name + outer
  except
* delete_preset — default-protected / not-found / storage hit / file
  fallback / outer except
* load_student_accommodations — storage hit / file fallback /
  corrupt-json swallow
* save_student_accommodations — happy + outer except
* set_student_accommodation — preserves existing student_name when
  none provided
* get_student_accommodation — UNKNOWN early-return / found / not-found
* remove_student_accommodation — found / not-found
* _get_ell_language — file-missing / language=none / valid / corrupt
* build_accommodation_prompt — UNKNOWN / no-mapping / preset+notes
  combined / custom-notes only
* build_prompt_from_presets (covered briefly via build_accommodation_prompt)
* import_accommodations_from_csv — known preset / unknown→notes /
  no-id skip / no-content skip
* export_student_accommodations / clear_all_accommodations /
  get_accommodation_stats
"""
from __future__ import annotations

import json
import os
from unittest.mock import patch, MagicMock

import pytest


@pytest.fixture
def tmp_paths(monkeypatch, tmp_path):
    """Redirect all module-level paths into tmp_path so tests never touch
    the real ~/.graider_data."""
    accommodations_dir = tmp_path / "accommodations"
    accommodations_dir.mkdir(parents=True)
    presets_file = accommodations_dir / "presets.json"
    student_file = accommodations_dir / "student_accommodations.json"
    ell_file = tmp_path / "ell_students.json"

    monkeypatch.setattr(
        "backend.accommodations.GRAIDER_DATA_DIR", str(tmp_path),
    )
    monkeypatch.setattr(
        "backend.accommodations.ACCOMMODATIONS_DIR", str(accommodations_dir),
    )
    monkeypatch.setattr(
        "backend.accommodations.PRESETS_FILE", str(presets_file),
    )
    monkeypatch.setattr(
        "backend.accommodations.STUDENT_ACCOMMODATIONS_FILE",
        str(student_file),
    )
    monkeypatch.setattr(
        "backend.accommodations.ELL_STUDENTS_FILE", str(ell_file),
    )
    return {
        "accommodations_dir": accommodations_dir,
        "presets_file": presets_file,
        "student_file": student_file,
        "ell_file": ell_file,
    }


# ──────────────────────────────────────────────────────────────────
# load_presets
# ──────────────────────────────────────────────────────────────────


class TestLoadPresets:
    def test_storage_hit_returns_merged(self, tmp_paths):
        # Storage returns custom presets that override the defaults.
        custom = {
            "simplified_language": {  # Override default
                "id": "simplified_language", "name": "Custom",
                "ai_instructions": "...",
            },
            "extra_custom": {
                "id": "extra_custom", "name": "Extra",
                "ai_instructions": "...",
            },
        }
        with patch(
            "backend.accommodations._storage_load", return_value=custom,
        ):
            from backend.accommodations import load_presets
            result = load_presets("teacher-1")
        # Custom override wins
        assert result["simplified_language"]["name"] == "Custom"
        # Custom preset added
        assert "extra_custom" in result
        # Other defaults preserved
        assert "effort_focused" in result

    def test_storage_miss_falls_back_to_file(self, tmp_paths):
        # Pre-write a custom presets file
        tmp_paths["presets_file"].write_text(json.dumps({
            "from_file": {"id": "from_file", "name": "From File",
                          "ai_instructions": "..."},
        }))
        with patch(
            "backend.accommodations._storage_load", None,
        ):
            from backend.accommodations import load_presets
            result = load_presets()
        assert "from_file" in result
        assert "simplified_language" in result  # default

    def test_corrupt_json_file_swallowed(self, tmp_paths):
        tmp_paths["presets_file"].write_text("{ not valid json")
        with patch("backend.accommodations._storage_load", None):
            from backend.accommodations import load_presets
            result = load_presets()
        # Defaults still returned; corrupt file silently dropped
        assert "simplified_language" in result


# ──────────────────────────────────────────────────────────────────
# save_preset / delete_preset
# ──────────────────────────────────────────────────────────────────


class TestSavePreset:
    def test_auto_id_from_name(self, tmp_paths):
        save_mock = MagicMock()
        with patch(
            "backend.accommodations._storage_load", return_value=None,
        ), patch(
            "backend.accommodations._storage_save", save_mock,
        ):
            from backend.accommodations import save_preset
            ok = save_preset({
                "name": "My Custom Preset",
                "ai_instructions": "do x",
            })
        assert ok is True
        # Auto-id slugifies " " → "_" and lowercases
        save_args = save_mock.call_args.args
        assert save_args[0] == "accommodation_presets"
        saved_dict = save_args[1]
        assert "my_custom_preset" in saved_dict

    def test_explicit_id_preserved(self, tmp_paths):
        with patch(
            "backend.accommodations._storage_load", return_value=None,
        ), patch(
            "backend.accommodations._storage_save",
        ) as save_mock:
            from backend.accommodations import save_preset
            save_preset({
                "id": "override-id", "name": "X",
                "ai_instructions": "y",
            })
        saved = save_mock.call_args.args[1]
        assert "override-id" in saved

    def test_storage_hit_prepopulates(self, tmp_paths):
        # Existing storage data is loaded and the new preset is added
        existing = {"old": {"id": "old", "name": "Old"}}
        with patch(
            "backend.accommodations._storage_load",
            return_value=existing,
        ), patch(
            "backend.accommodations._storage_save",
        ) as save_mock:
            from backend.accommodations import save_preset
            save_preset({"id": "new", "name": "New",
                         "ai_instructions": "..."})
        saved = save_mock.call_args.args[1]
        assert "old" in saved
        assert "new" in saved

    def test_storage_miss_loads_from_file(self, tmp_paths):
        # storage_load returns None → falls back to file
        tmp_paths["presets_file"].write_text(json.dumps({
            "file_existing": {"id": "file_existing", "name": "FE"},
        }))
        with patch(
            "backend.accommodations._storage_load", return_value=None,
        ), patch(
            "backend.accommodations._storage_save",
        ) as save_mock:
            from backend.accommodations import save_preset
            save_preset({"id": "new2", "name": "X",
                         "ai_instructions": "..."})
        saved = save_mock.call_args.args[1]
        assert "file_existing" in saved
        assert "new2" in saved

    def test_outer_exception_returns_false(self, tmp_paths):
        with patch(
            "backend.accommodations._storage_load", return_value=None,
        ), patch(
            "builtins.open", side_effect=IOError("disk gone"),
        ):
            from backend.accommodations import save_preset
            ok = save_preset({"name": "X", "ai_instructions": "..."})
        assert ok is False


class TestDeletePreset:
    def test_default_preset_cannot_be_deleted(self):
        from backend.accommodations import delete_preset
        # 'simplified_language' is a DEFAULT preset
        assert delete_preset("simplified_language") is False

    def test_storage_load_then_delete(self, tmp_paths):
        existing = {"custom-1": {"id": "custom-1", "name": "X"}}
        save_mock = MagicMock()
        with patch(
            "backend.accommodations._storage_load",
            return_value=existing,
        ), patch(
            "backend.accommodations._storage_save", save_mock,
        ):
            from backend.accommodations import delete_preset
            ok = delete_preset("custom-1")
        assert ok is True
        # Saved presets dict no longer contains custom-1
        saved = save_mock.call_args.args[1]
        assert "custom-1" not in saved

    def test_file_fallback_when_storage_returns_none(self, tmp_paths):
        # Storage None + file present → loads from file, deletes, writes
        tmp_paths["presets_file"].write_text(json.dumps({
            "file-only": {"id": "file-only", "name": "FO"},
        }))
        with patch(
            "backend.accommodations._storage_load", return_value=None,
        ), patch(
            "backend.accommodations._storage_save",
        ) as save_mock:
            from backend.accommodations import delete_preset
            ok = delete_preset("file-only")
        assert ok is True

    def test_not_found_returns_false(self, tmp_paths):
        with patch(
            "backend.accommodations._storage_load",
            return_value={"other": {}},
        ):
            from backend.accommodations import delete_preset
            assert delete_preset("missing") is False

    def test_outer_exception_returns_false(self, tmp_paths):
        with patch(
            "backend.accommodations._storage_load",
            side_effect=RuntimeError("storage fail"),
        ):
            from backend.accommodations import delete_preset
            assert delete_preset("custom-1") is False


# ──────────────────────────────────────────────────────────────────
# Student accommodation mappings
# ──────────────────────────────────────────────────────────────────


class TestLoadStudentAccommodations:
    def test_storage_hit(self, tmp_paths):
        data = {"stu-1": {"presets": ["x"], "custom_notes": ""}}
        with patch(
            "backend.accommodations._storage_load", return_value=data,
        ):
            from backend.accommodations import load_student_accommodations
            assert load_student_accommodations() == data

    def test_storage_miss_falls_back_to_file(self, tmp_paths):
        tmp_paths["student_file"].write_text(json.dumps({
            "stu-1": {"presets": ["a"]},
        }))
        with patch("backend.accommodations._storage_load", None):
            from backend.accommodations import load_student_accommodations
            assert load_student_accommodations() == {
                "stu-1": {"presets": ["a"]},
            }

    def test_no_data_returns_empty_dict(self, tmp_paths):
        # Storage None + no file → empty
        with patch("backend.accommodations._storage_load", None):
            from backend.accommodations import load_student_accommodations
            assert load_student_accommodations() == {}

    def test_corrupt_json_swallowed(self, tmp_paths):
        tmp_paths["student_file"].write_text("{ corrupt")
        with patch("backend.accommodations._storage_load", None):
            from backend.accommodations import load_student_accommodations
            assert load_student_accommodations() == {}


class TestSaveStudentAccommodations:
    def test_writes_file_and_storage(self, tmp_paths):
        save_mock = MagicMock()
        with patch(
            "backend.accommodations._storage_save", save_mock,
        ):
            from backend.accommodations import save_student_accommodations
            ok = save_student_accommodations({"stu-1": {"presets": []}})
        assert ok is True
        # Local file written
        assert tmp_paths["student_file"].exists()
        # Storage save called with key 'accommodations'
        save_mock.assert_called_once()
        assert save_mock.call_args.args[0] == "accommodations"

    def test_outer_exception_returns_false(self, tmp_paths):
        with patch(
            "builtins.open", side_effect=IOError("disk gone"),
        ):
            from backend.accommodations import save_student_accommodations
            assert save_student_accommodations({}) is False


class TestSetStudentAccommodation:
    def test_preserves_existing_student_name_when_none_provided(
        self, tmp_paths,
    ):
        # Pre-existing mapping with student_name → set_student
        # without name should preserve it.
        existing = {"stu-1": {"presets": ["a"],
                              "student_name": "Original Name"}}
        with patch(
            "backend.accommodations._storage_load", return_value=existing,
        ), patch(
            "backend.accommodations._storage_save",
        ) as save_mock:
            from backend.accommodations import set_student_accommodation
            ok = set_student_accommodation(
                "stu-1", ["new-preset"],
            )
        assert ok is True
        saved_mappings = save_mock.call_args.args[1]
        assert saved_mappings["stu-1"]["student_name"] == "Original Name"

    def test_explicit_student_name_overrides(self, tmp_paths):
        with patch(
            "backend.accommodations._storage_load", return_value={},
        ), patch(
            "backend.accommodations._storage_save",
        ) as save_mock:
            from backend.accommodations import set_student_accommodation
            set_student_accommodation(
                "stu-2", [], student_name="Explicit",
            )
        saved = save_mock.call_args.args[1]
        assert saved["stu-2"]["student_name"] == "Explicit"


class TestGetStudentAccommodation:
    def test_unknown_id_returns_none(self):
        from backend.accommodations import get_student_accommodation
        assert get_student_accommodation("UNKNOWN") is None
        assert get_student_accommodation("") is None

    def test_found(self, tmp_paths):
        with patch(
            "backend.accommodations._storage_load",
            return_value={"stu-1": {"presets": ["a"]}},
        ):
            from backend.accommodations import get_student_accommodation
            assert get_student_accommodation("stu-1")["presets"] == ["a"]

    def test_not_found_returns_none(self, tmp_paths):
        with patch(
            "backend.accommodations._storage_load", return_value={},
        ):
            from backend.accommodations import get_student_accommodation
            assert get_student_accommodation("missing") is None


class TestRemoveStudentAccommodation:
    def test_found_returns_true(self, tmp_paths):
        with patch(
            "backend.accommodations._storage_load",
            return_value={"stu-1": {"presets": []}},
        ), patch(
            "backend.accommodations._storage_save",
        ) as save_mock:
            from backend.accommodations import (
                remove_student_accommodation,
            )
            ok = remove_student_accommodation("stu-1")
        assert ok is True
        saved = save_mock.call_args.args[1]
        assert "stu-1" not in saved

    def test_not_found_returns_false(self, tmp_paths):
        with patch(
            "backend.accommodations._storage_load", return_value={},
        ):
            from backend.accommodations import remove_student_accommodation
            assert remove_student_accommodation("nope") is False


# ──────────────────────────────────────────────────────────────────
# _get_ell_language
# ──────────────────────────────────────────────────────────────────


class TestGetEllLanguage:
    def test_no_file_returns_none(self, tmp_paths):
        from backend.accommodations import _get_ell_language
        assert _get_ell_language("stu-1") is None

    def test_language_none_treated_as_no_ell(self, tmp_paths):
        tmp_paths["ell_file"].write_text(json.dumps({
            "stu-1": {"language": "none"},
        }))
        from backend.accommodations import _get_ell_language
        assert _get_ell_language("stu-1") is None

    def test_valid_language_returned(self, tmp_paths):
        tmp_paths["ell_file"].write_text(json.dumps({
            "stu-1": {"language": "Spanish"},
        }))
        from backend.accommodations import _get_ell_language
        assert _get_ell_language("stu-1") == "Spanish"

    def test_corrupt_json_returns_none(self, tmp_paths):
        tmp_paths["ell_file"].write_text("{ corrupt")
        from backend.accommodations import _get_ell_language
        assert _get_ell_language("stu-1") is None

    def test_unknown_student_returns_none(self, tmp_paths):
        tmp_paths["ell_file"].write_text(json.dumps({
            "other-stu": {"language": "Spanish"},
        }))
        from backend.accommodations import _get_ell_language
        assert _get_ell_language("stu-missing") is None


# ──────────────────────────────────────────────────────────────────
# build_accommodation_prompt (integrates load_presets + get_student)
# ──────────────────────────────────────────────────────────────────


class TestBuildAccommodationPrompt:
    def test_unknown_student_returns_empty(self):
        from backend.accommodations import build_accommodation_prompt
        assert build_accommodation_prompt("UNKNOWN") == ""
        assert build_accommodation_prompt("") == ""

    def test_no_mapping_returns_empty(self, tmp_paths):
        with patch(
            "backend.accommodations._storage_load", return_value={},
        ):
            from backend.accommodations import build_accommodation_prompt
            assert build_accommodation_prompt("stu-1") == ""

    def test_no_presets_no_notes_returns_empty(self, tmp_paths):
        # Mapping exists but is empty
        with patch(
            "backend.accommodations._storage_load",
            return_value={"stu-1": {"presets": [], "custom_notes": ""}},
        ):
            from backend.accommodations import build_accommodation_prompt
            assert build_accommodation_prompt("stu-1") == ""

    def test_presets_and_custom_notes_combined(self, tmp_paths):
        # storage_load called multiple times; route by key.
        def loader(key, tid):
            if key == "accommodations":
                return {"stu-1": {
                    "presets": ["simplified_language"],
                    "custom_notes": "Extra time",
                }}
            if key == "accommodation_presets":
                return None  # use defaults
            return None

        with patch(
            "backend.accommodations._storage_load",
            side_effect=loader,
        ):
            from backend.accommodations import build_accommodation_prompt
            prompt = build_accommodation_prompt("stu-1")
        assert "ACCOMMODATION INSTRUCTIONS" in prompt
        assert "SIMPLIFIED LANGUAGE" in prompt
        assert "Extra time" in prompt


# ──────────────────────────────────────────────────────────────────
# _find_student_accommodation + build_prompt_from_presets +
# build_prompt_from_student_accommodations + get_delivery_accommodations
# ──────────────────────────────────────────────────────────────────


class TestFindStudentAccommodation:
    def test_empty_inputs_return_none(self):
        from backend.accommodations import _find_student_accommodation
        assert _find_student_accommodation("", {}) is None
        assert _find_student_accommodation("Jane", {}) is None
        assert _find_student_accommodation(None, {"x": "y"}) is None

    def test_exact_match(self):
        from backend.accommodations import _find_student_accommodation
        accs = {"Jane Doe": {"presets": ["a"]}}
        assert _find_student_accommodation(
            "Jane Doe", accs,
        )["presets"] == ["a"]

    def test_case_insensitive_normalized_lookup(self):
        from backend.accommodations import _find_student_accommodation
        # Exact-key miss → falls into the case-insensitive scan
        accs = {"  jane DOE  ": {"presets": ["a"]}}
        assert _find_student_accommodation(
            "Jane Doe", accs,
        )["presets"] == ["a"]

    def test_no_normalized_match_returns_none(self):
        from backend.accommodations import _find_student_accommodation
        accs = {"Other Name": {"presets": ["a"]}}
        assert _find_student_accommodation("Jane Doe", accs) is None


class TestBuildPromptFromPresets:
    def test_empty_inputs_return_empty(self, tmp_paths):
        from backend.accommodations import build_prompt_from_presets
        # Both preset_ids and custom_notes empty → ""
        assert build_prompt_from_presets([]) == ""

    def test_only_delivery_presets_skipped_returns_empty(self, tmp_paths):
        # delivery-type presets are filtered out; if all are delivery
        # AND no custom_notes → empty
        with patch(
            "backend.accommodations.load_presets",
            return_value={
                "deliv-1": {"id": "deliv-1", "type": "delivery",
                            "ai_instructions": "ui only"},
            },
        ):
            from backend.accommodations import build_prompt_from_presets
            assert build_prompt_from_presets(["deliv-1"]) == ""

    def test_ai_preset_with_instructions_renders(self, tmp_paths):
        with patch(
            "backend.accommodations.load_presets",
            return_value={
                "ai-1": {"id": "ai-1",
                         "ai_instructions": "DO X"},
            },
        ):
            from backend.accommodations import build_prompt_from_presets
            prompt = build_prompt_from_presets(["ai-1"])
        assert "ACCOMMODATION INSTRUCTIONS" in prompt
        assert "DO X" in prompt

    def test_custom_notes_alone_render(self, tmp_paths):
        with patch(
            "backend.accommodations.load_presets",
            return_value={},
        ):
            from backend.accommodations import build_prompt_from_presets
            prompt = build_prompt_from_presets(
                [], custom_notes="Special accommodation",
            )
        assert "Special accommodation" in prompt
        assert "ADDITIONAL ACCOMMODATION NOTES" in prompt


class TestBuildPromptFromStudentAccommodations:
    def test_unknown_student_returns_empty(self):
        from backend.accommodations import (
            build_prompt_from_student_accommodations,
        )
        assert build_prompt_from_student_accommodations(
            "Nobody", {"Other": {"presets": []}},
        ) == ""

    def test_found_student_renders_prompt(self, tmp_paths):
        with patch(
            "backend.accommodations.load_presets",
            return_value={
                "preset-1": {"id": "preset-1",
                             "ai_instructions": "TEST INSTR"},
            },
        ):
            from backend.accommodations import (
                build_prompt_from_student_accommodations,
            )
            prompt = build_prompt_from_student_accommodations(
                "Jane Doe",
                {"Jane Doe": {"presets": ["preset-1"]}},
            )
        assert "TEST INSTR" in prompt


class TestGetDeliveryAccommodations:
    def test_unknown_student_returns_empty_list(self):
        from backend.accommodations import get_delivery_accommodations
        assert get_delivery_accommodations(
            "Nobody", {"Other": {"presets": ["x"]}},
        ) == []

    def test_returns_only_delivery_type_presets(self):
        # Patch DEFAULT_PRESETS to mark some as delivery type
        from backend.accommodations import get_delivery_accommodations
        with patch(
            "backend.accommodations.DEFAULT_PRESETS",
            {
                "ai-only": {"id": "ai-only", "type": "ai"},
                "delivery-1": {"id": "delivery-1", "type": "delivery"},
                "delivery-2": {"id": "delivery-2", "type": "delivery"},
            },
        ):
            result = get_delivery_accommodations(
                "Jane Doe",
                {"Jane Doe": {
                    "presets": ["ai-only", "delivery-1", "delivery-2"],
                }},
            )
        # Only delivery-type presets returned
        assert "ai-only" not in result
        assert "delivery-1" in result
        assert "delivery-2" in result


# ──────────────────────────────────────────────────────────────────
# import_accommodations_from_csv
# ──────────────────────────────────────────────────────────────────


class TestImportFromCsv:
    def test_known_preset_name_matched(self, tmp_paths):
        rows = [
            {"id": "stu-1", "accom": "Simplified Language"},
        ]
        with patch(
            "backend.accommodations._storage_load",
            return_value=None,  # use defaults
        ), patch(
            "backend.accommodations._storage_save",
        ) as save_mock:
            from backend.accommodations import import_accommodations_from_csv
            stats = import_accommodations_from_csv(
                rows, "id", "accom",
            )
        assert stats["imported"] == 1
        # The save-student-accommodations call should map the preset_id
        saved = save_mock.call_args.args[1]
        assert saved["stu-1"]["presets"] == ["simplified_language"]

    def test_unknown_preset_falls_to_custom_notes(self, tmp_paths):
        rows = [
            {"id": "stu-1", "accom": "Magic Pixie Dust",
             "notes": "primary"},
        ]
        with patch(
            "backend.accommodations._storage_load",
            return_value=None,
        ), patch(
            "backend.accommodations._storage_save",
        ) as save_mock:
            from backend.accommodations import import_accommodations_from_csv
            stats = import_accommodations_from_csv(
                rows, "id", "accom", notes_col="notes",
            )
        assert stats["imported"] == 1
        saved = save_mock.call_args.args[1]
        # Unknown preset got appended to custom_notes
        notes = saved["stu-1"]["custom_notes"]
        assert "primary" in notes
        assert "magic pixie dust" in notes

    def test_unknown_preset_with_no_existing_notes(self, tmp_paths):
        rows = [{"id": "stu-1", "accom": "Magic Pixie Dust"}]
        with patch(
            "backend.accommodations._storage_load",
            return_value=None,
        ), patch(
            "backend.accommodations._storage_save",
        ) as save_mock:
            from backend.accommodations import import_accommodations_from_csv
            stats = import_accommodations_from_csv(
                rows, "id", "accom",
            )
        assert stats["imported"] == 1
        saved = save_mock.call_args.args[1]
        assert saved["stu-1"]["custom_notes"] == "magic pixie dust"

    def test_no_id_skipped(self, tmp_paths):
        rows = [
            {"id": "", "accom": "Simplified Language"},
            {"id": "stu-1", "accom": "Simplified Language"},
        ]
        with patch(
            "backend.accommodations._storage_load", return_value=None,
        ), patch(
            "backend.accommodations._storage_save",
        ):
            from backend.accommodations import import_accommodations_from_csv
            stats = import_accommodations_from_csv(rows, "id", "accom")
        assert stats["imported"] == 1
        assert stats["skipped"] == 1

    def test_no_content_skipped(self, tmp_paths):
        # accommodation_value AND custom_notes both empty → skipped
        rows = [{"id": "stu-1", "accom": "", "notes": ""}]
        with patch(
            "backend.accommodations._storage_load", return_value=None,
        ):
            from backend.accommodations import import_accommodations_from_csv
            stats = import_accommodations_from_csv(
                rows, "id", "accom", notes_col="notes",
            )
        assert stats["imported"] == 0
        assert stats["skipped"] == 1


# ──────────────────────────────────────────────────────────────────
# export / clear_all / stats
# ──────────────────────────────────────────────────────────────────


class TestExportClearStats:
    def test_export_returns_load_result(self, tmp_paths):
        data = {"stu-1": {"presets": ["a"]}}
        with patch(
            "backend.accommodations._storage_load", return_value=data,
        ):
            from backend.accommodations import export_student_accommodations
            assert export_student_accommodations() == data

    def test_clear_all_removes_file_and_clears_storage(self, tmp_paths):
        tmp_paths["student_file"].write_text(json.dumps({
            "stu-1": {"presets": ["x"]},
        }))
        save_mock = MagicMock()
        with patch(
            "backend.accommodations._storage_save", save_mock,
        ):
            from backend.accommodations import clear_all_accommodations
            ok = clear_all_accommodations()
        assert ok is True
        assert not tmp_paths["student_file"].exists()
        # Storage cleared with empty dict
        save_mock.assert_called_once()
        assert save_mock.call_args.args[1] == {}

    def test_clear_all_no_file_still_succeeds(self, tmp_paths):
        with patch(
            "backend.accommodations._storage_save",
        ):
            from backend.accommodations import clear_all_accommodations
            assert clear_all_accommodations() is True

    def test_clear_all_exception_returns_false(self, tmp_paths):
        tmp_paths["student_file"].write_text("{}")
        with patch(
            "os.remove", side_effect=OSError("perm"),
        ):
            from backend.accommodations import clear_all_accommodations
            assert clear_all_accommodations() is False

    def test_stats_aggregates_preset_usage(self, tmp_paths):
        mappings = {
            "stu-1": {"presets": ["simplified_language",
                                  "effort_focused"]},
            "stu-2": {"presets": ["simplified_language"]},
            "stu-3": {"presets": []},
        }

        def loader(key, tid):
            if key == "accommodations":
                return mappings
            return None

        with patch(
            "backend.accommodations._storage_load",
            side_effect=loader,
        ):
            from backend.accommodations import get_accommodation_stats
            stats = get_accommodation_stats()
        assert stats["total_students_with_accommodations"] == 3
        assert stats["preset_count"] >= 5  # default presets
        assert stats["preset_usage"]["simplified_language"] == 2
        assert stats["preset_usage"]["effort_focused"] == 1
