import Icon from "../Icon";
import { STEPS } from "./constants";

// Modal chrome above the step content: progress bar, theme toggle, step indicator.
// Stateless — step/theme state lives in the shell.
export default function WizardProgressHeader(props) {
  const { step, theme, toggleTheme } = props;
  return (
    <>
      {/* Progress bar + theme toggle */}
      <div style={{
        display: "flex", alignItems: "center", gap: 8,
        padding: "20px 24px 0",
      }}>
        <div style={{ display: "flex", gap: 4, flex: 1 }}>
          {STEPS.map((_, i) => (
            <div
              key={i}
              style={{
                flex: 1, height: 4, borderRadius: 2,
                background: i <= step ? "var(--accent-primary)" : "var(--glass-border)",
                transition: "background 0.3s",
              }}
            />
          ))}
        </div>
        {toggleTheme && (
          <button
            onClick={toggleTheme}
            title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
            style={{
              width: 32, height: 32, borderRadius: 8,
              background: "var(--glass-bg)",
              border: "1px solid var(--glass-border)",
              cursor: "pointer",
              display: "flex", alignItems: "center", justifyContent: "center",
              flexShrink: 0, transition: "all 0.2s",
              color: "var(--text-primary)", padding: 0,
            }}
          >
            <Icon name={theme === "dark" ? "Sun" : "Moon"} size={16} />
          </button>
        )}
      </div>

      {/* Step indicator */}
      <div style={{
        padding: "12px 24px 0",
        fontSize: "0.75rem",
        color: "var(--text-muted)",
        textTransform: "uppercase",
        letterSpacing: "0.05em",
      }}>
        Step {step + 1} of {STEPS.length}
      </div>
    </>
  );
}
