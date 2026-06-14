import React from "react";
import Icon from "../../components/Icon";

/**
 * StudentNameCell — the first <td> of ResultsTableRow.
 * Renders the student name plus up to 5 status badge icons:
 *   handwritten, unverified-markers, config-mismatch, resubmission, accommodations.
 * Extracted from ResultsTableRow (CQ 7→8 campaign, Wave 3).
 * Props: r (result object), studentAccommodations (map of student_id → accommodation).
 */
export default function StudentNameCell({ r, studentAccommodations }) {
  return (
                                    <td style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                                      <div
                                        style={{
                                          display: "flex",
                                          alignItems: "center",
                                          gap: "4px",
                                          overflow: "hidden",
                                        }}
                                      >
                                        <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{r.student_name}</span>
                                        {r.is_handwritten && (
                                          <span
                                            title="Handwritten/Scanned Assignment"
                                            style={{
                                              display: "inline-flex",
                                              alignItems: "center",
                                              justifyContent: "center",
                                              width: "20px",
                                              height: "20px",
                                              borderRadius: "4px",
                                              background:
                                                "rgba(16, 185, 129, 0.15)",
                                              color: "#10b981",
                                            }}
                                          >
                                            <Icon name="PenTool" size={12} />
                                          </span>
                                        )}
                                        {r.marker_status === "unverified" && (
                                          <span
                                            title="UNVERIFIED: No markers or config found. Grade may be inaccurate. Set up assignment config and regrade."
                                            style={{
                                              display: "inline-flex",
                                              alignItems: "center",
                                              justifyContent: "center",
                                              width: "20px",
                                              height: "20px",
                                              borderRadius: "4px",
                                              background:
                                                "rgba(251, 191, 36, 0.2)",
                                              color: "#fbbf24",
                                              cursor: "help",
                                            }}
                                          >
                                            <Icon
                                              name="AlertTriangle"
                                              size={12}
                                            />
                                          </span>
                                        )}
                                        {r.config_mismatch && (
                                          <span
                                            title={r.config_mismatch_reason || "CONFIG MISMATCH: This submission doesn't match any saved assignment. Grade may be incorrect!"}
                                            style={{
                                              display: "inline-flex",
                                              alignItems: "center",
                                              justifyContent: "center",
                                              width: "20px",
                                              height: "20px",
                                              borderRadius: "4px",
                                              background: "rgba(239, 68, 68, 0.2)",
                                              color: "#ef4444",
                                              cursor: "help",
                                            }}
                                          >
                                            <Icon name="FileX" size={12} />
                                          </span>
                                        )}
                                        {r.is_resubmission && (
                                          <span
                                            title={r.kept_higher
                                              ? "RESUBMISSION: Kept original grade (" + r.score + "). New submission scored " + r.resubmission_score + "."
                                              : r.previous_score != null
                                                ? "RESUBMISSION: Improved from " + r.previous_score + " → " + r.score
                                                : "RESUBMISSION: This is a newer version of a previously graded assignment."
                                            }
                                            style={{
                                              display: "inline-flex",
                                              alignItems: "center",
                                              justifyContent: "center",
                                              width: "20px",
                                              height: "20px",
                                              borderRadius: "4px",
                                              background: r.kept_higher
                                                ? "rgba(251, 191, 36, 0.15)"
                                                : "rgba(59, 130, 246, 0.15)",
                                              color: r.kept_higher ? "#fbbf24" : "#3b82f6",
                                              cursor: "help",
                                            }}
                                          >
                                            <Icon
                                              name={r.kept_higher ? "ShieldCheck" : "RefreshCw"}
                                              size={12}
                                            />
                                          </span>
                                        )}
                                        {r.student_id &&
                                          studentAccommodations[
                                            r.student_id
                                          ] && (
                                            <span
                                              title={
                                                "Accommodations: " +
                                                (studentAccommodations[
                                                  r.student_id
                                                ]?.presets
                                                  ?.map((p) => p.name)
                                                  .join(", ") || "Custom")
                                              }
                                              style={{
                                                display: "inline-flex",
                                                alignItems: "center",
                                                justifyContent: "center",
                                                width: "20px",
                                                height: "20px",
                                                borderRadius: "4px",
                                                background:
                                                  "rgba(244, 114, 182, 0.15)",
                                                color: "#f472b6",
                                                cursor: "help",
                                              }}
                                            >
                                              <Icon name="Heart" size={12} />
                                            </span>
                                          )}
                                      </div>
                                    </td>
  );
}
