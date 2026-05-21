/* ============================================
   GRAIDER LANDING — STATUS BANNER
   ============================================

   Pulls the BetterStack public status JSON from status.graider.live and
   renders a banner at the top of the page when any of:
   - top-level status != "operational"
   - any monitor status != "operational"
   - any incident status in {"investigating", "identified", "monitoring"}

   Fails-open on any fetch error, parse error, or unexpected shape:
   a "status unknown" banner is worse than no banner during a normal
   page-load with an API hiccup.

   See docs/superpowers/specs/2026-05-21-opsafety-tier1-design.md.
   ============================================ */

const STATUS_URL = 'https://status.graider.live/api/v1/status.json';
const FETCH_TIMEOUT_MS = 3000;
const ACTIVE_INCIDENT_STATES = ['investigating', 'identified', 'monitoring'];

/**
 * Decide whether to show the banner.
 *
 * Fails-open: returns false on any unexpected input shape so the banner
 * does not render when the API is having a hiccup.
 *
 * @param {object} statusJSON - Parsed BetterStack /api/v1/status.json response.
 * @returns {boolean} true to show banner, false otherwise.
 */
function shouldShowBanner(statusJSON) {
  if (!statusJSON || typeof statusJSON !== 'object' || Array.isArray(statusJSON)) {
    return false;
  }

  // Check top-level aggregate status. Banner ON if anything other than
  // explicit "operational".
  if (statusJSON.status && statusJSON.status !== 'operational') {
    return true;
  }

  // Check individual monitors. Banner ON if any monitor reports non-operational.
  const monitors = Array.isArray(statusJSON.monitors) ? statusJSON.monitors : [];
  for (const m of monitors) {
    if (m && m.status && m.status !== 'operational') {
      return true;
    }
  }

  // Check active incidents. Banner ON if any incident is in an active
  // (non-resolved) state.
  const incidents = Array.isArray(statusJSON.incidents) ? statusJSON.incidents : [];
  for (const inc of incidents) {
    if (inc && inc.status && ACTIVE_INCIDENT_STATES.includes(inc.status)) {
      return true;
    }
  }

  return false;
}

// CommonJS export for node:test. The browser-mounting path in Task 2.2
// uses a separate IIFE that does not depend on CommonJS.
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { shouldShowBanner, STATUS_URL, FETCH_TIMEOUT_MS, ACTIVE_INCIDENT_STATES };
}
