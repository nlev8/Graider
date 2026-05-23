import React from "react";
import Icon from "./Icon";
import * as api from "../services/api";

export default function SettingsGeneral({ addToast, adminClaimCode, adminClaimResult, adminStatus, availableStates, config, setAdminClaimCode, setAdminClaimResult, setAdminStatus, setConfig, setShowOnboardingWizard, setShowVportalPassword, setVportalConfigured, setVportalPassword, setVportalSaving, showVportalPassword, vportalConfigured, vportalPassword, vportalSaving }) {
  return (
              <div data-tutorial="settings-general">

            {/* Teacher & School Info */}
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(2, 1fr)",
                gap: "20px",
              }}
            >
              <div>
                <label className="label">Teacher Name</label>
                <input
                  type="text"
                  className="input"
                  value={config.teacher_name}
                  onChange={(e) =>
                    setConfig((prev) => ({
                      ...prev,
                      teacher_name: e.target.value,
                    }))
                  }
                  placeholder="Mr. Smith"
                />
              </div>
              <div>
                <label className="label">Teacher Email</label>
                <input
                  type="email"
                  className="input"
                  value={config.teacher_email}
                  onChange={(e) =>
                    setConfig((prev) => ({
                      ...prev,
                      teacher_email: e.target.value,
                    }))
                  }
                  placeholder="teacher@school.edu"
                />
                <span style={{ fontSize: "0.75rem", color: "#888", marginTop: "4px", display: "block" }}>
                  Students will reply to this email
                </span>
              </div>
              <div>
                <label className="label">School Name</label>
                <input
                  type="text"
                  className="input"
                  value={config.school_name}
                  onChange={(e) =>
                    setConfig((prev) => ({
                      ...prev,
                      school_name: e.target.value,
                    }))
                  }
                  placeholder="Lincoln Middle School"
                />
              </div>
            </div>

            {/* State, Grade Level, Subject */}
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(3, 1fr)",
                gap: "20px",
                marginTop: "20px",
              }}
            >
              <div>
                <label className="label">State</label>
                <select
                  className="input"
                  value={config.state}
                  onChange={(e) =>
                    setConfig((prev) => ({
                      ...prev,
                      state: e.target.value,
                    }))
                  }
                >
                  {availableStates.length > 0 ? availableStates.map((s) => (
                    <option key={s.code} value={s.code}>{s.name}</option>
                  )) : (
                    <option value={config.state}>{config.state}</option>
                  )}
                </select>
              </div>

              <div>
                <label className="label">Grade Level</label>
                <select
                  className="input"
                  value={config.grade_level}
                  onChange={(e) =>
                    setConfig((prev) => ({
                      ...prev,
                      grade_level: e.target.value,
                    }))
                  }
                >
                  <option value="6">6th Grade</option>
                  <option value="7">7th Grade</option>
                  <option value="8">8th Grade</option>
                  <option value="9">9th Grade</option>
                  <option value="10">10th Grade</option>
                  <option value="11">11th Grade</option>
                  <option value="12">12th Grade</option>
                </select>
              </div>

              <div>
                <label className="label">Subject</label>
                <select
                  className="input"
                  value={config.subject}
                  onChange={(e) =>
                    setConfig((prev) => ({
                      ...prev,
                      subject: e.target.value,
                    }))
                  }
                >
                  <option value="US History">U.S. History</option>
                  <option value="World History">World History</option>
                  <option value="Social Studies">Social Studies</option>
                  <option value="Civics">Civics</option>
                  <option value="Geography">Geography</option>
                  <option value="English/ELA">English/ELA</option>
                  <option value="Math">Math</option>
                  <option value="Science">Science</option>
                  <option value="Spanish">Spanish</option>
                  <option value="French">French</option>
                  <option value="World Languages">World Languages</option>
                  <option value="Other">Other</option>
                </select>
              </div>
            </div>

            {/* Email Signature */}
            <div>
              <label className="label">Email Signature</label>
              <textarea
                className="input"
                value={config.email_signature}
                onChange={(e) =>
                  setConfig((prev) => ({
                    ...prev,
                    email_signature: e.target.value,
                  }))
                }
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.stopPropagation();
                  }
                }}
                placeholder={"Best regards," + String.fromCharCode(10) + "Mr. Smith" + String.fromCharCode(10) + "Room 204 | Office Hours: Mon-Fri 3-4pm"}
                rows={4}
                style={{ resize: "vertical", minHeight: "100px", fontFamily: "inherit", lineHeight: "1.5" }}
              />
              <span style={{ fontSize: "0.75rem", color: "#888", marginTop: "4px", display: "block" }}>
                Appears at the end of grade feedback emails
              </span>
            </div>

            {/* Admin Access */}
            <div style={{ marginTop: "30px" }}>
              <h3 style={{ fontSize: "1.1rem", fontWeight: 700, marginBottom: "15px", display: "flex", alignItems: "center", gap: "8px" }}>
                <Icon name="Shield" size={20} style={{ color: "#6366f1" }} />
                Admin Access
              </h3>
              {adminStatus && adminStatus.is_admin ? (
                <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                  <span style={{ display: "inline-block", padding: "6px 14px", borderRadius: "8px", fontSize: "0.85rem", fontWeight: 600, background: "rgba(34,197,94,0.12)", color: "#22c55e", border: "1px solid rgba(34,197,94,0.25)" }}>
                    {"School Admin \u2014 " + (adminStatus.school || "Your School")}
                  </span>
                </div>
              ) : (
                <div>
                  <p style={{ fontSize: "0.85rem", color: "#888", marginBottom: "10px" }}>
                    Enter an invite code from your district administrator to gain school admin access.
                  </p>
                  <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
                    <input
                      className="input"
                      value={adminClaimCode}
                      onChange={function(e) { setAdminClaimCode(e.target.value); }}
                      placeholder="Enter invite code"
                      style={{ maxWidth: "250px" }}
                    />
                    <button
                      className="btn btn-sm"
                      style={{ background: "#6366f1", color: "#fff", border: "none", padding: "8px 16px", borderRadius: "8px", fontWeight: 600, cursor: "pointer" }}
                      onClick={function() {
                        if (!adminClaimCode.trim()) return;
                        setAdminClaimResult(null);
                        api.claimAdmin(adminClaimCode.trim()).then(function(data) {
                          if (data && data.error) {
                            setAdminClaimResult({ error: data.error });
                          } else {
                            setAdminClaimResult({ success: true });
                            setAdminStatus({ is_admin: true, school: data.school || '' });
                            setAdminClaimCode('');
                          }
                        }).catch(function() {
                          setAdminClaimResult({ error: "Failed to claim admin access" });
                        });
                      }}
                    >
                      Claim Access
                    </button>
                  </div>
                  {adminClaimResult && adminClaimResult.error && (
                    <div style={{ color: "#ef4444", fontSize: "0.85rem", marginTop: "8px" }}>{adminClaimResult.error}</div>
                  )}
                  {adminClaimResult && adminClaimResult.success && (
                    <div style={{ color: "#22c55e", fontSize: "0.85rem", marginTop: "8px" }}>Admin access granted successfully!</div>
                  )}
                </div>
              )}
            </div>

            {/* Gradebook / SIS Integration */}
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

            {/* Notifications */}
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
              </div>
  );
}
