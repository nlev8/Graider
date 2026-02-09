"""
Worksheet Generator Service
============================
Creates structured .docx worksheets with an invisible answer key layer.
The visible layer is what students see when printing. The invisible layer
contains the answer key as white 1pt text, readable by Graider's text
extraction but invisible on white paper.
"""

import os
import re
import json
from urllib.parse import quote

from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH


WORKSHEETS_DIR = os.path.expanduser("~/Downloads/Graider/Worksheets")
ASSIGNMENTS_DIR = os.path.expanduser("~/.graider_assignments")


def create_worksheet_docx(filepath, title, worksheet_type, vocab_terms,
                          questions, summary_prompt, summary_key_points,
                          total_points):
    """Create a .docx worksheet with visible student layer and invisible answer key.

    Args:
        filepath: Output path for the .docx file
        title: Worksheet title
        worksheet_type: One of 'cornell-notes', 'fill-in-blank', 'short-answer', 'vocabulary'
        vocab_terms: List of dicts with 'term' and 'definition' keys
        questions: List of dicts with 'question', 'expected_answer', 'points' keys
        summary_prompt: Instruction text for the summary section
        summary_key_points: List of strings - key points for a good summary
        total_points: Total point value of the worksheet
    """
    doc = Document()

    # === VISIBLE LAYER ===

    # Title
    heading = doc.add_heading(title, level=1)
    heading.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # Header fields (Name / Date / Period)
    for field in ['Name', 'Date', 'Period']:
        p = doc.add_paragraph()
        run = p.add_run(field + ': ')
        run.bold = True
        run.font.size = Pt(12)
        p.add_run('_' * 50)

    doc.add_paragraph()  # spacing

    # Vocabulary Section
    if vocab_terms:
        doc.add_heading('VOCABULARY', level=2)
        for item in vocab_terms:
            p = doc.add_paragraph()
            run = p.add_run(item.get('term', '') + ': ')
            run.bold = True
            run.font.size = Pt(11)
            p.add_run('_' * 60)

        doc.add_paragraph()  # spacing

    # Questions Section
    if questions:
        doc.add_heading('QUESTIONS', level=2)
        for i, q in enumerate(questions, 1):
            pts = q.get('points', 10)
            question_text = q.get('question', '')

            # Question line with point value
            p = doc.add_paragraph()
            run = p.add_run(str(i) + ') ')
            run.bold = True
            run.font.size = Pt(11)
            p.add_run(question_text)
            pts_run = p.add_run('  (' + str(pts) + ' pts)')
            pts_run.font.size = Pt(9)
            pts_run.font.color.rgb = RGBColor(128, 128, 128)

            # Response lines
            p = doc.add_paragraph()
            run = p.add_run('Response: ')
            run.bold = True
            run.font.size = Pt(11)
            p.add_run('_' * 55)
            doc.add_paragraph('_' * 65)
            doc.add_paragraph()  # spacing between questions

    # Summary Section
    if summary_prompt:
        doc.add_heading('SUMMARY', level=2)
        doc.add_paragraph(summary_prompt)
        for _ in range(5):
            doc.add_paragraph('_' * 70)

    # === INVISIBLE LAYER (answer key for AI grading) ===
    doc.add_page_break()
    answer_key_text = _build_answer_key(
        title, worksheet_type, vocab_terms, questions,
        summary_key_points, total_points
    )
    _add_invisible_text(doc, answer_key_text)

    doc.save(filepath)


def _add_invisible_text(doc, text):
    """Add white 1pt text that is invisible when printed but readable by text extraction."""
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.font.size = Pt(1)
    run.font.color.rgb = RGBColor(255, 255, 255)


def _build_answer_key(title, worksheet_type, vocab_terms, questions,
                      summary_key_points, total_points):
    """Build structured answer key text for the invisible layer."""
    lines = [
        "---GRAIDER_ANSWER_KEY_START---",
        "TITLE: " + title,
        "TYPE: " + worksheet_type,
        "TOTAL_POINTS: " + str(total_points),
        ""
    ]

    if vocab_terms:
        lines.append("VOCABULARY_ANSWERS:")
        for v in vocab_terms:
            lines.append("  " + v.get('term', '') + ": " + v.get('definition', ''))
        lines.append("")

    if questions:
        lines.append("QUESTION_ANSWERS:")
        for i, q in enumerate(questions, 1):
            lines.append("  Q" + str(i) + ": " + q.get('expected_answer', ''))
            lines.append("  Q" + str(i) + "_POINTS: " + str(q.get('points', 10)))
        lines.append("")

    if summary_key_points:
        lines.append("SUMMARY_KEY_POINTS:")
        for kp in summary_key_points:
            lines.append("  - " + kp)
        lines.append("")

    lines.append("---GRAIDER_ANSWER_KEY_END---")
    return "\n".join(lines)


