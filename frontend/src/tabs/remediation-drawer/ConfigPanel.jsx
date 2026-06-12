import React from "react";

// Pre-generation config body for RemediationDrawer. JSX moved verbatim from
// the `state === "config"` branch of the drawer body (CQ wave-6 split).
// Stateless — config state stays in useRemediationDrawer.
export default function ConfigPanel({
  configCount, setConfigCount, configDifficulty, setConfigDifficulty,
  configDok, setConfigDok, disabled,
}) {
  return (
    /* Phase 4.2 #3: pre-generation config dialog. Slider for count
       (3-15) + three-button difficulty toggle. */
    <div style={{ display: "flex", flexDirection: "column", gap: "20px", maxWidth: "480px" }}>
      <div>
        <h4 style={{ margin: "0 0 4px", fontSize: "0.95rem", fontWeight: 700 }}>Configure remediation</h4>
        <p style={{ margin: 0, fontSize: "0.8rem", color: "var(--text-secondary)" }}>
          Set length and difficulty before generating.
        </p>
      </div>
      <div>
        <label style={{ display: "block", fontSize: "0.85rem", fontWeight: 600, marginBottom: "6px" }}>
          Question count: <span style={{ color: "var(--accent-primary)" }}>{configCount}</span>
        </label>
        <input
          type="range"
          min={3}
          max={15}
          step={1}
          value={configCount}
          onChange={function(e) { setConfigCount(parseInt(e.target.value, 10)); }}
          disabled={disabled}
          style={{ width: "100%" }}
        />
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.7rem", color: "var(--text-muted)", marginTop: "2px" }}>
          <span>3</span>
          <span>15</span>
        </div>
      </div>
      <div>
        <label style={{ display: "block", fontSize: "0.85rem", fontWeight: 600, marginBottom: "6px" }}>
          Difficulty
        </label>
        <div style={{ display: "flex", gap: "6px" }}>
          {["easier", "same", "harder"].map(function(diff) {
            var active = diff === configDifficulty;
            return (
              <button key={diff}
                      onClick={function() { setConfigDifficulty(diff); }}
                      disabled={disabled}
                      style={{
                        flex: 1, padding: "8px 12px", fontSize: "0.85rem",
                        borderRadius: "6px", fontWeight: active ? 700 : 500,
                        border: active ? "1px solid var(--accent-primary)" : "1px solid var(--glass-border)",
                        background: active ? "rgba(99,102,241,0.15)" : "transparent",
                        color: active ? "var(--accent-primary)" : "var(--text-primary)",
                        cursor: disabled ? "not-allowed" : "pointer",
                        textTransform: "capitalize",
                      }}>
                {diff}
              </button>
            );
          })}
        </div>
        <p style={{ margin: "6px 0 0", fontSize: "0.72rem", color: "var(--text-muted)" }}>
          {configDifficulty === "easier"
            ? "Simpler vocabulary, more scaffolding."
            : configDifficulty === "harder"
            ? "More challenging vocabulary, higher cognitive demand."
            : "Grade-level review."}
        </p>
      </div>
      {/* Phase 4.2 #12: DOK (Webb's Depth of Knowledge) toggle.
          null = Auto (no DOK directive); 1-4 = explicit cognitive
          rigor target. Coexists with difficulty (orthogonal —
          difficulty is vocab/scaffolding tone). */}
      <div>
        <label style={{ display: "block", fontSize: "0.85rem", fontWeight: 600, marginBottom: "6px" }}>
          Cognitive demand (DOK)
        </label>
        <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
          {[null, 1, 2, 3, 4].map(function(level) {
            var active = level === configDok;
            var label = level === null ? "Auto" : String(level);
            return (
              <button key={String(level)}
                      onClick={function() { setConfigDok(level); }}
                      disabled={disabled}
                      style={{
                        flex: "1 1 60px", padding: "8px 12px", fontSize: "0.85rem",
                        borderRadius: "6px", fontWeight: active ? 700 : 500,
                        border: active ? "1px solid var(--accent-primary)" : "1px solid var(--glass-border)",
                        background: active ? "rgba(99,102,241,0.15)" : "transparent",
                        color: active ? "var(--accent-primary)" : "var(--text-primary)",
                        cursor: disabled ? "not-allowed" : "pointer",
                      }}>
                {label}
              </button>
            );
          })}
        </div>
        <p style={{ margin: "6px 0 0", fontSize: "0.72rem", color: "var(--text-muted)" }}>
          {configDok === null
            ? "AI picks the cognitive level appropriate to the standard."
            : configDok === 1 ? "DOK 1 — Recall & Reproduction."
            : configDok === 2 ? "DOK 2 — Skills & Concepts."
            : configDok === 3 ? "DOK 3 — Strategic Thinking."
            : "DOK 4 — Extended Thinking."}
        </p>
      </div>
    </div>
  );
}
