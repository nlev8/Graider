# Graider API Reference

> Auto-derived from the Flask route definitions in `backend/routes/` and `backend/app.py`, verified against source. **308 endpoints.**

All endpoints are under the application host (production: `https://app.graider.live`). Auth column: **Teacher** = requires a teacher session (`@require_teacher`); **School Admin** = principal-level role (`@require_admin`, checks `admin_role:{user_id}`); **District Admin** = district-setup role (`@_require_district_admin`, password-based session); **Clever session** = `@require_clever_session`; **Public** = no auth decorator (may still validate tokens/codes in-body).

## AI Assistant

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| `POST` | `/api/assistant/cancel` | Teacher | Cancel an active assistant stream — stops tool execution loop. |
| `POST` | `/api/assistant/chat` | Teacher | Stream chat responses with tool use via SSE. |
| `POST` | `/api/assistant/clear` | Teacher | Clear conversation history for a session. |
| `GET` | `/api/assistant/costs` | Teacher | Return assistant API cost summary (total + daily breakdown). |
| `GET` | `/api/assistant/credentials` | Teacher | Check if VPortal credentials are configured (never returns password). |
| `POST` | `/api/assistant/credentials` | Teacher | Save VPortal credentials (base64 obfuscated, per-teacher in Supabase). |
| `DELETE` | `/api/assistant/memory` | Teacher | Clear all saved assistant memories. |
| `GET` | `/api/assistant/memory` | Teacher | Return all saved assistant memories. |
| `POST` | `/api/assistant/mute-tts` | Teacher | Mute TTS for a session — stops sending text to TTS mid-stream. |
| `GET` | `/api/assistant/voice-config` | Teacher | Return voice TTS configuration status. |

## Assignment Player

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| `POST` | `/api/assignment` | Teacher | Create/publish an assignment for students. |
| `GET` | `/api/assignment/<assignment_id>` | Public | Get an assignment for a student to complete. |
| `GET` | `/api/assignment/<assignment_id>/submissions` | Teacher | Get all submissions for an assignment (teacher view). |
| `POST` | `/api/assignment/<assignment_id>/submit` | Public | Submit and grade an assignment. |

## Assignments

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| `DELETE` | `/api/delete-assignment` | Teacher | Delete a saved assignment configuration. |
| `GET` | `/api/download-csv/<filename>` | Teacher | Serve a generated CSV file for download. |
| `GET` | `/api/download-document/<filename>` | Teacher | Serve a generated document for download. |
| `GET` | `/api/download-export/<filename>` | Teacher | Serve an exported CSV file for download. |
| `GET` | `/api/download-worksheet/<filename>` | Teacher | Serve a generated worksheet for download. |
| `POST` | `/api/export-assignment` | Teacher | Export assignment to Word or PDF format. |
| `POST` | `/api/generate-model-answers` | Teacher | Generate AI model answers for each section/marker in an assignment config. |
| `GET` | `/api/list-assignments` | Teacher | List saved assignment configurations with aliases. |
| `GET` | `/api/load-assignment` | Teacher | Load a saved assignment configuration. |
| `POST` | `/api/save-assignment-config` | Teacher | Save assignment configuration for grading. |

## Automations

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| `GET` | `/api/automations` | Teacher | List all saved workflow files. |
| `POST` | `/api/automations` | Teacher | Save or create a workflow. |
| `DELETE` | `/api/automations/<workflow_id>` | Teacher | Delete a workflow file. |
| `GET` | `/api/automations/<workflow_id>` | Teacher | Load a specific workflow JSON. |
| `POST` | `/api/automations/<workflow_id>/run` | Teacher | Launch workflow as subprocess. |
| `GET` | `/api/automations/picker/events` | Teacher | Drain and return accumulated picker events. |
| `POST` | `/api/automations/picker/start` | Teacher | Launch element picker browser. |
| `POST` | `/api/automations/picker/stop` | Teacher | Close picker browser. |
| `GET` | `/api/automations/run/status` | Teacher | Poll current automation run state. |
| `POST` | `/api/automations/run/stop` | Teacher | Kill running automation subprocess. |
| `GET` | `/api/automations/templates` | Teacher | Return built-in template workflows. |
| `DELETE` | `/api/automations/templates/<template_id>` | Teacher | Delete a template file by matching its JSON id field. |
| `GET` | `/api/automations/templates/<template_id>` | Teacher | Load a specific template by ID. |

