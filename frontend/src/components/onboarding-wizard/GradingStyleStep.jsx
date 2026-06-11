import Icon from "../Icon";
import { GRADING_STYLES } from "./constants";

// Step 3 — Grading Style. Stateless: wizardData + updateField live in the shell.
export default function GradingStyleStep(props) {
  const { wizardData, updateField } = props;
  return (
    <div style={{ padding: "10px 0" }}>
      <h2 style={{ fontSize: "1.4rem", fontWeight: 700, marginBottom: 8 }}>Grading Style</h2>
      <p style={{ color: "var(--text-secondary)", marginBottom: 24, fontSize: "0.95rem" }}>
        Choose how Graider approaches grading. You can change this anytime in Settings.
      </p>
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        {GRADING_STYLES.map((style) => {
          const isSelected = wizardData.gradingStyle === style.value;
          return (
            <button
              key={style.value}
              onClick={() => updateField("gradingStyle", style.value)}
              style={{
                display: "flex", alignItems: "center", gap: 16,
                padding: "16px 20px",
                background: isSelected ? "rgba(99,102,241,0.15)" : "var(--glass-bg)",
                border: isSelected ? "2px solid var(--accent-primary)" : "1px solid var(--glass-border)",
                borderRadius: 12, cursor: "pointer",
                textAlign: "left", transition: "all 0.2s",
                color: "var(--text-primary)", fontFamily: "inherit",
              }}
            >
              <div style={{
                width: 44, height: 44, borderRadius: 10,
                background: isSelected ? style.color + "22" : "var(--glass-bg)",
                border: "1px solid " + (isSelected ? style.color : "var(--glass-border)"),
                display: "flex", alignItems: "center", justifyContent: "center",
                flexShrink: 0,
              }}>
                <Icon name={style.icon} size={22} style={{ color: isSelected ? style.color : "var(--text-secondary)" }} />
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 600, fontSize: "1rem", marginBottom: 2 }}>
                  {style.label}
                  {isSelected && (
                    <Icon name="Check" size={16} style={{ color: "var(--accent-primary)", marginLeft: 8 }} />
                  )}
                </div>
                <div style={{ fontSize: "0.85rem", color: "var(--text-secondary)", lineHeight: 1.4 }}>
                  {style.description}
                </div>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
