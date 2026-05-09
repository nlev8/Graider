"""Unit tests for backend/services/mathpix_ocr.py.

Audit MAJOR #4 sprint follow-up to PR #268. Targets 52 uncovered LOC
(28% baseline).

Strategy
--------
Six functions:
  1. `_get_credentials` — env-var read; mock `os.getenv`
  2. `is_available` — composition of `_get_credentials`
  3. `image_to_latex` — main entry; mocks `requests.post` for HTTP scenarios
  4. `_extract_confidence` — pure function over Mathpix response shapes
  5. `extract_answer_from_image` — high-level composition; calls
     `image_to_latex` then `_clean_ocr_text`
  6. `_clean_ocr_text` — pure function for OCR artifact cleanup

Pure helpers (`_extract_confidence`, `_clean_ocr_text`) are tested directly.
HTTP-dependent paths use `unittest.mock.patch("...mathpix_ocr.requests")`.

Per `feedback_codex_always_high_effort.md`, the merge review uses Codex
high-effort.
"""
from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest

import requests as _requests  # for type-checking exception classes


# ──────────────────────────────────────────────────────────────────
# _get_credentials
# ──────────────────────────────────────────────────────────────────


class TestGetCredentials:
    def test_both_set_returns_pair(self):
        from backend.services.mathpix_ocr import _get_credentials

        with patch.dict("os.environ",
                        {"MATHPIX_APP_ID": "id-1", "MATHPIX_APP_KEY": "key-1"}):
            assert _get_credentials() == ("id-1", "key-1")

    def test_missing_app_id_returns_none_pair(self):
        from backend.services.mathpix_ocr import _get_credentials

        with patch.dict("os.environ",
                        {"MATHPIX_APP_ID": "", "MATHPIX_APP_KEY": "key-1"},
                        clear=False):
            assert _get_credentials() == (None, None)

    def test_missing_app_key_returns_none_pair(self):
        from backend.services.mathpix_ocr import _get_credentials

        with patch.dict("os.environ",
                        {"MATHPIX_APP_ID": "id-1", "MATHPIX_APP_KEY": ""},
                        clear=False):
            assert _get_credentials() == (None, None)

    def test_both_missing_returns_none_pair(self):
        from backend.services.mathpix_ocr import _get_credentials

        # Patch both to empty so the production `or ''` defaults take effect
        with patch.dict("os.environ",
                        {"MATHPIX_APP_ID": "", "MATHPIX_APP_KEY": ""},
                        clear=False):
            assert _get_credentials() == (None, None)

    def test_credentials_are_platform_global_not_per_tenant(self):
        # PR #269 Codex round-1 MINOR fold: pin the contract that Mathpix
        # creds are platform-owned (not per-teacher / per-district). Graider
        # pays for OCR centrally; tenants don't supply their own keys.
        # `_get_credentials` takes NO arguments — the function signature
        # already enforces this contract, but a regression that adds a
        # `teacher_id` parameter (intending per-tenant scoping) would change
        # observable behavior. This test pins the no-args contract.
        import inspect
        from backend.services.mathpix_ocr import _get_credentials

        sig = inspect.signature(_get_credentials)
        assert len(sig.parameters) == 0, (
            "Mathpix creds are platform-owned: _get_credentials() takes no "
            "tenant args. If you're adding per-tenant Mathpix billing, that "
            "is a contract change requiring documentation and migration."
        )


# ──────────────────────────────────────────────────────────────────
# is_available
# ──────────────────────────────────────────────────────────────────


class TestIsAvailable:
    def test_returns_true_when_creds_present(self):
        from backend.services.mathpix_ocr import is_available

        with patch("backend.services.mathpix_ocr._get_credentials",
                   return_value=("id", "key")):
            assert is_available() is True

    def test_returns_false_when_creds_missing(self):
        from backend.services.mathpix_ocr import is_available

        with patch("backend.services.mathpix_ocr._get_credentials",
                   return_value=(None, None)):
            assert is_available() is False

    def test_returns_false_when_partial_creds(self):
        from backend.services.mathpix_ocr import is_available

        with patch("backend.services.mathpix_ocr._get_credentials",
                   return_value=("id", None)):
            assert is_available() is False