## Behavior Tracking

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| `DELETE` | `/api/behavior/data` | Teacher | Delete behavior data. |
| `GET` | `/api/behavior/data` | Teacher | Get behavior tracking data. |
| `GET` | `/api/behavior/debug` | Teacher | Diagnostic: show teacher_id, event count, session count, and stored student names. |
| `GET` | `/api/behavior/events` | Teacher | Get individual behavior events (not aggregated). |
| `GET` | `/api/behavior/roster` | Teacher | Return a lightweight roster for name matching in the behavior panel. |
| `POST` | `/api/behavior/session` | Teacher | Save a completed behavior tracking session. |

## Billing (Stripe)

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| `POST` | `/api/stripe/create-checkout-session` | Teacher | Create a Stripe Checkout session for a new subscription. |
| `POST` | `/api/stripe/create-portal-session` | Teacher | Create a Stripe Customer Portal session for subscription management. |
| `GET` | `/api/stripe/subscription-status` | Teacher | Get the current user's subscription status from Stripe. |
| `POST` | `/api/stripe/webhook` | Public | Handle Stripe webhook events, verified via Stripe-Signature header. |

## ClassLink SSO

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| `GET` | `/api/classlink/callback` | Public | Handle ClassLink OAuth callback — exchange code for token, fetch user. |
| `GET` | `/api/classlink/login-url` | Public | Return ClassLink OAuth authorization URL with CSRF state token and nonce. |
| `POST` | `/api/classlink/logout` | Public | Clear ClassLink session. |
| `GET` | `/api/classlink/session` | Public | Check ClassLink session status. |

## Clever SSO & Roster

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| `POST` | `/api/clever/apply-accommodations` | Clever session | Apply Clever-sourced IEP/ELL flags as Graider accommodation presets. |
| `GET` | `/api/clever/callback` | Public | Handle the OAuth redirect from Clever. |
| `POST` | `/api/clever/delete-data` | Clever session | Delete all Clever-sourced student data for the current teacher. |
| `GET` | `/api/clever/district-keys` | Clever session | Check which API keys are configured at the district level. |
| `POST` | `/api/clever/district-keys` | Clever session | Save district-level API keys. Only district_admin users can do this. |
| `GET` | `/api/clever/health` | Public | Health check for Clever integration — verifies config and connectivity. |
| `GET` | `/api/clever/login-url` | Public | Return the Clever OAuth authorization URL. |
| `POST` | `/api/clever/logout` | Public | Clear the Clever session. |
| `GET/POST` | `/api/clever/select-class` | Public | Multi-enrollment Clever SSO finalize (Task A). |
| `GET` | `/api/clever/session` | Public | Return current Clever session info (if logged in via Clever). |
| `POST` | `/api/clever/student-token` | Public | Exchange a short-lived auth code for a student session token. |
| `POST` | `/api/clever/sync-roster` | Clever session | Trigger a roster sync from Clever. |

## Core App & Misc

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| `GET` | `/` | Public | Serve the React frontend. |
| `GET` | `/<path:path>` | Public | Serve static files or fall back to index.html for SPA routing. |
| `GET` | `/api/user-manual` | Public | Return User_Manual.md content as JSON. |
| `GET` | `/district` | Public | Serve React app for district admin setup. |
| `GET` | `/district/` | Public | Serve React app for district admin setup. |
| `GET` | `/healthz` | Public | General health check for Railway load balancer. |
| `GET` | `/join` | Public | Serve React app for student portal routes. |
| `GET` | `/join/` | Public | Serve React app for student portal routes. |
| `GET` | `/join/<path:code>` | Public | Serve React app for student portal routes. |
| `GET` | `/student` | Public | Serve React app for authenticated student portal. |
| `GET` | `/student/` | Public | Serve React app for authenticated student portal. |
| `GET` | `/student/<path:subpath>` | Public | Serve React app for authenticated student portal. |

