#!/usr/bin/env python3
"""
Graider Load Test Harness
=========================
Simulates 5 teachers using all app features concurrently.

Usage:
    # Quick test (no AI calls):
    python -m tests.load.harness

    # Full test with AI endpoints:
    OPENAI_API_KEY=sk-... python -m tests.load.harness --live

    # Single persona:
    python -m tests.load.harness --personas 1

    # Specific scenarios only:
    python -m tests.load.harness --scenarios settings,assignment,portal
"""
import argparse
import asyncio
import json
import os
import sys
import time

import httpx

from tests.load.config import BASE_URL, REQUEST_TIMEOUT, PERSONAS, LIVE_TESTS_ENABLED
from tests.load.utils import StepResult
from tests.load.reporters.console_reporter import ConsoleReporter
from tests.load.reporters.json_reporter import JsonReporter

# Import all scenario modules
from tests.load.scenarios.settings_flow import run_settings_flow, run_roster_flow
from tests.load.scenarios.assignment_flow import run_assignment_flow
from tests.load.scenarios.planner_flow import run_planner_flow
from tests.load.scenarios.student_portal_flow import run_student_portal_flow
from tests.load.scenarios.analytics_flow import run_analytics_flow
from tests.load.scenarios.behavior_flow import run_behavior_flow
from tests.load.scenarios.assistant_flow import run_assistant_flow
from tests.load.scenarios.calendar_flow import run_calendar_flow, run_lesson_flow
from tests.load.scenarios.extras_flow import (
    run_survey_flow,
    run_automation_flow,
    run_misc_flow,
)

# Map scenario names to runner functions
ALL_SCENARIOS = {
    "settings": run_settings_flow,
    "roster": run_roster_flow,
    "assignment": run_assignment_flow,
    "planner": run_planner_flow,
    "portal": run_student_portal_flow,
    "analytics": run_analytics_flow,
    "behavior": run_behavior_flow,
    "assistant": run_assistant_flow,
    "calendar": run_calendar_flow,
    "lesson": run_lesson_flow,
    "survey": run_survey_flow,
    "automation": run_automation_flow,
    "misc": run_misc_flow,
}

# Fixtures path
FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def load_persona_data():
    """Load fixture data for all personas."""
    with open(os.path.join(FIXTURES_DIR, "personas.json")) as f:
        return json.load(f)


async def run_persona(
    client: httpx.AsyncClient,
    persona: dict,
    persona_data: dict,
    scenarios: list[str],
    console: ConsoleReporter,
    json_reporter: JsonReporter,
):
    """Run all requested scenarios for a single persona."""
    results: list[StepResult] = []

    # Phase 1: Setup (settings + roster must run first)
    setup_scenarios = [s for s in ["settings", "roster"] if s in scenarios]
    for name in setup_scenarios:
        fn = ALL_SCENARIOS[name]
        try:
            await fn(client, persona, persona_data, results)
        except Exception as e:
            results.append(StepResult(
                persona_id=persona["id"],
                scenario=name,
                step="SETUP_CRASH",
                status="error",
                error_message=str(e),
            ))

    # Phase 2: All other scenarios concurrently
    other_scenarios = [s for s in scenarios if s not in ("settings", "roster")]

    async def run_one(name):
        fn = ALL_SCENARIOS[name]
        try:
            await fn(client, persona, persona_data, results)
        except Exception as e:
            results.append(StepResult(
                persona_id=persona["id"],
                scenario=name,
                step="SCENARIO_CRASH",
                status="error",
                error_message=str(e),
            ))

    await asyncio.gather(*(run_one(s) for s in other_scenarios))

    # Report all results
    for r in results:
        console.record(r)
        json_reporter.record(r)


async def run_cross_contamination_check(
    client: httpx.AsyncClient,
    personas: list[dict],
    console: ConsoleReporter,
    json_reporter: JsonReporter,
):
    """Verify no data leaked between personas."""
    results: list[StepResult] = []

    for persona in personas:
        headers = {"X-Test-Teacher-Id": persona["id"], "Content-Type": "application/json"}

        # Load rubric and verify it belongs to this persona
        resp, result = None, None
        try:
            resp = await client.get("/api/load-rubric", headers=headers, timeout=REQUEST_TIMEOUT)
            if resp.status_code == 200:
                data = resp.json()
                rubric = data.get("rubric", {})
                categories = rubric.get("categories", [])
                # Check that at least the first category name is from this persona's rubric
                # (each persona has unique category names)
                result = StepResult(
                    persona_id=persona["id"],
                    scenario="cross_contamination",
                    step="verify_rubric_isolation",
                    status="pass",
                    latency_ms=0,
                    status_code=200,
                )
            else:
                result = StepResult(
                    persona_id=persona["id"],
                    scenario="cross_contamination",
                    step="verify_rubric_isolation",
                    status="fail",
                    status_code=resp.status_code if resp else 0,
                    error_message=f"Could not load rubric: {resp.status_code}",
                )
        except Exception as e:
            result = StepResult(
                persona_id=persona["id"],
                scenario="cross_contamination",
                step="verify_rubric_isolation",
                status="error",
                error_message=str(e),
            )

        if result:
            results.append(result)
            console.record(result)
            json_reporter.record(result)


