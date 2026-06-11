"""Tests for the /metrics Prometheus endpoint (hardening sprint PR4).

Covers:
- Scrape format: content-type, HELP/TYPE lines, sample lines parse as
  Prometheus text exposition format v0.0.4.
- Counters are monotonic across two scrapes.
- Histogram invariants (bucket counts cumulative, +Inf == _count).
- PII safety: labels use the Flask route RULE (e.g. /api/x/<id>), never
  the concrete path with a real id; unmatched paths collapse to a
  constant label.
- Grading gauges read the real grading state registry.
- Auth posture: open when METRICS_TOKEN unset (matches /healthz);
  requires Bearer token when METRICS_TOKEN is set.
- Wiring: backend.app exposes /metrics and exempts it from the limiter.
"""
import importlib
import re
import sys

import pytest
from flask import Flask

from backend.metrics import register_metrics


# ──────────────────────────────────────────────────────────────────
# Fixtures — a minimal Flask app with the metrics extension
# ──────────────────────────────────────────────────────────────────

@pytest.fixture
def app(monkeypatch):
    monkeypatch.delenv("METRICS_TOKEN", raising=False)
    app = Flask(__name__)
    app.config["TESTING"] = True
    register_metrics(app)

    @app.route("/api/things/<thing_id>")
    def get_thing(thing_id):
        return {"id": thing_id}

    @app.route("/boom")
    def boom():
        raise ValueError("boom")

    return app


@pytest.fixture
def client(app):
    return app.test_client()


def _scrape(client, headers=None):
    resp = client.get("/metrics", headers=headers or {})
    return resp


# ──────────────────────────────────────────────────────────────────
# Scrape format
# ──────────────────────────────────────────────────────────────────

SAMPLE_LINE = re.compile(
    r'^[a-zA-Z_:][a-zA-Z0-9_:]*(\{[a-zA-Z_][a-zA-Z0-9_]*="[^"]*"'
    r'(,[a-zA-Z_][a-zA-Z0-9_]*="[^"]*")*\})? '
    r'[0-9eE+.\-]+(\s+[0-9]+)?$'
)


class TestScrapeFormat:
    def test_content_type_is_prometheus_text(self, client):
        resp = _scrape(client)
        assert resp.status_code == 200
        assert resp.content_type.startswith("text/plain")
        assert "version=0.0.4" in resp.content_type

    def test_every_line_is_help_type_or_sample(self, client):
        client.get("/api/things/42")  # generate one observation
        body = _scrape(client).get_data(as_text=True)
        assert body.endswith("\n"), "exposition must end with a newline"
        for line in body.splitlines():
            if not line:
                continue
            if line.startswith("# HELP ") or line.startswith("# TYPE "):
                continue
            assert SAMPLE_LINE.match(line), f"unparseable sample line: {line!r}"

    def test_help_and_type_present_for_core_families(self, client):
        body = _scrape(client).get_data(as_text=True)
        for family, mtype in [
            ("graider_http_requests_total", "counter"),
            ("graider_http_request_duration_seconds", "histogram"),
            ("graider_grading_runs_active", "gauge"),
            ("graider_grading_files_pending", "gauge"),
            ("graider_grading_states_tracked", "gauge"),
            ("graider_process_threads", "gauge"),
        ]:
            assert f"# HELP {family} " in body, f"missing HELP for {family}"
            assert f"# TYPE {family} {mtype}" in body, f"missing TYPE for {family}"

    def test_help_documents_per_worker_scope(self, client):
        """The per-worker limitation must be visible to scraper operators."""
        body = _scrape(client).get_data(as_text=True)
        assert "per-worker" in body


# ──────────────────────────────────────────────────────────────────
# Counter semantics
# ──────────────────────────────────────────────────────────────────

def _counter_value(body, family, **labels):
    for line in body.splitlines():
        if not line.startswith(family + "{"):
            continue
        if all(f'{k}="{v}"' in line for k, v in labels.items()):
            return float(line.rsplit(" ", 1)[1])
    return None


