"""Behavior-pinning tests for backend/staging.py.

Phase 2 Task 6 PR-c-1. Per Codex Gate 1: deterministic file-system
canonicalization + manifest module, full behavior-pinning approach
(round-trip + edge cases), no smoke-only.
"""
import json
import os
import shutil
from pathlib import Path

import pytest

from backend.staging import (
    canonicalize_filename,
    extract_student_and_assignment,
    get_staging_folder,
    stage_files,
    MANIFEST_NAME,
    SUPPORTED_EXTENSIONS,
)


# ─────────────────────────────────────────────────────────────────
# canonicalize_filename
# ─────────────────────────────────────────────────────────────────

class TestCanonicalize:
    def test_strips_paren_suffix(self):
        assert canonicalize_filename("john_Essay (1).docx") == "john_Essay.docx"

    def test_strips_copy_suffix(self):
        assert canonicalize_filename("john_Essay - Copy.docx") == "john_Essay.docx"

    def test_strips_copy_with_number(self):
        assert canonicalize_filename("john_Essay - Copy 2.docx") == "john_Essay.docx"

    def test_strips_trailing_digit(self):
        assert canonicalize_filename("john_Essay 2.docx") == "john_Essay.docx"

    def test_preserves_internal_digits(self):
        # Chapter_10 must NOT be stripped — only trailing 1-2 digits
        assert canonicalize_filename("john_Chapter_10_Notes.docx") == "john_Chapter_10_Notes.docx"

    def test_preserves_extension(self):
        assert canonicalize_filename("john_Essay (1).pdf") == "john_Essay.pdf"

    def test_empty_filename_with_extension(self):
        # Edge: no stem
        assert canonicalize_filename(".docx") == ".docx"


# ─────────────────────────────────────────────────────────────────
# extract_student_and_assignment
# ─────────────────────────────────────────────────────────────────

class TestExtractStudentAndAssignment:
    def test_standard_three_part(self):
        student, assignment = extract_student_and_assignment("John_Doe_Essay1.docx")
        assert student == "john_doe"
        assert assignment == "essay1"

    def test_two_part_unknown_assignment(self):
        student, assignment = extract_student_and_assignment("John_Doe.docx")
        assert student == "john_doe"
        assert assignment == "unknown"

    def test_comma_first_format(self):
        # "Last, First._Assignment"
        student, assignment = extract_student_and_assignment("Doe, John._Essay.docx")
        assert "doe" in student.lower()
        assert "john" in student.lower()
        assert "essay" in assignment

    def test_strips_emojis(self):
        student, assignment = extract_student_and_assignment("John_Doe_Essay🎯.docx")
        assert student == "john_doe"
        assert "essay" in assignment

    def test_lowercase_normalization(self):
        student, _ = extract_student_and_assignment("JOHN_DOE_Essay.docx")
        assert student == "john_doe"


# ─────────────────────────────────────────────────────────────────
# get_staging_folder
# ─────────────────────────────────────────────────────────────────

class TestStagingFolderName:
    def test_basic_path(self):
        assert get_staging_folder("/tmp/Assignments") == "/tmp/Assignments_Staged"

    def test_strips_trailing_slash(self):
        assert get_staging_folder("/tmp/Assignments/") == "/tmp/Assignments_Staged"


# ─────────────────────────────────────────────────────────────────
# stage_files — behavior pinning
# ─────────────────────────────────────────────────────────────────

@pytest.fixture
def assignments_dir(tmp_path):
    """A clean assignments folder with sample files."""
    folder = tmp_path / "Assignments"
    folder.mkdir()
    return folder


def _write_file(folder: Path, name: str, content: str = "x") -> Path:
    p = folder / name
    p.write_text(content)
    return p


