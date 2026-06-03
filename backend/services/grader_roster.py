"""File-based roster loading for the grading pipeline: parse a student roster from
CSV or Excel into a name->info dict. Flask-free (csv / openpyxl / file I/O — no LLM)
extracted from assignment_grader.py. Wave 7 (grading-engine decomposition). Diagnostic
output uses the module logger (the grader's debug prints became _logger calls on
extraction — return values are unchanged).
"""
import json
import logging
import os
from pathlib import Path

_logger = logging.getLogger(__name__)


def load_roster(roster_path: str) -> dict:
    """
    Load student roster from Excel or CSV file.

    Excel format: Student, Student ID, Local ID, Email, Grade, Team
    CSV format: FirstName, LastName, StudentID, Email, Period

    Returns dict mapping "firstname lastname" (lowercase) -> student info
    """
    roster = {}

    if not Path(roster_path).exists():
        _logger.warning("Roster file not found: %s", roster_path)
        return {}

    roster_path_lower = roster_path.lower()

    # Handle CSV files
    if roster_path_lower.endswith('.csv'):
        import csv
        with open(roster_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Try various column name formats
                first_name = row.get('FirstName') or row.get('First Name') or row.get('first_name') or row.get('First') or ''
                last_name = row.get('LastName') or row.get('Last Name') or row.get('last_name') or row.get('Last') or ''
                student_id = row.get('StudentID') or row.get('Student ID') or row.get('student_id') or row.get('ID') or ''
                email = row.get('Email') or row.get('email') or ''
                period = row.get('Period') or row.get('period') or row.get('Class') or ''

                # If Student column exists with "Last; First" format
                if not first_name and not last_name:
                    student_col = row.get('Student') or row.get('Name') or ''
                    if ';' in student_col:
                        parts = student_col.split(';')
                        last_name = parts[0].strip()
                        first_name = parts[1].strip() if len(parts) > 1 else ''
                    elif ',' in student_col:
                        parts = student_col.split(',')
                        last_name = parts[0].strip()
                        first_name = parts[1].strip() if len(parts) > 1 else ''

                if not first_name and not last_name:
                    continue

                first_name_simple = first_name.split()[0] if first_name else ''
                lookup_key = f"{first_name_simple} {last_name}".lower().strip()

                entry = {
                    "student_id": str(student_id),
                    "student_name": f"{first_name} {last_name}".strip(),
                    "first_name": first_name,
                    "last_name": last_name,
                    "email": email or "",
                    "period": str(period) if period else ""
                }
                roster[lookup_key] = entry

                reverse_key = f"{last_name} {first_name_simple}".lower().strip()
                roster[reverse_key] = entry

                # Apostrophe-stripped key (e.g., "da'juan liverpool" → "dajuan liverpool")
                stripped_first = first_name_simple.replace("'", "").replace("\u2019", "")
                stripped_last = last_name.replace("'", "").replace("\u2019", "")
                if stripped_first != first_name_simple.lower() or stripped_last != last_name.lower():
                    apo_key = f"{stripped_first} {stripped_last}".lower().strip()
                    if apo_key not in roster:
                        roster[apo_key] = entry
                    apo_rev = f"{stripped_last} {stripped_first}".lower().strip()
                    if apo_rev not in roster:
                        roster[apo_rev] = entry

                # For compound last names ("Wilkins Reels"), also add key with just first part
                # so "Dicen_Wilkins" filename matches "Dicen Macheil Wilkins Reels"
                last_parts = last_name.split()
                if len(last_parts) > 1:
                    short_key = f"{first_name_simple} {last_parts[0]}".lower().strip()
                    if short_key not in roster:
                        roster[short_key] = entry
                    reverse_short = f"{last_parts[0]} {first_name_simple}".lower().strip()
                    if reverse_short not in roster:
                        roster[reverse_short] = entry

        _logger.info("Loaded %d students from CSV roster", len(set(id(v) for v in roster.values())))
        return roster

    # Handle Excel files
    try:
        import openpyxl
    except ImportError:
        _logger.error("openpyxl not installed. Run: pip install openpyxl")
        return {}

    wb = openpyxl.load_workbook(roster_path)
    sheet = wb.active

    # Get header row to find column indices
    headers = [str(cell.value).lower() if cell.value else '' for cell in sheet[1]]

    # Try to find period column
    period_col = None
    for i, h in enumerate(headers):
        if 'period' in h or 'class' in h or 'team' in h:
            period_col = i
            break

    # Skip header row
    for row in sheet.iter_rows(min_row=2, values_only=True):
        if not row[0]:
            continue

        student_name = row[0]
        student_id = row[1]
        email = row[3] if len(row) > 3 else ''
        period = row[period_col] if period_col is not None and len(row) > period_col else ''

        if ';' in str(student_name):
            parts = str(student_name).split(';')
            last_name = parts[0].strip()
            first_name = parts[1].strip() if len(parts) > 1 else ""
            first_name_simple = first_name.split()[0] if first_name else ""
        elif ',' in str(student_name):
            parts = str(student_name).split(',', 1)
            last_name = parts[0].strip()
            first_name = parts[1].strip() if len(parts) > 1 else ""
            first_name_simple = first_name.split()[0] if first_name else ""
        else:
            last_name = str(student_name)
            first_name = ""
            first_name_simple = ""

        lookup_key = f"{first_name_simple} {last_name}".lower().strip()

        entry = {
            "student_id": str(student_id),
            "student_name": f"{first_name} {last_name}".strip(),
            "first_name": first_name,
            "last_name": last_name,
            "email": email or "",
            "period": str(period) if period else ""
        }
        roster[lookup_key] = entry

        reverse_key = f"{last_name} {first_name_simple}".lower().strip()
        roster[reverse_key] = entry

        # Apostrophe-stripped key (e.g., "andre'a chavarria" → "andrea chavarria")
        import re as _re
        stripped_first = _re.sub(r"['\u2019]", '', first_name_simple)
        stripped_last = _re.sub(r"['\u2019]", '', last_name)
        if stripped_first != first_name_simple or stripped_last != last_name:
            apo_key = f"{stripped_first} {stripped_last}".lower().strip()
            if apo_key not in roster:
                roster[apo_key] = entry
            apo_rev = f"{stripped_last} {stripped_first}".lower().strip()
            if apo_rev not in roster:
                roster[apo_rev] = entry

        # For compound last names, add short key with just first part of last name
        last_parts = last_name.split()
        if len(last_parts) > 1:
            short_key = f"{first_name_simple} {last_parts[0]}".lower().strip()
            if short_key not in roster:
                roster[short_key] = entry
            reverse_short = f"{last_parts[0]} {first_name_simple}".lower().strip()
            if reverse_short not in roster:
                roster[reverse_short] = entry

        # For hyphenated last names (e.g., "Barnhart-Hunter" → also add "Barnhart")
        if '-' in last_name:
            hyph_parts = last_name.split('-')
            hyph_short = f"{first_name_simple} {hyph_parts[0]}".lower().strip()
            if hyph_short not in roster:
                roster[hyph_short] = entry
            hyph_rev = f"{hyph_parts[0]} {first_name_simple}".lower().strip()
            if hyph_rev not in roster:
                roster[hyph_rev] = entry
            # Also add space-separated variant ("Salvador-Guzman" → "Salvador Guzman")
            space_last = last_name.replace('-', ' ')
            space_key = f"{first_name_simple} {space_last}".lower().strip()
            if space_key not in roster:
                roster[space_key] = entry

    _logger.info("Loaded %d students from Excel roster", len(set(id(v) for v in roster.values())))

    # Supplement with period CSVs from Focus Import (adds students not in Excel roster)
    periods_dir = os.path.expanduser("~/.graider_data/periods")
    if os.path.exists(periods_dir):
        import csv as csv_mod
        added = 0
        for period_file in sorted(os.listdir(periods_dir)):
            if not period_file.endswith('.csv'):
                continue
            period_name = period_file.replace('.csv', '').replace('_', ' ')
            # Try to get period name from metadata
            meta_path = os.path.join(periods_dir, f"{period_file}.meta.json")
            if os.path.exists(meta_path):
                try:
                    with open(meta_path, 'r') as mf:
                        meta = json.load(mf)
                        period_name = meta.get('period_name', period_name)
                except Exception:
                    _logger.debug("period metadata read failed", exc_info=True)
            filepath = os.path.join(periods_dir, period_file)
            try:
                with open(filepath, 'r', encoding='utf-8') as fh:
                    reader = csv_mod.DictReader(fh)
                    for row in reader:
                        student_col = row.get('Student', row.get('Name', '')).strip().strip('"')
                        student_id = row.get('Student ID', '').strip().strip('"')
                        local_id = row.get('Local ID', '').strip().strip('"')

                        # Parse "Last, First" or "Last; First" format
                        first_name = ''
                        last_name = ''
                        for sep in [';', ',']:
                            if sep in student_col:
                                parts = student_col.split(sep, 1)
                                last_name = parts[0].strip()
                                first_name = parts[1].strip() if len(parts) > 1 else ''
                                break
                        if not first_name and not last_name:
                            continue

                        first_name_simple = first_name.split()[0] if first_name else ''
                        lookup_key = f"{first_name_simple} {last_name}".lower().strip()

                        # Also check apostrophe-stripped key for existing roster match
                        apo_lookup = lookup_key.replace("'", "").replace("\u2019", "")

                        # If already in roster from Excel, just fill in period if missing
                        if lookup_key in roster:
                            if not roster[lookup_key].get('period'):
                                roster[lookup_key]['period'] = period_name
                            continue
                        if apo_lookup != lookup_key and apo_lookup in roster:
                            if not roster[apo_lookup].get('period'):
                                roster[apo_lookup]['period'] = period_name
                            continue

                        email = f"{local_id}@vcs2go.net" if local_id else ""
                        entry = {
                            "student_id": str(student_id),
                            "student_name": f"{first_name} {last_name}".strip(),
                            "first_name": first_name,
                            "last_name": last_name,
                            "email": email,
                            "period": period_name
                        }
                        roster[lookup_key] = entry
                        reverse_key = f"{last_name} {first_name_simple}".lower().strip()
                        if reverse_key not in roster:
                            roster[reverse_key] = entry
                        # Apostrophe-stripped key
                        stripped_first = first_name_simple.replace("'", "").replace("\u2019", "")
                        stripped_last = last_name.replace("'", "").replace("\u2019", "")
                        if stripped_first != first_name_simple.lower() or stripped_last != last_name.lower():
                            apo_key = f"{stripped_first} {stripped_last}".lower().strip()
                            if apo_key not in roster:
                                roster[apo_key] = entry
                            apo_rev = f"{stripped_last} {stripped_first}".lower().strip()
                            if apo_rev not in roster:
                                roster[apo_rev] = entry
                        # Compound last name short keys
                        last_parts = last_name.split()
                        if len(last_parts) > 1:
                            short_key = f"{first_name_simple} {last_parts[0]}".lower().strip()
                            if short_key not in roster:
                                roster[short_key] = entry
                        added += 1
            except Exception:
                _logger.debug("roster CSV row parse failed", exc_info=True)
        if added:
            _logger.info("Supplemented with %d students from period CSVs", added)

    return roster


def build_roster_from_periods() -> dict:
    """Build a roster dict exclusively from period CSVs in ~/.graider_data/periods/.

    Returns the same dict format as load_roster():
      "firstname lastname" (lowercase) -> {student_id, student_name, first_name, last_name, email, period}

    Email is derived as {local_id}@vcs2go.net.
    """
    import csv as csv_mod
    import re as _re

    roster = {}
    periods_dir = os.path.expanduser("~/.graider_data/periods")
    if not os.path.exists(periods_dir):
        _logger.warning("No period CSVs found at ~/.graider_data/periods/")
        return {}

    for period_file in sorted(os.listdir(periods_dir)):
        if not period_file.endswith('.csv'):
            continue
        period_name = period_file.replace('.csv', '').replace('_', ' ')
        # Try to get period name from metadata
        meta_path = os.path.join(periods_dir, f"{period_file}.meta.json")
        if os.path.exists(meta_path):
            try:
                with open(meta_path, 'r') as mf:
                    meta = json.load(mf)
                    period_name = meta.get('period_name', period_name)
            except Exception:
                _logger.debug("period metadata read failed", exc_info=True)

        filepath = os.path.join(periods_dir, period_file)
        try:
            with open(filepath, 'r', encoding='utf-8') as fh:
                reader = csv_mod.DictReader(fh)
                for row in reader:
                    student_col = row.get('Student', row.get('Name', '')).strip().strip('"')
                    student_id = row.get('Student ID', '').strip().strip('"')
                    local_id = row.get('Local ID', '').strip().strip('"')

                    # Parse "Last, First" or "Last; First" format
                    first_name = ''
                    last_name = ''
                    for sep in [';', ',']:
                        if sep in student_col:
                            parts = student_col.split(sep, 1)
                            last_name = parts[0].strip()
                            first_name = parts[1].strip() if len(parts) > 1 else ''
                            break
                    if not first_name and not last_name:
                        continue

                    first_name_simple = first_name.split()[0] if first_name else ''
                    lookup_key = f"{first_name_simple} {last_name}".lower().strip()

                    email = f"{local_id}@vcs2go.net" if local_id else ""
                    entry = {
                        "student_id": str(student_id),
                        "student_name": f"{first_name} {last_name}".strip(),
                        "first_name": first_name,
                        "last_name": last_name,
                        "email": email,
                        "period": period_name
                    }
                    roster[lookup_key] = entry

                    # Reverse key
                    reverse_key = f"{last_name} {first_name_simple}".lower().strip()
                    if reverse_key not in roster:
                        roster[reverse_key] = entry

                    # Apostrophe-stripped key (straight ' and curly \u2019)
                    stripped_first = _re.sub(r"['\u2019]", '', first_name_simple)
                    stripped_last = _re.sub(r"['\u2019]", '', last_name)
                    if stripped_first != first_name_simple or stripped_last != last_name:
                        apo_key = f"{stripped_first} {stripped_last}".lower().strip()
                        if apo_key not in roster:
                            roster[apo_key] = entry
                        apo_rev = f"{stripped_last} {stripped_first}".lower().strip()
                        if apo_rev not in roster:
                            roster[apo_rev] = entry

                    # Compound last name short keys
                    last_parts = last_name.split()
                    if len(last_parts) > 1:
                        short_key = f"{first_name_simple} {last_parts[0]}".lower().strip()
                        if short_key not in roster:
                            roster[short_key] = entry
                        reverse_short = f"{last_parts[0]} {first_name_simple}".lower().strip()
                        if reverse_short not in roster:
                            roster[reverse_short] = entry

                    # Hyphenated last name keys
                    if '-' in last_name:
                        hyph_parts = last_name.split('-')
                        hyph_short = f"{first_name_simple} {hyph_parts[0]}".lower().strip()
                        if hyph_short not in roster:
                            roster[hyph_short] = entry
                        hyph_rev = f"{hyph_parts[0]} {first_name_simple}".lower().strip()
                        if hyph_rev not in roster:
                            roster[hyph_rev] = entry
                        space_last = last_name.replace('-', ' ')
                        space_key = f"{first_name_simple} {space_last}".lower().strip()
                        if space_key not in roster:
                            roster[space_key] = entry
        except Exception:
            _logger.debug("roster name-variant key build failed", exc_info=True)

    unique_count = len(set(id(v) for v in roster.values()))
    _logger.info("Built roster with %d students from period CSVs", unique_count)
    return roster
