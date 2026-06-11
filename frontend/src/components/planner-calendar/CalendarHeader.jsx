import React from "react";
import Icon from "../Icon";
import * as api from "../../services/api";

// Calendar header bar: month navigation, month/week view toggle, Add Holiday,
// and Import (lazy-loads supportDocs via the App-level shared setter on first
// open — handler relocated verbatim with its button per the CQ split rule that
// handler+markup pairs stay together).
export default function CalendarHeader(props) {
  const {
    calendarMonth, setCalendarMonth, calendarView, setCalendarView,
    setHolidayForm, setShowHolidayModal, setShowImportModal,
    setImportEvents, setImportChecked, setImportSelectedDoc,
    supportDocs, setSupportDocs,
  } = props;
  return (
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
  );
}
