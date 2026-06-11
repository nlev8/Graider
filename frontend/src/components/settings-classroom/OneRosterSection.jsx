import React from "react";
import Icon from "../Icon";
import * as api from "../../services/api";

export default function OneRosterSection(props) {
  const { activeProvider, addToast, districtSisProvider, oneRosterStatus, oneRosterSyncResult, oneRosterSyncing, setOneRosterSyncResult, setOneRosterSyncing, setTeacherSisId, teacherSisId } = props;
  if (!(activeProvider !== 'clever')) return null;
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
                  <Icon name="Globe" size={20} style={{ color: "#6366f1" }} />
                  OneRoster Integration (1EdTech)
                  {oneRosterStatus === 'connected' && (
                    <span style={{
                      padding: "2px 8px", borderRadius: 6, fontSize: "0.7rem", fontWeight: 600,
                      background: "rgba(34,197,94,0.15)", color: "#22c55e", marginLeft: "auto",
                    }}>
                      Connected
                    </span>
                  )}
                </h3>
                <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "15px" }}>
                  Connect to any OneRoster-compatible SIS (PowerSchool, Infinite Campus, Skyward, etc.) to sync your roster automatically.
                </p>

                {districtSisProvider === 'oneroster' ? (
                  /* SIMPLIFIED VIEW - district has configured OneRoster credentials */
                  <div style={{ padding: "18px", background: "var(--card-bg)", borderRadius: "12px", border: "1px solid var(--glass-border)" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "12px" }}>
                      <Icon name="RefreshCw" size={20} />
                      <span style={{ fontWeight: 700, fontSize: "1rem" }}>Roster Sync</span>
                      <span style={{ background: "#059669", color: "white", padding: "2px 8px", borderRadius: "6px", fontSize: "0.7rem", fontWeight: 600 }}>District configured</span>
                    </div>
                    <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", marginBottom: "16px" }}>
                      Your district has set up OneRoster. Enter your SIS Teacher ID to sync your class roster.
                    </p>
                    <div style={{ marginBottom: "12px" }}>
                      <label style={{ fontSize: "0.85rem", fontWeight: 600, display: "block", marginBottom: "6px" }}>SIS Teacher ID</label>
                      <input
                        type="text"
                        value={teacherSisId}
                        onChange={function(e) { setTeacherSisId(e.target.value); }}
                        placeholder="Ask your school admin for your OneRoster teacher sourcedId"
                        style={{ width: "100%", padding: "10px 14px", background: "var(--input-bg)", border: "1px solid var(--input-border)", borderRadius: "10px", color: "var(--text-primary)", fontSize: "0.9rem", outline: "none", maxWidth: "500px" }}
                      />
                    </div>
                    <div style={{ display: "flex", gap: "8px" }}>
                      <button
                        onClick={async function() {
                          if (!teacherSisId.trim()) { addToast("Please enter your SIS Teacher ID", "error"); return; }
                          setOneRosterSyncing(true);
                          try {
                            await api.saveOneRosterTeacherId(teacherSisId.trim());
                            var result = await api.syncOneRosterRoster();
                            if (result.counts) {
                              setOneRosterSyncResult(result);
                              addToast("Roster synced: " + result.counts.classes + " classes, " + result.counts.students + " students", "success");
                            } else if (result.error) {
                              addToast(result.error, "error");
                            }
                          } catch (err) {
                            addToast("Sync failed: " + err.message, "error");
                          }
                          setOneRosterSyncing(false);
                        }}
                        disabled={oneRosterSyncing || !teacherSisId.trim()}
                        className="btn btn-primary"
                        style={{ opacity: (oneRosterSyncing || !teacherSisId.trim()) ? 0.6 : 1 }}
                      >
                        <Icon name="RefreshCw" size={18} style={oneRosterSyncing ? { animation: "spin 1s linear infinite" } : {}} />
                        {oneRosterSyncing ? "Syncing..." : "Sync Roster"}
                      </button>
                    </div>
                    {oneRosterSyncResult && oneRosterSyncResult.counts && (
                      <div style={{ marginTop: "12px", padding: "12px", background: "rgba(5,150,105,0.1)", borderRadius: "8px", fontSize: "0.85rem" }}>
                        <span style={{ fontWeight: 600 }}>Synced: </span>
                        {oneRosterSyncResult.counts.classes + " classes, " + oneRosterSyncResult.counts.students + " students, " + oneRosterSyncResult.counts.enrollments + " enrollments"}
                      </div>
                    )}
                  </div>
                ) : (
                  <OneRosterFullForm {...props} />
                )}
              </div>
  );
}