# ──────────────────────────────────────────────────────────────────
# image_to_latex — main HTTP-driven entry
# ──────────────────────────────────────────────────────────────────


def _make_response(json_data, status_code=200):
    """Build a mock requests.Response (success — raise_for_status no-op)."""
    r = MagicMock()
    r.json.return_value = json_data
    r.status_code = status_code
    r.text = "body"
    r.raise_for_status = MagicMock()
    return r


def _make_error_response(status_code, body):
    """Build a falsey mock Response that triggers HTTPError on raise_for_status.

    PR #269 Codex round-1 MAJOR fold: real `requests.Response` for 4xx/5xx
    is FALSEY (Response.__bool__ returns self.ok). This mock matches that
    so the production check `if e.response is not None:` is exercised on
    realistic input. The previous truthy `MagicMock()` could not detect
    the production bug where `if e.response:` was used instead.
    """
    r = MagicMock(spec=_requests.Response)
    r.status_code = status_code
    r.text = body
    # `__bool__` returns False so falsey-checks fail (matches real Response)
    r.__bool__ = lambda self: False
    # raise_for_status raises HTTPError with the response attached
    err = _requests.exceptions.HTTPError(response=r)
    r.raise_for_status = MagicMock(side_effect=err)
    return r


class TestImageToLatex:
    def test_no_credentials_returns_error_dict(self):
        from backend.services.mathpix_ocr import image_to_latex

        with patch("backend.services.mathpix_ocr._get_credentials",
                   return_value=(None, None)):
            result = image_to_latex("base64data")
        assert result["latex"] == ""
        assert result["text"] == ""
        assert result["confidence"] == 0
        assert result["raw"] == {}
        assert "credentials not configured" in result["error"]

    def test_data_uri_prefix_used_as_src_directly(self):
        from backend.services.mathpix_ocr import image_to_latex

        with patch("backend.services.mathpix_ocr._get_credentials",
                   return_value=("id", "key")), \
             patch("backend.services.mathpix_ocr.requests") as mock_requests:
            mock_requests.post.return_value = _make_response({
                "latex_styled": "x^2", "text": "x^2", "confidence_rate": 0.9,
            })
            mock_requests.exceptions = _requests.exceptions
            image_to_latex("data:image/jpeg;base64,abcd1234")
        payload = mock_requests.post.call_args.kwargs["json"]
        assert payload["src"] == "data:image/jpeg;base64,abcd1234"

    def test_raw_base64_gets_png_data_uri_prefix(self):
        from backend.services.mathpix_ocr import image_to_latex

        with patch("backend.services.mathpix_ocr._get_credentials",
                   return_value=("id", "key")), \
             patch("backend.services.mathpix_ocr.requests") as mock_requests:
            mock_requests.post.return_value = _make_response({})
            mock_requests.exceptions = _requests.exceptions
            image_to_latex("rawbase64xyz")
        payload = mock_requests.post.call_args.kwargs["json"]
        assert payload["src"] == "data:image/png;base64,rawbase64xyz"

    def test_default_formats_when_none_provided(self):
        from backend.services.mathpix_ocr import image_to_latex

        with patch("backend.services.mathpix_ocr._get_credentials",
                   return_value=("id", "key")), \
             patch("backend.services.mathpix_ocr.requests") as mock_requests:
            mock_requests.post.return_value = _make_response({})
            mock_requests.exceptions = _requests.exceptions
            image_to_latex("data:image/png;base64,abc")
        payload = mock_requests.post.call_args.kwargs["json"]
        assert payload["formats"] == ["latex_styled", "text"]

    def test_custom_formats_passed_through(self):
        from backend.services.mathpix_ocr import image_to_latex

        with patch("backend.services.mathpix_ocr._get_credentials",
                   return_value=("id", "key")), \
             patch("backend.services.mathpix_ocr.requests") as mock_requests:
            mock_requests.post.return_value = _make_response({})
            mock_requests.exceptions = _requests.exceptions
            image_to_latex(
                "data:image/png;base64,abc",
                formats=["mathml", "asciimath"],
            )
        payload = mock_requests.post.call_args.kwargs["json"]
        assert payload["formats"] == ["mathml", "asciimath"]

    def test_credentials_in_headers(self):
        from backend.services.mathpix_ocr import image_to_latex

        with patch("backend.services.mathpix_ocr._get_credentials",
                   return_value=("my-app-id", "my-app-key")), \
             patch("backend.services.mathpix_ocr.requests") as mock_requests:
            mock_requests.post.return_value = _make_response({})
            mock_requests.exceptions = _requests.exceptions
            image_to_latex("data:image/png;base64,abc")
        headers = mock_requests.post.call_args.kwargs["headers"]
        assert headers["app_id"] == "my-app-id"
        assert headers["app_key"] == "my-app-key"
        assert headers["Content-Type"] == "application/json"

    def test_endpoint_url(self):
        from backend.services.mathpix_ocr import image_to_latex

        with patch("backend.services.mathpix_ocr._get_credentials",
                   return_value=("id", "key")), \
             patch("backend.services.mathpix_ocr.requests") as mock_requests:
            mock_requests.post.return_value = _make_response({})
            mock_requests.exceptions = _requests.exceptions
            image_to_latex("data:image/png;base64,abc")
        url = mock_requests.post.call_args.args[0]
        assert url == "https://api.mathpix.com/v3/text"

    def test_timeout_passed_through(self):
        from backend.services.mathpix_ocr import image_to_latex

        with patch("backend.services.mathpix_ocr._get_credentials",
                   return_value=("id", "key")), \
             patch("backend.services.mathpix_ocr.requests") as mock_requests:
            mock_requests.post.return_value = _make_response({})
            mock_requests.exceptions = _requests.exceptions
            image_to_latex("data:image/png;base64,abc")
        assert mock_requests.post.call_args.kwargs["timeout"] == 30

    def test_successful_response_extracts_fields(self):
        from backend.services.mathpix_ocr import image_to_latex

        api_response = {
            "latex_styled": r"\frac{x}{2}",
            "text": "x/2",
            "confidence_rate": 0.95,
        }
        with patch("backend.services.mathpix_ocr._get_credentials",
                   return_value=("id", "key")), \
             patch("backend.services.mathpix_ocr.requests") as mock_requests:
            mock_requests.post.return_value = _make_response(api_response)
            mock_requests.exceptions = _requests.exceptions
            result = image_to_latex("data:image/png;base64,abc")
        assert result["latex"] == r"\frac{x}{2}"
        assert result["text"] == "x/2"
        assert result["confidence"] == 0.95
        assert result["raw"] == api_response
        assert result["error"] is None

    def test_falls_back_to_latex_normal(self):
        # When latex_styled is missing, fall back to latex_normal
        from backend.services.mathpix_ocr import image_to_latex

        with patch("backend.services.mathpix_ocr._get_credentials",
                   return_value=("id", "key")), \
             patch("backend.services.mathpix_ocr.requests") as mock_requests:
            mock_requests.post.return_value = _make_response({
                "latex_normal": "x", "text": "x",
            })
            mock_requests.exceptions = _requests.exceptions
            result = image_to_latex("data:image/png;base64,abc")
        assert result["latex"] == "x"

    def test_response_with_api_error_passes_through(self):
        # Mathpix returns 200 OK but with `error` in the JSON body
        from backend.services.mathpix_ocr import image_to_latex

        with patch("backend.services.mathpix_ocr._get_credentials",
                   return_value=("id", "key")), \
             patch("backend.services.mathpix_ocr.requests") as mock_requests:
            mock_requests.post.return_value = _make_response({
                "error": "image_no_content", "latex_styled": "",
            })
            mock_requests.exceptions = _requests.exceptions
            result = image_to_latex("data:image/png;base64,abc")
        assert result["error"] == "image_no_content"

    def test_timeout_exception_returns_error(self):
        from backend.services.mathpix_ocr import image_to_latex

        with patch("backend.services.mathpix_ocr._get_credentials",
                   return_value=("id", "key")), \
             patch("backend.services.mathpix_ocr.requests") as mock_requests:
            mock_requests.exceptions = _requests.exceptions
            mock_requests.post.side_effect = _requests.exceptions.Timeout()
            result = image_to_latex("data:image/png;base64,abc")
        assert "timed out" in result["error"]
        assert result["latex"] == ""
        assert result["confidence"] == 0

    def test_http_error_with_response_through_raise_for_status(self):
        # PR #269 Codex round-1 MAJOR fold: exercise the REAL flow where
        # requests.post returns successfully but raise_for_status() raises
        # HTTPError. Uses a falsey-Response mock that matches the real
        # `requests.Response.__bool__` semantics for 4xx/5xx — without this,
        # the test would still pass even if production line 100
        # (`response.raise_for_status()`) were deleted.
        from backend.services.mathpix_ocr import image_to_latex

        err_resp = _make_error_response(401, "Unauthorized: invalid app_key")

        with patch("backend.services.mathpix_ocr._get_credentials",
                   return_value=("id", "key")), \
             patch("backend.services.mathpix_ocr.requests") as mock_requests:
            mock_requests.exceptions = _requests.exceptions
            mock_requests.post.return_value = err_resp
            result = image_to_latex("data:image/png;base64,abc")
        # raise_for_status() actually fired (proves line 100 not stubbed)
        err_resp.raise_for_status.assert_called_once()
        # Status code + body extracted via `is not None` check (NOT truthy
        # check) — falsey 4xx response would otherwise mask both fields.
        assert "401" in result["error"]
        assert "Unauthorized: invalid app_key" in result["error"]

    def test_http_error_with_5xx_response_extracts_body(self):
        # Symmetric coverage: 5xx Response is also falsey in real requests
        # but `is not None` check still extracts the body. Pins the
        # production fix for `if e.response:` → `if e.response is not None`.
        from backend.services.mathpix_ocr import image_to_latex

        err_resp = _make_error_response(500, "internal server error")

        with patch("backend.services.mathpix_ocr._get_credentials",
                   return_value=("id", "key")), \
             patch("backend.services.mathpix_ocr.requests") as mock_requests:
            mock_requests.exceptions = _requests.exceptions
            mock_requests.post.return_value = err_resp
            result = image_to_latex("data:image/png;base64,abc")
        assert "500" in result["error"]
        assert "internal server error" in result["error"]
        # Confirm we did NOT fall into the "HTTP unknown" branch
        assert "unknown" not in result["error"]

    def test_http_error_without_response_uses_unknown(self):
        # HTTPError with no response attribute — production uses 'unknown'.
        # This stays a side_effect-from-post pattern because the bare
        # HTTPError can't be raised by raise_for_status (no Response).
        from backend.services.mathpix_ocr import image_to_latex

        http_err = _requests.exceptions.HTTPError()
        http_err.response = None

        with patch("backend.services.mathpix_ocr._get_credentials",
                   return_value=("id", "key")), \
             patch("backend.services.mathpix_ocr.requests") as mock_requests:
            mock_requests.exceptions = _requests.exceptions
            mock_requests.post.side_effect = http_err
            result = image_to_latex("data:image/png;base64,abc")
        assert "HTTP unknown" in result["error"]

    def test_generic_exception_returns_error(self):
        from backend.services.mathpix_ocr import image_to_latex

        with patch("backend.services.mathpix_ocr._get_credentials",
                   return_value=("id", "key")), \
             patch("backend.services.mathpix_ocr.requests") as mock_requests:
            mock_requests.exceptions = _requests.exceptions
            mock_requests.post.side_effect = ValueError("connection reset")
            result = image_to_latex("data:image/png;base64,abc")
        assert "Mathpix API error" in result["error"]
        assert "connection reset" in result["error"]

    def test_response_truncates_body_to_200_chars(self):
        # HTTPError body is truncated at 200 chars in the error message.
        # Uses the real raise_for_status path via _make_error_response.
        from backend.services.mathpix_ocr import image_to_latex

        err_resp = _make_error_response(500, "X" * 500)

        with patch("backend.services.mathpix_ocr._get_credentials",
                   return_value=("id", "key")), \
             patch("backend.services.mathpix_ocr.requests") as mock_requests:
            mock_requests.exceptions = _requests.exceptions
            mock_requests.post.return_value = err_resp
            result = image_to_latex("data:image/png;base64,abc")
        # Body truncation: 200 X's, not 500
        assert "X" * 200 in result["error"]
        assert "X" * 201 not in result["error"]


