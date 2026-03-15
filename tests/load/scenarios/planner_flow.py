"""
Planner flow scenario — tests lesson planning and assessment generation endpoints.
"""
import logging

import httpx

from tests.load.utils import timed_request, make_headers, StepResult, assert_json_has, poll_until
from tests.load.config import LIVE_TESTS_ENABLED

logger = logging.getLogger("load_test")

SCENARIO = "planner_flow"


async def run_planner_flow(client, persona, persona_data, results):
    """Exercise all lesson-planning and assessment-generation endpoints."""
    headers = make_headers(persona)
    pid = persona["id"]

    # ── Step A: Get standards ────────────────────────────────────────────
    resp, step = await timed_request(
        client, "POST", "/api/get-standards",
        persona_id=pid, scenario=SCENARIO, step="get_standards",
        json={
            "state": persona["state"],
            "grade": persona["grade"],
            "subject": persona["subject"],
        },
        headers=headers,
    )
    results.append(step)

    standards = []
    if resp and step.status == "pass":
        data = resp.json()
        standards = data.get("standards", [])
        missing = assert_json_has(data, "standards")
        if missing:
            step.status = "fail"
            step.error_message = f"Response missing keys: {missing}"

    # ── Live (AI) tests ──────────────────────────────────────────────────
    if LIVE_TESTS_ENABLED:
        # Step B: Generate lesson plan
        lesson_config = {
            "state": persona["state"],
            "grade": persona["grade"],
            "subject": persona["subject"],
            "standards": standards[:3],
            "duration": "50 minutes",
            "objectives": [f"Students will demonstrate understanding of {persona['subject']} concepts"],
        }
        resp_lp, step_lp = await timed_request(
            client, "POST", "/api/generate-lesson-plan",
            persona_id=pid, scenario=SCENARIO, step="generate_lesson_plan",
            json=lesson_config,
            headers=headers,
            timeout=httpx.Timeout(60.0),
        )
        results.append(step_lp)

        lesson_plan = {}
        if resp_lp and step_lp.status == "pass":
            lesson_plan = resp_lp.json()

        # Step C: Generate assessment
        assessment_config = persona_data.get("assessment_config", {
            "title": f"{persona['subject']} Unit Assessment",
            "subject": persona["subject"],
            "grade": persona["grade"],
            "standards": standards[:2],
            "question_count": 5,
            "question_types": ["multiple_choice", "true_false", "short_answer"],
            "difficulty": "medium",
            "total_points": 50,
        })
        resp_assess, step_assess = await timed_request(
            client, "POST", "/api/generate-assessment",
            persona_id=pid, scenario=SCENARIO, step="generate_assessment",
            json=assessment_config,
            headers=headers,
            timeout=httpx.Timeout(60.0),
        )
        results.append(step_assess)

        generated_questions = []
        if resp_assess and step_assess.status == "pass":
            assess_data = resp_assess.json()
            generated_questions = assess_data.get("questions", [])

        # Step D: Regenerate a subset of questions
        if generated_questions:
            regen_payload = {
                "questions": generated_questions[:2],
                "subject": persona["subject"],
                "grade": persona["grade"],
                "standards": standards[:2],
            }
            resp_regen, step_regen = await timed_request(
                client, "POST", "/api/regenerate-questions",
                persona_id=pid, scenario=SCENARIO, step="regenerate_questions",
                json=regen_payload,
                headers=headers,
                timeout=httpx.Timeout(60.0),
            )
            results.append(step_regen)

        # Step E: Adjust reading level
        resp_rl, step_rl = await timed_request(
            client, "POST", "/api/adjust-reading-level",
            persona_id=pid, scenario=SCENARIO, step="adjust_reading_level",
            json={
                "text": "The legislative branch of government is responsible for creating laws.",
                "target_level": persona["grade"],
            },
            headers=headers,
            timeout=httpx.Timeout(60.0),
        )
        results.append(step_rl)

        # Step F: Export lesson plan
        if lesson_plan:
            resp_exp_lp, step_exp_lp = await timed_request(
                client, "POST", "/api/export-lesson-plan",
                persona_id=pid, scenario=SCENARIO, step="export_lesson_plan",
                json={"lesson_plan": lesson_plan, "format": "docx"},
                headers=headers,
            )
            results.append(step_exp_lp)

        # Step G: Export assessment
        if generated_questions:
            resp_exp_a, step_exp_a = await timed_request(
                client, "POST", "/api/export-assessment",
                persona_id=pid, scenario=SCENARIO, step="export_assessment",
                json={
                    "title": assessment_config.get("title", "Assessment"),
                    "questions": generated_questions,
                    "format": "docx",
                },
                headers=headers,
            )
            results.append(step_exp_a)

        # Step H: Verify cost tracking
        resp_cost, step_cost = await timed_request(
            client, "GET", "/api/planner/costs",
            persona_id=pid, scenario=SCENARIO, step="planner_costs_live",
            headers=headers,
        )
        results.append(step_cost)

    else:
        # ── Non-AI tests (always safe to run) ────────────────────────────
        # Assessment templates
        resp_tpl, step_tpl = await timed_request(
            client, "GET", "/api/assessment-templates",
            persona_id=pid, scenario=SCENARIO, step="assessment_templates",
            headers=headers,
        )
        results.append(step_tpl)

        # Planner costs
        resp_cost, step_cost = await timed_request(
            client, "GET", "/api/planner/costs",
            persona_id=pid, scenario=SCENARIO, step="planner_costs",
            headers=headers,
        )
        results.append(step_cost)

    logger.info("[%s] planner_flow complete (%d steps)", pid, len(results))
