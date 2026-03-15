"""
Load-test scenario: Settings & Configuration flow.
Tests rubric, global settings, API keys, accommodations, and roster endpoints.
"""
import json
import logging
import os

import httpx

from tests.load.utils import (
    StepResult,
    assert_json_has,
    make_headers,
    make_multipart_headers,
    timed_request,
)

logger = logging.getLogger("load_test")

SCENARIO = "settings_flow"
ROSTER_SCENARIO = "roster_flow"

# Map persona subjects to roster fixture filenames
_SUBJECT_ROSTER_MAP = {
    "Civics": "roster_civics_7.csv",
    "US History": "roster_history_8.csv",
    "Mathematics": "roster_math_6.csv",
    "English Language Arts": "roster_ela_7.csv",
    "Science": "roster_science_8.csv",
}

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "..", "fixtures")
ROSTERS_DIR = os.path.join(FIXTURES_DIR, "rosters")


async def run_settings_flow(
    client: httpx.AsyncClient,
    persona: dict,
    persona_data: dict,
    results: list,
) -> None:
    """Run the full settings round-trip flow for one persona.

    Steps:
      1. Save rubric
      2. Load rubric (verify round-trip)
      3. Save global settings
      4. Load global settings (verify round-trip)
      5. Save API keys (dummy)
      6. Check API keys
      7. GET accommodation presets
      8. POST accommodation preset
      9. GET student accommodations
     10. GET accommodation stats
    """
    pid = persona["id"]
    headers = make_headers(persona)

    # ── 1. Save rubric ──────────────────────────────────────────────────
    rubric_payload = persona_data.get("rubric", {})
    logger.info("[%s] Saving rubric ...", pid)

    resp, step = await timed_request(
        client, "POST", "/api/save-rubric",
        persona_id=pid, scenario=SCENARIO, step="save_rubric",
        headers=headers, json=rubric_payload,
    )
    results.append(step)

    # ── 2. Load rubric ───────────────────────────────────────────────────
    logger.info("[%s] Loading rubric ...", pid)

    resp, step = await timed_request(
        client, "GET", "/api/load-rubric",
        persona_id=pid, scenario=SCENARIO, step="load_rubric",
        headers=headers,
    )
    results.append(step)

    if resp is not None and step.status == "pass":
        data = resp.json()
        missing = assert_json_has(data, "rubric")
        if missing:
            step.status = "fail"
            step.error_message = f"Rubric response missing keys: {missing}"

    # ── 3. Save global settings ──────────────────────────────────────────
    global_settings = persona_data.get("global_settings", {})
    logger.info("[%s] Saving global settings ...", pid)

    resp, step = await timed_request(
        client, "POST", "/api/save-global-settings",
        persona_id=pid, scenario=SCENARIO, step="save_global_settings",
        headers=headers, json=global_settings,
    )
    results.append(step)

    # ── 4. Load global settings ──────────────────────────────────────────
    logger.info("[%s] Loading global settings ...", pid)

    resp, step = await timed_request(
        client, "GET", "/api/load-global-settings",
        persona_id=pid, scenario=SCENARIO, step="load_global_settings",
        headers=headers,
    )
    results.append(step)

    if resp is not None and step.status == "pass":
        data = resp.json()
        missing = assert_json_has(data, "settings")
        if missing:
            step.status = "fail"
            step.error_message = f"Global settings response missing keys: {missing}"

    # ── 5. Save API keys (dummy) ─────────────────────────────────────────
    logger.info("[%s] Saving dummy API keys ...", pid)

    resp, step = await timed_request(
        client, "POST", "/api/save-api-keys",
        persona_id=pid, scenario=SCENARIO, step="save_api_keys",
        headers=headers,
        json={
            "openai_key": "sk-test-dummy-key-000",
            "anthropic_key": "",
            "gemini_key": "",
        },
    )
    results.append(step)

    # ── 6. Check API keys ────────────────────────────────────────────────
    logger.info("[%s] Checking API keys ...", pid)

    resp, step = await timed_request(
        client, "GET", "/api/check-api-keys",
        persona_id=pid, scenario=SCENARIO, step="check_api_keys",
        headers=headers,
    )
    results.append(step)

    # ── 7. GET accommodation presets ─────────────────────────────────────
    logger.info("[%s] Fetching accommodation presets ...", pid)

    resp, step = await timed_request(
        client, "GET", "/api/accommodation-presets",
        persona_id=pid, scenario=SCENARIO, step="get_accommodation_presets",
        headers=headers,
    )
    results.append(step)

    # ── 8. POST accommodation preset ────────────────────────────────────
    logger.info("[%s] Creating accommodation preset ...", pid)

    preset_payload = {
        "name": f"Load Test Preset ({persona.get('name', pid)})",
        "accommodations": {
            "extended_time": True,
            "reduced_questions": False,
            "simplified_language": True,
        },
        "ai_instructions": "Allow extended time, use simplified language",
    }

    resp, step = await timed_request(
        client, "POST", "/api/accommodation-presets",
        persona_id=pid, scenario=SCENARIO, step="create_accommodation_preset",
        headers=headers, json=preset_payload,
    )
    results.append(step)

    # ── 9. GET student accommodations ────────────────────────────────────
    logger.info("[%s] Fetching student accommodations ...", pid)

    resp, step = await timed_request(
        client, "GET", "/api/student-accommodations",
        persona_id=pid, scenario=SCENARIO, step="get_student_accommodations",
        headers=headers,
    )
    results.append(step)

    # ── 10. GET accommodation stats ──────────────────────────────────────
    logger.info("[%s] Fetching accommodation stats ...", pid)

    resp, step = await timed_request(
        client, "GET", "/api/accommodation-stats",
        persona_id=pid, scenario=SCENARIO, step="get_accommodation_stats",
        headers=headers,
    )
    results.append(step)

    logger.info("[%s] Settings flow complete (%d steps).", pid, 10)


