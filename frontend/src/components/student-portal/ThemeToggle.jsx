import React from "react";
import Icon from "../Icon";

// Theme toggle button, moved verbatim from the `themeToggle` JSX local in
// StudentPortal.jsx (CQ wave-6 split). Now a component instead of a per-render
// element variable; the shell passes the same lightMode state + setter the
// inline element closed over, so the onClick body and markup are unchanged.
export default function ThemeToggle({ lightMode, setLightMode }) {
  return (
    <button
      onClick={function() {
        var next = !lightMode;
        setLightMode(next);
        var theme = next ? "light" : "dark";
        document.body.setAttribute("data-theme", theme);
        localStorage.setItem("portal-theme", theme);
      }}
      style={{
        position: "fixed", top: "12px", right: "12px", zIndex: 200,
        background: "var(--btn-secondary-bg)",
        border: "none", borderRadius: "8px", padding: "8px",
        cursor: "pointer", color: "var(--text-secondary)",
      }}
      title={lightMode ? "Switch to dark mode" : "Switch to light mode"}
    >
      <Icon name={lightMode ? "Moon" : "Sun"} size={18} />
    </button>
  );
}
