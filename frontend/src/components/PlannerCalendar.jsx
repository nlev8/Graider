import React, { useState, useEffect } from "react";
import HolidayModal from "./HolidayModal";
import ImportEventsModal from "./ImportEventsModal";
import * as api from "../services/api";
import CalendarHeader from "./planner-calendar/CalendarHeader";
import MonthView from "./planner-calendar/MonthView";
import WeekView from "./planner-calendar/WeekView";
import AddEventModal from "./planner-calendar/AddEventModal";
import EditEventModal from "./planner-calendar/EditEventModal";

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

  // Shared props bag for the planner-calendar/* children (CQ wave-5 split).
  // State + handlers stay in this always-mounted shell; children destructure
  // what they render and guard their own visibility with early-return-null.
  const calendarProps = {
    calendarData, calendarMonth, setCalendarMonth, calendarView, setCalendarView,
    selectedCalendarDate, setSelectedCalendarDate, setShowHolidayModal, setHolidayForm,
    calendarDragId, setCalendarDragId, setShowImportModal, setImportEvents,
    setImportChecked, setImportSelectedDoc, editingEvent, setEditingEvent,
    quickAddForm, setQuickAddForm, savedLessons, supportDocs, setSupportDocs,
    scheduleLesson, unscheduleLesson, removeHoliday,
    getCalendarDays, getWeekDays, getStartOfWeek, isHoliday, getLessonsForDate, isSchoolDay,
  };

  return (
                    <div className="fade-in">
                      {/* Calendar Header */}
                      <CalendarHeader {...calendarProps} />

                      {/* Month View */}
                      <MonthView {...calendarProps} />

                      {/* Week View */}
                      <WeekView {...calendarProps} />

                      {/* Add Event / Schedule Lesson Modal */}
                      <AddEventModal {...calendarProps} />

                      {/* Edit Event Modal */}
                      <EditEventModal {...calendarProps} />

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
