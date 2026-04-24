# Phase 5c — Image Adapter Design

**Date:** 2026-04-24
**Status:** Specified, awaiting user review then implementation plan
**Review history:** Brainstorm (one session) → this document
**Follows:** Phase 5b (LLM adapter hardening, 6 PRs shipped 2026-04-24)

---

## Goal

Extend the `LLMAdapter` protocol with a `generate_image()` method. Migrate `slide_generator.py`'s direct `google.genai` image-gen call to flow through the adapter seam. This brings image generation under the same breaker, observability, and retry-disabled cost semantics that Phase 5b established for chat.

**Dimensions targeted:** Operational safety (breaker protection for image gen), Code quality (single seam for all provider I/O).

**Non-goal:** OpenAI DALL-E or any other provider. Anthropic does not do image generation. Only `slide_generator.py` consumes image gen today; no evidence more providers are needed.

---

## Scope — what's IN and OUT

**In Phase 5c (2 PRs):**

| PR | Item |
|---|---|
| 1 | `ImageRequest` + `ImageResponse` types; `generate_image()` on `LLMAdapter` Protocol; Gemini implementation; OpenAI + Anthropic stubs raising `NotImplementedError`; unit tests |
| 2 | Migrate `slide_generator.py::generate_slide_images` to call `GeminiAdapter.generate_image(ImageRequest(...))`; end-to-end tests verifying same observable behavior |

**Explicitly deferred:**
- OpenAI DALL-E implementation — no current consumer
- OpenAI TTS adapter — genuinely different shape (WebSocket streaming audio); revisit after image ships
- APM tracing, Redis-backed shared breaker state, VCR cassette tests, React frontend error tracking — separate future phases

---

## Current-state inventory (verified 2026-04-24)

- `backend/services/slide_generator.py:188` exposes `_get_genai_client(api_key)` which calls `from google import genai; genai.Client(api_key=...)`.
- `backend/services/slide_generator.py:220-290` is the image-gen loop. It iterates over slides with `image_prompt`, calls `client.models.generate_content(model="gemini-2.5-flash-preview-image-generation", contents=..., config=types.GenerateContentConfig(response_modalities=["IMAGE"], image_config=types.ImageConfig(aspect_ratio="16:9")))`, and extracts bytes from `response.candidates[0].content.parts[].inline_data.data`.
- Reference-image style consistency: the first successfully generated image becomes a `PIL.Image.Image` held in memory. Subsequent calls prepend that PIL object to `contents` before the prompt text.
- Retry policy: each image call is individually try/excepted. **No `with_retry` wrapping** — intentional cost decision. If a call fails, that slide renders text-only.
- No breaker protection today. A Gemini outage takes out every image call without fail-fast.
- Observability: `logger.info` lines only. No `emit()` events, no Sentry breadcrumbs.
- Only consumer of image gen: `generate_slide_images()` in `slide_generator.py`, called by `_run_slide_generator()` in `backend/routes/planner_routes.py` (slide deck export).
- `GeminiAdapter` (post-Phase-5b PR 2): uses `self._client = genai.Client(api_key=...)` in `__init__`, same client that image-gen uses. Retry + breaker wired on `chat()` and `stream_chat()`.
- `@runtime_checkable Protocol LLMAdapter` at `backend/services/llm_adapter/__init__.py:34-51` currently has `chat()` + `stream_chat()`. PR 1 extends it.

---

## PR 1 — Protocol extension + Gemini implementation

**Branch:** `phase5c/pr1-image-adapter` off `main`.

### New types in `backend/services/llm_adapter/types.py`

```python
@dataclass(frozen=True)
class ImageRequest:
    prompt: str
    model: str                                         # e.g. "gemini-2.5-flash-preview-image-generation"
    reference_images: list[ImagePart] | None = None    # style consistency (Gemini prepends these to contents)
    aspect_ratio: str | None = None                    # e.g. "16:9", "1:1", "9:16" — provider may ignore
    timeout: float = DEFAULT_TIMEOUT
    metadata: dict[str, Any] = field(default_factory=dict)
    retry: bool = False                                # default OFF — image gen is cost-sensitive (~$0.04/call); double-charge risk on 5xx after provider bills
```