## District Admin

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| `POST` | `/api/district/admin-invite` | District Admin | Generate a 6-char invite code for granting district admin role. |
| `DELETE` | `/api/district/admins` | District Admin | Revoke district admin role from a user. |
| `GET` | `/api/district/admins` | District Admin | List all users with district admin role. |
| `DELETE` | `/api/district/auth` | Public | Clear district admin session. |
| `POST` | `/api/district/auth` | Public | Authenticate as district admin or set up initial password. |
| `POST` | `/api/district/change-password` | District Admin | Change district admin password. |
| `GET` | `/api/district/config` | District Admin | Return full config with masked secrets. |
| `POST` | `/api/district/config` | District Admin | Save SIS and AI key configuration. |
| `GET` | `/api/district/config-status` | Public | Public endpoint: returns high-level config status (no secrets). |
| `GET` | `/api/district/teacher-search` | District Admin | Search teachers by name or email (case-insensitive). |
| `POST` | `/api/district/test-connection` | District Admin | Test SIS connectivity. |

## Email & Feedback Delivery

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| `POST` | `/api/confirm-send` | Teacher | Execute a confirmed send action from the assistant preview. |
| `GET` | `/api/email-status` | Teacher | Check if email is configured. |
| `POST` | `/api/export-outlook-emails` | Teacher | Build parent-notification email payloads as JSON for Outlook. |
| `GET` | `/api/focus-comms/status` | Teacher | Get current Focus Communications sending progress. |
| `POST` | `/api/focus-comms/stop` | Teacher | Kill the Focus Communications subprocess if running. |
| `POST` | `/api/mark-confirmations-sent-file` | Teacher | Mark files as confirmation_sent after Outlook send completes. |
| `POST` | `/api/outlook-login` | Teacher | Open Outlook in browser for login verification. |
| `GET` | `/api/outlook-send/status` | Teacher | Get current Outlook sending progress. |
| `POST` | `/api/pending-confirmations` | Teacher | Count how many files in the assignments folder need confirmation emails. |
| `POST` | `/api/save-email-config` | Teacher | Save teacher email configuration. |
| `POST` | `/api/send-confirmation-emails` | Teacher | Send submission-received confirmations for ALL files in the assignments folder. |
| `POST` | `/api/send-emails` | Teacher | Send grade emails to students via Resend. |
| `POST` | `/api/send-focus-comms` | Teacher | Start sending messages via Focus SIS Communications. |
| `POST` | `/api/send-outlook-emails` | Teacher | Start sending emails via Playwright Outlook automation. |
| `POST` | `/api/test-email` | Teacher | Send a test email to verify configuration. |

## FERPA / Data Privacy

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| `GET` | `/api/ferpa/audit-log` | Teacher | Retrieve audit log entries showing who accessed data when. |
| `GET` | `/api/ferpa/data-summary` | Teacher | Summarize what student data is stored locally. |
| `POST` | `/api/ferpa/delete-all-data` | Teacher | Securely delete all student data, settings, and cache. |
| `GET` | `/api/ferpa/export-data` | Teacher | Export all student data for portability requests. |
| `POST` | `/api/ferpa/export-student` | Teacher | Export one student's data as JSON plus PDF report. |
| `POST` | `/api/ferpa/import-student` | Teacher | FERPA-compliant: Import a previously exported student data file. |

