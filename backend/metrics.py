"""Prometheus text-format /metrics endpoint (hardening sprint PR4).

Hand-rolled stdlib registry — deliberately NOT prometheus_client:

* No new dependency → no lockfile churn, no pip-audit surface.
* gunicorn runs multiple workers; prometheus_client's answer to that is
  multiprocess mode (PROMETHEUS_MULTIPROC_DIR + lifecycle hooks), which
  is operationally heavier than this anchor needs. This registry is
  **per-worker**: each gunicorn worker keeps its own counters, and a
  scrape is served by whichever worker accepts the connection. That
  limitation is documented in every HELP line so scraper operators see
  it (sum/rate across scrapes still trends correctly; absolute totals
  are per-process). Revisit if we ever need exact cross-worker totals.

Exposed families (Prometheus text exposition format v0.0.4):

* ``graider_http_requests_total{method,endpoint,status}`` — counter.
* ``graider_http_request_duration_seconds{method,endpoint}`` — histogram.
* ``graider_grading_runs_active`` / ``graider_grading_files_pending`` /
  ``graider_grading_states_tracked`` — gauges computed at scrape time
  from the real per-teacher grading state registry in
  ``backend.grading.state`` (the same dicts the SIGTERM handler walks).
* ``graider_process_threads`` — ``threading.active_count()`` (grading +
  portal-grading threads run as plain threads in this process).

PII safety (plan PR4: "metrics endpoint must not leak PII"): the
``endpoint`` label is always the Flask route RULE (e.g.
``/api/students/<id>``), never the concrete request path. Requests that
match no rule (404 probes, scanner noise) collapse to the constant
``unmatched`` — raw attacker-/user-supplied paths never become label
values. ``method`` is bounded to the standard verb set (anything else
collapses to ``OTHER``) so arbitrary verbs can't grow label cardinality.

Auth posture: ``/metrics`` is outside ``/api/`` so the auth hook skips
it, and it is ``limiter.exempt`` — the same posture as ``/healthz`` (a
Redis blip must not 500 the scrape). The payload is aggregate-only
(route rules + counts + durations), which is industry-normal to expose
publicly; for defense-in-depth, setting ``METRICS_TOKEN`` requires
scrapers to send ``Authorization: Bearer <token>`` (constant-time
compare). Unset (the default) keeps the endpoint open.
"""
from __future__ import annotations

import hmac
import logging
import os
import threading
import time
from typing import TYPE_CHECKING, Any

from flask import Response, g, request

if TYPE_CHECKING:
    from flask import Flask

PROMETHEUS_CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"

# Standard HTTP verbs; anything else (BREW, scanner junk) → "OTHER" so
# attacker-supplied methods can't inflate label cardinality.
_KNOWN_METHODS = frozenset(
    {"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"}
)

# Latency buckets (seconds). Upper edge 10s covers the slow-parse tail
# (CLAUDE.md performance notes: large-file parses can run long); +Inf
# is implicit in the exposition.
_BUCKETS = (0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)

_PER_WORKER_NOTE = (
    "(per-worker: each gunicorn worker exposes its own values; a scrape "
    "reports the worker that served it)"
)


def _escape_label_value(value: str) -> str:
    """Escape a label value per the Prometheus text format spec."""
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _format_labels(labels: tuple[tuple[str, str], ...]) -> str:
    if not labels:
        return ""
    inner = ",".join(
        f'{name}="{_escape_label_value(value)}"' for name, value in labels
    )
    return "{" + inner + "}"


