"""
Analytics and grading result endpoints load test scenario.
Tests analytics, student history, ELL, and FERPA endpoints.
"""
import httpx

from tests.load.utils import timed_request, make_headers, StepResult


SCENARIO = "analytics_flow"


async def run_analytics_flow(
    client: httpx.AsyncClient,
    persona: dict,
    persona_data: dict,
    results: list,
) -> None:
    """Exercise analytics and grading result endpoints."""
    headers = make_headers(persona)
    pid = persona["id"]

    # 1. GET /api/analytics
    _, step = await timed_request(
        client, "GET", "/api/analytics",
        persona_id=pid, scenario=SCENARIO, step="get_analytics",
        headers=headers,
    )
    results.append(step)

    # 2. GET /api/status — grading status
    _, step = await timed_request(
        client, "GET", "/api/status",
        persona_id=pid, scenario=SCENARIO, step="get_grading_status",
        headers=headers,
    )
    results.append(step)

    # 3. GET /api/student-history — all student history
    _, step = await timed_request(
        client, "GET", "/api/student-history",
        persona_id=pid, scenario=SCENARIO, step="get_student_history",
        headers=headers,
    )
    results.append(step)

    # 4. GET /api/ell-students
    _, step = await timed_request(
        client, "GET", "/api/ell-students",
        persona_id=pid, scenario=SCENARIO, step="get_ell_students",
        headers=headers,
    )
    results.append(step)

    # 5. POST /api/ell-students — add an ELL student
    _, step = await timed_request(
        client, "POST", "/api/ell-students",
        persona_id=pid, scenario=SCENARIO, step="post_ell_student",
        headers=headers,
        json={"student_name": "Test Student", "target_language": "Spanish"},
    )
    results.append(step)

    # 6. GET /api/ferpa/data-summary
    _, step = await timed_request(
        client, "GET", "/api/ferpa/data-summary",
        persona_id=pid, scenario=SCENARIO, step="get_ferpa_data_summary",
        headers=headers,
    )
    results.append(step)

    # 7. GET /api/ferpa/audit-log
    _, step = await timed_request(
        client, "GET", "/api/ferpa/audit-log",
        persona_id=pid, scenario=SCENARIO, step="get_ferpa_audit_log",
        headers=headers,
    )
    results.append(step)
