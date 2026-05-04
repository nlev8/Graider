"""Gemini adapter for the Phase 5a LLM adapter layer.

Maps LLMRequest/Response to/from the google.genai SDK (google-genai package).

Key differences from OpenAI/Anthropic:
- system_prompt maps to system_instruction= in GenerateContentConfig
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

import json as _json
import logging
import os
import time
import uuid
from typing import Any, Iterator

import pybreaker
from google import genai
from google.genai import types as genai_types
import sentry_sdk

from backend.services.llm_adapter.breakers import get_breaker

from backend.observability.events import emit
from backend.retry import with_retry
from backend.services.llm_adapter.streaming import (
    FinishEvent,
    StreamEvent,
    TextDelta,
    ToolCallComplete,
    ToolCallDelta,
    UsageEvent,
)
from backend.services.llm_adapter.types import (
    ImagePart,
    ImageRequest,
    ImageResponse,
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


def _estimate_image_cost_usd(model: str, image_count: int) -> float:
    """Per-image flat-rate pricing. Verify against
    https://ai.google.dev/gemini-api/docs/pricing when adding a new model."""
    rates = {
        # $0.04 per image as of 2026-04
        "gemini-2.5-flash-preview-image-generation": 0.04,
    }
    return round(rates.get(model, 0.04) * image_count, 6)


def _part_to_gemini(p: Any) -> dict[str, Any]:
    """Map a single ContentPart to a Gemini part dict.

    Tool-use blocks map to Gemini's function_call/function_response shape:
      - ToolUsePart (assistant-side request) -> {"function_call": {name, args}}
      - ToolResultPart (user-side result)    -> {"function_response": {name, response}}

    Note: Gemini's function_response requires the tool NAME alongside the
    result. ToolResultPart only carries tool_call_id, so the route must
    either pair each tool_result with its tool_call_id<->name mapping
    before constructing the Message (preferred), or we fall back to
    passing the tool_call_id as the name (lossy but functional).
    """
    from backend.services.llm_adapter.types import ToolResultPart, ToolUsePart  # noqa: PLC0415

    if isinstance(p, TextPart):
        return {"text": p.text}
    elif isinstance(p, ImagePart):
        if p.base64:
            return {"inline_data": {"mime_type": p.mime_type, "data": p.base64}}
        else:
            # Gemini natively supports gs:// URIs; plain HTTPS URLs are passed
            # through — Gemini Flash will attempt to fetch them at inference time.
            return {"file_data": {"mime_type": p.mime_type, "file_uri": p.url}}
    elif isinstance(p, ToolUsePart):
        # Gemini function_call takes a name + args (dict).
        return {
            "function_call": {
                "name": p.name,
                "args": p.args,
            }
        }
    elif isinstance(p, ToolResultPart):
        # Gemini function_response needs a name; if ToolResultPart lacks one
        # explicitly, fall back to tool_call_id as a stable identifier.
        # Content must be a dict; wrap string results as {"result": <text>}.
        name = getattr(p, "name", None) or p.tool_call_id
        if isinstance(p.content, dict):
            response = p.content
        else:
            response = {"result": str(p.content)}
        return {
            "function_response": {
                "name": name,
                "response": response,
            }
        }
    return {"text": str(p)}


def _message_to_gemini(msg: Message) -> dict[str, Any]:
    # Gemini uses "user" and "model" (not "assistant"). Tool results
    # (role == "tool") route to "user" per Gemini's contract.
    role = "model" if msg.role == "assistant" else "user"
    parts = [_part_to_gemini(p) for p in msg.content]
    return {"role": role, "parts": parts}


def _unwrap_protobuf(value: Any) -> Any:
    """Recursively convert protobuf Struct/ListValue/Value into plain
    Python dict/list/scalar so json.dumps can serialize nested tool args.

    `FunctionCall.args` is a Struct whose __getitem__ returns nested
    Struct/ListValue for nested JSON — a plain dict() cast only gives
    one level. Without this unwrap, any tool call whose args contain
    nested objects or arrays hits JSONDecodeError silently (the adapter
    previously swallowed these in a blanket except).
    """
    # proto.marshal.collections.maps.MapComposite and ListValue expose
    # dict-like / list-like semantics but contain Struct values that
    # need recursion. Duck-type on attributes rather than import types
    # to avoid a hard dep on google.protobuf internals.
    if hasattr(value, "items") and callable(getattr(value, "items")):
        return {str(k): _unwrap_protobuf(v) for k, v in value.items()}
    if hasattr(value, "__iter__") and not isinstance(value, (str, bytes)):
        return [_unwrap_protobuf(v) for v in value]
    return value


