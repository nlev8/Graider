// Mass concurrent submission via the join-code portal.
//
// Simulates the worst-case "8am bell rings, all 50 students hit Enter at
// once" traffic pattern that a district pilot can produce.
//
// Run:
//   BASE_URL=https://staging.graider.live JOIN_CODE=ABC123 k6 run scenarios/mass-submit.js
//
// Smoke mode (CI / quick check):
//   k6 run --vus 1 --iterations 1 scenarios/mass-submit.js

import http from 'k6/http';
import { sleep } from 'k6';
import { BASE_URL, JSON_HEADERS, checkResponse, requireEnv } from '../lib/http.js';

export const options = {
  // Ramp up to 50 VUs over 30s, hold for 2 minutes, ramp down over 30s.
  // Tweak via CLI: `k6 run --vus 100 --duration 5m scenarios/mass-submit.js`
  // (CLI overrides win over `stages`).
  stages: [
    { duration: '30s', target: 50 },
    { duration: '2m', target: 50 },
    { duration: '30s', target: 0 },
  ],
  thresholds: {
    'http_req_duration{name:fetch_assessment}': ['p(95)<1500'],
    'http_req_duration{name:submit}': ['p(95)<1500'],
    http_req_failed: ['rate<0.01'], // <1% 5xx
  },
};

export function setup() {
  // Read env vars once and pass via setup data so per-iteration code
  // doesn't have to repeat validation.
  return {
    joinCode: requireEnv('JOIN_CODE'),
  };
}

export default function (data) {
  // 1. Fetch the assessment by join code (what the StudentPortal does on load).
  const fetchRes = http.get(`${BASE_URL}/api/student/join/${data.joinCode}`, {
    tags: { name: 'fetch_assessment' },
  });
  checkResponse(fetchRes, 'fetch_assessment');

  if (fetchRes.status !== 200) {
    // If we can't even fetch the assessment, no point trying to submit.
    return;
  }

  let payload;
  try {
    payload = fetchRes.json();
  } catch {
    return;
  }

  const questions = (payload && payload.content && payload.content.questions) || [];

  // 2. Build a minimal valid submission body. We don't try to answer
  //    correctly — load test cares about throughput / errors, not grade
  //    accuracy. Each VU picks "A" for everything.
  const answers = {};
  for (let i = 0; i < questions.length; i++) {
    const q = questions[i];
    if (!q || q.id == null) continue;
    if (q.type === 'multiple_choice' || q.type === 'matching') {
      answers[q.id] = 'A';
    } else {
      answers[q.id] = 'load test answer';
    }
  }

  const submitBody = JSON.stringify({
    student_name: `LoadTest VU ${__VU} iter ${__ITER}`,
    answers: answers,
  });

  const submitRes = http.post(
    `${BASE_URL}/api/student/submit/${data.joinCode}`,
    submitBody,
    { ...JSON_HEADERS, tags: { name: 'submit' } },
  );
  checkResponse(submitRes, 'submit');

  // Stagger between iterations so we're not pure tight-loop spamming.
  sleep(0.2 + Math.random() * 0.3);
}