```python
@dataclass(frozen=True)
class ImageResponse:
    images: list[bytes]        # one per image generated; Gemini returns exactly one, future providers may return multiple
    mime_type: str             # "image/png" typical
    provider: str              # "openai" | "anthropic" | "gemini"
    model: str
    cost_usd: float            # per-image flat rate, NOT token-based — separate from Usage
```

### `LLMAdapter` Protocol update at `backend/services/llm_adapter/__init__.py`

```python
@runtime_checkable
class LLMAdapter(Protocol):
    def chat(self, request: LLMRequest) -> LLMResponse: ...
    def stream_chat(self, request: LLMRequest) -> Iterator[StreamEvent]: ...
    def generate_image(self, request: ImageRequest) -> ImageResponse: ...
```

All three adapter classes must implement `generate_image()` to satisfy the protocol.

### Gemini implementation (`backend/services/llm_adapter/gemini_adapter.py`)

```python
def generate_image(self, request: ImageRequest) -> ImageResponse:
    contents: list[Any] = []
    if request.reference_images:
        for ref in request.reference_images:
            # Reuse existing _part_to_gemini; reference images are ImagePart
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

    emit("llm.image.call.start", provider=self._provider, model=request.model,
         **{k: v for k, v in request.metadata.items() if isinstance(v, (str, int, float, bool))})
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
            raw = _breakered()  # breaker-only, no retry
    except Exception as e:
        duration_ms = int((time.monotonic() - t0) * 1000)
        emit("llm.image.call.error", level="warning", provider=self._provider, model=request.model,
             duration_ms=duration_ms, error_kind=type(e).__name__)
        sentry_sdk.add_breadcrumb(category="llm.image.call", level="warning",
            message=f"gemini.generate_image failed for {request.model}",
            data={"provider": self._provider, "model": request.model,
                  "error_kind": type(e).__name__, "duration_ms": duration_ms})
        raise

    duration_ms = int((time.monotonic() - t0) * 1000)

    # Extract bytes from response
    images: list[bytes] = []
    mime_type = "image/png"
    for part in raw.candidates[0].content.parts:
        if hasattr(part, "inline_data") and part.inline_data is not None:
            images.append(part.inline_data.data)
            mime_type = getattr(part.inline_data, "mime_type", None) or mime_type

    cost_usd = _estimate_image_cost_usd(request.model, len(images))

    emit("llm.image.call.complete", provider=self._provider, model=request.model,
         duration_ms=duration_ms, image_count=len(images), cost_usd=cost_usd)

    return ImageResponse(
        images=images,
        mime_type=mime_type,
        provider=self._provider,
        model=request.model,
        cost_usd=cost_usd,
    )
```

New helper in `gemini_adapter.py`:

```python
def _estimate_image_cost_usd(model: str, image_count: int) -> float:
    """Per-image flat-rate pricing. Verify against
    https://ai.google.dev/gemini-api/docs/pricing when adding a new model."""
    rates = {
        "gemini-2.5-flash-preview-image-generation": 0.04,  # $0.04 per image as of 2026-04
    }
    return round(rates.get(model, 0.04) * image_count, 6)
```

### OpenAI + Anthropic stubs

```python
# openai_adapter.py
def generate_image(self, request: ImageRequest) -> ImageResponse:
    raise NotImplementedError("image generation not supported by openai adapter yet")

# anthropic_adapter.py
def generate_image(self, request: ImageRequest) -> ImageResponse:
    raise NotImplementedError("image generation not supported by anthropic (no image gen API)")
```

### Tests (new `tests/test_llm_adapter_image.py`)

- `test_gemini_generate_image_happy_path` — mock `client.models.generate_content` returning response with `inline_data.data`; verify `ImageResponse.images == [bytes]`, `provider == "gemini"`, `cost_usd > 0`.
- `test_gemini_generate_image_with_reference_image` — pass `reference_images=[ImagePart(base64=...)]`; verify contents list includes the reference before prompt.
- `test_gemini_generate_image_aspect_ratio` — pass `aspect_ratio="16:9"`; assert `config.image_config.aspect_ratio == "16:9"`.
- `test_gemini_generate_image_circuit_breaker_propagates` — pre-open breaker; assert `CircuitBreakerError` raised.
- `test_gemini_generate_image_retry_disabled_by_default` — inject `ConnectionError`; assert call made exactly once (no retry).
- `test_gemini_generate_image_retry_enabled_on_request_flag` — inject `ConnectionError` then success; with `retry=True`, assert second attempt succeeds.
- `test_gemini_generate_image_emits_observability_events` — monkeypatch `emit`; assert `llm.image.call.start` + `llm.image.call.complete` fire.
- `test_gemini_generate_image_emits_error_on_failure` — inject exception; assert `llm.image.call.error` + sentry breadcrumb.
- `test_openai_adapter_generate_image_raises_not_implemented` — instantiate OpenAIAdapter, call `generate_image`, assert `NotImplementedError`.
- `test_anthropic_adapter_generate_image_raises_not_implemented` — same for AnthropicAdapter.
- `test_llm_adapter_protocol_includes_generate_image` — runtime isinstance check against `LLMAdapter` protocol.

