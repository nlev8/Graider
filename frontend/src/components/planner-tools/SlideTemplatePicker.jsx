import React from "react";

// Four selectable design systems for slide decks. Pure-prop: value + onChange.
const TEMPLATES = [
  { key: "editorial", name: "Editorial", blurb: "Minimal, serif, upper grades" },
  { key: "bold", name: "Bold", blurb: "Gradient, big type, wow" },
  { key: "academic", name: "Academic", blurb: "Clean, structured (default)" },
  { key: "playful", name: "Playful", blurb: "Rounded, warm, younger grades" },
];

export default function SlideTemplatePicker({ value, onChange }) {
  return (
    <div>
      <label style={{ fontSize: "0.85rem", fontWeight: 600, display: "block", marginBottom: "6px" }}>
        Template
      </label>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: "8px" }}>
        {TEMPLATES.map(function (t) {
          const selected = value === t.key;
          return (
            <button
              key={t.key}
              type="button"
              onClick={function () { onChange(t.key); }}
              style={{
                textAlign: "left", padding: "10px 12px", cursor: "pointer",
                borderRadius: "8px",
                border: selected ? "2px solid var(--accent, #6366f1)" : "1px solid var(--glass-border)",
                background: selected ? "rgba(99,102,241,0.08)" : "transparent",
                color: "var(--text-primary)",
              }}
            >
              <div style={{ fontWeight: 700, fontSize: "0.85rem" }}>{t.name}</div>
              <div style={{ fontSize: "0.72rem", color: "var(--text-secondary)" }}>{t.blurb}</div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
