# ClassLink Certification — Validation Checklist

**Purpose:** the self-run checklist to clear BEFORE clicking "Request Certification"
in the ClassLink Partner Portal. Run every ⏳ item, then submit.

**Integration type:** OAuth2 / **OpenID Connect (OIDC)** + **OneRoster** rostering
(scopes `profile oneroster email openid`). NOT LTI/SAML — those are a separate,
unused config path.

**Cert environment (from this project's setup):**
- Tenant **2284**, district **4957**
- Roster Server: `classlinkcertification3-vn-v2.rosterserver.com`
- Test login: the **cltest LaunchPad** (NOT `launchpad.classlink.com` — the prod
  generic page). Use the cltest URL the PRM gave you.
- Test accounts validated: student **Jose Hunter** (single enrollment), student
  **Janet Chapman** (multi-enrollment). Test teacher: **T4957-0005**.
- 151 students provisioned with `classlink:2284:{sourcedId}` keys.

---

## A. Already validated this session ✅ (no action — evidence on record)

- [x] **Student SSO, single enrollment** — Jose Hunter launches the Graider tile
  → lands authenticated at `/student` (his class `4957_4957_02`, "No content yet").
- [x] **Student SSO, multi-enrollment** — Janet Chapman launches the tile → "Choose
  your class" picker → dashboard. (Picker labels show sourcedIds because the cert
  Roster Server returns the sourcedId as the class title — a cert-tenant data
  quirk, not a Graider bug.)
- [x] **Auto-sync on login (deployed)** — Janet was provisioned by the *deployed*
  auto-sync, not a manual script.
- [x] **Roster sync** — 151 students synced from the cert Roster Server (`/users`
  fallback handles the cert server returning `/students` empty).
- [x] **Logout → clean re-entry** — student portal logout returns the email+code
  form; SSO students re-enter via the tile (an SSO button was also added to that
  form).

---

## B. Remaining live validations ⏳ — RUN THESE before requesting cert

### B1. Teacher SSO — eyeball the teacher tile
- [ ] Log into the **cltest LaunchPad as the test TEACHER** (T4957-0005).
- [ ] Click the Graider tile.
- [ ] **Expected:** lands at the teacher dashboard (`/?classlink_login=success` →
  dashboard), NOT an error banner, NOT `/join`, NOT `/student`.
- [ ] **Also confirm:** the teacher's roster/classes populated (the login should
  have triggered an auto roster-sync). Check the Settings → Classroom / periods.
- [ ] If it lands wrong, capture the URL it landed on and the `classlink_error`
  query param (if any) for diagnosis.

### B2. Right-to-delete — exercise it live (don't just trust the code)
- [ ] As the test teacher (logged in via ClassLink), trigger the ClassLink
  delete-data action (`POST /api/classlink/delete-data`) from the UI (Settings →
  data/privacy) or directly.
- [ ] **Expected:** all `classlink:2284:*`-keyed rows for that teacher are removed
  (students, classes, enrollments, the teacher's ClassLink link).
- [ ] **Verify** in Supabase: `students` where `student_id_number LIKE
  'classlink:2284:%'` for that teacher → 0 rows after deletion.
- [ ] Confirm the response is a clean success (no 500), and the audit log recorded
  the deletion.
- [ ] (Re-provision afterward by having a test student log in again, so the tenant
  isn't left empty for the cert reviewer.)

### B3. Unauthenticated direct-access bounce (expected behavior — confirm it's clean)
- [ ] In a fresh incognito window (NOT logged into ClassLink), hit the Graider
  ClassLink login directly.
- [ ] **Expected:** redirected to the **generic ClassLink sign-in page** — this is
  ClassLink's documented, intended behavior ("the second redirect happens only
  when someone who isn't logged in accesses the app link directly"). Not an error.

### B4. End-to-end content flow (optional but strong for the demo)
- [ ] As the teacher, publish an assessment/assignment to a class (e.g.
  `4957_4957_02`).
- [ ] As Jose Hunter (student SSO), confirm it appears on his dashboard (replaces
  "No content yet"), open it, submit, and confirm a grade/feedback returns.
- [ ] This proves the full SSO → roster → publish → submit → grade loop, which is
  the most convincing thing to show a cert reviewer.

---

## C. Partner Portal process ⏳ — the actual submission

### C1. Reconcile the board bookkeeping (both boards)
- [ ] **SSO/OAuth2 board:** flip the two stale rows to **Complete** — they're
  functionally done (the tile works, students authenticate):
  - "Add Connection to Test Accounts" (was In Progress)
  - "Integration Development and Testing" (was Not Started)
- [ ] **Rostering board:** confirm all rows are Complete (they were) except Request
  Certification.

### C2. Confirm prerequisites are green in the portal
- [ ] SSO: domains added + **verified**; OAuth2/OpenID connection created; redirect
  URIs saved (test + prod).
- [ ] Rostering: roster connection registered; Tenant 2284 sample data received;
  accounts provisioned (✅ 151).

### C3. Request certification
- [ ] Click **"Request Certification"** on the **SSO/OAuth2** board.
- [ ] Click **"Request Certification"** on the **Rostering** board.
- [ ] **Expected:** you receive a link to **schedule the certification call** + new
  data shared to test onboarding (per ClassLink's process doc).

> ⚠️ If you changed ANY SSO connection setting in the Partner Portal, contact your
> PRM to mirror it into the test account BEFORE re-testing (per ClassLink's rule).

---

## D. Security hygiene ⏳ (independent of cert, do it)

- [ ] **Rotate the cert Roster Server client_secret** (`4d70f16728250ff6c4b79bf8`)
  in the ClassLink developer portal — the value was pasted in a chat session and
  is stored in Supabase `oneroster_config` for the cert teacher. Regenerate it and
  update the stored config.
- [ ] Confirm secrets are read from env / the encrypted store, never committed.

---

## E. After certification is granted (forward-looking)

- [ ] Repeat B1–B4 against the **production** ClassLink connection + a real district
  (per workflow Hard Rule #8: cert against the test tenant ≠ working against a live
  production tenant — re-run the originally-failing user flow against prod once a
  real district is connected).
- [ ] Real districts return **friendly class titles** (not sourcedIds) — confirm
  the picker/labels read well with real roster data.

---

## Quick status summary

| Area | State |
|---|---|
| Engineering (SSO OIDC, OneRoster, right-to-delete, multi-tenant, multi-enroll) | ✅ built + student-side validated |
| Teacher-tile eyeball (B1) | ⏳ |
| Right-to-delete live (B2) | ⏳ |
| Request Certification clicks (C3) | ⏳ |
| Secret rotation (D) | ⏳ |

**Bottom line:** no integration code remains. Clear B1, B2, and D, reconcile the
board (C1), then click Request Certification (C3).
