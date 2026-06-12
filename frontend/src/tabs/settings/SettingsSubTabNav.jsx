import React from "react";
import Icon from "../../components/Icon";

/*
 * SettingsSubTabNav — the Settings sub-tab button strip, relocated verbatim
 * from SettingsTab.jsx (CQ wave-9 split). Stateless: active tab + setter and
 * the Clever flag (hides Billing for Clever SSO users) arrive as props.
 */
export default function SettingsSubTabNav({ settingsTab, setSettingsTab, isCleverUser }) {
  return (
          <div style={{ display: "flex", gap: "4px", marginBottom: "20px", borderBottom: "1px solid var(--glass-border)", paddingBottom: "12px", flexWrap: "wrap" }}>
            {[
              { id: "general", label: "General", icon: "FolderOpen" },
              { id: "grading", label: "Grading", icon: "ClipboardCheck" },
              { id: "ai", label: "AI", icon: "Sparkles" },
              { id: "classroom", label: "Classroom", icon: "Users" },
              /* Tools tab removed — Clever handles integration */
              { id: "privacy", label: "Privacy", icon: "Shield" },
              ...(!isCleverUser ? [{ id: "billing", label: "Billing", icon: "CreditCard" }] : []),
              { id: "resources", label: "Resources", icon: "FolderOpen" },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setSettingsTab(tab.id)}
                style={{
                  padding: "8px 14px",
                  borderRadius: "8px",
                  border: "none",
                  background: settingsTab === tab.id ? "var(--accent-primary)" : "transparent",
                  color: settingsTab === tab.id ? "white" : "var(--text-secondary)",
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  gap: "6px",
                  fontSize: "0.85rem",
                  fontWeight: settingsTab === tab.id ? 600 : 500,
                  transition: "all 0.2s",
                }}
              >
                <Icon name={tab.icon} size={16} />
                {tab.label}
              </button>
            ))}
          </div>
  );
}