## Grading

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| `POST` | `/api/check-math-equivalence` | Teacher | Check whether two math expressions are equivalent. |
| `POST` | `/api/clear-results` | Teacher | Clear grading results. Optionally filter by assignment name. |
| `GET` | `/api/ell-students` | Teacher | Get all ELL student designations. |
| `POST` | `/api/ell-students` | Teacher | Save ELL student designations. |
| `POST` | `/api/export-focus-batch` | Teacher | Export per-period CSV files for Focus SIS bulk import. |
| `POST` | `/api/export-focus-comments` | Teacher | Export per-student comments as per-period JSON for Focus SIS. |
| `POST` | `/api/export-focus-csv` | Teacher | Export grades as CSV for Focus SIS import. |
| `POST` | `/api/export-lms-csv` | Teacher | Export grades as CSV for Canvas or PowerSchool import. |
| `GET` | `/api/focus-comments/status` | Teacher | Get current Focus comments upload progress. |
| `POST` | `/api/grade-coordinates` | Teacher | Grade a geography coordinate answer with distance tolerance. |
| `POST` | `/api/grade-data-table` | Teacher | Grade a science data table with numerical tolerance. |
| `POST` | `/api/grade-math` | Teacher | Grade a math answer using SymPy equivalence checking. |
| `POST` | `/api/grade-place-name` | Teacher | Grade a geography place-name answer accepting accepted alternatives. |
| `GET` | `/api/status` | Teacher | Get current grading status. |
| `POST` | `/api/stop-grading` | Teacher | Stop grading and save progress. |
| `DELETE` | `/api/student-history` | Teacher | Delete ALL student history (fresh start). |
| `GET` | `/api/student-history` | Teacher | List all students with saved history/writing profiles. |
| `DELETE` | `/api/student-history/<student_id>` | Teacher | Delete history for a specific student. |
| `GET` | `/api/student-history/<student_id>` | Teacher | Get detailed history for a specific student. |
| `POST` | `/api/student-history/migrate-names` | Teacher | Add student names to existing profiles by looking up from roster. |
| `POST` | `/api/update-result` | Teacher | Update a single grading result (score, feedback, etc.). |
| `POST` | `/api/upload-focus-comments` | Teacher | Start uploading comments to Focus via Playwright automation. |

## Grading Results

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| `POST` | `/api/delete-result` | Teacher | Delete a single grading result by filename. |
| `POST` | `/api/grade-individual` | Teacher | Grade a single uploaded image file (for paper/handwritten assignments). |
| `POST` | `/api/update-approval` | Teacher | Update email approval status for a result. |
| `POST` | `/api/update-approvals-bulk` | Teacher | Update email approval status for multiple results at once. |

## LTI 1.3 (1EdTech)

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| `DELETE` | `/api/lti/config` | Teacher | Delete a platform registration. |
| `GET` | `/api/lti/config` | Teacher | List registered platforms and tool config URLs. |
| `POST` | `/api/lti/config` | Teacher | Register a new LTI platform. |
| `GET` | `/api/lti/contexts` | Teacher | List AGS contexts with student counts. |
| `GET` | `/api/lti/jwks` | Public | Serve the tool's public JWKS document. |
| `POST` | `/api/lti/launch` | Public | LTI 1.3 launch callback — validates id_token and establishes session. |
| `GET/POST` | `/api/lti/login` | Public | OIDC login initiation — redirects to the platform's auth endpoint. |
| `POST` | `/api/lti/sync-grades` | Teacher | Sync grades to the LMS via AGS. |

## Lesson Planner & Assessment Generation

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| `POST` | `/api/adjust-reading-level` | Teacher | Rewrite text at a target reading level while preserving key terms. |
| `POST` | `/api/align-document-to-standards` | Teacher | Analyze a document and identify which standards it aligns to. |
| `DELETE` | `/api/assessment-template/<template_id>` | Teacher | Delete an assessment template. |
| `GET` | `/api/assessment-templates` | Teacher | Get all uploaded assessment templates. |
| `GET` | `/api/available-states` | Public | Return list of all supported states with names. No auth required. |
| `POST` | `/api/brainstorm-lesson-ideas` | Teacher | Generate multiple lesson plan ideas/concepts for selected standards. |
| `POST` | `/api/export-assessment` | Teacher | Export assessment to Word document with Graider table extraction tags. |
| `POST` | `/api/export-assessment-platform` | Teacher | Export assessment in a specific platform's format. |
| `POST` | `/api/export-flashcards` | Teacher | Export flashcards to PDF or DOCX. |
| `POST` | `/api/export-generated-assignment` | Teacher | Export a generated assignment to PDF or DOCX (with Graider tables) format. |
| `POST` | `/api/export-lesson-plan` | Teacher | Export the lesson plan to a Word document. |
| `POST` | `/api/export-slides` | Teacher | Export generated slides as PowerPoint (.pptx). |
| `POST` | `/api/export-study-guide` | Teacher | Export a study guide to DOCX or PDF. |
| `POST` | `/api/extract-text` | Teacher | Extract plain text from uploaded documents (docx, pdf, txt) or images (png, jpg, etc.). |
| `POST` | `/api/generate-assessment` | Teacher | Generate a standards-aligned assessment with DOK distribution. |
| `POST` | `/api/generate-assignment-from-lesson` | Teacher | Generate an assignment based on an existing lesson plan. |
| `POST` | `/api/generate-flashcards` | Teacher | Generate flashcards from content using Gemini Flash. |
| `POST` | `/api/generate-lesson-plan` | Teacher | Generate a lesson plan using AI. |
| `POST` | `/api/generate-slides` | Teacher | Generate a slide deck from content using Gemini Flash. |
| `POST` | `/api/generate-study-guide` | Teacher | Generate a structured study guide from content using Gemini Flash. |
| `POST` | `/api/get-lesson-templates` | Teacher | Get subject-specific lesson activity templates. |
| `POST` | `/api/get-standards` | Teacher | Get standards for a specific state, grade, and subject. |
| `POST` | `/api/grade-assessment-answers` | Teacher | Grade student answers against an assessment using AI. |
| `GET` | `/api/planner/costs` | Teacher | Return planner API cost summary. |
| `POST` | `/api/regenerate-questions` | Teacher | Regenerate specific questions in an assessment/assignment using AI. |
| `POST` | `/api/rewrite-for-alignment` | Teacher | Rewrite specific questions to better align with selected standards. |
| `POST` | `/api/upload-assessment-template` | Teacher | Upload a sample template from an assessment platform (e.g., Wayground, Canvas). |

