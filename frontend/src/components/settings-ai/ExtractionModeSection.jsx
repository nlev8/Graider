import React from "react";
import Icon from "../Icon";

export default function ExtractionModeSection(props) {
  const { config, setConfig } = props;
  return (
              <div style={{ marginTop: "20px", padding: "15px", background: "var(--input-bg)", borderRadius: "10px", border: "1px solid var(--input-border)" }}>
                <div style={{ marginBottom: "10px" }}>
                  <span style={{ fontWeight: 600 }}>
                    <Icon name="FileSearch" size={16} style={{ marginRight: "6px", verticalAlign: "middle" }} />
                    Response Extraction Mode
                  </span>
                </div>
                <div style={{ display: "flex", gap: "10px" }}>
                  <label style={{
                    display: "flex", alignItems: "center", gap: "8px", padding: "10px 15px",
                    borderRadius: "8px", cursor: "pointer",
                    background: config.extraction_mode === "structured" ? "rgba(59, 130, 246, 0.2)" : "transparent",
                    border: config.extraction_mode === "structured" ? "1px solid rgba(59, 130, 246, 0.5)" : "1px solid var(--input-border)"
                  }}>
                    <input
                      type="radio"
                      name="extraction_mode"
                      value="structured"
                      checked={config.extraction_mode === "structured"}
                      onChange={(e) => setConfig((prev) => ({ ...prev, extraction_mode: e.target.value }))}
                    />
                    <div>
                      <div style={{ fontWeight: 500 }}>Structured</div>
                      <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>Parse with rules</div>
                    </div>
                  </label>
                  <label style={{
                    display: "flex", alignItems: "center", gap: "8px", padding: "10px 15px",
                    borderRadius: "8px", cursor: "pointer",
                    background: config.extraction_mode === "ai" ? "rgba(139, 92, 246, 0.2)" : "transparent",
                    border: config.extraction_mode === "ai" ? "1px solid rgba(139, 92, 246, 0.5)" : "1px solid var(--input-border)"
                  }}>
                    <input
                      type="radio"
                      name="extraction_mode"
                      value="ai"
                      checked={config.extraction_mode === "ai"}
                      onChange={(e) => setConfig((prev) => ({ ...prev, extraction_mode: e.target.value }))}
                    />
                    <div>
                      <div style={{ fontWeight: 500 }}>AI-Powered</div>
                      <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>Let AI identify responses</div>
                    </div>
                  </label>
                </div>
                <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginTop: "10px" }}>
                  {config.extraction_mode === "structured"
                    ? "Uses parsing rules to separate questions from answers. More predictable but may miss edge cases."
                    : "Sends raw content to AI and lets it identify what's a prompt vs student response. More flexible."}
                </p>
              </div>
  );
}