class TestStageFiles:
    def test_stages_unsupported_extensions_skipped(self, assignments_dir):
        _write_file(assignments_dir, "John_Doe_Essay.docx")
        _write_file(assignments_dir, "ignore_me.zip")  # unsupported
        result = stage_files(str(assignments_dir))
        assert result["staged_count"] == 1

    def test_canonicalizes_during_stage(self, assignments_dir):
        _write_file(assignments_dir, "John_Doe_Essay (1).docx", "v1")
        result = stage_files(str(assignments_dir))
        staged = os.listdir(result["staging_folder"])
        # Manifest plus the canonical file
        assert "John_Doe_Essay.docx" in staged
        assert "John_Doe_Essay (1).docx" not in staged

    def test_dedup_keeps_newest(self, assignments_dir):
        # Two files that canonicalize to the same name; older + newer
        old = _write_file(assignments_dir, "John_Doe_Essay (1).docx", "old")
        os.utime(old, (1_000_000_000, 1_000_000_000))
        newer = _write_file(assignments_dir, "John_Doe_Essay (2).docx", "new")
        os.utime(newer, (1_500_000_000, 1_500_000_000))
        result = stage_files(str(assignments_dir))
        assert result["duplicates_skipped"] == 1
        # Verify newer content was the one staged
        staged_path = Path(result["staging_folder"]) / "John_Doe_Essay.docx"
        assert staged_path.read_text() == "new"

    def test_idempotent_second_run_same_count(self, assignments_dir):
        _write_file(assignments_dir, "John_Doe_Essay.docx")
        first = stage_files(str(assignments_dir))
        second = stage_files(str(assignments_dir))
        assert first["staged_count"] == second["staged_count"] == 1
        # No new copy on second run
        assert second["resubmissions"] == set()

    def test_resubmission_detected_on_size_change(self, assignments_dir):
        # Initial submission
        f = _write_file(assignments_dir, "John_Doe_Essay.docx", "first version")
        os.utime(f, (1_000_000_000, 1_000_000_000))
        first = stage_files(str(assignments_dir))
        assert first["resubmissions"] == set()
        # Replace with bigger content + newer mtime
        f.write_text("substantially different content second version")
        os.utime(f, (1_500_000_000, 1_500_000_000))
        second = stage_files(str(assignments_dir))
        assert "John_Doe_Essay.docx" in second["resubmissions"]

    def test_mtime_only_change_not_resubmission(self, assignments_dir):
        # Same content but newer mtime (OneDrive sync) → not resubmission
        f = _write_file(assignments_dir, "John_Doe_Essay.docx", "same content")
        os.utime(f, (1_000_000_000, 1_000_000_000))
        first = stage_files(str(assignments_dir))
        os.utime(f, (1_500_000_000, 1_500_000_000))
        second = stage_files(str(assignments_dir))
        assert second["resubmissions"] == set()

    def test_stale_file_removed_when_source_deleted(self, assignments_dir):
        f = _write_file(assignments_dir, "John_Doe_Essay.docx")
        first = stage_files(str(assignments_dir))
        assert first["staged_count"] == 1
        # Delete source
        f.unlink()
        second = stage_files(str(assignments_dir))
        assert second["staged_count"] == 0
        assert second["stale_removed"] >= 1

    def test_manifest_persists_across_runs(self, assignments_dir):
        _write_file(assignments_dir, "John_Doe_Essay.docx")
        result = stage_files(str(assignments_dir))
        manifest_path = Path(result["staging_folder"]) / MANIFEST_NAME
        assert manifest_path.exists()
        manifest = json.loads(manifest_path.read_text())
        assert "John_Doe_Essay.docx" in manifest
        entry = manifest["John_Doe_Essay.docx"]
        assert "source" in entry
        assert "mtime" in entry
        assert "size" in entry

    def test_log_fn_invoked_on_dedup(self, assignments_dir):
        old = _write_file(assignments_dir, "John_Doe_Essay (1).docx", "old")
        os.utime(old, (1_000_000_000, 1_000_000_000))
        newer = _write_file(assignments_dir, "John_Doe_Essay (2).docx", "new")
        os.utime(newer, (1_500_000_000, 1_500_000_000))
        logs = []
        stage_files(str(assignments_dir), log_fn=logs.append)
        assert any("duplicate" in m.lower() for m in logs)

    def test_multiple_supported_extensions_dedup_by_student_assignment(self, assignments_dir):
        # Pinning current behavior: dedup key is (student, assignment),
        # extension is NOT part of the key. Multiple files for the same
        # student+assignment with different extensions collapse to 1
        # (newest mtime wins).
        for ext in [".docx", ".pdf", ".txt", ".jpg", ".png"]:
            _write_file(assignments_dir, f"John_Doe_Essay{ext}")
        result = stage_files(str(assignments_dir))
        assert result["staged_count"] == 1
        assert result["duplicates_skipped"] == 4

    def test_different_assignments_kept_separate(self, assignments_dir):
        _write_file(assignments_dir, "John_Doe_Essay.docx")
        _write_file(assignments_dir, "John_Doe_Worksheet.docx")
        _write_file(assignments_dir, "Jane_Doe_Essay.docx")
        result = stage_files(str(assignments_dir))
        assert result["staged_count"] == 3

    def test_corrupt_manifest_recovers(self, assignments_dir):
        # Pre-create staging with a corrupt manifest
        staging = Path(get_staging_folder(str(assignments_dir)))
        staging.mkdir()
        (staging / MANIFEST_NAME).write_text("not valid json {{{")
        _write_file(assignments_dir, "John_Doe_Essay.docx")
        # Should not raise — falls back to empty manifest
        result = stage_files(str(assignments_dir))
        assert result["staged_count"] == 1


# Sanity: SUPPORTED_EXTENSIONS contract
def test_supported_extensions_contract():
    """Pin the set so downstream code can rely on it."""
    assert ".docx" in SUPPORTED_EXTENSIONS
    assert ".pdf" in SUPPORTED_EXTENSIONS
    assert ".jpg" in SUPPORTED_EXTENSIONS
    assert ".jpeg" in SUPPORTED_EXTENSIONS
    assert ".png" in SUPPORTED_EXTENSIONS
    assert ".txt" in SUPPORTED_EXTENSIONS