## Lessons

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| `GET` | `/api/calendar` | Teacher | Return full calendar data. |
| `DELETE` | `/api/calendar/holiday` | Teacher | Remove a holiday by date. |
| `POST` | `/api/calendar/holiday` | Teacher | Add a holiday or break to the calendar. |
| `POST` | `/api/calendar/import-events` | Teacher | Bulk import events into the teaching calendar. |
| `POST` | `/api/calendar/parse-document` | Teacher | Parse an uploaded document and extract calendar events using AI. |
| `PUT` | `/api/calendar/schedule` | Teacher | Add or update a scheduled lesson on the calendar. |
| `DELETE` | `/api/calendar/schedule/<entry_id>` | Teacher | Remove a scheduled lesson from the calendar. |
| `PUT` | `/api/calendar/school-days` | Teacher | Update which days of the week are school days. |
| `DELETE` | `/api/delete-lesson` | Teacher | Delete a saved lesson. |
| `POST` | `/api/delete-resource` | Teacher | Delete a saved resource by ID. |
| `GET` | `/api/list-lessons` | Teacher | List all saved lessons organized by unit. |
| `GET` | `/api/list-resources` | Teacher | List all saved resources for the teacher. |
| `GET` | `/api/list-units` | Teacher | List all unit names. |
| `GET` | `/api/load-lesson` | Teacher | Load a specific lesson by unit and filename. |
| `POST` | `/api/load-resource` | Teacher | Load a saved resource by ID. |
| `POST` | `/api/save-lesson` | Teacher | Save a lesson plan for later use in assessment generation. |
| `POST` | `/api/save-resource` | Teacher | Save a generated resource for the Assets library. |

## OneRoster (1EdTech)

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| `POST` | `/api/oneroster/apply-accommodations` | Teacher | Apply IEP/ELL accommodation presets to students. |
| `GET` | `/api/oneroster/config` | Teacher | Return OneRoster config status (never exposes secrets). |
| `POST` | `/api/oneroster/config` | Teacher | Save OneRoster configuration. |
| `POST` | `/api/oneroster/delete-data` | Teacher | Delete all OneRoster roster data and clear config. |
| `POST` | `/api/oneroster/sync-grades` | Teacher | Push graded scores + comments to SIS via OneRoster Gradebook API. |
| `POST` | `/api/oneroster/sync-roster` | Teacher | Sync roster from OneRoster API. |
| `POST` | `/api/oneroster/teacher-id` | Teacher | Save just the teacher's OneRoster sourcedId (used with district-level config). |
| `POST` | `/api/oneroster/test` | Teacher | Test OneRoster API connectivity. |

