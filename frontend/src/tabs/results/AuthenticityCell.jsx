import React from "react";
import Icon from "../../components/Icon";
import {
  getAuthenticityStatus,
  getAIFlagColor,
  getPlagFlagColor,
} from "../../utils/authenticity";

export default function AuthenticityCell({ r, config, setConfig, addToast }) {
  return (
                                    <td style={{ textAlign: "center" }}>
                                      {(() => {
                                        const auth = getAuthenticityStatus(r);
                                        const aiColor = getAIFlagColor(
                                          auth.ai.flag,
                                        );
                                        const plagColor = getPlagFlagColor(
                                          auth.plag.flag,
                                        );
                                        const studentId = r.student_id || r.student;
                                        const isTrusted = (config.trustedStudents || []).includes(studentId);
                                        const isFlagged = auth.ai.flag !== "none" || auth.plag.flag !== "none";

                                        // If student is trusted, show trusted badge instead
                                        if (isTrusted) {
                                          return (
                                            <div style={{ display: "flex", flexDirection: "column", gap: "4px", alignItems: "flex-start" }}>
                                              <span
                                                title="This student is marked as trusted - detection flags are overridden"
                                                style={{
                                                  display: "inline-flex",
                                                  alignItems: "center",
                                                  gap: "4px",
                                                  padding: "3px 8px",
                                                  borderRadius: "12px",
                                                  fontWeight: 500,
                                                  background: "rgba(34,197,94,0.2)",
                                                  color: "#22c55e",
                                                  fontSize: "0.75rem",
                                                }}
                                              >
                                                <Icon name="ShieldCheck" size={12} />
                                                Trusted Writer
                                              </span>
                                              <button
                                                onClick={() => {
                                                  setConfig(prev => ({
                                                    ...prev,
                                                    trustedStudents: prev.trustedStudents.filter(id => id !== studentId)
                                                  }));
                                                  addToast(`Removed ${r.student} from trusted list`, "info");
                                                }}
                                                style={{
                                                  background: "none",
                                                  border: "none",
                                                  color: "var(--text-muted)",
                                                  fontSize: "0.7rem",
                                                  cursor: "pointer",
                                                  padding: "2px 4px",
                                                }}
                                              >
                                                Remove trust
                                              </button>
                                            </div>
                                          );
                                        }

                                        return (
                                          <div
                                            style={{
                                              display: "flex",
                                              flexDirection: "column",
                                              gap: "4px",
                                            }}
                                          >
                                            {/* AI Detection */}
                                            <span
                                              title={
                                                auth.ai.reason ||
                                                `AI: ${auth.ai.flag}${auth.ai.confidence ? ` (${auth.ai.confidence}%)` : ""}`
                                              }
                                              style={{
                                                display: "inline-flex",
                                                alignItems: "center",
                                                gap: "4px",
                                                padding: "3px 8px",
                                                borderRadius: "12px",
                                                fontWeight: 500,
                                                background: aiColor.bg,
                                                color: aiColor.text,
                                                fontSize: "0.75rem",
                                                cursor: auth.ai.reason
                                                  ? "help"
                                                  : "default",
                                              }}
                                            >
                                              <Icon
                                                name={
                                                  auth.ai.flag === "likely"
                                                    ? "Bot"
                                                    : auth.ai.flag ===
                                                        "possible"
                                                      ? "Bot"
                                                      : "CheckCircle"
                                                }
                                                size={12}
                                              />
                                              AI:{" "}
                                              {auth.ai.flag === "none"
                                                ? "Clear"
                                                : auth.ai.flag}
                                              {auth.ai.confidence > 0 &&
                                                ` ${auth.ai.confidence}%`}
                                            </span>
                                            {/* Plagiarism Detection */}
                                            <span
                                              title={
                                                auth.plag.reason ||
                                                `Plagiarism: ${auth.plag.flag}`
                                              }
                                              style={{
                                                display: "inline-flex",
                                                alignItems: "center",
                                                gap: "4px",
                                                padding: "3px 8px",
                                                borderRadius: "12px",
                                                fontWeight: 500,
                                                background: plagColor.bg,
                                                color: plagColor.text,
                                                fontSize: "0.75rem",
                                                cursor: auth.plag.reason
                                                  ? "help"
                                                  : "default",
                                              }}
                                            >
                                              <Icon
                                                name={
                                                  auth.plag.flag === "likely"
                                                    ? "Copy"
                                                    : auth.plag.flag ===
                                                        "possible"
                                                      ? "Copy"
                                                      : "CheckCircle"
                                                }
                                                size={12}
                                              />
                                              Copy:{" "}
                                              {auth.plag.flag === "none"
                                                ? "Clear"
                                                : auth.plag.flag}
                                            </span>
                                            {/* Trust button for flagged students -- adds to trusted list AND regrades */}
                                            {isFlagged && (
                                              <button
                                                onClick={() => addToast("Regrading is not available in portal mode. Students can resubmit via the portal.", "info")}
                                                title="Mark as trusted writer - this student writes well naturally"
                                                style={{
                                                  background: "rgba(34,197,94,0.1)",
                                                  border: "1px solid rgba(34,197,94,0.3)",
                                                  color: "#22c55e",
                                                  fontSize: "0.7rem",
                                                  cursor: "pointer",
                                                  padding: "2px 6px",
                                                  borderRadius: "4px",
                                                  display: "inline-flex",
                                                  alignItems: "center",
                                                  gap: "3px",
                                                }}
                                              >
                                                <Icon name="ShieldCheck" size={10} />
                                                Trust
                                              </button>
                                            )}
                                          </div>
                                        );
                                      })()}
                                    </td>
  );
}
