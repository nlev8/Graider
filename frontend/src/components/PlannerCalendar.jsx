import React, { useState, useEffect } from "react";
import Icon from "./Icon";
import HolidayModal from "./HolidayModal";
import ImportEventsModal from "./ImportEventsModal";
import * as api from "../services/api";

// supportDocs/setSupportDocs are App-level shared state (App.jsx:1481) used by both
// PlannerTab and the Settings/Tools tab. The calendar import flow reads the doc list
// and lazy-loads it via setSupportDocs; both must stay wired to the shared state, so
// they are passed through as props (not component-local) to preserve behavior exactly.
export default function PlannerCalendar({ active, addToast, savedLessons, supportDocs, setSupportDocs }) {
  const [calendarData, setCalendarData] = useState({ scheduled_lessons: [], holidays: [], school_days: {} });
  const [calendarMonth, setCalendarMonth] = useState(new Date());
  const [calendarView, setCalendarView] = useState("month");
  const [selectedCalendarDate, setSelectedCalendarDate] = useState(null);
  const [showHolidayModal, setShowHolidayModal] = useState(false);
  const [holidayForm, setHolidayForm] = useState({ date: "", name: "", end_date: "" });
  const [calendarDragId, setCalendarDragId] = useState(null);
  const [showImportModal, setShowImportModal] = useState(false);
  const [importParsing, setImportParsing] = useState(false);
  const [importEvents, setImportEvents] = useState([]);
  const [importChecked, setImportChecked] = useState({});
  const [importSelectedDoc, setImportSelectedDoc] = useState("");
  const [importImporting, setImportImporting] = useState(false);
  const [editingEvent, setEditingEvent] = useState(null);
  const [quickAddForm, setQuickAddForm] = useState({ title: "", unit: "", color: "#6366f1" });

  // Calendar fetch — fires when this mode becomes active (originally guarded by
  // activeTab === "planner" && plannerMode === "calendar"; the parent's conditional
  // render now handles the plannerMode half, the `active` prop handles the rest).
  useEffect(() => {
    if (active) loadCalendar();
  }, [active]);

  function loadCalendar() {
    fetch("/api/calendar").then(r => r.json()).then(setCalendarData).catch(() => {});
  }

  async function scheduleLesson(entry) {
    try {
      const resp = await fetch("/api/calendar/schedule", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(entry),
      });
      const data = await resp.json();
      if (data.status === "scheduled") loadCalendar();
    } catch (e) {
      if (addToast) addToast("Failed to schedule lesson", "error");
    }
  }

  async function unscheduleLesson(entryId) {
    try {
      await fetch("/api/calendar/schedule/" + entryId, { method: "DELETE" });
      loadCalendar();
    } catch (e) {
      if (addToast) addToast("Failed to remove lesson", "error");
    }
  }

  async function addHoliday(holiday) {
    try {
      const resp = await fetch("/api/calendar/holiday", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(holiday),
      });
      const data = await resp.json();
      if (data.status === "added") loadCalendar();
    } catch (e) {
      if (addToast) addToast("Failed to add holiday", "error");
    }
  }

  async function removeHoliday(date) {
    try {
      await fetch("/api/calendar/holiday?date=" + date, { method: "DELETE" });
      loadCalendar();
    } catch (e) {
      if (addToast) addToast("Failed to remove holiday", "error");
    }
  }

  function getCalendarDays(month) {
    const year = month.getFullYear();
    const m = month.getMonth();
    const firstDay = new Date(year, m, 1);
    const lastDay = new Date(year, m + 1, 0);
    const startDow = firstDay.getDay();
    const totalDays = lastDay.getDate();

    const days = [];
    for (let i = 0; i < startDow; i++) days.push(null);
    for (let d = 1; d <= totalDays; d++) {
      const dateStr = year + "-" + String(m + 1).padStart(2, "0") + "-" + String(d).padStart(2, "0");
      days.push({ day: d, date: dateStr, dow: new Date(year, m, d).getDay() });
    }
    return days;
  }

  function getWeekDays(startOfWeek) {
    const days = [];
    for (let i = 0; i < 7; i++) {
      const d = new Date(startOfWeek);
      d.setDate(d.getDate() + i);
      const dateStr = d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
      days.push({ day: d.getDate(), date: dateStr, dow: d.getDay(), fullDate: d });
    }
    return days;
  }

  function getStartOfWeek(date) {
    const d = new Date(date);
    const day = d.getDay();
    d.setDate(d.getDate() - day);
    return d;
  }

  function isHoliday(dateStr) {
    return (calendarData.holidays || []).find(h => {
      if (h.date === dateStr) return true;
      if (h.end_date && dateStr >= h.date && dateStr <= h.end_date) return true;
      return false;
    });
  }

  function getLessonsForDate(dateStr) {
    return (calendarData.scheduled_lessons || []).filter(s => s.date === dateStr);
  }

  function isSchoolDay(dow) {
    const dayNames = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"];
    return calendarData.school_days ? calendarData.school_days[dayNames[dow]] : (dow >= 1 && dow <= 5);
  }

  return (
                    <div className="fade-in">
                      {/* Calendar Header */}
                      <div className="glass-card" style={{ padding: "16px 20px", marginBottom: "20px", display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "12px" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                          <button
                            onClick={() => {
                              const d = new Date(calendarMonth)
                              d.setMonth(d.getMonth() - 1)
                              setCalendarMonth(d)
                            }}
                            style={{ background: "var(--glass-bg)", border: "1px solid var(--glass-border)", borderRadius: "8px", padding: "6px 10px", cursor: "pointer", color: "var(--text-primary)" }}
                          >
                            <Icon name="ChevronLeft" size={18} />
                          </button>
                          <h3 style={{ fontSize: "1.2rem", fontWeight: 700, margin: 0, minWidth: "180px", textAlign: "center" }}>
                            {calendarMonth.toLocaleDateString('en-US', { month: 'long', year: 'numeric' })}
                          </h3>
                          <button
                            onClick={() => {
                              const d = new Date(calendarMonth)
                              d.setMonth(d.getMonth() + 1)
                              setCalendarMonth(d)
                            }}
                            style={{ background: "var(--glass-bg)", border: "1px solid var(--glass-border)", borderRadius: "8px", padding: "6px 10px", cursor: "pointer", color: "var(--text-primary)" }}
                          >
                            <Icon name="ChevronRight" size={18} />
                          </button>
                          <button
                            onClick={() => setCalendarMonth(new Date())}
                            className="btn btn-secondary"
                            style={{ padding: "6px 14px", fontSize: "0.8rem" }}
                          >
                            Today
                          </button>
                        </div>
                        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                          <div style={{ display: "flex", borderRadius: "8px", overflow: "hidden", border: "1px solid var(--glass-border)" }}>
                            <button
                              onClick={() => setCalendarView('month')}
                              style={{
                                padding: "6px 14px", fontSize: "0.8rem", cursor: "pointer", border: "none",
                                background: calendarView === 'month' ? 'var(--accent-primary)' : 'var(--glass-bg)',
                                color: calendarView === 'month' ? '#fff' : 'var(--text-secondary)',
                                fontWeight: 600,
                              }}
                            >
                              Month
                            </button>
                            <button
                              onClick={() => setCalendarView('week')}
                              style={{
                                padding: "6px 14px", fontSize: "0.8rem", cursor: "pointer", border: "none",
                                background: calendarView === 'week' ? 'var(--accent-primary)' : 'var(--glass-bg)',
                                color: calendarView === 'week' ? '#fff' : 'var(--text-secondary)',
                                fontWeight: 600,
                              }}
                            >
                              Week
                            </button>
                          </div>
                          <button
                            onClick={() => { setHolidayForm({ date: '', name: '', end_date: '' }); setShowHolidayModal(true) }}
                            className="btn btn-secondary"
                            style={{ padding: "6px 14px", fontSize: "0.8rem" }}
                          >
                            <Icon name="CalendarOff" size={14} />
                            Add Holiday
                          </button>
                          <button
                            onClick={async () => {
                              setImportEvents([])
                              setImportChecked({})
                              setImportSelectedDoc('')
                              setShowImportModal(true)
                              if (supportDocs.length === 0) {
                                try {
                                  const data = await api.listSupportDocuments()
                                  if (data.documents) setSupportDocs(data.documents)
                                } catch (e) { /* ignore */ }
                              }
                            }}
                            className="btn btn-secondary"
                            style={{ padding: "6px 14px", fontSize: "0.8rem" }}
                          >
                            <Icon name="FileUp" size={14} />
                            Import
                          </button>
                        </div>
                      </div>

                      {/* Month View */}
                      {calendarView === 'month' && (() => {
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
                        )
                      })()}

                      {/* Week View */}
                      {calendarView === 'week' && (() => {
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
                        )
                      })()}

                      {/* Add Event / Schedule Lesson Modal */}
                      {selectedCalendarDate && (
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
                      )}

                      {/* Edit Event Modal */}
                      {editingEvent && (
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
                      )}

                      {/* Add Holiday Modal */}
                      <HolidayModal
                        open={showHolidayModal}
                        onClose={() => setShowHolidayModal(false)}
                        form={holidayForm}
                        setForm={setHolidayForm}
                        onAdd={addHoliday}
                      />

                      {/* Import Document Modal */}
                      <ImportEventsModal
                        open={showImportModal}
                        onClose={() => setShowImportModal(false)}
                        selectedDoc={importSelectedDoc}
                        setSelectedDoc={setImportSelectedDoc}
                        events={importEvents}
                        setEvents={setImportEvents}
                        checked={importChecked}
                        setChecked={setImportChecked}
                        parsing={importParsing}
                        importing={importImporting}
                        supportDocs={supportDocs}
                        onParse={async () => {
                          if (!importSelectedDoc) return;
                          setImportParsing(true);
                          setImportEvents([]);
                          setImportChecked({});
                          try {
                            const data = await api.parseDocumentForCalendar(importSelectedDoc);
                            if (data.events) {
                              setImportEvents(data.events);
                              const checked = {};
                              data.events.forEach((_, i) => { checked[i] = true; });
                              setImportChecked(checked);
                            } else if (data.error) {
                              if (addToast) addToast(data.error, "error");
                            }
                          } catch (e) {
                            if (addToast) addToast("Failed to parse document", "error");
                          } finally {
                            setImportParsing(false);
                          }
                        }}
                        onImport={async () => {
                          const selected = importEvents.filter((_, i) => importChecked[i]);
                          if (selected.length === 0) return;
                          setImportImporting(true);
                          try {
                            const data = await api.importCalendarEvents(selected);
                            if (data.status === "imported") {
                              loadCalendar();
                              setShowImportModal(false);
                              if (addToast) addToast("Imported " + data.lessons_added + " lessons and " + data.holidays_added + " holidays", "success");
                            } else if (data.error) {
                              if (addToast) addToast(data.error, "error");
                            }
                          } catch (e) {
                            if (addToast) addToast("Failed to import events", "error");
                          } finally {
                            setImportImporting(false);
                          }
                        }}
                      />
                    </div>
  );
}
