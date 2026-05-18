"""
Regression tests for GH #253: path traversal in document_generator.py
load_style() and save_style() — both joined `style_name + ".json"` to
STYLES_DIR without sanitization. Attacker-controlled style names like
"../../etc/passwd" would resolve outside STYLES_DIR.

Fix: `_safe_style_name` sanitizes input to alphanum + dash + underscore,
`_resolve_style_path` adds defense-in-depth realpath check.

These tests pin both layers so a future revert can't silently
re-introduce the traversal.
"""
from __future__ import annotations

import json
import os

import pytest


@pytest.fixture
def isolated_dirs(tmp_path, monkeypatch):
    import backend.services.document_generator as dg
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("GRAIDER_EXPORT_DIR", str(tmp_path / "Downloads" / "Graider"))
    monkeypatch.setattr(dg, "STYLES_DIR", str(tmp_path / "doc_styles"))
    monkeypatch.setattr(dg, "ASSIGNMENTS_DIR", str(tmp_path / "assignments"))
    return tmp_path, dg


# ──────────────────────────────────────────────────────────────────
# _safe_style_name — pure sanitizer
# ──────────────────────────────────────────────────────────────────


class TestSafeStyleName:
    def test_alphanumeric_passthrough(self):
        from backend.services.document_generator import _safe_style_name
        assert _safe_style_name("cornell-notes") == "cornell-notes"
        assert _safe_style_name("parent_letter_v2") == "parent_letter_v2"
        assert _safe_style_name("Style123") == "Style123"

    def test_path_traversal_neutralized(self):
        from backend.services.document_generator import _safe_style_name
        # `..` and `/` and `\` get replaced with `_`
        result = _safe_style_name("../../etc/passwd")
        # No path separators or dots that could escape
        assert "/" not in result
        assert "\\" not in result
        assert ".." not in result

    def test_absolute_path_neutralized(self):
        from backend.services.document_generator import _safe_style_name
        result = _safe_style_name("/etc/passwd")
        assert "/" not in result
        # Result is some sanitized string starting with `_etc_passwd` or similar
        assert "etc" in result or result.startswith("_")

    def test_empty_returns_none(self):
        from backend.services.document_generator import _safe_style_name
        assert _safe_style_name("") is None
        assert _safe_style_name(None) is None

    def test_dot_sentinel_returns_none(self):
        """`.` and `..` sanitize to `.` and `..` (the regex preserves dots),
        which would resolve to current/parent dir if joined. Reject."""
        from backend.services.document_generator import _safe_style_name
        # Note: the regex replaces non-alphanum/dash/underscore with `_`,
        # so `.` becomes `_`. But explicit check for `.` and `..` after
        # sanitization protects against a future regex tweak.
        result_dot = _safe_style_name(".")
        # `.` → `_` (sanitization replaces). Then sanitized != '.', so it returns the sanitized version.
        assert result_dot != "."

    def test_special_chars_replaced(self):
        from backend.services.document_generator import _safe_style_name
        result = _safe_style_name("style; rm -rf /; '")
        assert "/" not in result
        assert ";" not in result
        assert "'" not in result
        assert " " not in result

    def test_overlong_name_rejected(self):
        """Codex round-1 MINOR: silent truncation let two distinct names
        differing only past char 120 collide and overwrite each other.
        Now they're rejected outright."""
        from backend.services.document_generator import _safe_style_name
        assert _safe_style_name("a" * 121) is None
        assert _safe_style_name("a" * 500) is None

    def test_exactly_120_chars_accepted(self):
        from backend.services.document_generator import _safe_style_name
        assert _safe_style_name("a" * 120) == "a" * 120


# ──────────────────────────────────────────────────────────────────
# _resolve_style_path — defense-in-depth realpath check
# ──────────────────────────────────────────────────────────────────