function OneRosterFullForm(props) {
  const { addToast, oneRosterConfig, oneRosterHasCredentials, oneRosterSaving, oneRosterStatus, oneRosterSyncResult, oneRosterSyncing, oneRosterTestResult, setOneRosterAccommodations, setOneRosterConfig, setOneRosterHasCredentials, setOneRosterSaving, setOneRosterStatus, setOneRosterSyncResult, setOneRosterSyncing, setOneRosterTestResult, setPeriods, setShowOneRosterSecret, showOneRosterSecret } = props;
  return (
                  <>

                {/* Config fields */}
                <div style={{ display: "flex", flexDirection: "column", gap: "12px", maxWidth: "500px" }}>
                  <div>
                    <label style={{ fontSize: "0.85rem", fontWeight: 600, display: "block", marginBottom: "6px" }}>Base URL *</label>
                    <input
                      type="text"
                      value={oneRosterConfig.base_url}
                      onChange={function(e) { setOneRosterConfig(function(prev) { return Object.assign({}, prev, { base_url: e.target.value }); }); }}
                      placeholder="https://yoursis.example.com/ims/oneroster/v1p1"
                      style={{ width: "100%", padding: "10px 14px", background: "var(--input-bg)", border: "1px solid var(--input-border)", borderRadius: "10px", color: "var(--text-primary)", fontSize: "0.9rem", outline: "none" }}
                    />
                  </div>
                  <div>
                    <label style={{ fontSize: "0.85rem", fontWeight: 600, display: "block", marginBottom: "6px" }}>Client ID *</label>
                    <input
                      type="text"
                      value={oneRosterConfig.client_id}
                      onChange={function(e) { setOneRosterConfig(function(prev) { return Object.assign({}, prev, { client_id: e.target.value }); }); }}
                      placeholder="OAuth 2.0 Client ID"
                      style={{ width: "100%", padding: "10px 14px", background: "var(--input-bg)", border: "1px solid var(--input-border)", borderRadius: "10px", color: "var(--text-primary)", fontSize: "0.9rem", outline: "none" }}
                    />
                  </div>
                  <div>
                    <label style={{ fontSize: "0.85rem", fontWeight: 600, display: "block", marginBottom: "6px" }}>
                      Client Secret *
                      {oneRosterHasCredentials && !oneRosterConfig.client_secret && (
                        <span style={{ marginLeft: "8px", padding: "2px 8px", borderRadius: 6, fontSize: "0.7rem", fontWeight: 600, background: "rgba(34,197,94,0.15)", color: "#22c55e" }}>
                          Credentials saved
                        </span>
                      )}
                    </label>
                    <div style={{ position: "relative" }}>
                      <input
                        type={showOneRosterSecret ? "text" : "password"}
                        value={oneRosterConfig.client_secret}
                        onChange={function(e) { setOneRosterConfig(function(prev) { return Object.assign({}, prev, { client_secret: e.target.value }); }); }}
                        placeholder={oneRosterHasCredentials ? "Leave blank to keep existing" : "OAuth 2.0 Client Secret"}
                        style={{ width: "100%", padding: "10px 14px", paddingRight: "44px", background: "var(--input-bg)", border: "1px solid var(--input-border)", borderRadius: "10px", color: "var(--text-primary)", fontSize: "0.9rem", outline: "none" }}
                      />
                      <button type="button" onClick={function() { setShowOneRosterSecret(function(p) { return !p; }); }} style={{ position: "absolute", right: "10px", top: "50%", transform: "translateY(-50%)", background: "none", border: "none", cursor: "pointer", padding: "4px", color: "var(--text-secondary)", display: "flex", alignItems: "center" }} title={showOneRosterSecret ? "Hide secret" : "Show secret"}>
                        <Icon name={showOneRosterSecret ? "EyeOff" : "Eye"} size={18} />
                      </button>
                    </div>
                  </div>
                  <div>
                    <label style={{ fontSize: "0.85rem", fontWeight: 600, display: "block", marginBottom: "6px" }}>Token URL (optional)</label>
                    <input
                      type="text"
                      value={oneRosterConfig.token_url}
                      onChange={function(e) { setOneRosterConfig(function(prev) { return Object.assign({}, prev, { token_url: e.target.value }); }); }}
                      placeholder="Defaults to base_url/token"
                      style={{ width: "100%", padding: "10px 14px", background: "var(--input-bg)", border: "1px solid var(--input-border)", borderRadius: "10px", color: "var(--text-primary)", fontSize: "0.9rem", outline: "none" }}
                    />
                  </div>
                  <div>
                    <label style={{ fontSize: "0.85rem", fontWeight: 600, display: "block", marginBottom: "6px" }}>School ID (optional)</label>
                    <input
                      type="text"
                      value={oneRosterConfig.school_id}
                      onChange={function(e) { setOneRosterConfig(function(prev) { return Object.assign({}, prev, { school_id: e.target.value }); }); }}
                      placeholder="Filter roster to a specific school"
                      style={{ width: "100%", padding: "10px 14px", background: "var(--input-bg)", border: "1px solid var(--input-border)", borderRadius: "10px", color: "var(--text-primary)", fontSize: "0.9rem", outline: "none" }}
                    />
                  </div>
                  <div>
                    <label style={{ fontSize: "0.85rem", fontWeight: 600, display: "block", marginBottom: "6px" }}>Teacher Sourced ID *</label>
                    <input
                      type="text"
                      value={oneRosterConfig.teacher_sourced_id}
                      onChange={function(e) { setOneRosterConfig(function(prev) { return Object.assign({}, prev, { teacher_sourced_id: e.target.value }); }); }}
                      placeholder="Your OneRoster teacher sourcedId"
                      style={{ width: "100%", padding: "10px 14px", background: "var(--input-bg)", border: "1px solid var(--input-border)", borderRadius: "10px", color: "var(--text-primary)", fontSize: "0.9rem", outline: "none" }}
                    />
                  </div>
                </div>

                {/* Action buttons */}
                <div style={{ display: "flex", gap: "10px", marginTop: "15px", flexWrap: "wrap", alignItems: "center" }}>
                  <button
                    onClick={async function() {
                      if (!oneRosterConfig.base_url || !oneRosterConfig.client_id || !oneRosterConfig.teacher_sourced_id) {
                        addToast("Base URL, Client ID, and Teacher Sourced ID are required", "error");
                        return;
                      }
                      if (!oneRosterConfig.client_secret && !oneRosterHasCredentials) {
                        addToast("Client Secret is required", "error");
                        return;
                      }
                      setOneRosterSaving(true);
                      try {
                        var saveData = Object.assign({}, oneRosterConfig);
                        if (!saveData.client_secret && oneRosterHasCredentials) {
                          delete saveData.client_secret;
                        }
                        var result = await api.saveOneRosterConfig(saveData);
                        if (result.error) {
                          addToast("Save failed: " + result.error, "error");
                        } else {
                          setOneRosterHasCredentials(true);
                          setOneRosterConfig(function(prev) { return Object.assign({}, prev, { client_secret: '' }); });
                          addToast("OneRoster configuration saved", "success");
                        }
                      } catch (err) {
                        addToast("Save failed: " + err.message, "error");
                      }
                      setOneRosterSaving(false);
                    }}
                    className="btn btn-primary"
                    disabled={oneRosterSaving}
                    style={{ opacity: oneRosterSaving ? 0.6 : 1 }}
                  >
                    <Icon name="Save" size={18} />
                    {oneRosterSaving ? "Saving..." : "Save Config"}
                  </button>

                  <button
                    onClick={async function() {
                      setOneRosterTestResult(null);
                      try {
                        var result = await api.testOneRosterConnection();
                        setOneRosterTestResult(result);
                        if (result.success) {
                          setOneRosterStatus('connected');
                          addToast("Connection successful! " + (result.school_name || ""), "success");
                        } else {
                          setOneRosterStatus('error');
                          addToast("Connection failed: " + (result.error || "Unknown error"), "error");
                        }
                      } catch (err) {
                        setOneRosterTestResult({ success: false, error: err.message });
                        setOneRosterStatus('error');
                        addToast("Connection test failed: " + err.message, "error");
                      }
                    }}
                    className="btn btn-secondary"
                    disabled={!oneRosterHasCredentials && !oneRosterConfig.client_secret}
                  >
                    <Icon name="Plug" size={18} />
                    Test Connection
                  </button>

                  <button
                    onClick={async function() {
                      setOneRosterSyncing(true);
                      setOneRosterSyncResult(null);
                      setOneRosterAccommodations(null);
                      try {
                        var result = await api.syncOneRosterRoster();
                        if (result.error) {
                          addToast("Sync failed: " + result.error, "error");
                        } else {
                          setOneRosterSyncResult(result);
                          setOneRosterStatus('connected');
                          if (result.accommodation_suggestions && Object.keys(result.accommodation_suggestions).length > 0) {
                            setOneRosterAccommodations(result.accommodation_suggestions);
                          }
                          addToast("Synced " + (result.counts ? result.counts.students + " students, " + result.counts.sections + " sections" : "roster"), "success");
                          // Refresh periods list
                          var periodsData = await api.listPeriods();
                          setPeriods(periodsData.periods || []);
                        }
                      } catch (err) {
                        addToast("Sync failed: " + err.message, "error");
                      }
                      setOneRosterSyncing(false);
                    }}
                    className="btn btn-secondary"
                    disabled={oneRosterSyncing || (!oneRosterHasCredentials && !oneRosterConfig.client_secret)}
                    style={{ opacity: oneRosterSyncing ? 0.6 : 1 }}
                  >
                    <Icon name="RefreshCw" size={18} style={oneRosterSyncing ? { animation: "spin 1s linear infinite" } : {}} />
                    {oneRosterSyncing ? "Syncing..." : "Sync Roster"}
                  </button>
                </div>

                {/* Test result */}
                {oneRosterTestResult && (
                  <div style={{
                    marginTop: "10px", padding: "10px 14px", borderRadius: "8px", fontSize: "0.85rem",
                    background: oneRosterTestResult.success ? "rgba(34,197,94,0.08)" : "rgba(239,68,68,0.08)",
                    border: "1px solid " + (oneRosterTestResult.success ? "rgba(34,197,94,0.3)" : "rgba(239,68,68,0.3)"),
                    color: oneRosterTestResult.success ? "#22c55e" : "#ef4444",
                  }}>
                    <Icon name={oneRosterTestResult.success ? "CheckCircle2" : "XCircle"} size={16} style={{ marginRight: "6px", verticalAlign: "middle" }} />
                    {oneRosterTestResult.success ? "Connected successfully" + (oneRosterTestResult.school_name ? " - " + oneRosterTestResult.school_name : "") : "Failed: " + (oneRosterTestResult.error || "Unknown error")}
                  </div>
                )}

                {/* Sync result */}
                {oneRosterSyncResult && oneRosterSyncResult.counts && (
                  <div style={{ marginTop: "10px", fontSize: "0.82rem", color: "var(--text-secondary)" }}>
                    Synced {oneRosterSyncResult.counts.students} students, {oneRosterSyncResult.counts.sections} sections
                    {oneRosterSyncResult.counts.students_with_accommodations > 0 && (
                      <span style={{ color: "#f59e0b" }}> ({oneRosterSyncResult.counts.students_with_accommodations} with IEP/ELL)</span>
                    )}
                  </div>
                )}

                {/* Accommodation suggestions */}
                <OneRosterAccommodationSuggestions {...props} />

                {/* Delete OneRoster Data */}
                {oneRosterStatus === 'connected' && (
                  <div style={{ marginTop: "20px", paddingTop: "15px", borderTop: "1px solid var(--glass-border)" }}>
                    <button
                      onClick={function() {
                        if (window.confirm("Delete all OneRoster-synced roster data? This cannot be undone.")) {
                          api.deleteOneRosterData().then(function(result) {
                            if (result.error) {
                              addToast("Delete failed: " + result.error, "error");
                            } else {
                              setOneRosterStatus(null);
                              setOneRosterSyncResult(null);
                              setOneRosterAccommodations(null);
                              setOneRosterTestResult(null);
                              addToast("OneRoster data deleted", "success");
                              api.listPeriods().then(function(d) { setPeriods(d.periods || []); }).catch(function() {});
                            }
                          }).catch(function(err) {
                            addToast("Delete failed: " + err.message, "error");
                          });
                        }
                      }}
                      style={{
                        background: "none", border: "1px solid rgba(239,68,68,0.3)", borderRadius: "8px",
                        padding: "6px 14px", cursor: "pointer", fontSize: "0.82rem",
                        color: "#ef4444", display: "flex", alignItems: "center", gap: "6px",
                      }}
                    >
                      <Icon name="Trash2" size={14} />
                      Delete OneRoster Data
                    </button>
                  </div>
                )}
                  </>
  );
}

