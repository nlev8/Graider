import React from "react";
import Icon from "../Icon";

// Add Event / Schedule Lesson modal. Originally `{selectedCalendarDate && (...)}`
// in PlannerCalendar — relocated verbatim; the conditional render became the
// early-return guard below.
export default function AddEventModal(props) {
  const {
    selectedCalendarDate, setSelectedCalendarDate,
    quickAddForm, setQuickAddForm, scheduleLesson, savedLessons,
  } = props;
  if (!(selectedCalendarDate)) return null;
  return (
                        <div
                          style={{ position: "fixed", top: 0, left: 0, right: 0, bottom: 0, background: "rgba(0,0,0,0.6)", zIndex: 10000, display: "flex", alignItems: "center", justifyContent: "center", padding: "20px" }}
                          onClick={() => setSelectedCalendarDate(null)}
                        >
                          <div
                            className="glass-card"
                            style={{ maxWidth: "500px", width: "100%", padding: "24px", maxHeight: "80vh", overflowY: "auto" }}
                            onClick={e => e.stopPropagation()}
                          >
                            <h3 style={{ fontSize: "1.1rem", fontWeight: 700, marginBottom: "4px", display: "flex", alignItems: "center", gap: "8px" }}>
                              <Icon name="CalendarPlus" size={20} style={{ color: "var(--accent-primary)" }} />
                              Add Event
                            </h3>
                            <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "16px" }}>
                              {new Date(selectedCalendarDate + 'T12:00:00').toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' })}
                            </p>

                            {/* Quick Add Custom Event */}
                            <div style={{ padding: "14px", background: "var(--glass-bg)", border: "1px solid var(--glass-border)", borderRadius: "10px", marginBottom: "16px" }}>
                              <div style={{ fontSize: "0.85rem", fontWeight: 600, marginBottom: "10px", display: "flex", alignItems: "center", gap: "6px", color: "var(--text-primary)" }}>
                                <Icon name="Plus" size={14} />
                                Custom Event
                              </div>
                              <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                                <input
                                  type="text"
                                  value={quickAddForm.title}
                                  onChange={e => setQuickAddForm(prev => ({ ...prev, title: e.target.value }))}
                                  placeholder="Event title (e.g., Unit 5 Test, Lab Day)"
                                  style={{ width: "100%", padding: "8px 12px", background: "var(--input-bg)", border: "1px solid var(--input-border)", borderRadius: "8px", color: "var(--text-primary)", fontSize: "0.9rem" }}
                                  onKeyDown={e => {
                                    if (e.key === 'Enter' && quickAddForm.title.trim()) {
                                      scheduleLesson({ date: selectedCalendarDate, lesson_title: quickAddForm.title.trim(), unit: quickAddForm.unit.trim(), color: quickAddForm.color })
                                      setSelectedCalendarDate(null)
                                    }
                                  }}
                                  autoFocus
                                />
                                <div style={{ display: "flex", gap: "8px" }}>
                                  <input
                                    type="text"
                                    value={quickAddForm.unit}
                                    onChange={e => setQuickAddForm(prev => ({ ...prev, unit: e.target.value }))}
                                    placeholder="Unit (optional)"
                                    style={{ flex: 1, padding: "8px 12px", background: "var(--input-bg)", border: "1px solid var(--input-border)", borderRadius: "8px", color: "var(--text-primary)", fontSize: "0.85rem" }}
                                  />
                                  <div style={{ display: "flex", alignItems: "center", gap: "4px" }}>
                                    {['#6366f1', '#8b5cf6', '#ec4899', '#f59e0b', '#22c55e', '#06b6d4', '#ef4444'].map(c => (
                                      <button
                                        key={c}
                                        onClick={() => setQuickAddForm(prev => ({ ...prev, color: c }))}
                                        style={{
                                          width: 22, height: 22, borderRadius: "6px", background: c, border: quickAddForm.color === c ? "2px solid #fff" : "2px solid transparent",
                                          cursor: "pointer", outline: quickAddForm.color === c ? "2px solid " + c : "none", padding: 0,
                                        }}
                                      />
                                    ))}
                                  </div>
                                </div>
                                <button
                                  onClick={() => {
                                    if (quickAddForm.title.trim()) {
                                      scheduleLesson({ date: selectedCalendarDate, lesson_title: quickAddForm.title.trim(), unit: quickAddForm.unit.trim(), color: quickAddForm.color })
                                      setSelectedCalendarDate(null)
                                    }
                                  }}
                                  className="btn btn-primary"
                                  style={{ width: "100%", padding: "8px" }}
                                  disabled={!quickAddForm.title.trim()}
                                >
                                  Add Event
                                </button>
                              </div>
                            </div>

                            {/* Saved Lessons Section */}
                            {Object.keys(savedLessons.units || {}).length > 0 && (
                              <>
                                <div style={{ fontSize: "0.8rem", fontWeight: 600, color: "var(--text-secondary)", marginBottom: "8px", display: "flex", alignItems: "center", gap: "6px" }}>
                                  <Icon name="BookOpen" size={14} />
                                  Or pick from saved lessons
                                </div>
                                <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                                  {Object.entries(savedLessons.units || {}).map(([unitName, unitLessons]) => (
                                    <div key={unitName}>
                                      <div style={{ fontSize: "0.8rem", fontWeight: 600, color: "var(--text-secondary)", marginBottom: "4px", display: "flex", alignItems: "center", gap: "6px" }}>
                                        <Icon name="FolderOpen" size={14} />
                                        {unitName}
                                      </div>
                                      {unitLessons.map((lesson, li) => {
                                        const unitColors = ['#6366f1', '#8b5cf6', '#ec4899', '#f59e0b', '#22c55e', '#06b6d4', '#ef4444']
                                        const colorIdx = Object.keys(savedLessons.units).indexOf(unitName) % unitColors.length
                                        return (
                                          <button
                                            key={li}
                                            onClick={() => {
                                              scheduleLesson({
                                                date: selectedCalendarDate,
                                                unit: unitName,
                                                lesson_title: lesson.title,
                                                lesson_file: unitName + '/' + lesson.filename + '.json',
                                                color: unitColors[colorIdx],
                                              })
                                              setSelectedCalendarDate(null)
                                            }}
                                            style={{
                                              width: "100%", textAlign: "left", padding: "10px 14px",
                                              background: "var(--glass-bg)", border: "1px solid var(--glass-border)",
                                              borderRadius: "8px", cursor: "pointer", color: "var(--text-primary)",
                                              fontSize: "0.85rem", marginBottom: "4px",
                                              display: "flex", alignItems: "center", gap: "8px",
                                              transition: "all 0.15s",
                                            }}
                                            onMouseEnter={e => { e.currentTarget.style.borderColor = "var(--accent-primary)"; e.currentTarget.style.background = "var(--glass-hover)" }}
                                            onMouseLeave={e => { e.currentTarget.style.borderColor = "var(--glass-border)"; e.currentTarget.style.background = "var(--glass-bg)" }}
                                          >
                                            <div style={{ width: 8, height: 8, borderRadius: "50%", background: unitColors[colorIdx], flexShrink: 0 }} />
                                            {lesson.title}
                                          </button>
                                        )
                                      })}
                                    </div>
                                  ))}
                                </div>
                              </>
                            )}
                            <button
                              onClick={() => setSelectedCalendarDate(null)}
                              className="btn btn-secondary"
                              style={{ marginTop: "16px", width: "100%" }}
                            >
                              Cancel
                            </button>
                          </div>
                        </div>
  );
}
