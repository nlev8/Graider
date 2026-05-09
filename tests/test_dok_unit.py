"""Unit tests for backend/services/dok.py.

Audit MAJOR #4 sprint follow-up to PR #276. Targets the 1 uncovered LOC
(line 63 — `_derive_uniform_dok` returns None when a question entry
isn't a dict). Existing coverage came indirectly via
`tests/test_remediation.py`; this dedicated file pins the contract for
each function.

Per `feedback_codex_medium_effort_2026-05-09.md` and
`reference_gemini_cli_codex_fallback.md`: Codex is rate-limited; Gemini
3.1 Pro is the validated fallback reviewer.
"""
from __future__ import annotations

import pytest


# ──────────────────────────────────────────────────────────────────
# _validate_dok
# ──────────────────────────────────────────────────────────────────


class TestValidateDok:
    @pytest.mark.parametrize("value", [1, 2, 3, 4])
    def test_valid_int_returns_self(self, value):
        from backend.services.dok import _validate_dok
        assert _validate_dok(value) == value

    @pytest.mark.parametrize("value", [0, 5, -1, 99, 100])
    def test_out_of_range_int_returns_none(self, value):
        from backend.services.dok import _validate_dok
        assert _validate_dok(value) is None

    @pytest.mark.parametrize("value", ["1", "2", "3", "4"])
    def test_valid_string_int_returns_int(self, value):
        from backend.services.dok import _validate_dok
        assert _validate_dok(value) == int(value)

    @pytest.mark.parametrize("value", ["  3  ", "\t2\n", "1 "])
    def test_whitespace_padded_string_stripped(self, value):
        from backend.services.dok import _validate_dok
        assert _validate_dok(value) == int(value.strip())

    @pytest.mark.parametrize("value", ["0", "5", "10"])
    def test_out_of_range_string_returns_none(self, value):
        from backend.services.dok import _validate_dok
        assert _validate_dok(value) is None

    @pytest.mark.parametrize("value", ["abc", "1.5", "true", "DOK 3"])
    def test_non_numeric_string_returns_none(self, value):
        from backend.services.dok import _validate_dok
        assert _validate_dok(value) is None

    def test_empty_string_returns_none(self):
        from backend.services.dok import _validate_dok
        assert _validate_dok("") is None

    def test_whitespace_only_string_returns_none(self):
        from backend.services.dok import _validate_dok
        assert _validate_dok("   ") is None

    def test_bool_true_rejected(self):
        # bool is an int subclass; explicit rejection per docstring
        from backend.services.dok import _validate_dok
        assert _validate_dok(True) is None

    def test_bool_false_rejected(self):
        from backend.services.dok import _validate_dok
        assert _validate_dok(False) is None

    @pytest.mark.parametrize("value", [None, [1], {"dok": 3}, 1.5, 2.0])
    def test_other_types_return_none(self, value):
        from backend.services.dok import _validate_dok
        assert _validate_dok(value) is None


# ──────────────────────────────────────────────────────────────────
# _derive_uniform_dok
# ──────────────────────────────────────────────────────────────────


