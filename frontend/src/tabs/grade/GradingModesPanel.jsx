import React from "react";
import Icon from "../../components/Icon";
import * as api from "../../services/api";

/*
 * Assignment Grading Modes — collapsible panel; relocated verbatim from
 * GradeTab.jsx (CQ wave-2 split). `{savedAssignments.length > 0 && (...)}`
 * at the call site became the early-return-null below.
 *
 * gradingModesExpanded stays GradeTab-owned state (threaded as props) so the
 * expand/collapse state survives this panel unmounting when savedAssignments
 * empties — identical lifecycle to the pre-split inline JSX.
 */
export default function GradingModesPanel({
  savedAssignments,
  savedAssignmentData,
  setSavedAssignmentData,
  addToast,
  gradingModesExpanded,
  setGradingModesExpanded,
}) {
  if (savedAssignments.length === 0) return null;
  return (
    <div
      className="glass-card"
      style={{
        padding: gradingModesExpanded ? "15px 20px" : "12px 20px",
        marginBottom: "20px",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          cursor: "pointer",
        }}
        onClick={() => setGradingModesExpanded(!gradingModesExpanded)}
      >
        <h3
          style={{
            fontSize: "1rem",
            fontWeight: 600,
            display: "flex",
            alignItems: "center",
            gap: "10px",
            margin: 0,
          }}
        >
          <Icon
            name={gradingModesExpanded ? "ChevronDown" : "ChevronRight"}
            size={18}
          />
          <Icon name="FileCheck" size={18} style={{ color: "#10b981" }} />
          Assignment Grading Modes
          <span
            style={{
              fontSize: "0.8rem",
              color: "var(--text-muted)",
              fontWeight: 400,
            }}
          >
            ({savedAssignments.filter(n => savedAssignmentData[n]?.completionOnly).length} completion-only)
          </span>
        </h3>
      </div>

      {gradingModesExpanded && (
        <div style={{ marginTop: "15px" }}>
          <p
            style={{
              fontSize: "0.85rem",
              color: "var(--text-muted)",
              marginBottom: "12px",
            }}
          >
            Toggle assignments between AI grading and completion-only tracking.
          </p>
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: "8px",
              maxHeight: "250px",
              overflowY: "auto",
            }}
          >
            {savedAssignments.map((name) => {
              const isCompletionOnly = savedAssignmentData[name]?.completionOnly || false;
              return (
                <div
                  key={name}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    padding: "10px 12px",
                    borderRadius: "8px",
                    background: isCompletionOnly
                      ? "rgba(34, 197, 94, 0.1)"
                      : "rgba(99, 102, 241, 0.05)",
                    border: isCompletionOnly
                      ? "1px solid rgba(34, 197, 94, 0.3)"
                      : "1px solid var(--glass-border)",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                    <Icon
                      name={isCompletionOnly ? "CheckCircle" : "FileText"}
                      size={18}
                      style={{ color: isCompletionOnly ? "#22c55e" : "#6366f1" }}
                    />
                    <span style={{ fontWeight: 500 }}>{name}</span>
                    {isCompletionOnly && (
                      <span
                        style={{
                          fontSize: "0.7rem",
                          background: "rgba(34, 197, 94, 0.2)",
                          color: "#22c55e",
                          padding: "2px 8px",
                          borderRadius: "10px",
                          fontWeight: 600,
                        }}
                      >
                        COMPLETION
                      </span>
                    )}
                  </div>
                  <button
                    className="btn"
                    onClick={async (e) => {
                      e.stopPropagation();
                      const newData = {
                        ...savedAssignmentData[name],
                        completionOnly: !isCompletionOnly,
                      };
                      setSavedAssignmentData(prev => ({
                        ...prev,
                        [name]: newData,
                      }));
                      try {
                        // Load the full assignment first to preserve all data (including importedDoc)
                        const fullData = await api.loadAssignment(name);
                        if (fullData.assignment) {
                          await api.saveAssignmentConfig({
                            ...fullData.assignment,
                            completionOnly: !isCompletionOnly,
                          });
                        } else {
                          // Fallback if load fails
                          await api.saveAssignmentConfig({
                            ...newData,
                            title: name,
                            completionOnly: !isCompletionOnly,
                          });
                        }
                        addToast(
                          `"${name}" set to ${!isCompletionOnly ? "Completion Only" : "AI Grading"}`,
                          "success"
                        );
                      } catch (e) {
                        addToast("Error saving: " + e.message, "error");
                      }
                    }}
                    style={{
                      padding: "6px 12px",
                      fontSize: "0.8rem",
                      background: isCompletionOnly ? "rgba(34, 197, 94, 0.2)" : "rgba(99, 102, 241, 0.2)",
                      color: isCompletionOnly ? "#22c55e" : "#818cf8",
                      border: `1px solid ${isCompletionOnly ? "rgba(34, 197, 94, 0.4)" : "rgba(99, 102, 241, 0.4)"}`,
                    }}
                    title={isCompletionOnly ? "Click to enable AI grading" : "Click to set as completion only"}
                  >
                    <Icon name={isCompletionOnly ? "CheckCircle" : "Sparkles"} size={14} style={{ marginRight: "6px" }} />
                    {isCompletionOnly ? "Completion Only" : "AI Grading"}
                  </button>
                  <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                    <Icon name="Clock" size={14} style={{ color: (() => { const dd = savedAssignmentData[name]?.dueDate; if (!dd) return "var(--text-muted)"; return new Date(dd) < new Date() ? "#f87171" : "#fbbf24"; })() }} />
                    <input
                      type="date"
                      className="input"
                      value={(savedAssignmentData[name]?.dueDate || "").slice(0, 10)}
                      onChange={async (e) => {
                        const dateVal = e.target.value ? e.target.value + "T23:59" : "";
                        setSavedAssignmentData(prev => ({ ...prev, [name]: { ...prev[name], dueDate: dateVal } }));
                        try {
                          const fullData = await api.loadAssignment(name);
                          if (fullData.assignment) {
                            await api.saveAssignmentConfig({ ...fullData.assignment, dueDate: dateVal });
                          }
                          addToast(dateVal ? "Due date set for " + name : "Due date cleared for " + name, "success");
                        } catch (err) {
                          addToast("Error saving due date: " + err.message, "error");
                        }
                      }}
                      style={{ width: "130px", fontSize: "0.75rem", padding: "4px 6px", height: "30px" }}
                      title={savedAssignmentData[name]?.dueDate ? "Due: " + new Date(savedAssignmentData[name].dueDate).toLocaleDateString() : "Set due date"}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
