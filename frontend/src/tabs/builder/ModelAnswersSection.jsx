import React from "react";
import Icon from "../../components/Icon";

/*
 * Generate Model Answers button + count — relocated verbatim from
 * BuilderTab.jsx (CQ wave-9 split). `{assignment.customMarkers &&
 * assignment.customMarkers.length > 0 && importedDoc && (importedDoc.text
 * || importedDoc.html) && (...)}` at the call site became the
 * early-return-null below.
 */
export default function ModelAnswersSection({
  assignment,
  importedDoc,
  modelAnswersLoading,
  handleGenerateModelAnswers,
}) {
  if (!(assignment.customMarkers && assignment.customMarkers.length > 0
        && importedDoc && (importedDoc.text || importedDoc.html))) return null;
  return (
    <div style={{ marginTop: "12px", marginBottom: "12px" }}>
      <button className="btn btn-secondary" onClick={handleGenerateModelAnswers}
        disabled={modelAnswersLoading}
        style={{ display: "flex", alignItems: "center", gap: "6px" }}>
        {modelAnswersLoading
          ? <><Icon name="Loader2" size={14} className="spinning" /> Generating...</>
          : <><Icon name="Sparkles" size={14} /> Generate Model Answers</>}
      </button>
      {assignment.modelAnswers && Object.keys(assignment.modelAnswers).length > 0 && (
        <span style={{ marginLeft: "8px", fontSize: "12px", color: "var(--text-secondary)", marginTop: "4px", display: "inline-block" }}>
          {Object.keys(assignment.modelAnswers).length + " sections answered"}
        </span>
      )}
    </div>
  );
}
