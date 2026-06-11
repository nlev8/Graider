import React from "react";
import Icon from "../Icon";
import * as api from "../../services/api";
import { getAuthHeaders } from "../../services/api";

export default function CleverSyncSection({ addToast, cleverAccommSuggestions, cleverApplying, cleverSelectedSections, cleverSyncResult, cleverSyncing, isCleverUser, setCleverAccommSuggestions, setCleverApplying, setCleverSelectedSections, setCleverSyncResult, setCleverSyncing, setPeriods, setStudentAccommodations }) {
  if (!(isCleverUser)) return null;
  return (
              <div
                style={{
                  borderTop: "1px solid var(--glass-border)",
                  paddingTop: "25px",
                  marginTop: "25px",
                }}
              >
                <h3
                  style={{
                    fontSize: "1.1rem",
                    fontWeight: 700,
                    marginBottom: "15px",
                    display: "flex",
                    alignItems: "center",
                    gap: "10px",
                  }}
                >
                  <Icon name="RefreshCw" size={20} style={{ color: "#6366f1" }} />
                  Clever Roster Sync
                  <span style={{
                    padding: "2px 8px", borderRadius: 6, fontSize: "0.7rem", fontWeight: 600,
                    background: "rgba(34,197,94,0.15)", color: "#22c55e", marginLeft: "auto",
                  }}>
                    Connected
                  </span>
                </h3>
                <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "15px" }}>
                  Your roster syncs automatically from Clever. Select which sections to import, then click Sync.
                </p>

                {/* Sync button */}
                <div style={{ display: "flex", gap: "10px", marginBottom: "15px", alignItems: "center" }}>
                  <button
                    onClick={async () => {
                      setCleverSyncing(true);
                      setCleverSyncResult(null);
                      setCleverAccommSuggestions(null);
                      try {
                        var selectedIds = Object.keys(cleverSelectedSections).filter(function(k) { return cleverSelectedSections[k]; });
                        var body = selectedIds.length > 0 ? { section_ids: selectedIds } : {};
                        var authHdrs = await getAuthHeaders();
                        var resp = await fetch("/api/clever/sync-roster", {
                          method: "POST",
                          headers: { "Content-Type": "application/json", ...authHdrs },
                          body: JSON.stringify(body),
                        });
                        var data = await resp.json();
                        if (data.error) {
                          addToast("Sync failed: " + data.error, "error");
                        } else {
                          setCleverSyncResult(data);
                          // Pre-select all available sections if none were selected
                          if (data.available_sections && Object.keys(cleverSelectedSections).length === 0) {
                            var allSelected = {};
                            data.available_sections.forEach(function(s) { allSelected[s.clever_section_id] = true; });
                            setCleverSelectedSections(allSelected);
                          }
                          if (data.accommodation_suggestions && Object.keys(data.accommodation_suggestions).length > 0) {
                            setCleverAccommSuggestions(data.accommodation_suggestions);
                          }
                          addToast("Synced " + data.counts.students + " students, " + data.counts.sections + " sections", "success");
                          // Refresh periods list
                          var periodsData = await api.listPeriods();
                          setPeriods(periodsData.periods || []);
                        }
                      } catch (err) {
                        addToast("Sync failed: " + err.message, "error");
                      }
                      setCleverSyncing(false);
                    }}
                    className="btn btn-primary"
                    disabled={cleverSyncing}
                    style={{ opacity: cleverSyncing ? 0.6 : 1 }}
                  >
                    <Icon name="RefreshCw" size={18} style={cleverSyncing ? { animation: "spin 1s linear infinite" } : {}} />
                    {cleverSyncing ? "Syncing..." : "Sync from Clever"}
                  </button>
                  {cleverSyncResult && (
                    <span style={{ fontSize: "0.82rem", color: "var(--text-secondary)" }}>
                      {cleverSyncResult.counts.students} students, {cleverSyncResult.counts.sections} sections
                      {cleverSyncResult.counts.students_with_accommodations > 0 && (
                        <span style={{ color: "#f59e0b" }}> ({cleverSyncResult.counts.students_with_accommodations} with IEP/ELL)</span>
                      )}
                    </span>
                  )}
                </div>

                {/* Section selector — shown after first sync */}
                {cleverSyncResult && cleverSyncResult.available_sections && cleverSyncResult.available_sections.length > 0 && (
                  <div style={{
                    background: "var(--input-bg)", borderRadius: "8px", padding: "12px 15px",
                    marginBottom: "15px", border: "1px solid var(--glass-border)",
                  }}>
                    <div style={{ fontSize: "0.85rem", fontWeight: 600, marginBottom: "10px", display: "flex", alignItems: "center", gap: "8px" }}>
                      <Icon name="List" size={16} style={{ color: "var(--accent-primary)" }} />
                      Select Sections to Sync
                    </div>
                    <div style={{ display: "flex", flexDirection: "column", gap: "6px", maxHeight: "200px", overflowY: "auto" }}>
                      {cleverSyncResult.available_sections.map(function(section) {
                        var sid = section.clever_section_id;
                        var isChecked = !!cleverSelectedSections[sid];
                        return (
                          <label key={sid} style={{
                            display: "flex", alignItems: "center", gap: "10px",
                            padding: "6px 8px", borderRadius: "6px", cursor: "pointer",
                            background: isChecked ? "rgba(99,102,241,0.1)" : "transparent",
                          }}>
                            <input
                              type="checkbox"
                              checked={isChecked}
                              onChange={function() {
                                setCleverSelectedSections(function(prev) {
                                  var next = Object.assign({}, prev);
                                  next[sid] = !prev[sid];
                                  return next;
                                });
                              }}
                            />
                            <span style={{ fontSize: "0.88rem", fontWeight: 500 }}>{section.name}</span>
                            <span style={{ fontSize: "0.78rem", color: "var(--text-muted)", marginLeft: "auto" }}>
                              {section.subject} {section.grade ? "- Grade " + section.grade : ""}
                              {" (" + (section.student_clever_ids || []).length + " students)"}
                            </span>
                          </label>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* Accommodation suggestions — shown after sync if IEP/ELL students found */}
                {cleverAccommSuggestions && Object.keys(cleverAccommSuggestions).length > 0 && (
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
                )}
              </div>
  );
}
