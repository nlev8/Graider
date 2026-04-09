"""Tests for send-tool user-message name guard."""

import pytest


class TestExtractUserMessageNames:
    """Tests for _extract_message_names — pulling potential student names from user text."""

    def test_extracts_full_name(self):
        from backend.routes.assistant_routes import _extract_message_names
        names = _extract_message_names("draft an email to Charles Cavanaugh's parents about his behavior")
        assert any("charles" in n for n in names)
        assert any("cavanaugh" in n for n in names)

    def test_extracts_name_with_possessive(self):
        from backend.routes.assistant_routes import _extract_message_names
        names = _extract_message_names("email Troy Mikell's mother")
        assert any("troy" in n for n in names)
        assert any("mikell" in n for n in names)

    def test_returns_empty_for_no_names(self):
        from backend.routes.assistant_routes import _extract_message_names
        names = _extract_message_names("yes send it")
        assert names == []

    def test_returns_empty_for_generic_confirmation(self):
        from backend.routes.assistant_routes import _extract_message_names
        names = _extract_message_names("looks good, send now")
        assert names == []

    def test_ignores_common_words(self):
        from backend.routes.assistant_routes import _extract_message_names
        # "Dear" and "Please" are capitalized but not student names
        names = _extract_message_names("Dear teacher, Please send the email")
        assert "dear" not in names
        assert "please" not in names

    def test_extracts_name_after_preposition(self):
        from backend.routes.assistant_routes import _extract_message_names
        names = _extract_message_names("send a message to London Samuel about missing work")
        assert any("london" in n for n in names)
        assert any("samuel" in n for n in names)

    def test_handles_multiple_names(self):
        from backend.routes.assistant_routes import _extract_message_names
        names = _extract_message_names("email Charles Cavanaugh and London Samuel's parents")
        assert any("charles" in n for n in names)
        assert any("london" in n for n in names)

    def test_extracts_lowercase_names(self):
        from backend.routes.assistant_routes import _extract_message_names
        names = _extract_message_names("email charles cavanaugh's parents about his behavior")
        assert "charles" in names
        assert "cavanaugh" in names

    def test_extracts_allcaps_names(self):
        from backend.routes.assistant_routes import _extract_message_names
        names = _extract_message_names("EMAIL CHARLES CAVANAUGH'S PARENTS")
        assert "charles" in names
        assert "cavanaugh" in names

    def test_extracts_unicode_names(self):
        from backend.routes.assistant_routes import _extract_message_names
        names = _extract_message_names("email José Ángela's parents")
        assert any("jos" in n for n in names)
        assert any("ngela" in n for n in names)


class TestNameOverlapCheck:
    """Tests for _student_name_in_message — checking if a tool's student name overlaps with user message names."""

    def test_matching_name_returns_true(self):
        from backend.routes.assistant_routes import _student_name_in_message
        assert _student_name_in_message("Charles Cavanaugh", "email Charles Cavanaugh's parents about defiance") is True

    def test_mismatched_name_returns_false(self):
        from backend.routes.assistant_routes import _student_name_in_message
        assert _student_name_in_message("Troy Jaxson Mikell", "email Charles Cavanaugh's parents about defiance") is False

    def test_partial_name_match(self):
        from backend.routes.assistant_routes import _student_name_in_message
        # User says "Charles" only, tool has full name
        assert _student_name_in_message("Charles Cavanaugh", "email Charles about his behavior") is True

    def test_skips_check_for_confirmations(self):
        from backend.routes.assistant_routes import _student_name_in_message
        # "yes" / "send it" — no names in message, should return True (skip check)
        assert _student_name_in_message("Troy Mikell", "yes send it") is True

    def test_skips_check_for_short_messages(self):
        from backend.routes.assistant_routes import _student_name_in_message
        assert _student_name_in_message("Troy Mikell", "looks good") is True

    def test_case_insensitive(self):
        from backend.routes.assistant_routes import _student_name_in_message
        assert _student_name_in_message("charles cavanaugh", "Email CHARLES CAVANAUGH's parents") is True

    def test_name_with_middle_name(self):
        from backend.routes.assistant_routes import _student_name_in_message
        # User says "Troy Mikell", tool uses full "Troy Jaxson Mikell"
        assert _student_name_in_message("Troy Jaxson Mikell", "email Troy Mikell's parents") is True

    def test_lowercase_message_blocks_wrong_student(self):
        from backend.routes.assistant_routes import _student_name_in_message
        # Previously this returned True (bypass) because lowercase names weren't extracted
        assert _student_name_in_message("Troy Mikell", "email charles cavanaugh's parents") is False

    def test_lowercase_message_allows_correct_student(self):
        from backend.routes.assistant_routes import _student_name_in_message
        assert _student_name_in_message("Charles Cavanaugh", "email charles cavanaugh's parents") is True

    def test_unicode_name_matches(self):
        from backend.routes.assistant_routes import _student_name_in_message
        # "Ángela" starts with a non-ASCII char; old [A-Za-z]+ strips it to "ngela"
        # which doesn't match the Unicode-extracted "ángela" from the message
        assert _student_name_in_message("Ángela Ñoño", "email Ángela Ñoño's parents about her grades") is True

    def test_unicode_name_blocks_mismatch(self):
        from backend.routes.assistant_routes import _student_name_in_message
        assert _student_name_in_message("Ángela Ñoño", "email Charles Cavanaugh's parents") is False
