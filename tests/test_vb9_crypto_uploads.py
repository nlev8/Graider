"""VB9 — Crypto/RNG, audit-name redaction, image-URL SSRF, and zip-bomb guards.

Security batch VB9 (audit findings #20, #21 Low / #24, #25 Info):

  #21 — Join/class/survey access codes must use a cryptographically secure RNG
        (`secrets`), not the predictable Mersenne-Twister `random` module.
  #20 — Audit-log details must redact student NAMES (consistent with the
        existing email/UUID/hex redaction at the audit boundary).
  #24 — Student-controlled image fields must not be forwarded verbatim as an
        OpenAI `image_url` — external `http(s)://`/`file://` URLs are rejected,
        only inline base64 / data: image URIs are allowed.
  #25 — Zip-based office docs (.docx) must be rejected when their uncompressed
        expansion ratio / member count indicates a zip bomb.
"""
import io
import re
import zipfile

import pytest


# ---------------------------------------------------------------------------
# #21 — Cryptographic RNG for access codes
# ---------------------------------------------------------------------------
class TestAccessCodesUseSecrets:
    """The three 6-char access-code generators must draw from `secrets`,
    not the predictable `random` module. We assert by monkeypatching
    `secrets.choice` and confirming it is the source of every character."""

    ALPHABET = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'

    def test_generate_join_code_uses_secrets(self, monkeypatch):
        import backend.routes.student_portal_routes as mod

        calls = {"secrets": 0}

        def tracking_choice(seq):
            calls["secrets"] += 1
            return seq[0]

        monkeypatch.setattr(mod.secrets, "choice", tracking_choice)
        # The predictable Mersenne-Twister `random` module must no longer be
        # imported by this module at all.
        assert not hasattr(mod, "random"), "module still imports `random`"

        # Supabase uniqueness check returns "no existing code" immediately.
        class _Chain:
            data = []

            def select(self, *a, **k):
                return self

            def eq(self, *a, **k):
                return self

            def execute(self):
                return self

            def table(self, *a, **k):
                return self

        monkeypatch.setattr(mod, "get_supabase", lambda: _Chain())

        code = mod.generate_join_code()
        assert len(code) == 6
        assert all(c in self.ALPHABET for c in code)
        assert calls["secrets"] == 6

    def test_generate_class_code_uses_secrets(self, monkeypatch):
        import backend.routes.student_account_routes as mod

        calls = {"secrets": 0}

        def tracking_choice(seq):
            calls["secrets"] += 1
            return seq[0]

        monkeypatch.setattr(mod.secrets, "choice", tracking_choice)
        assert not hasattr(mod, "random"), "module still imports `random`"

        class _Chain:
            data = []

            def select(self, *a, **k):
                return self

            def eq(self, *a, **k):
                return self

            def execute(self):
                return self

            def table(self, *a, **k):
                return self

        monkeypatch.setattr(mod, "_get_supabase", lambda: _Chain())

        code = mod._generate_class_code()
        assert len(code) == 6
        assert all(c in self.ALPHABET for c in code)
        assert calls["secrets"] == 6

    def test_generate_survey_code_uses_secrets(self, monkeypatch):
        import backend.routes.survey_routes as mod

        calls = {"secrets": 0}

        def tracking_choice(seq):
            calls["secrets"] += 1
            return seq[0]

        monkeypatch.setattr(mod.secrets, "choice", tracking_choice)
        assert not hasattr(mod, "random"), "module still imports `random`"

        class _Chain:
            data = []

            def select(self, *a, **k):
                return self

            def eq(self, *a, **k):
                return self

            def execute(self):
                return self

            def table(self, *a, **k):
                return self

        monkeypatch.setattr(mod, "get_supabase", lambda: _Chain())

        code = mod._generate_survey_code()
        assert len(code) == 6
        assert all(c in self.ALPHABET for c in code)
        assert calls["secrets"] == 6


