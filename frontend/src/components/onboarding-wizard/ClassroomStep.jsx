import { GRADE_LEVELS, SUBJECTS, STATES, GRADING_PERIODS } from "./constants";

// Step 2 — Your Classroom. Stateless: wizardData + updateField live in the shell.
export default function ClassroomStep(props) {
  const { wizardData, updateField } = props;
  return (
    <div style={{ padding: "10px 0" }}>
      <h2 style={{ fontSize: "1.4rem", fontWeight: 700, marginBottom: 8 }}>Your Classroom</h2>
      <p style={{ color: "var(--text-secondary)", marginBottom: 24, fontSize: "0.95rem" }}>
        This helps Graider set age-appropriate expectations and align with your state standards.
      </p>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <div>
          <label className="label" style={{ marginBottom: 4 }}>Grade Level</label>
          <select
            className="input"
            value={wizardData.grade_level}
            onChange={(e) => updateField("grade_level", e.target.value)}
          >
            {GRADE_LEVELS.map((g) => (
              <option key={g} value={g}>{g === "K" ? "Kindergarten" : "Grade " + g}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="label" style={{ marginBottom: 4 }}>Subject</label>
          <select
            className="input"
            value={wizardData.subject}
            onChange={(e) => updateField("subject", e.target.value)}
          >
            {SUBJECTS.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="label" style={{ marginBottom: 4 }}>State</label>
          <select
            className="input"
            value={wizardData.state}
            onChange={(e) => updateField("state", e.target.value)}
          >
            {STATES.map((s) => (
              <option key={s.value} value={s.value}>{s.label}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="label" style={{ marginBottom: 4 }}>Grading Period</label>
          <select
            className="input"
            value={wizardData.grading_period}
            onChange={(e) => updateField("grading_period", e.target.value)}
          >
            {GRADING_PERIODS.map((p) => (
              <option key={p.value} value={p.value}>{p.label}</option>
            ))}
          </select>
        </div>
      </div>
    </div>
  );
}
