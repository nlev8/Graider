"""Tests for LLMAdapter.generate_image (Phase 5c PR 1)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pybreaker
import pytest


def test_generate_image_types_exported_from_package():
    """ImageRequest and ImageResponse must be importable from the package root."""
    from backend.services.llm_adapter import ImageRequest, ImageResponse
    assert ImageRequest is not None
    assert ImageResponse is not None


def test_llm_adapter_protocol_declares_generate_image():
    """Every concrete adapter class must implement generate_image() to satisfy
    the @runtime_checkable LLMAdapter protocol."""
    from backend.services.llm_adapter import LLMAdapter, OpenAIAdapter, AnthropicAdapter, GeminiAdapter

    for cls in (OpenAIAdapter, AnthropicAdapter, GeminiAdapter):
        assert hasattr(cls, "generate_image"), f"{cls.__name__} missing generate_image()"

    # Runtime-checkable protocol recognition — instances must match structurally.
    openai = OpenAIAdapter(api_key="test-key")
    assert isinstance(openai, LLMAdapter)


def test_estimate_image_cost_known_model():
    from backend.services.llm_adapter.gemini_adapter import _estimate_image_cost_usd
    assert _estimate_image_cost_usd("gemini-2.5-flash-preview-image-generation", 1) == 0.04
    assert _estimate_image_cost_usd("gemini-2.5-flash-preview-image-generation", 3) == 0.12


def test_estimate_image_cost_unknown_model_defaults_to_base_rate():
    from backend.services.llm_adapter.gemini_adapter import _estimate_image_cost_usd
    assert _estimate_image_cost_usd("gemini-future-unknown", 1) == 0.04
    assert _estimate_image_cost_usd("gemini-future-unknown", 0) == 0.0


def _make_fake_response(image_bytes=b"\x89PNG\r\n\x1a\n", mime_type="image/png",
                        finish_reason_name="STOP", usage_prompt=5, usage_cand=10):
    """Build a MagicMock mimicking Gemini's GenerateContentResponse."""
    part = MagicMock()
    part.inline_data = MagicMock()
    part.inline_data.data = image_bytes
    part.inline_data.mime_type = mime_type
    candidate = MagicMock()
    candidate.content = MagicMock()
    candidate.content.parts = [part]
    candidate.finish_reason = MagicMock()
    candidate.finish_reason.name = finish_reason_name
    resp = MagicMock()
    resp.candidates = [candidate]
    resp.prompt_feedback = None
    return resp


def _make_empty_candidates_response(prompt_feedback_reason_name=None):
    """Build a response with empty candidates list (pre-candidate policy block)."""
    resp = MagicMock()
    resp.candidates = []
    if prompt_feedback_reason_name is not None:
        resp.prompt_feedback = MagicMock()
        resp.prompt_feedback.block_reason = MagicMock()
        resp.prompt_feedback.block_reason.name = prompt_feedback_reason_name
    else:
        resp.prompt_feedback = None
    return resp


def _clear_breakers():
    """Reset the module-level breaker registry — essential between tests
    that drive the breaker into OPEN state."""
    from backend.services.llm_adapter import breakers
    breakers._BREAKERS.clear()