class TestCounters:
    def test_request_counter_increments_monotonically(self, client):
        client.get("/api/things/1")
        body1 = _scrape(client).get_data(as_text=True)
        v1 = _counter_value(
            body1, "graider_http_requests_total",
            method="GET", endpoint="/api/things/<thing_id>", status="2xx",
        )
        assert v1 == 1.0
        client.get("/api/things/2")
        client.get("/api/things/3")
        body2 = _scrape(client).get_data(as_text=True)
        v2 = _counter_value(
            body2, "graider_http_requests_total",
            method="GET", endpoint="/api/things/<thing_id>", status="2xx",
        )
        assert v2 == 3.0
        assert v2 > v1

    def test_status_label_is_class_not_exact_code(self, client):
        client.get("/api/things/1")
        body = _scrape(client).get_data(as_text=True)
        assert 'status="2xx"' in body
        assert 'status="200"' not in body

    def test_5xx_responses_are_counted(self, app, client):
        app.config["PROPAGATE_EXCEPTIONS"] = False
        client.get("/boom")
        body = _scrape(client).get_data(as_text=True)
        v = _counter_value(
            body, "graider_http_requests_total",
            method="GET", endpoint="/boom", status="5xx",
        )
        assert v == 1.0

    def test_unknown_method_collapses_to_other(self, client):
        client.open("/api/things/1", method="GET")
        client.open("/metrics", method="BREW")  # bogus verb → 405
        body = _scrape(client).get_data(as_text=True)
        assert 'method="BREW"' not in body


# ──────────────────────────────────────────────────────────────────
# Histogram semantics
# ──────────────────────────────────────────────────────────────────

class TestHistogram:
    def test_buckets_cumulative_and_inf_equals_count(self, client):
        for i in range(5):
            client.get(f"/api/things/{i}")
        body = _scrape(client).get_data(as_text=True)
        buckets = []
        for line in body.splitlines():
            if line.startswith("graider_http_request_duration_seconds_bucket{") \
                    and 'endpoint="/api/things/<thing_id>"' in line:
                buckets.append(float(line.rsplit(" ", 1)[1]))
        assert buckets, "no histogram buckets emitted"
        assert buckets == sorted(buckets), "bucket counts must be cumulative"
        count = _counter_value(
            body, "graider_http_request_duration_seconds_count",
            method="GET", endpoint="/api/things/<thing_id>",
        )
        assert count == 5.0
        assert buckets[-1] == count, "+Inf bucket must equal _count"
        s = _counter_value(
            body, "graider_http_request_duration_seconds_sum",
            method="GET", endpoint="/api/things/<thing_id>",
        )
        assert s is not None and s >= 0.0


# ──────────────────────────────────────────────────────────────────
# PII safety
# ──────────────────────────────────────────────────────────────────

class TestNoPiiInLabels:
    def test_endpoint_label_is_route_rule_not_concrete_path(self, client):
        client.get("/api/things/student-uuid-12345")
        body = _scrape(client).get_data(as_text=True)
        assert "student-uuid-12345" not in body
        assert 'endpoint="/api/things/<thing_id>"' in body

    def test_unmatched_404_path_never_appears_in_labels(self, client):
        client.get("/api/secret/jane.doe@school.edu/report.docx")
        body = _scrape(client).get_data(as_text=True)
        assert "jane.doe" not in body
        assert "report.docx" not in body
        assert 'endpoint="unmatched"' in body


# ──────────────────────────────────────────────────────────────────
# Grading gauges read real state
# ──────────────────────────────────────────────────────────────────