class MetricsRegistry:
    """Thread-safe per-process registry for request counters/histograms.

    State is per-app-instance (stored in ``app.extensions``) so test
    apps get isolated registries, and per-worker in production (see
    module docstring for the multi-worker limitation).
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # (method, endpoint, status_class) -> count
        self._requests: dict[tuple[str, str, str], int] = {}
        # (method, endpoint) -> {"buckets": [...], "sum": float, "count": int}
        self._durations: dict[tuple[str, str], dict[str, Any]] = {}

    def observe_request(
        self, method: str, endpoint: str, status_code: int, duration_s: float
    ) -> None:
        method = method.upper() if method.upper() in _KNOWN_METHODS else "OTHER"
        status_class = f"{status_code // 100}xx"
        counter_key = (method, endpoint, status_class)
        histo_key = (method, endpoint)
        with self._lock:
            self._requests[counter_key] = self._requests.get(counter_key, 0) + 1
            histo = self._durations.get(histo_key)
            if histo is None:
                histo = {"buckets": [0] * len(_BUCKETS), "sum": 0.0, "count": 0}
                self._durations[histo_key] = histo
            for i, edge in enumerate(_BUCKETS):
                if duration_s <= edge:
                    histo["buckets"][i] += 1
            histo["sum"] += duration_s
            histo["count"] += 1

    def render(self) -> str:
        """Render the full exposition (request metrics + live gauges)."""
        lines: list[str] = []
        with self._lock:
            requests_snapshot = dict(self._requests)
            durations_snapshot = {
                key: {
                    "buckets": list(histo["buckets"]),
                    "sum": histo["sum"],
                    "count": histo["count"],
                }
                for key, histo in self._durations.items()
            }

        lines.append(
            "# HELP graider_http_requests_total Total HTTP requests "
            f"handled {_PER_WORKER_NOTE}."
        )
        lines.append("# TYPE graider_http_requests_total counter")
        for (method, endpoint, status_class), count in sorted(
            requests_snapshot.items()
        ):
            labels = _format_labels(
                (("method", method), ("endpoint", endpoint), ("status", status_class))
            )
            lines.append(f"graider_http_requests_total{labels} {count}")

        lines.append(
            "# HELP graider_http_request_duration_seconds HTTP request "
            f"latency {_PER_WORKER_NOTE}."
        )
        lines.append("# TYPE graider_http_request_duration_seconds histogram")
        for (method, endpoint), histo in sorted(durations_snapshot.items()):
            base = (("method", method), ("endpoint", endpoint))
            for i, edge in enumerate(_BUCKETS):
                labels = _format_labels(base + (("le", repr(edge)),))
                lines.append(
                    "graider_http_request_duration_seconds_bucket"
                    f"{labels} {histo['buckets'][i]}"
                )
            labels = _format_labels(base + (("le", "+Inf"),))
            lines.append(
                "graider_http_request_duration_seconds_bucket"
                f"{labels} {histo['count']}"
            )
            base_labels = _format_labels(base)
            lines.append(
                "graider_http_request_duration_seconds_sum"
                f"{base_labels} {histo['sum']:.6f}"
            )
            lines.append(
                "graider_http_request_duration_seconds_count"
                f"{base_labels} {histo['count']}"
            )

        lines.extend(_render_grading_gauges())
        return "\n".join(lines) + "\n"


def _render_grading_gauges() -> list[str]:
    """Gauges computed at scrape time from real process state.

    Reads ``backend.grading.state._grading_states`` (the per-teacher
    grading state dicts) under ``_states_meta_lock`` — the same
    snapshot pattern ``_handle_sigterm`` in backend/app.py uses.
    Imported lazily so a minimal test app doesn't pull the grading
    stack at registration time.
    """
    from backend.grading import state as grading_state

    with grading_state._states_meta_lock:
        snapshot = list(grading_state._grading_states.values())

    runs_active = 0
    files_pending = 0
    for state in snapshot:
        if state.get("is_running"):
            runs_active += 1
            total = state.get("total", 0) or 0
            progress = state.get("progress", 0) or 0
            files_pending += max(total - progress, 0)

    return [
        "# HELP graider_grading_runs_active Teacher grading runs currently "
        f"executing in this process {_PER_WORKER_NOTE}.",
        "# TYPE graider_grading_runs_active gauge",
        f"graider_grading_runs_active {runs_active}",
        "# HELP graider_grading_files_pending Files queued but not yet graded "
        f"across active grading runs {_PER_WORKER_NOTE}.",
        "# TYPE graider_grading_files_pending gauge",
        f"graider_grading_files_pending {files_pending}",
        "# HELP graider_grading_states_tracked Teacher grading-state entries "
        f"held in memory {_PER_WORKER_NOTE}.",
        "# TYPE graider_grading_states_tracked gauge",
        f"graider_grading_states_tracked {len(snapshot)}",
        "# HELP graider_process_threads Live threads in this process, "
        f"including grading threads {_PER_WORKER_NOTE}.",
        "# TYPE graider_process_threads gauge",
        f"graider_process_threads {threading.active_count()}",
    ]


def _endpoint_label() -> str:
    """Route RULE for the matched endpoint, or 'unmatched'.

    NEVER returns the raw request path — concrete paths can embed
    student ids, emails, or file names (PII), and unmatched scanner
    probes are attacker-controlled strings.
    """
    rule = request.url_rule
    return rule.rule if rule is not None else "unmatched"


def register_metrics(app: "Flask") -> None:
    """Register request instrumentation hooks + the /metrics route.

    Idempotent (same guard pattern as backend/app.py's init_app):
    re-registering on the same app would raise Flask's
    view-mapping-overwrite AssertionError.
    """
    if app.extensions.get("graider_metrics") is not None:
        return
    registry = MetricsRegistry()
    app.extensions["graider_metrics"] = registry

    @app.before_request
    def _metrics_start_timer() -> None:
        g._metrics_start_time = time.monotonic()

    @app.after_request
    def _metrics_observe(response: Response) -> Response:
        start = getattr(g, "_metrics_start_time", None)
        duration_s = (time.monotonic() - start) if start is not None else 0.0
        registry.observe_request(
            request.method, _endpoint_label(), response.status_code, duration_s
        )
        return response

    def graider_metrics() -> Response:
        # Optional bearer gate: METRICS_TOKEN set → require it (constant-
        # time compare); unset → open, matching /healthz's public posture.
        expected = os.getenv("METRICS_TOKEN")
        if expected:
            supplied = request.headers.get("Authorization", "")
            if not (
                supplied.startswith("Bearer ")
                and hmac.compare_digest(supplied[7:], expected)
            ):
                return Response(
                    "unauthorized\n", status=401, content_type="text/plain"
                )
        return Response(registry.render(), content_type=PROMETHEUS_CONTENT_TYPE)

    # limiter.exempt: a Redis blip in flask-limiter's storage must not
    # 500 the scrape — same rationale as /healthz. Imported lazily so a
    # bare test app doesn't need the limiter's Redis startup probe.
    try:
        from backend.extensions import limiter

        graider_metrics = limiter.exempt(graider_metrics)
    except Exception as exc:  # pragma: no cover — extensions unavailable in odd harnesses  # noqa: BLE001 — broad catch: error is logged; exemption is best-effort
        logging.getLogger(__name__).warning(
            "flask-limiter unavailable; /metrics registered without "
            "limiter exemption: %s", exc,
        )

    app.add_url_rule("/metrics", endpoint="graider_metrics", view_func=graider_metrics)
