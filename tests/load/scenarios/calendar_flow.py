"""
Calendar and lesson management load test scenarios.
Tests calendar CRUD, school-day config, holidays, and lesson storage endpoints.
"""
import httpx

from tests.load.utils import timed_request, make_headers, StepResult


SCENARIO_CALENDAR = "calendar_flow"
SCENARIO_LESSON = "lesson_flow"


async def run_calendar_flow(
    client: httpx.AsyncClient,
    persona: dict,
    persona_data: dict,
    results: list,
) -> None:
    """Exercise calendar management endpoints."""
    headers = make_headers(persona)
    pid = persona["id"]
    subject = persona.get("subject", "General")

    # 1. GET /api/calendar — initial fetch
    _, step = await timed_request(
        client, "GET", "/api/calendar",
        persona_id=pid, scenario=SCENARIO_CALENDAR, step="get_calendar",
        headers=headers,
    )
    results.append(step)

    # 2. PUT /api/calendar/schedule — add a test lesson entry
    _, step = await timed_request(
        client, "PUT", "/api/calendar/schedule",
        persona_id=pid, scenario=SCENARIO_CALENDAR, step="put_schedule",
        headers=headers,
        json={
            "date": "2026-04-01",
            "unit": subject,
            "lesson_title": f"{subject} Lesson 1",
            "color": "#6366f1",
        },
    )
    results.append(step)

    # 3. PUT /api/calendar/school-days — configure school days
    _, step = await timed_request(
        client, "PUT", "/api/calendar/school-days",
        persona_id=pid, scenario=SCENARIO_CALENDAR, step="put_school_days",
        headers=headers,
        json={
            "monday": True,
            "tuesday": True,
            "wednesday": True,
            "thursday": True,
            "friday": True,
            "saturday": False,
            "sunday": False,
        },
    )
    results.append(step)

    # 4. POST /api/calendar/holiday — add a holiday
    _, step = await timed_request(
        client, "POST", "/api/calendar/holiday",
        persona_id=pid, scenario=SCENARIO_CALENDAR, step="post_holiday",
        headers=headers,
        json={"date": "2026-04-15", "name": "Spring Break"},
    )
    results.append(step)

    # 5. GET /api/calendar — verify entries present
    _, step = await timed_request(
        client, "GET", "/api/calendar",
        persona_id=pid, scenario=SCENARIO_CALENDAR, step="get_calendar_verify",
        headers=headers,
    )
    results.append(step)

    # 6. DELETE /api/calendar/holiday — clean up the holiday
    _, step = await timed_request(
        client, "DELETE", "/api/calendar/holiday",
        persona_id=pid, scenario=SCENARIO_CALENDAR, step="delete_holiday",
        headers=headers,
        params={"date": "2026-04-15"},
    )
    results.append(step)


async def run_lesson_flow(
    client: httpx.AsyncClient,
    persona: dict,
    persona_data: dict,
    results: list,
) -> None:
    """Exercise lesson storage endpoints."""
    headers = make_headers(persona)
    pid = persona["id"]
    subject = persona.get("subject", "General")
    title = f"{subject} Review"
    standards = persona_data.get("assessment_config", {}).get("standards", [])

    # 1. POST /api/save-lesson — save a test lesson
    _, step = await timed_request(
        client, "POST", "/api/save-lesson",
        persona_id=pid, scenario=SCENARIO_LESSON, step="save_lesson",
        headers=headers,
        json={
            "lesson": {
                "title": title,
                "standards": standards,
                "learning_objectives": ["Understand key concepts"],
            },
            "unitName": subject,
        },
    )
    results.append(step)

    # 2. GET /api/list-lessons
    _, step = await timed_request(
        client, "GET", "/api/list-lessons",
        persona_id=pid, scenario=SCENARIO_LESSON, step="list_lessons",
        headers=headers,
    )
    results.append(step)

    # 3. GET /api/load-lesson — load the saved lesson
    _, step = await timed_request(
        client, "GET", "/api/load-lesson",
        persona_id=pid, scenario=SCENARIO_LESSON, step="load_lesson",
        headers=headers,
        params={"unit": subject, "filename": title},
    )
    results.append(step)

    # 4. GET /api/list-units
    _, step = await timed_request(
        client, "GET", "/api/list-units",
        persona_id=pid, scenario=SCENARIO_LESSON, step="list_units",
        headers=headers,
    )
    results.append(step)

    # 5. DELETE /api/delete-lesson — clean up
    _, step = await timed_request(
        client, "DELETE", "/api/delete-lesson",
        persona_id=pid, scenario=SCENARIO_LESSON, step="delete_lesson",
        headers=headers,
        params={"unit": subject, "filename": title},
    )
    results.append(step)
