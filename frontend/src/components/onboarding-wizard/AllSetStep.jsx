import Icon from "../Icon";
import { RUBRIC_PRESETS, getPresetForStateSubject } from "../../data/rubricPresets";
import { STATES, GRADING_PERIODS, GRADING_STYLES } from "./constants";

// Step 7 — All Set! summary. Stateless: reads shell state via props;
// handleComplete stays in the shell (it writes config/rubric and exits the wizard).
export default function AllSetStep(props) {
  const { wizardData, rubricChoice, hasAnyApiKey, isSSOUser, isCleverUser, handleComplete } = props;
  const selectedPreset = rubricChoice === "preset"
    ? getPresetForStateSubject(wizardData.state, wizardData.subject)
    : rubricChoice === "standard"
      ? RUBRIC_PRESETS.default
      : null;

  const summaryItems = [
    { icon: "User", label: "Teacher", value: wizardData.teacher_name },
    { icon: "School", label: "School", value: wizardData.school_name || "Not set" },
    { icon: "BookOpen", label: "Subject", value: "Grade " + wizardData.grade_level + " " + wizardData.subject },
    { icon: "MapPin", label: "State", value: STATES.find((s) => s.value === wizardData.state)?.label || wizardData.state },
    { icon: "Calendar", label: "Period", value: GRADING_PERIODS.find((p) => p.value === wizardData.grading_period)?.label || wizardData.grading_period },
    { icon: "ClipboardCheck", label: "Style", value: GRADING_STYLES.find((s) => s.value === wizardData.gradingStyle)?.label || wizardData.gradingStyle },
    { icon: "ClipboardList", label: "Rubric", value: selectedPreset ? selectedPreset.name : "Custom (unchanged)" },
    { icon: "Cpu", label: "AI Provider", value: hasAnyApiKey ? "Connected" : "Not configured" },
    { icon: "Users", label: "Roster", value: isSSOUser ? (isCleverUser ? "Clever" : "ClassLink") + " (auto-sync)" : "Manual upload" },
  ];

  return (
    <div style={{ textAlign: "center", padding: "10px 0" }}>
      <div style={{
        width: 64, height: 64, borderRadius: "50%",
        background: "linear-gradient(135deg, #22c55e, #16a34a)",
        display: "flex", alignItems: "center", justifyContent: "center",
        margin: "0 auto 20px",
      }}>
        <Icon name="Check" size={32} style={{ color: "#fff" }} />
      </div>
      <h2 style={{ fontSize: "1.4rem", fontWeight: 700, marginBottom: 8 }}>You're All Set!</h2>
      <p style={{ color: "var(--text-secondary)", marginBottom: 24, fontSize: "0.95rem" }}>
        Here's a summary of your setup. You can change any of these in Settings.
      </p>
      <div style={{
        background: "var(--glass-bg)",
        border: "1px solid var(--glass-border)",
        borderRadius: 12, padding: 16,
        textAlign: "left", marginBottom: 16,
      }}>
        {summaryItems.map((item, i) => (
          <div
            key={i}
            style={{
              display: "flex", alignItems: "center", gap: 12,
              padding: "10px 0",
              borderBottom: i < summaryItems.length - 1 ? "1px solid var(--glass-border)" : "none",
            }}
          >
            <Icon name={item.icon} size={18} style={{ color: "var(--text-secondary)", flexShrink: 0 }} />
            <span style={{ fontSize: "0.85rem", color: "var(--text-secondary)", width: 80, flexShrink: 0 }}>
              {item.label}
            </span>
            <span style={{ fontSize: "0.95rem", fontWeight: 500 }}>
              {item.value}
            </span>
          </div>
        ))}
      </div>
      <button
        onClick={() => handleComplete("builder")}
        className="btn btn-secondary"
        style={{
          display: "inline-flex", alignItems: "center", gap: 8,
          padding: "10px 20px", fontSize: "0.95rem",
        }}
      >
        <Icon name="Plus" size={18} />
        Create Your First Assignment
      </button>
    </div>
  );
}
