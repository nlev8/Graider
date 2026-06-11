import React from "react";
import Icon from "../Icon";

export default function RawSubmissionView({ r }) {
  return (
                        <div
                          style={{
                            height: "100%",
                            background: "var(--input-bg)",
                            padding: "20px",
                            borderRadius: "10px",
                            overflowY: "auto",
                          }}
                        >
                          {(() => {
                            const imageExts = ['.png', '.jpg', '.jpeg', '.gif', '.webp'];
                            const fname = (r.filename || '').toLowerCase();
                            const isImage = r.is_handwritten || imageExts.some(ext => fname.endsWith(ext)) || r.student_content === '[Image file]';
                            if (isImage) {
                              const imagePath = r.filepath || r.original_image_path;
                              return (
                                <div style={{ textAlign: "center" }}>
                                  <div
                                    style={{
                                      display: "flex",
                                      alignItems: "center",
                                      justifyContent: "center",
                                      gap: "8px",
                                      marginBottom: "15px",
                                      color: "#10b981",
                                      fontWeight: 500,
                                    }}
                                  >
                                    <Icon name={r.is_handwritten ? "PenTool" : "Image"} size={18} />
                                    {r.is_handwritten ? "Handwritten Assignment" : "Image Submission"}
                                  </div>
                                  {imagePath ? (
                                    <img
                                      src={"/api/serve-file?path=" + encodeURIComponent(imagePath)}
                                      alt={r.filename || "Student submission"}
                                      style={{
                                        maxWidth: "100%",
                                        borderRadius: "10px",
                                        boxShadow: "0 2px 10px rgba(0,0,0,0.15)",
                                      }}
                                    />
                                  ) : (
                                    <p
                                      style={{
                                        fontSize: "0.85rem",
                                        color: "var(--text-muted)",
                                      }}
                                    >
                                      {r.is_handwritten
                                        ? "Handwritten responses were extracted by AI vision. Check the \"Responses\" tab to see extracted answers."
                                        : "[No image path available - click Open Original to view]"}
                                    </p>
                                  )}
                                </div>
                              );
                            }
                            return (
                              <div
                                style={{
                                  whiteSpace: "pre-wrap",
                                  fontSize: "22px",
                                  lineHeight: 1.7,
                                  color: "var(--text-secondary)",
                                  fontFamily: "monospace",
                                }}
                              >
                                {r.full_content ||
                                  r.student_content ||
                                  "[No content - click Open Original to view]"}
                              </div>
                            );
                          })()}
                        </div>
  );
}
