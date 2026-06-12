import React from "react";
import Icon from "../Icon";

// Actions footer — Cancel + Publish CTA.
// JSX moved verbatim from PublishContentModal.jsx (CQ wave-7 split).
// `publishDisabled` stays derived in the shell (it gates the publish
// action, which the shell's caller owns).
export default function ModalActions({
  isAssessment,
  settings,
  publishing,
  publishDisabled,
  onClose,
  onPublish,
}) {
  return (
    <div style={{ display: "flex", gap: "10px", justifyContent: "flex-end" }}>
      <button
        onClick={() => onClose()}
        className="btn btn-secondary"
        style={{ padding: "10px 20px" }}
      >
        Cancel
      </button>
      <button
        onClick={onPublish}
        disabled={publishDisabled}
        className="btn btn-primary"
        style={{
          padding: "10px 24px",
          background: settings.contentType === 'assignment' ? "linear-gradient(135deg, #22c55e, #16a34a)" : "linear-gradient(135deg, #8b5cf6, #6366f1)",
        }}
      >
        <Icon name={publishing ? "Loader" : "Share2"} size={16} />
        {publishing ? "Publishing..." : 'Publish ' + (isAssessment ? 'Assessment' : 'Assignment')}
      </button>
    </div>
  );
}
