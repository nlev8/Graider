import React from "react";
import Icon from "../Icon";

export default function SetupWizardSection(props) {
  const { setShowOnboardingWizard } = props;
  return (
            <div style={{ marginTop: 20, paddingTop: 20, borderTop: "1px solid var(--glass-border)" }}>
              <h3 style={{ fontSize: "1rem", fontWeight: 600, marginBottom: 6 }}>Setup Wizard</h3>
              <p style={{ fontSize: "0.85rem", color: "var(--text-muted)", marginBottom: 12 }}>
                Re-run the initial setup to update your core settings.
              </p>
              <button
                onClick={() => setShowOnboardingWizard(true)}
                className="btn btn-secondary"
                style={{ display: "flex", alignItems: "center", gap: 6 }}
              >
                <Icon name="RefreshCw" size={16} />
                Run Setup Wizard Again
              </button>
            </div>
  );
}