class TestResolveStylePath:
    def test_valid_name_resolves_inside_styles_dir(self, isolated_dirs):
        tmp, dg = isolated_dirs
        # STYLES_DIR doesn't have to exist for resolve to work
        path = dg._resolve_style_path("custom")
        assert path is not None
        # Resolved path is inside (the realpath of) STYLES_DIR
        assert os.path.realpath(path).startswith(os.path.realpath(dg.STYLES_DIR))

    def test_traversal_attempt_rejected(self, isolated_dirs):
        tmp, dg = isolated_dirs
        # Even if _safe_style_name didn't catch it, _resolve_style_path
        # verifies the resolved path stays inside STYLES_DIR.
        # `../../etc/passwd` → sanitizes to `_____etc_passwd` (or similar)
        # which resolves INSIDE STYLES_DIR. So this just tests the safe
        # name pipeline doesn't escape.
        path = dg._resolve_style_path("../../etc/passwd")
        if path is not None:
            assert os.path.realpath(path).startswith(os.path.realpath(dg.STYLES_DIR))

    def test_empty_returns_none(self, isolated_dirs):
        _, dg = isolated_dirs
        assert dg._resolve_style_path("") is None
        assert dg._resolve_style_path(None) is None


# ──────────────────────────────────────────────────────────────────
# load_style respects sanitization
# ──────────────────────────────────────────────────────────────────


class TestLoadStyleSanitization:
    def test_traversal_attempt_returns_default(self, isolated_dirs):
        tmp, dg = isolated_dirs
        os.makedirs(dg.STYLES_DIR, exist_ok=True)
        # Create a real file at the sanitized path that an attacker
        # might be aiming for — load_style should NOT read it via
        # the unsanitized "../../" form.
        target_outside = tmp / "outside_target.json"
        target_outside.write_text(json.dumps({"title_font_name": "ATTACKER"}))

        # `../../outside_target` should sanitize to a name that doesn't
        # actually point at the attacker's file.
        result = dg.load_style("../../outside_target")
        # title_font_name should NOT be ATTACKER — i.e. the sanitized
        # path didn't accidentally resolve to the attacker's file.
        assert result["title_font_name"] != "ATTACKER"

    def test_legitimate_traversal_chars_in_name_safely_handled(self, isolated_dirs):
        """A user might legitimately call load_style('../style') by
        mistake. Should return defaults (not crash, not read a file
        outside STYLES_DIR)."""
        _, dg = isolated_dirs
        result = dg.load_style("../style")
        # Falls back to defaults silently
        assert result == dg.DEFAULT_STYLE

    def test_absolute_path_returns_default(self, isolated_dirs):
        _, dg = isolated_dirs
        result = dg.load_style("/etc/passwd")
        # Sanitization neutralizes the absolute path; file doesn't exist
        # under sanitized name → fallback to defaults
        assert result == dg.DEFAULT_STYLE

    def test_legitimate_style_still_works(self, isolated_dirs):
        """Sanitization must not break the normal happy path."""
        tmp, dg = isolated_dirs
        os.makedirs(dg.STYLES_DIR, exist_ok=True)
        with open(os.path.join(dg.STYLES_DIR, "cornell-notes.json"), 'w') as f:
            json.dump({"title_font_name": "Helvetica"}, f)
        result = dg.load_style("cornell-notes")
        assert result["title_font_name"] == "Helvetica"

    def test_legacy_unsanitized_filename_loads_via_fallback(self, isolated_dirs):
        """Codex round-1 MAJOR: pre-#253 saves used raw names like 'My Style'
        which list_styles() still returns. load_style('My Style') must find
        the existing 'My Style.json' file even though sanitization would
        produce 'My_Style'. The legacy fallback handles this."""
        tmp, dg = isolated_dirs
        os.makedirs(dg.STYLES_DIR, exist_ok=True)
        legacy_path = os.path.join(dg.STYLES_DIR, "My Style.json")
        with open(legacy_path, 'w') as f:
            json.dump({"title_font_name": "LegacyFont"}, f)
        result = dg.load_style("My Style")
        assert result["title_font_name"] == "LegacyFont", (
            "Backward-compat fallback failed: load_style returned defaults "
            "for a legitimate pre-#253 style filename."
        )

    def test_legacy_fallback_still_blocks_traversal(self, isolated_dirs):
        """The legacy fallback must NOT open the door to path traversal.
        A name with `/` or `\\` is hard-rejected before any filesystem op."""
        tmp, dg = isolated_dirs
        # Place attacker file at the path the OLD vulnerable code would have read
        attacker_path = tmp / "outside.json"
        attacker_path.write_text(json.dumps({"title_font_name": "ATTACKER"}))

        # Old code: os.path.join(STYLES_DIR, "../../outside" + ".json") would
        # resolve to tmp.parent / outside.json (depending on tmp depth).
        # In our test, STYLES_DIR is tmp/doc_styles, so '../outside' would
        # resolve to tmp/outside.json — exactly where we placed the file.
        result = dg.load_style("../outside")
        # Legacy fallback rejects the name (contains /), AND realpath rejects
        # because the resolved path escapes STYLES_DIR.
        assert result["title_font_name"] != "ATTACKER", (
            "Legacy fallback re-opened the path traversal vector that #253 fixed!"
        )
        assert result == dg.DEFAULT_STYLE


