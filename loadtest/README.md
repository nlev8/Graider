# Graider Load Tests

Tier 3 #10 from the district-readiness plan. The goal is to surface latency cliffs, connection-pool exhaustion, and AI-rate-limit cascades **before** a real district hits them on a test day.

## Layout

```
loadtest/
├── README.md             # this file
├── scenarios/
│   └── mass-submit.js    # N concurrent students submitting to one assessment
└── lib/
    └── http.js           # helpers (base URL, headers, response checks)
```

Scenarios are k6 scripts. Each one is self-contained (no shared state) so you can run them individually with sane defaults or compose them via the k6 `executor: scenarios` block in a future PR.

## Prerequisites

Install k6 (one-time):

```bash
# macOS
brew install k6

# Linux (Debian/Ubuntu)
sudo gpg -k && sudo gpg --no-default-keyring --keyring /usr/share/keyrings/k6-archive-keyring.gpg --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" | sudo tee /etc/apt/sources.list.d/k6.list
sudo apt-get update && sudo apt-get install k6
```

Or use the official Docker image — the run instructions below cover both.

## Running scenarios

> **Never run load tests against production.** All scenarios default to `BASE_URL=http://localhost:5000`. Override via env var to point at staging once a staging environment exists (Tier 2 follow-up — see `docs/disaster-recovery.md` for context).

### Smoke mode (1 VU × 1 iteration)

Verifies the script runs end-to-end without actually loading anything. Useful as a CI gate or as a quick "did I break it" check after editing.

```bash
cd loadtest
k6 run --vus 1 --iterations 1 scenarios/mass-submit.js
```

### Full scenario

```bash
# 50 virtual users, ramping up over 30s, holding for 2 min
BASE_URL=https://staging.graider.live \
JOIN_CODE=ABC123 \
k6 run scenarios/mass-submit.js
```

## Scenarios

### `mass-submit.js`

**What it simulates:** 50 students concurrently submit to the same published assessment via the join-code portal. This is the worst-case "8am bell rings, everyone hits enter" pattern.

**Inputs (env vars):**
- `BASE_URL` — required for non-localhost
- `JOIN_CODE` — required, 6-character code from a published assessment

**Thresholds:**
- p95 response time < 1.5s
- 5xx error rate < 1%

**What it does NOT cover (yet):**
- Authenticated path (`/api/student/class-submit/<id>`) — requires session token plumbing.
- Mass-grade scenario — gated on the Celery worker queue, separate concerns.
- Roster sync — separate scenario for a future PR.

## Future work

When staging exists, add:
- `mass-grade.js` — concurrent grading thread invocations
- `mass-roster-sync.js` — concurrent CSV upload + Supabase upsert
- A k6 dashboard / Grafana export for trend tracking

Until then, this scaffolding is the floor — a single working scenario you can run by hand to spot-check before a district pilot.
