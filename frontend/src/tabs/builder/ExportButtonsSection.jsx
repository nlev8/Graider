import React from "react";
import Icon from "../../components/Icon";

/*
 * Save / export buttons row — relocated verbatim from BuilderTab.jsx
 * (CQ wave-9 split).
 */
export default function ExportButtonsSection({ assignment, saveAssignmentConfig, exportAssignment }) {
  return (
    <div
      data-tutorial="builder-save"
      style={{
        display: "flex",
        gap: "15px",
        flexWrap: "wrap",
        alignItems: "center",
      }}
    >
      {assignment.title && (
        <span
          style={{
            display: "flex",
            alignItems: "center",
            gap: "6px",
            color: "#4ade80",
            fontSize: "0.85rem",
            padding: "8px 12px",
            background: "rgba(74,222,128,0.1)",
            border: "1px solid rgba(74,222,128,0.3)",
            borderRadius: "8px",
          }}
        >
          <Icon
            name="Check"
            size={14}
            style={{ color: "#4ade80" }}
          />
          Auto-saves
        </span>
      )}
      <button
        onClick={saveAssignmentConfig}
        disabled={!assignment.title}
        className="btn btn-secondary"
        style={{ opacity: !assignment.title ? 0.5 : 1 }}
      >
        <Icon name="Save" size={18} /> Save Now
      </button>
      <button
        onClick={() => exportAssignment("docx")}
        disabled={!assignment.title}
        className="btn btn-secondary"
        style={{ opacity: !assignment.title ? 0.5 : 1 }}
      >
        <Icon name="FileText" size={18} /> Export Word Doc
      </button>
      <button
        onClick={() => exportAssignment("pdf")}
        disabled={!assignment.title}
        className="btn btn-secondary"
        style={{ opacity: !assignment.title ? 0.5 : 1 }}
      >
        <Icon name="FileType" size={18} /> Export PDF
      </button>
    </div>
  );
}
