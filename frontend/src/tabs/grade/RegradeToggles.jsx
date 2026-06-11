import React from "react";

/*
 * Regrade / exclusion toggles — relocated verbatim from GradeTab.jsx (CQ
 * wave-2 split). Three independently-conditional cards:
 *   1. Skip Verified ("Regrade All") — shown when any unverified result exists.
 *   2. Exclude Already Graded Files — shown when any results exist.
 *   3. Exclude Already Approved — shown when results exist AND any approval.
 * The conditions are independent, so they stay as `{cond && ...}` inside this
 * component rather than early returns (only whole-component conditions convert
 * to early-return-null under the wave-1 precedent).
 */
export default function RegradeToggles({
  status,
  emailApprovals,
  savedAssignmentData,
  gradeFilterAssignment,
  skipVerified,
  setSkipVerified,
  excludeGradedStudents,
  setExcludeGradedStudents,
  excludeApprovedStudents,
  setExcludeApprovedStudents,
}) {
  return (
    <>
      {/* Skip Verified Toggle - Show when there are unverified results */}
      {status.results &&
        status.results.some(
          (r) => r.marker_status === "unverified",
        ) && (
          <div
            style={{
              padding: "15px",
              background:
                "linear-gradient(135deg, rgba(251, 191, 36, 0.1), rgba(245, 158, 11, 0.05))",
              borderRadius: "12px",
              border: "1px solid rgba(251, 191, 36, 0.3)",
              marginBottom: "20px",
            }}
          >
            <label
              style={{
                display: "flex",
                alignItems: "center",
                gap: "10px",
                cursor: "pointer",
              }}
            >
              <input
                type="checkbox"
                checked={skipVerified}
                onChange={(e) =>
                  setSkipVerified(e.target.checked)
                }
                style={{
                  width: "18px",
                  height: "18px",
                  cursor: "pointer",
                }}
              />
              <div>
                <span
                  style={{ fontWeight: 600, color: "#fbbf24" }}
                >
                  Regrade All (Including Verified)
                </span>
                <p
                  style={{
                    fontSize: "0.75rem",
                    color: "var(--text-secondary)",
                    margin: "4px 0 0 0",
                  }}
                >
                  {`Check to also regrade ${status.results.filter((r) => r.marker_status === "verified").length} verified grades. ${status.results.filter((r) => r.marker_status === "unverified").length} unverified will always be regraded.`}
                </p>
              </div>
            </label>
          </div>
        )}

      {/* Exclude students already graded in this session */}
      {status.results.length > 0 && (
        <div
          className="glass-card"
          style={{
            padding: "15px 20px",
            marginBottom: "20px",
            background: "rgba(34, 197, 94, 0.05)",
            border: "1px solid rgba(34, 197, 94, 0.2)",
          }}
        >
          <label
            style={{
              display: "flex",
              alignItems: "center",
              gap: "10px",
              cursor: "pointer",
            }}
          >
            <input
              type="checkbox"
              checked={excludeGradedStudents}
              onChange={(e) =>
                setExcludeGradedStudents(e.target.checked)
              }
              style={{
                width: "18px",
                height: "18px",
                cursor: "pointer",
              }}
            />
            <div>
              <span
                style={{ fontWeight: 600, color: "#22c55e" }}
              >
                Exclude Already Graded Files
              </span>
              <p
                style={{
                  fontSize: "0.75rem",
                  color: "var(--text-secondary)",
                  margin: "4px 0 0 0",
                }}
              >
                Skip {(() => {
                  // Filter results by current assignment filter
                  let relevantResults = status.results;
                  if (gradeFilterAssignment) {
                    const cfg = savedAssignmentData[gradeFilterAssignment] || {};
                    const importedFn = (cfg.importedFilename || "").toLowerCase().replace(/\.[^/.]+$/, "");
                    const names = [gradeFilterAssignment, cfg.title || "", ...(cfg.aliases || []), importedFn].filter(Boolean).map(n => n.toLowerCase());
                    relevantResults = status.results.filter((r) => {
                      const rAssign = (r.assignment || "").toLowerCase();
                      const rFile = (r.filename || "").toLowerCase();
                      return names.some(n => rAssign.includes(n) || rFile.includes(n) || n.includes(rAssign));
                    });
                  }
                  return relevantResults.length;
                })()} file(s) already graded{gradeFilterAssignment ? ` for "${gradeFilterAssignment}"` : ""}.
                Only grade new files.
              </p>
            </div>
          </label>
        </div>
      )}

      {/* Exclude students already approved */}
      {status.results.length > 0 && Object.values(emailApprovals).some((v) => v === "approved") && (
        <div
          className="glass-card"
          style={{
            padding: "15px 20px",
            marginBottom: "20px",
            background: "rgba(34, 197, 94, 0.05)",
            border: "1px solid rgba(34, 197, 94, 0.2)",
          }}
        >
          <label
            style={{
              display: "flex",
              alignItems: "center",
              gap: "10px",
              cursor: "pointer",
            }}
          >
            <input
              type="checkbox"
              checked={excludeApprovedStudents}
              onChange={(e) =>
                setExcludeApprovedStudents(e.target.checked)
              }
              style={{
                width: "18px",
                height: "18px",
                cursor: "pointer",
              }}
            />
            <div>
              <span
                style={{ fontWeight: 600, color: "#22c55e" }}
              >
                Exclude Already Approved
              </span>
              <p
                style={{
                  fontSize: "0.75rem",
                  color: "var(--text-secondary)",
                  margin: "4px 0 0 0",
                }}
              >
                Skip {(() => {
                  // Count approved results, optionally filtered by assignment
                  let count = 0;
                  if (gradeFilterAssignment) {
                    const cfg = savedAssignmentData[gradeFilterAssignment] || {};
                    const importedFn = (cfg.importedFilename || "").toLowerCase().replace(/\.[^/.]+$/, "");
                    const names = [gradeFilterAssignment, cfg.title || "", ...(cfg.aliases || []), importedFn].filter(Boolean).map(n => n.toLowerCase());
                    status.results.forEach((r, idx) => {
                      if (emailApprovals[idx] !== "approved") return;
                      const rAssign = (r.assignment || "").toLowerCase();
                      const rFile = (r.filename || "").toLowerCase();
                      if (names.some(n => rAssign.includes(n) || rFile.includes(n) || n.includes(rAssign))) {
                        count++;
                      }
                    });
                  } else {
                    status.results.forEach((r, idx) => {
                      if (emailApprovals[idx] === "approved") count++;
                    });
                  }
                  return count;
                })()} approved file(s){gradeFilterAssignment ? ` for "${gradeFilterAssignment}"` : ""}.
                Only re-grade unapproved files.
              </p>
            </div>
          </label>
        </div>
      )}
    </>
  );
}
