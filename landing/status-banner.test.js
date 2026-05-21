// Tests for the status-banner pure logic. Run with `node --test landing/status-banner.test.js`.
// No test framework dependency — uses Node 20+ built-in node:test runner.

const test = require('node:test');
const assert = require('node:assert/strict');
const { shouldShowBanner } = require('./status-banner.js');

test('returns false when top-level operational, all monitors operational, no incidents', () => {
  const json = {
    status: 'operational',
    monitors: [{ name: 'app', status: 'operational' }],
    incidents: [],
  };
  assert.equal(shouldShowBanner(json), false);
});

test('returns true when top-level status is degraded', () => {
  const json = {
    status: 'degraded',
    monitors: [{ name: 'app', status: 'operational' }],
    incidents: [],
  };
  assert.equal(shouldShowBanner(json), true);
});

test('returns true when top-level status is partial_outage', () => {
  const json = {
    status: 'partial_outage',
    monitors: [{ name: 'app', status: 'down' }],
    incidents: [],
  };
  assert.equal(shouldShowBanner(json), true);
});

test('returns true when top-level status is major_outage', () => {
  const json = {
    status: 'major_outage',
    monitors: [{ name: 'app', status: 'down' }],
    incidents: [{ id: '1', name: 'Outage', status: 'investigating' }],
  };
  assert.equal(shouldShowBanner(json), true);
});

test('returns true when any monitor is degraded (even if top-level says operational)', () => {
  const json = {
    status: 'operational',
    monitors: [
      { name: 'app', status: 'operational' },
      { name: 'api', status: 'degraded' },
    ],
    incidents: [],
  };
  assert.equal(shouldShowBanner(json), true);
});

test('returns true on incident-active-with-monitor-operational (scheduled maintenance window or delayed monitor pickup)', () => {
  const json = {
    status: 'operational',
    monitors: [{ name: 'app', status: 'operational' }],
    incidents: [{ id: '1', name: 'Maintenance', status: 'monitoring' }],
  };
  assert.equal(shouldShowBanner(json), true);
});

test('returns true for incidents with status investigating', () => {
  const json = {
    status: 'operational',
    monitors: [{ name: 'app', status: 'operational' }],
    incidents: [{ id: '1', status: 'investigating' }],
  };
  assert.equal(shouldShowBanner(json), true);
});

test('returns true for incidents with status identified', () => {
  const json = {
    status: 'operational',
    monitors: [{ name: 'app', status: 'operational' }],
    incidents: [{ id: '1', status: 'identified' }],
  };
  assert.equal(shouldShowBanner(json), true);
});

test('returns false when only resolved incidents are present', () => {
  const json = {
    status: 'operational',
    monitors: [{ name: 'app', status: 'operational' }],
    incidents: [{ id: '1', status: 'resolved' }],
  };
  assert.equal(shouldShowBanner(json), false);
});

test('returns false (fails-open) when input is null', () => {
  assert.equal(shouldShowBanner(null), false);
});

test('returns false (fails-open) when input is undefined', () => {
  assert.equal(shouldShowBanner(undefined), false);
});

test('returns false (fails-open) when input is not an object', () => {
  assert.equal(shouldShowBanner('not json'), false);
  assert.equal(shouldShowBanner(42), false);
  assert.equal(shouldShowBanner([]), false);
});

test('returns false (fails-open) when input is missing all expected fields', () => {
  assert.equal(shouldShowBanner({}), false);
});

test('handles missing monitors array (treats as no-monitor signal)', () => {
  const json = { status: 'operational', incidents: [] };
  assert.equal(shouldShowBanner(json), false);
});

test('handles missing incidents array (treats as no-incident signal)', () => {
  const json = { status: 'operational', monitors: [{ status: 'operational' }] };
  assert.equal(shouldShowBanner(json), false);
});

test('handles monitor entries with missing status field (treats as operational)', () => {
  const json = {
    status: 'operational',
    monitors: [{ name: 'app' }],
    incidents: [],
  };
  assert.equal(shouldShowBanner(json), false);
});
