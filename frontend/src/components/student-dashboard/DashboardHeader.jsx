import React from "react";
import Icon from "../Icon";

// ============ DASHBOARD HEADER ============
// JSX moved verbatim from StudentDashboard.jsx (CQ wave-7 split): the
// student-name/class header bar with the theme toggle and Log Out button.
// State (lightMode) and the logout handler stay in the always-mounted
// StudentDashboard shell; this component only renders them.
export default function DashboardHeader(props) {
  const { studentInfo, classInfo, lightMode, setLightMode, handleLogout } = props;

  return (
    <div style={{
      background: "var(--header-bg)", borderBottom: "1px solid var(--glass-border)",
      padding: "16px 24px", display: "flex", justifyContent: "space-between", alignItems: "center",
    }}>
      <div>
        <h1 style={{ fontSize: "1.2rem", fontWeight: 700, margin: 0 }}>
          {studentInfo.first_name} {studentInfo.last_name}
        </h1>
        <p style={{ color: "var(--text-secondary)", fontSize: "0.8rem", margin: "2px 0 0" }}>
          {classInfo.name}{classInfo.subject ? " \u2022 " + classInfo.subject : ""}
        </p>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
        <button
          onClick={function() {
            var next = !lightMode;
            setLightMode(next);
            var theme = next ? "light" : "dark";
            document.body.setAttribute("data-theme", theme);
            localStorage.setItem("portal-theme", theme);
          }}
          style={{
            padding: "8px", borderRadius: "8px", background: "var(--btn-secondary-bg)",
            border: "none", cursor: "pointer", color: "var(--text-secondary)",
          }}
          title={lightMode ? "Switch to dark mode" : "Switch to light mode"}
        >
          <Icon name={lightMode ? "Moon" : "Sun"} size={18} />
        </button>
        <button onClick={handleLogout} style={{
          padding: "8px 16px", borderRadius: "8px", background: "var(--danger-bg)",
          border: "1px solid var(--danger-border)", color: "var(--danger-light)", cursor: "pointer",
          fontSize: "0.85rem",
        }}>
          Log Out
        </button>
      </div>
    </div>
  );
}
