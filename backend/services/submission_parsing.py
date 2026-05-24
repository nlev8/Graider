"""Submission parsing for the grading pipeline: extract student info from a
filename (and, later, read submission file contents). Pure logic (pathlib +
strings — no LLM / network / Flask) extracted from assignment_grader.py.
Wave 7 Slice 6 (grading-engine decomposition).
"""
from pathlib import Path


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
