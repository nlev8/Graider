import React from "react";

// Five selectable design systems for slide decks. Pure-prop: value + onChange.
const TEMPLATES = [
  { key: "editorial-bold", name: "Editorial Bold", blurb: "Magazine serif, refined" },
  { key: "vibrant-gradient", name: "Vibrant Gradient", blurb: "Bold gradient keynote" },
  { key: "cinematic", name: "Cinematic Dark", blurb: "Dark, neon, dramatic" },
  { key: "playful-organic", name: "Playful Organic", blurb: "Warm, rounded, younger grades" },
  { key: "minimal", name: "Minimal / Swiss", blurb: "Clean, structured (default)" },
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
