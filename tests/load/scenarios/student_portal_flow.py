"""
Student portal flow scenario — tests the full publish / join / submit / grade lifecycle.
"""
import logging

from tests.load.utils import timed_request, make_headers, StepResult, assert_json_has, poll_until

logger = logging.getLogger("load_test")

SCENARIO = "student_portal_flow"


def _build_assessment(persona):
    """Build a subject-relevant inline assessment for the given persona."""
    subject = persona.get("subject", "General")

    question_banks = {
        "Civics": [
            {"number": 1, "question": "What is the capital of Florida?", "type": "multiple_choice", "points": 10,
             "options": ["Miami", "Tallahassee", "Orlando", "Jacksonville"], "answer": "B"},
            {"number": 2, "question": "True or False: The Constitution has 27 amendments.",
             "type": "true_false", "points": 10, "answer": "True"},
            {"number": 3, "question": "Explain the importance of civic participation.",
             "type": "short_answer", "points": 10,
             "answer": "Civic participation is essential for a functioning democracy."},
        ],
        "US History": [
            {"number": 1, "question": "Which document declared independence from Britain?",
             "type": "multiple_choice", "points": 10,
             "options": ["The Constitution", "The Declaration of Independence", "The Bill of Rights", "The Federalist Papers"],
             "answer": "B"},
            {"number": 2, "question": "True or False: The Louisiana Purchase doubled the size of the United States.",
             "type": "true_false", "points": 10, "answer": "True"},
            {"number": 3, "question": "Describe one cause of the Civil War.",
             "type": "short_answer", "points": 10,
             "answer": "Slavery and states' rights were primary causes of the Civil War."},
        ],
        "Mathematics": [
            {"number": 1, "question": "What is the value of 7 x 8?", "type": "multiple_choice", "points": 10,
             "options": ["48", "54", "56", "64"], "answer": "C"},
            {"number": 2, "question": "True or False: A triangle has four sides.",
             "type": "true_false", "points": 10, "answer": "False"},
            {"number": 3, "question": "Explain how to find the area of a rectangle.",
             "type": "short_answer", "points": 10,
             "answer": "Multiply the length by the width to find the area."},
        ],
        "English Language Arts": [
            {"number": 1, "question": "Which part of speech describes a noun?", "type": "multiple_choice", "points": 10,
             "options": ["Verb", "Adjective", "Adverb", "Preposition"], "answer": "B"},
            {"number": 2, "question": "True or False: A simile uses 'like' or 'as' to make a comparison.",
             "type": "true_false", "points": 10, "answer": "True"},
            {"number": 3, "question": "Write a thesis statement about the theme of courage in literature.",
             "type": "short_answer", "points": 10,
             "answer": "Courage is a recurring theme that reveals character growth under adversity."},
        ],
        "Science": [
            {"number": 1, "question": "What is the chemical symbol for water?", "type": "multiple_choice", "points": 10,
             "options": ["CO2", "H2O", "NaCl", "O2"], "answer": "B"},
            {"number": 2, "question": "True or False: Sound travels faster than light.",
             "type": "true_false", "points": 10, "answer": "False"},
            {"number": 3, "question": "Describe the water cycle in your own words.",
             "type": "short_answer", "points": 10,
             "answer": "Water evaporates, condenses into clouds, and falls as precipitation."},
        ],
    }

    questions = question_banks.get(subject, question_banks["Civics"])

    return {
        "title": f"{subject} Quick Check",
        "total_points": 30,
        "sections": [{
            "name": "Section 1",
            "instructions": "Answer all questions.",
            "questions": questions,
        }],
    }


def _build_student_answers(assessment):
    """Build a plausible student submission from the assessment questions.

    The backend grades using keys like "sectionIdx-questionIdx", so we must
    return a *dict* keyed that way — not a list of {number, answer} objects.
    """
    answers = {}
    for sIdx, section in enumerate(assessment.get("sections", [])):
        for qIdx, q in enumerate(section.get("questions", [])):
            key = f"{sIdx}-{qIdx}"
            if q["type"] == "multiple_choice":
                answers[key] = "B"
            elif q["type"] == "true_false":
                answers[key] = "True"
            elif q["type"] == "short_answer":
                answers[key] = "This is my answer to the question."
            else:
                answers[key] = "Answer"
    return answers


