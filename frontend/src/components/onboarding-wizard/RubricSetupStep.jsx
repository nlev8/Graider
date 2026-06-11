import Icon from "../Icon";
import { RUBRIC_PRESETS, getPresetForStateSubject } from "../../data/rubricPresets";

// Step 4 — Rubric Setup. Stateless: rubricChoice state lives in the shell
// (it is read again by the summary step and handleComplete).
export default function RubricSetupStep(props) {
  const { wizardData, rubricChoice, setRubricChoice } = props;
  const isFL = wizardData.state === "FL";
  const matchedPreset = getPresetForStateSubject(wizardData.state, wizardData.subject);
  const standardPreset = RUBRIC_PRESETS.default;

  const renderPresetCard = (preset, selected, onClick) => (
    <button
      onClick={onClick}
      style={{
        display: "block", width: "100%", textAlign: "left",
        padding: "16px",
        background: selected ? "rgba(99,102,241,0.15)" : "var(--glass-bg)",
        border: selected ? "2px solid var(--accent-primary)" : "1px solid var(--glass-border)",
        borderRadius: 12, cursor: "pointer",
        transition: "all 0.2s",
        color: "var(--text-primary)", fontFamily: "inherit",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
        <span style={{ fontWeight: 600, fontSize: "1rem" }}>{preset.name}</span>
        {preset.badge && (
          <span style={{
            padding: "2px 8px", borderRadius: 6, fontSize: "0.7rem", fontWeight: 600,
            background: "rgba(99,102,241,0.2)", color: "#818cf8",
          }}>
            {preset.badge}
          </span>
        )}
        {selected && <Icon name="Check" size={16} style={{ color: "var(--accent-primary)", marginLeft: "auto" }} />}
      </div>
      <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginBottom: 10 }}>
        {preset.description}
      </p>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
        {preset.categories.map((cat) => (
          <span key={cat.name} style={{
            padding: "4px 10px", borderRadius: 6, fontSize: "0.75rem",
            background: "var(--input-bg)", color: "var(--text-secondary)",
          }}>
            {cat.name} {cat.weight}%
          </span>
        ))}
      </div>
    </button>
  );

  return (
    <div style={{ padding: "10px 0" }}>
      <h2 style={{ fontSize: "1.4rem", fontWeight: 700, marginBottom: 8 }}>Rubric Setup</h2>
      <p style={{ color: "var(--text-secondary)", marginBottom: 20, fontSize: "0.95rem" }}>
        {isFL
          ? "We matched a B.E.S.T.-aligned rubric for your subject. You can customize it later in Settings."
          : "Choose a starting rubric for grading. You can customize it later in Settings."}
      </p>

      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        {/* Show B.E.S.T. preset for FL if different from standard */}
        {isFL && matchedPreset.badge && (
          renderPresetCard(
            matchedPreset,
            rubricChoice === "preset",
            () => setRubricChoice("preset")
          )
        )}

        {/* Standard rubric option */}
        {renderPresetCard(
          standardPreset,
          isFL ? rubricChoice === "standard" : rubricChoice === "preset",
          () => setRubricChoice(isFL ? "standard" : "preset")
        )}

        {/* Customize later */}
        <button
          onClick={() => setRubricChoice("custom")}
          style={{
            display: "flex", alignItems: "center", gap: 10,
            padding: "12px 16px",
            background: rubricChoice === "custom" ? "rgba(99,102,241,0.15)" : "var(--glass-bg)",
            border: rubricChoice === "custom" ? "2px solid var(--accent-primary)" : "1px solid var(--glass-border)",
            borderRadius: 12, cursor: "pointer",
            transition: "all 0.2s", textAlign: "left",
            color: "var(--text-primary)", fontFamily: "inherit",
          }}
        >
          <Icon name="Settings" size={18} style={{ color: "var(--text-secondary)" }} />
          <div>
            <span style={{ fontWeight: 600, fontSize: "0.95rem" }}>Customize Later</span>
            <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", margin: 0 }}>
              Keep your current rubric and adjust in Settings
            </p>
          </div>
          {rubricChoice === "custom" && <Icon name="Check" size={16} style={{ color: "var(--accent-primary)", marginLeft: "auto" }} />}
        </button>
      </div>
    </div>
  );
}
