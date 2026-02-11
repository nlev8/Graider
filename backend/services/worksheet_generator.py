"""
Worksheet Generator Service
============================
Creates structured .docx worksheets for students.
Expected answers are stored in the assignment config's gradingNotes field,
not embedded in the document itself.
"""

import os
import re
import json
from urllib.parse import quote

from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

from backend.services.document_generator import (
    _parse_markdown_runs, load_style, DEFAULT_STYLE, _apply_style_to_heading
)


WORKSHEETS_DIR = os.path.expanduser("~/Downloads/Graider/Worksheets")
ASSIGNMENTS_DIR = os.path.expanduser("~/.graider_assignments")


def create_worksheet_docx(filepath, title, worksheet_type, vocab_terms,
                          questions, summary_prompt, summary_key_points,
                          total_points, style=None):
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
        style: Optional style dict (from load_style). Uses DEFAULT_STYLE if None.
    """
    if style is None:
        style = dict(DEFAULT_STYLE)

    body_font = style.get("body_font_name", "Calibri")
    body_size = style.get("body_font_size", 11)

    doc = Document()

    # === VISIBLE LAYER ===

    # Title
    heading = doc.add_heading(title, level=1)
    heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for run in heading.runs:
        run.font.name = style.get("title_font_name", "Georgia")
        run.font.size = Pt(style.get("title_font_size", 24))
        run.bold = style.get("title_bold", True)

    # Header fields (Name / Date / Period)
    for field in ['Name', 'Date', 'Period']:
        p = doc.add_paragraph()
        run = p.add_run(field + ': ')
        run.bold = True
        run.font.size = Pt(12)
        run.font.name = body_font
        fill_run = p.add_run('_' * 50)
        fill_run.font.name = body_font

    doc.add_paragraph()  # spacing

    # Vocabulary Section
    if vocab_terms:
        vh = doc.add_heading('VOCABULARY', level=2)
        _apply_style_to_heading(vh, 2, style)
        for item in vocab_terms:
            p = doc.add_paragraph()
            term_text = item.get('term', '') + ': '
            run = p.add_run(term_text)
            run.bold = True
            run.font.size = Pt(body_size)
            run.font.name = body_font
            fill_run = p.add_run('_' * 60)
            fill_run.font.name = body_font

        doc.add_paragraph()  # spacing

    # Questions Section
    if questions:
        qh = doc.add_heading('QUESTIONS', level=2)
        _apply_style_to_heading(qh, 2, style)
        for i, q in enumerate(questions, 1):
            pts = q.get('points', 10)
            question_text = q.get('question', '')

            # Question line with point value
            p = doc.add_paragraph()
            num_run = p.add_run(str(i) + ') ')
            num_run.bold = True
            num_run.font.size = Pt(body_size)
            num_run.font.name = body_font
            _parse_markdown_runs(p, question_text, body_font, body_size)
            pts_run = p.add_run('  (' + str(pts) + ' pts)')
            pts_run.font.size = Pt(9)
            pts_run.font.name = body_font
            pts_run.font.color.rgb = RGBColor(128, 128, 128)

            # Response lines
            p = doc.add_paragraph()
            run = p.add_run('Response: ')
            run.bold = True
            run.font.size = Pt(body_size)
            run.font.name = body_font
            fill_run = p.add_run('_' * 55)
            fill_run.font.name = body_font
            line_p = doc.add_paragraph()
            line_run = line_p.add_run('_' * 65)
            line_run.font.name = body_font
            doc.add_paragraph()  # spacing between questions

    # Summary Section
    if summary_prompt:
        sh = doc.add_heading('SUMMARY', level=2)
        _apply_style_to_heading(sh, 2, style)
        sp = doc.add_paragraph()
        _parse_markdown_runs(sp, summary_prompt, body_font, body_size)
        for _ in range(5):
            line_p = doc.add_paragraph()
            line_run = line_p.add_run('_' * 70)
            line_run.font.name = body_font

    doc.save(filepath)


def _build_document_text(title, vocab_terms, questions, summary_prompt,
                         summary_key_points, total_points):
    """Build plain-text version of the worksheet matching what read_docx_file extracts.

    This is stored in importedDoc.text so Grading Setup can display the template
    and the grading engine can use it for template comparison.
    """
    lines = [title, '', 'Name: ' + '_' * 50, 'Date: ' + '_' * 50,
             'Period: ' + '_' * 50, '']

    if vocab_terms:
        lines.append('VOCABULARY')
        for item in vocab_terms:
            lines.append(item.get('term', '') + ': ' + '_' * 60)
        lines.append('')

    if questions:
        lines.append('QUESTIONS')
        for i, q in enumerate(questions, 1):
            pts = q.get('points', 10)
            lines.append(str(i) + ') ' + q.get('question', '') + '  (' + str(pts) + ' pts)')
            lines.append('Response: ' + '_' * 55)
            lines.append('_' * 65)
            lines.append('')

    if summary_prompt:
        lines.append('SUMMARY')
        lines.append(summary_prompt)
        for _ in range(5):
            lines.append('_' * 70)

    return '\n'.join(lines)


def generate_worksheet(title, worksheet_type, vocab_terms=None, questions=None,
                       summary_prompt=None, summary_key_points=None,
                       total_points=100, subject=None, style_name=None):
    """Generate a .docx worksheet and save its config to Grading Setup.

    Returns dict with status, filepath, download_url, etc.
    """
    os.makedirs(WORKSHEETS_DIR, exist_ok=True)

    # Load visual style
    style = load_style(style_name)

    # Match naming convention used by assignment_routes.py (spaces, not underscores)
    safe_title = "".join(c for c in title if c.isalnum() or c in ' -_').strip()
    filename = safe_title + '.docx'
    filepath = os.path.join(WORKSHEETS_DIR, filename)

    vterms = vocab_terms or []
    qs = questions or []
    skp = summary_key_points or []

    create_worksheet_docx(
        filepath=filepath,
        title=title,
        worksheet_type=worksheet_type,
        vocab_terms=vterms,
        questions=qs,
        summary_prompt=summary_prompt,
        summary_key_points=skp,
        total_points=total_points,
        style=style
    )

    # Build plain-text representation matching what read_docx_file extracts
    doc_text = _build_document_text(title, vterms, qs, summary_prompt, skp, total_points)

    # Save assignment config to Grading Setup
    download_url = "/api/download-worksheet/" + quote(filename)
    config = _build_assignment_config(
        title, worksheet_type, vterms, qs,
        summary_prompt, skp, total_points, subject
    )
    config["worksheetDownloadUrl"] = download_url
    config["importedDoc"] = {
        "text": doc_text,
        "html": "",
        "filename": filename,
        "loading": False
    }
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
        "config_name": safe_title,
        "style_used": style_name or "default",
    }


def _build_assignment_config(title, worksheet_type, vocab_terms, questions,
                             summary_prompt, summary_key_points, total_points,
                             subject=None):
    """Build a Grading Setup-compatible assignment config from worksheet data."""
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
        "subject": subject or "",
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
        "importedDoc": None,  # Populated by generate_worksheet() after file creation
        "worksheetDownloadUrl": None
    }
