import React from "react";

// Apply Accommodations Toggle.
// JSX moved verbatim from PublishContentModal.jsx (CQ wave-7 split). The
// shell's original `{settings.periodFilename &&
// Object.keys(studentAccommodations).length > 0 && (...)}` gate becomes the
// guard here.
export default function AccommodationsToggle({ settings, setSettings, studentAccommodations }) {
  if (!(settings.periodFilename && Object.keys(studentAccommodations).length > 0)) return null;

  return (
    <div style={{ marginBottom: "20px" }}>
      <label
        style={{
          display: "flex",
          alignItems: "center",
          gap: "10px",
          cursor: "pointer",
          padding: "12px 15px",
          background: settings.applyAccommodations ? "rgba(59, 130, 246, 0.1)" : "rgba(255,255,255,0.05)",
          border: settings.applyAccommodations ? "1px solid #3b82f6" : "1px solid rgba(255,255,255,0.15)",
          borderRadius: "8px",
        }}
      >
        <input
          type="checkbox"
          checked={settings.applyAccommodations}
          onChange={(e) => setSettings({ ...settings, applyAccommodations: e.target.checked })}
          style={{ width: "18px", height: "18px", accentColor: "#3b82f6" }}
        />
        <div>
          <div style={{ fontWeight: 600 }}>Apply IEP/504 Accommodations</div>
          <div style={{ fontSize: "0.85rem", color: "#94a3b8" }}>
            Students with accommodations will see modified instructions
          </div>
        </div>
      </label>
    </div>
  );
}