class TestGradingGauges:
    def test_gauges_reflect_grading_state_registry(self, client, monkeypatch):
        from backend.grading import state as gstate
        fake_states = {
            "t1": {"is_running": True, "progress": 3, "total": 10},
            "t2": {"is_running": False, "progress": 0, "total": 0},
            "t3": {"is_running": True, "progress": 9, "total": 12},
        }
        monkeypatch.setattr(gstate, "_grading_states", fake_states)
        body = _scrape(client).get_data(as_text=True)
        assert "graider_grading_runs_active 2" in body
        # pending = (10-3) + (12-9) = 10
        assert "graider_grading_files_pending 10" in body
        assert "graider_grading_states_tracked 3" in body

    def test_process_threads_gauge_positive(self, client):
        body = _scrape(client).get_data(as_text=True)
        m = re.search(r"^graider_process_threads (\d+)", body, re.M)
        assert m and int(m.group(1)) >= 1


# ──────────────────────────────────────────────────────────────────
# Auth posture
# ──────────────────────────────────────────────────────────────────

class TestAuthPosture:
    def test_open_when_metrics_token_unset(self, client):
        assert _scrape(client).status_code == 200

    def test_401_without_token_when_metrics_token_set(self, monkeypatch):
        monkeypatch.setenv("METRICS_TOKEN", "s3cret")
        app = Flask(__name__)
        app.config["TESTING"] = True
        register_metrics(app)
        c = app.test_client()
        assert c.get("/metrics").status_code == 401
        assert c.get(
            "/metrics", headers={"Authorization": "Bearer wrong"}
        ).status_code == 401

    def test_200_with_correct_bearer_when_token_set(self, monkeypatch):
        monkeypatch.setenv("METRICS_TOKEN", "s3cret")
        app = Flask(__name__)
        app.config["TESTING"] = True
        register_metrics(app)
        c = app.test_client()
        resp = c.get("/metrics", headers={"Authorization": "Bearer s3cret"})
        assert resp.status_code == 200

    def test_metrics_response_carries_no_session_cookie(self, client):
        resp = _scrape(client)
        assert "Set-Cookie" not in resp.headers


# ──────────────────────────────────────────────────────────────────
# Idempotence
# ──────────────────────────────────────────────────────────────────

def test_register_metrics_is_idempotent():
    app = Flask(__name__)
    register_metrics(app)
    register_metrics(app)  # must not raise route-overwrite AssertionError


# ──────────────────────────────────────────────────────────────────
# Wiring into the real backend app
# ──────────────────────────────────────────────────────────────────

def _import_backend_app():
    """Import backend.app freshly (mirrors test_app_boot pattern)."""
    sys.path.insert(0, "backend")
    try:
        import app as backend_app
        importlib.reload(backend_app)
        return backend_app
    finally:
        if "backend" in sys.path:
            sys.path.remove("backend")


class TestBackendAppWiring:
    def test_backend_app_exposes_metrics_route(self):
        backend_app = _import_backend_app()
        rules = {r.rule for r in backend_app.app.url_map.iter_rules()}
        assert "/metrics" in rules

    def test_metrics_scrape_on_real_app(self, monkeypatch):
        monkeypatch.delenv("METRICS_TOKEN", raising=False)
        backend_app = _import_backend_app()
        c = backend_app.app.test_client()
        resp = c.get("/metrics")
        assert resp.status_code == 200
        assert "graider_http_requests_total" in resp.get_data(as_text=True)

    def test_metrics_view_is_limiter_exempt(self):
        """A Redis blip must not 500 the scrape — same posture as /healthz."""
        backend_app = _import_backend_app()
        from backend.extensions import limiter
        from flask_limiter.constants import ExemptionScope

        # Resolve the endpoint name for the /metrics rule, then ask the
        # limiter for its exemption scope (same lookup flask-limiter does
        # per-request in 4.x).
        endpoint = next(
            r.endpoint
            for r in backend_app.app.url_map.iter_rules()
            if r.rule == "/metrics"
        )
        scope = limiter.limit_manager.exemption_scope(
            backend_app.app, endpoint, None
        )
        assert scope != ExemptionScope.NONE, (
            "/metrics view is not exempt from flask-limiter"
        )