def generate_worksheet(title, worksheet_type, vocab_terms=None, questions=None,
                       summary_prompt=None, summary_key_points=None,
                       total_points=100):
    """Generate a .docx worksheet and save its config to Builder.

    Returns dict with status, filepath, download_url, etc.
    """
    os.makedirs(WORKSHEETS_DIR, exist_ok=True)

    # Match naming convention used by assignment_routes.py (spaces, not underscores)
    safe_title = "".join(c for c in title if c.isalnum() or c in ' -_').strip()
    filename = safe_title + '.docx'
    filepath = os.path.join(WORKSHEETS_DIR, filename)

    create_worksheet_docx(
        filepath=filepath,
        title=title,
        worksheet_type=worksheet_type,
        vocab_terms=vocab_terms or [],
        questions=questions or [],
        summary_prompt=summary_prompt,
        summary_key_points=summary_key_points or [],
        total_points=total_points
    )

    # Save assignment config to Builder
    download_url = "/api/download-worksheet/" + quote(filename)
    config = _build_assignment_config(
        title, worksheet_type, vocab_terms or [], questions or [],
        summary_prompt, summary_key_points or [], total_points
    )
    config["worksheetDownloadUrl"] = download_url
    os.makedirs(ASSIGNMENTS_DIR, exist_ok=True)
    config_path = os.path.join(ASSIGNMENTS_DIR, safe_title + '.json')
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2)

    return {
        "status": "created",
        "filepath": filepath,
        "filename": filename,
        "download_url": "/api/download-worksheet/" + quote(filename),
        "saved_to_builder": True,
        "config_name": safe_title
    }


def _build_assignment_config(title, worksheet_type, vocab_terms, questions,
                             summary_prompt, summary_key_points, total_points):
    """Build a Builder-compatible assignment config from worksheet data."""
    rubric_map = {
        "cornell-notes": "cornell-notes",
        "fill-in-blank": "fill-in-blank",
        "short-answer": "standard",
        "vocabulary": "fill-in-blank"
    }

    markers = []
    if vocab_terms:
        markers.append("VOCABULARY")
    if questions:
        markers.append("QUESTIONS")
    if summary_prompt:
        markers.append("SUMMARY")

    # Build grading notes with answer key
    grading_notes_parts = []
    if vocab_terms:
        grading_notes_parts.append("VOCABULARY EXPECTED DEFINITIONS:")
        for v in vocab_terms:
            grading_notes_parts.append("- " + v.get('term', '') + ": " +
                                       v.get('definition', 'Accept reasonable definition'))
    if questions:
        grading_notes_parts.append("")
        grading_notes_parts.append("EXPECTED ANSWERS:")
        for i, q in enumerate(questions, 1):
            grading_notes_parts.append("- Q" + str(i) + ": " +
                                       q.get('expected_answer', ''))
    if summary_key_points:
        grading_notes_parts.append("")
        grading_notes_parts.append("SUMMARY SHOULD INCLUDE:")
        for kp in summary_key_points:
            grading_notes_parts.append("- " + kp)

    return {
        "title": title,
        "subject": "",
        "totalPoints": total_points,
        "instructions": "",
        "aliases": [],
        "customMarkers": markers,
        "excludeMarkers": [],
        "gradingNotes": "\n".join(grading_notes_parts),
        "responseSections": [],
        "rubricType": rubric_map.get(worksheet_type, "standard"),
        "customRubric": None,
        "useSectionPoints": False,
        "sectionTemplate": "Custom",
        "effortPoints": 15,
        "completionOnly": False,
        "countsTowardsGrade": True,
        "importedDoc": None,
        "worksheetDownloadUrl": None
    }