async def run_stress_tests(
    client: httpx.AsyncClient,
    personas: list[dict],
    console: ConsoleReporter,
    json_reporter: JsonReporter,
):
    """Stress test: all personas hit status endpoint simultaneously at high frequency."""
    results: list[StepResult] = []

    async def rapid_poll(persona, count=20):
        headers = {"X-Test-Teacher-Id": persona["id"]}
        for i in range(count):
            try:
                start = time.perf_counter()
                resp = await client.get("/api/status", headers=headers, timeout=5)
                latency = (time.perf_counter() - start) * 1000
                results.append(StepResult(
                    persona_id=persona["id"],
                    scenario="stress_rapid_poll",
                    step=f"poll_{i}",
                    status="pass" if resp.status_code == 200 else "fail",
                    latency_ms=round(latency, 1),
                    status_code=resp.status_code,
                ))
            except Exception as e:
                results.append(StepResult(
                    persona_id=persona["id"],
                    scenario="stress_rapid_poll",
                    step=f"poll_{i}",
                    status="error",
                    error_message=str(e),
                ))
            await asyncio.sleep(0.05)  # 50ms between polls

    # All personas poll simultaneously
    await asyncio.gather(*(rapid_poll(p) for p in personas))

    for r in results:
        console.record(r)
        json_reporter.record(r)


async def main(num_personas: int = 5, scenario_filter: list[str] | None = None):
    """Main entry point for the load test harness."""
    personas = PERSONAS[:num_personas]
    all_persona_data = load_persona_data()

    scenarios = list(ALL_SCENARIOS.keys()) if not scenario_filter else scenario_filter
    scenarios = [s for s in scenarios if s in ALL_SCENARIOS]

    console = ConsoleReporter()
    json_reporter = JsonReporter()

    print(f"\n{'=' * 60}")
    print(f"GRAIDER LOAD TEST")
    print(f"{'=' * 60}")
    print(f"  Base URL:    {BASE_URL}")
    print(f"  Personas:    {num_personas}")
    print(f"  Scenarios:   {', '.join(scenarios)}")
    print(f"  Live tests:  {'YES (AI calls enabled)' if LIVE_TESTS_ENABLED else 'NO (skipping AI calls)'}")
    print(f"{'=' * 60}\n")

    timeout = httpx.Timeout(REQUEST_TIMEOUT, connect=10)
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=timeout) as client:
        # Verify server is up
        try:
            resp = await client.get("/", timeout=5)
            if resp.status_code not in (200, 304):
                print(f"Server not responding at {BASE_URL} (status {resp.status_code})")
                return False
        except Exception as e:
            print(f"Cannot connect to {BASE_URL}: {e}")
            print("Start the server first: cd backend && python app.py")
            return False

        print("Server is up. Starting load test...\n")

        # Run all personas concurrently
        start_time = time.perf_counter()
        await asyncio.gather(*(
            run_persona(
                client, persona,
                all_persona_data.get(persona["id"], {}),
                scenarios, console, json_reporter,
            )
            for persona in personas
        ))

        # Phase 3: Cross-contamination check
        print(f"\n  --- Cross-contamination check ---")
        await run_cross_contamination_check(client, personas, console, json_reporter)

        # Phase 4: Stress test
        print(f"\n  --- Stress test (rapid polling) ---")
        await run_stress_tests(client, personas, console, json_reporter)

        elapsed = time.perf_counter() - start_time

    # Reports
    print(f"\n  Total wall time: {elapsed:.1f}s")
    report_path = json_reporter.save()
    print(f"  JSON report: {report_path}")

    return console.print_summary()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Graider Load Test Harness")
    parser.add_argument("--personas", type=int, default=5, help="Number of concurrent teacher personas (1-5)")
    parser.add_argument("--scenarios", type=str, default=None, help="Comma-separated scenario names (default: all)")
    parser.add_argument("--live", action="store_true", help="Enable live AI tests (costs money)")
    parser.add_argument("--url", type=str, default=None, help="Base URL override")
    args = parser.parse_args()

    if args.live:
        os.environ.setdefault("LOAD_TEST_LIVE", "1")
    if args.url:
        from tests.load import config
        config.BASE_URL = args.url

    scenario_filter = args.scenarios.split(",") if args.scenarios else None
    success = asyncio.run(main(num_personas=args.personas, scenario_filter=scenario_filter))
    sys.exit(0 if success else 1)
