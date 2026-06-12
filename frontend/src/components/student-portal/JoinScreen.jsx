import React from "react";
import Icon from "../Icon";
import ThemeToggle from "./ThemeToggle";
import { containerStyle, cardStyle, inputStyle, buttonStyle, subtextColor } from "./portalStyles";

// ============ JOIN SCREEN ============
// JSX moved verbatim from StudentPortal.jsx (CQ wave-6 split). The shell's
// original `if (stage === ...) return (...)` chain becomes a guard here:
// stage state stays in the shell; this screen early-returns null when
// inactive, so the rendered tree is unchanged.
export default function JoinScreen(props) {
  const {
    stage, lightMode, setLightMode,
    joinCode, setJoinCode, handleJoin, error, loading,
  } = props;
  if (stage !== "join" && stage !== "loading") return null;

  return (
    <div style={containerStyle}>
      <ThemeToggle lightMode={lightMode} setLightMode={setLightMode} />
      <div style={{ padding: "40px 20px", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", minHeight: "100vh" }}>
        <div style={{ textAlign: "center", marginBottom: "40px" }}>
          <h1 style={{ fontSize: "2.5rem", fontWeight: 800, marginBottom: "10px", display: "flex", alignItems: "center", justifyContent: "center", gap: "12px" }}>
            <Icon name="FileText" size={36} /> Graider
          </h1>
          <p style={{ color: subtextColor, fontSize: "1.1rem" }}>
            Enter your join code to get started
          </p>
        </div>

        <div style={cardStyle}>
          <form onSubmit={handleJoin}>
            <div style={{ marginBottom: "20px" }}>
              <label style={{ display: "block", marginBottom: "10px", fontWeight: 600 }}>
                Join Code
              </label>
              <input
                type="text"
                value={joinCode}
                onChange={(e) => setJoinCode(e.target.value.toUpperCase())}
                placeholder="ABC123"
                maxLength={6}
                style={inputStyle}
                autoFocus
              />
            </div>

            {error && (
              <div style={{ background: "var(--danger-bg)", border: "1px solid var(--danger-border)", borderRadius: "8px", padding: "12px", marginBottom: "20px", color: "var(--danger-light)" }}>
                <Icon name="AlertCircle" size={16} /> {error}
              </div>
            )}

            <button type="submit" disabled={loading} style={buttonStyle}>
              {loading ? (
                <>
                  <Icon name="Loader" /> Loading...
                </>
              ) : (
                <>
                  Join <Icon name="ArrowRight" />
                </>
              )}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
