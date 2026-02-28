commit 25d67d30a159ddee49d51dd6341d611bcf276c8f
Author: Alexander Crionas <nlev8@icloud.com>
Date:   Fri Feb 27 23:11:05 2026 -0500

    Add behavior tracking feature (manual + Whisper STT), confirmation email improvements, and post-beta plan
    
    Includes: behavior panel sidebar, local Whisper STT hooks, backend persistence,
    assistant tools for behavior summaries/emails, and confirmation emails for all
    roster students (not just those with files).
    
    Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>

diff --git a/POST_BETA_PLAN.md b/POST_BETA_PLAN.md
new file mode 100644
index 0000000..1f6525f
--- /dev/null
+++ b/POST_BETA_PLAN.md
@@ -0,0 +1,49 @@
+# Post-Beta Plan
+
+## SharePoint Filename Truncation & Assignment Matching
+
+SharePoint truncates long filenames, which breaks the Analytics word-overlap matching (requires 60% of config title words to appear in the filename). Currently fixed per-assignment by manually adding aliases.
+
+**Idea**: Auto-detect truncated filenames by lowering the match threshold when a filename appears cut off (e.g., ends mid-word or with a parenthetical). Or, when importing an assignment config, auto-generate a short alias from the title's first few distinctive words. This would eliminate the need for manual alias maintenance as new assignments are added.
+
+---
+
+## Behavior Tracking
+
+Ambitious but coherent scope: local Whisper STT feeds a behavior panel, with backend persistence and assistant tools for summaries/emails. Architecture diagram clarifies browser-only audio and new backend pieces.
+
+Biggest risk is front-end complexity: loading a 150 MB Whisper model, continuous audio processing, pending queues, tally tables, and behavior stores all wired into the existing Assistant tab. This will take substantial effort (hooks, components, UI polish), so be sure the team has bandwidth — this isn't a small feature.
+
+### Key Considerations
+
+**Whisper performance & permissions**
+- Whisper-base at ~150 MB + WASM will strain lower-end Chromebooks. Consider offering a smaller q4/Q5 model or gating the feature with a compatibility check.
+- Microphone permission prompts could conflict with other voice features (Assistant voice mode). The plan says to pause when voiceModeActive is true, but also ensure there's a single shared audio pipeline so the browser isn't juggling multiple streams.
+
+**Name detection reliability**
+- Regex boundary matching on first/last names will produce false positives (e.g., "Mark" in "remark"). Plan says skip names <3 chars, but still expect noise. The UI must make pending approvals fast; teachers won't tolerate constant false alarms.
+- Students with identical names need extra context (last name, period). Make sure the roster includes unique IDs and the UI surfaces them.
+
+**Local storage and session recoverability**
+- Backing up session data every 500 ms is great for crash recovery, but you need a clear flow for resuming after refresh: show a prompt ("Resume last session?") so teachers don't accidentally double-log events.
+- Clearing on "End Session" must also wipe pending events; otherwise stale data may linger.
+
+**Backend persistence & privacy**
+- behavior_routes write to ~/.graider_data/behavior_tracking.json. Make sure this file is encrypted or at least documented; it contains sensitive behavior notes. FERPA compliance isn't just about audio.
+- Deleting data (DELETE /api/behavior/data) should support pruning by date range; the plan says "clear student/all" but administrators may mandate automatic retention limits (e.g., 90 days).
+
+**Assistant tools & parent emails**
+- Sending behavior emails via Resend may run into the same district filtering issues noted elsewhere. Consider offering the Outlook/Focus automation path first, or at least flag to the teacher that Resend might be blocked.
+- Tool prompts must cap what the assistant can say; ensure generate_behavior_email templates are empathetic and that send_behavior_email verifies parent contact info exists (and handles cases with multiple guardians).
+
+**UI integration**
+- Embedding a 320 px sidebar in the Assistant tab might make the chat cramped on smaller screens. Provide a global toggle to hide the behavior panel entirely (feature gating).
+- Visual indicators (LIVE badge, listening status) need to be very clear so teachers know when the mic is hot.
+
+**Testing & rollout**
+- Given the sensitive nature, start with manual log only. Gate Whisper behind an experimental flag until accuracy is acceptable.
+- Provide a kill switch in settings to disable behavior tracking entirely (and ensure no hooks load Whisper unless explicitly enabled).
+
+### Recommended Phasing
+
+Ship manual logging + backend APIs first, then layer in STT once the core flows are stable.
