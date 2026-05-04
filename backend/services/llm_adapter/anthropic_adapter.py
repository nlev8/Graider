"""Anthropic adapter for the Phase 5a LLM adapter layer.

Maps LLMRequest/Response to/from anthropic.messages.create.

Key differences from OpenAI:
- system_prompt maps to top-level system= param (NOT a message role)
- message content is always a list of typed blocks, never a plain string
- image input uses {"type": "image", "source": {"type": "base64"|"url", ...}}
- tool_use blocks in response content are extracted into tool_calls
- stop_reason "tool_use" maps to finish_reason "tool_use"
"""
from __future__ import annotations

import json as _json
import logging
import os
import time
from typing import Any, Iterator

import anthropic
import pybreaker
import sentry_sdk

from backend.observability.events import emit
from backend.retry import with_retry
from backend.services.llm_adapter.breakers import get_breaker
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
    LLMToolArgsOverflow,
    Message,
    TextPart,
    ToolCall,
    ToolResultPart,
    ToolUsePart,
    Usage,
    normalize_finish_reason,
)

_logger = logging.getLogger(__name__)

# Phase 5b PR 5 — memory cap for streaming tool-call argument accumulation.
# See openai_adapter.py::_MAX_TOOL_ARGS_BYTES for rationale.
_MAX_TOOL_ARGS_BYTES = 5 * 1024 * 1024


def _estimate_cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Rough per-1K-token pricing for Anthropic models (verify against
    https://www.anthropic.com/pricing when adding a new model)."""
    rates = {
        "claude-opus-4-20250514": (0.015, 0.075),
        "claude-sonnet-4-20250514": (0.003, 0.015),
        # Haiku 4.5 is $1 / $5 per million tokens (not $0.25 / $1.25).
        "claude-haiku-4-5-20251001": (0.001, 0.005),
    }
    in_rate, out_rate = rates.get(model, (0.003, 0.015))
    return round(prompt_tokens * in_rate / 1000 + completion_tokens * out_rate / 1000, 6)


def _content_to_anthropic(content: list) -> list[dict[str, Any]]:
    """Map our ContentPart list to Anthropic's message content block list."""
    blocks: list[dict[str, Any]] = []
    for p in content:
        if isinstance(p, TextPart):
            blocks.append({"type": "text", "text": p.text})
        elif isinstance(p, ImagePart):
            if p.base64:
                blocks.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": p.mime_type,
                        "data": p.base64,
                    },
                })
            else:
                blocks.append({
                    "type": "image",
                    "source": {
                        "type": "url",
                        "url": p.url,
                    },
                })
        elif isinstance(p, ToolUsePart):
            blocks.append({
                "type": "tool_use",
                "id": p.tool_call_id,
                "name": p.name,
                "input": p.args,
            })
        # ToolResultPart should be in a "tool" role message, handled at message level
    return blocks


def _message_to_anthropic(msg: Message) -> dict[str, Any]:
    # Anthropic uses "user" and "assistant" — "tool" role is not used;
    # tool results are "user" messages with tool_result blocks.
    if msg.role == "tool":
        # Convert ToolResultPart content into a tool_result block
        blocks: list[dict[str, Any]] = []
        for p in msg.content:
            if isinstance(p, ToolResultPart):
                result_content = p.content if isinstance(p.content, str) else str(p.content)
                blocks.append({
                    "type": "tool_result",
                    "tool_use_id": p.tool_call_id,
                    "content": result_content,
                })
        return {"role": "user", "content": blocks}

    role = "user" if msg.role == "user" else "assistant"
    return {"role": role, "content": _content_to_anthropic(msg.content)}


