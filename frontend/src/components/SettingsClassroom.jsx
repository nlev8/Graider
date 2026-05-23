import React from "react";
import Icon from "./Icon";
import * as api from "../services/api";
import { getAuthHeaders } from "../services/api";

export default function SettingsClassroom({ accommodationPresets, activeProvider, addToast, addingStudent, cleverAccommSuggestions, cleverApplying, cleverSelectedSections, cleverSyncResult, cleverSyncing, districtSisProvider, editStudentData, editingStudentId, expandedPeriod, expandedStudents, focusImportProgress, focusImporting, isCleverUser, loadingExpandedStudents, ltiContexts, ltiNewPlatform, ltiPlatforms, ltiSaving, ltiSelectedContext, ltiShowForm, ltiSyncLabel, ltiSyncMaxScore, ltiSyncResult, ltiSyncScores, ltiSyncing, ltiToolConfig, newPeriodName, newStudent, oneRosterAccommodations, oneRosterApplying, oneRosterConfig, oneRosterHasCredentials, oneRosterSaving, oneRosterStatus, oneRosterSyncResult, oneRosterSyncing, oneRosterTestResult, parentContacts, parentContactsInputRef, periodInputRef, setAccommEllLanguage, setAccommodationCustomNotes, setAccommodationModal, setAddStudentModal, setAddingStudent, setCleverAccommSuggestions, setCleverApplying, setCleverSelectedSections, setCleverSyncResult, setCleverSyncing, setEditStudentData, setEditingStudentId, setExpandedPeriod, setExpandedStudents, setFocusImportProgress, setFocusImporting, setLoadingExpandedStudents, setLtiNewPlatform, setLtiPlatforms, setLtiSaving, setLtiSelectedContext, setLtiShowForm, setLtiSyncLabel, setLtiSyncMaxScore, setLtiSyncResult, setLtiSyncScores, setLtiSyncing, setLtiToolConfig, setNewPeriodName, setNewStudent, setOneRosterAccommodations, setOneRosterApplying, setOneRosterConfig, setOneRosterHasCredentials, setOneRosterSaving, setOneRosterStatus, setOneRosterSyncResult, setOneRosterSyncing, setOneRosterTestResult, setParentContactMapping, setPeriods, setSelectedAccommodationPresets, setShowManualSetup, setShowOneRosterSecret, setStudentAccommodations, setTeacherSisId, setUploadingParentContacts, setUploadingPeriod, showManualSetup, showOneRosterSecret, sortedPeriods, studentAccommodations, teacherSisId, uploadingParentContacts, uploadingPeriod }) {
  return (
              <>

            {/* Clever Roster Sync Section — shown for Clever SSO users */}
            {isCleverUser && (
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
            )}

            {/* OneRoster Integration Section */}
            {activeProvider !== 'clever' && (
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
                  /* FULL FORM - no district config, teacher manages everything */
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
                {oneRosterAccommodations && Object.keys(oneRosterAccommodations).length > 0 && (
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
                )}

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
                )}
              </div>
            )}

            {/* LTI 1.3 Integration Section — always visible, not a roster provider */}
            <div style={{
              marginTop: "20px", padding: "18px", background: "var(--card-bg)",
              borderRadius: "12px", border: "1px solid var(--glass-border)",
            }}>
              <h3 style={{ fontSize: "1rem", fontWeight: 700, marginBottom: "12px", display: "flex", alignItems: "center", gap: "8px" }}>
                <Icon name="Shield" size={18} />
                LTI 1.3 Integration
              </h3>
              <p style={{ fontSize: "0.82rem", color: "var(--text-secondary)", marginBottom: "14px" }}>
                Connect Graider to your LMS (Canvas, Schoology, etc.) for single sign-on launches and grade passback. LTI works alongside any roster provider.
              </p>

              {/* Tool Configuration — read-only URLs for LMS admin */}
              {ltiToolConfig && (
                <div style={{
                  marginBottom: "14px", padding: "12px", background: "rgba(99,102,241,0.06)",
                  borderRadius: "8px", border: "1px solid rgba(99,102,241,0.15)",
                }}>
                  <div style={{ fontSize: "0.78rem", fontWeight: 600, marginBottom: "8px", color: "var(--text-secondary)" }}>
                    Tool Configuration (provide these to your LMS admin)
                  </div>
                  {[
                    { label: "OIDC Login URL", value: ltiToolConfig.oidc_login_url },
                    { label: "Launch URL", value: ltiToolConfig.launch_url },
                    { label: "JWKS URL", value: ltiToolConfig.jwks_url },
                    { label: "Redirect URI", value: ltiToolConfig.redirect_uri },
                  ].map(function(item) {
                    return (
                      <div key={item.label} style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "6px" }}>
                        <span style={{ fontSize: "0.78rem", fontWeight: 600, minWidth: "120px", color: "var(--text-secondary)" }}>{item.label}:</span>
                        <span style={{ fontSize: "0.78rem", flex: 1, fontFamily: "monospace", wordBreak: "break-all", color: "var(--text-primary)" }}>{item.value || "—"}</span>
                        <button
                          type="button"
                          onClick={function() {
                            navigator.clipboard.writeText(item.value || '');
                            addToast("Copied " + item.label, "success");
                          }}
                          style={{
                            background: "none", border: "1px solid var(--glass-border)", borderRadius: "6px",
                            padding: "3px 8px", cursor: "pointer", fontSize: "0.72rem", color: "var(--text-secondary)",
                            display: "flex", alignItems: "center", gap: "4px", flexShrink: 0,
                          }}
                        >
                          <Icon name="Copy" size={12} />
                          Copy
                        </button>
                      </div>
                    );
                  })}
                </div>
              )}

              {/* Registered Platforms */}
              {ltiPlatforms.length > 0 && (
                <div style={{ marginBottom: "14px" }}>
                  <div style={{ fontSize: "0.82rem", fontWeight: 600, marginBottom: "8px" }}>Registered Platforms</div>
                  <div style={{ border: "1px solid var(--glass-border)", borderRadius: "8px", overflow: "hidden" }}>
                    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.8rem" }}>
                      <thead>
                        <tr style={{ background: "rgba(99,102,241,0.06)" }}>
                          <th style={{ padding: "8px 12px", textAlign: "left", fontWeight: 600 }}>Name</th>
                          <th style={{ padding: "8px 12px", textAlign: "left", fontWeight: 600 }}>Issuer</th>
                          <th style={{ padding: "8px 12px", textAlign: "left", fontWeight: 600 }}>Client ID</th>
                          <th style={{ padding: "8px 12px", textAlign: "right", fontWeight: 600 }}></th>
                        </tr>
                      </thead>
                      <tbody>
                        {ltiPlatforms.map(function(p, idx) {
                          return (
                            <tr key={idx} style={{ borderTop: "1px solid var(--glass-border)" }}>
                              <td style={{ padding: "8px 12px" }}>{p.name || "—"}</td>
                              <td style={{ padding: "8px 12px", fontFamily: "monospace", fontSize: "0.75rem", wordBreak: "break-all" }}>{p.issuer}</td>
                              <td style={{ padding: "8px 12px", fontFamily: "monospace", fontSize: "0.75rem" }}>{p.client_id}</td>
                              <td style={{ padding: "8px 12px", textAlign: "right" }}>
                                <button
                                  type="button"
                                  onClick={function() {
                                    if (window.confirm("Remove platform " + (p.name || p.issuer) + "?")) {
                                      api.deleteLTIPlatform(p.issuer).then(function(result) {
                                        if (result.status === 'ok') {
                                          setLtiPlatforms(function(prev) { return prev.filter(function(x) { return x.issuer !== p.issuer; }); });
                                          addToast("Platform removed", "success");
                                        } else {
                                          addToast(result.error || "Delete failed", "error");
                                        }
                                      }).catch(function(err) {
                                        addToast("Delete failed: " + err.message, "error");
                                      });
                                    }
                                  }}
                                  style={{
                                    background: "none", border: "none", cursor: "pointer",
                                    color: "#ef4444", padding: "4px",
                                  }}
                                >
                                  <Icon name="Trash2" size={14} />
                                </button>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Add Platform toggle */}
              {!ltiShowForm && (
                <button
                  type="button"
                  onClick={function() { setLtiShowForm(true); }}
                  style={{
                    background: "rgba(99,102,241,0.1)", border: "1px solid rgba(99,102,241,0.3)", borderRadius: "8px",
                    padding: "8px 16px", cursor: "pointer", fontSize: "0.82rem",
                    color: "var(--accent)", display: "flex", alignItems: "center", gap: "6px", fontWeight: 600,
                  }}
                >
                  <Icon name="Plus" size={14} />
                  Add Platform
                </button>
              )}

              {/* Add Platform Form */}
              {ltiShowForm && (
                <div style={{
                  padding: "14px", background: "rgba(99,102,241,0.04)",
                  borderRadius: "8px", border: "1px solid rgba(99,102,241,0.15)", marginTop: "8px",
                }}>
                  <div style={{ fontSize: "0.82rem", fontWeight: 600, marginBottom: "10px" }}>New Platform Registration</div>

                  {/* LMS Preset Buttons */}
                  <div style={{ display: "flex", gap: "8px", marginBottom: "12px" }}>
                    <button
                      type="button"
                      onClick={function() {
                        var issuer = ltiNewPlatform.issuer || '';
                        setLtiNewPlatform(function(prev) {
                          return Object.assign({}, prev, {
                            name: prev.name || 'Canvas',
                            auth_login_url: issuer ? issuer + "/api/lti/authorize_redirect" : prev.auth_login_url,
                            auth_token_url: issuer ? issuer + "/login/oauth2/token" : prev.auth_token_url,
                            jwks_url: issuer ? issuer + "/api/lti/security/jwks" : prev.jwks_url,
                          });
                        });
                        if (!issuer) addToast("Enter the Issuer URL first, then click Canvas again to auto-fill URLs", "info");
                      }}
                      style={{
                        background: "rgba(239,108,0,0.1)", border: "1px solid rgba(239,108,0,0.3)", borderRadius: "6px",
                        padding: "5px 12px", cursor: "pointer", fontSize: "0.78rem", color: "#ef6c00", fontWeight: 600,
                      }}
                    >
                      Canvas
                    </button>
                    <button
                      type="button"
                      onClick={function() {
                        setLtiNewPlatform(function(prev) {
                          return Object.assign({}, prev, {
                            name: prev.name || 'Schoology',
                            auth_login_url: "https://lti.schoology.com/lti/authorize",
                            auth_token_url: "https://lti.schoology.com/lti/token",
                            jwks_url: "https://lti.schoology.com/lti/.well-known/jwks",
                          });
                        });
                      }}
                      style={{
                        background: "rgba(33,150,243,0.1)", border: "1px solid rgba(33,150,243,0.3)", borderRadius: "6px",
                        padding: "5px 12px", cursor: "pointer", fontSize: "0.78rem", color: "#2196f3", fontWeight: 600,
                      }}
                    >
                      Schoology
                    </button>
                  </div>

                  <div style={{ display: "grid", gap: "8px" }}>
                    <input
                      type="text" placeholder="Platform Name (e.g. Canvas, Schoology)"
                      value={ltiNewPlatform.name}
                      onChange={function(e) { setLtiNewPlatform(function(prev) { return Object.assign({}, prev, { name: e.target.value }); }); }}
                      style={{ width: "100%", padding: "8px 12px", borderRadius: "8px", border: "1px solid var(--glass-border)", background: "var(--input-bg)", color: "var(--text-primary)", fontSize: "0.85rem" }}
                    />
                    <input
                      type="text" placeholder="Issuer URL (required)" required
                      value={ltiNewPlatform.issuer}
                      onChange={function(e) { setLtiNewPlatform(function(prev) { return Object.assign({}, prev, { issuer: e.target.value }); }); }}
                      style={{ width: "100%", padding: "8px 12px", borderRadius: "8px", border: "1px solid var(--glass-border)", background: "var(--input-bg)", color: "var(--text-primary)", fontSize: "0.85rem" }}
                    />
                    <input
                      type="text" placeholder="Client ID (required)" required
                      value={ltiNewPlatform.client_id}
                      onChange={function(e) { setLtiNewPlatform(function(prev) { return Object.assign({}, prev, { client_id: e.target.value }); }); }}
                      style={{ width: "100%", padding: "8px 12px", borderRadius: "8px", border: "1px solid var(--glass-border)", background: "var(--input-bg)", color: "var(--text-primary)", fontSize: "0.85rem" }}
                    />
                    <input
                      type="text" placeholder="Authorization URL (required)" required
                      value={ltiNewPlatform.auth_login_url}
                      onChange={function(e) { setLtiNewPlatform(function(prev) { return Object.assign({}, prev, { auth_login_url: e.target.value }); }); }}
                      style={{ width: "100%", padding: "8px 12px", borderRadius: "8px", border: "1px solid var(--glass-border)", background: "var(--input-bg)", color: "var(--text-primary)", fontSize: "0.85rem" }}
                    />
                    <input
                      type="text" placeholder="Token URL (required)" required
                      value={ltiNewPlatform.auth_token_url}
                      onChange={function(e) { setLtiNewPlatform(function(prev) { return Object.assign({}, prev, { auth_token_url: e.target.value }); }); }}
                      style={{ width: "100%", padding: "8px 12px", borderRadius: "8px", border: "1px solid var(--glass-border)", background: "var(--input-bg)", color: "var(--text-primary)", fontSize: "0.85rem" }}
                    />
                    <input
                      type="text" placeholder="JWKS URL (required)" required
                      value={ltiNewPlatform.jwks_url}
                      onChange={function(e) { setLtiNewPlatform(function(prev) { return Object.assign({}, prev, { jwks_url: e.target.value }); }); }}
                      style={{ width: "100%", padding: "8px 12px", borderRadius: "8px", border: "1px solid var(--glass-border)", background: "var(--input-bg)", color: "var(--text-primary)", fontSize: "0.85rem" }}
                    />
                    <input
                      type="text" placeholder="Deployment IDs (comma-separated, optional)"
                      value={ltiNewPlatform.deployment_ids}
                      onChange={function(e) { setLtiNewPlatform(function(prev) { return Object.assign({}, prev, { deployment_ids: e.target.value }); }); }}
                      style={{ width: "100%", padding: "8px 12px", borderRadius: "8px", border: "1px solid var(--glass-border)", background: "var(--input-bg)", color: "var(--text-primary)", fontSize: "0.85rem" }}
                    />
                  </div>

                  <div style={{ display: "flex", gap: "8px", marginTop: "12px" }}>
                    <button
                      type="button"
                      disabled={ltiSaving || !ltiNewPlatform.issuer || !ltiNewPlatform.client_id || !ltiNewPlatform.auth_login_url || !ltiNewPlatform.auth_token_url || !ltiNewPlatform.jwks_url}
                      onClick={async function() {
                        setLtiSaving(true);
                        try {
                          var payload = Object.assign({}, ltiNewPlatform, {
                            deployment_ids: ltiNewPlatform.deployment_ids.split(',').map(function(s) { return s.trim(); }).filter(Boolean),
                          });
                          var result = await api.registerLTIPlatform(payload);
                          if (result.status === 'ok') {
                            setLtiPlatforms(result.platforms || []);
                            setLtiToolConfig(result.tool_config || ltiToolConfig);
                            setLtiNewPlatform({ name: '', issuer: '', client_id: '', auth_login_url: '', auth_token_url: '', jwks_url: '', deployment_ids: '' });
                            setLtiShowForm(false);
                            addToast("Platform registered", "success");
                          } else {
                            addToast(result.error || "Registration failed", "error");
                          }
                        } catch (err) {
                          addToast("Registration failed: " + err.message, "error");
                        }
                        setLtiSaving(false);
                      }}
                      style={{
                        background: "var(--accent)", color: "white", border: "none", borderRadius: "8px",
                        padding: "8px 16px", cursor: "pointer", fontSize: "0.82rem", fontWeight: 600,
                        opacity: (ltiSaving || !ltiNewPlatform.issuer || !ltiNewPlatform.client_id) ? 0.5 : 1,
                      }}
                    >
                      {ltiSaving ? "Saving..." : "Register Platform"}
                    </button>
                    <button
                      type="button"
                      onClick={function() {
                        setLtiShowForm(false);
                        setLtiNewPlatform({ name: '', issuer: '', client_id: '', auth_login_url: '', auth_token_url: '', jwks_url: '', deployment_ids: '' });
                      }}
                      style={{
                        background: "none", border: "1px solid var(--glass-border)", borderRadius: "8px",
                        padding: "8px 16px", cursor: "pointer", fontSize: "0.82rem", color: "var(--text-secondary)",
                      }}
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}

              {/* Grade Sync to LMS */}
              <div style={{ marginTop: "18px", borderTop: "1px solid var(--glass-border)", paddingTop: "14px" }}>
                <h4 style={{ fontSize: "0.92rem", fontWeight: 700, marginBottom: "10px", display: "flex", alignItems: "center", gap: "8px" }}>
                  <Icon name="Upload" size={16} />
                  Grade Sync to LMS
                </h4>

                {ltiContexts.length === 0 ? (
                  <p style={{ fontSize: "0.82rem", color: "var(--text-muted)", fontStyle: "italic" }}>
                    Launch Graider from your LMS to enable grade sync. No LTI course contexts are available yet.
                  </p>
                ) : (
                  <div>
                    {/* Context selector */}
                    <div style={{ marginBottom: "10px" }}>
                      <label style={{ fontSize: "0.78rem", fontWeight: 600, color: "var(--text-secondary)", display: "block", marginBottom: "4px" }}>Course</label>
                      <select
                        value={ltiSelectedContext ? ltiSelectedContext.context_id : ''}
                        onChange={function(e) {
                          var ctx = ltiContexts.find(function(c) { return c.context_id === e.target.value; });
                          setLtiSelectedContext(ctx || null);
                          setLtiSyncResult(null);
                          if (ctx && ctx.students) {
                            setLtiSyncScores(ctx.students.map(function(s) { return { student_name: s.name || s.user_id, score: '' }; }));
                          } else {
                            setLtiSyncScores([]);
                          }
                        }}
                        style={{ width: "100%", padding: "8px 12px", borderRadius: "8px", border: "1px solid var(--glass-border)", background: "var(--input-bg)", color: "var(--text-primary)", fontSize: "0.85rem" }}
                      >
                        <option value="">Select a course...</option>
                        {ltiContexts.map(function(ctx) {
                          return (
                            <option key={ctx.context_id} value={ctx.context_id}>
                              {ctx.context_title + " (" + (ctx.student_count || 0) + " students)"}
                            </option>
                          );
                        })}
                      </select>
                    </div>

                    {/* Score entry area — shown when context selected */}
                    {ltiSelectedContext && (
                      <div>
                        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px", marginBottom: "10px" }}>
                          <div>
                            <label style={{ fontSize: "0.78rem", fontWeight: 600, color: "var(--text-secondary)", display: "block", marginBottom: "4px" }}>Gradebook Column Name</label>
                            <input
                              type="text" placeholder="e.g. Chapter 5 Quiz"
                              value={ltiSyncLabel}
                              onChange={function(e) { setLtiSyncLabel(e.target.value); }}
                              style={{ width: "100%", padding: "8px 12px", borderRadius: "8px", border: "1px solid var(--glass-border)", background: "var(--input-bg)", color: "var(--text-primary)", fontSize: "0.85rem" }}
                            />
                          </div>
                          <div>
                            <label style={{ fontSize: "0.78rem", fontWeight: 600, color: "var(--text-secondary)", display: "block", marginBottom: "4px" }}>Max Score</label>
                            <input
                              type="number" min="1" value={ltiSyncMaxScore}
                              onChange={function(e) { setLtiSyncMaxScore(parseInt(e.target.value) || 100); }}
                              style={{ width: "100%", padding: "8px 12px", borderRadius: "8px", border: "1px solid var(--glass-border)", background: "var(--input-bg)", color: "var(--text-primary)", fontSize: "0.85rem" }}
                            />
                          </div>
                        </div>

                        {/* Student scores */}
                        {ltiSyncScores.length > 0 && (
                          <div style={{ marginBottom: "10px" }}>
                            <div style={{ fontSize: "0.78rem", fontWeight: 600, color: "var(--text-secondary)", marginBottom: "6px" }}>Student Scores</div>
                            <div style={{ maxHeight: "200px", overflowY: "auto", border: "1px solid var(--glass-border)", borderRadius: "8px" }}>
                              {ltiSyncScores.map(function(entry, idx) {
                                return (
                                  <div key={idx} style={{ display: "flex", alignItems: "center", gap: "8px", padding: "6px 10px", borderBottom: idx < ltiSyncScores.length - 1 ? "1px solid var(--glass-border)" : "none" }}>
                                    <span style={{ flex: 1, fontSize: "0.82rem" }}>{entry.student_name}</span>
                                    <input
                                      type="number" min="0" placeholder="Score"
                                      value={entry.score}
                                      onChange={function(e) {
                                        var val = e.target.value;
                                        setLtiSyncScores(function(prev) {
                                          var updated = prev.slice();
                                          updated[idx] = Object.assign({}, updated[idx], { score: val });
                                          return updated;
                                        });
                                      }}
                                      style={{ width: "80px", padding: "4px 8px", borderRadius: "6px", border: "1px solid var(--glass-border)", background: "var(--input-bg)", color: "var(--text-primary)", fontSize: "0.82rem", textAlign: "right" }}
                                    />
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                        )}

                        {/* Sync button */}
                        <button
                          type="button"
                          disabled={ltiSyncing || !ltiSyncLabel}
                          onClick={async function() {
                            setLtiSyncing(true);
                            setLtiSyncResult(null);
                            try {
                              var scoresToSend = ltiSyncScores.filter(function(s) { return s.score !== '' && s.score !== null; }).map(function(s) { return { student_name: s.student_name, score: parseFloat(s.score) }; });
                              var result = await api.syncLTIGrades({
                                platform_issuer: ltiSelectedContext.platform_issuer,
                                context_id: ltiSelectedContext.context_id,
                                label: ltiSyncLabel,
                                max_score: ltiSyncMaxScore,
                                scores: scoresToSend,
                              });
                              setLtiSyncResult(result);
                              if (result.status === 'ok') {
                                addToast((result.synced || 0) + " scores synced to LMS", "success");
                              } else {
                                addToast(result.error || "Sync failed", "error");
                              }
                            } catch (err) {
                              addToast("Sync failed: " + err.message, "error");
                            }
                            setLtiSyncing(false);
                          }}
                          style={{
                            background: "var(--accent)", color: "white", border: "none", borderRadius: "8px",
                            padding: "8px 16px", cursor: "pointer", fontSize: "0.82rem", fontWeight: 600,
                            opacity: (ltiSyncing || !ltiSyncLabel) ? 0.5 : 1,
                            display: "flex", alignItems: "center", gap: "6px",
                          }}
                        >
                          <Icon name="Upload" size={14} />
                          {ltiSyncing ? "Syncing..." : "Sync Grades"}
                        </button>

                        {/* Sync result */}
                        {ltiSyncResult && ltiSyncResult.status === 'ok' && (
                          <div style={{ marginTop: "10px", padding: "10px", background: "rgba(34,197,94,0.08)", borderRadius: "8px", border: "1px solid rgba(34,197,94,0.2)" }}>
                            <div style={{ fontSize: "0.82rem", color: "#22c55e", fontWeight: 600 }}>
                              {(ltiSyncResult.synced || 0) + "/" + (ltiSyncResult.total || 0) + " scores synced successfully"}
                            </div>
                            {ltiSyncResult.unmatched_students && ltiSyncResult.unmatched_students.length > 0 && (
                              <div style={{ marginTop: "6px", padding: "8px", background: "rgba(234,179,8,0.08)", borderRadius: "6px", border: "1px solid rgba(234,179,8,0.2)" }}>
                                <div style={{ fontSize: "0.78rem", color: "#eab308", fontWeight: 600, marginBottom: "4px" }}>Unmatched Students</div>
                                <div style={{ fontSize: "0.78rem", color: "var(--text-secondary)" }}>
                                  {ltiSyncResult.unmatched_students.join(", ")}
                                </div>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>

            {/* Manual Setup toggle for Clever users */}
            {isCleverUser && (
              <div style={{ marginTop: "10px" }}>
                <button
                  onClick={function() { setShowManualSetup(function(p) { return !p; }); }}
                  style={{
                    background: "none", border: "none", cursor: "pointer",
                    color: "var(--text-muted)", fontSize: "0.82rem",
                    display: "flex", alignItems: "center", gap: "6px", padding: "4px 0",
                  }}
                >
                  <Icon name={showManualSetup ? "ChevronUp" : "ChevronDown"} size={14} />
                  {showManualSetup ? "Hide" : "Show"} Manual Setup (CSV upload, Focus import)
                </button>
              </div>
            )}

            {/* Manual setup sections — always shown for non-Clever users, collapsible for Clever users */}
            {(!isCleverUser || showManualSetup) && (
              <>
            {/* Add Student from Screenshot Section */}
            <div
              data-tutorial="settings-classroom"
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
                <Icon
                  name="Camera"
                  size={20}
                  style={{ color: "#8b5cf6" }}
                />
                Add Student from Screenshot
              </h3>
              <p
                style={{
                  fontSize: "0.85rem",
                  color: "var(--text-secondary)",
                  marginBottom: "15px",
                }}
              >
                Paste or upload a screenshot of student info - AI will extract and add to roster
              </p>

              <div style={{ display: "flex", gap: "10px", marginBottom: "15px", flexWrap: "wrap" }}>
                <button
                  onClick={async () => {
                    try {
                      const clipboardItems = await navigator.clipboard.read();
                      for (const item of clipboardItems) {
                        if (item.types.includes("image/png")) {
                          const blob = await item.getType("image/png");
                          const reader = new FileReader();
                          reader.onload = async (e) => {
                            const base64 = e.target.result;
                            setAddStudentModal({ show: true, loading: true, image: base64, student: null, error: null });
                            try {
                              const authHdrs = await getAuthHeaders();
                              const response = await fetch("/api/extract-student-from-image", {
                                method: "POST",
                                headers: { "Content-Type": "application/json", ...authHdrs },
                                body: JSON.stringify({ image: base64 }),
                              });
                              const data = await response.json();
                              if (data.error) {
                                setAddStudentModal(prev => ({ ...prev, loading: false, error: data.error }));
                              } else {
                                setAddStudentModal(prev => ({ ...prev, loading: false, student: data.student }));
                              }
                            } catch (err) {
                              setAddStudentModal(prev => ({ ...prev, loading: false, error: err.message }));
                            }
                          };
                          reader.readAsDataURL(blob);
                          return;
                        }
                      }
                      addToast("No image found in clipboard. Copy a screenshot first.", "warning");
                    } catch (err) {
                      addToast("Could not access clipboard: " + err.message, "error");
                    }
                  }}
                  className="btn btn-primary"
                >
                  <Icon name="Clipboard" size={18} />
                  Paste from Clipboard
                </button>
                <label className="btn btn-secondary" style={{ cursor: "pointer" }}>
                  <Icon name="Upload" size={18} />
                  Upload Image
                  <input
                    type="file"
                    accept="image/*"
                    style={{ display: "none" }}
                    onChange={async (e) => {
                      const file = e.target.files?.[0];
                      if (!file) return;
                      const reader = new FileReader();
                      reader.onload = async (ev) => {
                        const base64 = ev.target.result;
                        setAddStudentModal({ show: true, loading: true, image: base64, student: null, error: null });
                        try {
                          const authHdrs = await getAuthHeaders();
                          const response = await fetch("/api/extract-student-from-image", {
                            method: "POST",
                            headers: { "Content-Type": "application/json", ...authHdrs },
                            body: JSON.stringify({ image: base64 }),
                          });
                          const data = await response.json();
                          if (data.error) {
                            setAddStudentModal(prev => ({ ...prev, loading: false, error: data.error }));
                          } else {
                            setAddStudentModal(prev => ({ ...prev, loading: false, student: data.student }));
                          }
                        } catch (err) {
                          setAddStudentModal(prev => ({ ...prev, loading: false, error: err.message }));
                        }
                      };
                      reader.readAsDataURL(file);
                      e.target.value = "";
                    }}
                  />
                </label>
              </div>
            </div>

            {/* Period/Class Upload Section */}
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
                <Icon
                  name="Clock"
                  size={20}
                  style={{ color: "#f59e0b" }}
                />
                Class Periods
              </h3>
              <p
                style={{
                  fontSize: "0.85rem",
                  color: "var(--text-secondary)",
                  marginBottom: "15px",
                }}
              >
                Upload separate rosters for each class period, or import directly from Focus SIS
              </p>

              <input
                ref={periodInputRef}
                type="file"
                accept=".csv,.xlsx,.xls"
                style={{ display: "none" }}
                onChange={async (e) => {
                  const file = e.target.files?.[0];
                  if (!file) return;
                  if (!newPeriodName.trim()) {
                    addToast(
                      "Please enter a period name first",
                      "warning",
                    );
                    e.target.value = "";
                    return;
                  }
                  setUploadingPeriod(true);
                  try {
                    const result = await api.uploadPeriod(
                      file,
                      newPeriodName,
                    );
                    if (result.error) {
                      addToast(result.error, "error");
                    } else {
                      const periodsData = await api.listPeriods();
                      setPeriods(periodsData.periods || []);
                      setNewPeriodName("");
                    }
                  } catch (err) {
                    addToast("Upload failed: " + err.message, "error");
                  }
                  setUploadingPeriod(false);
                  e.target.value = "";
                }}
              />

              <div
                style={{
                  display: "flex",
                  gap: "10px",
                  marginBottom: "15px",
                }}
              >
                <input
                  type="text"
                  className="input"
                  placeholder="Period name (e.g., Period 1, Block A)"
                  value={newPeriodName}
                  onChange={(e) => setNewPeriodName(e.target.value)}
                  style={{ maxWidth: "250px" }}
                />
                <button
                  onClick={() => periodInputRef.current?.click()}
                  className="btn btn-secondary"
                  disabled={uploadingPeriod || !newPeriodName.trim()}
                  style={{
                    opacity:
                      !newPeriodName.trim() || uploadingPeriod
                        ? 0.5
                        : 1,
                    cursor:
                      !newPeriodName.trim() || uploadingPeriod
                        ? "not-allowed"
                        : "pointer",
                  }}
                  title={
                    !newPeriodName.trim()
                      ? "Enter a period name first"
                      : ""
                  }
                >
                  <Icon name="Upload" size={18} />
                  {uploadingPeriod
                    ? "Uploading..."
                    : "Upload CSV/Excel"}
                </button>
                <div style={{ position: "relative" }}>
                  <button
                    className="btn"
                    onClick={(e) => {
                      e.stopPropagation();
                      const el = e.currentTarget.nextElementSibling;
                      if (el) el.style.display = el.style.display === "none" ? "block" : "none";
                    }}
                    style={{ padding: "8px", minWidth: 0, borderRadius: "50%", width: "36px", height: "36px", display: "flex", alignItems: "center", justifyContent: "center" }}
                    title="How to export roster from Focus"
                  >
                    <Icon name="HelpCircle" size={18} style={{ color: "var(--accent-primary)" }} />
                  </button>
                  <div style={{ display: "none", position: "absolute", top: "42px", right: 0, zIndex: 100, width: "320px", background: "var(--modal-content-bg)", border: "1px solid var(--glass-border)", borderRadius: "12px", padding: "16px", boxShadow: "0 8px 30px rgba(0,0,0,0.3)" }}>
                    <div style={{ fontWeight: 600, fontSize: "0.9rem", marginBottom: "10px", display: "flex", alignItems: "center", gap: "8px" }}>
                      <Icon name="FileSpreadsheet" size={16} style={{ color: "var(--accent-primary)" }} />
                      Export from Focus SIS
                    </div>
                    <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)", lineHeight: 1.6 }}>
                      <p style={{ margin: "0 0 6px" }}><strong>Reports {'>'} Student Listings {'>'} CSV</strong></p>
                      <p style={{ margin: "0 0 6px" }}>Required columns: Student ID, First Name, Last Name, Email</p>
                      <p style={{ margin: "0 0 6px", color: "var(--text-muted)" }}>Column names are detected automatically (e.g. "student_id", "StudentID", or "Student ID" all work).</p>
                      <p style={{ margin: 0, color: "var(--text-muted)" }}>Combined "Student Name" columns with "Last, First" format are also supported.</p>
                    </div>
                  </div>
                </div>
              </div>
              <div style={{ display: "flex", gap: "10px", alignItems: "center", marginBottom: "15px" }}>
                {!newPeriodName.trim() && (
                  <p
                    style={{
                      fontSize: "0.75rem",
                      color: "var(--text-muted)",
                      margin: 0,
                    }}
                  >
                    Enter a period name above, then click Upload
                  </p>
                )}
                <button
                  onClick={async () => {
                    if (focusImporting) return;
                    setFocusImporting(true);
                    setFocusImportProgress("Starting Focus import...");
                    try {
                      const res = await api.importFromFocus();
                      if (res.error) {
                        addToast(res.error, "error");
                        setFocusImporting(false);
                        return;
                      }
                      // Poll for status
                      const pollInterval = setInterval(async () => {
                        try {
                          const status = await api.getFocusImportStatus();
                          setFocusImportProgress(status.progress || "");
                          if (status.status === "completed") {
                            clearInterval(pollInterval);
                            setFocusImporting(false);
                            setFocusImportProgress("");
                            const r = status.result || {};
                            addToast("Imported " + (r.periods_imported || 0) + " periods, " + (r.total_students || 0) + " students, " + (r.total_contacts || 0) + " parent contacts", "success");
                            const periodsData = await api.listPeriods();
                            setPeriods(periodsData.periods || []);
                          } else if (status.status === "failed") {
                            clearInterval(pollInterval);
                            setFocusImporting(false);
                            setFocusImportProgress("");
                            addToast("Focus import failed: " + (status.error || "Unknown error"), "error");
                          }
                        } catch (err) {
                          clearInterval(pollInterval);
                          setFocusImporting(false);
                          setFocusImportProgress("");
                        }
                      }, 2000);
                    } catch (err) {
                      addToast("Failed to start Focus import: " + err.message, "error");
                      setFocusImporting(false);
                      setFocusImportProgress("");
                    }
                  }}
                  className="btn btn-secondary"
                  disabled={focusImporting}
                  style={{ marginLeft: "auto", opacity: focusImporting ? 0.6 : 1, whiteSpace: "nowrap" }}
                >
                  <Icon name="Download" size={18} />
                  {focusImporting ? "Importing..." : "Import from Focus"}
                </button>
              </div>

              {/* Focus import progress banner */}
              {focusImporting && focusImportProgress && (
                <div style={{
                  padding: "10px 15px",
                  marginBottom: "15px",
                  background: "rgba(59, 130, 246, 0.1)",
                  border: "1px solid rgba(59, 130, 246, 0.3)",
                  borderRadius: "8px",
                  fontSize: "0.85rem",
                  color: "#60a5fa",
                  display: "flex",
                  alignItems: "center",
                  gap: "10px",
                }}>
                  <Icon name="Loader" size={16} style={{ animation: "spin 1s linear infinite" }} />
                  {focusImportProgress}
                </div>
              )}

              {/* Period Cards - Expandable */}
              {sortedPeriods.length > 0 && (
                <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                  {sortedPeriods.map((period) => (
                    <div key={period.filename} style={{ borderRadius: "8px", border: "1px solid var(--glass-border)", overflow: "hidden" }}>
                      {/* Period Header Row */}
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: "10px",
                          padding: "10px 15px",
                          background: expandedPeriod === period.filename ? "rgba(245, 158, 11, 0.08)" : "var(--input-bg)",
                          cursor: "pointer",
                        }}
                        onClick={async () => {
                          if (expandedPeriod === period.filename) {
                            setExpandedPeriod(null);
                            setExpandedStudents([]);
                            setEditingStudentId(null);
                            setAddingStudent(false);
                            return;
                          }
                          setExpandedPeriod(period.filename);
                          setLoadingExpandedStudents(true);
                          setEditingStudentId(null);
                          setAddingStudent(false);
                          try {
                            const [studentsRes, contactsRes] = await Promise.all([
                              api.getPeriodStudents(period.filename),
                              api.getParentContacts(),
                            ]);
                            const students = studentsRes.students || [];
                            const contacts = contactsRes.contacts || {};
                            // Merge contact info into student list
                            // student_email comes from contacts (backend merges from grading results)
                            const merged = students.map(s => {
                              const contact = contacts[s.id] || {};
                              return {
                                ...s,
                                student_email: contact.student_email || "",
                                parent_emails: contact.parent_emails || [],
                                parent_phones: contact.parent_phones || [],
                              };
                            });
                            setExpandedStudents(merged);
                          } catch (err) {
                            addToast("Failed to load students: " + err.message, "error");
                            setExpandedStudents([]);
                          }
                          setLoadingExpandedStudents(false);
                        }}
                      >
                        <Icon
                          name={expandedPeriod === period.filename ? "ChevronDown" : "ChevronRight"}
                          size={16}
                          style={{ color: "#f59e0b", flexShrink: 0 }}
                        />
                        <Icon name="Users" size={16} style={{ color: "#f59e0b", flexShrink: 0 }} />
                        <div style={{ flex: 1 }}>
                          <div style={{ fontWeight: 600, fontSize: "0.9rem", display: "flex", alignItems: "center", gap: "8px" }}>
                            {period.period_name}
                            {period.course_codes && period.course_codes.length > 0 && (
                              <span style={{ fontSize: "0.7rem", padding: "1px 6px", borderRadius: "4px", background: "rgba(139, 92, 246, 0.15)", color: "#a78bfa", fontWeight: 500 }}>
                                {period.course_codes.join(", ")}
                              </span>
                            )}
                          </div>
                          <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                            {period.row_count} students{period.imported_from === "focus" ? " (Focus SIS)" : ""}
                          </div>
                        </div>
                        <select
                          value={period.class_level || "standard"}
                          onClick={(e) => e.stopPropagation()}
                          onChange={async (e) => {
                            e.stopPropagation();
                            const newLevel = e.target.value;
                            await api.updatePeriodLevel(period.filename, newLevel);
                            const data = await api.listPeriods();
                            setPeriods(data.periods || []);
                          }}
                          style={{
                            padding: "4px 8px",
                            borderRadius: "6px",
                            border: "1px solid var(--glass-border)",
                            background: period.class_level === "advanced" ? "rgba(139, 92, 246, 0.2)" : period.class_level === "support" ? "rgba(244, 114, 182, 0.2)" : "var(--input-bg)",
                            color: period.class_level === "advanced" ? "#a78bfa" : period.class_level === "support" ? "#f472b6" : "var(--text-primary)",
                            fontSize: "0.8rem",
                            cursor: "pointer",
                          }}
                        >
                          <option value="standard">Standard</option>
                          <option value="advanced">Advanced</option>
                          <option value="support">Support</option>
                        </select>
                        <button
                          onClick={async (e) => {
                            e.stopPropagation();
                            if (confirm("Delete " + period.period_name + "?")) {
                              await api.deletePeriod(period.filename);
                              const data = await api.listPeriods();
                              setPeriods(data.periods || []);
                              if (expandedPeriod === period.filename) {
                                setExpandedPeriod(null);
                                setExpandedStudents([]);
                              }
                            }
                          }}
                          style={{ padding: "4px 6px", background: "none", border: "none", color: "var(--text-muted)", cursor: "pointer" }}
                        >
                          <Icon name="X" size={14} />
                        </button>
                      </div>

                      {/* Expanded Student List */}
                      {expandedPeriod === period.filename && (
                        <div style={{ borderTop: "1px solid var(--glass-border)", padding: "10px 15px", background: "var(--bg-secondary)" }}>
                          {loadingExpandedStudents ? (
                            <div style={{ textAlign: "center", padding: "20px", color: "var(--text-secondary)", fontSize: "0.85rem" }}>
                              <Icon name="Loader" size={18} style={{ animation: "spin 1s linear infinite", marginRight: "8px" }} />
                              Loading students...
                            </div>
                          ) : expandedStudents.length === 0 ? (
                            <p style={{ fontSize: "0.85rem", color: "var(--text-muted)", textAlign: "center", padding: "10px" }}>No students found</p>
                          ) : (
                            <div style={{ overflowX: "auto" }}>
                              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.8rem" }}>
                                <thead>
                                  <tr style={{ borderBottom: "1px solid var(--glass-border)" }}>
                                    <th style={{ textAlign: "left", padding: "6px 8px", color: "var(--text-secondary)", fontWeight: 600 }}>Student Name</th>
                                    <th style={{ textAlign: "left", padding: "6px 8px", color: "var(--text-secondary)", fontWeight: 600 }}>ID</th>
                                    <th style={{ textAlign: "left", padding: "6px 8px", color: "var(--text-secondary)", fontWeight: 600 }}>Student Email</th>
                                    <th style={{ textAlign: "left", padding: "6px 8px", color: "var(--text-secondary)", fontWeight: 600 }}>Parent Emails</th>
                                    <th style={{ textAlign: "left", padding: "6px 8px", color: "var(--text-secondary)", fontWeight: 600 }}>Parent Phones</th>
                                    <th style={{ textAlign: "right", padding: "6px 8px", color: "var(--text-secondary)", fontWeight: 600, width: "80px" }}>Actions</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {expandedStudents.map((student) => (
                                    <tr key={student.id || student.full} style={{ borderBottom: "1px solid var(--glass-border)" }}>
                                      {editingStudentId === student.id ? (
                                        <>
                                          <td style={{ padding: "6px 8px" }}>
                                            <input type="text" value={editStudentData.student_name || ""} onChange={(e) => setEditStudentData({...editStudentData, student_name: e.target.value})} style={{ width: "100%", padding: "3px 6px", borderRadius: "4px", border: "1px solid var(--glass-border)", background: "var(--input-bg)", color: "var(--text-primary)", fontSize: "0.8rem" }} />
                                          </td>
                                          <td style={{ padding: "6px 8px", color: "var(--text-muted)" }}>{student.id}</td>
                                          <td style={{ padding: "6px 8px" }}>
                                            <input type="email" value={editStudentData.student_email || ""} onChange={(e) => setEditStudentData({...editStudentData, student_email: e.target.value})} placeholder="student@school.edu" style={{ width: "100%", padding: "3px 6px", borderRadius: "4px", border: "1px solid var(--glass-border)", background: "var(--input-bg)", color: "var(--text-primary)", fontSize: "0.8rem" }} />
                                          </td>
                                          <td style={{ padding: "6px 8px" }}>
                                            <input type="text" value={editStudentData.parent_emails || ""} onChange={(e) => setEditStudentData({...editStudentData, parent_emails: e.target.value})} placeholder="email1, email2" style={{ width: "100%", padding: "3px 6px", borderRadius: "4px", border: "1px solid var(--glass-border)", background: "var(--input-bg)", color: "var(--text-primary)", fontSize: "0.8rem" }} />
                                          </td>
                                          <td style={{ padding: "6px 8px" }}>
                                            <input type="text" value={editStudentData.parent_phones || ""} onChange={(e) => setEditStudentData({...editStudentData, parent_phones: e.target.value})} placeholder="(386) 555-1234" style={{ width: "100%", padding: "3px 6px", borderRadius: "4px", border: "1px solid var(--glass-border)", background: "var(--input-bg)", color: "var(--text-primary)", fontSize: "0.8rem" }} />
                                          </td>
                                          <td style={{ padding: "6px 8px", textAlign: "right", whiteSpace: "nowrap" }}>
                                            <button
                                              onClick={async () => {
                                                try {
                                                  const emails = editStudentData.parent_emails ? editStudentData.parent_emails.split(",").map(e => e.trim()).filter(Boolean) : [];
                                                  const phones = editStudentData.parent_phones ? editStudentData.parent_phones.split(",").map(p => p.trim()).filter(Boolean) : [];
                                                  await api.updateStudent({
                                                    period_filename: period.filename,
                                                    student_id: student.id,
                                                    student_name: editStudentData.student_name,
                                                    student_email: editStudentData.student_email || "",
                                                    parent_emails: emails,
                                                    parent_phones: phones,
                                                  });
                                                  setEditingStudentId(null);
                                                  // Refresh
                                                  const [studentsRes, contactsRes] = await Promise.all([api.getPeriodStudents(period.filename), api.getParentContacts()]);
                                                  const contacts = contactsRes.contacts || {};
                                                  setExpandedStudents((studentsRes.students || []).map(s => ({ ...s, student_email: (contacts[s.id] || {}).student_email || "", parent_emails: (contacts[s.id] || {}).parent_emails || [], parent_phones: (contacts[s.id] || {}).parent_phones || [] })));
                                                  addToast("Student updated", "success");
                                                } catch (err) {
                                                  addToast("Update failed: " + err.message, "error");
                                                }
                                              }}
                                              style={{ padding: "2px 6px", background: "rgba(74, 222, 128, 0.2)", border: "1px solid rgba(74, 222, 128, 0.4)", borderRadius: "4px", color: "#4ade80", cursor: "pointer", fontSize: "0.75rem", marginRight: "4px" }}
                                            >Save</button>
                                            <button
                                              onClick={() => setEditingStudentId(null)}
                                              style={{ padding: "2px 6px", background: "none", border: "1px solid var(--glass-border)", borderRadius: "4px", color: "var(--text-muted)", cursor: "pointer", fontSize: "0.75rem" }}
                                            >Cancel</button>
                                          </td>
                                        </>
                                      ) : (
                                        <>
                                          <td style={{ padding: "6px 8px" }}>{student.full || (student.first + " " + student.last)}</td>
                                          <td style={{ padding: "6px 8px", color: "var(--text-secondary)" }}>{student.id || "\u2014"}</td>
                                          <td style={{ padding: "6px 8px", color: student.student_email ? "var(--text-primary)" : "var(--text-muted)" }}>{student.student_email || "\u2014"}</td>
                                          <td style={{ padding: "6px 8px", color: student.parent_emails.length ? "var(--text-primary)" : "var(--text-muted)" }}>
                                            {student.parent_emails.length > 0 ? student.parent_emails.join(", ") : "\u2014"}
                                          </td>
                                          <td style={{ padding: "6px 8px", color: student.parent_phones.length ? "var(--text-primary)" : "var(--text-muted)" }}>
                                            {student.parent_phones.length > 0 ? student.parent_phones.join(", ") : "\u2014"}
                                          </td>
                                          <td style={{ padding: "6px 8px", textAlign: "right", whiteSpace: "nowrap" }}>
                                            {student.id && (
                                              <>
                                                <button
                                                  onClick={() => {
                                                    setEditingStudentId(student.id);
                                                    setEditStudentData({
                                                      student_name: student.full || (student.first + " " + student.last),
                                                      student_email: student.student_email || "",
                                                      parent_emails: student.parent_emails.join(", "),
                                                      parent_phones: student.parent_phones.join(", "),
                                                    });
                                                  }}
                                                  title="Edit"
                                                  style={{ padding: "2px 4px", background: "none", border: "none", color: "var(--text-muted)", cursor: "pointer" }}
                                                ><Icon name="Pencil" size={13} /></button>
                                                <button
                                                  onClick={async () => {
                                                    if (!confirm("Remove " + (student.full || student.first + " " + student.last) + " from this period?")) return;
                                                    try {
                                                      await api.removeStudent({ period_filename: period.filename, student_id: student.id });
                                                      const [studentsRes, contactsRes] = await Promise.all([api.getPeriodStudents(period.filename), api.getParentContacts()]);
                                                      const contacts = contactsRes.contacts || {};
                                                      setExpandedStudents((studentsRes.students || []).map(s => ({ ...s, student_email: (contacts[s.id] || {}).student_email || "", parent_emails: (contacts[s.id] || {}).parent_emails || [], parent_phones: (contacts[s.id] || {}).parent_phones || [] })));
                                                      const periodsData = await api.listPeriods();
                                                      setPeriods(periodsData.periods || []);
                                                      addToast("Student removed", "success");
                                                    } catch (err) {
                                                      addToast("Remove failed: " + err.message, "error");
                                                    }
                                                  }}
                                                  title="Remove"
                                                  style={{ padding: "2px 4px", background: "none", border: "none", color: "var(--text-muted)", cursor: "pointer" }}
                                                ><Icon name="Trash2" size={13} /></button>
                                              </>
                                            )}
                                          </td>
                                        </>
                                      )}
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          )}

                          {/* Add Student Form */}
                          {addingStudent ? (
                            <div style={{ marginTop: "10px", padding: "10px", background: "var(--input-bg)", borderRadius: "6px", border: "1px solid var(--glass-border)" }}>
                              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px", marginBottom: "8px" }}>
                                <input type="text" placeholder="Student Name (Last; First)" value={newStudent.name} onChange={(e) => setNewStudent({...newStudent, name: e.target.value})} style={{ padding: "6px 8px", borderRadius: "4px", border: "1px solid var(--glass-border)", background: "var(--bg-secondary)", color: "var(--text-primary)", fontSize: "0.8rem" }} />
                                <input type="text" placeholder="Student ID" value={newStudent.student_id} onChange={(e) => setNewStudent({...newStudent, student_id: e.target.value})} style={{ padding: "6px 8px", borderRadius: "4px", border: "1px solid var(--glass-border)", background: "var(--bg-secondary)", color: "var(--text-primary)", fontSize: "0.8rem" }} />
                                <input type="text" placeholder="Grade (e.g., 06)" value={newStudent.grade} onChange={(e) => setNewStudent({...newStudent, grade: e.target.value})} style={{ padding: "6px 8px", borderRadius: "4px", border: "1px solid var(--glass-border)", background: "var(--bg-secondary)", color: "var(--text-primary)", fontSize: "0.8rem" }} />
                                <input type="email" placeholder="Student Email" value={newStudent.student_email} onChange={(e) => setNewStudent({...newStudent, student_email: e.target.value})} style={{ padding: "6px 8px", borderRadius: "4px", border: "1px solid var(--glass-border)", background: "var(--bg-secondary)", color: "var(--text-primary)", fontSize: "0.8rem" }} />
                                <input type="text" placeholder="Parent Emails (comma-separated)" value={newStudent.parent_emails} onChange={(e) => setNewStudent({...newStudent, parent_emails: e.target.value})} style={{ padding: "6px 8px", borderRadius: "4px", border: "1px solid var(--glass-border)", background: "var(--bg-secondary)", color: "var(--text-primary)", fontSize: "0.8rem" }} />
                                <input type="text" placeholder="Parent Phones (comma-separated)" value={newStudent.parent_phones} onChange={(e) => setNewStudent({...newStudent, parent_phones: e.target.value})} style={{ padding: "6px 8px", borderRadius: "4px", border: "1px solid var(--glass-border)", background: "var(--bg-secondary)", color: "var(--text-primary)", fontSize: "0.8rem" }} />
                              </div>
                              <div style={{ display: "flex", gap: "8px" }}>
                                <button
                                  onClick={async () => {
                                    if (!newStudent.name.trim()) { addToast("Student name is required", "warning"); return; }
                                    try {
                                      const emails = newStudent.parent_emails ? newStudent.parent_emails.split(",").map(e => e.trim()).filter(Boolean) : [];
                                      const phones = newStudent.parent_phones ? newStudent.parent_phones.split(",").map(p => p.trim()).filter(Boolean) : [];
                                      const res = await api.addStudent({
                                        period_filename: period.filename,
                                        student_name: newStudent.name,
                                        student_id: newStudent.student_id,
                                        student_email: newStudent.student_email,
                                        grade: newStudent.grade,
                                        parent_emails: emails,
                                        parent_phones: phones,
                                      });
                                      if (res.error) { addToast(res.error, "error"); return; }
                                      setNewStudent({ name: '', student_id: '', grade: '', student_email: '', parent_emails: '', parent_phones: '' });
                                      setAddingStudent(false);
                                      // Refresh
                                      const [studentsRes, contactsRes] = await Promise.all([api.getPeriodStudents(period.filename), api.getParentContacts()]);
                                      const contacts = contactsRes.contacts || {};
                                      setExpandedStudents((studentsRes.students || []).map(s => ({ ...s, student_email: (contacts[s.id] || {}).student_email || "", parent_emails: (contacts[s.id] || {}).parent_emails || [], parent_phones: (contacts[s.id] || {}).parent_phones || [] })));
                                      const periodsData = await api.listPeriods();
                                      setPeriods(periodsData.periods || []);
                                      addToast("Student added", "success");
                                    } catch (err) {
                                      addToast("Add failed: " + err.message, "error");
                                    }
                                  }}
                                  className="btn btn-primary"
                                  style={{ fontSize: "0.8rem", padding: "5px 12px" }}
                                >Add Student</button>
                                <button
                                  onClick={() => { setAddingStudent(false); setNewStudent({ name: '', student_id: '', grade: '', student_email: '', parent_emails: '', parent_phones: '' }); }}
                                  className="btn btn-secondary"
                                  style={{ fontSize: "0.8rem", padding: "5px 12px" }}
                                >Cancel</button>
                              </div>
                            </div>
                          ) : (
                            <button
                              onClick={() => setAddingStudent(true)}
                              style={{
                                marginTop: "10px",
                                padding: "6px 12px",
                                background: "none",
                                border: "1px dashed var(--glass-border)",
                                borderRadius: "6px",
                                color: "var(--text-secondary)",
                                cursor: "pointer",
                                fontSize: "0.8rem",
                                display: "flex",
                                alignItems: "center",
                                gap: "6px",
                                width: "100%",
                                justifyContent: "center",
                              }}
                            >
                              <Icon name="Plus" size={14} />
                              Add Student
                            </button>
                          )}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
              </>
            )}

            {/* IEP/504 Accommodations Section */}
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
                <Icon
                  name="Heart"
                  size={20}
                  style={{ color: "#f472b6" }}
                />
                IEP/504 Accommodations
                <span
                  style={{
                    fontSize: "0.7rem",
                    padding: "2px 8px",
                    background: "rgba(74, 222, 128, 0.2)",
                    color: "#4ade80",
                    borderRadius: "4px",
                    fontWeight: 500,
                  }}
                >
                  FERPA Compliant
                </span>
              </h3>
              <p
                style={{
                  fontSize: "0.85rem",
                  color: "var(--text-secondary)",
                  marginBottom: "20px",
                }}
              >
                Assign accommodation presets to students for
                personalized feedback. Only accommodation types are sent
                to AI - never student names or IDs.
              </p>

              {/* Available Presets */}
              <div style={{ marginBottom: "20px" }}>
                <div
                  style={{
                    fontWeight: 600,
                    marginBottom: "12px",
                    fontSize: "0.95rem",
                  }}
                >
                  Available Presets
                </div>
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns:
                      "repeat(auto-fill, minmax(200px, 1fr))",
                    gap: "10px",
                  }}
                >
                  {accommodationPresets.map((preset) => (
                    <div
                      key={preset.id}
                      style={{
                        padding: "12px",
                        background: "var(--input-bg)",
                        borderRadius: "8px",
                        border: "1px solid var(--input-border)",
                      }}
                    >
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: "8px",
                          marginBottom: "6px",
                        }}
                      >
                        <Icon
                          name={preset.icon || "FileText"}
                          size={16}
                          style={{ color: "#f472b6" }}
                        />
                        <span
                          style={{
                            fontWeight: 600,
                            fontSize: "0.85rem",
                          }}
                        >
                          {preset.name}
                        </span>
                      </div>
                      <p
                        style={{
                          fontSize: "0.75rem",
                          color: "var(--text-muted)",
                          margin: 0,
                        }}
                      >
                        {preset.description}
                      </p>
                    </div>
                  ))}
                </div>
              </div>

              {/* Student Accommodations List */}
              <div style={{ marginBottom: "20px" }}>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    marginBottom: "12px",
                  }}
                >
                  <div style={{ fontWeight: 600, fontSize: "0.95rem" }}>
                    Student Accommodations (
                    {Object.keys(studentAccommodations).length}{" "}
                    students)
                  </div>
                  <button
                    onClick={() =>
                      setAccommodationModal({
                        show: true,
                        studentId: null,
                      })
                    }
                    className="btn btn-primary"
                    style={{ fontSize: "0.8rem", padding: "6px 12px" }}
                  >
                    <Icon name="Plus" size={14} />
                    Add Student
                  </button>
                </div>

                {Object.keys(studentAccommodations).length > 0 ? (
                  <div
                    style={{
                      maxHeight: "200px",
                      overflowY: "auto",
                      display: "flex",
                      flexDirection: "column",
                      gap: "8px",
                    }}
                  >
                    {Object.entries(studentAccommodations).map(
                      ([studentId, data]) => (
                        <div
                          key={studentId}
                          style={{
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "space-between",
                            padding: "10px 14px",
                            background: "var(--input-bg)",
                            borderRadius: "8px",
                            border: "1px solid var(--input-border)",
                          }}
                        >
                          <div>
                            <div
                              style={{
                                fontWeight: 600,
                                fontSize: "0.9rem",
                              }}
                            >
                              {data.student_name || "ID: " + studentId}
                            </div>
                            <div
                              style={{
                                display: "flex",
                                gap: "6px",
                                marginTop: "4px",
                                flexWrap: "wrap",
                              }}
                            >
                              {data.presets.map((preset) => (
                                <span
                                  key={preset.id}
                                  style={{
                                    padding: "2px 8px",
                                    background:
                                      preset.id === "ell_support"
                                        ? "rgba(96, 165, 250, 0.15)"
                                        : "rgba(244, 114, 182, 0.15)",
                                    color:
                                      preset.id === "ell_support"
                                        ? "#60a5fa"
                                        : "#f472b6",
                                    borderRadius: "4px",
                                    fontSize: "0.7rem",
                                    fontWeight: 500,
                                  }}
                                >
                                  {preset.name}
                                </span>
                              ))}
                              {data.custom_notes && (
                                <span
                                  style={{
                                    padding: "2px 8px",
                                    background:
                                      "rgba(99, 102, 241, 0.15)",
                                    color: "#818cf8",
                                    borderRadius: "4px",
                                    fontSize: "0.7rem",
                                    fontWeight: 500,
                                  }}
                                >
                                  Custom Notes
                                </span>
                              )}
                            </div>
                          </div>
                          <div style={{ display: "flex", gap: "6px" }}>
                            <button
                              onClick={async () => {
                                setSelectedAccommodationPresets(
                                  data.presets.map((p) => p.id),
                                );
                                setAccommodationCustomNotes(
                                  data.custom_notes || "",
                                );
                                // Load ELL language if ELL Support is active
                                if (
                                  data.presets.some(
                                    (p) => p.id === "ell_support",
                                  )
                                ) {
                                  try {
                                    const ellData =
                                      await api.getEllStudents();
                                    setAccommEllLanguage(
                                      ellData?.[studentId]?.language ||
                                        "",
                                    );
                                  } catch (e) {
                                    setAccommEllLanguage("");
                                  }
                                } else {
                                  setAccommEllLanguage("");
                                }
                                setAccommodationModal({
                                  show: true,
                                  studentId,
                                });
                              }}
                              className="btn btn-secondary"
                              style={{ padding: "4px 8px" }}
                            >
                              <Icon name="Edit2" size={14} />
                            </button>
                            <button
                              onClick={async () => {
                                if (
                                  confirm(
                                    "Remove accommodations for this student?",
                                  )
                                ) {
                                  try {
                                    await api.deleteStudentAccommodation(
                                      studentId,
                                    );
                                    const newData = {
                                      ...studentAccommodations,
                                    };
                                    delete newData[studentId];
                                    setStudentAccommodations(newData);
                                  } catch (err) {
                                    addToast(
                                      "Error removing accommodation: " +
                                        err.message,
                                      "error",
                                    );
                                  }
                                }
                              }}
                              className="btn btn-secondary"
                              style={{
                                padding: "4px 8px",
                                color: "#ef4444",
                              }}
                            >
                              <Icon name="Trash2" size={14} />
                            </button>
                          </div>
                        </div>
                      ),
                    )}
                  </div>
                ) : (
                  <div
                    style={{
                      padding: "30px",
                      textAlign: "center",
                      background: "var(--input-bg)",
                      borderRadius: "8px",
                      border: "1px dashed var(--input-border)",
                    }}
                  >
                    <Icon
                      name="Heart"
                      size={32}
                      style={{
                        color: "var(--text-muted)",
                        marginBottom: "10px",
                      }}
                    />
                    <p
                      style={{
                        color: "var(--text-muted)",
                        fontSize: "0.85rem",
                        margin: 0,
                      }}
                    >
                      No students with accommodations yet. Add students
                      from your roster.
                    </p>
                  </div>
                )}
              </div>

              {/* Import/Export */}
              <div
                style={{
                  padding: "15px",
                  background: "var(--input-bg)",
                  borderRadius: "10px",
                  border: "1px solid var(--input-border)",
                }}
              >
                <div style={{ fontWeight: 600, marginBottom: "12px" }}>
                  Import & Export
                </div>
                <div
                  style={{
                    display: "flex",
                    gap: "10px",
                    flexWrap: "wrap",
                  }}
                >
                  <label
                    className="btn btn-secondary"
                    style={{ fontSize: "0.85rem", cursor: "pointer" }}
                  >
                    <Icon name="Upload" size={16} />
                    Import from CSV
                    <input
                      type="file"
                      accept=".csv"
                      style={{ display: "none" }}
                      onChange={async (e) => {
                        const file = e.target.files?.[0];
                        if (!file) return;
                        try {
                          const result = await api.importAccommodations(
                            file,
                            "student_id",
                            "accommodation_type",
                            "accommodation_notes",
                          );
                          addToast(
                            "Import complete: " +
                              result.imported +
                              " imported, " +
                              result.skipped +
                              " skipped",
                            "success",
                          );
                          // Reload accommodations
                          const data =
                            await api.getStudentAccommodations();
                          if (data.accommodations)
                            setStudentAccommodations(
                              data.accommodations,
                            );
                        } catch (err) {
                          addToast(
                            "Import failed: " + err.message,
                            "error",
                          );
                        }
                        e.target.value = "";
                      }}
                    />
                  </label>
                  <button
                    onClick={async () => {
                      try {
                        const data = await api.exportAccommodations();
                        const blob = new Blob(
                          [JSON.stringify(data, null, 2)],
                          { type: "application/json" },
                        );
                        const url = URL.createObjectURL(blob);
                        const a = document.createElement("a");
                        a.href = url;
                        a.download =
                          "graider_accommodations_" +
                          new Date().toISOString().split("T")[0] +
                          ".json";
                        a.click();
                        URL.revokeObjectURL(url);
                      } catch (err) {
                        addToast(
                          "Export failed: " + err.message,
                          "error",
                        );
                      }
                    }}
                    className="btn btn-secondary"
                    style={{ fontSize: "0.85rem" }}
                  >
                    <Icon name="Download" size={16} />
                    Export Accommodations
                  </button>
                </div>
                <p
                  style={{
                    fontSize: "0.75rem",
                    color: "var(--text-muted)",
                    marginTop: "10px",
                  }}
                >
                  CSV should have columns: student_id,
                  accommodation_type, accommodation_notes (optional)
                </p>
              </div>
            </div>

            {/* Parent Contacts Upload */}
            <div style={{ marginTop: "30px" }}>
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
                <Icon
                  name="Contact"
                  size={20}
                  style={{ color: "#f59e0b" }}
                />
                Parent Contacts
              </h3>
              <p
                style={{
                  fontSize: "0.85rem",
                  color: "var(--text-secondary)",
                  marginBottom: "15px",
                }}
              >
                Upload class list Excel file with parent email and phone
                columns. Used for Focus export and Outlook email generation.
              </p>

              <input
                ref={parentContactsInputRef}
                type="file"
                accept=".xlsx,.xls,.csv"
                style={{ display: "none" }}
                onChange={async (e) => {
                  var file = e.target.files?.[0];
                  if (!file) return;
                  setUploadingParentContacts(true);
                  try {
                    var result = await api.previewParentContacts(file);
                    if (result.error) {
                      addToast(result.error, "error");
                    } else {
                      var suggested = result.suggested_mapping || {};
                      setParentContactMapping({
                        show: true,
                        preview: result,
                        mapping: {
                          name_col: suggested.name_col || "",
                          name_format: suggested.name_format || "last_first",
                          id_col: suggested.id_col || "",
                          id_strip_digits: suggested.id_strip_digits || 0,
                          contact_cols: suggested.contact_cols || [],
                          period_col: suggested.period_col || "",
                        },
                      });
                    }
                  } catch (err) {
                    addToast("Upload failed: " + err.message, "error");
                  }
                  setUploadingParentContacts(false);
                  e.target.value = "";
                }}
              />

              <button
                onClick={() => parentContactsInputRef.current?.click()}
                className="btn btn-secondary"
                disabled={uploadingParentContacts}
                style={{ marginBottom: "15px" }}
              >
                <Icon name="Upload" size={18} />
                {uploadingParentContacts ? "Reading file..." : "Upload Class List (.xlsx, .csv)"}
              </button>

              {parentContacts && parentContacts.count > 0 && (
                <div
                  style={{
                    padding: "12px 15px",
                    background: "var(--input-bg)",
                    borderRadius: "8px",
                    border: "1px solid var(--glass-border)",
                    fontSize: "0.85rem",
                  }}
                >
                  <div style={{ fontWeight: 600, marginBottom: "8px" }}>
                    {parentContacts.count} students loaded
                  </div>
                  <div style={{ color: "var(--text-secondary)" }}>
                    {parentContacts.with_email} with parent email
                    {parentContacts.without_email > 0 && (
                      <span style={{ color: "#f59e0b" }}>
                        {" "}({parentContacts.without_email} missing email)
                      </span>
                    )}
                  </div>
                  {parentContacts.period_stats && (
                    <div style={{ marginTop: "8px", display: "flex", flexWrap: "wrap", gap: "6px" }}>
                      {Object.entries(parentContacts.period_stats).map(function(entry) {
                        return (
                          <span
                            key={entry[0]}
                            style={{
                              padding: "2px 8px",
                              background: "rgba(99,102,241,0.15)",
                              borderRadius: "4px",
                              fontSize: "0.75rem",
                            }}
                          >
                            {entry[0]}: {entry[1].total}
                          </span>
                        );
                      })}
                    </div>
                  )}
                </div>
              )}
            </div>
              </>
  );
}
