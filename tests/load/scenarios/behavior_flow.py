"""
Behavior tracking endpoints load test scenario.
Tests roster, session creation, data retrieval, and event listing.
"""
import httpx

from tests.load.utils import timed_request, make_headers, StepResult


SCENARIO = "behavior_flow"


async def run_behavior_flow(
    client: httpx.AsyncClient,
    persona: dict,
    persona_data: dict,
    results: list,
) -> None:
    """Exercise behavior tracking endpoints."""
    headers = make_headers(persona)
    pid = persona["id"]

    # 1. GET /api/behavior/roster
    _, step = await timed_request(
        client, "GET", "/api/behavior/roster",
        persona_id=pid, scenario=SCENARIO, step="get_behavior_roster",
        headers=headers,
    )
    results.append(step)

    # 2. POST /api/behavior/session — create a test session
    _, step = await timed_request(
        client, "POST", "/api/behavior/session",
        persona_id=pid, scenario=SCENARIO, step="post_behavior_session",
        headers=headers,
        json={
            "class_period": "3",
            "date": "2026-03-15",
            "notes": "Load test session",
        },
    )
    results.append(step)

    # 3. GET /api/behavior/data
    _, step = await timed_request(
        client, "GET", "/api/behavior/data",
        persona_id=pid, scenario=SCENARIO, step="get_behavior_data",
        headers=headers,
    )
    results.append(step)

    # 4. GET /api/behavior/events
    _, step = await timed_request(
        client, "GET", "/api/behavior/events",
        persona_id=pid, scenario=SCENARIO, step="get_behavior_events",
        headers=headers,
    )
    results.append(step)
