import React from "react";
import Icon from "../Icon";
import * as api from "../../services/api";

export default function GradebookIntegrationSection(props) {
  const { addToast, config, setConfig, setShowVportalPassword, setVportalConfigured, setVportalPassword, setVportalSaving, showVportalPassword, vportalConfigured, vportalPassword, vportalSaving } = props;
  return (
            <div style={{ marginTop: "30px" }}>
              <h3 style={{ fontSize: "1.1rem", fontWeight: 700, marginBottom: "15px", display: "flex", alignItems: "center", gap: "8px" }}>
                <Icon name="Building2" size={20} style={{ color: "#6366f1" }} />
                Gradebook Integration
              </h3>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: "20px" }}>
                <div>
                  <label className="label">Student Information System</label>
                  <select className="input" value={config.sis_type || 'csv'} onChange={(e) => setConfig((prev) => ({...prev, sis_type: e.target.value}))}>
                    <option value="csv">CSV Export Only</option>
                    <option value="focus">Focus SIS</option>
                  </select>
                </div>
              </div>
              <div style={{ marginTop: "20px", padding: "16px", background: "var(--input-bg)", borderRadius: "12px", border: "1px solid var(--input-border)" }}>
                <div style={{ fontWeight: 600, fontSize: "0.95rem", marginBottom: "8px" }}>District Portal</div>
                <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "12px" }}>
                  Enter your district portal password to enable gradebook automation and email sending. Uses your Teacher Email above for login.
                </p>
                <div style={{ display: "flex", flexDirection: "column", gap: "12px", maxWidth: "400px" }}>
                  <div>
                    <label style={{ fontSize: "0.85rem", fontWeight: 600, display: "block", marginBottom: "6px" }}>Portal Password</label>
                    <div style={{ position: "relative" }}>
                      <input
                        type={showVportalPassword ? "text" : "password"}
                        value={vportalPassword}
                        onChange={(e) => setVportalPassword(e.target.value)}
                        placeholder={vportalConfigured ? "••••••••" : "Enter password"}
                        style={{ width: "100%", padding: "10px 14px", paddingRight: "44px", background: "var(--input-bg)", border: "1px solid var(--input-border)", borderRadius: "10px", color: "var(--text-primary)", fontSize: "0.9rem", outline: "none" }}
                      />
                      <button type="button" onClick={() => setShowVportalPassword(!showVportalPassword)} style={{ position: "absolute", right: "10px", top: "50%", transform: "translateY(-50%)", background: "none", border: "none", cursor: "pointer", padding: "4px", color: "var(--text-secondary)", display: "flex", alignItems: "center" }} title={showVportalPassword ? "Hide password" : "Show password"}>
                        <Icon name={showVportalPassword ? "EyeOff" : "Eye"} size={18} />
                      </button>
                    </div>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                    <button
                      onClick={async () => {
                        if (!config.teacher_email || !vportalPassword) {
                          addToast("Please enter your Teacher Email above and portal password", "error");
                          return;
                        }
                        setVportalSaving(true);
                        try {
                          await api.savePortalCredentials(config.teacher_email, vportalPassword);
                          setVportalConfigured(true);
                          setVportalPassword("");
                          setShowVportalPassword(false);
                          addToast("Portal credentials saved", "success");
                        } catch (err) {
                          addToast("Failed to save credentials: " + err.message, "error");
                        }
                        setVportalSaving(false);
                      }}
                      className="btn btn-primary"
                      style={{ padding: "8px 16px" }}
                      disabled={vportalSaving}
                    >
                      {vportalSaving ? "Saving..." : "Save Credentials"}
                    </button>
                    {vportalConfigured && (
                      <span style={{ display: "inline-flex", alignItems: "center", gap: "4px", fontSize: "0.8rem", color: "var(--success)" }}>
                        <Icon name="CheckCircle2" size={14} />
                        Configured
                      </span>
                    )}
                  </div>
                </div>
              </div>
            </div>
  );
}