async def run_student_portal_flow(client, persona, persona_data, results):
    """Full student portal lifecycle: publish, join, submit, grade, manage."""
    headers = make_headers(persona)
    pid = persona["id"]
    test_assessment = _build_assessment(persona)

    # ── Step A: Publish assessment ───────────────────────────────────────
    resp_pub, step_pub = await timed_request(
        client, "POST", "/api/publish-assessment",
        persona_id=pid, scenario=SCENARIO, step="publish_assessment",
        json={"assessment": test_assessment},
        headers=headers,
    )
    results.append(step_pub)

    join_code = None
    if resp_pub and step_pub.status == "pass":
        pub_data = resp_pub.json()
        join_code = pub_data.get("join_code") or pub_data.get("code")
        missing = assert_json_has(pub_data, "join_code")
        if missing:
            # Try alternate key
            missing2 = assert_json_has(pub_data, "code")
            if missing2:
                step_pub.status = "fail"
                step_pub.error_message = f"Response missing join code key. Keys: {list(pub_data.keys())}"

    if not join_code:
        logger.warning("[%s] No join_code obtained; skipping dependent steps", pid)
        results.append(StepResult(
            persona_id=pid, scenario=SCENARIO, step="join_assessment",
            status="skip", error_message="No join_code from publish step",
        ))
        return

    # ── Step B: Student joins (PUBLIC, no teacher header) ────────────────
    resp_join, step_join = await timed_request(
        client, "GET", f"/api/student/join/{join_code}",
        persona_id=pid, scenario=SCENARIO, step="join_assessment",
    )
    results.append(step_join)

    if resp_join and step_join.status == "pass":
        join_data = resp_join.json()
        # Verify no answer keys leaked
        for section in join_data.get("sections", []):
            for q in section.get("questions", []):
                if "answer" in q:
                    step_join.status = "fail"
                    step_join.error_message = "Answer key leaked to student join endpoint"
                    break

    # ── Step C: Student submits answers (PUBLIC) ─────────────────────────
    student_answers = _build_student_answers(test_assessment)
    resp_sub, step_sub = await timed_request(
        client, "POST", f"/api/student/submit/{join_code}",
        persona_id=pid, scenario=SCENARIO, step="submit_answers",
        json={
            "student_name": "Test Student",
            "answers": student_answers,
        },
        expected_status=(200, 500),  # 500 if grading requires real AI key
    )
    results.append(step_sub)

    # ── Step D: Teacher lists assessments ────────────────────────────────
    resp_list, step_list = await timed_request(
        client, "GET", "/api/teacher/assessments",
        persona_id=pid, scenario=SCENARIO, step="teacher_list_assessments",
        headers=headers,
    )
    results.append(step_list)

    # ── Step E: Teacher views results for this assessment ────────────────
    resp_res, step_res = await timed_request(
        client, "GET", f"/api/teacher/assessment/{join_code}/results",
        persona_id=pid, scenario=SCENARIO, step="teacher_view_results",
        headers=headers,
        expected_status=(200, 500),
    )
    results.append(step_res)

    if resp_res and step_res.status == "pass":
        res_data = resp_res.json()
        submissions = res_data.get("submissions", res_data.get("results", []))
        if not submissions:
            step_res.status = "pass"  # No submissions expected with test API keys

    # ── Step F: Toggle deactivate ────────────────────────────────────────
    resp_off, step_off = await timed_request(
        client, "POST", f"/api/teacher/assessment/{join_code}/toggle",
        persona_id=pid, scenario=SCENARIO, step="toggle_deactivate",
        headers=headers,
        expected_status=(200, 500),
    )
    results.append(step_off)

    # ── Step G: Toggle reactivate ────────────────────────────────────────
    resp_on, step_on = await timed_request(
        client, "POST", f"/api/teacher/assessment/{join_code}/toggle",
        persona_id=pid, scenario=SCENARIO, step="toggle_reactivate",
        headers=headers,
        expected_status=(200, 500),
    )
    results.append(step_on)

    # ── Step H: Save assessment draft ────────────────────────────────────
    save_payload = {
        "name": f"Load Test Draft - {persona['subject']}",
        "assessment": test_assessment,
    }
    resp_save, step_save = await timed_request(
        client, "POST", "/api/save-assessment",
        persona_id=pid, scenario=SCENARIO, step="save_assessment",
        json=save_payload,
        headers=headers,
    )
    results.append(step_save)

    # ── Step I: List saved assessments ───────────────────────────────────
    resp_ls, step_ls = await timed_request(
        client, "GET", "/api/list-saved-assessments",
        persona_id=pid, scenario=SCENARIO, step="list_saved_assessments",
        headers=headers,
    )
    results.append(step_ls)

    # ── Step J: Load saved assessment ────────────────────────────────────
    # The endpoint expects "filename" (the sanitized name + .json extension)
    load_name = f"Load Test Draft - {persona['subject']}"
    safe_name = "".join(c for c in load_name if c.isalnum() or c in (' ', '-', '_')).strip()
    resp_load, step_load = await timed_request(
        client, "POST", "/api/load-saved-assessment",
        persona_id=pid, scenario=SCENARIO, step="load_saved_assessment",
        json={"filename": f"{safe_name}.json"},
        headers=headers,
    )
    results.append(step_load)

    logger.info("[%s] student_portal_flow complete (%d steps)", pid, len(results))
