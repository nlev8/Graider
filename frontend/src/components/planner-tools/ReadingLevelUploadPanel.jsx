import React from "react";
import Icon from "../Icon";

/*
 * Pure-prop child extracted from ReadingLevelAdjuster (CQ wave-8 split #cq8-07).
 * Renders the drop-zone, hidden file input, and uploaded-file tag list.
 * All state and handlers live in the parent; this component only renders.
 */
export default function ReadingLevelUploadPanel({
  rlExtracting,
  rlFiles,
  onDragOver,
  onDragLeave,
  onDrop,
  onDropZoneClick,
  onFileChange,
}) {
  return (
    <div style={{ marginBottom: "12px" }}>
      <div
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
        style={{ border: "2px dashed var(--input-border)", borderRadius: "8px", padding: "16px", textAlign: "center", cursor: "pointer", transition: "border-color 0.2s" }}
        onClick={onDropZoneClick}
      >
        <input
          id="rl-file-input"
          type="file"
          accept=".docx,.pdf,.txt,.png,.jpg,.jpeg,.gif,.webp"
          multiple
          style={{ display: "none" }}
          onChange={onFileChange}
        />
        {rlExtracting ? (
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: "8px", color: "#06b6d4" }}>
            <Icon name="Loader2" size={18} className="spinning" /> Extracting text...
          </div>
        ) : (
          <div>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: "6px", color: "var(--text-secondary)", fontSize: "0.85rem" }}>
              <Icon name="Upload" size={16} />
              <span>Drop files here or click to upload</span>
            </div>
            <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: "4px", opacity: 0.7 }}>
              Documents (.docx, .pdf, .txt) or screenshots (.png, .jpg)
            </div>
          </div>
        )}
      </div>
      {rlFiles.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: "6px", marginTop: "8px" }}>
          {rlFiles.map(function(name, i) {
            return (
              <span key={i} style={{ display: "inline-flex", alignItems: "center", gap: "4px", padding: "2px 8px", background: "rgba(6,182,212,0.1)", color: "#06b6d4", borderRadius: "6px", fontSize: "0.75rem" }}>
                <Icon name="FileText" size={12} /> {name}
              </span>
            );
          })}
        </div>
      )}
    </div>
  );
}