### Acceptance

- All new tests pass.
- Existing `test_llm_adapter_*.py` tests continue passing (no regression in chat/stream paths).
- `grep -rn "client.models.generate_content.*response_modalities" backend/` returns ONE hit (the new Gemini adapter method) — proves no stray direct-call paths.

---

## PR 2 — slide_generator migration

**Branch:** `phase5c/pr2-slide-generator-migration` off `main` (after PR 1 merges).

### Change in `backend/services/slide_generator.py`

Replace the image-gen loop body (currently at ~lines 242-290) with adapter calls. Replace the direct `client.models.generate_content` call with:

```python
from backend.services.llm_adapter.gemini_adapter import GeminiAdapter
from backend.services.llm_adapter.types import ImageRequest, ImagePart
from PIL import Image
from io import BytesIO

adapter = GeminiAdapter(api_key=api_key)
# ... existing loop over image_slides ...
for idx, (slide_index, image_prompt) in enumerate(image_slides):
    try:
        full_prompt = style_prompt + ". " + image_prompt
        reference_images = None
        if reference_image_bytes is not None:
            # Convert PIL-kept reference to ImagePart
            import base64
            b64 = base64.b64encode(reference_image_bytes).decode("ascii")
            reference_images = [ImagePart(
                url=None, base64=b64, mime_type="image/png"
            )]
            style_note = "Generate an illustration in the EXACT same visual style as the reference image above. "
            full_prompt = style_note + full_prompt

        response = adapter.generate_image(ImageRequest(
            prompt=full_prompt,
            model="gemini-2.5-flash-preview-image-generation",
            reference_images=reference_images,
            aspect_ratio="16:9",
            metadata={"feature_label": "slide_generator_image"},
        ))

        if response.images:
            image_data = response.images[0]
            images[slide_index] = image_data
            if reference_image_bytes is None:
                reference_image_bytes = image_data  # first image becomes style reference (bytes, not PIL)
    except Exception as e:
        logger.warning("Image generation failed for slide %d: %s", slide_index, e)
        continue
```

**Behavioral change from current code:** reference image is now stored as `bytes` not `PIL.Image`. The adapter's `ImagePart` takes `base64`-encoded bytes, and Gemini's underlying SDK accepts that form. Eliminates one dependency on PIL in the image-gen hot path (PIL is still used elsewhere in slide_generator for PPTX assembly).