async def run_roster_flow(
    client: httpx.AsyncClient,
    persona: dict,
    persona_data: dict,
    results: list,
) -> None:
    """Run roster upload and listing flow for one persona.

    Steps:
      1. Upload roster CSV (multipart)
      2. List rosters
      3. List periods
    """
    pid = persona["id"]
    headers = make_headers(persona)
    mp_headers = make_multipart_headers(persona)

    # Determine which roster file to use based on persona subject
    subject = persona.get("subject", "")
    roster_filename = _SUBJECT_ROSTER_MAP.get(subject)

    if not roster_filename:
        logger.warning("[%s] No roster fixture for subject '%s', skipping upload.", pid, subject)
        results.append(StepResult(
            persona_id=pid, scenario=ROSTER_SCENARIO,
            step="upload_roster", status="skip",
            error_message=f"No roster fixture for subject: {subject}",
        ))
    else:
        roster_path = os.path.join(ROSTERS_DIR, roster_filename)

        # ── 1. Upload roster ─────────────────────────────────────────────
        logger.info("[%s] Uploading roster %s ...", pid, roster_filename)

        if not os.path.exists(roster_path):
            logger.error("[%s] Roster file not found: %s", pid, roster_path)
            results.append(StepResult(
                persona_id=pid, scenario=ROSTER_SCENARIO,
                step="upload_roster", status="error",
                error_message=f"File not found: {roster_path}",
            ))
        else:
            with open(roster_path, "rb") as f:
                resp, step = await timed_request(
                    client, "POST", "/api/upload-roster",
                    persona_id=pid, scenario=ROSTER_SCENARIO, step="upload_roster",
                    headers=mp_headers,
                    files={"file": (roster_filename, f, "text/csv")},
                )
            results.append(step)

            if resp is not None and step.status == "pass":
                data = resp.json()
                missing = assert_json_has(data, "filename", "headers", "row_count")
                if missing:
                    step.status = "fail"
                    step.error_message = f"Upload response missing keys: {missing}"

    # ── 2. List rosters ──────────────────────────────────────────────────
    logger.info("[%s] Listing rosters ...", pid)

    resp, step = await timed_request(
        client, "GET", "/api/list-rosters",
        persona_id=pid, scenario=ROSTER_SCENARIO, step="list_rosters",
        headers=headers,
    )
    results.append(step)

    # ── 3. List periods ──────────────────────────────────────────────────
    logger.info("[%s] Listing periods ...", pid)

    resp, step = await timed_request(
        client, "GET", "/api/list-periods",
        persona_id=pid, scenario=ROSTER_SCENARIO, step="list_periods",
        headers=headers,
    )
    results.append(step)

    logger.info("[%s] Roster flow complete.", pid)
