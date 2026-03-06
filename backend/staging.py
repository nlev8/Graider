"""
Staging Module — Single source of truth for filename canonicalization and dedup.

Before grading or listing files, copy assignments to a sibling staging folder
with clean canonical names. All downstream code reads from the staged folder.
"""
import json
import os
import re
import shutil
from pathlib import Path

SUPPORTED_EXTENSIONS = {'.docx', '.pdf', '.txt', '.jpg', '.jpeg', '.png'}
MANIFEST_NAME = '_staging_manifest.json'


def canonicalize_filename(filename):
    """Strip OneDrive duplicate suffixes from a filename.

    Handles: (1), (2), trailing bare digits, "- Copy", "- Copy 2".
    Preserves original casing and extension.

    Examples:
        'john_doe_Essay (1).docx'       -> 'john_doe_Essay.docx'
        'john_doe_Essay - Copy.docx'    -> 'john_doe_Essay.docx'
        'john_doe_Essay - Copy 2.docx'  -> 'john_doe_Essay.docx'
        'john_doe_Essay 2.docx'         -> 'john_doe_Essay.docx'
        'john_doe_Chapter_10_Notes.docx' -> 'john_doe_Chapter_10_Notes.docx'
    """
    stem, ext = os.path.splitext(filename)

    # Order matters: strip "- Copy" first, then parens, then trailing digits
    stem = re.sub(r'\s*-\s*[Cc]opy\s*\d*\s*$', '', stem)
    stem = re.sub(r'\s*\(\d+\)\s*$', '', stem)
    stem = re.sub(r'\s+\d{1,2}\s*$', '', stem)

    return stem.strip() + ext


def extract_student_and_assignment(filename):
    """Extract (student_key, assignment_key) from a *canonicalized* filename.

    Expects format: FirstName_LastName_AssignmentName.ext
    Also handles:   Last, First._AssignmentName.ext

    Returns lowercase tuple for dedup grouping.
    """
    name = os.path.splitext(filename)[0].lower()

    # Remove emojis / special chars for cleaner parsing
    name_clean = re.sub(r'[^\w\s_,-]', '', name)

    # Handle "Last, First._Assignment" (comma before first underscore)
    first_underscore = name_clean.find('_')
    if first_underscore > 0 and ',' in name_clean[:first_underscore]:
        name_part = name_clean[:first_underscore]
        assignment_part = name_clean[first_underscore + 1:] if first_underscore < len(name_clean) - 1 else ""
        comma_parts = name_part.split(',')
        last_name = comma_parts[0].strip()
        first_name = comma_parts[1].strip().split()[0] if len(comma_parts) > 1 else ""
        student_key = f"{first_name}_{last_name}".strip('_')
        assignment_key = re.sub(r'[_\s]+', '_', assignment_part.strip()).strip('_')
        return (student_key, assignment_key or "unknown")

    # Standard: split by underscores or spaces
    parts = re.split(r'[_\s]+', name_clean)
    parts = [p for p in parts if p]

    if len(parts) >= 3:
        student_key = f"{parts[0]}_{parts[1]}"
        assignment_key = '_'.join(parts[2:])
    elif len(parts) == 2:
        student_key = f"{parts[0]}_{parts[1]}"
        assignment_key = "unknown"
    else:
        student_key = name_clean
        assignment_key = "unknown"

    return (student_key, assignment_key)


def get_staging_folder(assignments_folder):
    """Return the path to the staging folder for a given assignments folder.

    Example: '/Users/me/Assignments' -> '/Users/me/Assignments_Staged'
    """
    folder = str(assignments_folder).rstrip(os.sep)
    return folder + '_Staged'


def _load_manifest(staging_folder):
    """Load the staging manifest, or return empty dict."""
    manifest_path = os.path.join(staging_folder, MANIFEST_NAME)
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_manifest(staging_folder, manifest):
    """Write the staging manifest."""
    manifest_path = os.path.join(staging_folder, MANIFEST_NAME)
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2)


