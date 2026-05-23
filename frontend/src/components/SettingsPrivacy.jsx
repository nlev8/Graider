import React from "react";
import Icon from "./Icon";
import * as api from "../services/api";
import { getAuthHeaders } from "../services/api";

export default function SettingsPrivacy({ addToast, config, exportStudentSearch, importFileRef, importStudentData, periods, selectedStudentHistory, setConfig, setExportStudentSearch, setImportStudentData, setSelectedStudentHistory, setStudentHistoryList, setStudentHistoryLoading, studentHistoryList, studentHistoryLoading }) {
  return (
              <div data-tutorial="settings-privacy">
            {/* FERPA Compliance & Data Privacy */}
            <div>
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
                  name="Shield"
                  size={20}
                  style={{ color: "#10b981" }}
                />
                Privacy & Data (FERPA)
              </h3>
              <p
                style={{
                  fontSize: "0.85rem",
                  color: "var(--text-secondary)",
                  marginBottom: "20px",
                }}
              >
                Graider is designed for FERPA compliance. Student names
                are sanitized before AI processing. Your data is stored
                securely on Graider's server and is never shared with
                third-party vendors or aggregated across districts.
              </p>

              {/* Privacy Features */}
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(2, 1fr)",
                  gap: "15px",
                  marginBottom: "20px",
                }}
              >
                <div
                  style={{
                    padding: "15px",
                    background: "rgba(74,222,128,0.1)",
                    borderRadius: "10px",
                    border: "1px solid rgba(74,222,128,0.2)",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "8px",
                      marginBottom: "8px",
                    }}
                  >
                    <Icon
                      name="CheckCircle"
                      size={16}
                      style={{ color: "#4ade80" }}
                    />
                    <span
                      style={{ fontWeight: 600, fontSize: "0.9rem" }}
                    >
                      PII Sanitization
                    </span>
                  </div>
                  <p
                    style={{
                      fontSize: "0.8rem",
                      color: "var(--text-secondary)",
                      margin: 0,
                    }}
                  >
                    Student names, IDs, emails, and phone numbers are
                    removed before AI processing
                  </p>
                </div>

                <div
                  style={{
                    padding: "15px",
                    background: "rgba(74,222,128,0.1)",
                    borderRadius: "10px",
                    border: "1px solid rgba(74,222,128,0.2)",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "8px",
                      marginBottom: "8px",
                    }}
                  >
                    <Icon
                      name="CheckCircle"
                      size={16}
                      style={{ color: "#4ade80" }}
                    />
                    <span
                      style={{ fontWeight: 600, fontSize: "0.9rem" }}
                    >
                      No Third-Party Sharing
                    </span>
                  </div>
                  <p
                    style={{
                      fontSize: "0.8rem",
                      color: "var(--text-secondary)",
                      margin: 0,
                    }}
                  >
                    Student data is never sold, shared with vendors, or
                    aggregated across districts
                  </p>
                </div>

                <div
                  style={{
                    padding: "15px",
                    background: "rgba(74,222,128,0.1)",
                    borderRadius: "10px",
                    border: "1px solid rgba(74,222,128,0.2)",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "8px",
                      marginBottom: "8px",
                    }}
                  >
                    <Icon
                      name="CheckCircle"
                      size={16}
                      style={{ color: "#4ade80" }}
                    />
                    <span
                      style={{ fontWeight: 600, fontSize: "0.9rem" }}
                    >
                      No AI Training
                    </span>
                  </div>
                  <p
                    style={{
                      fontSize: "0.8rem",
                      color: "var(--text-secondary)",
                      margin: 0,
                    }}
                  >
                    OpenAI and Anthropic APIs do not use submitted data
                    to train models (per their policies)
                  </p>
                </div>

                <div
                  style={{
                    padding: "15px",
                    background: "rgba(74,222,128,0.1)",
                    borderRadius: "10px",
                    border: "1px solid rgba(74,222,128,0.2)",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "8px",
                      marginBottom: "8px",
                    }}
                  >
                    <Icon
                      name="CheckCircle"
                      size={16}
                      style={{ color: "#4ade80" }}
                    />
                    <span
                      style={{ fontWeight: 600, fontSize: "0.9rem" }}
                    >
                      Audit Logging
                    </span>
                  </div>
                  <p
                    style={{
                      fontSize: "0.8rem",
                      color: "var(--text-secondary)",
                      margin: 0,
                    }}
                  >
                    All data access is logged for compliance
                    tracking and FERPA audit trails
                  </p>
                </div>
              </div>

              {/* Data Management Actions */}
              <div
                style={{
                  padding: "15px",
                  background: "var(--input-bg)",
                  borderRadius: "10px",
                  border: "1px solid var(--input-border)",
                }}
              >
                <div style={{ fontWeight: 600, marginBottom: "12px" }}>
                  Data Management
                </div>
                <div
                  style={{
                    display: "flex",
                    gap: "10px",
                    flexWrap: "wrap",
                  }}
                >
                  <button
                    onClick={async () => {
                      try {
                        const authHdrs = await getAuthHeaders();
                        const response = await fetch(
                          "/api/ferpa/data-summary",
                          { headers: { ...authHdrs } },
                        );
                        const data = await response.json();
                        alert(
                          `Data Storage Summary\n\n` +
                            `• Grading Results: ${data.results.count} records\n` +
                            `• Settings: ${data.settings.exists ? "Saved" : "Not saved"}\n` +
                            `• Audit Log: ${data.audit_log.exists ? "Active" : "Not started"}\n\n` +
                            `Data Locations:\n` +
                            data.data_locations.join("\n"),
                        );
                      } catch (err) {
                        addToast(
                          "Failed to fetch data summary",
                          "error",
                        );
                      }
                    }}
                    className="btn btn-secondary"
                    style={{ fontSize: "0.85rem" }}
                  >
                    <Icon name="Database" size={16} />
                    View Data Summary
                  </button>

                  <button
                    onClick={async () => {
                      try {
                        const authHdrs2 = await getAuthHeaders();
                        const response = await fetch(
                          "/api/ferpa/export-data",
                          { headers: { ...authHdrs2 } },
                        );
                        const data = await response.json();
                        const blob = new Blob(
                          [JSON.stringify(data, null, 2)],
                          { type: "application/json" },
                        );
                        const url = URL.createObjectURL(blob);
                        const a = document.createElement("a");
                        a.href = url;
                        a.download = `graider_export_${new Date().toISOString().split("T")[0]}.json`;
                        a.click();
                        URL.revokeObjectURL(url);
                      } catch (err) {
                        addToast("Failed to export data", "error");
                      }
                    }}
                    className="btn btn-secondary"
                    style={{ fontSize: "0.85rem" }}
                  >
                    <Icon name="Download" size={16} />
                    Export All Data
                  </button>

                  {/* Export Individual Student Data */}
                  <div style={{ position: "relative", display: "inline-block" }}>
                    <button
                      onClick={async () => {
                        if (exportStudentSearch.active) {
                          setExportStudentSearch({ active: false, query: "", results: [], allStudents: [] });
                          return;
                        }
                        // Load all students from all periods
                        let all = [];
                        try {
                          const results = await Promise.all(
                            periods.map((p) =>
                              api.getPeriodStudents(p.filename)
                                .then((d) => (d.students || []).map((s) => ({ ...s, period: p.period_name })))
                                .catch(() => [])
                            )
                          );
                          all = results.flat();
                        } catch (e) { /* ignore */ }
                        setExportStudentSearch({ active: true, query: "", results: [], allStudents: all });
                      }}
                      className="btn btn-secondary"
                      style={{ fontSize: "0.85rem" }}
                    >
                      <Icon name="UserCheck" size={16} />
                      Export Student Data
                    </button>
                    {exportStudentSearch.active && (
                      <div style={{ position: "absolute", top: "100%", left: 0, marginTop: "6px", zIndex: 100, width: "280px" }}>
                        <input
                          type="text"
                          placeholder="Type student name..."
                          value={exportStudentSearch.query}
                          onChange={(e) => {
                            const q = e.target.value;
                            const lq = q.toLowerCase().replace(/['"]/g, "");
                            const suggestions = lq.length >= 2 ? exportStudentSearch.allStudents.filter((s) => {
                              const full = (s.full || "").toLowerCase().replace(/['"]/g, "");
                              const first = (s.first || "").toLowerCase();
                              const last = (s.last || "").toLowerCase();
                              return full.includes(lq) || first.includes(lq) || last.includes(lq);
                            }).slice(0, 5) : [];
                            setExportStudentSearch(prev => ({ ...prev, query: q, results: suggestions }));
                          }}
                          style={{
                            width: "100%",
                            padding: "8px 12px",
                            borderRadius: "8px",
                            border: "1px solid var(--glass-border)",
                            background: "var(--modal-content-bg)",
                            color: "var(--text-primary)",
                            fontSize: "0.85rem",
                          }}
                          autoFocus
                        />
                        {exportStudentSearch.results.length > 0 && (
                          <div style={{
                            background: "var(--modal-content-bg)",
                            border: "1px solid var(--glass-border)",
                            borderRadius: "8px",
                            marginTop: "4px",
                            boxShadow: "0 4px 12px rgba(0,0,0,0.3)",
                            maxHeight: "200px",
                            overflowY: "auto",
                          }}>
                            {exportStudentSearch.results.map((student, idx) => (
                              <div
                                key={idx}
                                onClick={async () => {
                                  const name = student.full || (student.first + " " + student.last);
                                  setExportStudentSearch({ active: false, query: "", results: [] });
                                  try {
                                    const authH = await getAuthHeaders();
                                    const resp = await fetch("/api/ferpa/export-student", {
                                      method: "POST",
                                      headers: { "Content-Type": "application/json", ...authH },
                                      body: JSON.stringify({ student_name: name }),
                                    });
                                    const d = await resp.json();
                                    if (d.status === "success") {
                                      addToast("Exported " + d.record_count + " records for " + d.student_name, "success");
                                    } else {
                                      addToast("Export failed: " + (d.error || "Unknown error"), "error");
                                    }
                                  } catch (err) {
                                    addToast("Export failed: " + err.message, "error");
                                  }
                                }}
                                style={{
                                  padding: "10px 12px",
                                  cursor: "pointer",
                                  borderBottom: idx < exportStudentSearch.results.length - 1 ? "1px solid var(--glass-border)" : "none",
                                  display: "flex",
                                  alignItems: "center",
                                  gap: "10px",
                                }}
                                onMouseEnter={(e) => (e.target.style.background = "var(--glass-bg)")}
                                onMouseLeave={(e) => (e.target.style.background = "transparent")}
                              >
                                <Icon name="User" size={16} style={{ color: "var(--text-muted)", flexShrink: 0 }} />
                                <div>
                                  <div style={{ fontWeight: 500 }}>
                                    {student.full || (student.first + " " + student.last)}
                                  </div>
                                  {student.period && (
                                    <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                                      {student.period}
                                    </div>
                                  )}
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Import Student Data */}
                  <div style={{ position: "relative", display: "inline-block" }}>
                    <input
                      type="file"
                      accept=".json"
                      ref={importFileRef}
                      style={{ display: "none" }}
                      onChange={async (e) => {
                        const f = e.target.files[0];
                        if (!f) return;
                        e.target.value = "";
                        try {
                          const formData = new FormData();
                          formData.append("file", f);
                          formData.append("preview", "true");
                          const authH = await getAuthHeaders();
                          const resp = await fetch("/api/ferpa/import-student", {
                            method: "POST",
                            headers: { ...authH },
                            body: formData,
                          });
                          const d = await resp.json();
                          if (d.status === "preview") {
                            setImportStudentData({ active: true, preview: d, file: f, importing: false, selectedPeriod: "" });
                          } else {
                            addToast("Import failed: " + (d.error || "Unknown error"), "error");
                          }
                        } catch (err) {
                          addToast("Import failed: " + err.message, "error");
                        }
                      }}
                    />
                    <button
                      onClick={() => {
                        if (importStudentData.active) {
                          setImportStudentData({ active: false, preview: null, file: null, importing: false, selectedPeriod: "" });
                        } else {
                          importFileRef.current && importFileRef.current.click();
                        }
                      }}
                      className="btn btn-secondary"
                      style={{ fontSize: "0.85rem" }}
                    >
                      <Icon name="Upload" size={16} />
                      Import Student Data
                    </button>
                    {importStudentData.active && importStudentData.preview && (
                      <div style={{
                        position: "absolute", top: "100%", left: 0, marginTop: "6px", zIndex: 100, width: "320px",
                        background: "var(--modal-content-bg)", border: "1px solid var(--glass-border)",
                        borderRadius: "8px", padding: "14px", boxShadow: "0 4px 12px rgba(0,0,0,0.3)",
                      }}>
                        <div style={{ fontWeight: 600, marginBottom: "8px" }}>
                          Import {importStudentData.preview.student_name}?
                        </div>
                        <div style={{ fontSize: "0.82rem", color: "var(--text-muted)", marginBottom: "10px" }}>
                          {importStudentData.preview.detail_text}
                          {importStudentData.preview.original_period && (
                            <span> (from {importStudentData.preview.original_period})</span>
                          )}
                        </div>
                        {periods.length > 0 && (
                          <div style={{ marginBottom: "10px" }}>
                            <label style={{ fontSize: "0.8rem", color: "var(--text-muted)", display: "block", marginBottom: "4px" }}>
                              Add to period:
                            </label>
                            <select
                              value={importStudentData.selectedPeriod}
                              onChange={(e) => setImportStudentData(prev => ({ ...prev, selectedPeriod: e.target.value }))}
                              style={{
                                width: "100%", padding: "6px 8px", borderRadius: "6px",
                                border: "1px solid var(--glass-border)", background: "var(--modal-content-bg)",
                                color: "var(--text-primary)", fontSize: "0.85rem",
                              }}
                            >
                              <option value="">No period (data only)</option>
                              {periods.map((p) => (
                                <option key={p.filename} value={p.filename}>{p.period_name}</option>
                              ))}
                            </select>
                          </div>
                        )}
                        <div style={{ display: "flex", gap: "8px" }}>
                          <button
                            className="btn btn-primary"
                            style={{ fontSize: "0.8rem", flex: 1 }}
                            disabled={importStudentData.importing}
                            onClick={async () => {
                              setImportStudentData(prev => ({ ...prev, importing: true }));
                              try {
                                const formData = new FormData();
                                formData.append("file", importStudentData.file);
                                if (importStudentData.selectedPeriod) {
                                  formData.append("period_filename", importStudentData.selectedPeriod);
                                }
                                const authH = await getAuthHeaders();
                                const resp = await fetch("/api/ferpa/import-student", {
                                  method: "POST",
                                  headers: { ...authH },
                                  body: formData,
                                });
                                const d = await resp.json();
                                if (d.status === "success") {
                                  const count = (d.imported_sections.results || 0);
                                  addToast("Imported " + (count ? count + " records" : "data") + " for " + d.student_name, "success");
                                  setImportStudentData({ active: false, preview: null, file: null, importing: false, selectedPeriod: "" });
                                } else {
                                  addToast("Import failed: " + (d.error || "Unknown error"), "error");
                                  setImportStudentData(prev => ({ ...prev, importing: false }));
                                }
                              } catch (err) {
                                addToast("Import failed: " + err.message, "error");
                                setImportStudentData(prev => ({ ...prev, importing: false }));
                              }
                            }}
                          >
                            {importStudentData.importing ? "Importing..." : "Confirm Import"}
                          </button>
                          <button
                            className="btn btn-secondary"
                            style={{ fontSize: "0.8rem" }}
                            onClick={() => setImportStudentData({ active: false, preview: null, file: null, importing: false, selectedPeriod: "" })}
                          >
                            Cancel
                          </button>
                        </div>
                      </div>
                    )}
                  </div>

                  <button
                    onClick={async () => {
                      if (
                        !confirm(
                          "⚠️ DELETE ALL STUDENT DATA?\n\n" +
                            "This will permanently delete:\n" +
                            "• All grading results\n" +
                            "• Current session data\n\n" +
                            "This action cannot be undone.\n\n" +
                            "Type 'DELETE' in the next prompt to confirm.",
                        )
                      )
                        return;

                      const confirmText = prompt(
                        "Type DELETE to confirm:",
                      );
                      if (confirmText !== "DELETE") {
                        addToast("Deletion cancelled", "warning");
                        return;
                      }

                      try {
                        const authHdrs3 = await getAuthHeaders();
                        const response = await fetch(
                          "/api/ferpa/delete-all-data",
                          {
                            method: "POST",
                            headers: {
                              "Content-Type": "application/json",
                              ...authHdrs3,
                            },
                            body: JSON.stringify({ confirm: true }),
                          },
                        );
                        const data = await response.json();
                        if (data.status === "success") {
                          addToast(
                            "All student data has been deleted",
                            "success",
                          );
                          setTimeout(
                            () => window.location.reload(),
                            1000,
                          );
                        } else {
                          addToast(
                            "Error: " + (data.error || "Unknown error"),
                            "error",
                          );
                        }
                      } catch (err) {
                        addToast(
                          "Failed to delete data: " + err.message,
                          "error",
                        );
                      }
                    }}
                    className="btn btn-danger"
                    style={{ fontSize: "0.85rem" }}
                  >
                    <Icon name="Trash2" size={16} />
                    Delete All Data
                  </button>
                </div>
              </div>

              {/* Student Writing Profiles */}
              <div
                style={{
                  marginTop: "20px",
                  padding: "15px",
                  background: "var(--input-bg)",
                  borderRadius: "10px",
                  border: "1px solid var(--input-border)",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    marginBottom: "12px",
                  }}
                >
                  <div style={{ fontWeight: 600 }}>
                    <Icon
                      name="UserCheck"
                      size={16}
                      style={{
                        marginRight: "8px",
                        verticalAlign: "middle",
                      }}
                    />
                    Student Writing Profiles
                  </div>
                  <button
                    onClick={async () => {
                      setStudentHistoryLoading(true);
                      try {
                        const data = await api.listStudentHistory();
                        setStudentHistoryList(data.students || []);
                      } catch (err) {
                        addToast(
                          "Failed to load history: " + err.message,
                          "error",
                        );
                      }
                      setStudentHistoryLoading(false);
                    }}
                    className="btn btn-secondary"
                    style={{ fontSize: "0.8rem", padding: "4px 10px" }}
                  >
                    {studentHistoryLoading ? "Loading..." : "Refresh"}
                  </button>
                </div>
                <p
                  style={{
                    fontSize: "0.8rem",
                    color: "var(--text-muted)",
                    marginBottom: "12px",
                  }}
                >
                  Writing profiles track vocabulary complexity and style
                  patterns for AI detection. View or delete individual
                  profiles.
                </p>

                {studentHistoryList.length > 0 ? (
                  <>
                    <div
                      style={{
                        maxHeight: "200px",
                        overflowY: "auto",
                        marginBottom: "10px",
                      }}
                    >
                      {studentHistoryList.map((student) => (
                        <div
                          key={student.student_id}
                          style={{
                            display: "flex",
                            justifyContent: "space-between",
                            alignItems: "center",
                            padding: "8px 12px",
                            background: "var(--glass-bg)",
                            borderRadius: "6px",
                            marginBottom: "6px",
                            border: "1px solid var(--glass-border)",
                          }}
                        >
                          <div>
                            <div
                              style={{
                                fontWeight: 500,
                                fontSize: "0.85rem",
                              }}
                            >
                              {student.name || student.student_id}
                            </div>
                            <div
                              style={{
                                fontSize: "0.75rem",
                                color: "var(--text-muted)",
                              }}
                            >
                              {student.submissions_analyzed} submissions
                              • Complexity: {student.avg_complexity}
                            </div>
                          </div>
                          <div style={{ display: "flex", gap: "6px" }}>
                            <button
                              onClick={async () => {
                                try {
                                  const data =
                                    await api.getStudentHistory(
                                      student.student_id,
                                    );
                                  setSelectedStudentHistory(data);
                                } catch (err) {
                                  addToast(
                                    "Failed to load: " + err.message,
                                    "error",
                                  );
                                }
                              }}
                              className="btn btn-secondary"
                              style={{
                                padding: "4px 8px",
                                fontSize: "0.75rem",
                              }}
                            >
                              <Icon name="Eye" size={12} />
                            </button>
                            <button
                              onClick={async () => {
                                if (
                                  !confirm(
                                    `Delete writing profile for ${student.name || student.student_id}?`,
                                  )
                                )
                                  return;
                                try {
                                  await api.deleteStudentHistory(
                                    student.student_id,
                                  );
                                  setStudentHistoryList((prev) =>
                                    prev.filter(
                                      (s) =>
                                        s.student_id !==
                                        student.student_id,
                                    ),
                                  );
                                  addToast("Profile deleted", "success");
                                } catch (err) {
                                  addToast(
                                    "Failed to delete: " + err.message,
                                    "error",
                                  );
                                }
                              }}
                              className="btn btn-secondary"
                              style={{
                                padding: "4px 8px",
                                fontSize: "0.75rem",
                                color: "#ef4444",
                              }}
                            >
                              <Icon name="Trash2" size={12} />
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                    <button
                      onClick={async () => {
                        if (
                          !confirm(
                            "Delete ALL student writing profiles? This resets AI detection baselines.",
                          )
                        )
                          return;
                        try {
                          const result =
                            await api.deleteAllStudentHistory();
                          setStudentHistoryList([]);
                          addToast(
                            `Deleted ${result.deleted} profiles`,
                            "success",
                          );
                        } catch (err) {
                          addToast(
                            "Failed to delete: " + err.message,
                            "error",
                          );
                        }
                      }}
                      className="btn btn-danger"
                      style={{ fontSize: "0.8rem" }}
                    >
                      <Icon name="Trash2" size={14} />
                      Delete All Profiles
                    </button>
                  </>
                ) : (
                  <div
                    style={{
                      padding: "20px",
                      textAlign: "center",
                      color: "var(--text-muted)",
                      fontSize: "0.85rem",
                    }}
                  >
                    {studentHistoryLoading
                      ? "Loading..."
                      : 'Click "Refresh" to load student writing profiles'}
                  </div>
                )}
              </div>

              {/* Trusted Writers */}
              <div
                style={{
                  marginTop: "20px",
                  padding: "15px",
                  background: "rgba(34,197,94,0.1)",
                  borderRadius: "12px",
                  border: "1px solid rgba(34,197,94,0.2)",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    marginBottom: "10px",
                  }}
                >
                  <div
                    style={{
                      fontWeight: 600,
                      display: "flex",
                      alignItems: "center",
                      gap: "8px",
                    }}
                  >
                    <Icon
                      name="ShieldCheck"
                      size={18}
                      style={{
                        color: "#22c55e",
                        verticalAlign: "middle",
                      }}
                    />
                    Trusted Writers
                  </div>
                  {(config.trustedStudents || []).length > 0 && (
                    <button
                      onClick={() => {
                        if (confirm("Remove all trusted writers?")) {
                          setConfig(prev => ({ ...prev, trustedStudents: [] }));
                          addToast("Cleared trusted writers list", "info");
                        }
                      }}
                      className="btn btn-secondary"
                      style={{ padding: "4px 10px", fontSize: "0.75rem" }}
                    >
                      Clear All
                    </button>
                  )}
                </div>
                <p
                  style={{
                    fontSize: "0.85rem",
                    color: "var(--text-muted)",
                    marginBottom: "12px",
                  }}
                >
                  Students marked as trusted writers won't be flagged for AI/copy detection.
                  Use this for students who naturally write well.
                </p>

                {(config.trustedStudents || []).length > 0 ? (
                  <div
                    style={{
                      display: "flex",
                      flexWrap: "wrap",
                      gap: "8px",
                    }}
                  >
                    {config.trustedStudents.map((studentId) => {
                      const matchedResult = (status.results || []).find(r => (r.student_id || r.student) === studentId);
                      let displayName = matchedResult ? matchedResult.student_name : null;
                      if (!displayName) {
                        for (const p of periods) {
                          const s = (p.students || []).find(st => st.id === studentId || st.student_id === studentId);
                          if (s) { displayName = s.full || s.name || ((s.first || "") + " " + (s.last || "")).trim(); break; }
                        }
                      }
                      if (!displayName) displayName = studentId;
                      return (
                      <div
                        key={studentId}
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: "6px",
                          padding: "6px 10px",
                          background: "rgba(34,197,94,0.15)",
                          borderRadius: "6px",
                          fontSize: "0.85rem",
                        }}
                      >
                        <Icon name="User" size={14} style={{ color: "#22c55e" }} />
                        <span>{displayName}</span>
                        <button
                          onClick={() => {
                            setConfig(prev => ({
                              ...prev,
                              trustedStudents: prev.trustedStudents.filter(id => id !== studentId)
                            }));
                            addToast(`Removed ${displayName} from trusted list`, "info");
                          }}
                          style={{
                            background: "none",
                            border: "none",
                            cursor: "pointer",
                            padding: "2px",
                            color: "var(--text-muted)",
                          }}
                        >
                          <Icon name="X" size={12} />
                        </button>
                      </div>
                      );
                    })}
                  </div>
                ) : (
                  <div
                    style={{
                      padding: "15px",
                      textAlign: "center",
                      color: "var(--text-muted)",
                      fontSize: "0.85rem",
                      background: "rgba(0,0,0,0.1)",
                      borderRadius: "8px",
                    }}
                  >
                    No trusted writers yet. Mark students as trusted from the Results tab
                    when they're flagged for AI/copy detection.
                  </div>
                )}
              </div>

              {/* Student History Detail Modal */}
              {selectedStudentHistory && (
                <div
                  style={{
                    position: "fixed",
                    top: 0,
                    left: 0,
                    right: 0,
                    bottom: 0,
                    background: "rgba(0,0,0,0.7)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    zIndex: 1000,
                  }}
                  onClick={() => setSelectedStudentHistory(null)}
                >
                  <div
                    style={{
                      background: "var(--card-bg)",
                      borderRadius: "12px",
                      padding: "25px",
                      maxWidth: "600px",
                      maxHeight: "80vh",
                      overflow: "auto",
                      width: "90%",
                    }}
                    onClick={(e) => e.stopPropagation()}
                  >
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        marginBottom: "20px",
                      }}
                    >
                      <h3 style={{ margin: 0 }}>
                        <Icon
                          name="User"
                          size={20}
                          style={{ marginRight: "10px" }}
                        />
                        {selectedStudentHistory.name ||
                          selectedStudentHistory.student_id ||
                          "Student Profile"}
                      </h3>
                      <button
                        onClick={() => setSelectedStudentHistory(null)}
                        className="btn btn-secondary"
                        style={{ padding: "4px 8px" }}
                      >
                        <Icon name="X" size={16} />
                      </button>
                    </div>

                    <div
                      style={{
                        background: "var(--input-bg)",
                        borderRadius: "8px",
                        padding: "15px",
                        fontSize: "0.85rem",
                      }}
                    >
                      <pre
                        style={{
                          margin: 0,
                          whiteSpace: "pre-wrap",
                          wordBreak: "break-word",
                          fontFamily: "monospace",
                          fontSize: "0.8rem",
                        }}
                      >
                        {JSON.stringify(
                          selectedStudentHistory,
                          null,
                          2,
                        )}
                      </pre>
                    </div>
                  </div>
                </div>
              )}
            </div>
              </div>
  );
}
