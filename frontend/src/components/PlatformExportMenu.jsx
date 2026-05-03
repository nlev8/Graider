/**
 * PlatformExportMenu — small dropdown that lists external assessment
 * platforms (Wayground, CSV, Canvas QTI, Kahoot, Quizlet, Google Forms)
 * the teacher can export the current assessment to. Anchored absolute,
 * meant to be positioned by its (relatively-positioned) parent.
 *
 * Extracted from App.jsx (2026-05-02) — was inline JSX gated by
 * `showPlatformExport`. Presentational; the actual export action and
 * close-on-select stay in App.jsx via `onSelect`.
 *
 * Props:
 *   open: bool
 *   onSelect: (platformId) => void  — called with the chosen platform's
 *                                     id; caller is responsible for
 *                                     dispatching the export and closing
 *                                     the menu.
 */
import React from "react";
import Icon from "./Icon";

const PLATFORMS = [
  { id: "wayground", name: "Wayground", icon: "FileSpreadsheet" },
  { id: "csv", name: "CSV (Generic)", icon: "Table" },
  { id: "canvas_qti", name: "Canvas (QTI)", icon: "GraduationCap" },
  { id: "kahoot", name: "Kahoot", icon: "Gamepad2" },
  { id: "quizlet", name: "Quizlet", icon: "BookOpen" },
  { id: "google_forms", name: "Google Forms", icon: "FormInput" },
];

export default function PlatformExportMenu({ open, onSelect }) {
  if (!open) return null;

  return (
    <div
      style={{
        position: "absolute",
        top: "100%",
        right: 0,
        marginTop: "5px",
        background: "var(--surface)",
        border: "1px solid var(--glass-border)",
        borderRadius: "10px",
        boxShadow: "0 10px 40px rgba(0,0,0,0.3)",
        zIndex: 100,
        minWidth: "200px",
        overflow: "hidden",
      }}
    >
      {PLATFORMS.map((platform) => (
        <button
          key={platform.id}
          onClick={() => onSelect(platform.id)}
          style={{
            display: "flex",
            alignItems: "center",
            gap: "10px",
            width: "100%",
            padding: "12px 16px",
            background: "transparent",
            border: "none",
            borderBottom: "1px solid var(--glass-border)",
            color: "var(--text-primary)",
            cursor: "pointer",
            textAlign: "left",
            fontSize: "0.9rem",
          }}
          onMouseEnter={(e) => (e.target.style.background = "var(--glass-hover)")}
          onMouseLeave={(e) => (e.target.style.background = "transparent")}
        >
          <Icon name={platform.icon} size={18} />
          {platform.name}
        </button>
      ))}
    </div>
  );
}
