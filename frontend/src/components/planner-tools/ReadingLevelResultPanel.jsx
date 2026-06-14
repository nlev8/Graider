import React from "react";
import Icon from "../Icon";

/*
 * Pure-prop child extracted from ReadingLevelAdjuster (CQ wave-8 split #cq8-07).
 * Renders the adjusted-text result, vocabulary changes table, and usage cost.
 * All state and handlers live in the parent; this component only renders.
 */
export default function ReadingLevelResultPanel({ rlResult, onCopy }) {
  return (
    <div style={{ borderTop: "1px solid var(--glass-border)", paddingTop: "16px", marginTop: "8px" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "12px" }}>
        <span style={{ fontSize: "0.85rem", fontWeight: 600, color: "var(--text-secondary)" }}>
          Estimated reading level: <span style={{ color: "#06b6d4", fontWeight: 700 }}>{rlResult.reading_level_estimate}</span>
        </span>
        <button
          onClick={onCopy}
          className="btn btn-secondary"
          style={{ padding: "4px 12px", fontSize: "0.8rem" }}
        >
          <Icon name="Copy" size={14} /> Copy
        </button>
      </div>
      <div style={{ padding: "12px", background: "var(--input-bg)", borderRadius: "8px", fontSize: "0.9rem", lineHeight: 1.6, color: "var(--text-primary)", whiteSpace: "pre-wrap", maxHeight: "300px", overflowY: "auto", marginBottom: "12px" }}>
        {rlResult.adjusted_text}
      </div>
      {rlResult.vocabulary_changes && rlResult.vocabulary_changes.length > 0 && (
        <div>
          <h4 style={{ fontSize: "0.85rem", fontWeight: 600, color: "var(--text-secondary)", marginBottom: "8px" }}>Vocabulary Changes</h4>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "4px 16px", fontSize: "0.8rem" }}>
            {rlResult.vocabulary_changes.map(function(vc, i) {
              return (
                <React.Fragment key={i}>
                  <span style={{ color: "var(--text-secondary)", textDecoration: "line-through" }}>{vc.original}</span>
                  <span style={{ color: "#06b6d4", fontWeight: 500 }}>{vc.replacement}</span>
                </React.Fragment>
              )
            })}
          </div>
        </div>
      )}
      {rlResult.usage && (
        <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: "12px", textAlign: "right" }}>
          {rlResult.usage.cost_display}
        </div>
      )}
    </div>
  );
}