class AnthropicAdapter:
    """Adapter for Anthropic's Messages API."""

    def __init__(self, api_key: str | None = None):
        self._client = anthropic.Anthropic(api_key=api_key or os.getenv("ANTHROPIC_API_KEY"))
        self._provider = "anthropic"

    def chat(self, request: LLMRequest) -> LLMResponse:
        messages = [_message_to_anthropic(msg) for msg in request.messages]

        kwargs: dict[str, Any] = {
            "model": request.model,
            "messages": messages,
            "max_tokens": request.max_tokens or 1024,
            "timeout": request.timeout,
        }
        if request.system_prompt:
            kwargs["system"] = request.system_prompt
        if request.temperature is not None:
            kwargs["temperature"] = request.temperature
        if request.tools:
            kwargs["tools"] = [
                {
                    "name": t.name,
                    "description": t.description,
                    "input_schema": t.input_schema,
                }
                for t in request.tools
            ]
        if request.response_format is not None:
            # Anthropic doesn't have a native response_format param, but a JSON
            # tool schema can enforce structured output. When response_format is
            # json_schema and no tools are already defined, prepend a JSON-extract
            # tool and instruct the model to call it. For plain "json_object" we
            # leave it to the caller's system prompt (Anthropic recommends this).
            if request.response_format.type == "json_schema" and request.response_format.schema and not request.tools:
                kwargs["tools"] = [{
                    "name": "emit_json",
                    "description": "Return the requested JSON object.",
                    "input_schema": request.response_format.schema,
                }]
                kwargs["tool_choice"] = {"type": "tool", "name": "emit_json"}

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
                return self._client.messages.create(**kwargs)

            def _breakered():
                return breaker.call(_raw_call)

            raw = with_retry(
                _breakered,
                label=f"anthropic.messages.create({request.model})",
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
                message=f"anthropic.messages.create failed for {request.model}",
                data={"provider": self._provider, "model": request.model, "error_kind": type(e).__name__, "duration_ms": duration_ms},
            )
            raise

        duration_ms = int((time.monotonic() - t0) * 1000)

        # Map response blocks into content_parts and tool_calls
        content_parts = []
        tool_calls: list[ToolCall] = []
        for block in raw.content:
            if block.type == "text":
                content_parts.append(TextPart(text=block.text))
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(
                    tool_call_id=block.id,
                    name=block.name,
                    args=block.input if isinstance(block.input, dict) else {},
                ))
                # Also surface as ToolUsePart in content_parts for callers
                # that inspect content_parts (e.g. multi-turn reconstruction)
                content_parts.append(ToolUsePart(
                    tool_call_id=block.id,
                    name=block.name,
                    args=block.input if isinstance(block.input, dict) else {},
                ))

        prompt_tokens = raw.usage.input_tokens if raw.usage else 0
        completion_tokens = raw.usage.output_tokens if raw.usage else 0
        usage = Usage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=_estimate_cost_usd(request.model, prompt_tokens, completion_tokens),
        )

        finish_reason = normalize_finish_reason(raw.stop_reason)

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

        return LLMResponse(
            content_parts=content_parts,
            tool_calls=tool_calls,
            usage=usage,
            finish_reason=finish_reason,
            provider=self._provider,
            model=raw.model,
        )

    def stream_chat(self, request: LLMRequest) -> Iterator[StreamEvent]:
        """Yield StreamEvent instances from an Anthropic streaming response.

        Uses client.messages.stream() context manager. The initial open
        call is protected by with_retry(); iteration is not.

        Event mapping:
        - content_block_start (tool_use) → records block metadata
        - content_block_delta (text_delta) → TextDelta
        - content_block_delta (input_json_delta) → ToolCallDelta
        - content_block_stop (tool_use block) → ToolCallComplete
        - message_start → captures input_tokens
        - message_delta → UsageEvent (output_tokens), FinishEvent
        - message_stop → no additional event (FinishEvent already emitted)
        """
        messages = [_message_to_anthropic(msg) for msg in request.messages]

        kwargs: dict[str, Any] = {
            "model": request.model,
            "messages": messages,
            "max_tokens": request.max_tokens or 1024,
            "timeout": request.timeout,
        }
        if request.system_prompt:
            kwargs["system"] = request.system_prompt
        if request.temperature is not None:
            kwargs["temperature"] = request.temperature
        if request.tools:
            kwargs["tools"] = [
                {
                    "name": t.name,
                    "description": t.description,
                    "input_schema": t.input_schema,
                }
                for t in request.tools
            ]

        emit(
            "llm.call.start",
            provider=self._provider,
            model=request.model,
            streaming=True,
            **{k: v for k, v in request.metadata.items() if isinstance(v, (str, int, float, bool))},
        )
        t0 = time.monotonic()

        # NOTE on retry semantics: `self._client.messages.stream(**kwargs)`
        # returns a MessageStreamManager WITHOUT performing any HTTP — the
        # actual request is dispatched inside `__enter__()`. So wrapping
        # `.stream(...)` alone in with_retry is a no-op for transient
        # network failures. To retry stream-open for real, we enter the
        # context manager INSIDE the retry lambda. If an HTTP-level error
        # fires during __enter__, with_retry catches + retries. Once
        # iteration begins (yield loop below), we don't retry — that would
        # replay tool-call state inconsistently.
        ctx_holder: list[Any] = [None]
        stream_breaker = get_breaker(self._provider, request.model)

        def _open_stream():
            ctx = self._client.messages.stream(**kwargs)
            stream = ctx.__enter__()
            ctx_holder[0] = ctx
            return stream

        def _breakered_open_stream():
            return stream_breaker.call(_open_stream)

        try:
            stream = with_retry(
                _breakered_open_stream,
                label=f"anthropic.messages.stream({request.model})",
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
                message=f"anthropic.messages.stream failed for {request.model}",
                data={"provider": self._provider, "model": request.model, "error_kind": type(e).__name__, "duration_ms": duration_ms},
            )
            raise

        # block_meta: index -> {type, id, name, accumulated_json}
        block_meta: dict[int, dict[str, str]] = {}
        input_tokens = 0
        output_tokens = 0
        finish_reason_raw: str | None = None

        try:
            for event in stream:
                etype = event.type

                if etype == "message_start":
                    try:
                        input_tokens = event.message.usage.input_tokens or 0
                    except Exception as e:
                        # SDK-defensive: usage shape varies across anthropic
                        # versions. Missing → 0 input tokens (cost slightly
                        # under-counted; no impact on grading correctness).
                        _logger.debug("Failed to extract Anthropic message_start input_tokens: %s", e)

                elif etype == "content_block_start":
                    cb = event.content_block
                    block_meta[event.index] = {
                        "type": cb.type,
                        "id": getattr(cb, "id", ""),
                        "name": getattr(cb, "name", ""),
                        "accumulated_json": "",
                    }

                elif etype == "content_block_delta":
                    delta = event.delta
                    delta_type = getattr(delta, "type", "")

                    if delta_type == "text_delta":
                        text = getattr(delta, "text", "")
                        if text:
                            yield TextDelta(text=text)

                    elif delta_type == "input_json_delta":
                        fragment = getattr(delta, "partial_json", "")
                        meta = block_meta.get(event.index, {})
                        is_first = not meta.get("accumulated_json")
                        projected = len(meta.get("accumulated_json", "")) + len(fragment)
                        if projected > _MAX_TOOL_ARGS_BYTES:
                            emit(
                                "llm.tool_call.args_overflow",
                                provider=self._provider,
                                model=request.model,
                                tool_name=meta.get("name") or "unknown",
                                bytes_accumulated=len(meta.get("accumulated_json", "")),
                            )
                            raise LLMToolArgsOverflow(
                                f"tool_call args exceeded {_MAX_TOOL_ARGS_BYTES} bytes "
                                f"for tool {meta.get('name')!r} on {self._provider}"
                            )
                        meta["accumulated_json"] = meta.get("accumulated_json", "") + fragment
                        yield ToolCallDelta(
                            tool_call_id=meta.get("id", ""),
                            name=meta.get("name") if is_first else None,
                            args_delta=fragment,
                        )

                elif etype == "content_block_stop":
                    meta = block_meta.get(event.index, {})
                    if meta.get("type") == "tool_use":
                        raw_json = meta.get("accumulated_json", "")
                        try:
                            args = _json.loads(raw_json) if raw_json else {}
                        except _json.JSONDecodeError:
                            _logger.warning(
                                "Dropping malformed Anthropic tool args for %s (block=%s): %r",
                                meta.get("name"), event.index, raw_json,
                            )
                            sentry_sdk.add_breadcrumb(
                                category="llm.tool_call",
                                level="warning",
                                message=f"anthropic tool args JSONDecodeError for {meta.get('name')}",
                                data={"provider": "anthropic", "tool_name": meta.get("name"), "args_len": len(raw_json or "")},
                            )
                            args = {}
                        yield ToolCallComplete(
                            tool_call=ToolCall(
                                tool_call_id=meta.get("id", ""),
                                name=meta.get("name", ""),
                                args=args,
                            )
                        )

                elif etype == "message_delta":
                    try:
                        output_tokens = event.usage.output_tokens or 0
                    except Exception as e:
                        # SDK-defensive: message_delta usage shape varies.
                        # Missing → keep prior output_tokens.
                        _logger.debug("Failed to extract Anthropic message_delta output_tokens: %s", e)
                    try:
                        finish_reason_raw = event.delta.stop_reason
                    except Exception as e:
                        # SDK-defensive: stop_reason may not be set on every
                        # delta. Keeps the prior finish_reason_raw; if never
                        # set, normalize_finish_reason(None) returns "stop".
                        _logger.debug("Failed to extract Anthropic message_delta stop_reason: %s", e)

                # message_stop — FinishEvent emitted after loop

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
                message=f"anthropic stream iteration failed for {request.model}",
                data={"provider": self._provider, "model": request.model, "error_kind": type(e).__name__, "duration_ms": duration_ms},
            )
            if ctx_holder[0] is not None:
                try:
                    ctx_holder[0].__exit__(type(e), e, e.__traceback__)
                except Exception as exit_err:
                    # Cleanup-time failures must not mask the original `e`
                    # (we re-raise it below). Swallow but log so the cleanup
                    # path is observable. Don't sentry-capture: the original
                    # exception is the one ops needs to see.
                    _logger.debug("Anthropic stream context cleanup raised on error path: %s", exit_err)
            raise
        else:
            # Clean finish — release the context manager.
            if ctx_holder[0] is not None:
                try:
                    ctx_holder[0].__exit__(None, None, None)
                except Exception as exit_err:
                    # Cleanup-time failures on the success path: the response
                    # was already streamed successfully, so don't propagate
                    # the cleanup error to the caller. Unlike the error path
                    # below, there is no primary exception to preserve, so a
                    # silent swallow at debug-only would be invisible in
                    # production (default INFO+). Escalate to warning + emit
                    # a structured observability event so resource-leak
                    # symptoms have a paper trail (per Codex review).
                    _logger.warning("Anthropic stream context cleanup raised on success path: %s", exit_err)
                    emit(
                        "llm.stream.cleanup_failure",
                        level="warning",
                        provider=self._provider,
                        model=request.model,
                        path="success",
                        error_kind=type(exit_err).__name__,
                    )

        usage = Usage(
            prompt_tokens=input_tokens,
            completion_tokens=output_tokens,
            cost_usd=_estimate_cost_usd(request.model, input_tokens, output_tokens),
        )
        yield UsageEvent(usage=usage)

        finish_reason = normalize_finish_reason(finish_reason_raw)
        yield FinishEvent(finish_reason=finish_reason)

        duration_ms = int((time.monotonic() - t0) * 1000)
        emit(
            "llm.call.complete",
            provider=self._provider,
            model=request.model,
            duration_ms=duration_ms,
            streaming=True,
            prompt_tokens=input_tokens,
            completion_tokens=output_tokens,
            cost_usd=usage.cost_usd,
            finish_reason=finish_reason,
        )

    def generate_image(self, request: ImageRequest) -> ImageResponse:
        """Not supported — Anthropic does not provide an image-generation API."""
        raise NotImplementedError(
            "image generation is not supported by the anthropic adapter "
            "(anthropic does not provide an image-generation api)"
        )