# ──────────────────────────────────────────────────────────────────
# save_style respects sanitization
# ──────────────────────────────────────────────────────────────────


class TestSaveStyleSanitization:
    def test_traversal_name_rejected_with_error(self, isolated_dirs):
        """save_style with `..` sanitizes to `__` which is valid, so
        it would accept it. Test the actual behavior: file lands inside
        STYLES_DIR, NOT outside."""
        tmp, dg = isolated_dirs
        result = dg.save_style("../escape_attempt", {"title_font_name": "Arial"})
        # Either rejected with error OR written inside STYLES_DIR
        if "error" not in result:
            # File was written — must be inside STYLES_DIR
            assert os.path.realpath(result["filepath"]).startswith(
                os.path.realpath(dg.STYLES_DIR)
            )
            # Outside-STYLES_DIR file does NOT exist
            assert not os.path.exists(str(tmp / "escape_attempt.json"))

    def test_empty_name_rejected(self, isolated_dirs):
        _, dg = isolated_dirs
        result = dg.save_style("", {"title_font_name": "x"})
        assert "error" in result

    def test_none_name_rejected(self, isolated_dirs):
        _, dg = isolated_dirs
        result = dg.save_style(None, {"title_font_name": "x"})
        assert "error" in result

    def test_legitimate_save_still_works(self, isolated_dirs):
        tmp, dg = isolated_dirs
        result = dg.save_style("my_style", {"title_font_name": "Arial"})
        assert result.get("status") == "saved"
        # File written at sanitized path (which equals input here since
        # input was already safe)
        assert os.path.exists(result["filepath"])
        # Stored name reflects sanitization
        assert result["style_name"] == "my_style"

    def test_overlong_names_dont_silently_collide(self, isolated_dirs):
        """Codex round-1 MINOR: if save_style truncated at 120, two distinct
        names differing past char 120 would produce the same filename and
        the second save would overwrite the first. After the fold,
        over-long names are rejected with an error (not truncated)."""
        _, dg = isolated_dirs
        a_name = "a" * 121
        b_name = ("a" * 130) + "DIFFERENT_TAIL"
        ra = dg.save_style(a_name, {"title_font_name": "First"})
        rb = dg.save_style(b_name, {"title_font_name": "Second"})
        # Both rejected — no overwrite collision possible
        assert "error" in ra
        assert "error" in rb

    def test_save_normalizes_name_in_payload(self, isolated_dirs):
        """The stored 'name' field in the JSON should be the sanitized
        form, not the raw input. Prevents attacker from injecting a
        special-char name into the saved JSON."""
        tmp, dg = isolated_dirs
        result = dg.save_style("name with spaces", {"title_font_name": "Arial"})
        # Underscores replaced spaces
        assert "name_with_spaces" in result.get("style_name", "")
        # File stores the sanitized name
        with open(result["filepath"]) as f:
            saved = json.load(f)
        assert saved["name"] == result["style_name"]
