import React from "react";
import Icon from "../Icon";

export default function NotificationsSection(props) {
  const { config, setConfig } = props;
  return (
            <div style={{ marginTop: "30px" }}>
              <h3
                style={{
                  fontSize: "1.1rem",
                  fontWeight: 700,
                  marginBottom: "15px",
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                }}
              >
                <Icon name="Bell" size={20} style={{ color: "#f59e0b" }} />
                Notifications
              </h3>
              <label
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "12px",
                  cursor: "pointer",
                  padding: "12px 16px",
                  background: "var(--input-bg)",
                  borderRadius: "12px",
                  border: "1px solid var(--input-border)",
                }}
              >
                <input
                  type="checkbox"
                  checked={config.showToastNotifications}
                  onChange={(e) =>
                    setConfig((prev) => ({
                      ...prev,
                      showToastNotifications: e.target.checked,
                    }))
                  }
                  style={{
                    width: "18px",
                    height: "18px",
                    accentColor: "var(--accent-primary)",
                    cursor: "pointer",
                  }}
                />
                <div>
                  <div style={{ fontWeight: 600, fontSize: "0.95rem" }}>
                    Toast Notifications
                  </div>
                  <div
                    style={{
                      fontSize: "0.85rem",
                      color: "var(--text-muted)",
                    }}
                  >
                    Show popup notifications when assignments are graded
                  </div>
                </div>
              </label>
            </div>
  );
}
