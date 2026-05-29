# Temporary debug-log workflow for §7 Action B SourcedId capture

When you need Jose Hunter's userinfo SourcedId during a fresh ClassLink LaunchPad-tile click — and you can't get it from the ClassLink developer portal directly — ship this temporary debug log, capture the value from **Better Stack or Railway logs** (NOT Sentry — see capture note below), then revert.

The audit_log at `backend/routes/classlink_routes.py:603` already captures a truncated SHA-256 `person_hash` (FERPA-compliant). The hash is non-reversible, so a raw-value log is needed only for the one-shot diagnostic.

## Apply the debug log

```bash
cd /Users/alexc/Downloads/Graider
git checkout main && git pull --ff-only
git checkout -b debug/classlink-sourcedid-probe

git apply scripts/debug_log_sourcedid.diff
git diff --stat
#   expected: backend/routes/classlink_routes.py | 9 +++++++++

# Sanity-check tests still pass with the added log line
source venv/bin/activate
pytest tests/test_classlink_sso.py -q

git add backend/routes/classlink_routes.py
git commit -m "DEBUG (temporary): log raw SourcedId for handoff §7 Action B SourcedId contract verification"
git push -u origin debug/classlink-sourcedid-probe

gh pr create --title "DEBUG (REVERT BEFORE NEXT RELEASE): log raw SourcedId for SourcedId contract diagnostic" \
             --body "Temporary diagnostic per handoff §7 Action B. REVERT immediately after capturing the SourcedId from Sentry. See scripts/debug_log_sourcedid.README.md."

# Class A — non-auth-semantic log addition. Squash-merge once CI is green.
```

## Capture the value

After Railway deploys the debug-log PR:

1. Have Jose Hunter (in the ClassLink Test District LaunchPad — tenant 4957) click the Graider tile.
2. The callback hits the fail-closed branch (existing `not_provisioned` behavior) and the new `logger.warning` fires.
3. Pull **Better Stack** (or Railway live-tail) for the latest `DEBUG_SOURCEDID_PROBE` log line. **Do not look in Sentry** — `logger.warning` produces only a Sentry breadcrumb (not a standalone event) under the project's current `LoggingIntegration` configuration (`event_level=ERROR`). The breadcrumb only attaches to a subsequent error event, not on its own. Better Stack ingests Railway stdout/stderr directly, so the log line lands there in plain text. Railway live-tail (`railway logs --service <web>`) is the most direct fallback if Better Stack is unreachable.

   The log line reads:
   ```
   DEBUG_SOURCEDID_PROBE tenant=<tenant_id> person_id=<raw SourcedId> (temporary — revert after handoff §7 Action B)
   ```
4. Note the raw `person_id` value.

## Use the captured SourcedId in the diagnostic

```bash
export ONEROSTER_BASE_URL="https://4957.classlink-os.com/ims/oneroster/v1p1"   # confirm with ClassLink developer portal
export ONEROSTER_CLIENT_ID="<from ClassLink developer portal — Roster Server credentials for tenant 4957>"
export ONEROSTER_CLIENT_SECRET="<same source>"
export USERINFO_SOURCED_ID="<raw value captured in step 4 above>"
export LOOKUP_EMAIL="S4957-0002@4957.demo"

bash scripts/diag_classlink_sourcedid.sh

# Interpret the exit code:
#   0 → contract HOLDS. The userinfo SourcedId exists in the roster.
#        Next: trigger a roster sync for tenant 4957 to populate the
#        students table, then re-test the LaunchPad tile.
#   1 → contract BROKEN. Userinfo SourcedId ≠ Roster Server sourcedId.
#        Next: escalate to ClassLink support with the printed diff.
#        Block the Roster Server cert call.
#   2 → operational error (auth / network / wrong base_url).
#        Fix the inputs and re-run.
```

## Revert the debug log

**Do not leave the temporary log line in `main`.**

```bash
git checkout main && git pull --ff-only
git checkout -b revert/classlink-sourcedid-probe

git revert <SHA_OF_THE_DEBUG_COMMIT>
git push -u origin revert/classlink-sourcedid-probe

gh pr create --title "Revert temporary SourcedId debug log (post-§7 Action B capture)" \
             --body "Reverts the debug log added in <debug PR #>. SourcedId already captured + contract verified per handoff §7 Action B."
```

CI runs, manual squash-merge, Railway deploys, confirm `DEBUG_SOURCEDID_PROBE` no longer appears in Better Stack on subsequent LaunchPad clicks. Done.
