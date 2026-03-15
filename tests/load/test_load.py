"""
Pytest integration for the Graider load test harness.

Run:
    # All non-AI tests against running server:
    pytest tests/load/test_load.py -v

    # With AI endpoints (costs money):
    pytest tests/load/test_load.py -v -m live

    # Quick smoke (1 persona, core scenarios):
    pytest tests/load/test_load.py::test_single_persona_smoke -v
"""
import asyncio
import json
import os

import pytest
import httpx

from tests.load.config import BASE_URL, REQUEST_TIMEOUT, PERSONAS, LIVE_TESTS_ENABLED
from tests.load.utils import StepResult, make_headers
from tests.load.reporters.console_reporter import ConsoleReporter
from tests.load.reporters.json_reporter import JsonReporter

# Scenario imports
from tests.load.scenarios.settings_flow import run_settings_flow, run_roster_flow
from tests.load.scenarios.assignment_flow import run_assignment_flow
from tests.load.scenarios.planner_flow import run_planner_flow
from tests.load.scenarios.student_portal_flow import run_student_portal_flow
from tests.load.scenarios.analytics_flow import run_analytics_flow
from tests.load.scenarios.behavior_flow import run_behavior_flow
from tests.load.scenarios.assistant_flow import run_assistant_flow
from tests.load.scenarios.calendar_flow import run_calendar_flow, run_lesson_flow
from tests.load.scenarios.extras_flow import run_survey_flow, run_automation_flow, run_misc_flow

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def _load_persona_data():
    with open(os.path.join(FIXTURES_DIR, "personas.json")) as f:
        return json.load(f)


def _server_available():
    """Check if the dev server is running."""
    try:
        import urllib.request
        resp = urllib.request.urlopen(BASE_URL, timeout=3)
        return resp.status == 200
    except Exception:
        return False


# Skip all tests if server is not running
pytestmark = pytest.mark.skipif(
    not _server_available(),
    reason=f"Dev server not running at {BASE_URL}. Start with: cd backend && python app.py"
)


@pytest.fixture(scope="module")
def persona_data():
    return _load_persona_data()


@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ──────────────────────────────────────────────
# SMOKE TEST: Single persona, all scenarios
# ──────────────────────────────────────────────

def test_single_persona_smoke(persona_data):
    """Run all non-AI scenarios for a single persona."""
    persona = PERSONAS[0]
    pdata = persona_data.get(persona["id"], {})
    results = []

    async def _run():
        timeout = httpx.Timeout(REQUEST_TIMEOUT, connect=10)
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=timeout) as client:
            await run_settings_flow(client, persona, pdata, results)
            await run_roster_flow(client, persona, pdata, results)
            await run_assignment_flow(client, persona, pdata, results)
            await run_analytics_flow(client, persona, pdata, results)
            await run_behavior_flow(client, persona, pdata, results)
            await run_calendar_flow(client, persona, pdata, results)
            await run_lesson_flow(client, persona, pdata, results)
            await run_misc_flow(client, persona, pdata, results)

    asyncio.run(_run())

    failures = [r for r in results if r.status in ("fail", "error")]
    if failures:
        msg = "\n".join(f"  [{r.scenario}.{r.step}] {r.error_message}" for r in failures)
        pytest.fail(f"{len(failures)} steps failed:\n{msg}")


# ──────────────────────────────────────────────
# CONCURRENT: All 5 personas, all scenarios
# ──────────────────────────────────────────────

def test_concurrent_all_personas(persona_data):
    """Run all non-AI scenarios for all 5 personas concurrently."""
    results = []
    console = ConsoleReporter()

    async def _run():
        timeout = httpx.Timeout(REQUEST_TIMEOUT, connect=10)
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=timeout) as client:
            tasks = []
            for persona in PERSONAS:
                pdata = persona_data.get(persona["id"], {})

                async def persona_flow(p=persona, pd=pdata):
                    r = []
                    await run_settings_flow(client, p, pd, r)
                    await run_roster_flow(client, p, pd, r)
                    # Run remaining scenarios concurrently within each persona
                    await asyncio.gather(
                        run_assignment_flow(client, p, pd, r),
                        run_analytics_flow(client, p, pd, r),
                        run_behavior_flow(client, p, pd, r),
                        run_calendar_flow(client, p, pd, r),
                        run_lesson_flow(client, p, pd, r),
                        run_student_portal_flow(client, p, pd, r),
                        run_misc_flow(client, p, pd, r),
                        run_survey_flow(client, p, pd, r),
                        run_automation_flow(client, p, pd, r),
                    )
                    results.extend(r)

                tasks.append(persona_flow())
            await asyncio.gather(*tasks)

    asyncio.run(_run())

    failures = [r for r in results if r.status in ("fail", "error")]
    total = len(results)
    passed = sum(1 for r in results if r.status == "pass")
    print(f"\n  {passed}/{total} steps passed across {len(PERSONAS)} personas")

    if failures:
        msg = "\n".join(
            f"  [{r.persona_id}] {r.scenario}.{r.step}: {r.error_message}"
            for r in failures[:20]
        )
        extra = f"\n  ... and {len(failures) - 20} more" if len(failures) > 20 else ""
        pytest.fail(f"{len(failures)} steps failed:\n{msg}{extra}")


