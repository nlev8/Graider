"""Targeted coverage extension for backend/staging.py.

Audit MAJOR #4 sprint follow-up to PR #275. Module is at 90% from
existing `tests/test_staging.py`. Closes the 14 remaining uncovered
lines, all on edge-case error paths or rare format branches:

  * 76-77 — `extract_student_and_assignment` fallback when filename has
            fewer than 2 parseable parts (single-word or empty)
  * 139   — `stage_files` skips entries that aren't regular files
            (subdirectories, symlinks-to-dirs)
  * 145-146 — `stage_files` skips files that raise OSError on stat()
  * 192-193 — `stage_files` swallows OSError when reading current file
              size for resubmission detection
  * 204-205 — `stage_files` swallows OSError on stat() after copy
              (file_size = -1 fallback)
  * 230-234 — `stage_files` removes "orphan" files in staging folder
              that aren't in the manifest, swallowing OSError on remove

Per `feedback_codex_medium_effort_2026-05-09.md` and
`reference_gemini_cli_codex_fallback.md`: Codex is rate-limited until
2026-05-12; Gemini 3.1 Pro is the validated fallback reviewer.
"""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


# ──────────────────────────────────────────────────────────────────
# extract_student_and_assignment fallback (single-word filename)
# ──────────────────────────────────────────────────────────────────


class TestExtractFallbacks:
    def test_single_word_filename_uses_full_name_as_student_key(self):
        # Hit lines 76-77: when split produces fewer than 2 parts,
        # student_key = full clean name, assignment_key = "unknown"
        from backend.staging import extract_student_and_assignment

        student_key, assignment_key = extract_student_and_assignment(
            "loose.docx",
        )
        # Single-word: student_key = "loose", assignment_key = "unknown"
        assert student_key == "loose"
        assert assignment_key == "unknown"

    def test_empty_stem_filename_handled(self):
        # ".docx" has no stem after splitext — re.split returns []
        from backend.staging import extract_student_and_assignment

        student_key, assignment_key = extract_student_and_assignment(".docx")
        # 0 parts → falls into the else branch
        assert assignment_key == "unknown"

    def test_only_emoji_filename(self):
        # After regex strip, only special chars remain. After split, no parts.
        from backend.staging import extract_student_and_assignment

        student_key, assignment_key = extract_student_and_assignment(
            "😀😀😀.docx",
        )
        assert assignment_key == "unknown"


# ──────────────────────────────────────────────────────────────────
# stage_files non-file skip + stat OSError paths
# ──────────────────────────────────────────────────────────────────


@pytest.fixture
def staging_dirs(tmp_path):
    """Create a tmp source folder for stage_files tests."""
    source = tmp_path / "Assignments"
    source.mkdir()
    return source


