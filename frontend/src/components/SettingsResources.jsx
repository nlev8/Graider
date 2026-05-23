import React from "react";
import Icon from "./Icon";
import * as api from "../services/api";

export default function SettingsResources({ addToast, newDocDescription, newDocType, setNewDocDescription, setNewDocType, setSupportDocs, setUploadingDoc, supportDocInputRef, supportDocs, uploadingDoc }) {
  return (
              <div data-tutorial="resources-upload">
                <p
                  style={{
                    fontSize: "0.9rem",
                    color: "var(--text-secondary)",
                    marginBottom: "25px",
                  }}
                >
                  Upload curriculum guides, rubrics, standards documents, and
                  other reference materials to enhance AI grading and lesson
                  planning.
                </p>

                {/* Supporting Documents Section */}
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
                      name="FileText"
                      size={20}
                      style={{ color: "#10b981" }}
                    />
                    Supporting Documents
                  </h3>
                  <p
                    style={{
                      fontSize: "0.85rem",
                      color: "var(--text-secondary)",
                      marginBottom: "15px",
                    }}
                  >
                    Upload curriculum guides, rubrics, standards docs, or
                    other reference materials
                  </p>

                  <input
                    ref={supportDocInputRef}
                    type="file"
                    accept=".pdf,.docx,.doc,.txt,.md"
                    style={{ display: "none" }}
                    onChange={async (e) => {
                      const file = e.target.files?.[0];
                      if (!file) return;
                      setUploadingDoc(true);
                      try {
                        const result = await api.uploadSupportDocument(
                          file,
                          newDocType,
                          newDocDescription,
                        );
                        if (result.error) {
                          addToast(result.error, "error");
                        } else {
                          const docsData = await api.listSupportDocuments();
                          setSupportDocs(docsData.documents || []);
                          setNewDocDescription("");
                        }
                      } catch (err) {
                        addToast("Upload failed: " + err.message, "error");
                      }
                      setUploadingDoc(false);
                      e.target.value = "";
                    }}
                  />

                  <div
                    style={{
                      display: "flex",
                      gap: "10px",
                      marginBottom: "15px",
                      flexWrap: "wrap",
                    }}
                  >
                    <select
                      className="input"
                      value={newDocType}
                      onChange={(e) => setNewDocType(e.target.value)}
                      style={{ maxWidth: "180px" }}
                    >
                      <option value="curriculum">Curriculum Guide</option>
                      <option value="rubric">Rubric Template</option>
                      <option value="standards">Standards Document</option>
                      <option value="general">General Reference</option>
                    </select>
                    <input
                      type="text"
                      className="input"
                      placeholder="Description (optional)"
                      value={newDocDescription}
                      onChange={(e) => setNewDocDescription(e.target.value)}
                      style={{ flex: 1, minWidth: "200px" }}
                    />
                    <button
                      onClick={() => supportDocInputRef.current?.click()}
                      className="btn btn-secondary"
                      disabled={uploadingDoc}
                    >
                      <Icon name="Upload" size={18} />
                      {uploadingDoc ? "Uploading..." : "Upload Document"}
                    </button>
                  </div>

                  {supportDocs.length > 0 && (
                    <div
                      style={{
                        display: "flex",
                        flexDirection: "column",
                        gap: "10px",
                      }}
                    >
                      {supportDocs.map((doc) => (
                        <div
                          key={doc.filename}
                          style={{
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "space-between",
                            padding: "12px 15px",
                            background: "var(--input-bg)",
                            borderRadius: "8px",
                            border: "1px solid var(--glass-border)",
                          }}
                        >
                          <div
                            style={{
                              display: "flex",
                              alignItems: "center",
                              gap: "12px",
                            }}
                          >
                            <Icon
                              name={
                                doc.doc_type === "rubric"
                                  ? "ClipboardCheck"
                                  : doc.doc_type === "standards"
                                    ? "BookOpen"
                                    : "FileText"
                              }
                              size={18}
                              style={{ color: "#10b981" }}
                            />
                            <div>
                              <div style={{ fontWeight: 600 }}>
                                {doc.filename}
                              </div>
                              <div
                                style={{
                                  fontSize: "0.8rem",
                                  color: "var(--text-secondary)",
                                }}
                              >
                                {doc.doc_type}{" "}
                                {doc.description && `• ${doc.description}`}
                              </div>
                            </div>
                          </div>
                          <button
                            onClick={async () => {
                              if (confirm("Delete this document?")) {
                                await api.deleteSupportDocument(doc.filename);
                                const data = await api.listSupportDocuments();
                                setSupportDocs(data.documents || []);
                              }
                            }}
                            style={{
                              padding: "6px 10px",
                              background: "rgba(239,68,68,0.2)",
                              border: "none",
                              borderRadius: "6px",
                              color: "#ef4444",
                              cursor: "pointer",
                            }}
                          >
                            <Icon name="Trash2" size={14} />
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
  );
}
