import React from "react";
import Icon from "../components/Icon";

/*
 * AppHeaderBar — the sticky top header bar (Start/Stop grading toolbar +
 * theme toggle), relocated VERBATIM from App.jsx 2100-2167 in the finale
 * split (the "Top Header Bar" JSX comment stays at the call site).
 * Stateless; owns the data-tutorial="grade-toolbar" anchor.
 */
export default function AppHeaderBar(props) {
  const {
    handleStartGrading, handleStopGrading, status, theme, toggleTheme,
  } = props;

  return (
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              padding: "15px 30px",
              borderBottom: "1px solid var(--glass-border)",
              background: "var(--card-bg)",
              position: "sticky",
              top: 0,
              zIndex: 50,
            }}
          >
            {/* Left: Auto-Grade & Start/Stop */}
            <div data-tutorial="grade-toolbar" style={{ display: "flex", alignItems: "center", gap: "15px" }}>
              <div
                style={{
                  width: "1px",
                  height: "24px",
                  background: "var(--glass-border)",
                }}
              />
              {!status.is_running ? (
                <button
                  onClick={handleStartGrading}
                  className="btn btn-primary"
                  style={{ padding: "8px 20px" }}
                >
                  <Icon name="Play" size={16} />
                  Start Grading
                </button>
              ) : (
                <button
                  onClick={handleStopGrading}
                  className="btn btn-danger"
                  style={{ padding: "8px 20px" }}
                >
                  <Icon name="Square" size={16} />
                  Stop ({status.progress}/{status.total})
                </button>
              )}
            </div>

            {/* Right: Theme Toggle */}
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <button
              onClick={toggleTheme}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                padding: "10px",
                borderRadius: "8px",
                border: "1px solid var(--glass-border)",
                background: "var(--glass-bg)",
                color: "var(--text-primary)",
                cursor: "pointer",
              }}
              title={
                theme === "dark"
                  ? "Switch to Light Mode"
                  : "Switch to Dark Mode"
              }
            >
              <Icon name={theme === "dark" ? "Sun" : "Moon"} size={18} />
            </button>
            </div>
          </div>
  );
}
