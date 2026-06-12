import React from "react";
import useRemediationDrawer from "./remediation-drawer/useRemediationDrawer";
import ConfigPanel from "./remediation-drawer/ConfigPanel";
import PreviewPane from "./remediation-drawer/PreviewPane";

/**
 * Phase 4 — Remediation Drawer.
 * Phase 4.2 #1: also previews + round-trips a lesson dict to publish payload.
 *
 * State machine: idle → generating → preview → (regenerating | publishing) → success | error
 *
 * CQ wave-6 split: this shell owns layout (backdrop, header, body dispatch,
 * footers, confirm dialog); state + handlers live in
 * remediation-drawer/useRemediationDrawer.js (same lifetime — the hook is
 * called only here); config/preview bodies are stateless components in
 * remediation-drawer/*.
 */
export default function RemediationDrawer({
  open, onClose, classId, standardCode, targetMode, targetStudentId, targetStudentName,
  onPublished,
}) {
  var d = useRemediationDrawer({
    open: open, onClose: onClose, classId: classId, standardCode: standardCode,
    targetMode: targetMode, targetStudentId: targetStudentId, onPublished: onPublished,
  });
  var state = d.state, data = d.data, questions = d.questions, variants = d.variants;
  var isPersonalized = d.isPersonalized;

  if (!open) return null;

  var disabled = state === "generating" || state === "regenerating" || state === "publishing";
  // Phase 4.2 #2: in personalized mode, nTargets comes from variants.length;
  // in shared mode, from data.target_student_ids.
  var nTargets = isPersonalized
    ? variants.length
    : (data && data.target_student_ids ? data.target_student_ids.length : 0);
  var subtitle = "";
  if (targetMode === "single_student") {
    subtitle = "for " + (targetStudentName || "student");
  } else if (isPersonalized) {
    subtitle = "for " + nTargets + " student" + (nTargets === 1 ? "" : "s") + " (personalized)";
  } else if (data && data.target_student_ids) {
    subtitle = "for " + nTargets + " red-tier student" + (nTargets === 1 ? "" : "s");
  }

  return (
    <>
      <div onClick={onClose}
           style={{ position: "fixed", top: 0, left: 0, right: 0, bottom: 0,
                    background: "rgba(0,0,0,0.4)", zIndex: 9499 }} />
      <div style={{
        position: "fixed", top: 0, right: 0, height: "100vh",
        width: "min(720px, 96vw)", background: "var(--card-bg)",
        zIndex: 9500, display: "flex", flexDirection: "column",
        boxShadow: "-4px 0 24px rgba(0,0,0,0.3)",
      }}>
        {/* Header */}
        <div style={{ padding: "16px 20px", borderBottom: "1px solid var(--glass-border)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
            <div>
              <h3 style={{ margin: 0, fontSize: "1rem", fontWeight: 700 }}>Remediation: {standardCode}</h3>
              <p style={{ margin: "4px 0 0", fontSize: "0.8rem", color: "var(--text-secondary)" }}>{subtitle}</p>
            </div>
            <button onClick={onClose} disabled={disabled}
                    style={{ background: "none", border: "none", cursor: "pointer", color: "var(--text-secondary)", fontSize: "1.2rem" }}>
              {String.fromCharCode(10005)}
            </button>
          </div>
        </div>

        {/* Body */}
        <div style={{ flex: 1, overflowY: "auto", padding: "16px 20px" }}>
          {state === "config" ? (
            <ConfigPanel
              configCount={d.configCount} setConfigCount={d.setConfigCount}
              configDifficulty={d.configDifficulty} setConfigDifficulty={d.setConfigDifficulty}
              configDok={d.configDok} setConfigDok={d.setConfigDok}
              disabled={disabled}
            />
          ) : state === "generating" || state === "regenerating" ? (
            <div style={{ textAlign: "center", padding: "40px 0", color: "var(--text-secondary)" }}>
              {state === "regenerating" ? "Regenerating..." : ("Generating " + d.configCount + " practice questions...")}
            </div>
          ) : state === "error" ? (
            <div style={{ padding: "20px", color: "var(--danger)", textAlign: "center" }}>
              {d.error}
              <div style={{ marginTop: "16px" }}>
                <button onClick={d.regenerateAll} className="btn btn-primary">Retry</button>
              </div>
            </div>
          ) : state === "success" ? (
            <div style={{ textAlign: "center", padding: "40px 0", color: "var(--success)" }}>
              Published to {nTargets} student{nTargets === 1 ? "" : "s"}.
            </div>
          ) : (
            <PreviewPane
              isPersonalized={isPersonalized} variants={variants}
              activeVariantIndex={d.activeVariantIndex} setActiveVariantIndex={d.setActiveVariantIndex}
              activeVariant={d.activeVariant} data={data}
              validationError={d.validationError}
              activeQuestions={d.activeQuestions} setActiveQuestions={d.setActiveQuestions}
              disabled={disabled}
            />
          )}
        </div>

        {/* Footer — config state */}
        {state === "config" && (
          <div style={{ padding: "12px 20px", borderTop: "1px solid var(--glass-border)",
                        display: "flex", gap: "8px", justifyContent: "flex-end" }}>
            {/* Phase 4.2 #3 (Codex full-PR MAJOR): Cancel preserves preview
                when prior data exists. Only fully closes when no preview to
                return to (initial open state). */}
            <button
              onClick={function() {
                if (data && (questions.length > 0 || variants.length > 0)) {
                  d.setState("preview");
                } else {
                  onClose();
                }
              }}
              disabled={disabled}
              className="btn btn-secondary"
            >
              Cancel
            </button>
            <button onClick={d.handleGenerate} disabled={disabled} className="btn btn-primary">
              Generate
            </button>
          </div>
        )}

        {/* Footer — preview / publishing state */}
        {(state === "preview" || state === "publishing") && (
          <div style={{ padding: "12px 20px", borderTop: "1px solid var(--glass-border)",
                        display: "flex", gap: "8px", justifyContent: "flex-end", flexWrap: "wrap" }}>
            <button onClick={onClose} disabled={disabled} className="btn btn-secondary">Cancel</button>
            {/* Phase 4.2 #3: Adjust settings returns to config state with
                preview state preserved (in case teacher cancels back). */}
            <button onClick={function() { d.setState("config"); }} disabled={disabled} className="btn btn-secondary">
              Adjust settings
            </button>
            <button onClick={function() { d.setConfirmRegenOpen(true); }} disabled={disabled} className="btn btn-secondary">
              Regenerate all
            </button>
            <button onClick={d.publish} disabled={disabled} className="btn btn-primary">
              {state === "publishing" ? "Publishing..." : "Publish to " + nTargets}
            </button>
          </div>
        )}

        {/* Confirm regenerate dialog */}
        {d.confirmRegenOpen && (
          <div onClick={function() { d.setConfirmRegenOpen(false); }}
               style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)",
                        zIndex: 9501, display: "flex", alignItems: "center", justifyContent: "center" }}>
            <div onClick={function(e) { e.stopPropagation(); }} className="glass-card"
                 style={{ padding: "20px", maxWidth: "400px" }}>
              <h4 style={{ marginTop: 0 }}>Regenerate all questions?</h4>
              <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>Any edits you've made will be lost.</p>
              <div style={{ display: "flex", gap: "8px", justifyContent: "flex-end" }}>
                <button onClick={function() { d.setConfirmRegenOpen(false); }} className="btn btn-secondary">Keep editing</button>
                <button onClick={d.regenerateAll} className="btn btn-primary">Regenerate</button>
              </div>
            </div>
          </div>
        )}
      </div>
    </>
  );
}
