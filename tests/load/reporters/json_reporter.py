"""
JSON reporter — writes machine-readable results to a timestamped file.
"""
import json
import os
from datetime import datetime
from dataclasses import asdict
from collections import defaultdict
from tests.load.utils import StepResult
from tests.load.config import REPORT_DIR


class JsonReporter:
    def __init__(self):
        self.results: list[StepResult] = []

    def record(self, result: StepResult):
        self.results.append(result)

    def save(self) -> str:
        os.makedirs(REPORT_DIR, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = os.path.join(REPORT_DIR, f"load_test_{timestamp}.json")

        # Compute summary stats
        counts = defaultdict(int)
        for r in self.results:
            counts[r.status] += 1

        latencies = [r.latency_ms for r in self.results if r.status == "pass" and r.latency_ms > 0]
        latencies.sort()

        summary = {
            "timestamp": datetime.now().isoformat(),
            "total_steps": len(self.results),
            "passed": counts["pass"],
            "failed": counts["fail"],
            "errors": counts["error"],
            "skipped": counts["skip"],
        }
        if latencies:
            summary["latency_p50_ms"] = latencies[len(latencies) // 2]
            summary["latency_p95_ms"] = latencies[int(len(latencies) * 0.95)]
            summary["latency_p99_ms"] = latencies[int(len(latencies) * 0.99)]

        report = {
            "summary": summary,
            "results": [asdict(r) for r in self.results],
        }

        with open(filepath, "w") as f:
            json.dump(report, f, indent=2)

        return filepath
