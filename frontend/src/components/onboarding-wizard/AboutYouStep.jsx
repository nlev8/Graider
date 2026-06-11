import Icon from "../Icon";

// Step 1 — About You. Stateless: wizardData + updateField live in the shell.
export default function AboutYouStep(props) {
  const { wizardData, updateField, isCleverUser } = props;
  return (
    <div style={{ padding: "10px 0" }}>
      <h2 style={{ fontSize: "1.4rem", fontWeight: 700, marginBottom: 8 }}>About You</h2>
      <p style={{ color: "var(--text-secondary)", marginBottom: 24, fontSize: "0.95rem" }}>
        Tell us a little about yourself so we can personalize your experience.
      </p>
      {isCleverUser && wizardData.teacher_name && (
        <div style={{
          display: "flex", alignItems: "center", gap: 8,
          padding: "8px 12px", borderRadius: 8, marginBottom: 16,
          background: "rgba(34,197,94,0.08)", border: "1px solid rgba(34,197,94,0.2)",
          fontSize: "0.82rem", color: "#22c55e",
        }}>
          <Icon name="CheckCircle" size={14} />
          Pre-filled from your Clever account
        </div>
      )}
      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <div>
          <label className="label" style={{ marginBottom: 4 }}>Teacher Name *</label>
          <input
            className="input"
            placeholder="e.g. Ms. Johnson"
            value={wizardData.teacher_name}
            onChange={(e) => updateField("teacher_name", e.target.value)}
            autoFocus
          />
        </div>
        <div>
          <label className="label" style={{ marginBottom: 4 }}>Email Address</label>
          <input
            className="input"
            type="email"
            placeholder="e.g. johnson@school.edu"
            value={wizardData.teacher_email}
            onChange={(e) => updateField("teacher_email", e.target.value)}
          />
        </div>
        <div>
          <label className="label" style={{ marginBottom: 4 }}>School Name</label>
          <input
            className="input"
            placeholder="e.g. Lincoln Middle School"
            value={wizardData.school_name}
            onChange={(e) => updateField("school_name", e.target.value)}
          />
        </div>
      </div>
    </div>
  );
}
