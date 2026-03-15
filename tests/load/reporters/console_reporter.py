"""
Console reporter — real-time colored output during load test execution.
"""
import sys
from collections import defaultdict
from tests.load.utils import StepResult


# ANSI colors
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
DIM = "\033[2m"
RESET = "\033[0m"
BOLD = "\033[1m"

STATUS_COLORS = {
    "pass": GREEN,
    "fail": RED,
    "error": RED,
    "skip": YELLOW,
}


class ConsoleReporter:
    def __init__(self):
        self.results: list[StepResult] = []
        self.counts = defaultdict(int)

    def record(self, result: StepResult):
        self.results.append(result)
        self.counts[result.status] += 1
        color = STATUS_COLORS.get(result.status, RESET)
        icon = {"pass": "+", "fail": "X", "error": "!", "skip": "-"}.get(result.status, "?")
        persona_tag = f"{DIM}[{result.persona_id[-3:]}]{RESET}"
        latency = f"{DIM}{result.latency_ms:>7.0f}ms{RESET}"
        line = f"  {color}[{icon}]{RESET} {persona_tag} {result.scenario}.{result.step} {latency}"
        if result.status in ("fail", "error") and result.error_message:
            line += f"  {RED}{result.error_message[:80]}{RESET}"
        print(line, flush=True)

    def print_summary(self):
        total = len(self.results)
        passed = self.counts["pass"]
        failed = self.counts["fail"]
        errors = self.counts["error"]
        skipped = self.counts["skip"]

        print(f"\n{BOLD}{'=' * 60}{RESET}")
        print(f"{BOLD}LOAD TEST SUMMARY{RESET}")
        print(f"{'=' * 60}")
        print(f"  Total steps:  {total}")
        print(f"  {GREEN}Passed:     {passed}{RESET}")
        if failed:
            print(f"  {RED}Failed:     {failed}{RESET}")
        if errors:
            print(f"  {RED}Errors:     {errors}{RESET}")
        if skipped:
            print(f"  {YELLOW}Skipped:    {skipped}{RESET}")

        # Latency stats
        latencies = [r.latency_ms for r in self.results if r.status == "pass" and r.latency_ms > 0]
        if latencies:
            latencies.sort()
            p50 = latencies[len(latencies) // 2]
            p95 = latencies[int(len(latencies) * 0.95)]
            p99 = latencies[int(len(latencies) * 0.99)]
            print(f"\n  {CYAN}Latency (passing steps):{RESET}")
            print(f"    P50: {p50:.0f}ms  P95: {p95:.0f}ms  P99: {p99:.0f}ms")

        # Failures detail
        failures = [r for r in self.results if r.status in ("fail", "error")]
        if failures:
            print(f"\n  {RED}FAILURES:{RESET}")
            for f in failures:
                print(f"    [{f.persona_id}] {f.scenario}.{f.step}: {f.error_message}")
                if f.response_snippet:
                    snippet = f.response_snippet[:120].replace("\n", " ")
                    print(f"      {DIM}Response: {snippet}{RESET}")

        # Per-persona breakdown
        persona_stats = defaultdict(lambda: defaultdict(int))
        for r in self.results:
            persona_stats[r.persona_id][r.status] += 1
        print(f"\n  {CYAN}Per-persona breakdown:{RESET}")
        for pid, stats in sorted(persona_stats.items()):
            p = stats.get("pass", 0)
            f = stats.get("fail", 0) + stats.get("error", 0)
            s = stats.get("skip", 0)
            status_str = f"{GREEN}{p} pass{RESET}"
            if f:
                status_str += f", {RED}{f} fail{RESET}"
            if s:
                status_str += f", {YELLOW}{s} skip{RESET}"
            print(f"    {pid}: {status_str}")

        print(f"{'=' * 60}\n")
        return failed + errors == 0
