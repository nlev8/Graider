"""Tests for accommodation prompt building from presets."""
import pytest


class TestBuildPromptFromPresets:
    """Test building accommodation prompts directly from preset data."""

    def test_builds_prompt_from_preset_ids(self):
        from backend.accommodations import build_prompt_from_presets
        result = build_prompt_from_presets(
            preset_ids=["simplified_language", "effort_focused"],
            custom_notes="",
        )
        assert "SIMPLIFIED LANGUAGE" in result
        assert "EFFORT-FOCUSED" in result

    def test_includes_custom_notes(self):
        from backend.accommodations import build_prompt_from_presets
        result = build_prompt_from_presets(
            preset_ids=[],
            custom_notes="This student needs extra time to process questions.",
        )
        assert "extra time to process" in result

    def test_empty_presets_returns_empty(self):
        from backend.accommodations import build_prompt_from_presets
        result = build_prompt_from_presets(preset_ids=[], custom_notes="")
        assert result == ""

    def test_unknown_preset_id_skipped(self):
        from backend.accommodations import build_prompt_from_presets
        result = build_prompt_from_presets(
            preset_ids=["simplified_language", "nonexistent_preset"],
            custom_notes="",
        )
        assert "SIMPLIFIED LANGUAGE" in result

    def test_delivery_presets_skipped_in_ai_prompt(self):
        from backend.accommodations import build_prompt_from_presets
        result = build_prompt_from_presets(
            preset_ids=["extended_time_1_5x", "large_text"],
            custom_notes="",
        )
        assert result == ""

    def test_mixed_presets_only_include_ai_ones(self):
        from backend.accommodations import build_prompt_from_presets
        result = build_prompt_from_presets(
            preset_ids=["simplified_language", "extended_time_1_5x"],
            custom_notes="",
        )
        assert "SIMPLIFIED LANGUAGE" in result
        assert "extended_time" not in result.lower()

    def test_delivery_presets_exist(self):
        from backend.accommodations import DEFAULT_PRESETS
        assert "extended_time_1_5x" in DEFAULT_PRESETS
        assert "extended_time_2x" in DEFAULT_PRESETS
        assert "extended_time_unlimited" in DEFAULT_PRESETS
        assert "large_text" in DEFAULT_PRESETS
        assert "read_aloud" in DEFAULT_PRESETS
        assert "reduced_distractions" in DEFAULT_PRESETS

    def test_delivery_presets_have_delivery_type(self):
        from backend.accommodations import DEFAULT_PRESETS
        for key in ["extended_time_1_5x", "extended_time_2x", "extended_time_unlimited",
                     "large_text", "read_aloud", "reduced_distractions"]:
            assert DEFAULT_PRESETS[key].get("type") == "delivery"


class TestBuildPromptFromStudentAccommodations:
    def test_finds_student_by_exact_name(self):
        from backend.accommodations import build_prompt_from_student_accommodations
        accom = {"Jane Doe": {"presets": ["simplified_language"], "custom_notes": ""}}
        result = build_prompt_from_student_accommodations("Jane Doe", accom)
        assert "SIMPLIFIED LANGUAGE" in result

    def test_finds_student_case_insensitive(self):
        from backend.accommodations import build_prompt_from_student_accommodations
        accom = {"Jane Doe": {"presets": ["effort_focused"], "custom_notes": ""}}
        result = build_prompt_from_student_accommodations("jane doe", accom)
        assert "EFFORT-FOCUSED" in result

    def test_returns_empty_for_unknown_student(self):
        from backend.accommodations import build_prompt_from_student_accommodations
        result = build_prompt_from_student_accommodations(
            "Unknown", {"Jane Doe": {"presets": ["simplified_language"]}}
        )
        assert result == ""

    def test_returns_empty_for_none(self):
        from backend.accommodations import build_prompt_from_student_accommodations
        assert build_prompt_from_student_accommodations("Jane", None) == ""
        assert build_prompt_from_student_accommodations("Jane", {}) == ""


class TestGetDeliveryAccommodations:
    def test_extracts_delivery_presets(self):
        from backend.accommodations import get_delivery_accommodations
        accom = {
            "Jane Doe": {
                "presets": ["simplified_language", "extended_time_1_5x", "large_text"],
                "custom_notes": "",
            },
        }
        delivery = get_delivery_accommodations("Jane Doe", accom)
        assert "extended_time_1_5x" in delivery
        assert "large_text" in delivery
        assert "simplified_language" not in delivery

    def test_returns_empty_for_no_delivery(self):
        from backend.accommodations import get_delivery_accommodations
        accom = {"Jane Doe": {"presets": ["simplified_language"], "custom_notes": ""}}
        assert get_delivery_accommodations("Jane Doe", accom) == []

    def test_returns_empty_for_unknown_student(self):
        from backend.accommodations import get_delivery_accommodations
        assert get_delivery_accommodations("Unknown", {"Jane": {"presets": ["large_text"]}}) == []
