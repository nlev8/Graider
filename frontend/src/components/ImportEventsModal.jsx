/**
 * ImportEventsModal — modal that lets the teacher pick a previously
 * uploaded support document, ask the AI to parse calendar events out of
 * it (lessons + holidays), then bulk-import the events they want.
 *
 * Extracted from App.jsx (2026-05-02) — was inline JSX gated by
 * `showImportModal`. Lifted as a presentational component: state stays
 * owned by App.jsx and is passed in as props, so the parse + import
 * lifecycle (api calls, toasts, calendar refresh) keeps living next to
 * the rest of App's planner state.
 *
 * Props:
 *   open: bool
 *   onClose: () => void
 *   selectedDoc / setSelectedDoc: filename of the doc to parse
 *   events / setEvents: parsed events from the AI ([{type,title,date}])
 *   checked / setChecked: { [index]: bool } selection map
 *   parsing: bool — true while the parse-document API call is in flight
 *   importing: bool — true while the import API call is in flight
 *   supportDocs: Array<{ filename, ... }> — full upload list (component
 *                filters to .pdf/.doc/.docx itself, matching prior UI)
 *   onParse: () => void — invoked when "Parse Document" clicked
 *   onImport: () => void — invoked when "Import N Events" clicked
 */
import React from "react";
import Icon from "./Icon";

export default function ImportEventsModal({
  open,
  onClose,
  selectedDoc,
  setSelectedDoc,
  events,
  setEvents,
  checked,
  setChecked,
  parsing,
  importing,
  supportDocs,
  onParse,
  onImport,
}) {
  if (!open) return null;

  return (
    <div
      style={{ position: "fixed", top: 0, left: 0, right: 0, bottom: 0, background: "rgba(0,0,0,0.6)", zIndex: 10000, display: "flex", alignItems: "center", justifyContent: "center", padding: "20px" }}
      onClick={() => onClose()}
    >
      <div
        className="glass-card"
        style={{ maxWidth: "560px", width: "100%", padding: "24px", maxHeight: "80vh", display: "flex", flexDirection: "column" }}
        onClick={e => e.stopPropagation()}
      >
        <h3 style={{ fontSize: "1.1rem", fontWeight: 700, marginBottom: "16px", display: "flex", alignItems: "center", gap: "8px" }}>
          <Icon name="FileUp" size={20} style={{ color: "var(--accent-primary)" }} />
          Import Events from Document
        </h3>

        {/* Step 1: Select document */}
        <div style={{ display: "flex", gap: "8px", marginBottom: "16px" }}>
          <select
            value={selectedDoc}
            onChange={e => { setSelectedDoc(e.target.value); setEvents([]); setChecked({}) }}
            style={{ flex: 1, padding: "8px 12px", background: "var(--input-bg)", border: "1px solid var(--input-border)", borderRadius: "8px", color: "var(--text-primary)", fontSize: "0.9rem" }}
          >
            <option value="">Select a document...</option>
            {supportDocs.filter(d => /\.(pdf|docx?)$/i.test(d.filename)).map(d => (
              <option key={d.filename} value={d.filename}>{d.filename}</option>
            ))}
          </select>
          <button
            onClick={onParse}
            className="btn btn-primary"
            style={{ padding: "8px 16px", fontSize: "0.85rem", whiteSpace: "nowrap" }}
            disabled={!selectedDoc || parsing}
          >
            {parsing ? 'Parsing...' : 'Parse Document'}
          </button>
        </div>

        {parsing && (
          <div style={{ textAlign: "center", padding: "24px 0", color: "var(--text-secondary)", fontSize: "0.9rem" }}>
            <Icon name="Loader2" size={24} style={{ animation: "spin 1s linear infinite", marginBottom: "8px" }} />
            <div>AI is extracting events from your document...</div>
          </div>
        )}

        {/* Step 2: Event list with checkboxes */}
        {events.length > 0 && !parsing && (
          <>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
              <span style={{ fontSize: "0.85rem", fontWeight: 600, color: "var(--text-secondary)" }}>
                {events.length} events found
              </span>
              <div style={{ display: "flex", gap: "8px" }}>
                <button
                  onClick={() => {
                    const all = {}
                    events.forEach((_, i) => { all[i] = true })
                    setChecked(all)
                  }}
                  style={{ background: "none", border: "none", color: "var(--accent-primary)", cursor: "pointer", fontSize: "0.8rem", fontWeight: 600, padding: "2px 6px" }}
                >
                  Select All
                </button>
                <button
                  onClick={() => setChecked({})}
                  style={{ background: "none", border: "none", color: "var(--text-secondary)", cursor: "pointer", fontSize: "0.8rem", fontWeight: 600, padding: "2px 6px" }}
                >
                  Deselect All
                </button>
              </div>
            </div>
            <div style={{ flex: 1, overflowY: "auto", maxHeight: "340px", border: "1px solid var(--glass-border)", borderRadius: "8px", marginBottom: "16px" }}>
              {events.map((ev, i) => (
                <label
                  key={i}
                  style={{
                    display: "flex", alignItems: "center", gap: "10px", padding: "8px 12px",
                    borderBottom: i < events.length - 1 ? "1px solid var(--glass-border)" : "none",
                    cursor: "pointer", fontSize: "0.85rem",
                  }}
                >
                  <input
                    type="checkbox"
                    checked={!!checked[i]}
                    onChange={() => setChecked(prev => ({ ...prev, [i]: !prev[i] }))}
                    style={{ accentColor: "var(--accent-primary)" }}
                  />
                  <span style={{
                    display: "inline-block", padding: "2px 8px", borderRadius: "4px", fontSize: "0.7rem", fontWeight: 600,
                    background: ev.type === 'holiday' ? "rgba(239, 68, 68, 0.15)" : "rgba(99, 102, 241, 0.15)",
                    color: ev.type === 'holiday' ? "#ef4444" : "#6366f1",
                    minWidth: "52px", textAlign: "center",
                  }}>
                    {ev.type === 'holiday' ? 'Holiday' : 'Lesson'}
                  </span>
                  <span style={{ fontWeight: 500, color: "var(--text-primary)", flex: 1 }}>{ev.title}</span>
                  <span style={{ color: "var(--text-secondary)", fontSize: "0.8rem", whiteSpace: "nowrap" }}>{ev.date}</span>
                </label>
              ))}
            </div>
          </>
        )}

        {/* Action buttons */}
        <div style={{ display: "flex", gap: "8px" }}>
          {events.length > 0 && !parsing && (
            <button
              onClick={onImport}
              className="btn btn-primary"
              style={{ flex: 1 }}
              disabled={importing || Object.values(checked).filter(Boolean).length === 0}
            >
              {importing ? 'Importing...' : 'Import ' + Object.values(checked).filter(Boolean).length + ' Events'}
            </button>
          )}
          <button
            onClick={() => onClose()}
            className="btn btn-secondary"
            style={{ flex: events.length > 0 && !parsing ? undefined : 1 }}
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