class TestStageFilesEdgeCases:
    def test_subdirectory_in_source_is_skipped(self, staging_dirs):
        # Hit line 139: `if not f.is_file(): continue` — directories don't
        # have a .suffix in SUPPORTED_EXTENSIONS, but the explicit is_file
        # guard runs first. Verify a subdirectory is silently skipped.
        from backend.staging import stage_files

        # Real file
        (staging_dirs / "alice_smith_essay.docx").write_text("content")
        # Subdirectory (looks file-ish to a casual glob but is_file=False)
        subdir = staging_dirs / "subfolder.docx"  # extension matches!
        subdir.mkdir()

        result = stage_files(str(staging_dirs))
        # The .docx subdir is skipped (is_file=False). Only the real
        # file should be staged.
        assert result["staged_count"] == 1

    def test_stat_oserror_on_source_skips_file(self, staging_dirs):
        # Hit lines 145-146: `except OSError: continue` when stat() fails
        # on a source file. Need to patch BOTH `Path.is_file` (so the
        # production check at line 138 returns True without calling stat
        # internally — Python 3.12's is_file() calls stat()) AND
        # `Path.stat` (so the explicit call at line 144 raises).
        from backend.staging import stage_files
        from pathlib import Path as _RealPath

        good = staging_dirs / "alice_smith_essay.docx"
        good.write_text("content")
        bad = staging_dirs / "bob_jones_quiz.docx"
        bad.write_text("content")

        real_stat = _RealPath.stat
        real_is_file = _RealPath.is_file

        def selective_stat(self, *args, **kwargs):
            if self.name == "bob_jones_quiz.docx":
                raise OSError("permission denied")
            return real_stat(self, *args, **kwargs)

        def selective_is_file(self):
            # is_file() internally calls stat() in Python 3.12. Force
            # True for our bad file so production reaches line 144's
            # explicit stat() call (which is the line we're testing).
            if self.name == "bob_jones_quiz.docx":
                return True
            return real_is_file(self)

        with patch.object(Path, "stat", selective_stat), \
             patch.object(Path, "is_file", selective_is_file):
            result = stage_files(str(staging_dirs))

        # Only the good file should be staged (bad was skipped on stat)
        assert result["staged_count"] == 1

    def test_size_oserror_on_resubmission_check_treats_as_no_resubmission(
        self, staging_dirs,
    ):
        # Hit lines 192-193: `except OSError: curr_size = None`. When
        # size lookup fails inside the resubmission-detection block,
        # `size_changed` evaluates to False, so no resubmission is
        # flagged. (The stat at line 203 also fails, hitting lines
        # 204-205 — both branches share the same OSError trigger and
        # cannot be cleanly isolated since both call src_path.stat()
        # in the same flow. The file still gets staged because
        # `shutil.copy2` doesn't depend on stat().)
        #
        # PR #276 Gemini round-1 fold: was previously try/except'd and
        # swallowed test failures. Now strict — function MUST complete,
        # MUST stage the file, and MUST NOT flag resubmission.
        from backend.staging import stage_files

        from pathlib import Path as _RealPath

        # Initial stage with everything working
        f = staging_dirs / "alice_smith_essay.docx"
        f.write_text("v1 content")
        first = stage_files(str(staging_dirs))
        assert first["staged_count"] == 1
        assert first["resubmissions"] == set()

        # Modify file: changes both size and mtime → would normally flag
        # resubmission, but with stat-OSError curr_size=None → no flag
        f.write_text("v2 different content with more bytes total")
        os.utime(str(f), (10000, 20000))

        # Per-file call counter (NOT global) — only counts stats on
        # alice's file so other files / hidden filesystem stats don't
        # throw the count off.
        real_stat = _RealPath.stat
        real_is_file = _RealPath.is_file
        alice_calls = {"n": 0}

        def selective_stat(self, *args, **kwargs):
            if self.name == "alice_smith_essay.docx":
                alice_calls["n"] += 1
                # First call is phase-1 mtime read at viz.py:144 — let it
                # succeed so the file is included in source_files.
                # Subsequent calls (line 191 size-check, line 203 post-
                # copy size) raise to exercise the OSError branches.
                if alice_calls["n"] >= 2:
                    raise OSError("intermittent stat failure")
            return real_stat(self, *args, **kwargs)

        def selective_is_file(self):
            # Python 3.12's is_file() calls stat(). Force True for our
            # target so production reaches the explicit try/except.
            if self.name == "alice_smith_essay.docx":
                return True
            return real_is_file(self)

        with patch.object(Path, "stat", selective_stat), \
             patch.object(Path, "is_file", selective_is_file):
            # NO try/except — production must handle the OSError itself.
            # If stage_files crashes with OSError, the test correctly
            # fails (signaling that the production guard is broken).
            result = stage_files(str(staging_dirs))

        # Production handled the OSError gracefully:
        # 1. File still staged (copy2 doesn't need stat)
        assert result["staged_count"] == 1
        # 2. NO resubmission flagged — because curr_size was None during
        #    the check, size_changed evaluated to False
        assert result["resubmissions"] == set(), (
            "Stat-OSError during resubmission check should NOT flag a "
            "resubmission (curr_size unknown means we can't confirm it "
            "actually changed)."
        )
        # 3. Verify the post-copy stat OSError fell through to file_size=-1
        from backend.staging import _load_manifest
        manifest = _load_manifest(result["staging_folder"])
        assert manifest["alice_smith_essay.docx"]["size"] == -1
        # 4. Confirm the OSError trigger actually fired the way we expected
        #    (alice's stat was called >= 2 times — the count proves the
        #    OSError branches were exercised, not bypassed)
        assert alice_calls["n"] >= 2

    def test_stat_after_copy_oserror_uses_negative_one_size(
        self, staging_dirs,
    ):
        # Hit lines 204-205: `except OSError: file_size = -1` when stat
        # on src_path fails AFTER shutil.copy2 succeeded.
        from backend.staging import stage_files
        from pathlib import Path as _RealPath

        f = staging_dirs / "alice_smith_essay.docx"
        f.write_text("content")

        real_stat = _RealPath.stat
        real_is_file = _RealPath.is_file
        # Track stat calls so we can fail only the post-copy one
        # (lines 191 and 203 both call src_path.stat).
        stat_calls = {"by_file": {}}

        def selective_stat(self, *args, **kwargs):
            if self.name == "alice_smith_essay.docx":
                count = stat_calls["by_file"].get(self.name, 0) + 1
                stat_calls["by_file"][self.name] = count
                # Phase-1 mtime stat at line 144 must succeed
                # Lines 191 (resubmission-check) doesn't fire on first run
                # Line 203 (post-copy size stat) fires; let's fail it.
                if count >= 2:
                    raise OSError("vanished")
            return real_stat(self, *args, **kwargs)

        def selective_is_file(self):
            # Python 3.12's is_file() calls stat(); force True for target
            if self.name == "alice_smith_essay.docx":
                return True
            return real_is_file(self)

        with patch.object(Path, "stat", selective_stat), \
             patch.object(Path, "is_file", selective_is_file):
            result = stage_files(str(staging_dirs))

        # File still staged (copy succeeded) — manifest stored size=-1
        assert result["staged_count"] == 1
        # Verify the manifest was written with size=-1 fallback
        from backend.staging import _load_manifest
        manifest = _load_manifest(result["staging_folder"])
        assert manifest["alice_smith_essay.docx"]["size"] == -1


