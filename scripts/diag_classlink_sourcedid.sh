#!/usr/bin/env bash
# diag_classlink_sourcedid.sh — wrapper for the ClassLink SourcedId
# contract diagnostic (originally shipped in PR #590 as
# scripts/verify_classlink_sourcedid_contract.py).
#
# Use this when a ClassLink LaunchPad-tile student SSO lands at
# /student?classlink_error=not_provisioned and you need to know whether
# the failure is:
#   (a) SourcedId contract broken (userinfo SourcedId ≠ Roster Server
#       sourcedId for the same person), OR
#   (b) contract holds but no `students` row exists yet (we just haven't
#       run a roster sync for this tenant).
#
# Required inputs (set as env vars or edit inline):
#
#   ONEROSTER_BASE_URL        ClassLink Test District Roster Server root.
#                             Probably: https://4957.classlink-os.com/ims/oneroster/v1p1
#                             Confirm with the ClassLink developer portal
#                             for tenant 4957 (Dev: ClassLink Test District).
#
#   ONEROSTER_CLIENT_ID       OAuth2 Roster Server credential. Retrieve from:
#                               https://developer.classlink.com → Roster Server →
#                               select tenant 4957 → API credentials.
#
#   ONEROSTER_CLIENT_SECRET   Same source as above.
#
#   USERINFO_SOURCED_ID       The raw SourcedId ClassLink's userinfo endpoint
#                             returns for Jose Hunter at SSO time.
#
#                             Three ways to obtain:
#
#                             1. (Fastest if you have it) Look up Jose Hunter
#                                in the ClassLink developer portal user admin
#                                UI — the SourcedId is shown directly.
#
#                             2. Ship a temporary debug log (see the diff
#                                in /Users/alexc/Downloads/Graider/scripts/
#                                debug_log_sourcedid.diff), redeploy, click
#                                the LaunchPad Graider tile, read Better Stack
#                                (or Railway live-tail) for the
#                                "DEBUG_SOURCEDID_PROBE" line, then revert.
#                                NOTE: do NOT look in Sentry — logger.warning
#                                produces a breadcrumb (not an event) under
#                                the project's LoggingIntegration config.
#
#                             3. Hit ClassLink's userinfo endpoint directly
#                                with Jose's access token:
#                                  curl https://nodeapi.classlink.com/v2/my/info \
#                                       -H "Authorization: Bearer <ACCESS_TOKEN>"
#                                Read the SourcedId field from the JSON response.
#                                (Requires intercepting the access token —
#                                generally easier via option 1 or 2.)
#
#   LOOKUP_EMAIL              For the fallback "find by email" path when the
#                             direct lookup returns 404. Already known from the
#                             LaunchPad profile screenshot:
#                                  S4957-0002@4957.demo

set -euo pipefail

# ── Configuration ──────────────────────────────────────────────────────────────
ONEROSTER_BASE_URL="${ONEROSTER_BASE_URL:-https://4957.classlink-os.com/ims/oneroster/v1p1}"
ONEROSTER_CLIENT_ID="${ONEROSTER_CLIENT_ID:-}"
ONEROSTER_CLIENT_SECRET="${ONEROSTER_CLIENT_SECRET:-}"
USERINFO_SOURCED_ID="${USERINFO_SOURCED_ID:-}"
LOOKUP_EMAIL="${LOOKUP_EMAIL:-S4957-0002@4957.demo}"

# ── Validation ─────────────────────────────────────────────────────────────────
missing=()
[ -z "$ONEROSTER_CLIENT_ID"     ] && missing+=("ONEROSTER_CLIENT_ID")
[ -z "$ONEROSTER_CLIENT_SECRET" ] && missing+=("ONEROSTER_CLIENT_SECRET")
[ -z "$USERINFO_SOURCED_ID"     ] && missing+=("USERINFO_SOURCED_ID")

if [ ${#missing[@]} -gt 0 ]; then
    cat <<EOF >&2
ERROR: missing required env var(s): ${missing[*]}

Set them before running, e.g.:

    export ONEROSTER_BASE_URL="https://4957.classlink-os.com/ims/oneroster/v1p1"
    export ONEROSTER_CLIENT_ID="<from ClassLink developer portal>"
    export ONEROSTER_CLIENT_SECRET="<from ClassLink developer portal>"
    export USERINFO_SOURCED_ID="<from Better Stack / Railway logs / developer portal>"
    export LOOKUP_EMAIL="S4957-0002@4957.demo"   # already-known default

    bash scripts/diag_classlink_sourcedid.sh

See the header of this script for where to obtain each value.
EOF
    exit 2
fi

# ── Activate venv ──────────────────────────────────────────────────────────────
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

if [ -f venv/bin/activate ]; then
    # shellcheck disable=SC1091
    source venv/bin/activate
fi

# ── Run the diagnostic ─────────────────────────────────────────────────────────
echo "== diag_classlink_sourcedid.sh =="
echo "  base_url:           $ONEROSTER_BASE_URL"
echo "  userinfo SourcedId: $USERINFO_SOURCED_ID"
echo "  fallback email:     $LOOKUP_EMAIL"
echo ""

python scripts/verify_classlink_sourcedid_contract.py \
    --base-url "$ONEROSTER_BASE_URL" \
    --client-id "$ONEROSTER_CLIENT_ID" \
    --client-secret "$ONEROSTER_CLIENT_SECRET" \
    --userinfo-sourced-id "$USERINFO_SOURCED_ID" \
    --lookup-email "$LOOKUP_EMAIL"

rc=$?
echo ""
case $rc in
    0) echo "→ Contract HOLDS. The userinfo SourcedId exists as a roster sourcedId."
       echo "  Next step: run a roster sync for this tenant via"
       echo "    POST /api/oneroster/sync-roster"
       echo "  to populate the students table; then re-test the LaunchPad tile."
       ;;
    1) echo "→ Contract BROKEN. The userinfo SourcedId does NOT match the roster."
       echo "  Next step: escalate to ClassLink support with the diff above."
       echo "  Block the Roster Server cert call until ClassLink fixes the contract."
       ;;
    2) echo "→ Operational error. Fix the inputs (creds / base_url / network) and re-run."
       ;;
esac
exit $rc
