import React from "react";
import Icon from "../Icon";

// Edit Event modal. Originally `{editingEvent && (...)}` in PlannerCalendar —
// relocated verbatim; the conditional render became the early-return guard below.
export default function EditEventModal(props) {
  const { editingEvent, setEditingEvent, scheduleLesson, unscheduleLesson } = props;
  if (!(editingEvent)) return null;
  return (
                        <div
                          style={{ position: "fixed", top: 0, left: 0, right: 0, bottom: 0, background: "rgba(0,0,0,0.6)", zIndex: 10000, display: "flex", alignItems: "center", justifyContent: "center", padding: "20px" }}
                          onClick={() => setEditingEvent(null)}
                        >
                          <div
                            className="glass-card"
                            style={{ maxWidth: "460px", width: "100%", padding: "24px" }}
                            onClick={e => e.stopPropagation()}
                          >
                            <h3 style={{ fontSize: "1.1rem", fontWeight: 700, marginBottom: "16px", display: "flex", alignItems: "center", gap: "8px" }}>
                              <Icon name="Pencil" size={20} style={{ color: "var(--accent-primary)" }} />
                              Edit Event
                            </h3>
                            <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                              <div>
                                <label style={{ fontSize: "0.8rem", fontWeight: 600, color: "var(--text-secondary)", display: "block", marginBottom: "4px" }}>Title</label>
                                <input
                                  type="text"
                                  value={editingEvent.lesson_title || ''}
                                  onChange={e => setEditingEvent(prev => ({ ...prev, lesson_title: e.target.value }))}
                                  style={{ width: "100%", padding: "8px 12px", background: "var(--input-bg)", border: "1px solid var(--input-border)", borderRadius: "8px", color: "var(--text-primary)", fontSize: "0.9rem" }}
                                  autoFocus
                                />
                              </div>
                              <div>
                                <label style={{ fontSize: "0.8rem", fontWeight: 600, color: "var(--text-secondary)", display: "block", marginBottom: "4px" }}>Date</label>
                                <input
                                  type="date"
                                  value={editingEvent.date || ''}
                                  onChange={e => setEditingEvent(prev => ({ ...prev, date: e.target.value }))}
                                  style={{ width: "100%", padding: "8px 12px", background: "var(--input-bg)", border: "1px solid var(--input-border)", borderRadius: "8px", color: "var(--text-primary)", fontSize: "0.9rem" }}
                                />
                              </div>
                              <div>
                                <label style={{ fontSize: "0.8rem", fontWeight: 600, color: "var(--text-secondary)", display: "block", marginBottom: "4px" }}>Unit</label>
                                <input
                                  type="text"
                                  value={editingEvent.unit || ''}
                                  onChange={e => setEditingEvent(prev => ({ ...prev, unit: e.target.value }))}
                                  placeholder="Unit name (optional)"
                                  style={{ width: "100%", padding: "8px 12px", background: "var(--input-bg)", border: "1px solid var(--input-border)", borderRadius: "8px", color: "var(--text-primary)", fontSize: "0.9rem" }}
                                />
                              </div>
                              <div>
                                <label style={{ fontSize: "0.8rem", fontWeight: 600, color: "var(--text-secondary)", display: "block", marginBottom: "6px" }}>Color</label>
                                <div style={{ display: "flex", gap: "6px" }}>
                                  {['#6366f1', '#8b5cf6', '#ec4899', '#f59e0b', '#22c55e', '#06b6d4', '#ef4444'].map(c => (
                                    <button
                                      key={c}
                                      onClick={() => setEditingEvent(prev => ({ ...prev, color: c }))}
                                      style={{
                                        width: 28, height: 28, borderRadius: "8px", background: c, border: (editingEvent.color || '#6366f1') === c ? "2px solid #fff" : "2px solid transparent",
                                        cursor: "pointer", outline: (editingEvent.color || '#6366f1') === c ? "2px solid " + c : "none", padding: 0,
                                      }}
                                    />
                                  ))}
                                </div>
                              </div>
                              <div style={{ display: "flex", gap: "8px", marginTop: "8px" }}>
                                <button
                                  onClick={() => {
                                    if (editingEvent.lesson_title && editingEvent.date) {
                                      scheduleLesson(editingEvent)
                                      setEditingEvent(null)
                                    }
                                  }}
                                  className="btn btn-primary"
                                  style={{ flex: 1 }}
                                  disabled={!editingEvent.lesson_title || !editingEvent.date}
                                >
                                  Save Changes
                                </button>
                                <button
                                  onClick={() => {
                                    unscheduleLesson(editingEvent.id)
                                    setEditingEvent(null)
                                  }}
                                  className="btn btn-secondary"
                                  style={{ color: "#ef4444" }}
                                >
                                  <Icon name="Trash2" size={14} />
                                  Delete
                                </button>
                                <button
                                  onClick={() => setEditingEvent(null)}
                                  className="btn btn-secondary"
                                >
                                  Cancel
                                </button>
                              </div>
                            </div>
                          </div>
                        </div>
  );
}
