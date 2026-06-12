import React from "react";
import Icon from "../Icon";

// CQ wave-7 split: extracted verbatim from PlannerDashboard.jsx ("Teacher's
// Classes" card). Stateless — all data/handlers come from the orchestrator.
export default function TeacherClassesCard({ fetchTeacherClasses, teacherClasses }) {
  return (
                      <div className="glass-card" style={{ padding: "20px", marginBottom: "20px" }}>
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "15px" }}>
                              <h3 style={{ fontSize: "1.1rem", fontWeight: 700, display: "flex", alignItems: "center", gap: "10px" }}>
                                  <Icon name="School" size={20} />
                                  Your Classes
                              </h3>
                              <button onClick={fetchTeacherClasses} className="btn btn-secondary" style={{ padding: "8px 12px", fontSize: "0.85rem" }}>
                                  <Icon name="RefreshCw" size={16} /> Refresh
                              </button>
                          </div>
                          {teacherClasses.length === 0 ? (
                              <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>
                                  No classes yet. Classes are created automatically when you sync your roster via Clever, ClassLink, or CSV import.
                              </p>
                          ) : (
                              <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                                  {teacherClasses.map(function(cls) {
                                      return (
                                          <div key={cls.id} style={{
                                              padding: "12px 15px",
                                              background: "rgba(255,255,255,0.03)",
                                              borderRadius: "10px",
                                              border: "1px solid rgba(255,255,255,0.1)",
                                              display: "flex",
                                              justifyContent: "space-between",
                                              alignItems: "center",
                                          }}>
                                              <div>
                                                  <div style={{ fontWeight: 600 }}>{cls.name}</div>
                                                  <div style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
                                                      {"Code: " + cls.join_code + " | " + (cls.subject || "No subject") + " | " + ((cls.class_students || [{}])[0]?.count || 0) + " students"}
                                                  </div>
                                              </div>
                                          </div>
                                      );
                                  })}
                              </div>
                          )}
                      </div>
  );
}
