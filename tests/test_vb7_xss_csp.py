"""Security regression tests — BATCH VB7 (XSS / HTML-injection + CSP).

Covers audit findings:
* #15 (Med, stored XSS): backend/routes/survey_routes.py — the anonymous
  parent-survey HTML page interpolated teacher-controlled fields (title,
  teacher name, question text, question id) UNESCAPED into a text/html
  document.
* #23 (Low, HTML injection): backend/routes/auth_routes.py
  /api/auth/notify-signup (PUBLIC) embedded request-supplied
  email/first_name/last_name UNESCAPED into the admin notification email
  HTML.
* #27 (Info, reflected XSS + missing CSP): /api/auth/approve-user reflected
  the `email` query param UNESCAPED into a text/html page; and
  backend/app.py only attached a Content-Security-Policy header when the
  path did NOT start with /api/, so these /api/ HTML pages got no CSP.

Each test injects a malicious value (`<script>alert(1)</script>` or
`"><img src=x onerror=alert(1)>`) and asserts it appears ESCAPED (the
literal `<script>` tag does NOT appear as a live tag) in the response body,
and that the CSP header is present on the HTML /api/ responses.
"""
from __future__ import annotations

import json
from unittest.mock import patch, MagicMock

import pytest


XSS = "<script>alert(1)</script>"
XSS_ATTR = '"><img src=x onerror=alert(1)>'


@pytest.fixture
def client():
    from backend.app import app
    from backend.extensions import limiter
    try:
        limiter.reset()
    except Exception:
        pass
    with app.test_client() as c:
        yield c


@pytest.fixture(autouse=True)
def dev_env(monkeypatch):
    monkeypatch.setenv("FLASK_ENV", "development")


# ──────────────────────────────────────────────────────────────────
# Chain-mock helper for Supabase fluent queries (mirrors
# test_survey_routes_unit.py)
# ──────────────────────────────────────────────────────────────────


class FakeChain:
    def __init__(self, execute_data=None):
        self._execute_data = execute_data

    def table(self, *a, **kw): return self
    def select(self, *a, **kw): return self
    def eq(self, *a, **kw): return self

    def execute(self):
        m = MagicMock()
        m.data = self._execute_data
        return m


def patch_survey_supabase(execute_data):
    sb = MagicMock()
    chain = FakeChain(execute_data)
    sb.table.side_effect = chain.table
    return patch("backend.routes.survey_routes.get_supabase", return_value=sb)


# ──────────────────────────────────────────────────────────────────
# #15 — Stored XSS in /survey/<code> public HTML page
# ──────────────────────────────────────────────────────────────────


class TestSurveyPageEscaping:
    def _record(self, *, title=XSS, teacher=XSS, q_text=XSS, q_id="q1"):
        return {
            "title": title,
            "teacher_name": teacher,
            "is_active": True,
            "assessment": {
                "content_type": "survey",
                "questions": [
                    {"id": q_id, "text": q_text, "type": "rating"},
                ],
            },
        }

    def test_title_is_escaped(self, client):
        with patch_survey_supabase([self._record()]):
            resp = client.get("/survey/CODE")
        body = resp.data.decode()
        assert resp.status_code == 200
        # The live <script> tag must NOT appear; the escaped form must.
        assert XSS not in body
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in body

    def test_teacher_name_is_escaped(self, client):
        rec = self._record(title="Safe Title", teacher=XSS, q_text="Safe Q")
        with patch_survey_supabase([rec]):
            resp = client.get("/survey/CODE")
        body = resp.data.decode()
        assert XSS not in body
        assert "&lt;script&gt;" in body

    def test_question_text_is_escaped(self, client):
        rec = self._record(title="Safe", teacher="Safe", q_text=XSS)
        with patch_survey_supabase([rec]):
            resp = client.get("/survey/CODE")
        body = resp.data.decode()
        assert XSS not in body
        assert "&lt;script&gt;" in body

    def test_question_id_attribute_cannot_break_out(self, client):
        # The question id is interpolated into name="<id>" and value
        # attributes; a quote-breaking id must be escaped so it cannot
        # inject an onerror handler / new tag.
        rec = self._record(title="Safe", teacher="Safe", q_text="Safe",
                            q_id=XSS_ATTR)
        with patch_survey_supabase([rec]):
            resp = client.get("/survey/CODE")
        body = resp.data.decode()
        # The raw breakout payload (live <img ... onerror>) must not appear.
        assert "<img src=x onerror=alert(1)>" not in body
        # Double-quote that would terminate the attribute must be escaped.
        assert 'name="<script>' not in body

    def test_text_question_id_escaped(self, client):
        rec = {
            "title": "Safe", "teacher_name": "Safe", "is_active": True,
            "assessment": {
                "content_type": "survey",
                "questions": [
                    {"id": XSS_ATTR, "text": XSS, "type": "text"},
                ],
            },
        }
        with patch_survey_supabase([rec]):
            resp = client.get("/survey/CODE")
        body = resp.data.decode()
        assert "<img src=x onerror=alert(1)>" not in body
        assert XSS not in body

    def test_csp_header_present_on_survey_page(self, client):
        with patch_survey_supabase([self._record(title="Safe", teacher="Safe",
                                                  q_text="Safe")]):
            resp = client.get("/survey/CODE")
        assert resp.status_code == 200
        # /survey/<code> is NOT under /api/, so it already gets CSP — but
        # pin it so a regression in the after_request hook is caught.
        assert "Content-Security-Policy" in resp.headers


