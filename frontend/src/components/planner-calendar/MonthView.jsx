import React from "react";
import Icon from "../Icon";

// Month grid view. Originally `{calendarView === 'month' && (() => {...})()}`
// in PlannerCalendar — the IIFE body is relocated verbatim; the conditional
// render became the early-return guard below. Drag/drop + click handlers are
// wired to cell coordinates and stay paired with the cell markup.
export default function MonthView(props) {
  const {
    calendarView, calendarMonth, calendarData, calendarDragId, setCalendarDragId,
    getCalendarDays, isHoliday, getLessonsForDate, isSchoolDay,
    scheduleLesson, unscheduleLesson, removeHoliday,
    setQuickAddForm, setSelectedCalendarDate, setEditingEvent,
  } = props;
  if (!(calendarView === 'month')) return null;
  const days = getCalendarDays(calendarMonth)
  const today = new Date()
  const todayStr = today.getFullYear() + '-' + String(today.getMonth() + 1).padStart(2, '0') + '-' + String(today.getDate()).padStart(2, '0')
  return (
                          <div style={{ display: "grid", gridTemplateColumns: "repeat(7, minmax(0, 1fr))", gap: "2px" }}>
                            {/* Day headers */}
                            {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map(d => (
                              <div key={d} style={{ textAlign: "center", fontSize: "0.75rem", fontWeight: 600, color: "var(--text-secondary)", padding: "6px" }}>
                                {d}
                              </div>
                            ))}
                            {/* Day cells */}
                              {days.map((cell, idx) => {
                                if (!cell) return <div key={'blank-' + idx} style={{ minHeight: "100px" }} />
                                const holiday = isHoliday(cell.date)
                                const lessons = getLessonsForDate(cell.date)
                                const school = isSchoolDay(cell.dow)
                                const isToday = cell.date === todayStr
                                return (
                                  <div
                                    key={cell.date}
                                    onDragOver={e => e.preventDefault()}
                                    onDrop={e => {
                                      e.preventDefault()
                                      if (calendarDragId) {
                                        const entry = (calendarData.scheduled_lessons || []).find(s => s.id === calendarDragId)
                                        if (entry) scheduleLesson({ ...entry, date: cell.date })
                                        setCalendarDragId(null)
                                      }
                                    }}
                                    onClick={() => {
                                      if (!holiday && school) {
                                        setQuickAddForm({ title: '', unit: '', color: '#6366f1' })
                                        setSelectedCalendarDate(cell.date)
                                      }
                                    }}
                                    style={{
                                      minHeight: "100px",
                                      background: holiday ? "rgba(239, 68, 68, 0.08)" : !school ? "rgba(100,100,100,0.05)" : isToday ? "rgba(99, 102, 241, 0.08)" : "var(--glass-bg)",
                                      border: isToday ? "2px solid var(--accent-primary)" : "1px solid var(--glass-border)",
                                      borderRadius: "8px",
                                      padding: "6px",
                                      cursor: !holiday && school ? "pointer" : "default",
                                      opacity: !school ? 0.5 : 1,
                                      transition: "all 0.15s",
                                    }}
                                  >
                                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px" }}>
                                      <span style={{ fontSize: "0.8rem", fontWeight: isToday ? 700 : 500, color: isToday ? "var(--accent-primary)" : "var(--text-primary)" }}>
                                        {cell.day}
                                      </span>
                                    </div>
                                    {holiday && (
                                      <div style={{
                                        fontSize: "0.7rem", padding: "2px 6px", borderRadius: "6px",
                                        background: "rgba(239, 68, 68, 0.2)", color: "#ef4444", fontWeight: 600,
                                        display: "flex", alignItems: "center", gap: "3px", marginBottom: "3px", justifyContent: "space-between",
                                      }}>
                                        <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{holiday.name}</span>
                                        <button
                                          onClick={e => { e.stopPropagation(); removeHoliday(holiday.date) }}
                                          style={{ background: "none", border: "none", color: "#ef4444", cursor: "pointer", padding: 0, lineHeight: 1, flexShrink: 0 }}
                                        >
                                          <Icon name="X" size={10} />
                                        </button>
                                      </div>
                                    )}
                                    {lessons.map(lesson => (
                                      <div
                                        key={lesson.id}
                                        draggable
                                        onDragStart={() => setCalendarDragId(lesson.id)}
                                        onDragEnd={() => setCalendarDragId(null)}
                                        onClick={e => {
                                          e.stopPropagation()
                                          setEditingEvent({ ...lesson })
                                        }}
                                        style={{
                                          fontSize: "0.7rem", padding: "3px 6px", borderRadius: "6px",
                                          background: lesson.color || "#6366f1", color: "#fff", fontWeight: 500,
                                          marginBottom: "2px", cursor: "pointer", display: "flex", alignItems: "center",
                                          justifyContent: "space-between", gap: "2px",
                                        }}
                                      >
                                        <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                                          {lesson.day_number ? 'D' + lesson.day_number + ': ' : ''}{lesson.lesson_title}
                                        </span>
                                        <button
                                          onClick={e => { e.stopPropagation(); unscheduleLesson(lesson.id) }}
                                          style={{ background: "none", border: "none", color: "rgba(255,255,255,0.7)", cursor: "pointer", padding: 0, lineHeight: 1, flexShrink: 0 }}
                                        >
                                          <Icon name="X" size={10} />
                                        </button>
                                      </div>
                                    ))}
                                  </div>
                                )
                              })}
                          </div>
  );
}
