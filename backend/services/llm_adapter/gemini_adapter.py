"""Gemini adapter for the Phase 5a LLM adapter layer.

Maps LLMRequest/Response to/from google.generativeai.GenerativeModel.generate_content.

Key differences from OpenAI/Anthropic:
- system_prompt maps to system_instruction= at model creation time
- messages map to contents= as a list of {role, parts} dicts
- Gemini uses role "model" not "assistant" — we map "assistant" → "model"
- Multimodal image input uses {"inline_data": {"mime_type": ..., "data": base64}}
  for base64, or {"file_data": {"mime_type": ..., "file_uri": url}} for URLs;
  for plain HTTP URLs we fall back to {"text": url} with a note (Gemini's
  URL support is limited to Cloud Storage URIs)
- Response is a GenerateContentResponse; text is response.text, parts are
  in response.candidates[0].content.parts
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any

import google.generativeai as genai
import sentry_sdk

from backend.observability.events import emit
from backend.retry import with_retry
from backend.services.llm_adapter.types import (
    ImagePart,
    LLMRequest,
    LLMResponse,
    Message,
    TextPart,
    ToolCall,
    Usage,
    normalize_finish_reason,
)

_logger = logging.getLogger(__name__)


def _estimate_cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Rough per-1K-token pricing for Gemini models (verify against
    https://ai.google.dev/gemini-api/docs/pricing when adding a new model)."""
    rates = {
        # gemini-2.0-flash is $0.10 / $0.40 per million tokens (not $0.075 / $0.30).
        "gemini-2.0-flash": (0.0001, 0.0004),
        "gemini-1.5-pro": (0.00125, 0.005),
        "gemini-1.5-flash": (0.000075, 0.0003),
    }
    in_rate, out_rate = rates.get(model, (0.0001, 0.0004))
    return round(prompt_tokens * in_rate / 1000 + completion_tokens * out_rate / 1000, 6)


def _part_to_gemini(p: Any) -> dict[str, Any]:
    """Map a single ContentPart to a Gemini part dict."""
    if isinstance(p, TextPart):
        return {"text": p.text}
    elif isinstance(p, ImagePart):
        if p.base64:
            return {"inline_data": {"mime_type": p.mime_type, "data": p.base64}}
        else:
            # Gemini natively supports gs:// URIs; plain HTTPS URLs are passed
            # through — Gemini Flash will attempt to fetch them at inference time.
            return {"file_data": {"mime_type": p.mime_type, "file_uri": p.url}}
    # ToolUsePart / ToolResultPart not handled here — tool-use is D2 scope
    return {"text": str(p)}


def _message_to_gemini(msg: Message) -> dict[str, Any]:
    # Gemini uses "user" and "model" (not "assistant")
    role = "model" if msg.role == "assistant" else "user"
    parts = [_part_to_gemini(p) for p in msg.content]
    return {"role": role, "parts": parts}


class GeminiAdapter:
    """Adapter for Google's Gemini generative AI API (google.generativeai)."""

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self._provider = "gemini"

    def chat(self, request: LLMRequest) -> LLMResponse:
        genai.configure(api_key=self._api_key)

        model_kwargs: dict[str, Any] = {}
        if request.system_prompt:
            model_kwargs["system_instruction"] = request.system_prompt

        model = genai.GenerativeModel(request.model, **model_kwargs)

        contents = [_message_to_gemini(msg) for msg in request.messages]

        # For single-turn requests with only a user message, Gemini also accepts
        # a plain string — but we always use the list form for consistency.
        generation_config: dict[str, Any] = {}
        if request.max_tokens is not None:
            generation_config["max_output_tokens"] = request.max_tokens
        if request.temperature is not None:
            generation_config["temperature"] = request.temperature
        if request.response_format is not None:
            # Gemini's generation_config.response_mime_type enforces JSON output
            # when set to "application/json". json_schema adds response_schema.
            if request.response_format.type in ("json_object", "json_schema"):
                generation_config["response_mime_type"] = "application/json"
            if request.response_format.type == "json_schema" and request.response_format.schema:
                generation_config["response_schema"] = request.response_format.schema

        # Plumb timeout through the SDK's request_options.
        request_options = {"timeout": request.timeout}

        emit(
            "llm.call.start",
            provider=self._provider,
            model=request.model,
            **{k: v for k, v in request.metadata.items() if isinstance(v, (str, int, float, bool))},
        )
        t0 = time.monotonic()

        try:
            raw = with_retry(
                lambda: model.generate_content(
                    contents,
                    generation_config=generation_config if generation_config else None,
                    request_options=request_options,
                ),
                label=f"gemini.generate_content({request.model})",
            )
        except Exception as e:
            duration_ms = int((time.monotonic() - t0) * 1000)
            emit(
                "llm.call.error",
                level="warning",
                provider=self._provider,
                model=request.model,
                duration_ms=duration_ms,
                error_kind=type(e).__name__,
            )
            sentry_sdk.add_breadcrumb(
                category="llm.call",
                level="warning",
                message=f"gemini.generate_content failed for {request.model}",
                data={"provider": self._provider, "model": request.model, "error_kind": type(e).__name__, "duration_ms": duration_ms},
            )
            raise

        duration_ms = int((time.monotonic() - t0) * 1000)

        # Extract text from response
        content_parts = []
        try:
            text = raw.text
            if text:
                content_parts.append(TextPart(text=text))
        except Exception:
            # raw.text raises if the response was blocked; try parts directly
            try:
                candidate = raw.candidates[0]
                for part in candidate.content.parts:
                    if hasattr(part, "text") and part.text:
                        content_parts.append(TextPart(text=part.text))
            except Exception:
                pass

        # Usage metadata (may not be present on all Gemini responses)
        prompt_tokens = 0
        completion_tokens = 0
        try:
            if hasattr(raw, "usage_metadata") and raw.usage_metadata:
                prompt_tokens = getattr(raw.usage_metadata, "prompt_token_count", 0) or 0
                completion_tokens = getattr(raw.usage_metadata, "candidates_token_count", 0) or 0
        except Exception:
            pass

        usage = Usage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=_estimate_cost_usd(request.model, prompt_tokens, completion_tokens),
        )

        # Finish reason — Gemini returns an enum; extract string then normalize
        # through the shared map so consumers see the canonical 4 values
        # (stop/length/tool_use/content_filter).
        raw_finish_reason = None
        try:
            candidate = raw.candidates[0]
            fr = candidate.finish_reason
            raw_finish_reason = fr.name if hasattr(fr, "name") else str(fr)
        except Exception:
            pass
        # Map Gemini's integer enum values (1=STOP, 2=MAX_TOKENS) before normalize
        if raw_finish_reason == "1":
            raw_finish_reason = "stop"
        elif raw_finish_reason == "2":
            raw_finish_reason = "max_tokens_reached"
        finish_reason = normalize_finish_reason(raw_finish_reason)

        emit(
            "llm.call.complete",
            provider=self._provider,
            model=request.model,
            duration_ms=duration_ms,
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            cost_usd=usage.cost_usd,
            finish_reason=finish_reason,
        )

        # Prefer the provider-reported model ID (consistent with OpenAI/Anthropic
        # adapters). Gemini's raw response doesn't always expose `.model`, so
        # fall back to the request alias when unavailable.
        response_model = getattr(raw, "model_version", None) or getattr(raw, "model", None) or request.model

        return LLMResponse(
            content_parts=content_parts,
            tool_calls=[],  # tool-use is D2 scope
            usage=usage,
            finish_reason=finish_reason,
            provider=self._provider,
            model=response_model,
        )
