import React from "react";
import Icon from "../Icon";

export default function StudentHistoryModal(props) {
  const { selectedStudentHistory, setSelectedStudentHistory } = props;
  if (!selectedStudentHistory) return null;
  return (
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
  );
}
