import React from "react";
import Icon from "../Icon";
import QuestionPlayer from "../QuestionPlayer";
import ThemeToggle from "./ThemeToggle";
import { containerStyle } from "./portalStyles";

// ============ ASSESSMENT SCREEN ============
// JSX (and the render-scoped effectiveTimeLimit computation) moved verbatim
// from StudentPortal.jsx (CQ wave-6 split). Stage guard replaces the shell's
// original `if (stage === "assessment") return (...)` block. The error banner
// rendered during stage === "assessment" (duplicate-submission fix, PR #740)
// is preserved exactly — `error` is threaded from the shell.
export default function AssessmentScreen(props) {
  const {
    stage, lightMode, setLightMode,
    assessment, deliveryAccommodations, resumedFromDraft, answers, error,
    studentName, setAnswer, handleSubmit, loading, studentAccommodation,
    contentId, saveDraftNow, savingDraft,
  } = props;
  if (stage !== "assessment") return null;

  // Compute effective time limit with extended time accommodation
  var effectiveTimeLimit = assessment?.settings?.time_limit_minutes || null;
  if (effectiveTimeLimit && deliveryAccommodations.length > 0) {
    if (deliveryAccommodations.indexOf("extended_time_unlimited") !== -1) {
      effectiveTimeLimit = null;
    } else if (deliveryAccommodations.indexOf("extended_time_2x") !== -1) {
      effectiveTimeLimit = Math.round(effectiveTimeLimit * 2);
    } else if (deliveryAccommodations.indexOf("extended_time_1_5x") !== -1) {
      effectiveTimeLimit = Math.round(effectiveTimeLimit * 1.5);
    }
  }

  return (
    <div style={containerStyle}>
      <ThemeToggle lightMode={lightMode} setLightMode={setLightMode} />
      {resumedFromDraft && (
        <div style={{
          padding: "10px 16px", marginBottom: "0",
          background: "var(--success-bg)", border: "1px solid var(--success-border)",
          borderRadius: "0", fontSize: "0.85rem", color: "var(--text-primary)",
          textAlign: "center",
        }}>
          Resumed from draft {String.fromCharCode(8212)} {Object.keys(answers).length} questions answered. Your progress auto-saves every 15 seconds.
        </div>
      )}
      {error && (
        /* Submit failures (e.g. duplicate-submission 409/400, network errors)
           land here while stage stays "assessment" — without this banner the
           student gets NO feedback at all (the confirm modal has already
           closed). Root-caused via the PR5 de-skipped duplicate-submission
           e2e (student-error-states.spec.js). Same style as the join/name
           stage banners above. */
        <div style={{ background: "var(--danger-bg)", border: "1px solid var(--danger-border)", borderRadius: "8px", padding: "12px", margin: "12px 16px", color: "var(--danger-light)", textAlign: "center" }}>
          <Icon name="AlertCircle" size={16} /> {error}
        </div>
      )}
      <QuestionPlayer
        sections={
          assessment?.sections
            ? assessment.sections
            : (assessment?.questions
                ? [{ name: "Practice", questions: assessment.questions }]
                : [])
        }
        lesson={assessment?.lesson || (assessment?.content && assessment.content.lesson) || null}
        contentType={assessment?.settings?.content_type || "assessment"}
        settings={assessment?.settings || {}}
        accommodations={deliveryAccommodations}
        effectiveTimeLimit={effectiveTimeLimit}
        studentName={studentName}
        title={assessment?.title}
        answers={answers}
        onAnswer={setAnswer}
        onSubmit={handleSubmit}
        loading={loading}
        assessment={assessment}
        studentAccommodation={studentAccommodation}
        lightMode={lightMode}
      />
      {contentId && (
        <div style={{ textAlign: "center", padding: "16px 20px 24px" }}>
          <button
            type="button"
            onClick={saveDraftNow}
            disabled={savingDraft}
            style={{ padding: "12px 24px", borderRadius: "10px", background: "var(--btn-secondary-bg)", border: "1px solid var(--glass-border)", color: "var(--text-primary)", fontSize: "1rem", cursor: "pointer" }}
          >
            {savingDraft ? 'Saving...' : 'Save for later'}
          </button>
        </div>
      )}
    </div>
  );
}
