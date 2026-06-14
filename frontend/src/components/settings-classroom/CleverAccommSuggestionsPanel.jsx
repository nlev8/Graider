import React from "react";
import Icon from "../Icon";
import * as api from "../../services/api";
import { getAuthHeaders } from "../../services/api";

export default function CleverAccommSuggestionsPanel({ addToast, cleverAccommSuggestions, cleverApplying, setCleverAccommSuggestions, setCleverApplying, setStudentAccommodations }) {
  if (!(cleverAccommSuggestions && Object.keys(cleverAccommSuggestions).length > 0)) return null;
  return (
                  <div style={{
                    background: "rgba(245,158,11,0.08)", borderRadius: "8px", padding: "12px 15px",
                    marginBottom: "15px", border: "1px solid rgba(245,158,11,0.3)",
                  }}>
                    <div style={{ fontSize: "0.85rem", fontWeight: 600, marginBottom: "8px", display: "flex", alignItems: "center", gap: "8px" }}>
                      <Icon name="Shield" size={16} style={{ color: "#f59e0b" }} />
                      IEP/ELL Accommodation Suggestions
                      <span style={{
                        padding: "2px 8px", borderRadius: 6, fontSize: "0.7rem", fontWeight: 600,
                        background: "rgba(245,158,11,0.2)", color: "#f59e0b",
                      }}>
                        {Object.keys(cleverAccommSuggestions).length} students
                      </span>
                    </div>
                    <p style={{ fontSize: "0.82rem", color: "var(--text-secondary)", marginBottom: "10px" }}>
                      Clever detected these students have IEP or ELL flags. Review and apply accommodation presets:
                    </p>
                    <div style={{ maxHeight: "200px", overflowY: "auto", marginBottom: "10px" }}>
                      {Object.entries(cleverAccommSuggestions).map(function(entry) {
                        var studentId = entry[0];
                        var info = entry[1];
                        return (
                          <div key={studentId} style={{
                            display: "flex", alignItems: "center", gap: "10px",
                            padding: "6px 0", borderBottom: "1px solid var(--glass-border)",
                            fontSize: "0.85rem",
                          }}>
                            <span style={{ fontWeight: 500, minWidth: "120px" }}>{info.name}</span>
                            <div style={{ display: "flex", gap: "4px", flexWrap: "wrap" }}>
                              {info.iep_status && (
                                <span style={{ padding: "2px 6px", borderRadius: 4, fontSize: "0.72rem", background: "rgba(244,114,182,0.2)", color: "#f472b6" }}>IEP</span>
                              )}
                              {info.ell_status && (
                                <span style={{ padding: "2px 6px", borderRadius: 4, fontSize: "0.72rem", background: "rgba(96,165,250,0.2)", color: "#60a5fa" }}>ELL</span>
                              )}
                              {info.home_language && info.home_language !== "English" && (
                                <span style={{ padding: "2px 6px", borderRadius: 4, fontSize: "0.72rem", background: "var(--input-bg)", color: "var(--text-muted)" }}>{info.home_language}</span>
                              )}
                            </div>
                            <span style={{ fontSize: "0.78rem", color: "var(--text-muted)", marginLeft: "auto" }}>
                              {(info.suggested_presets || []).join(", ")}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                    <button
                      onClick={async function() {
                        setCleverApplying(true);
                        try {
                          var authHdrs = await getAuthHeaders();
                          var resp = await fetch("/api/clever/apply-accommodations", {
                            method: "POST",
                            headers: { "Content-Type": "application/json", ...authHdrs },
                            body: JSON.stringify({ accommodations: cleverAccommSuggestions }),
                          });
                          var data = await resp.json();
                          if (data.errors && data.errors.length > 0) {
                            addToast("Applied " + data.applied + "/" + data.total + " (some errors)", "warning");
                          } else {
                            addToast("Applied accommodations for " + data.applied + " students", "success");
                          }
                          setCleverAccommSuggestions(null);
                          // Refresh accommodations
                          var accommData = await api.getStudentAccommodations();
                          setStudentAccommodations(accommData.accommodations || {});
                        } catch (err) {
                          addToast("Failed to apply accommodations: " + err.message, "error");
                        }
                        setCleverApplying(false);
                      }}
                      className="btn btn-primary"
                      disabled={cleverApplying}
                      style={{ opacity: cleverApplying ? 0.6 : 1 }}
                    >
                      <Icon name="Check" size={18} />
                      {cleverApplying ? "Applying..." : "Apply All Accommodations"}
                    </button>
                  </div>
  );
}
