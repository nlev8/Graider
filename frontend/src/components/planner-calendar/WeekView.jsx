import React from "react";
import Icon from "../Icon";

// Week view. Originally `{calendarView === 'week' && (() => {...})()}` in
// PlannerCalendar — the IIFE body is relocated verbatim; the conditional
// render became the early-return guard below. Drag/drop + click handlers are
// wired to day cells and stay paired with the cell markup.
export default function WeekView(props) {
  const {
    calendarView, calendarMonth, calendarData, calendarDragId, setCalendarDragId,
    getStartOfWeek, getWeekDays, isHoliday, getLessonsForDate, isSchoolDay,
    scheduleLesson, unscheduleLesson,
    setQuickAddForm, setSelectedCalendarDate, setEditingEvent,
  } = props;
  if (!(calendarView === 'week')) return null;
  const weekStart = getStartOfWeek(calendarMonth)
  const days = getWeekDays(weekStart)
  const today = new Date()
  const todayStr = today.getFullYear() + '-' + String(today.getMonth() + 1).padStart(2, '0') + '-' + String(today.getDate()).padStart(2, '0')
  return (
                          <div style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", gap: "8px" }}>
                            {days.map(cell => {
                              const holiday = isHoliday(cell.date)
                              const lessons = getLessonsForDate(cell.date)
                              const school = isSchoolDay(cell.dow)
                              const isToday = cell.date === todayStr
                              const dayLabel = cell.fullDate.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })
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
                                  className="glass-card"
                                  style={{
                                    minHeight: "280px", padding: "12px",
                                    opacity: !school ? 0.4 : 1,
                                    border: isToday ? "2px solid var(--accent-primary)" : undefined,
                                    background: holiday ? "rgba(239, 68, 68, 0.08)" : undefined,
                                    cursor: !holiday && school ? "pointer" : "default",
                                  }}
                                >
                                  <div style={{ fontSize: "0.85rem", fontWeight: 600, marginBottom: "10px", color: isToday ? "var(--accent-primary)" : "var(--text-primary)" }}>
                                    {dayLabel}
                                  </div>
                                  {holiday && (
                                    <div style={{
                                      fontSize: "0.8rem", padding: "6px 10px", borderRadius: "8px",
                                      background: "rgba(239, 68, 68, 0.15)", color: "#ef4444", fontWeight: 600,
                                      marginBottom: "8px", display: "flex", alignItems: "center", gap: "6px",
                                    }}>
                                      <Icon name="CalendarOff" size={14} />
                                      {holiday.name}
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
                                        padding: "8px 10px", borderRadius: "8px",
                                        background: lesson.color || "#6366f1", color: "#fff",
                                        marginBottom: "6px", cursor: "pointer",
                                      }}
                                    >
                                      <div style={{ fontSize: "0.8rem", fontWeight: 600, marginBottom: "2px" }}>
                                        {lesson.day_number ? 'Day ' + lesson.day_number + ': ' : ''}{lesson.lesson_title}
                                      </div>
                                      {lesson.unit && <div style={{ fontSize: "0.7rem", opacity: 0.8 }}>{lesson.unit}</div>}
                                      <div style={{ display: "flex", gap: "6px", marginTop: "4px" }}>
                                        <button
                                          onClick={e => { e.stopPropagation(); setEditingEvent({ ...lesson }) }}
                                          style={{ background: "rgba(255,255,255,0.2)", border: "none", color: "#fff", cursor: "pointer", padding: "2px 6px", borderRadius: "4px", fontSize: "0.7rem" }}
                                        >
                                          Edit
                                        </button>
                                        <button
                                          onClick={e => { e.stopPropagation(); unscheduleLesson(lesson.id) }}
                                          style={{ background: "rgba(255,255,255,0.2)", border: "none", color: "#fff", cursor: "pointer", padding: "2px 6px", borderRadius: "4px", fontSize: "0.7rem" }}
                                        >
                                          Remove
                                        </button>
                                      </div>
                                    </div>
                                  ))}
                                  {!holiday && school && lessons.length === 0 && (
                                    <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", fontStyle: "italic", textAlign: "center", marginTop: "40px" }}>
                                      Click to add event
                                    </div>
                                  )}
                                </div>
                              )
                            })}
                          </div>
  );
}
