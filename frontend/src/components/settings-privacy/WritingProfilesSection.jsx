import React from "react";
import Icon from "../Icon";
import * as api from "../../services/api";
import WritingProfilesList from "./WritingProfilesList";

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

                <WritingProfilesList
                  addToast={addToast}
                  setSelectedStudentHistory={setSelectedStudentHistory}
                  setStudentHistoryList={setStudentHistoryList}
                  studentHistoryList={studentHistoryList}
                  studentHistoryLoading={studentHistoryLoading}
                />
              </div>
  );
}
