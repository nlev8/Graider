/**
 * ShareWithClassesModal — modal for sharing a generated content item with
 * one or more enrolled classes (via `/api/publish-to-class`). Lets the
 * teacher tag the content with a unit name and pick the target classes.
 *
 * Extracted from App.jsx (2026-05-02) — was inline JSX gated by
 * `showShareModal`. Lifted as a presentational component: it does not
 * own its state, it receives state + setters + the share handler as
 * props. The fetch + toast logic remains in App.jsx (caller-owned).
 *
 * Props:
 *   open: bool — whether the modal is shown
 *   onClose: () => void — close handler (called from backdrop / cancel)
 *   content: { title, content, contentType, unitName } | null — the
 *            content being shared (mutable: edits to unitName are
 *            written back via setContent)
 *   setContent: (updater | value) => void — setter for content
 *   selectedIds: string[] — class IDs currently selected
 *   setSelectedIds: (ids) => void — setter for selectedIds
 *   sharing: bool — true while the publish request is in flight
 *   classes: Array<{ id, name, class_students? }> — teacher's classes
 *   onShare: () => void — invoked when the user clicks "Share"
 */
import React from "react";
import Icon from "./Icon";

export default function ShareWithClassesModal({
  open,
  onClose,
  content,
  setContent,
  selectedIds,
  setSelectedIds,
  sharing,
  classes,
  onShare,
}) {
  if (!open) return null;

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0, 0, 0, 0.8)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 9999,
        padding: "20px",
      }}
      onClick={() => { if (!sharing) onClose(); }}
    >
      <div
        className="glass-card"
        style={{
          width: "100%",
          maxWidth: "440px",
          padding: "28px",
          borderRadius: "16px",
        }}
        onClick={function(e) { e.stopPropagation(); }}
      >
        <h2 style={{ fontSize: "1.3rem", fontWeight: 700, marginBottom: "6px", display: "flex", alignItems: "center", gap: "10px" }}>
          <Icon name="Share2" size={22} />
          Share with Class
        </h2>
        <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "20px" }}>
          {content ? '"' + content.title + '"' : ''}
        </p>

        {/* Unit field */}
        <div style={{ marginBottom: "16px" }}>
          <label style={{ fontSize: "0.75rem", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-muted)", display: "block", marginBottom: "4px" }}>
            Unit
          </label>
          <input
            type="text"
            value={content ? (content.unitName || '') : ''}
            onChange={function(e) {
              var val = e.target.value;
              setContent(function(prev) {
                return prev ? Object.assign({}, prev, { unitName: val }) : prev;
              });
            }}
            placeholder="e.g. Unit 4: The Road to the Civil War"
            className="input"
            style={{ width: "100%", padding: "8px 12px", fontSize: "0.9rem" }}
          />
        </div>

        {/* Select All */}
        <label
          style={{
            display: "flex",
            alignItems: "center",
            gap: "10px",
            padding: "10px 14px",
            borderRadius: "10px",
            background: "var(--hover-bg)",
            cursor: "pointer",
            marginBottom: "8px",
            fontWeight: 600,
            fontSize: "0.9rem",
          }}
        >
          <input
            type="checkbox"
            checked={selectedIds.length === classes.length && classes.length > 0}
            onChange={function(e) {
              if (e.target.checked) {
                setSelectedIds(classes.map(function(c) { return c.id; }));
              } else {
                setSelectedIds([]);
              }
            }}
            style={{ width: "18px", height: "18px", accentColor: "var(--primary-500)" }}
          />
          Select All ({classes.length} classes)
        </label>

        {/* Class list */}
        <div style={{ display: "flex", flexDirection: "column", gap: "4px", maxHeight: "300px", overflowY: "auto", marginBottom: "20px" }}>
          {classes.map(function(cls) {
            var isChecked = selectedIds.indexOf(cls.id) !== -1;
            var studentCount = cls.class_students && cls.class_students[0] ? cls.class_students[0].count : 0;
            return (
              <label
                key={cls.id}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "10px",
                  padding: "10px 14px",
                  borderRadius: "10px",
                  background: isChecked ? "rgba(99, 102, 241, 0.1)" : "transparent",
                  cursor: "pointer",
                  transition: "background 0.15s",
                  fontSize: "0.9rem",
                }}
              >
                <input
                  type="checkbox"
                  checked={isChecked}
                  onChange={function() {
                    if (isChecked) {
                      setSelectedIds(selectedIds.filter(function(id) { return id !== cls.id; }));
                    } else {
                      setSelectedIds(selectedIds.concat([cls.id]));
                    }
                  }}
                  style={{ width: "18px", height: "18px", accentColor: "var(--primary-500)" }}
                />
                <span style={{ flex: 1 }}>{cls.name}</span>
                <span style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>{studentCount} students</span>
              </label>
            );
          })}
        </div>

        {/* Actions */}
        <div style={{ display: "flex", gap: "10px", justifyContent: "flex-end" }}>
          <button
            onClick={function() { onClose(); }}
            className="btn btn-secondary"
            style={{ padding: "10px 20px" }}
            disabled={sharing}
          >
            Cancel
          </button>
          <button
            onClick={onShare}
            className="btn btn-primary"
            style={{ padding: "10px 20px", display: "flex", alignItems: "center", gap: "8px" }}
            disabled={selectedIds.length === 0 || sharing}
          >
            {sharing ? (
              React.createElement(React.Fragment, null,
                React.createElement(Icon, { name: "Loader", size: 16, className: "spinning" }), " Sharing...")
            ) : (
              React.createElement(React.Fragment, null,
                React.createElement(Icon, { name: "Share2", size: 16 }),
                " Share with " + selectedIds.length + " class" + (selectedIds.length === 1 ? "" : "es"))
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
