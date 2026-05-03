/**
 * NewUnitModal — small dialog for naming a brand-new unit OR a brand-new
 * tag attached to a shared resource. The same modal serves both flows;
 * `mode` toggles label/copy/placeholder text.
 *
 * Extracted from App.jsx (2026-05-02) — was inline JSX gated by
 * `newUnitModal` (truthy object). Lifted as a presentational component.
 *
 * Behavior change: the inline version had two near-identical 30-line
 * async handlers (Enter key + Create button) that called the same API
 * paths. Both are collapsed into a single `onSubmit(trimmedValue)`
 * callback owned by App.jsx, so the duplication is gone.
 *
 * Props:
 *   open: bool
 *   onClose: () => void  — backdrop click, Cancel button, Escape key
 *   value: string
 *   setValue: (next) => void
 *   mode: "tag" | "unit"
 *   onSubmit: (trimmedValue) => void  — invoked from Enter key OR
 *                                       Create button when value is
 *                                       non-empty after trim
 */
import React from "react";
import Icon from "./Icon";

export default function NewUnitModal({
  open,
  onClose,
  value,
  setValue,
  mode,
  onSubmit,
}) {
  if (!open) return null;

  const isTag = mode === 'tag';
  const trimmed = (value || '').trim();
  const submit = () => {
    if (!trimmed) return;
    onSubmit(trimmed);
  };

  return (
    <div
      style={{
        position: "fixed", top: 0, left: 0, right: 0, bottom: 0,
        background: "var(--modal-bg)", display: "flex", alignItems: "center",
        justifyContent: "center", zIndex: 9999, padding: "20px",
      }}
      onClick={() => onClose()}
    >
      <div
        className="glass-card"
        style={{ maxWidth: "440px", width: "100%", padding: "28px", borderRadius: "16px" }}
        onClick={(e) => e.stopPropagation()}
      >
        <h2 style={{ fontSize: "1.2rem", fontWeight: 700, marginBottom: "6px", display: "flex", alignItems: "center", gap: "10px" }}>
          <Icon name="FolderPlus" size={20} />
          {isTag ? 'New Tag' : 'New Unit'}
        </h2>
        <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "18px" }}>
          {isTag ? 'Enter a name for the new tag' : 'Enter a name for the new unit'}
        </p>
        <input
          type="text"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              submit();
            } else if (e.key === 'Escape') {
              onClose();
            }
          }}
          placeholder={isTag ? 'e.g. Review, Formative, Civil War' : 'e.g. Unit 4: The Road to the Civil War'}
          autoFocus
          className="input"
          style={{ width: "100%", padding: "10px 14px", fontSize: "0.95rem", marginBottom: "20px" }}
        />
        <div style={{ display: "flex", gap: "10px", justifyContent: "flex-end" }}>
          <button
            onClick={() => onClose()}
            className="btn btn-secondary"
            style={{ padding: "10px 20px" }}
          >
            Cancel
          </button>
          <button
            onClick={submit}
            className="btn btn-primary"
            style={{ padding: "10px 20px" }}
            disabled={!trimmed}
          >
            {isTag ? 'Create Tag' : 'Create Unit'}
          </button>
        </div>
      </div>
    </div>
  );
}
