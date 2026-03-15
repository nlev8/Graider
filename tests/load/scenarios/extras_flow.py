"""
Surveys, automations, and miscellaneous endpoint load test scenarios.
Tests survey CRUD, automation templates, user manual, and auth/billing status.
"""
import httpx

from tests.load.utils import timed_request, make_headers, StepResult


SCENARIO_SURVEY = "survey_flow"
SCENARIO_AUTOMATION = "automation_flow"
SCENARIO_MISC = "misc_flow"


async def run_survey_flow(
    client: httpx.AsyncClient,
    persona: dict,
    persona_data: dict,
    results: list,
) -> None:
    """Exercise survey endpoints."""
    headers = make_headers(persona)
    pid = persona["id"]
    subject = persona.get("subject", "General")

    # 1. POST /api/survey/create — create a feedback survey
    _, step = await timed_request(
        client, "POST", "/api/survey/create",
        persona_id=pid, scenario=SCENARIO_SURVEY, step="create_survey",
        headers=headers,
        json={
            "title": f"{subject} Feedback",
            "questions": [
                "How was the lesson?",
                "What can be improved?",
            ],
        },
    )
    results.append(step)

    # 2. GET /api/survey/list
    _, step = await timed_request(
        client, "GET", "/api/survey/list",
        persona_id=pid, scenario=SCENARIO_SURVEY, step="list_surveys",
        headers=headers,
    )
    results.append(step)

    # 3. GET /api/survey/results
    _, step = await timed_request(
        client, "GET", "/api/survey/results",
        persona_id=pid, scenario=SCENARIO_SURVEY, step="get_survey_results",
        headers=headers,
    )
    results.append(step)


async def run_automation_flow(
    client: httpx.AsyncClient,
    persona: dict,
    persona_data: dict,
    results: list,
) -> None:
    """Exercise automation endpoints."""
    headers = make_headers(persona)
    pid = persona["id"]

    # 1. GET /api/automations
    _, step = await timed_request(
        client, "GET", "/api/automations",
        persona_id=pid, scenario=SCENARIO_AUTOMATION, step="get_automations",
        headers=headers,
    )
    results.append(step)

    # 2. GET /api/automations/templates
    _, step = await timed_request(
        client, "GET", "/api/automations/templates",
        persona_id=pid, scenario=SCENARIO_AUTOMATION, step="get_automation_templates",
        headers=headers,
    )
    results.append(step)


async def run_misc_flow(
    client: httpx.AsyncClient,
    persona: dict,
    persona_data: dict,
    results: list,
) -> None:
    """Exercise miscellaneous endpoints."""
    headers = make_headers(persona)
    pid = persona["id"]

    # 1. GET /api/user-manual
    _, step = await timed_request(
        client, "GET", "/api/user-manual",
        persona_id=pid, scenario=SCENARIO_MISC, step="get_user_manual",
        headers=headers,
    )
    results.append(step)

    # 2. GET / — serve app home (expect HTML)
    _, step = await timed_request(
        client, "GET", "/",
        persona_id=pid, scenario=SCENARIO_MISC, step="get_home",
        headers=headers,
    )
    results.append(step)

    # 3. GET /api/stripe/subscription-status — may 500 if Stripe not configured
    _, step = await timed_request(
        client, "GET", "/api/stripe/subscription-status",
        persona_id=pid, scenario=SCENARIO_MISC, step="get_subscription_status",
        headers=headers,
        expected_status=(200, 500),
    )
    results.append(step)

    # 4. GET /api/auth/approval-status
    _, step = await timed_request(
        client, "GET", "/api/auth/approval-status",
        persona_id=pid, scenario=SCENARIO_MISC, step="get_approval_status",
        headers=headers,
    )
    results.append(step)
