import React from "react";
import Icon from "../Icon";

export default function TrustedWritersSection(props) {
  const { addToast, config, periods, setConfig } = props;
  return (
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
  );
}
