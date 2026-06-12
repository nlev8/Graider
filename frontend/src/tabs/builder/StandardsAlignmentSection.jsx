import React from "react";
import Icon from "../../components/Icon";

/*
 * Align to Standards button + results panel — relocated verbatim from
 * BuilderTab.jsx (CQ wave-9 split). `{importedDoc && (importedDoc.text ||
 * importedDoc.html) && (...)}` at the call site became the
 * early-return-null below.
 */
export default function StandardsAlignmentSection({
  importedDoc,
  standardsAlignment,
  alignmentLoading,
  rewriteLoading,
  handleAlignToStandards,
  handleRewriteForAlignment,
}) {
  if (!(importedDoc && (importedDoc.text || importedDoc.html))) return null;
  return (
    <div style={{ marginTop: "12px", marginBottom: "20px" }}>
      <button
        className="btn btn-secondary"
        onClick={handleAlignToStandards}
        disabled={alignmentLoading}
        style={{ display: "flex", alignItems: "center", gap: "6px" }}
      >
        {alignmentLoading
          ? <><Icon name="Loader2" size={14} className="spinning" /> Analyzing Standards...</>
          : <><Icon name="BookOpen" size={14} /> Align to Standards</>}
      </button>

      {standardsAlignment && (
        <div style={{
          marginTop: "15px",
          padding: "20px",
          background: "rgba(99,102,241,0.08)",
          borderRadius: "12px",
          border: "1px solid rgba(99,102,241,0.3)",
        }}>
          {/* Overall Score */}
          <div style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: "15px" }}>
            <h4 style={{ margin: 0, fontSize: "1rem" }}>Standards Alignment</h4>
            <div style={{
              flex: 1, height: "8px", background: "rgba(255,255,255,0.1)",
              borderRadius: "4px", overflow: "hidden"
            }}>
              <div style={{
                width: Math.round((standardsAlignment.overall_alignment_score || 0) * 100) + "%",
                height: "100%",
                background: (standardsAlignment.overall_alignment_score || 0) > 0.7 ? "#4ade80"
                  : (standardsAlignment.overall_alignment_score || 0) > 0.4 ? "#fbbf24" : "#ef4444",
                borderRadius: "4px",
                transition: "width 0.5s ease",
              }} />
            </div>
            <span style={{ fontWeight: 600, minWidth: "40px", textAlign: "right" }}>
              {Math.round((standardsAlignment.overall_alignment_score || 0) * 100)}%
            </span>
          </div>

          {/* Matched Standards */}
          {(standardsAlignment.matched_standards || []).map(function(std, idx) {
            return (
              <div key={std.code || idx} style={{
                padding: "10px 12px",
                background: "var(--input-bg)",
                borderRadius: "8px",
                marginBottom: "8px",
                borderLeft: "3px solid " + (std.confidence > 0.7 ? "#4ade80" : std.confidence > 0.4 ? "#fbbf24" : "#ef4444"),
              }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <strong style={{ fontSize: "0.9rem" }}>{std.code}</strong>
                  <span style={{
                    fontSize: "0.8rem", fontWeight: 600,
                    color: std.confidence > 0.7 ? "#4ade80" : std.confidence > 0.4 ? "#fbbf24" : "#ef4444",
                  }}>{Math.round(std.confidence * 100)}% match</span>
                </div>
                <p style={{ fontSize: "0.85rem", margin: "4px 0", color: "var(--text-primary)" }}>{std.benchmark}</p>
                {std.evidence && (
                  <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", margin: "2px 0" }}>
                    <em>Evidence:</em> {std.evidence}
                  </p>
                )}
                {std.alignment_notes && (
                  <p style={{ fontSize: "0.8rem", color: "#fbbf24", margin: "2px 0" }}>{std.alignment_notes}</p>
                )}
              </div>
            );
          })}

          {/* Suggestions */}
          {(standardsAlignment.suggestions || []).length > 0 && (
            <div style={{ marginTop: "12px" }}>
              <h5 style={{ margin: "0 0 8px", fontSize: "0.9rem" }}>Improvement Suggestions</h5>
              <ul style={{ margin: 0, paddingLeft: "20px", fontSize: "0.85rem" }}>
                {standardsAlignment.suggestions.map(function(s, i) {
                  return <li key={i} style={{ marginBottom: "4px" }}>{s}</li>;
                })}
              </ul>
            </div>
          )}

          {/* Question Analysis */}
          {(standardsAlignment.question_analysis || []).filter(function(q) { return q.rewrite_suggestion; }).length > 0 && (
            <div style={{ marginTop: "15px" }}>
              <h5 style={{ margin: "0 0 8px", fontSize: "0.9rem" }}>Question-Level Analysis</h5>
              {standardsAlignment.question_analysis.filter(function(q) { return q.rewrite_suggestion; }).map(function(q, i) {
                return (
                  <div key={i} style={{
                    padding: "10px 12px",
                    background: "var(--input-bg)",
                    borderRadius: "8px",
                    marginBottom: "8px",
                  }}>
                    <p style={{ fontSize: "0.85rem", margin: "0 0 4px" }}>
                      <strong>Q:</strong> {(q.question_text || "").substring(0, 120)}{(q.question_text || "").length > 120 ? "..." : ""}
                    </p>
                    <p style={{ fontSize: "0.8rem", margin: "2px 0", color: "var(--text-secondary)" }}>
                      Aligned to: {q.aligned_standard || "None"} ({q.alignment_quality || "unknown"})
                    </p>
                    <p style={{ fontSize: "0.8rem", margin: "2px 0", color: "#fbbf24" }}>{q.rewrite_suggestion}</p>
                    <button
                      className="btn btn-secondary"
                      onClick={function() {
                        handleRewriteForAlignment([{
                          original_text: q.question_text,
                          target_standard: q.aligned_standard,
                          rewrite_goal: q.rewrite_suggestion
                        }]);
                      }}
                      disabled={rewriteLoading}
                      style={{ fontSize: "0.8rem", padding: "4px 10px", marginTop: "6px" }}
                    >
                      {rewriteLoading ? "Rewriting..." : "Rewrite This Question"}
                    </button>
                  </div>
                );
              })}
            </div>
          )}

          {/* Rewrites */}
          {standardsAlignment.rewrites && standardsAlignment.rewrites.length > 0 && (
            <div style={{ marginTop: "15px" }}>
              <h5 style={{ margin: "0 0 8px", fontSize: "0.9rem" }}>Rewritten Questions</h5>
              {standardsAlignment.rewrites.map(function(r, i) {
                return (
                  <div key={i} style={{
                    padding: "10px 12px",
                    background: "var(--input-bg)",
                    borderRadius: "8px",
                    marginBottom: "8px",
                    borderLeft: "3px solid #4ade80",
                  }}>
                    <p style={{ fontSize: "0.8rem", margin: "0 0 4px", color: "var(--text-secondary)" }}>
                      <strong>Original:</strong> {r.original_text}
                    </p>
                    <p style={{ fontSize: "0.85rem", margin: "4px 0", color: "#4ade80" }}>
                      <strong>Rewritten:</strong> {r.rewritten_text}
                    </p>
                    <p style={{ fontSize: "0.8rem", margin: "2px 0", color: "var(--text-secondary)" }}>
                      <em>{r.standard_code}:</em> {r.change_explanation}
                    </p>
                    <button
                      className="btn btn-secondary"
                      onClick={function() {
                        navigator.clipboard.writeText(r.rewritten_text);
                      }}
                      style={{ fontSize: "0.75rem", padding: "2px 8px", marginTop: "4px" }}
                    >
                      Copy Rewrite
                    </button>
                  </div>
                );
              })}
            </div>
          )}

          {/* Cost info */}
          {standardsAlignment.usage && (
            <p style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: "10px", textAlign: "right" }}>
              {standardsAlignment.usage.cost_display || ""}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
