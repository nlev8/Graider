import Icon from "../Icon";

// Step 0 — Welcome. Stateless: all wizard state lives in OnboardingWizard.jsx
// (steps render conditionally, so any local state here would reset on navigation).
export default function WelcomeStep(props) {
  const { isCleverUser } = props;
  return (
    <div style={{ textAlign: "center", padding: "20px 0" }}>
      <div style={{
        width: 80, height: 80, borderRadius: "50%",
        background: "linear-gradient(135deg, var(--accent-primary), var(--accent-secondary))",
        display: "flex", alignItems: "center", justifyContent: "center",
        margin: "0 auto 24px",
      }}>
        <img src="/graider-brain-dark.png" alt="Graider" style={{ width: 48, height: 48 }} />
      </div>
      <h2 style={{ fontSize: "1.75rem", fontWeight: 700, marginBottom: 12 }}>
        Welcome to Graider!
      </h2>
      <p style={{ fontSize: "1.05rem", color: "var(--text-secondary)", lineHeight: 1.6, maxWidth: 420, margin: "0 auto" }}>
        Your AI-powered grading assistant. Let's get you set up in just a few quick steps so Graider can work best for your classroom.
      </p>
      {!isCleverUser && (
        <div style={{
          marginTop: 20, padding: "12px 16px", maxWidth: 460, margin: "20px auto 0",
          background: "rgba(245, 158, 11, 0.08)", border: "1px solid rgba(245, 158, 11, 0.2)",
          borderRadius: 10, fontSize: "0.85rem", color: "#fbbf24", lineHeight: 1.5,
          textAlign: "left",
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6, fontWeight: 600 }}>
            <Icon name="AlertTriangle" size={14} />
            AI Services Notice
          </div>
          Graider uses AI services (OpenAI, Anthropic) to grade assignments and generate content.
          Some school networks may restrict access to these services. If you experience connectivity issues,
          check with your IT department.
        </div>
      )}
    </div>
  );
}
