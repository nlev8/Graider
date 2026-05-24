"""Direct-import tests for the render helpers moved into planner_export (Wave 6 Slice 1)."""
import os
import tempfile


def test_export_study_guide_docx_writes_file():
    from backend.services.planner_export import _export_study_guide_docx
    sg = {"title": "Photosynthesis", "sections": [{"heading": "Intro", "content": "Plants make food."}]}
    path = os.path.join(tempfile.mkdtemp(), "sg.docx")
    _export_study_guide_docx(sg, path)
    assert os.path.exists(path) and os.path.getsize(path) > 0


def test_export_study_guide_pdf_writes_file():
    from backend.services.planner_export import _export_study_guide_pdf
    sg = {"title": "Photosynthesis", "sections": [{"heading": "Intro", "content": "Plants make food."}]}
    path = os.path.join(tempfile.mkdtemp(), "sg.pdf")
    _export_study_guide_pdf(sg, path)
    assert os.path.exists(path) and os.path.getsize(path) > 0


def test_export_flashcards_pdf_writes_file():
    from backend.services.planner_export import _export_flashcards_pdf
    cards = {"title": "Vocab", "cards": [{"front": "cat", "back": "feline"}]}
    path = os.path.join(tempfile.mkdtemp(), "fc.pdf")
    _export_flashcards_pdf(cards, path)
    assert os.path.exists(path) and os.path.getsize(path) > 0


def test_export_flashcards_docx_writes_file():
    from backend.services.planner_export import _export_flashcards_docx
    cards = {"title": "Vocab", "cards": [{"front": "cat", "back": "feline"}]}
    path = os.path.join(tempfile.mkdtemp(), "fc.docx")
    _export_flashcards_docx(cards, path)
    assert os.path.exists(path) and os.path.getsize(path) > 0
