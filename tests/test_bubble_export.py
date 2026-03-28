"""Unit tests for bubble answer sheet export."""
import pytest


class TestNormalizeAnswer:
    def test_letter(self):
        from backend.services.worksheet_generator import _normalize_correct_answer_to_letter
        assert _normalize_correct_answer_to_letter('B', ['A) X', 'B) Y']) == 'B'

    def test_letter_lowercase(self):
        from backend.services.worksheet_generator import _normalize_correct_answer_to_letter
        assert _normalize_correct_answer_to_letter('c', ['A) X', 'B) Y', 'C) Z']) == 'C'

    def test_letter_paren(self):
        from backend.services.worksheet_generator import _normalize_correct_answer_to_letter
        assert _normalize_correct_answer_to_letter('C)', ['A) X', 'B) Y', 'C) Z']) == 'C'

    def test_full_text(self):
        from backend.services.worksheet_generator import _normalize_correct_answer_to_letter
        result = _normalize_correct_answer_to_letter(
            'Paris', ['A) London', 'B) Berlin', 'C) Paris', 'D) Madrid'])
        assert result == 'C'

    def test_no_match(self):
        from backend.services.worksheet_generator import _normalize_correct_answer_to_letter
        assert _normalize_correct_answer_to_letter('XYZ', ['A) One', 'B) Two']) is None

    def test_index_zero_based(self):
        from backend.services.worksheet_generator import _normalize_correct_answer_to_letter
        assert _normalize_correct_answer_to_letter('1', ['A) X', 'B) Y', 'C) Z']) == 'B'

    def test_empty_answer(self):
        from backend.services.worksheet_generator import _normalize_correct_answer_to_letter
        assert _normalize_correct_answer_to_letter('', ['A) X']) is None

    def test_empty_options(self):
        from backend.services.worksheet_generator import _normalize_correct_answer_to_letter
        assert _normalize_correct_answer_to_letter('B', []) is None


class TestAddBubbleRow:
    def test_empty_bubbles_mc(self):
        from docx import Document
        from backend.services.worksheet_generator import _add_bubble_row
        doc = Document()
        para = _add_bubble_row(doc, 1, ['A', 'B', 'C', 'D'])
        text = para.text
        assert '1.' in text
        assert 'A' in text
        assert 'D' in text
        assert '\u25CB' in text  # empty circles
        assert '\u25CF' not in text  # no filled

    def test_filled_bubble_mc_letter(self):
        from docx import Document
        from backend.services.worksheet_generator import _add_bubble_row
        doc = Document()
        para = _add_bubble_row(doc, 1, ['A', 'B', 'C', 'D'], correct_answer='B',
                               option_texts=['A) 3', 'B) 4', 'C) 5', 'D) 6'])
        text = para.text
        assert text.count('\u25CF') == 1

    def test_filled_bubble_mc_full_text(self):
        from docx import Document
        from backend.services.worksheet_generator import _add_bubble_row
        doc = Document()
        para = _add_bubble_row(doc, 1, ['A', 'B', 'C', 'D'],
                               correct_answer='Declaration of Independence',
                               option_texts=['A) Constitution', 'B) Declaration of Independence',
                                             'C) Bill of Rights', 'D) Magna Carta'])
        text = para.text
        assert text.count('\u25CF') == 1

    def test_empty_bubbles_tf(self):
        from docx import Document
        from backend.services.worksheet_generator import _add_bubble_row
        doc = Document()
        para = _add_bubble_row(doc, 5, ['True', 'False'], is_tf=True)
        text = para.text
        assert 'True' in text
        assert 'False' in text
        assert '\u25CF' not in text

    def test_filled_bubble_tf(self):
        from docx import Document
        from backend.services.worksheet_generator import _add_bubble_row
        doc = Document()
        para = _add_bubble_row(doc, 5, ['True', 'False'], correct_answer='True', is_tf=True)
        text = para.text
        assert text.count('\u25CF') == 1

    def test_no_match_no_fill(self):
        from docx import Document
        from backend.services.worksheet_generator import _add_bubble_row
        doc = Document()
        para = _add_bubble_row(doc, 1, ['A', 'B', 'C', 'D'],
                               correct_answer='Nonsense',
                               option_texts=['A) One', 'B) Two', 'C) Three', 'D) Four'])
        text = para.text
        assert '\u25CF' not in text


class TestAddAnswerKeyPage:
    def test_answer_key_has_header(self):
        from docx import Document
        from backend.services.worksheet_generator import _add_answer_key_page
        doc = Document()
        questions = [
            {"number": 1, "options": ["A", "B", "C", "D"], "correct_answer": "B",
             "is_tf": False, "option_texts": ["A) X", "B) Y", "C) Z", "D) W"]},
            {"number": 2, "options": ["True", "False"], "correct_answer": "True", "is_tf": True},
        ]
        _add_answer_key_page(doc, questions)
        full_text = "\n".join(p.text for p in doc.paragraphs)
        assert "ANSWER KEY" in full_text

    def test_answer_key_empty_list(self):
        from docx import Document
        from backend.services.worksheet_generator import _add_answer_key_page
        doc = Document()
        _add_answer_key_page(doc, [])
        assert len(doc.paragraphs) == 0

    def test_answer_key_has_filled_bubbles(self):
        from docx import Document
        from backend.services.worksheet_generator import _add_answer_key_page
        doc = Document()
        questions = [
            {"number": 1, "options": ["A", "B", "C", "D"], "correct_answer": "C",
             "is_tf": False, "option_texts": ["A) X", "B) Y", "C) Z", "D) W"]},
        ]
        _add_answer_key_page(doc, questions)
        full_text = "\n".join(p.text for p in doc.paragraphs)
        assert '\u25CF' in full_text
