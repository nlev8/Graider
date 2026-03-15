"""
AI assistant chat and utility endpoints load test scenario.
Tests costs, credentials, voice config, and optionally live chat.
"""
import time

import httpx

from tests.load.utils import timed_request, make_headers, StepResult
from tests.load.config import LIVE_TESTS_ENABLED


SCENARIO = "assistant_flow"


async def run_assistant_flow(
    client: httpx.AsyncClient,
    persona: dict,
    persona_data: dict,
    results: list,
) -> None:
    """Exercise AI assistant endpoints."""
    headers = make_headers(persona)
    pid = persona["id"]

    # 1. GET /api/assistant/costs
    _, step = await timed_request(
        client, "GET", "/api/assistant/costs",
        persona_id=pid, scenario=SCENARIO, step="get_assistant_costs",
        headers=headers,
    )
    results.append(step)

    # 2. GET /api/assistant/credentials
    _, step = await timed_request(
        client, "GET", "/api/assistant/credentials",
        persona_id=pid, scenario=SCENARIO, step="get_assistant_credentials",
        headers=headers,
    )
    results.append(step)

    # 3. GET /api/assistant/voice-config
    _, step = await timed_request(
        client, "GET", "/api/assistant/voice-config",
        persona_id=pid, scenario=SCENARIO, step="get_assistant_voice_config",
        headers=headers,
    )
    results.append(step)

    # 4. Live tests (SSE chat, memory, clear) — only when API key is available
    if LIVE_TESTS_ENABLED:
        subject = persona.get("subject", "general studies")

        # POST /api/assistant/chat — SSE streaming endpoint
        start = time.perf_counter()
        try:
            async with client.stream(
                "POST",
                "/api/assistant/chat",
                headers=headers,
                json={"message": f"What standards should I focus on for {subject}?"},
            ) as resp:
                latency = (time.perf_counter() - start) * 1000
                # Read a small chunk to confirm the stream is working
                chunk = b""
                async for part in resp.aiter_bytes():
                    chunk += part
                    if len(chunk) > 256:
                        break

                if resp.status_code == 200:
                    step = StepResult(
                        persona_id=pid,
                        scenario=SCENARIO,
                        step="post_assistant_chat_sse",
                        status="pass",
                        latency_ms=round(latency, 1),
                        status_code=resp.status_code,
                        response_snippet=chunk[:500].decode("utf-8", errors="replace"),
                    )
                else:
                    step = StepResult(
                        persona_id=pid,
                        scenario=SCENARIO,
                        step="post_assistant_chat_sse",
                        status="fail",
                        latency_ms=round(latency, 1),
                        status_code=resp.status_code,
                        error_message=f"Expected 200, got {resp.status_code}",
                    )
        except Exception as e:
            latency = (time.perf_counter() - start) * 1000
            step = StepResult(
                persona_id=pid,
                scenario=SCENARIO,
                step="post_assistant_chat_sse",
                status="error",
                latency_ms=round(latency, 1),
                error_message=str(e),
            )
        results.append(step)

        # GET /api/assistant/memory
        _, step = await timed_request(
            client, "GET", "/api/assistant/memory",
            persona_id=pid, scenario=SCENARIO, step="get_assistant_memory",
            headers=headers,
        )
        results.append(step)

        # POST /api/assistant/clear
        _, step = await timed_request(
            client, "POST", "/api/assistant/clear",
            persona_id=pid, scenario=SCENARIO, step="post_assistant_clear",
            headers=headers,
        )
        results.append(step)
