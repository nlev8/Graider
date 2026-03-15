"""
Shared utilities for load testing.
Timing, assertions, polling, and result tracking.
"""
import time
import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime

import httpx

logger = logging.getLogger("load_test")


@dataclass
class StepResult:
    persona_id: str
    scenario: str
    step: str
    status: str  # pass | fail | error | skip
    latency_ms: float = 0.0
    status_code: int = 0
    error_message: str | None = None
    response_snippet: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


async def timed_request(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    persona_id: str = "",
    scenario: str = "",
    step: str = "",
    expected_status: int | tuple = 200,
    **kwargs,
) -> tuple[httpx.Response | None, StepResult]:
    """Make an HTTP request and return (response, StepResult)."""
    if isinstance(expected_status, int):
        expected_status = (expected_status,)

    start = time.perf_counter()
    try:
        resp = await client.request(method, url, **kwargs)
        latency = (time.perf_counter() - start) * 1000

        if resp.status_code in expected_status:
            return resp, StepResult(
                persona_id=persona_id,
                scenario=scenario,
                step=step,
                status="pass",
                latency_ms=round(latency, 1),
                status_code=resp.status_code,
                response_snippet=resp.text[:500] if resp.text else None,
            )
        else:
            return resp, StepResult(
                persona_id=persona_id,
                scenario=scenario,
                step=step,
                status="fail",
                latency_ms=round(latency, 1),
                status_code=resp.status_code,
                error_message=f"Expected {expected_status}, got {resp.status_code}",
                response_snippet=resp.text[:500] if resp.text else None,
            )
    except Exception as e:
        latency = (time.perf_counter() - start) * 1000
        return None, StepResult(
            persona_id=persona_id,
            scenario=scenario,
            step=step,
            status="error",
            latency_ms=round(latency, 1),
            error_message=str(e),
        )


async def poll_until(
    client: httpx.AsyncClient,
    url: str,
    condition_fn,
    timeout_s: float = 60,
    interval_s: float = 0.5,
    **kwargs,
) -> httpx.Response | None:
    """Poll a URL until condition_fn(response_json) returns True or timeout."""
    deadline = time.perf_counter() + timeout_s
    while time.perf_counter() < deadline:
        try:
            resp = await client.get(url, **kwargs)
            if resp.status_code == 200:
                data = resp.json()
                if condition_fn(data):
                    return resp
        except Exception:
            pass
        await asyncio.sleep(interval_s)
    return None


def assert_json_has(data: dict, *keys) -> list[str]:
    """Return list of missing keys from a JSON dict."""
    return [k for k in keys if k not in data]


def make_headers(persona: dict) -> dict:
    """Build request headers for a test persona."""
    return {
        "X-Test-Teacher-Id": persona["id"],
        "Content-Type": "application/json",
    }


def make_multipart_headers(persona: dict) -> dict:
    """Build headers for multipart requests (no Content-Type — httpx sets it)."""
    return {"X-Test-Teacher-Id": persona["id"]}
