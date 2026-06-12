import * as api from "../../services/api";

// Publish-promise construction for RemediationDrawer. Moved verbatim from the
// body of publish() in RemediationDrawer.jsx (CQ wave-6 split). The shared vs
// personalized branching, payload shapes, and api calls are unchanged — the
// caller (useRemediationDrawer) still owns validation, state transitions, and
// the .then/.catch handling of the returned promise.
export function buildPublishPromise({ isPersonalized, variants, questions, data, classId, standardCode }) {
  var publishPromise;
  if (isPersonalized) {
    // Phase 4.2 #2: atomic batch publish — N rows written in a single
    // PostgREST INSERT. The drawer issues ONE call, not N.
    var items = variants.map(function(v) {
      var contentPayload = { questions: v.questions || [] };
      if (v.lesson) contentPayload.lesson = v.lesson;
      return {
        content: contentPayload,
        target_student_ids: [v.student_id],
        settings: { target_standard: standardCode },
        title: "Remediation: " + standardCode,
      };
    });
    publishPromise = api.publishToClassBatch(classId, items, "assessment");
  } else {
    // Phase 4.2 #1: round-trip the validated lesson dict (or null) through
    // to publish_to_class so it lands in published_content.content JSONB.
    var sharedContentPayload = { questions: questions };
    if (data && data.lesson) sharedContentPayload.lesson = data.lesson;
    publishPromise = api.publishToClass(
      classId,
      sharedContentPayload,
      "assessment",
      "Remediation: " + standardCode,
      // Phase 4.2 #6: persist target_standard so the Effectiveness dashboard
      // can attribute mastery delta without parsing title.
      { target_standard: standardCode },
      null,  // dueDate — none
      data.target_student_ids,
    );
  }
  return publishPromise;
}
