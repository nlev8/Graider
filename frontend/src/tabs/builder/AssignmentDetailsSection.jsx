import React from "react";

/*
 * Assignment Details grid (title, aliases, subject, total points) —
 * relocated verbatim from BuilderTab.jsx (CQ wave-9 split).
 */
export default function AssignmentDetailsSection({ assignment, setAssignment, config }) {
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "2fr 1fr 1fr",
        gap: "15px",
        marginBottom: "25px",
      }}
    >
      <div>
        <label className="label">Assignment Title</label>
        <input
          type="text"
          className="input"
          value={assignment.title}
          onChange={(e) =>
            setAssignment({
              ...assignment,
              title: e.target.value,
            })
          }
          placeholder="e.g., Louisiana Purchase Quiz"
        />
      </div>
      <div style={{ gridColumn: "1 / -1" }}>
        <label className="label" style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          Aliases (Alternative Names)
          <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", fontWeight: 400 }}>
            - helps match student files with different naming
          </span>
        </label>
        <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", marginBottom: "8px" }}>
          {(assignment.aliases || []).map((alias, i) => (
            <span
              key={i}
              style={{
                padding: "4px 10px",
                background: "rgba(139, 92, 246, 0.2)",
                border: "1px solid rgba(139, 92, 246, 0.4)",
                borderRadius: "6px",
                fontSize: "0.85rem",
                display: "flex",
                alignItems: "center",
                gap: "6px",
              }}
            >
              {alias}
              <button
                onClick={() => setAssignment({
                  ...assignment,
                  aliases: assignment.aliases.filter((_, idx) => idx !== i)
                })}
                style={{
                  background: "none",
                  border: "none",
                  color: "var(--text-muted)",
                  cursor: "pointer",
                  padding: "0",
                  fontSize: "1rem",
                  lineHeight: 1,
                }}
                title="Remove alias"
              >
                ×
              </button>
            </span>
          ))}
        </div>
        <div style={{ display: "flex", gap: "8px" }}>
          <input
            type="text"
            className="input"
            placeholder="Add alias (e.g., Chapter 10 Section 2)"
            style={{ flex: 1 }}
            onKeyDown={(e) => {
              if (e.key === "Enter" && e.target.value.trim()) {
                e.preventDefault();
                const newAlias = e.target.value.trim();
                if (!assignment.aliases?.includes(newAlias)) {
                  setAssignment({
                    ...assignment,
                    aliases: [...(assignment.aliases || []), newAlias]
                  });
                }
                e.target.value = "";
              }
            }}
          />
          <button
            className="btn btn-secondary"
            style={{ padding: "8px 16px" }}
            onClick={(e) => {
              const input = e.target.previousSibling;
              if (input.value.trim()) {
                const newAlias = input.value.trim();
                if (!assignment.aliases?.includes(newAlias)) {
                  setAssignment({
                    ...assignment,
                    aliases: [...(assignment.aliases || []), newAlias]
                  });
                }
                input.value = "";
              }
            }}
          >
            Add
          </button>
        </div>
      </div>
      <div>
        <label className="label">Subject</label>
        <input
          type="text"
          className="input"
          value={config.subject || "Social Studies"}
          disabled
          style={{
            background: "var(--glass-hover)",
            color: "var(--text-secondary)",
          }}
          title="Subject is set in Settings tab"
        />
      </div>
      <div>
        <label className="label">Total Points</label>
        <input
          type="number"
          className="input"
          value={assignment.totalPoints}
          onChange={(e) => {
            const val = e.target.value;
            setAssignment({
              ...assignment,
              totalPoints: val === '' ? '' : parseInt(val),
            });
          }}
          onBlur={(e) => {
            const val = parseInt(e.target.value) || 100;
            setAssignment({
              ...assignment,
              totalPoints: val,
            });
          }}
          disabled={assignment.completionOnly}
          style={
            assignment.completionOnly ? { opacity: 0.5 } : {}
          }
        />
      </div>
    </div>
  );
}