# ──────────────────────────────────────────────
# STUDENT PORTAL: Full lifecycle concurrent
# ──────────────────────────────────────────────

def test_student_portal_concurrent(persona_data):
    """All 5 teachers publish + students submit concurrently."""
    results = []

    async def _run():
        timeout = httpx.Timeout(REQUEST_TIMEOUT, connect=10)
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=timeout) as client:
            tasks = []
            for persona in PERSONAS:
                pdata = persona_data.get(persona["id"], {})
                tasks.append(run_student_portal_flow(client, persona, pdata, results))
            await asyncio.gather(*tasks)

    asyncio.run(_run())

    failures = [r for r in results if r.status in ("fail", "error")]
    if failures:
        msg = "\n".join(f"  [{r.persona_id}] {r.scenario}.{r.step}: {r.error_message}" for r in failures)
        pytest.fail(f"{len(failures)} portal steps failed:\n{msg}")


# ──────────────────────────────────────────────
# STRESS: Rapid concurrent polling
# ──────────────────────────────────────────────

def test_stress_rapid_polling(persona_data):
    """All personas poll /api/status at high frequency simultaneously."""
    results = []

    async def rapid_poll(client, persona, count=30):
        headers = make_headers(persona)
        for i in range(count):
            try:
                resp = await client.get("/api/status", headers=headers, timeout=5)
                results.append(StepResult(
                    persona_id=persona["id"],
                    scenario="stress",
                    step=f"poll_{i}",
                    status="pass" if resp.status_code == 200 else "fail",
                    status_code=resp.status_code,
                ))
            except Exception as e:
                results.append(StepResult(
                    persona_id=persona["id"],
                    scenario="stress",
                    step=f"poll_{i}",
                    status="error",
                    error_message=str(e),
                ))
            await asyncio.sleep(0.03)

    async def _run():
        timeout = httpx.Timeout(10, connect=5)
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=timeout) as client:
            await asyncio.gather(*(rapid_poll(client, p) for p in PERSONAS))

    asyncio.run(_run())

    errors = [r for r in results if r.status in ("fail", "error")]
    error_rate = len(errors) / len(results) * 100 if results else 0
    print(f"\n  {len(results)} polls, {len(errors)} failures ({error_rate:.1f}% error rate)")
    # Allow up to 5% error rate under stress
    assert error_rate < 5, f"Error rate {error_rate:.1f}% exceeds 5% threshold"


# ──────────────────────────────────────────────
# LIVE AI TESTS (cost money, gated)
# ──────────────────────────────────────────────

@pytest.mark.live
def test_planner_ai_generation(persona_data):
    """Test AI lesson plan + assessment generation (costs ~$0.10)."""
    if not LIVE_TESTS_ENABLED:
        pytest.skip("OPENAI_API_KEY not set")

    persona = PERSONAS[0]
    pdata = persona_data.get(persona["id"], {})
    results = []

    async def _run():
        timeout = httpx.Timeout(120, connect=10)
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=timeout) as client:
            await run_settings_flow(client, persona, pdata, results)
            await run_planner_flow(client, persona, pdata, results)

    asyncio.run(_run())

    failures = [r for r in results if r.status in ("fail", "error")]
    if failures:
        msg = "\n".join(f"  {r.scenario}.{r.step}: {r.error_message}" for r in failures)
        pytest.fail(f"{len(failures)} planner steps failed:\n{msg}")


@pytest.mark.live
def test_assistant_ai_chat(persona_data):
    """Test AI assistant chat (costs ~$0.05)."""
    if not LIVE_TESTS_ENABLED:
        pytest.skip("OPENAI_API_KEY not set")

    persona = PERSONAS[0]
    pdata = persona_data.get(persona["id"], {})
    results = []

    async def _run():
        timeout = httpx.Timeout(60, connect=10)
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=timeout) as client:
            await run_assistant_flow(client, persona, pdata, results)

    asyncio.run(_run())

    failures = [r for r in results if r.status in ("fail", "error")]
    if failures:
        msg = "\n".join(f"  {r.scenario}.{r.step}: {r.error_message}" for r in failures)
        pytest.fail(f"{len(failures)} assistant steps failed:\n{msg}")
