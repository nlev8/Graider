import React from "react";
import Icon from "../Icon";
import * as api from "../../services/api";

export default function AdminAccessSection(props) {
  const { adminClaimCode, adminClaimResult, adminStatus, setAdminClaimCode, setAdminClaimResult, setAdminStatus } = props;
  return (
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
  );
}
