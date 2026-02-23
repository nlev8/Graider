import Icon from './Icon';

/**
 * QuestionEditToolbar - Bulk actions bar shown when edit mode is active
 */
export default function QuestionEditToolbar({
  selectedCount,
  totalCount,
  onSelectAll,
  onDeselectAll,
  onDeleteSelected,
  onRegenerateSelected,
  onDoneEditing,
  isRegenerating,
}) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: "10px",
        padding: "10px 16px",
        background: "rgba(99, 102, 241, 0.1)",
        border: "1px solid rgba(99, 102, 241, 0.3)",
        borderRadius: "10px",
        marginBottom: "15px",
        flexWrap: "wrap",
      }}
    >
      <span style={{ fontSize: "0.9rem", fontWeight: 600, color: "var(--text-primary)" }}>
        {selectedCount} of {totalCount} selected
      </span>

      <div style={{ display: "flex", gap: "6px", marginLeft: "auto", flexWrap: "wrap" }}>
        <button
          onClick={selectedCount === totalCount ? onDeselectAll : onSelectAll}
          className="btn btn-secondary"
          style={{ padding: "6px 12px", fontSize: "0.8rem" }}
        >
          {selectedCount === totalCount ? "Deselect All" : "Select All"}
        </button>

        {selectedCount > 0 && (
          <>
            <button
              onClick={() => {
                if (window.confirm("Delete " + selectedCount + " selected question(s)? This cannot be undone.")) {
                  onDeleteSelected();
                }
              }}
              className="btn"
              style={{
                padding: "6px 12px",
                fontSize: "0.8rem",
                background: "rgba(239, 68, 68, 0.2)",
                border: "1px solid rgba(239, 68, 68, 0.3)",
                color: "#ef4444",
              }}
            >
              <Icon name="Trash2" size={14} /> Delete ({selectedCount})
            </button>

            <button
              onClick={onRegenerateSelected}
              disabled={isRegenerating}
              className="btn btn-primary"
              style={{ padding: "6px 12px", fontSize: "0.8rem" }}
            >
              <Icon name={isRegenerating ? "Loader" : "RefreshCw"} size={14} />
              {isRegenerating ? " Regenerating..." : " Regenerate (" + selectedCount + ")"}
            </button>
          </>
        )}

        <button
          onClick={onDoneEditing}
          className="btn btn-secondary"
          style={{
            padding: "6px 12px",
            fontSize: "0.8rem",
            background: "rgba(34, 197, 94, 0.2)",
            border: "1px solid rgba(34, 197, 94, 0.3)",
            color: "#22c55e",
          }}
        >
          <Icon name="Check" size={14} /> Done Editing
        </button>
      </div>
    </div>
  );
}
