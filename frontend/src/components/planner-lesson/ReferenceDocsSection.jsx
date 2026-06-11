import React from "react";
import Icon from "../Icon";

export default function ReferenceDocsSection(props) {
  const { contentOnly, docUploading, handleDocUpload, handleMatchStandards, matchResults, matchingInProgress, removeUploadedDoc, selectedStandards, setContentOnly, setSelectedStandards, uploadedDocs } = props;
  return (
    <>
                          {/* Reference Documents */}
                          <div>
                            <label className="label" style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                              <Icon name="FileUp" size={14} />
                              Reference Documents
                              {uploadedDocs.length > 0 && <span style={{ fontWeight: 400, color: "var(--text-muted)" }}>({uploadedDocs.length})</span>}
                            </label>
                            <input type="file" id="doc-upload-sidebar" multiple accept=".pdf,.doc,.docx,.png,.jpg,.jpeg,.gif,.webp,.txt" style={{ display: "none" }} onChange={handleDocUpload} />
                            <div style={{ display: "flex", gap: "6px", marginBottom: uploadedDocs.length > 0 ? "8px" : "0" }}>
                              <button className="btn btn-secondary" onClick={() => document.getElementById("doc-upload-sidebar").click()} disabled={docUploading} style={{ padding: "5px 12px", fontSize: "0.8rem", display: "flex", alignItems: "center", gap: "5px", flex: 1 }}>
                                <Icon name="Upload" size={13} />
                                {docUploading ? "Uploading..." : "Upload"}
                              </button>
                              {uploadedDocs.length > 0 && (
                                <button className="btn btn-primary" onClick={handleMatchStandards} disabled={matchingInProgress} style={{ padding: "5px 12px", fontSize: "0.8rem", display: "flex", alignItems: "center", gap: "5px", flex: 1 }}>
                                  <Icon name="Target" size={13} />
                                  {matchingInProgress ? "Matching..." : "Match Standards"}
                                </button>
                              )}
                            </div>
                            {uploadedDocs.length > 0 && (
                              <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                                {uploadedDocs.map((doc, idx) => (
                                  <div key={idx} style={{ display: "flex", alignItems: "center", gap: "6px", background: "rgba(139, 92, 246, 0.1)", border: "1px solid rgba(139, 92, 246, 0.3)", borderRadius: "6px", padding: "4px 8px", fontSize: "0.8rem" }}>
                                    <Icon name={["png","jpg","jpeg","gif","webp"].includes((doc.filename || "").split(".").pop().toLowerCase()) ? "Image" : "FileText"} size={12} />
                                    <span style={{ fontWeight: 600, flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{doc.filename}</span>
                                    <span style={{ color: "var(--text-muted)", fontSize: "0.7rem", flexShrink: 0 }}>{doc.size < 1024 ? doc.size + "B" : Math.round(doc.size / 1024) + "KB"}</span>
                                    <button onClick={() => removeUploadedDoc(idx)} style={{ background: "none", border: "none", color: "var(--text-muted)", cursor: "pointer", padding: "0 2px", fontSize: "0.9rem", lineHeight: 1, flexShrink: 0 }}>×</button>
                                  </div>
                                ))}
                              </div>
                            )}
                            {matchResults && matchResults.matched_standards && matchResults.matched_standards.length > 0 && (
                              <div style={{ background: "var(--glass-bg)", borderRadius: "8px", padding: "8px", border: "1px solid var(--glass-border)", marginTop: "8px" }}>
                                <div style={{ fontSize: "0.75rem", fontWeight: 600, marginBottom: "6px" }}>
                                  {matchResults.matched_standards.filter((a) => a.confidence >= 0.4).length} matching standards — click to select
                                </div>
                                {matchResults.matched_standards.filter((a) => a.confidence >= 0.2).slice(0, 8).map((a, idx) => {
                                  const isSelected = selectedStandards.includes(a.code);
                                  const color = a.confidence >= 0.7 ? "#22c55e" : a.confidence >= 0.4 ? "#f59e0b" : "#ef4444";
                                  return (
                                    <div key={idx} onClick={() => {
                                      if (isSelected) {
                                        setSelectedStandards(prev => prev.filter(c => c !== a.code));
                                      } else {
                                        setSelectedStandards(prev => [...prev, a.code]);
                                      }
                                    }} style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "4px", padding: "4px 6px", borderRadius: "6px", cursor: "pointer", background: isSelected ? "rgba(99, 102, 241, 0.15)" : "transparent", border: isSelected ? "1px solid rgba(99, 102, 241, 0.4)" : "1px solid transparent", transition: "all 0.15s ease" }}>
                                      <Icon name={isSelected ? "CheckCircle" : "Circle"} size={12} style={{ color: isSelected ? "#6366f1" : "var(--text-muted)", flexShrink: 0 }} />
                                      <span style={{ fontWeight: 600, fontSize: "0.7rem", minWidth: "70px", flexShrink: 0 }}>{a.code}</span>
                                      <div style={{ flex: 1, height: "4px", background: "var(--glass-border)", borderRadius: "2px", overflow: "hidden" }}>
                                        <div style={{ width: Math.round(a.confidence * 100) + "%", height: "100%", borderRadius: "2px", background: color }} />
                                      </div>
                                      <span style={{ fontSize: "0.7rem", fontWeight: 600, color: color, flexShrink: 0 }}>{Math.round(a.confidence * 100)}%</span>
                                    </div>
                                  );
                                })}
                              </div>
                            )}
                          </div>

                          {uploadedDocs.length > 0 && (
                          <div style={{ display: "flex", alignItems: "center", gap: "8px", padding: "8px 0" }}>
                            <input
                              type="checkbox"
                              id="content-only-toggle"
                              checked={contentOnly}
                              onChange={function(e) { setContentOnly(e.target.checked); }}
                              style={{ width: "16px", height: "16px", cursor: "pointer" }}
                            />
                            <label htmlFor="content-only-toggle" style={{ fontSize: "0.82rem", cursor: "pointer", color: "var(--text-secondary)" }}>
                              Only create questions from uploaded content
                            </label>
                          </div>
                          )}
    </>
  );
}