# ──────────────────────────────────────────────────────────────────
# _extract_confidence — pure function
# ──────────────────────────────────────────────────────────────────


class TestExtractConfidence:
    def test_top_level_confidence_rate(self):
        from backend.services.mathpix_ocr import _extract_confidence

        assert _extract_confidence({"confidence_rate": 0.87}) == 0.87

    def test_confidence_rate_takes_priority_over_line_data(self):
        from backend.services.mathpix_ocr import _extract_confidence

        # Both present — `confidence_rate` wins because the if-branch returns
        # before reaching `line_data`.
        result = _extract_confidence({
            "confidence_rate": 0.99,
            "line_data": [{"confidence": 0.1}, {"confidence": 0.2}],
        })
        assert result == 0.99

    def test_line_data_average_when_no_top_level_rate(self):
        from backend.services.mathpix_ocr import _extract_confidence

        result = _extract_confidence({
            "line_data": [
                {"confidence": 0.8},
                {"confidence": 0.6},
                {"confidence": 0.4},
            ],
        })
        # avg = (0.8 + 0.6 + 0.4) / 3 = 0.6
        assert result == pytest.approx(0.6)

    def test_line_data_empty_returns_zero(self):
        from backend.services.mathpix_ocr import _extract_confidence

        assert _extract_confidence({"line_data": []}) == 0

    def test_line_data_skips_lines_without_confidence_field(self):
        from backend.services.mathpix_ocr import _extract_confidence

        result = _extract_confidence({
            "line_data": [
                {"confidence": 0.5},
                {"text": "no confidence key here"},
                {"confidence": 0.7},
            ],
        })
        # avg = (0.5 + 0.7) / 2 = 0.6
        assert result == pytest.approx(0.6)

    def test_line_data_all_missing_confidence_returns_zero(self):
        from backend.services.mathpix_ocr import _extract_confidence

        assert _extract_confidence({
            "line_data": [{"text": "a"}, {"text": "b"}],
        }) == 0

    def test_fallback_confidence_field(self):
        from backend.services.mathpix_ocr import _extract_confidence

        # Neither confidence_rate nor line_data — falls back to top-level
        # `confidence` field.
        assert _extract_confidence({"confidence": 0.42}) == 0.42

    def test_no_confidence_data_returns_zero_default(self):
        from backend.services.mathpix_ocr import _extract_confidence

        assert _extract_confidence({}) == 0