**Retained behavior:**
- Per-image try/except (one failure doesn't stop the whole deck)
- No retry by default (via `ImageRequest.retry=False`)
- Same `image_slides[:max_images]` cap
- Same logger.info on style-reference set

**Removed:**
- `_get_genai_client` helper — adapter's `__init__` owns client creation now.
- Direct `from google.genai import types` import at function top.
- Direct `from google import genai` import.

### Consumer side: `backend/routes/planner_routes.py`

No change required — `_run_slide_generator()` calls `generate_slide_images(slides, theme, api_key, max_images)` which still has the same signature.

### Tests

- Update `tests/test_slide_generator.py` mocks that currently patch `backend.services.slide_generator._get_genai_client`. After migration, mocks target `backend.services.llm_adapter.gemini_adapter.genai.Client` (adapter's client) OR `GeminiAdapter.generate_image` directly.
- Add `test_slide_generator_invokes_adapter_for_each_image` — mock `GeminiAdapter.generate_image`; verify called once per `image_prompt` slide, up to `max_images`.
- Add `test_slide_generator_reference_image_passed_to_subsequent_calls` — mock adapter returns bytes; verify second adapter call receives `reference_images=[ImagePart(base64=...)]`.
- Keep existing `test_slide_generator` happy-path tests passing.

### Acceptance

- `tests/test_slide_generator.py` all green.
- Running `generate_slide_images` in dev generates real images (manual smoke — not in CI since it requires live Gemini key).
- `grep -rn "generate_content.*response_modalities" backend/services/slide_generator.py` returns ZERO hits (proves migration is complete).

---

## Sequencing

**Merge order:** PR 1 → PR 2.

PR 2 depends on PR 1's `GeminiAdapter.generate_image` method existing on main. After PR 1 merges, PR 2 branches off the updated `main`.

No other phase dependencies.

---

## Testing strategy

- All PRs maintain CI green on 7 jobs: Backend Tests, Frontend Build, Migrations Smoke, Lockfile Drift Check, Ruff Lint, Bandit SAST, Secret Scan.
- Coverage floor stays at 32% (CI-enforced). New code ≥80% line coverage by own unit tests.
- No SIS contract touched. 199 Clever/ClassLink/OneRoster tests continue passing unchanged.

**No live-API integration test in CI.** Live Gemini image gen costs money and needs a live key; mock-based tests are sufficient for adapter contract verification. A future phase can add recorded-cassette integration if drift concerns emerge.

---

## Rollout + risks

**Rollout:** Each PR merged independently; Railway auto-deploys on merge. Operator spot-checks `/healthz` + slide deck export flow after PR 2 merges.

**Per-PR risks:**

| PR | Risk | Mitigation |
|---|---|---|
| 1 | Breaker trip during image gen blocks all subsequent image requests for 60s | Same `(gemini, model)` key as chat — operators see unified breaker state in `llm.breaker.state_change` events. Accept as correct fail-fast behavior. |
| 1 | `NotImplementedError` on OpenAI/Anthropic is accidentally thrown by a caller that expects silent fallback | PR 1 tests + grep verification that only `slide_generator.py` calls `generate_image` today. |
| 2 | Reference-image bytes→base64 round-trip corrupts PNG data | Unit test with a real PNG sample verifies byte-for-byte round-trip. |
| 2 | Cost accounting drift — `ImageResponse.cost_usd` might not match actual Gemini billing | `_estimate_image_cost_usd` uses the same $0.04 constant the current code implies; no behavior change. |

**Rollback per PR:** `git revert <squash-commit>`. No stateful changes (no DB migrations, no feature flags).

---

## Effort estimate

| PR | Days |
|---|---|
| 1 | 1 |
| 2 | 0.5 |
| **Total** | **1.5 days** |

Much smaller than Phase 5b (6-8 days). Low complexity because:
- Gemini's image API is already the same `client.models.generate_content` shape as chat
- Only one consumer to migrate
- No streaming/tool-use/multi-turn complexity to model
- Leverages all Phase 5b infrastructure (breaker, retry, emit, sentry) without new wiring

---

## Expected outcome

| Dimension | Pre-5c | After 5c |
|---|---|---|
| Operational safety | 9.5 | 9.5 (breaker already protects chat; image gen inherits) |
| Code quality | 7 | 7.25 (single seam for all provider I/O, one fewer bypass path) |
| Test coverage | 9 | 9.25 (new adapter method fully covered + migration tests) |

Phase 5c moves composite average from ~7.6 (post-5b) to ~7.65.

---

## Self-review (2026-04-24)

**1. Placeholder scan:** none. Every PR section has concrete code, file paths, and test names.

**2. Internal consistency:**
- PR 1 defines `ImageRequest.retry: bool = False`; PR 2's migration sets `retry=False` (default) to preserve current no-retry behavior. ✓
- Cost calc: `_estimate_image_cost_usd` uses $0.04 constant; risk table notes this matches current code's implied cost. ✓
- Protocol method signature `generate_image(request: ImageRequest) -> ImageResponse` is consistent across types.py, __init__.py, and all three adapter files. ✓

**3. Scope check:** 2 PRs is appropriately small. Each PR is self-contained and reviewable in one sitting. No PR mixes unrelated concerns.

**4. Ambiguity check:**
- Reference-image shape: explicit — `ImagePart(base64=..., mime_type="image/png")` bytes form, not PIL Image.
- Retry default: explicit — `False` to preserve cost-sensitive current behavior.
- Image count return shape: explicit — `list[bytes]` even when Gemini always returns one.

Plan-writing can proceed.