# ---------------------------------------------------------------------------
# #20 — Audit-log student-name redaction
# ---------------------------------------------------------------------------
class TestAuditNameRedaction:
    """Audit details that carry an explicit student name (the `name=<...>`
    or `student=<...>` convention used by the FERPA audit writers) must be
    redacted to a non-identifying initial form before persistence."""

    def test_student_name_field_is_redacted(self):
        from backend.utils.audit import _redact_for_audit

        out = _redact_for_audit("GRADE_EDIT student=Alice Johnson score=95")
        assert "Alice Johnson" not in out
        # First initial preserved for debuggability, surname stripped.
        assert "score=95" in out  # non-PII preserved

    def test_name_field_redacted(self):
        from backend.utils.audit import _redact_for_audit

        out = _redact_for_audit("ROSTER_ADD name=Bob Smith id=42")
        assert "Bob Smith" not in out
        assert "id=42" in out

    def test_audit_log_persists_redacted_name(self, monkeypatch, tmp_path):
        from backend.utils.audit import audit_log

        captured = {}

        def fake_insert(payload):
            captured["payload"] = payload

            class _C:
                def execute(self_inner):
                    return None

            return _C()

        class _Table:
            def insert(self, payload):
                return fake_insert(payload)

        class _SB:
            def table(self, *a, **k):
                return _Table()

        monkeypatch.setattr(
            "backend.supabase_client.get_supabase", lambda: _SB()
        )
        monkeypatch.setattr(
            "backend.utils.audit.AUDIT_LOG_FILE", str(tmp_path / "audit.log")
        )

        audit_log(
            action="GRADE_VIEW",
            details="viewed submission for student=Charlie Brown",
            user="teacher",
            teacher_id="t-1",
        )

        payload = captured.get("payload")
        assert payload is not None
        assert "Charlie Brown" not in payload["details"]


# ---------------------------------------------------------------------------
# #24 — Image-URL SSRF guard
# ---------------------------------------------------------------------------
class TestImageUrlSsrfGuard:
    """Student-controlled image input must not be forwarded as a remote URL."""

    def test_external_http_url_rejected(self):
        from backend.routes.assignment_player_routes import _is_safe_image_input

        assert _is_safe_image_input("http://169.254.169.254/latest/meta-data/") is False
        assert _is_safe_image_input("https://internal.example/secret") is False
        assert _is_safe_image_input("file:///etc/passwd") is False
        assert _is_safe_image_input("ftp://host/x") is False

    def test_data_uri_allowed(self):
        from backend.routes.assignment_player_routes import _is_safe_image_input

        assert _is_safe_image_input("data:image/png;base64,iVBORw0KGgo=") is True

    def test_raw_base64_allowed(self):
        from backend.routes.assignment_player_routes import _is_safe_image_input

        # Raw base64 (no scheme) — the legitimate non-data-URI case.
        assert _is_safe_image_input("iVBORw0KGgoAAAANSUhEUgAAAAEAAAAB") is True

    def test_process_image_answer_rejects_external_url(self, monkeypatch):
        """An external URL in answer['image'] must not reach the OCR backends."""
        import backend.routes.assignment_player_routes as mod

        def boom(*a, **k):
            pytest.fail("external image URL was forwarded to an OCR backend")

        monkeypatch.setattr(mod, "extract_answer_from_image", boom)
        monkeypatch.setattr(mod, "_vision_ocr_fallback", boom)

        answer = {"image": "https://169.254.169.254/latest/meta-data/"}
        result, ocr = mod._process_image_answer(
            answer, {"question": "Q"}, "math", "math_equation"
        )
        # Returns the original answer untouched; OCR never ran.
        assert ocr is None


# ---------------------------------------------------------------------------
# #25 — Zip-bomb guard on .docx parsing
# ---------------------------------------------------------------------------
def _make_valid_docx(path):
    """Build a minimal but structurally valid .docx so the test exercises
    the bomb guard, not python-docx's own "not a valid OPC package" error."""
    from docx import Document

    d = Document()
    d.add_paragraph("hello world")
    d.save(str(path))


def _add_bomb_member(path, payload_size=300 * 1024 * 1024):
    """Append a high-ratio member to an existing valid docx zip. 300 MB of
    zeros compresses to a few KB — the central-directory `file_size` field
    reports the inflated size, so a guard can reject before decompressing."""
    with zipfile.ZipFile(path, "a", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("word/bomb.bin", b"\x00" * payload_size)


class TestDocxZipBombGuard:
    def test_zip_bomb_rejected_by_read_docx_file(self, tmp_path):
        from backend.services.submission_parsing import read_docx_file

        bomb = tmp_path / "bomb.docx"
        _make_valid_docx(bomb)
        _add_bomb_member(str(bomb))

        # Must NOT attempt to fully expand the bomb; returns None (safe failure).
        result = read_docx_file(str(bomb))
        assert result is None

    def test_zip_bomb_rejected_by_structured_reader(self, tmp_path):
        from backend.services.submission_parsing import read_docx_file_structured

        bomb = tmp_path / "bomb.docx"
        _make_valid_docx(bomb)
        _add_bomb_member(str(bomb))

        result = read_docx_file_structured(str(bomb))
        assert result.get("is_graider_table") is False
        assert not result.get("tables")

    def test_legitimate_docx_still_parses(self, tmp_path):
        """A normal docx (well under the cap) must still be read."""
        from backend.services.submission_parsing import read_docx_file

        ok = tmp_path / "ok.docx"
        _make_valid_docx(ok)

        result = read_docx_file(str(ok))
        assert result is not None
        assert "hello world" in result