# ──────────────────────────────────────────────────────────────────
# extract_answer_from_image
# ──────────────────────────────────────────────────────────────────


class TestExtractAnswerFromImage:
    def test_propagates_image_to_latex_error(self):
        from backend.services.mathpix_ocr import extract_answer_from_image

        with patch("backend.services.mathpix_ocr.image_to_latex",
                   return_value={
                       "latex": "", "text": "",
                       "confidence": 0, "raw": {},
                       "error": "creds missing",
                   }):
            result = extract_answer_from_image("data:image/png;base64,abc")
        assert result["error"] == "creds missing"
        assert result["extracted_text"] == ""
        assert result["latex"] == ""
        assert result["confidence"] == 0
        assert result["ocr_source"] == "mathpix"

    def test_math_question_prefers_latex(self):
        from backend.services.mathpix_ocr import extract_answer_from_image

        with patch("backend.services.mathpix_ocr.image_to_latex",
                   return_value={
                       "latex": r"\frac{1}{2}", "text": "1/2",
                       "confidence": 0.9, "raw": {}, "error": None,
                   }):
            result = extract_answer_from_image(
                "x", question_type="math_equation",
            )
        assert result["extracted_text"] == r"\frac{1}{2}"

    def test_geometry_type_prefers_latex(self):
        from backend.services.mathpix_ocr import extract_answer_from_image

        with patch("backend.services.mathpix_ocr.image_to_latex",
                   return_value={
                       "latex": r"\angle ABC = 30^\circ",
                       "text": "angle ABC = 30 degrees",
                       "confidence": 1, "raw": {}, "error": None,
                   }):
            result = extract_answer_from_image(
                "x", question_type="geometry",
            )
        assert result["extracted_text"] == r"\angle ABC = 30^\circ"

    def test_data_table_type_prefers_latex(self):
        from backend.services.mathpix_ocr import extract_answer_from_image

        with patch("backend.services.mathpix_ocr.image_to_latex",
                   return_value={
                       "latex": "tex-form",
                       "text": "text-form",
                       "confidence": 1, "raw": {}, "error": None,
                   }):
            result = extract_answer_from_image(
                "x", question_type="data_table",
            )
        assert result["extracted_text"] == "tex-form"

    def test_text_question_type_prefers_text(self):
        from backend.services.mathpix_ocr import extract_answer_from_image

        with patch("backend.services.mathpix_ocr.image_to_latex",
                   return_value={
                       "latex": "tex", "text": "Hello world",
                       "confidence": 0.9, "raw": {}, "error": None,
                   }):
            result = extract_answer_from_image(
                "x", question_type="short_answer",
            )
        assert result["extracted_text"] == "Hello world"

    def test_math_falls_back_to_text_when_latex_empty(self):
        from backend.services.mathpix_ocr import extract_answer_from_image

        with patch("backend.services.mathpix_ocr.image_to_latex",
                   return_value={
                       "latex": "", "text": "fallback text",
                       "confidence": 0.7, "raw": {}, "error": None,
                   }):
            result = extract_answer_from_image(
                "x", question_type="math_equation",
            )
        assert result["extracted_text"] == "fallback text"

    def test_text_falls_back_to_latex_when_text_empty(self):
        from backend.services.mathpix_ocr import extract_answer_from_image

        with patch("backend.services.mathpix_ocr.image_to_latex",
                   return_value={
                       "latex": "fallback latex", "text": "",
                       "confidence": 0.5, "raw": {}, "error": None,
                   }):
            result = extract_answer_from_image(
                "x", question_type="short_answer",
            )
        assert result["extracted_text"] == "fallback latex"

    def test_default_question_type_is_math_equation(self):
        from backend.services.mathpix_ocr import extract_answer_from_image

        with patch("backend.services.mathpix_ocr.image_to_latex",
                   return_value={
                       "latex": "math_default",
                       "text": "text_default",
                       "confidence": 1, "raw": {}, "error": None,
                   }):
            result = extract_answer_from_image("x")
        # No question_type → defaults to math_equation → prefers latex
        assert result["extracted_text"] == "math_default"

    def test_clean_ocr_text_called(self):
        # Pin that the post-extract cleanup runs (verified by the dollar-sign
        # strip behavior, which is in _clean_ocr_text)
        from backend.services.mathpix_ocr import extract_answer_from_image

        with patch("backend.services.mathpix_ocr.image_to_latex",
                   return_value={
                       "latex": "$x^2$", "text": "$x^2$",
                       "confidence": 1, "raw": {}, "error": None,
                   }):
            result = extract_answer_from_image(
                "x", question_type="math_equation",
            )
        # Outer $...$ gets stripped by _clean_ocr_text
        assert result["extracted_text"] == "x^2"

    def test_response_shape_constant(self):
        from backend.services.mathpix_ocr import extract_answer_from_image

        with patch("backend.services.mathpix_ocr.image_to_latex",
                   return_value={
                       "latex": "x", "text": "x", "confidence": 1,
                       "raw": {}, "error": None,
                   }):
            result = extract_answer_from_image("x")
        # Required keys
        assert set(result.keys()) >= {
            "extracted_text", "latex", "confidence", "ocr_source", "error",
        }
        assert result["ocr_source"] == "mathpix"