function OneRosterAccommodationSuggestions({ addToast, oneRosterAccommodations, oneRosterApplying, setOneRosterAccommodations, setOneRosterApplying, setStudentAccommodations }) {
  if (!(oneRosterAccommodations && Object.keys(oneRosterAccommodations).length > 0)) return null;
  return (
                  <div style={{
                    background: "rgba(245,158,11,0.08)", borderRadius: "8px", padding: "12px 15px",
                    marginTop: "15px", border: "1px solid rgba(245,158,11,0.3)",
                  }}>
                    <div style={{ fontSize: "0.85rem", fontWeight: 600, marginBottom: "8px", display: "flex", alignItems: "center", gap: "8px" }}>
                      <Icon name="Shield" size={16} style={{ color: "#f59e0b" }} />
                      IEP/ELL Accommodation Suggestions
                      <span style={{
                        padding: "2px 8px", borderRadius: 6, fontSize: "0.7rem", fontWeight: 600,
                        background: "rgba(245,158,11,0.2)", color: "#f59e0b",
                      }}>
                        {Object.keys(oneRosterAccommodations).length} students
                      </span>
                    </div>
                    <p style={{ fontSize: "0.82rem", color: "var(--text-secondary)", marginBottom: "10px" }}>
                      OneRoster detected these students have IEP or ELL flags. Review and apply accommodation presets:
                    </p>
                    <div style={{ maxHeight: "200px", overflowY: "auto", marginBottom: "10px" }}>
                      {Object.entries(oneRosterAccommodations).map(function(entry) {
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
                        setOneRosterApplying(true);
                        try {
                          var result = await api.applyOneRosterAccommodations(oneRosterAccommodations);
                          if (result.errors && result.errors.length > 0) {
                            addToast("Applied " + result.applied + "/" + result.total + " (some errors)", "warning");
                          } else {
                            addToast("Applied accommodations for " + result.applied + " students", "success");
                          }
                          setOneRosterAccommodations(null);
                          // Refresh accommodations
                          var accommData = await api.getStudentAccommodations();
                          setStudentAccommodations(accommData.accommodations || {});
                        } catch (err) {
                          addToast("Failed to apply accommodations: " + err.message, "error");
                        }
                        setOneRosterApplying(false);
                      }}
                      className="btn btn-primary"
                      disabled={oneRosterApplying}
                      style={{ opacity: oneRosterApplying ? 0.6 : 1 }}
                    >
                      <Icon name="Check" size={18} />
                      {oneRosterApplying ? "Applying..." : "Apply All Accommodations"}
                    </button>
                  </div>
  );
}