def stage_files(assignments_folder, log_fn=None):
    """Stage assignment files: canonicalize names, deduplicate, copy to staging folder.

    Args:
        assignments_folder: Source folder with raw assignment files.
        log_fn: Optional callable for progress messages (e.g. grading_state["log"].append).

    Returns dict with:
        staging_folder: Path to the staging folder.
        staged_count: Number of files staged.
        duplicates_skipped: Number of duplicate files not staged.
        stale_removed: Number of stale staged files removed.
        resubmissions: Set of canonical filenames where a newer source replaced
                       a previously staged version (resubmission detected).
    """
    def log(msg):
        if log_fn:
            log_fn(msg)

    source = Path(assignments_folder)
    staging_folder = get_staging_folder(assignments_folder)
    os.makedirs(staging_folder, exist_ok=True)

    manifest = _load_manifest(staging_folder)

    # Phase 1: Scan source files
    source_files = []
    for f in source.iterdir():
        if not f.is_file():
            continue
        ext = f.suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            continue
        try:
            mtime = f.stat().st_mtime
        except OSError:
            continue
        source_files.append((f, mtime))

    # Phase 2: Canonicalize and deduplicate (keep newest per student+assignment)
    # Group by dedup key -> keep the source file with highest mtime
    groups = {}  # (student_key, assignment_key) -> (source_path, canonical_name, mtime)
    for f, mtime in source_files:
        canonical = canonicalize_filename(f.name)
        dedup_key = extract_student_and_assignment(canonical)

        existing = groups.get(dedup_key)
        if existing is None or mtime > existing[2]:
            groups[dedup_key] = (f, canonical, mtime)

    duplicates_skipped = len(source_files) - len(groups)

    if duplicates_skipped > 0:
        log(f"Found {duplicates_skipped} duplicate submissions, using most recent only")

    # Phase 3: Copy to staging folder (idempotent — skip unchanged files)
    staged_count = 0
    copied_count = 0
    resubmissions = set()
    canonical_names_in_use = set()

    for dedup_key, (src_path, canonical, mtime) in groups.items():
        canonical_names_in_use.add(canonical)
        dest = os.path.join(staging_folder, canonical)

        # Check manifest — skip if source unchanged
        prev = manifest.get(canonical)
        if prev and prev.get('source') == str(src_path) and prev.get('mtime') == mtime:
            if os.path.exists(dest):
                staged_count += 1
                continue

        # Resubmission: manifest had this canonical name but from a different
        # source file AND file size changed (student uploaded a newer version).
        # Mtime-only changes (OneDrive sync) are NOT resubmissions.
        if prev:
            source_changed = prev.get('source') != str(src_path)
            mtime_changed = prev.get('mtime') != mtime
            # Compare file sizes to detect actual content change vs OneDrive mtime touch
            prev_size = prev.get('size')  # None if old manifest without size
            try:
                curr_size = src_path.stat().st_size
            except OSError:
                curr_size = None
            # Only count as resubmission if size is known and actually changed
            size_changed = (prev_size is not None and curr_size is not None
                           and prev_size != curr_size)
            if source_changed or (mtime_changed and size_changed):
                resubmissions.add(canonical)

        # Copy with metadata preserved (mtime for late-penalty)
        shutil.copy2(str(src_path), dest)
        try:
            file_size = src_path.stat().st_size
        except OSError:
            file_size = -1
        manifest[canonical] = {
            'source': str(src_path),
            'mtime': mtime,
            'size': file_size,
            'staged_at': os.path.getmtime(dest),
        }
        staged_count += 1
        copied_count += 1

    # Phase 4: Remove stale staged files (no longer in source or lost dedup)
    stale_removed = 0
    stale_keys = [k for k in manifest if k not in canonical_names_in_use]
    for key in stale_keys:
        stale_path = os.path.join(staging_folder, key)
        if os.path.exists(stale_path):
            os.remove(stale_path)
            stale_removed += 1
        del manifest[key]

    # Also remove any files in staging folder that aren't in manifest
    for f in os.listdir(staging_folder):
        if f == MANIFEST_NAME:
            continue
        if f not in canonical_names_in_use:
            try:
                os.remove(os.path.join(staging_folder, f))
                stale_removed += 1
            except OSError:
                pass

    if stale_removed > 0:
        log(f"Removed {stale_removed} stale staged file(s)")

    _save_manifest(staging_folder, manifest)

    if copied_count > 0:
        log(f"Staged {copied_count} new/updated file(s)")

    if resubmissions:
        log(f"Detected {len(resubmissions)} resubmission(s) — newer versions staged")

    return {
        'staging_folder': staging_folder,
        'staged_count': staged_count,
        'duplicates_skipped': duplicates_skipped,
        'stale_removed': stale_removed,
        'resubmissions': resubmissions,
    }