# ──────────────────────────────────────────────────────────────────
# _clean_ocr_text — pure function
# ──────────────────────────────────────────────────────────────────


class TestCleanOcrText:
    def test_empty_string_returns_empty(self):
        from backend.services.mathpix_ocr import _clean_ocr_text
        assert _clean_ocr_text("") == ""

    def test_none_treated_as_empty(self):
        from backend.services.mathpix_ocr import _clean_ocr_text
        assert _clean_ocr_text(None) == ""

    def test_whitespace_stripped(self):
        from backend.services.mathpix_ocr import _clean_ocr_text
        assert _clean_ocr_text("   x^2   ") == "x^2"

    def test_single_dollar_signs_stripped(self):
        from backend.services.mathpix_ocr import _clean_ocr_text
        assert _clean_ocr_text("$x^2$") == "x^2"

    def test_double_dollar_signs_stripped(self):
        from backend.services.mathpix_ocr import _clean_ocr_text
        assert _clean_ocr_text("$$x^2$$") == "x^2"

    def test_multiple_spaces_collapsed(self):
        from backend.services.mathpix_ocr import _clean_ocr_text
        # The regex collapses 2+ spaces to single. Single spaces preserved.
        assert _clean_ocr_text("a    b   c d") == "a b c d"

    def test_double_space_collapsed(self):
        from backend.services.mathpix_ocr import _clean_ocr_text
        assert _clean_ocr_text("a  b") == "a b"

    def test_single_space_preserved(self):
        from backend.services.mathpix_ocr import _clean_ocr_text
        # `re.sub(r'  +', ' ', ...)` requires 2+ spaces — single preserved
        assert _clean_ocr_text("a b c") == "a b c"

    def test_dollar_strip_then_whitespace_strip(self):
        from backend.services.mathpix_ocr import _clean_ocr_text
        # The `[1:-1].strip()` after dollar strip handles whitespace inside
        assert _clean_ocr_text("$ inner content $") == "inner content"

    def test_double_dollar_strip_then_whitespace_strip(self):
        from backend.services.mathpix_ocr import _clean_ocr_text
        assert _clean_ocr_text("$$  spaced  $$") == "spaced"

    def test_only_leading_dollar_not_stripped(self):
        # Production checks BOTH startswith AND endswith — only one shouldn't strip
        from backend.services.mathpix_ocr import _clean_ocr_text
        # "$x" doesn't end with "$" → not stripped
        assert _clean_ocr_text("$x") == "$x"

    def test_only_trailing_dollar_not_stripped(self):
        from backend.services.mathpix_ocr import _clean_ocr_text
        assert _clean_ocr_text("x$") == "x$"
