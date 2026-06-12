import React from "react";
import LessonBlock from "../../components/LessonBlock";
import QuestionCard from "./QuestionCard";

// Preview body for RemediationDrawer: variant tab strip (personalized mode),
// lesson preview, inline validation banner, editable question cards. JSX
// moved verbatim from the preview branch of the drawer body (CQ wave-6
// split). Stateless — all state stays in useRemediationDrawer.
export default function PreviewPane({
  isPersonalized, variants, activeVariantIndex, setActiveVariantIndex,
  activeVariant, data, validationError, activeQuestions, setActiveQuestions,
  disabled,
}) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
      {/* Phase 4.2 #2: tab strip when personalized. One tab per
          variant; click to switch the preview pane. */}
      {isPersonalized && (
        <div style={{
          display: "flex", flexWrap: "wrap", gap: "6px",
          borderBottom: "1px solid var(--glass-border)", paddingBottom: "8px",
        }}>
          {variants.map(function(v, vi) {
            var active = vi === activeVariantIndex;
            return (
              <button key={v.student_id || vi}
                      onClick={function() { setActiveVariantIndex(vi); }}
                      disabled={disabled}
                      style={{
                        padding: "6px 12px", fontSize: "0.8rem",
                        borderRadius: "6px",
                        border: active ? "1px solid var(--accent-primary)" : "1px solid var(--glass-border)",
                        background: active ? "rgba(99,102,241,0.15)" : "transparent",
                        color: active ? "var(--accent-primary)" : "var(--text-primary)",
                        cursor: disabled ? "not-allowed" : "pointer",
                        fontWeight: active ? 700 : 500,
                      }}>
                {v.student_name || v.student_id}
              </button>
            );
          })}
        </div>
      )}
      {/* Phase 4.2 #1: lesson preview above questions. In personalized
          mode, show the active variant's lesson; in shared mode, the
          shared one. */}
      {isPersonalized
        ? (activeVariant && activeVariant.lesson && <LessonBlock lesson={activeVariant.lesson} />)
        : (data && data.lesson && <LessonBlock lesson={data.lesson} />)
      }
      {validationError && (
        <div style={{
          padding: "10px 14px", borderRadius: "6px",
          background: "rgba(239,68,68,0.15)", color: "var(--danger)",
          fontSize: "0.85rem", border: "1px solid var(--danger)",
        }}>
          {validationError}
        </div>
      )}
      {activeQuestions.map(function(q, idx) {
        return (
          <QuestionCard key={idx} index={idx} question={q} disabled={disabled}
                        onChange={function(updated) {
                          setActiveQuestions(function(prev) {
                            var copy = prev.slice();
                            copy[idx] = updated;
                            return copy;
                          });
                        }} />
        );
      })}
    </div>
  );
}