## Roster / Periods

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| `POST` | `/api/add-student-to-roster` | Teacher | Add a student to the appropriate period CSV and optionally the main roster. |
| `POST` | `/api/extract-student-from-image` | Teacher | Use Claude Opus 4.5 to extract student info from a screenshot. |
| `GET` | `/api/list-periods` | Teacher | List available period CSV files. |
| `POST` | `/api/retranslate-feedback` | Teacher | Re-translate English feedback to the target language. |
| `GET` | `/api/student-baseline/<student_id>` | Teacher | Get a student's baseline performance metrics for deviation detection. |
| `GET` | `/api/student-history/<student_id>` | Teacher | Get a student's grading history and progress patterns. |

## SEO / Public Pages

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| `POST` | `/api/seo/analyze-content` | Teacher | Analyze content for SEO score and get improvement suggestions. |
| `POST` | `/api/seo/generate-schema` | Teacher | Generate JSON-LD structured data for a page. |
| `POST` | `/api/seo/optimize-meta` | Teacher | Optimize meta tags (title, description, keywords) for given page content. |
| `POST` | `/api/seo/suggest-blog-topics` | Teacher | Suggest new blog topics based on existing content and target keywords. |

## School Admin (Principal)

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| `GET` | `/api/admin/activity` | School Admin | Recent activity feed across all admin's teachers. |
| `POST` | `/api/admin/claim` | Teacher | Claim school-admin role with an invite code (rate-limited). |
| `GET` | `/api/admin/overview` | School Admin | Aggregate metrics across admin's teachers. |
| `GET` | `/api/admin/status` | Teacher | Check whether the current teacher is a school admin. |
| `GET` | `/api/admin/teacher/<teacher_id>/summary` | School Admin | Drill-down summary for a specific teacher in the admin's school. |
| `GET` | `/api/admin/teachers` | School Admin | List teachers in the admin's school (multi-layer discovery). |

## Settings

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| `GET` | `/api/accommodation-presets` | Teacher | Get all available accommodation presets (default + custom). |
| `POST` | `/api/accommodation-presets` | Teacher | Create or update a custom accommodation preset. |
| `DELETE` | `/api/accommodation-presets/<preset_id>` | Teacher | Delete a custom accommodation preset. |
| `GET` | `/api/accommodation-stats` | Teacher | Get statistics about accommodation usage. |
| `POST` | `/api/add-student` | Teacher | Add a student to a period CSV and optionally to parent contacts. |
| `GET` | `/api/check-api-keys` | Teacher | Check which API keys are configured (without exposing the keys). |
| `POST` | `/api/clear-accommodations` | Teacher | Delete all student accommodation data. |
| `POST` | `/api/delete-document` | Teacher | Delete a supporting document. |
| `POST` | `/api/delete-period` | Teacher | Delete a period file. |
| `POST` | `/api/delete-roster` | Teacher | Delete a roster file. |
| `GET` | `/api/export-accommodations` | Teacher | Export all accommodation data for backup. |
| `GET` | `/api/focus-import-status` | Teacher | Get current status of the Focus import process. |
| `POST` | `/api/get-period-students` | Teacher | Get student names from a period CSV file. |
| `POST` | `/api/import-accommodations` | Teacher | Import accommodations from an uploaded CSV file. |
| `POST` | `/api/import-from-focus` | Teacher | Trigger Focus SIS roster import via Playwright. |
| `GET` | `/api/list-documents` | Teacher | List all uploaded supporting documents. |
| `GET` | `/api/list-periods` | Teacher | List all uploaded period files with their students. |
| `GET` | `/api/list-rosters` | Teacher | List all uploaded roster files. |
| `GET` | `/api/load-global-settings` | Teacher | Load global AI notes and settings. |
| `GET` | `/api/load-rubric` | Teacher | Load rubric configuration. |
| `GET` | `/api/parent-contacts` | Teacher | Return stored parent contacts with summary stats. |
| `POST` | `/api/preview-parent-contacts` | Teacher | Preview uploaded class-list file headers and suggested column mapping. |
| `POST` | `/api/remove-student` | Teacher | Remove a student from period CSV and parent contacts. |
| `POST` | `/api/save-api-keys` | Teacher | Save API keys securely via BYOK module. |
| `POST` | `/api/save-global-settings` | Teacher | Save global AI notes and settings. |
| `POST` | `/api/save-parent-contact-mapping` | Teacher | Process uploaded file with confirmed mapping, save parent contacts. |
| `POST` | `/api/save-roster-mapping` | Teacher | Save column mapping for a roster file. |
| `POST` | `/api/save-rubric` | Teacher | Save rubric configuration. |
| `GET` | `/api/student-accommodations` | Teacher | Get all student accommodation mappings with name resolution. |
| `DELETE` | `/api/student-accommodations/<student_id>` | Teacher | Remove accommodation settings for a student. |
| `GET` | `/api/student-accommodations/<student_id>` | Teacher | Get accommodation settings for a specific student. |
| `POST` | `/api/student-accommodations/<student_id>` | Teacher | Set accommodation presets for a student. |
| `POST` | `/api/sync-to-cloud` | Teacher | Upload all local ~/.graider_* data to Supabase for the logged-in teacher. |
| `POST` | `/api/update-period-level` | Teacher | Update the class level (standard/advanced/support) for a period. |
| `POST` | `/api/update-student` | Teacher | Update a student's info in the period CSV and/or parent contacts. |
| `POST` | `/api/upload-document` | Teacher | Upload a supporting document for lesson planning/grading. |
| `POST` | `/api/upload-period` | Teacher | Upload a period/class CSV file. |
| `POST` | `/api/upload-roster` | Teacher | Upload and process a roster CSV file. |