class GeminiAdapter:
    """Adapter for Google's Gemini generative AI API (google.genai)."""

    def __init__(self, api_key: str | None = None):
        resolved_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self._client = genai.Client(api_key=resolved_key)
        self._provider = "gemini"

    def chat(self, request: LLMRequest) -> LLMResponse:
        contents = [_message_to_gemini(msg) for msg in request.messages]

        # Build GenerateContentConfig kwargs
        config_kwargs: dict[str, Any] = {}
        if request.system_prompt:
            config_kwargs["system_instruction"] = request.system_prompt
        if request.max_tokens is not None:
            config_kwargs["max_output_tokens"] = request.max_tokens
        if request.temperature is not None:
            config_kwargs["temperature"] = request.temperature
        if request.response_format is not None:
            # Gemini's response_mime_type enforces JSON output when set to
            # "application/json". json_schema adds response_schema.
            if request.response_format.type in ("json_object", "json_schema"):
                config_kwargs["response_mime_type"] = "application/json"
            if request.response_format.type == "json_schema" and request.response_format.schema:
                config_kwargs["response_schema"] = request.response_format.schema

        # Plumb timeout through HttpOptions (new SDK uses milliseconds).
        config_kwargs["http_options"] = genai_types.HttpOptions(
            timeout=int(request.timeout * 1000)
        )

        config = genai_types.GenerateContentConfig(**config_kwargs)

        emit(
            "llm.call.start",
            provider=self._provider,
            model=request.model,
            **{k: v for k, v in request.metadata.items() if isinstance(v, (str, int, float, bool))},
        )
        t0 = time.monotonic()

        try:
            breaker = get_breaker(self._provider, request.model)

            def _raw_call():
                return self._client.models.generate_content(
                    model=request.model,
                    contents=contents,
                    config=config,
                )

            def _breakered():
                return breaker.call(_raw_call)

            raw = with_retry(
                _breakered,
                label=f"gemini.generate_content({request.model})",
                non_retryable=(pybreaker.CircuitBreakerError,),
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
            except Exception as e:
                # SDK-defensive: candidate/parts shape varies across genai
                # versions. Missing parts → empty content_parts (caller
                # treats as no text response).
                _logger.debug("Failed to extract Gemini content parts: %s", e)

        # Usage metadata (may not be present on all Gemini responses)
        prompt_tokens = 0
        completion_tokens = 0
        try:
            if hasattr(raw, "usage_metadata") and raw.usage_metadata:
                prompt_tokens = getattr(raw.usage_metadata, "prompt_token_count", 0) or 0
                completion_tokens = getattr(raw.usage_metadata, "candidates_token_count", 0) or 0
        except Exception as e:
            # SDK-defensive: usage_metadata schema varies. Missing → 0/0
            # tokens (cost will be reported as $0 for this call; cumulative
            # cost tracking will be slightly under-counted).
            _logger.debug("Failed to extract Gemini usage_metadata: %s", e)

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
        except Exception as e:
            # SDK-defensive: candidate/finish_reason may be missing. Falls
            # through to normalize_finish_reason(None) which returns the
            # canonical default.
            _logger.debug("Failed to extract Gemini finish_reason: %s", e)
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

    def stream_chat(self, request: LLMRequest) -> Iterator[StreamEvent]:
        """Yield StreamEvent instances from a Gemini streaming response.

        Uses generate_content_stream(). The initial call is protected
        by with_retry(); iteration is not (can't retry mid-stream).

        Gemini yields full GenerateContentResponse chunks per step.
        Each chunk may have .text (TextDelta) or function_call parts in
        candidates[0].content.parts (ToolCallDelta / ToolCallComplete).
        Usage is only present on the final chunk.
        """
        contents = [_message_to_gemini(msg) for msg in request.messages]

        # Build GenerateContentConfig kwargs
        config_kwargs: dict[str, Any] = {}
        if request.system_prompt:
            config_kwargs["system_instruction"] = request.system_prompt
        if request.max_tokens is not None:
            config_kwargs["max_output_tokens"] = request.max_tokens
        if request.temperature is not None:
            config_kwargs["temperature"] = request.temperature
        if request.tools:
            declarations = []
            for t in request.tools:
                schema = t.input_schema
                props = schema.get("properties", {})
                cleaned_props = {
                    k: {kk: vv for kk, vv in v.items() if kk != "additionalProperties"}
                    for k, v in props.items()
                }
                declarations.append(genai_types.FunctionDeclaration(
                    name=t.name,
                    description=t.description,
                    parameters={
                        "type": "object",
                        "properties": cleaned_props,
                        "required": schema.get("required", []),
                    },
                ))
            config_kwargs["tools"] = [genai_types.Tool(function_declarations=declarations)]

        # Plumb timeout through HttpOptions (new SDK uses milliseconds).
        config_kwargs["http_options"] = genai_types.HttpOptions(
            timeout=int(request.timeout * 1000)
        )

        config = genai_types.GenerateContentConfig(**config_kwargs)

        emit(
            "llm.call.start",
            provider=self._provider,
            model=request.model,
            streaming=True,
            **{k: v for k, v in request.metadata.items() if isinstance(v, (str, int, float, bool))},
        )
        t0 = time.monotonic()

        try:
            stream_breaker = get_breaker(self._provider, request.model)

            def _raw_stream_call():
                return self._client.models.generate_content_stream(
                    model=request.model,
                    contents=contents,
                    config=config,
                )

            def _breakered_stream():
                return stream_breaker.call(_raw_stream_call)

            stream = with_retry(
                _breakered_stream,
                label=f"gemini.generate_content(stream, {request.model})",
                non_retryable=(pybreaker.CircuitBreakerError,),
            )
        except Exception as e:
            duration_ms = int((time.monotonic() - t0) * 1000)
            emit(
                "llm.call.error",
                level="warning",
                provider=self._provider,
                model=request.model,
                duration_ms=duration_ms,
                streaming=True,
                error_kind=type(e).__name__,
            )
            sentry_sdk.add_breadcrumb(
                category="llm.call",
                level="warning",
                message=f"gemini.generate_content(stream) failed for {request.model}",
                data={"provider": self._provider, "model": request.model, "error_kind": type(e).__name__, "duration_ms": duration_ms},
            )
            raise

        prompt_tokens = 0
        completion_tokens = 0
        finish_reason_raw: str | None = None

        try:
            try:
                for chunk in stream:
                    # Text delta — chunk.text raises if the response has function calls
                    try:
                        text = chunk.text
                        if text:
                            yield TextDelta(text=text)
                    except (ValueError, AttributeError):
                        pass

                    # Function call parts — treated as atomic ToolCallDelta + ToolCallComplete
                    # (Gemini doesn't stream incremental JSON fragments, it delivers the
                    # whole function_call at once in a part)
                    try:
                        for candidate in chunk.candidates:
                            for part in candidate.content.parts:
                                if hasattr(part, "function_call") and part.function_call:
                                    fc = part.function_call
                                    tool_id = f"gemini_{fc.name}_{uuid.uuid4().hex[:8]}"
                                    # Use _unwrap_protobuf so nested dicts/lists survive
                                    # JSON serialization. `dict(fc.args)` alone only
                                    # unwraps one level — nested Struct/ListValue values
                                    # would crash json.dumps.
                                    try:
                                        args = _unwrap_protobuf(fc.args) if fc.args else {}
                                        if not isinstance(args, dict):
                                            args = {}
                                    except Exception as unwrap_err:
                                        _logger.warning(
                                            "Failed to unwrap Gemini tool args for %s: %s — treating as empty",
                                            fc.name, unwrap_err,
                                        )
                                        sentry_sdk.add_breadcrumb(
                                            category="llm.tool_call",
                                            level="warning",
                                            message=f"gemini tool args unwrap failed for {fc.name}",
                                            data={"provider": "gemini", "tool_name": fc.name, "error_kind": type(unwrap_err).__name__},
                                        )
                                        args = {}
                                    # Single delta that is also complete (no incremental JSON)
                                    yield ToolCallDelta(
                                        tool_call_id=tool_id,
                                        name=fc.name,
                                        args_delta=_json.dumps(args),
                                    )
                                    yield ToolCallComplete(
                                        tool_call=ToolCall(
                                            tool_call_id=tool_id,
                                            name=fc.name,
                                            args=args,
                                        )
                                    )
                    except Exception as loop_err:
                        _logger.warning("Gemini tool-call scan failed mid-stream: %s", loop_err)

                    # Usage metadata — only on final chunk
                    try:
                        if hasattr(chunk, "usage_metadata") and chunk.usage_metadata:
                            prompt_tokens = getattr(chunk.usage_metadata, "prompt_token_count", 0) or 0
                            completion_tokens = getattr(chunk.usage_metadata, "candidates_token_count", 0) or 0
                    except Exception as e:
                        # SDK-defensive: streaming chunk usage_metadata schema
                        # varies. Missing → keep prior token counts.
                        _logger.debug("Failed to extract Gemini stream usage_metadata: %s", e)

                    # Finish reason — from candidate (may only be set on last chunk)
                    try:
                        candidate = chunk.candidates[0]
                        fr = candidate.finish_reason
                        raw = fr.name if hasattr(fr, "name") else str(fr)
                        if raw and raw not in ("", "FINISH_REASON_UNSPECIFIED", "0"):
                            finish_reason_raw = raw
                    except Exception as e:
                        # SDK-defensive: streaming chunk candidates may be
                        # absent until the last chunk. Falls through to
                        # whatever finish_reason_raw was set elsewhere.
                        _logger.debug("Failed to extract Gemini stream finish_reason: %s", e)

            except Exception as e:
                duration_ms = int((time.monotonic() - t0) * 1000)
                emit(
                    "llm.call.error",
                    level="warning",
                    provider=self._provider,
                    model=request.model,
                    duration_ms=duration_ms,
                    streaming=True,
                    error_kind=type(e).__name__,
                )
                sentry_sdk.add_breadcrumb(
                    category="llm.call",
                    level="warning",
                    message=f"gemini stream iteration failed for {request.model}",
                    data={"provider": self._provider, "model": request.model, "error_kind": type(e).__name__, "duration_ms": duration_ms},
                )
                raise
        finally:
            # Phase 5b PR 4 — best-effort upstream cancel on exit.
            # Tries .cancel() first (preferred semantic); falls back to .close()
            # if only that exists. If neither is exposed by the SDK version,
            # we rely on generator garbage collection.
            for method_name in ("cancel", "close"):
                method = getattr(stream, method_name, None)
                if callable(method):
                    try:
                        method()
                    except Exception:
                        _logger.debug("gemini stream %s() raised on cleanup", method_name, exc_info=True)
                    break

        usage = Usage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=_estimate_cost_usd(request.model, prompt_tokens, completion_tokens),
        )
        yield UsageEvent(usage=usage)

        # Normalize Gemini integer enum values before the shared map
        if finish_reason_raw == "1":
            finish_reason_raw = "stop"
        elif finish_reason_raw == "2":
            finish_reason_raw = "max_tokens_reached"
        finish_reason = normalize_finish_reason(finish_reason_raw)
        yield FinishEvent(finish_reason=finish_reason)

        duration_ms = int((time.monotonic() - t0) * 1000)
        emit(
            "llm.call.complete",
            provider=self._provider,
            model=request.model,
            duration_ms=duration_ms,
            streaming=True,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=usage.cost_usd,
            finish_reason=finish_reason,
        )

    def generate_image(self, request: ImageRequest) -> ImageResponse:
        """Generate image(s) from a text prompt via Gemini's image-gen model.

        Gemini uses the SAME client.models.generate_content entrypoint as chat,
        differentiated by response_modalities=["IMAGE"] on the config. Retry
        defaults to OFF because each image call is ~$0.04 and a 5xx after
        provider billing would double-charge on retry.
        """
        contents: list[Any] = []
        if request.reference_images:
            for ref in request.reference_images:
                contents.append(_part_to_gemini(ref))
        contents.append(request.prompt)

        config_kwargs: dict[str, Any] = {
            "response_modalities": ["IMAGE"],
        }
        if request.aspect_ratio:
            config_kwargs["image_config"] = genai_types.ImageConfig(aspect_ratio=request.aspect_ratio)
        if request.timeout:
            config_kwargs["http_options"] = genai_types.HttpOptions(timeout=int(request.timeout * 1000))
        config = genai_types.GenerateContentConfig(**config_kwargs)

        emit(
            "llm.image.call.start",
            provider=self._provider,
            model=request.model,
            **{k: v for k, v in request.metadata.items() if isinstance(v, (str, int, float, bool))},
        )
        t0 = time.monotonic()

        breaker = get_breaker(self._provider, request.model)

        def _raw_call():
            return self._client.models.generate_content(
                model=request.model,
                contents=contents,
                config=config,
            )

        def _breakered():
            return breaker.call(_raw_call)

        try:
            if request.retry:
                raw = with_retry(
                    _breakered,
                    label=f"gemini.generate_image({request.model})",
                    non_retryable=(pybreaker.CircuitBreakerError,),
                )
            else:
                raw = _breakered()
        except Exception as e:
            duration_ms = int((time.monotonic() - t0) * 1000)
            if not isinstance(e, pybreaker.CircuitBreakerError):
                emit(
                    "llm.image.call.error",
                    level="warning",
                    provider=self._provider,
                    model=request.model,
                    duration_ms=duration_ms,
                    error_kind=type(e).__name__,
                )
                sentry_sdk.add_breadcrumb(
                    category="llm.image.call",
                    level="warning",
                    message=f"gemini.generate_image failed for {request.model}",
                    data={
                        "provider": self._provider,
                        "model": request.model,
                        "error_kind": type(e).__name__,
                        "duration_ms": duration_ms,
                    },
                )
            raise

        duration_ms = int((time.monotonic() - t0) * 1000)

        images: list[bytes] = []
        mime_type = "image/png"
        candidate = None
        if raw.candidates:
            candidate = raw.candidates[0]
        if candidate is not None and getattr(candidate, "content", None) is not None:
            parts = getattr(candidate.content, "parts", None) or []
            for part in parts:
                if hasattr(part, "inline_data") and part.inline_data is not None:
                    images.append(part.inline_data.data)
                    mime_type = getattr(part.inline_data, "mime_type", None) or mime_type

        finish_reason_raw = None
        if candidate is not None:
            try:
                fr = candidate.finish_reason
                finish_reason_raw = fr.name if hasattr(fr, "name") else str(fr)
            except Exception as e:
                # SDK-defensive: image-gen finish_reason may be absent.
                # Falls through to prompt_feedback.block_reason check below.
                _logger.debug("Failed to extract Gemini image finish_reason: %s", e)
        if finish_reason_raw is None:
            try:
                pf = getattr(raw, "prompt_feedback", None)
                if pf is not None:
                    br = getattr(pf, "block_reason", None)
                    if br is not None:
                        finish_reason_raw = br.name if hasattr(br, "name") else str(br)
            except Exception as e:
                # SDK-defensive: prompt_feedback shape varies. Falls through
                # to "unknown" finish_reason in the blocked-call emit below.
                _logger.debug("Failed to extract Gemini image block_reason: %s", e)

        if not images:
            emit(
                "llm.image.call.blocked",
                level="warning",
                provider=self._provider,
                model=request.model,
                duration_ms=duration_ms,
                finish_reason=finish_reason_raw or "unknown",
            )

        cost_usd = _estimate_image_cost_usd(request.model, len(images))

        emit(
            "llm.image.call.complete",
            provider=self._provider,
            model=request.model,
            duration_ms=duration_ms,
            image_count=len(images),
            cost_usd=cost_usd,
            finish_reason=finish_reason_raw,
        )

        return ImageResponse(
            images=images,
            mime_type=mime_type,
            provider=self._provider,
            model=request.model,
            cost_usd=cost_usd,
        )