# ──────────────────────────────────────────────────────────────────
# stage_files orphan-file removal in staging folder
# ──────────────────────────────────────────────────────────────────


class TestStageFilesOrphanRemoval:
    def test_orphan_file_in_staging_removed(self, staging_dirs, tmp_path):
        # Hit lines 230-232: orphan files (in staging folder but not in
        # manifest and not in source) get removed.
        from backend.staging import stage_files, get_staging_folder

        # First, create the staging folder with an orphan file BEFORE
        # any stage_files call (no manifest yet)
        staging_folder = Path(get_staging_folder(str(staging_dirs)))
        staging_folder.mkdir()
        orphan = staging_folder / "ghost_student_lost.docx"
        orphan.write_text("orphan content")
        assert orphan.exists()

        # Now stage one new file. The orphan should be cleaned up.
        (staging_dirs / "alice_smith_essay.docx").write_text("content")
        result = stage_files(str(staging_dirs))

        # Orphan is gone
        assert not orphan.exists()
        assert result["stale_removed"] >= 1

    def test_orphan_remove_oserror_swallowed(self, staging_dirs):
        # Hit lines 233-234: `except OSError: pass` when os.remove on an
        # orphan fails (e.g., permission denied). The function should
        # not crash.
        from backend.staging import stage_files, get_staging_folder

        staging_folder = Path(get_staging_folder(str(staging_dirs)))
        staging_folder.mkdir()
        orphan = staging_folder / "ghost_student_lost.docx"
        orphan.write_text("orphan content")

        # Stage a file so the function actually runs all phases
        (staging_dirs / "alice_smith_essay.docx").write_text("content")

        # Mock os.remove to raise OSError on the orphan's exact path.
        # Also need to let the manifest save use os.remove if any (it doesn't).
        real_remove = os.remove
        def selective_remove(path):
            if "ghost_student_lost" in str(path):
                raise OSError("permission denied")
            return real_remove(path)

        with patch("backend.staging.os.remove", side_effect=selective_remove):
            # Should not raise
            result = stage_files(str(staging_dirs))

        # Function still completed
        assert "staging_folder" in result
        assert result["staged_count"] == 1


# ──────────────────────────────────────────────────────────────────
# Manifest helpers — additional gap coverage
# ──────────────────────────────────────────────────────────────────


class TestManifestHelpers:
    def test_load_manifest_returns_empty_when_corrupt(self, staging_dirs, tmp_path):
        # The `except (json.JSONDecodeError, OSError): pass` branch in
        # `_load_manifest` returns {} for malformed JSON. Pin that.
        from backend.staging import _load_manifest, MANIFEST_NAME

        staging_folder = tmp_path / "stage"
        staging_folder.mkdir()
        (staging_folder / MANIFEST_NAME).write_text("{not valid json")

        assert _load_manifest(str(staging_folder)) == {}

    def test_load_manifest_returns_empty_when_file_missing(self, tmp_path):
        from backend.staging import _load_manifest

        staging_folder = tmp_path / "no_manifest_yet"
        staging_folder.mkdir()
        # No manifest file written
        assert _load_manifest(str(staging_folder)) == {}