## Student Accounts (Class-based)

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| `GET` | `/api/classes` | Teacher | List teacher's classes with student counts. |
| `POST` | `/api/classes` | Teacher | Create a class. Generates join code. |
| `GET` | `/api/classes/<class_id>/students` | Teacher | List students enrolled in a class. |
| `POST` | `/api/classes/<class_id>/sync-roster` | Teacher | Sync students from an uploaded CSV into the class. |
| `POST` | `/api/grade-portal-submission` | Teacher | Grade a portal submission using the existing grading pipeline. |
| `POST` | `/api/mark-confirmations-sent` | Teacher | Mark confirmations as sent after Outlook send completes. |
| `GET` | `/api/portal-submissions` | Teacher | Get all student submissions for the Results tab. |
| `POST` | `/api/publish-to-class` | Teacher | Publish an assessment or assignment to a class. |
| `POST` | `/api/publish-to-class-batch` | Teacher | Phase 4.2 #2: atomic batch publish for personalized remediations. |
| `POST` | `/api/send-submission-confirmations` | Teacher | Batch-send pending submission confirmations via Outlook. |
| `POST` | `/api/student/class-submit/<content_id>` | Public | Submit answers for an assessment or assignment. |
| `GET` | `/api/student/content/<content_id>` | Public | Get assessment/assignment content for a student to complete. |
| `GET` | `/api/student/dashboard` | Public | Get student's assigned work (assessments + assignments). |
| `POST` | `/api/student/login` | Public | Student login with email + class join code. |
| `GET` | `/api/student/resource/<content_id>` | Public | Get full resource content for viewing/downloading. |
| `GET` | `/api/student/resources` | Public | List resources (study guides, flashcards, slide decks) published to student's class. |
| `GET` | `/api/student/session` | Public | Check if current student session is valid. |
| `GET` | `/api/student/submission/<content_id>/draft` | Public | Fetch an existing draft for resume. |
| `POST` | `/api/student/submission/<content_id>/draft` | Public | Save or update a draft submission for the authenticated student. |