def test_gemini_generate_image_happy_path():
    _clear_breakers()
    from backend.services.llm_adapter.gemini_adapter import GeminiAdapter
    from backend.services.llm_adapter.types import ImageRequest

    with patch("backend.services.llm_adapter.gemini_adapter.genai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.generate_content.return_value = _make_fake_response()

        adapter = GeminiAdapter(api_key="test-key")
        resp = adapter.generate_image(ImageRequest(
            prompt="a cat",
            model="gemini-2.5-flash-preview-image-generation",
        ))

    assert resp.images == [b"\x89PNG\r\n\x1a\n"]
    assert resp.mime_type == "image/png"
    assert resp.provider == "gemini"
    assert resp.model == "gemini-2.5-flash-preview-image-generation"
    assert resp.cost_usd == 0.04


def test_gemini_generate_image_with_reference_images():
    _clear_breakers()
    from backend.services.llm_adapter.gemini_adapter import GeminiAdapter
    from backend.services.llm_adapter.types import ImagePart, ImageRequest

    with patch("backend.services.llm_adapter.gemini_adapter.genai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.generate_content.return_value = _make_fake_response()

        adapter = GeminiAdapter(api_key="test-key")
        ref = ImagePart(url=None, base64="aGVsbG8=", mime_type="image/png")
        adapter.generate_image(ImageRequest(
            prompt="style-match this",
            model="gemini-2.5-flash-preview-image-generation",
            reference_images=[ref],
        ))

    kwargs = mock_client.models.generate_content.call_args.kwargs
    contents = kwargs["contents"]
    assert len(contents) == 2
    assert isinstance(contents[0], dict)
    assert contents[0].get("inline_data", {}).get("mime_type") == "image/png"
    assert contents[1] == "style-match this"


def test_gemini_generate_image_aspect_ratio_wired_into_config():
    _clear_breakers()
    from backend.services.llm_adapter.gemini_adapter import GeminiAdapter
    from backend.services.llm_adapter.types import ImageRequest

    with patch("backend.services.llm_adapter.gemini_adapter.genai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.generate_content.return_value = _make_fake_response()

        adapter = GeminiAdapter(api_key="test-key")
        adapter.generate_image(ImageRequest(
            prompt="wide shot",
            model="gemini-2.5-flash-preview-image-generation",
            aspect_ratio="16:9",
        ))

    kwargs = mock_client.models.generate_content.call_args.kwargs
    config = kwargs["config"]
    assert config.image_config.aspect_ratio == "16:9"


def test_gemini_generate_image_response_modalities_includes_image():
    _clear_breakers()
    from backend.services.llm_adapter.gemini_adapter import GeminiAdapter
    from backend.services.llm_adapter.types import ImageRequest

    with patch("backend.services.llm_adapter.gemini_adapter.genai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.generate_content.return_value = _make_fake_response()

        adapter = GeminiAdapter(api_key="test-key")
        adapter.generate_image(ImageRequest(
            prompt="hi",
            model="gemini-2.5-flash-preview-image-generation",
        ))

    kwargs = mock_client.models.generate_content.call_args.kwargs
    config = kwargs["config"]
    assert config.response_modalities == ["IMAGE"]


def test_gemini_generate_image_mime_type_from_sdk():
    _clear_breakers()
    from backend.services.llm_adapter.gemini_adapter import GeminiAdapter
    from backend.services.llm_adapter.types import ImageRequest

    with patch("backend.services.llm_adapter.gemini_adapter.genai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.generate_content.return_value = _make_fake_response(mime_type="image/jpeg")

        adapter = GeminiAdapter(api_key="test-key")
        resp = adapter.generate_image(ImageRequest(
            prompt="x",
            model="gemini-2.5-flash-preview-image-generation",
        ))

    assert resp.mime_type == "image/jpeg"


def test_gemini_generate_image_metadata_propagates_to_emit(monkeypatch):
    _clear_breakers()
    from backend.services.llm_adapter.gemini_adapter import GeminiAdapter
    from backend.services.llm_adapter.types import ImageRequest

    captured = []
    monkeypatch.setattr(
        "backend.services.llm_adapter.gemini_adapter.emit",
        lambda name, **kw: captured.append((name, kw)),
    )

    with patch("backend.services.llm_adapter.gemini_adapter.genai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.generate_content.return_value = _make_fake_response()

        adapter = GeminiAdapter(api_key="test-key")
        adapter.generate_image(ImageRequest(
            prompt="x",
            model="gemini-2.5-flash-preview-image-generation",
            metadata={"feature_label": "slide_generator_image"},
        ))

    start_events = [e for e in captured if e[0] == "llm.image.call.start"]
    complete_events = [e for e in captured if e[0] == "llm.image.call.complete"]
    assert len(start_events) == 1
    assert len(complete_events) == 1
    assert start_events[0][1].get("feature_label") == "slide_generator_image"
    assert complete_events[0][1]["image_count"] == 1
    assert complete_events[0][1]["cost_usd"] == 0.04


def test_gemini_generate_image_retry_disabled_by_default():
    _clear_breakers()
    from backend.services.llm_adapter.gemini_adapter import GeminiAdapter
    from backend.services.llm_adapter.types import ImageRequest

    call_count = {"n": 0}

    def side_effect(**_):
        call_count["n"] += 1
        raise ConnectionError("transient network blip")

    with patch("backend.services.llm_adapter.gemini_adapter.genai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.generate_content.side_effect = side_effect

        adapter = GeminiAdapter(api_key="test-key")
        with pytest.raises(ConnectionError):
            adapter.generate_image(ImageRequest(
                prompt="x",
                model="gemini-2.5-flash-preview-image-generation",
            ))

    assert call_count["n"] == 1


def test_gemini_generate_image_retry_enabled_on_request_flag():
    _clear_breakers()
    from backend.services.llm_adapter.gemini_adapter import GeminiAdapter
    from backend.services.llm_adapter.types import ImageRequest

    call_count = {"n": 0}
    success_response = _make_fake_response()

    def side_effect(**_):
        call_count["n"] += 1
        if call_count["n"] < 3:
            raise ConnectionError("transient blip")
        return success_response

    with patch("backend.services.llm_adapter.gemini_adapter.genai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.generate_content.side_effect = side_effect

        adapter = GeminiAdapter(api_key="test-key")
        resp = adapter.generate_image(ImageRequest(
            prompt="x",
            model="gemini-2.5-flash-preview-image-generation",
            retry=True,
        ))

    assert call_count["n"] == 3
    assert resp.images == [b"\x89PNG\r\n\x1a\n"]


def test_gemini_generate_image_circuit_breaker_propagates():
    _clear_breakers()
    from backend.services.llm_adapter import breakers
    from backend.services.llm_adapter.gemini_adapter import GeminiAdapter
    from backend.services.llm_adapter.types import ImageRequest

    b = breakers.get_breaker("gemini", "gemini-2.5-flash-preview-image-generation")
    for _ in range(breakers.FAIL_MAX):
        try:
            b.call(lambda: (_ for _ in ()).throw(ConnectionError("x")))
        except (ConnectionError, pybreaker.CircuitBreakerError):
            pass
    assert b.current_state == pybreaker.STATE_OPEN

    with patch("backend.services.llm_adapter.gemini_adapter.genai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        adapter = GeminiAdapter(api_key="test-key")
        with pytest.raises(pybreaker.CircuitBreakerError):
            adapter.generate_image(ImageRequest(
                prompt="x",
                model="gemini-2.5-flash-preview-image-generation",
            ))

        mock_client.models.generate_content.assert_not_called()


def test_gemini_generate_image_emits_error_on_failure(monkeypatch):
    _clear_breakers()
    from backend.services.llm_adapter.gemini_adapter import GeminiAdapter
    from backend.services.llm_adapter.types import ImageRequest

    captured = []
    breadcrumbs = []
    monkeypatch.setattr(
        "backend.services.llm_adapter.gemini_adapter.emit",
        lambda name, **kw: captured.append((name, kw)),
    )
    monkeypatch.setattr(
        "backend.services.llm_adapter.gemini_adapter.sentry_sdk.add_breadcrumb",
        lambda **kw: breadcrumbs.append(kw),
    )

    with patch("backend.services.llm_adapter.gemini_adapter.genai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.generate_content.side_effect = ConnectionError("down")

        adapter = GeminiAdapter(api_key="test-key")
        with pytest.raises(ConnectionError):
            adapter.generate_image(ImageRequest(
                prompt="x",
                model="gemini-2.5-flash-preview-image-generation",
            ))

    errors = [e for e in captured if e[0] == "llm.image.call.error"]
    assert len(errors) == 1
    assert errors[0][1]["error_kind"] == "ConnectionError"
    assert len(breadcrumbs) == 1


def test_gemini_generate_image_suppresses_error_event_for_circuit_breaker(monkeypatch):
    _clear_breakers()
    from backend.services.llm_adapter import breakers
    from backend.services.llm_adapter.gemini_adapter import GeminiAdapter
    from backend.services.llm_adapter.types import ImageRequest

    captured = []
    breadcrumbs = []
    monkeypatch.setattr(
        "backend.services.llm_adapter.gemini_adapter.emit",
        lambda name, **kw: captured.append((name, kw)),
    )
    monkeypatch.setattr(
        "backend.services.llm_adapter.gemini_adapter.sentry_sdk.add_breadcrumb",
        lambda **kw: breadcrumbs.append(kw),
    )

    b = breakers.get_breaker("gemini", "gemini-2.5-flash-preview-image-generation")
    for _ in range(breakers.FAIL_MAX):
        try:
            b.call(lambda: (_ for _ in ()).throw(ConnectionError("x")))
        except (ConnectionError, pybreaker.CircuitBreakerError):
            pass

    captured.clear()
    breadcrumbs.clear()

    with patch("backend.services.llm_adapter.gemini_adapter.genai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        adapter = GeminiAdapter(api_key="test-key")
        with pytest.raises(pybreaker.CircuitBreakerError):
            adapter.generate_image(ImageRequest(
                prompt="x",
                model="gemini-2.5-flash-preview-image-generation",
            ))

    errors = [e for e in captured if e[0] == "llm.image.call.error"]
    assert errors == [], f"CircuitBreakerError should NOT emit llm.image.call.error; got {errors}"
    assert breadcrumbs == [], f"CircuitBreakerError should NOT add a breadcrumb; got {breadcrumbs}"


def test_gemini_generate_image_safety_block_zero_inline_data(monkeypatch):
    """Response has candidate.finish_reason='SAFETY' and ZERO parts with inline_data.
    Expected: ImageResponse(images=[], cost_usd=0.0); llm.image.call.blocked fires."""
    _clear_breakers()
    from backend.services.llm_adapter.gemini_adapter import GeminiAdapter
    from backend.services.llm_adapter.types import ImageRequest

    captured = []
    monkeypatch.setattr(
        "backend.services.llm_adapter.gemini_adapter.emit",
        lambda name, **kw: captured.append((name, kw)),
    )

    empty_part = MagicMock()
    empty_part.inline_data = None
    candidate = MagicMock()
    candidate.content = MagicMock()
    candidate.content.parts = [empty_part]
    candidate.finish_reason = MagicMock()
    candidate.finish_reason.name = "SAFETY"
    resp = MagicMock()
    resp.candidates = [candidate]
    resp.prompt_feedback = None

    with patch("backend.services.llm_adapter.gemini_adapter.genai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.generate_content.return_value = resp

        adapter = GeminiAdapter(api_key="test-key")
        result = adapter.generate_image(ImageRequest(
            prompt="x",
            model="gemini-2.5-flash-preview-image-generation",
        ))

    assert result.images == []
    assert result.cost_usd == 0.0
    blocked = [e for e in captured if e[0] == "llm.image.call.blocked"]
    assert len(blocked) == 1
    assert blocked[0][1]["finish_reason"] == "SAFETY"


def test_gemini_generate_image_safe_on_empty_candidates(monkeypatch):
    """raw.candidates=[] AND prompt_feedback absent.
    Expected: empty ImageResponse, finish_reason='unknown'."""
    _clear_breakers()
    from backend.services.llm_adapter.gemini_adapter import GeminiAdapter
    from backend.services.llm_adapter.types import ImageRequest

    captured = []
    monkeypatch.setattr(
        "backend.services.llm_adapter.gemini_adapter.emit",
        lambda name, **kw: captured.append((name, kw)),
    )

    resp = _make_empty_candidates_response(prompt_feedback_reason_name=None)

    with patch("backend.services.llm_adapter.gemini_adapter.genai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.generate_content.return_value = resp

        adapter = GeminiAdapter(api_key="test-key")
        result = adapter.generate_image(ImageRequest(
            prompt="x",
            model="gemini-2.5-flash-preview-image-generation",
        ))

    assert result.images == []
    blocked = [e for e in captured if e[0] == "llm.image.call.blocked"]
    assert len(blocked) == 1
    assert blocked[0][1]["finish_reason"] == "unknown"


def test_gemini_generate_image_safe_on_none_content(monkeypatch):
    """raw.candidates=[candidate] where candidate.content is None.
    Expected: empty ImageResponse (no AttributeError)."""
    _clear_breakers()
    from backend.services.llm_adapter.gemini_adapter import GeminiAdapter
    from backend.services.llm_adapter.types import ImageRequest

    captured = []
    monkeypatch.setattr(
        "backend.services.llm_adapter.gemini_adapter.emit",
        lambda name, **kw: captured.append((name, kw)),
    )

    candidate = MagicMock()
    candidate.content = None
    candidate.finish_reason = MagicMock()
    candidate.finish_reason.name = "RECITATION"
    resp = MagicMock()
    resp.candidates = [candidate]
    resp.prompt_feedback = None

    with patch("backend.services.llm_adapter.gemini_adapter.genai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.generate_content.return_value = resp

        adapter = GeminiAdapter(api_key="test-key")
        result = adapter.generate_image(ImageRequest(
            prompt="x",
            model="gemini-2.5-flash-preview-image-generation",
        ))

    assert result.images == []
    blocked = [e for e in captured if e[0] == "llm.image.call.blocked"]
    assert len(blocked) == 1
    assert blocked[0][1]["finish_reason"] == "RECITATION"


def test_gemini_generate_image_empty_candidates_uses_prompt_feedback_block_reason(monkeypatch):
    """raw.candidates=[] AND raw.prompt_feedback.block_reason.name='SAFETY'.
    Expected: finish_reason='SAFETY' (Gemini Round-3 observability polish)."""
    _clear_breakers()
    from backend.services.llm_adapter.gemini_adapter import GeminiAdapter
    from backend.services.llm_adapter.types import ImageRequest

    captured = []
    monkeypatch.setattr(
        "backend.services.llm_adapter.gemini_adapter.emit",
        lambda name, **kw: captured.append((name, kw)),
    )

    resp = _make_empty_candidates_response(prompt_feedback_reason_name="SAFETY")

    with patch("backend.services.llm_adapter.gemini_adapter.genai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.generate_content.return_value = resp

        adapter = GeminiAdapter(api_key="test-key")
        result = adapter.generate_image(ImageRequest(
            prompt="x",
            model="gemini-2.5-flash-preview-image-generation",
        ))

    assert result.images == []
    blocked = [e for e in captured if e[0] == "llm.image.call.blocked"]
    assert len(blocked) == 1
    assert blocked[0][1]["finish_reason"] == "SAFETY"
