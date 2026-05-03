// Shared helpers for k6 scenarios.
//
// Keep this file tiny — k6 doesn't have npm. If you find yourself wanting
// real npm packages, you've outgrown loadtest/ and need a proper
// load-testing harness (consider k6 with xk6 plugins, or move to artillery).

import { check } from 'k6';

// BASE_URL is set via `BASE_URL=...` env var. Defaults to localhost so
// running scripts without env vars never accidentally hits prod/staging.
export const BASE_URL = __ENV.BASE_URL || 'http://localhost:5000';

// Standard JSON headers for API calls.
export const JSON_HEADERS = {
  headers: { 'Content-Type': 'application/json' },
};

// Wrap a k6 response with the standard "expected status / no 5xx" checks
// so every scenario reports the same shape of failure.
export function checkResponse(res, label) {
  return check(res, {
    [`${label} status is 2xx`]: (r) => r.status >= 200 && r.status < 300,
    [`${label} not 5xx`]: (r) => r.status < 500,
  });
}

// Read a required env var; fail fast at script start if missing.
export function requireEnv(name) {
  const v = __ENV[name];
  if (!v) {
    throw new Error(`Missing required env var: ${name}`);
  }
  return v;
}
