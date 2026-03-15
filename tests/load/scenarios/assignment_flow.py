"""
Load-test scenario: Assignment Management flow.
Tests save, list, load, model-answer generation, and export endpoints.
"""
import json
import logging

import httpx

from tests.load.config import LIVE_TESTS_ENABLED
from tests.load.utils import (
    StepResult,
    assert_json_has,
    make_headers,
    timed_request,
)

logger = logging.getLogger("load_test")

SCENARIO = "assignment_flow"


async def run_assignment_flow(
    client: httpx.AsyncClient,
    persona: dict,
    persona_data: dict,
    results: list,
) -> None:
    """Run the full assignment management flow for one persona.

    Steps:
      1. Save assignment config
      2. List assignments (verify it appears)
      3. Load assignment by name (verify round-trip)
      4. Generate model answers (only when LIVE_TESTS_ENABLED)
      5. Export assignment as docx
    """
    pid = persona["id"]
    headers = make_headers(persona)
    assignment_config = persona_data.get("assignment_config", {})
    title = assignment_config.get("title", "Untitled")

    # Build a safe title the same way the backend does (alnum + space/dash/underscore)
    safe_title = "".join(
        c for c in title if c.isalnum() or c in " -_"
    ).strip()

    # ── 1. Save assignment config ────────────────────────────────────────
    logger.info("[%s] Saving assignment config '%s' ...", pid, title)

    resp, step = await timed_request(
        client, "POST", "/api/save-assignment-config",
        persona_id=pid, scenario=SCENARIO, step="save_assignment_config",
        headers=headers, json=assignment_config,
    )
    results.append(step)

    # ── 2. List assignments ──────────────────────────────────────────────
    logger.info("[%s] Listing assignments ...", pid)

    resp, step = await timed_request(
        client, "GET", "/api/list-assignments",
        persona_id=pid, scenario=SCENARIO, step="list_assignments",
        headers=headers,
    )
    results.append(step)

    if resp is not None and step.status == "pass":
        data = resp.json()
        assignments = data.get("assignments", [])
        if safe_title not in assignments:
            step.status = "fail"
            step.error_message = (
                f"Saved assignment '{safe_title}' not found in list: {assignments}"
            )

    # ── 3. Load assignment ───────────────────────────────────────────────
    logger.info("[%s] Loading assignment '%s' ...", pid, safe_title)

    resp, step = await timed_request(
        client, "GET", "/api/load-assignment",
        persona_id=pid, scenario=SCENARIO, step="load_assignment",
        headers=headers, params={"name": safe_title},
    )
    results.append(step)

    if resp is not None and step.status == "pass":
        data = resp.json()
        assignment = data.get("assignment", {})
        if not assignment:
            step.status = "fail"
            step.error_message = "Loaded assignment is empty"
        elif assignment.get("title") != title:
            step.status = "fail"
            step.error_message = (
                f"Title mismatch: expected '{title}', "
                f"got '{assignment.get('title')}'"
            )

    # ── 4. Generate model answers (live tests only) ──────────────────────
    if LIVE_TESTS_ENABLED:
        logger.info("[%s] Generating model answers (live AI call) ...", pid)

        model_answers_payload = {
            "customMarkers": assignment_config.get("customMarkers", []),
            "documentText": (
                f"This is a sample {persona.get('subject', 'general')} assignment "
                f"for grade {persona.get('grade', '7')}. "
                f"{assignment_config.get('gradingNotes', '')}"
            ),
            "title": title,
            "grade_level": persona.get("grade", "7"),
            "subject": persona.get("subject", "Social Studies"),
            "globalAINotes": persona_data.get("global_settings", {}).get(
                "globalAINotes", ""
            ),
        }

        resp, step = await timed_request(
            client, "POST", "/api/generate-model-answers",
            persona_id=pid, scenario=SCENARIO, step="generate_model_answers",
            headers=headers, json=model_answers_payload,
            expected_status=(200, 400),  # 400 if doc text too short is acceptable
        )
        results.append(step)
    else:
        logger.info("[%s] Skipping model answer generation (LIVE_TESTS_ENABLED=False).", pid)
        results.append(StepResult(
            persona_id=pid, scenario=SCENARIO,
            step="generate_model_answers", status="skip",
            error_message="LIVE_TESTS_ENABLED is False; skipping AI call",
        ))

    # ── 5. Export assignment ─────────────────────────────────────────────
    logger.info("[%s] Exporting assignment as docx ...", pid)

    export_payload = {
        "format": "docx",
        "assignment": {
            "title": title,
            "instructions": assignment_config.get("gradingNotes", ""),
            "customMarkers": assignment_config.get("customMarkers", []),
        },
    }

    resp, step = await timed_request(
        client, "POST", "/api/export-assignment",
        persona_id=pid, scenario=SCENARIO, step="export_assignment",
        headers=headers, json=export_payload,
    )
    results.append(step)

    logger.info("[%s] Assignment flow complete.", pid)