# ──────────────────────────────────────────────────────────────────
# #27 — Reflected XSS + missing CSP in /api/auth/approve-user
# ──────────────────────────────────────────────────────────────────


class TestApproveUserReflectedXss:
    def test_invalid_token_page_escapes_email(self, client, monkeypatch):
        # Invalid token path reflects the email into the error page.
        monkeypatch.setenv("SUPABASE_JWT_SECRET", "s")
        resp = client.get(
            "/api/auth/approve-user",
            query_string={"user_id": "u1", "email": XSS, "token": "wrong"},
        )
        body = resp.get_data(as_text=True)
        # The message is "Invalid or expired..." so the email is not echoed
        # in THIS branch, but the success branch below echoes it. This test
        # pins that the page itself never reflects a raw script tag.
        assert XSS not in body

    def test_success_page_escapes_reflected_email(self, client, monkeypatch):
        from backend.routes.auth_routes import _sign_approval
        monkeypatch.setenv("SUPABASE_JWT_SECRET", "s")
        token = _sign_approval("u1", XSS)
        mock_sb = MagicMock()
        with patch("backend.routes.auth_routes._get_supabase",
                   return_value=mock_sb):
            resp = client.get(
                "/api/auth/approve-user",
                query_string={"user_id": "u1", "email": XSS, "token": token},
            )
        body = resp.get_data(as_text=True)
        # The email is reflected into "<email> has been approved!" — it must
        # be escaped.
        assert XSS not in body
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in body
        assert "has been approved" in body

    def test_csp_header_present_on_approve_page(self, client, monkeypatch):
        monkeypatch.setenv("SUPABASE_JWT_SECRET", "s")
        resp = client.get(
            "/api/auth/approve-user",
            query_string={"user_id": "u1", "email": "a@x.com",
                          "token": "wrong"},
        )
        # This is an /api/ HTML page — it MUST carry a CSP header now.
        assert resp.headers["Content-Type"].startswith("text/html")
        assert "Content-Security-Policy" in resp.headers


# ──────────────────────────────────────────────────────────────────
# #23 — HTML injection in /api/auth/notify-signup admin email
# ──────────────────────────────────────────────────────────────────


class TestNotifySignupEscaping:
    def _send(self, client, monkeypatch, **payload):
        monkeypatch.setenv("ADMIN_EMAIL", "admin@x.com")
        monkeypatch.setenv("RESEND_API_KEY", "re_test_xyz")
        monkeypatch.setenv("SUPABASE_JWT_SECRET", "s")
        monkeypatch.setenv("SUPABASE_URL", "https://abc.supabase.co")
        mock_sb = MagicMock()
        mock_sb.auth.admin.list_users.return_value = []
        with patch("backend.routes.auth_routes._get_supabase",
                   return_value=mock_sb), \
             patch("backend.routes.auth_routes.requests.post") as mock_post:
            resp = client.post("/api/auth/notify-signup", json=payload)
        return resp, mock_post

    def test_first_last_name_escaped_in_email_html(self, client, monkeypatch):
        resp, mock_post = self._send(
            client, monkeypatch,
            email="alice@x.com", first_name=XSS, last_name="Smith",
        )
        assert resp.get_json()["status"] == "ok"
        html = mock_post.call_args.kwargs["json"]["html"]
        assert XSS not in html
        assert "&lt;script&gt;" in html

    def test_email_escaped_in_email_html(self, client, monkeypatch):
        # email itself is request-supplied and embedded in the body.
        resp, mock_post = self._send(
            client, monkeypatch,
            email=XSS, first_name="Alice", last_name="Smith",
        )
        assert resp.get_json()["status"] == "ok"
        html = mock_post.call_args.kwargs["json"]["html"]
        assert XSS not in html

    def test_first_name_escaped_in_approve_button(self, client, monkeypatch):
        # When a user_id is found, first_name is embedded into the
        # "Approve <first_name>" button.
        monkeypatch.setenv("ADMIN_EMAIL", "admin@x.com")
        monkeypatch.setenv("RESEND_API_KEY", "re_test_xyz")
        monkeypatch.setenv("SUPABASE_JWT_SECRET", "s")
        mock_user = MagicMock()
        mock_user.email = "alice@x.com"
        mock_user.id = "user-1"
        mock_sb = MagicMock()
        mock_sb.auth.admin.list_users.return_value = [mock_user]
        with patch("backend.routes.auth_routes._get_supabase",
                   return_value=mock_sb), \
             patch("backend.routes.auth_routes.requests.post") as mock_post:
            resp = client.post(
                "/api/auth/notify-signup",
                json={"email": "alice@x.com", "first_name": XSS},
            )
        assert resp.get_json()["status"] == "ok"
        html = mock_post.call_args.kwargs["json"]["html"]
        assert XSS not in html
        assert "&lt;script&gt;" in html

    def test_subject_safe_name_unchanged(self, client, monkeypatch):
        # Regression guard: a benign name still flows through unchanged
        # (escaping must not corrupt normal input).
        resp, mock_post = self._send(
            client, monkeypatch,
            email="alice@x.com", first_name="Alice", last_name="Smith",
        )
        payload = mock_post.call_args.kwargs["json"]
        assert "Alice Smith" in payload["subject"]
