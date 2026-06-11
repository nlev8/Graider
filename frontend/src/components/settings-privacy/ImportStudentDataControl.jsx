import React from "react";
import Icon from "../Icon";
import { getAuthHeaders } from "../../services/api";

export default function ImportStudentDataControl(props) {
  const { addToast, importFileRef, importStudentData, periods, setImportStudentData } = props;
  return (
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
  );
}
