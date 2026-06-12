import React from "react";
import Icon from "../components/Icon";
import { getAuthHeaders } from "../services/api";

/*
 * FocusExportModal — the Focus SIS CSV export modal, relocated VERBATIM from
 * App.jsx 2545-2801 in the finale split. The shell's `{focusExportModal && (`
 * guard became the early return below (house pattern: `{cond && ...}` →
 * `if (!(cond)) return null;`), so nothing inside evaluates while closed —
 * exactly like the pre-split short-circuit. The grouping IIFE inside is
 * preserved as-is.
 */
export default function FocusExportModal(props) {
  const {
    addToast, editedResults, focusExportLoading, focusExportModal, focusIncludeLetterGrade,
    setFocusExportLoading, setFocusExportModal, setFocusIncludeLetterGrade, status,
  } = props;

  // Was `{focusExportModal && (...)}` in the App shell.
  if (!focusExportModal) return null;

  return (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: "rgba(0,0,0,0.7)",
            zIndex: 10000,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: "20px",
          }}
        >
          <div
            className="glass-card"
            style={{
              borderRadius: "12px",
              width: "100%",
              maxWidth: "500px",
              padding: "25px",
              boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.5)",
            }}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginBottom: "20px",
              }}
            >
              <h2
                style={{
                  fontSize: "1.2rem",
                  fontWeight: 700,
                  display: "flex",
                  alignItems: "center",
                  gap: "10px",
                }}
              >
                <Icon name="Download" size={24} />
                Export to Focus
              </h2>
              <button
                onClick={() => setFocusExportModal(false)}
                style={{
                  background: "var(--glass-bg)",
                  border: "1px solid var(--glass-border)",
                  cursor: "pointer",
                  padding: "8px",
                  borderRadius: "6px",
                  color: "var(--text-primary)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <Icon name="X" size={20} />
              </button>
            </div>

            <p
              style={{
                color: "var(--text-secondary)",
                marginBottom: "20px",
                fontSize: "0.9rem",
              }}
            >
              Generate a CSV file formatted for Focus SIS import with Student_ID
              and Score columns.
            </p>


            {/* Group results by assignment — filter out one-off student uploads
                (config mismatches where the "assignment" is actually a filename) */}
            {(() => {
              const assignmentCounts = {};
              status.results.forEach((r) => {
                const a = r.assignment || "Unknown";
                assignmentCounts[a] = (assignmentCounts[a] || 0) + 1;
              });
              const assignments = Object.keys(assignmentCounts)
                .filter((a) => assignmentCounts[a] >= 2 || Object.keys(assignmentCounts).length <= 3)
                .sort((a, b) => assignmentCounts[b] - assignmentCounts[a]);
              const periods = [
                ...new Set(status.results.map((r) => r.period || "All")),
              ];
              return (
                <div
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: "15px",
                  }}
                >
                  <div>
                    <label className="label">Assignment</label>
                    <select
                      id="focus-assignment"
                      className="input"
                      defaultValue={assignments[0]}
                    >
                      {assignments.map((a) => (
                        <option key={a} value={a}>
                          {a}
                        </option>
                      ))}
                    </select>
                  </div>
                  {periods.length > 1 && (
                    <div>
                      <label className="label">Period</label>
                      <select
                        id="focus-period"
                        className="input"
                        defaultValue="all"
                      >
                        <option value="all">All Periods</option>
                        {periods
                          .filter((p) => p !== "All")
                          .map((p) => (
                            <option key={p} value={p}>
                              {p}
                            </option>
                          ))}
                      </select>
                    </div>
                  )}
                  <div
                    style={{
                      padding: "12px",
                      background: "var(--glass-bg)",
                      borderRadius: "8px",
                      fontSize: "0.85rem",
                      color: "var(--text-secondary)",
                    }}
                  >
                    <Icon
                      name="Info"
                      size={14}
                      style={{ marginRight: "6px", verticalAlign: "middle" }}
                    />
                    Students without a Student_ID will be matched by name using
                    Claude AI.
                  </div>
                  <label style={{
                    display: "flex", alignItems: "center", gap: "8px",
                    padding: "10px 12px", borderRadius: "8px", cursor: "pointer",
                    background: "var(--glass-bg)", fontSize: "0.85rem",
                    color: "var(--text-secondary)",
                  }}>
                    <input
                      type="checkbox"
                      checked={focusIncludeLetterGrade}
                      onChange={(e) => setFocusIncludeLetterGrade(e.target.checked)}
                      style={{ accentColor: "#6366f1" }}
                    />
                    Include Letter Grade column
                  </label>
                  <button
                    onClick={async () => {
                      setFocusExportLoading(true);
                      try {
                        const assignment =
                          document.getElementById("focus-assignment")?.value;
                        const period =
                          document.getElementById("focus-period")?.value ||
                          "all";

                        // Filter results (use editedResults if available, to include curves/edits)
                        const sourceResults = editedResults.length > 0 ? editedResults : status.results;
                        let resultsToExport = sourceResults.filter(
                          (r) =>
                            (r.assignment || "Unknown") === assignment &&
                            (period === "all" ||
                              (r.period || "All") === period),
                        );

                        const authHdrs = await getAuthHeaders();
                        const response = await fetch("/api/export-focus-csv", {
                          method: "POST",
                          headers: { "Content-Type": "application/json", ...authHdrs },
                          body: JSON.stringify({
                            results: resultsToExport,
                            assignment,
                            period,
                            periods: periods.map((p) => ({ name: p })),
                            include_letter_grade: focusIncludeLetterGrade,
                          }),
                        });

                        const data = await response.json();
                        if (data.csv) {
                          // Download the CSV
                          const blob = new Blob([data.csv], {
                            type: "text/csv",
                          });
                          const url = URL.createObjectURL(blob);
                          const a = document.createElement("a");
                          a.href = url;
                          a.download = data.filename || "focus_grades.csv";
                          document.body.appendChild(a);
                          a.click();
                          document.body.removeChild(a);
                          URL.revokeObjectURL(url);

                          addToast(
                            `Exported ${data.count} grades to ${data.filename}`,
                            "success",
                          );
                          setFocusExportModal(false);
                        } else {
                          addToast(data.error || "Export failed", "error");
                        }
                      } catch (err) {
                        addToast("Export error: " + err.message, "error");
                      } finally {
                        setFocusExportLoading(false);
                      }
                    }}
                    disabled={focusExportLoading || status.results.length === 0}
                    className="btn btn-primary"
                    style={{ width: "100%", marginTop: "10px" }}
                  >
                    {focusExportLoading ? (
                      <>
                        <Icon
                          name="Loader2"
                          size={18}
                          style={{ animation: "spin 1s linear infinite" }}
                        />
                        Generating CSV with Claude...
                      </>
                    ) : (
                      <>
                        <Icon name="Download" size={18} />
                        Download Focus CSV
                      </>
                    )}
                  </button>
                  <button
                    onClick={() => setFocusExportModal(false)}
                    className="btn btn-secondary"
                    style={{ width: "100%", marginTop: "10px" }}
                  >
                    Cancel
                  </button>
                </div>
              );
            })()}
          </div>
        </div>
  );
}