class TestDeriveUniformDok:
    def test_non_dict_content_returns_none(self):
        from backend.services.dok import _derive_uniform_dok
        assert _derive_uniform_dok(None) is None
        assert _derive_uniform_dok([]) is None
        assert _derive_uniform_dok("string") is None
        assert _derive_uniform_dok(42) is None

    def test_no_questions_key_returns_none(self):
        from backend.services.dok import _derive_uniform_dok
        assert _derive_uniform_dok({}) is None
        assert _derive_uniform_dok({"title": "no questions"}) is None

    def test_empty_questions_list_returns_none(self):
        from backend.services.dok import _derive_uniform_dok
        assert _derive_uniform_dok({"questions": []}) is None

    def test_questions_not_a_list_returns_none(self):
        from backend.services.dok import _derive_uniform_dok
        # `questions` is a dict / string / int / None — all reject
        assert _derive_uniform_dok({"questions": {"q1": {}}}) is None
        assert _derive_uniform_dok({"questions": "not a list"}) is None
        assert _derive_uniform_dok({"questions": None}) is None

    def test_non_dict_question_returns_none(self):
        # PR #277 gap-fill: hits line 63 — when a question entry is NOT a
        # dict, return None immediately. This is the only previously
        # uncovered line in the module.
        from backend.services.dok import _derive_uniform_dok
        # Mix valid dict question + non-dict entry → None
        assert _derive_uniform_dok({
            "questions": [{"dok": 3}, "not a dict question"],
        }) is None
        # All non-dict entries → None
        assert _derive_uniform_dok({
            "questions": [None, "string", 42, [1, 2]],
        }) is None
        # Single non-dict → None
        assert _derive_uniform_dok({"questions": ["just a string"]}) is None

    def test_all_uniform_dok_returns_value(self):
        from backend.services.dok import _derive_uniform_dok
        # 3 questions all DOK=3 → 3
        result = _derive_uniform_dok({
            "questions": [{"dok": 3}, {"dok": 3}, {"dok": 3}],
        })
        assert result == 3

    def test_mixed_dok_returns_none(self):
        from backend.services.dok import _derive_uniform_dok
        result = _derive_uniform_dok({
            "questions": [{"dok": 1}, {"dok": 2}, {"dok": 3}],
        })
        assert result is None

    def test_one_question_with_invalid_dok_returns_none(self):
        # Even if every other question agrees on DOK=2, a single invalid
        # entry collapses the whole thing to None.
        from backend.services.dok import _derive_uniform_dok
        assert _derive_uniform_dok({
            "questions": [{"dok": 2}, {"dok": "invalid"}, {"dok": 2}],
        }) is None

    def test_one_question_missing_dok_returns_none(self):
        from backend.services.dok import _derive_uniform_dok
        # `dok` key absent → q.get('dok') returns None → _validate_dok
        # returns None → uniform check fails
        assert _derive_uniform_dok({
            "questions": [{"dok": 2}, {"text": "no dok"}, {"dok": 2}],
        }) is None

    def test_string_dok_normalized_before_compare(self):
        # _validate_dok normalizes "3" → 3. So mixed string and int forms
        # of the same DOK level should still derive uniform.
        from backend.services.dok import _derive_uniform_dok
        assert _derive_uniform_dok({
            "questions": [{"dok": "3"}, {"dok": 3}, {"dok": 3}],
        }) == 3

    def test_single_question_uniform(self):
        # 1 question with valid DOK → that DOK
        from backend.services.dok import _derive_uniform_dok
        assert _derive_uniform_dok({"questions": [{"dok": 4}]}) == 4

    def test_all_dok_levels_supported(self):
        from backend.services.dok import _derive_uniform_dok
        for level in (1, 2, 3, 4):
            assert _derive_uniform_dok({
                "questions": [{"dok": level}, {"dok": level}],
            }) == level


# ──────────────────────────────────────────────────────────────────
# Module-level constants
# ──────────────────────────────────────────────────────────────────


class TestModuleConstants:
    def test_dok_options_is_1_through_4(self):
        from backend.services.dok import DOK_OPTIONS
        assert DOK_OPTIONS == (1, 2, 3, 4)

    def test_remediation_dok_default_is_none(self):
        from backend.services.dok import REMEDIATION_DOK_DEFAULT
        assert REMEDIATION_DOK_DEFAULT is None

    def test_dok_descriptions_keys_match_options(self):
        from backend.services.dok import DOK_DESCRIPTIONS, DOK_OPTIONS
        assert set(DOK_DESCRIPTIONS.keys()) == set(DOK_OPTIONS)

    def test_each_description_is_non_empty_string(self):
        from backend.services.dok import DOK_DESCRIPTIONS
        for level, desc in DOK_DESCRIPTIONS.items():
            assert isinstance(desc, str)
            assert len(desc) > 10
            # The Webb's DOK level names appear in each description
            level_words = {
                1: "Recall",
                2: "Skills",
                3: "Strategic",
                4: "Extended",
            }
            assert level_words[level] in desc