## Student Portal (Join Code)

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| `POST` | `/api/delete-saved-assessment` | Teacher | Delete a saved assessment. |
| `GET` | `/api/list-saved-assessments` | Teacher | List all saved assessments. |
| `POST` | `/api/load-saved-assessment` | Teacher | Load a saved assessment by filename. |
| `POST` | `/api/publish-assessment` | Teacher | Publish an assessment, returning a join code and link. |
| `POST` | `/api/save-assessment` | Teacher | Save a generated assessment locally for later use. |
| `GET` | `/api/student/join/<code>` | Public | Get assessment details (without answers) for a join code. |
| `POST` | `/api/student/submit/<code>` | Public | Submit student answers for grading, returning immediate feedback. |
| `DELETE` | `/api/teacher/assessment/<code>` | Teacher | Delete a published assessment and all its submissions. |
| `GET` | `/api/teacher/assessment/<code>/results` | Teacher | Get all submissions for a published assessment. |
| `POST` | `/api/teacher/assessment/<code>/toggle` | Teacher | Activate or deactivate a published assessment. |
| `GET` | `/api/teacher/assessments` | Teacher | List all published assessments for the teacher. |
| `GET` | `/api/teacher/class/<class_id>/compare` | Teacher | Compare 2-6 assessments side-by-side (class-scoped). |
| `GET` | `/api/teacher/class/<class_id>/gradebook` | Teacher | Return per-(student, assessment) canonical grades for a class. |
| `GET` | `/api/teacher/class/<class_id>/progress-rank` | Teacher | Return a class-scoped progress rank grid aggregating standards_mastery |
| `POST` | `/api/teacher/class/<class_id>/remediate` | Teacher | Phase 4 Quick-Click Remediation: generate 8 grade-level practice |
| `GET` | `/api/teacher/class/<class_id>/remediation-effectiveness` | Teacher | Phase 4.2 #6 — Remediation Effectiveness dashboard (read-only). |
| `POST` | `/api/teacher/class/<class_id>/remediation/<rem_id>/recall` | Teacher | Phase 4.2 #5: soft-recall a remediation (flip is_active=false; no quota refund). |
| `GET` | `/api/teacher/class/<class_id>/student/<student_id>/report-card` | Teacher | Return per-student report card: trajectory + standards breakdown. |
| `GET` | `/api/teacher/content/<content_id>/in-progress` | Teacher | List students currently drafting a specific piece of class-based content. |
| `GET` | `/api/teacher/content/<content_id>/submissions` | Teacher | List all submissions (all attempts per student) for a class-based assessment. |
| `POST` | `/api/teacher/delete-shared-resources-bulk` | Teacher | Delete all shared resources matching a title for this teacher. |
| `POST` | `/api/teacher/end-attempt/<submission_id>` | Teacher | Force-end a student's in-progress draft, converting it to a submitted row. |
| `POST` | `/api/teacher/published-content/<content_id>/tags` | Teacher | Replace the tags array on a published content row (either table). |
| `DELETE` | `/api/teacher/shared-resource/<resource_id>` | Teacher | Delete a single shared resource. |
| `POST` | `/api/teacher/shared-resource/<resource_id>/unit` | Teacher | Update the unit_name in a published content row's settings. |
| `GET` | `/api/teacher/shared-resources` | Teacher | List all shared resources (flashcards, study guides, slide decks) for the teacher. |
| `GET` | `/api/teacher/submission/<submission_id>/detail` | Teacher | Return per-submission detail: metadata + per-question breakdown + sibling attempts. |
| `GET` | `/api/teacher/tags` | Teacher | Return all unique tags across the teacher's published content (both tables), |

## Surveys

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| `POST` | `/api/survey/<code>/submit` | Public | Submit a parent's survey response. |
| `POST` | `/api/survey/create` | Teacher | Create a new parent survey and return the link. |
| `GET` | `/api/survey/list` | Teacher | List all surveys created by the teacher. |
| `GET` | `/api/survey/results` | Teacher | Get aggregate survey results for the teacher. |
| `GET` | `/survey/<code>` | Public | Serve the self-contained survey HTML page. |

## analytics_routes

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| `GET` | `/api/analytics` | Teacher | Load master CSV and return analytics data for charts. |
| `POST` | `/api/analytics/cleanup` | Teacher | One-time cleanup of master_grades.csv names and Approved column. |
| `GET` | `/api/export-district-report` | Teacher | Export anonymized aggregate statistics (no PII) for district reporting. |

## assessment_results_routes

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| `GET` | `/api/assessment-results` | Teacher | Return all assessments with aggregated results for the current teacher. |

## auth_routes

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| `GET` | `/api/auth/approval-status` | Public | Check whether the current user is approved. |
| `GET/POST` | `/api/auth/approve-user` | Public | One-click user approval from admin notification email. |
| `POST` | `/api/auth/notify-signup` | Public | Send admin notification email when a new user signs up. |

## document_routes

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| `POST` | `/api/parse-document` | Teacher | Parse an uploaded Word/PDF document and convert to HTML. |

## sync_routes

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| `POST` | `/api/sync/periodic-roster` | Public | Webhook endpoint for cron-triggered periodic roster sync. |
