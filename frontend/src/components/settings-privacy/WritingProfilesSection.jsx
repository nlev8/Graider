import React from "react";
import Icon from "../Icon";
import * as api from "../../services/api";

export default function WritingProfilesSection(props) {
  const { addToast, setSelectedStudentHistory, setStudentHistoryList, setStudentHistoryLoading, studentHistoryList, studentHistoryLoading } = props;
  return (
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
  );
}
