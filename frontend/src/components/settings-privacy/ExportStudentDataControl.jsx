import React from "react";
import Icon from "../Icon";
import * as api from "../../services/api";
import { getAuthHeaders } from "../../services/api";

export default function ExportStudentDataControl(props) {
  const { addToast, exportStudentSearch, periods, setExportStudentSearch } = props;
  return (
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
  );
}
