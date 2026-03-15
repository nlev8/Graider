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
    # The endpoint expects questions as objects with id, text, and type fields
    resp_create, step = await timed_request(
        client, "POST", "/api/survey/create",
        persona_id=pid, scenario=SCENARIO_SURVEY, step="create_survey",
        headers=headers,
        json={
            "title": f"{subject} Feedback",
            "questions": [
                {"id": "lesson_quality", "text": "How was the lesson?", "type": "rating"},
                {"id": "improvements", "text": "What can be improved?", "type": "text"},
            ],
        },
    )
    results.append(step)

    # Extract join_code from create response for use in results query
    join_code = None
    if resp_create and step.status == "pass":
        create_data = resp_create.json()
        join_code = create_data.get("join_code") or create_data.get("code")

    # 2. GET /api/survey/list
    _, step = await timed_request(
        client, "GET", "/api/survey/list",
        persona_id=pid, scenario=SCENARIO_SURVEY, step="list_surveys",
        headers=headers,
    )
    results.append(step)

    # 3. GET /api/survey/results — requires code query param
    if join_code:
        _, step = await timed_request(
            client, "GET", f"/api/survey/results?code={join_code}",
            persona_id=pid, scenario=SCENARIO_SURVEY, step="get_survey_results",
            headers=headers,
        )
    else:
        step = StepResult(
            persona_id=pid, scenario=SCENARIO_SURVEY,
            step="get_survey_results", status="skip",
            error_message="No join_code from create_survey step",
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

    # 4. GET /api/auth/approval-status — may 500 with fake test user IDs (Supabase admin lookup)
    _, step = await timed_request(
        client, "GET", "/api/auth/approval-status",
        persona_id=pid, scenario=SCENARIO_MISC, step="get_approval_status",
        headers=headers,
        expected_status=(200, 500),
    )
    results.append(step)
