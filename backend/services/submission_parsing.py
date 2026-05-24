"""Submission parsing for the grading pipeline: extract student info from a
filename + read submission file contents. Flask-free (pathlib / base64 / file I/O —
no LLM / network) extracted from assignment_grader.py. Wave 7 (grading-engine
decomposition). Diagnostic output uses the module logger (the grader's debug prints
became _logger calls on extraction — return values are unchanged).
"""
import logging
from pathlib import Path

_logger = logging.getLogger(__name__)


def parse_filename(filename: str) -> dict:
    """
    Parse student info from filename.

    Expected formats:
        FirstName_LastName_AssignmentName.docx
        Last, First M._AssignmentName.docx
    Examples:
        A'kareah_West_Cornell Notes_ Political Parties.docx
        Eli_Long_Hamilton_Jefferson_Graphic_Organizer.docx
        Deloach, Rylee M._Washington_Stations_Handout.docx

    Returns: {"first_name": ..., "last_name": ..., "assignment_part": ...}
    """
    # Remove extension
    name = Path(filename).stem

    # Handle "Last, First M._Assignment" format (comma before first underscore)
    first_underscore = name.find('_')
    if first_underscore > 0 and ',' in name[:first_underscore]:
        name_part = name[:first_underscore]
        assignment_part = name[first_underscore + 1:] if first_underscore < len(name) - 1 else ""
        comma_parts = name_part.split(',')
        last_name = comma_parts[0].strip()
        # First name may include middle initial like "Rylee M."
        first_full = comma_parts[1].strip() if len(comma_parts) > 1 else ""
        first_name = first_full.split()[0] if first_full else ""

        # Strip apostrophes/curly quotes so Da'Juan matches Dajuan
        key = f"{first_name} {last_name}".lower()
        key = key.replace("'", "").replace("\u2019", "")
        return {
            "first_name": first_name,
            "last_name": last_name,
            "assignment_part": assignment_part,
            "lookup_key": key
        }

    # Standard format: FirstName_LastName_AssignmentName
    parts = name.split('_')

    if len(parts) >= 2:
        first_name = parts[0].strip()
        last_name = parts[1].strip()
        assignment_part = '_'.join(parts[2:]) if len(parts) > 2 else ""

        # Strip apostrophes/curly quotes so Da'Juan matches Dajuan
        key = f"{first_name} {last_name}".lower()
        key = key.replace("'", "").replace("\u2019", "")
        return {
            "first_name": first_name,
            "last_name": last_name,
            "assignment_part": assignment_part,
            "lookup_key": key
        }
    else:
        # Can't parse - return filename as-is
        return {
            "first_name": name,
            "last_name": "",
            "assignment_part": "",
            "lookup_key": name.lower().replace("'", "").replace("\u2019", "")
        }


def read_image_file(filepath: str) -> dict:
    """
    Read an image file and return it as base64 for GPT-4o vision.

    Returns dict with:
    - type: "image"
    - data: base64 encoded image
    - media_type: image MIME type
    """
    import base64

    filepath = Path(filepath)
    extension = filepath.suffix.lower()

    # Map extensions to MIME types
    mime_types = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.webp': 'image/webp'
    }

    if extension not in mime_types:
        _logger.warning("Unsupported image type: %s", extension)
        return None

    try:
        with open(filepath, 'rb') as f:
            image_data = base64.b64encode(f.read()).decode('utf-8')

        return {
            "type": "image",
            "data": image_data,
            "media_type": mime_types[extension]
        }
    except Exception as e:
        _logger.warning("Error reading image: %s", e)
        return None


def read_docx_file(filepath: str) -> str:
    """
    Read text content from a Word document (.docx) in document order.
    This properly interleaves paragraphs and tables as they appear.
    """
    try:
        from docx import Document
        from docx.table import Table
        from docx.text.paragraph import Paragraph
    except ImportError:
        _logger.error("python-docx not installed. Run: pip install python-docx")
        return None

    try:
        doc = Document(filepath)
        full_text = []

        # Iterate through document body elements in order
        # This ensures tables and paragraphs appear in their actual document order
        for element in doc.element.body:
            # Check if it's a paragraph
            if element.tag.endswith('p'):
                para = Paragraph(element, doc)
                if para.text.strip():
                    full_text.append(para.text)
            # Check if it's a table
            elif element.tag.endswith('tbl'):
                table = Table(element, doc)
                for row in table.rows:
                    row_text = []
                    for cell in row.cells:
                        if cell.text.strip():
                            row_text.append(cell.text.strip())
                    if row_text:
                        full_text.append(' | '.join(row_text))

        return '\n'.join(full_text)
    except Exception as e:
        _logger.warning("Error reading file: %s", e)
        return None
