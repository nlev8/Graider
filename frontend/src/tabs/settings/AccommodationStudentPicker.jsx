import React from "react";
import * as api from "../../services/api";

/*
 * AccommodationStudentPicker — the "Select Students" period/checkbox block of
 * the accommodation modal, relocated verbatim from SettingsTab.jsx (CQ wave-9
 * split). The `{!accommodationModal.studentId && ...}` guard (only shown when
 * adding accommodations for new students, not when editing one) became the
 * early return below.
 */
export default function AccommodationStudentPicker({
  accommodationModal,
  accommPeriodFilter,
  setAccommPeriodFilter,
  accommSelectedStudents,
  setAccommSelectedStudents,
  accommStudentsList,
  setAccommStudentsList,
  sortedPeriods,
}) {
  if (accommodationModal.studentId) return null;

  return (
              <div style={{ marginBottom: "20px" }}>
                <label className="label">Select Students</label>
                {/* Period selector */}
                <select
                  className="input"
                  value={accommPeriodFilter}
                  onChange={async (e) => {
                    const val = e.target.value;
                    setAccommPeriodFilter(val);
                    setAccommSelectedStudents({});
                    if (val) {
                      try {
                        const data =
                          await api.getPeriodStudents(val);
                        if (data.students)
                          setAccommStudentsList(data.students);
                      } catch (err) {
                        setAccommStudentsList([]);
                      }
                    } else {
                      setAccommStudentsList([]);
                    }
                  }}
                  style={{ marginBottom: "8px" }}
                >
                  <option value="">Choose a period...</option>
                  {sortedPeriods.map((p) => (
                    <option key={p.filename} value={p.filename}>
                      {p.period_name} ({p.student_count} students)
                    </option>
                  ))}
                </select>
                {/* Student checkbox list */}
                {accommStudentsList.length > 0 && (
                  <div
                    style={{
                      maxHeight: "200px",
                      overflowY: "auto",
                      border: "1px solid var(--input-border)",
                      borderRadius: "8px",
                    }}
                  >
                    {accommStudentsList.map((s) => {
                      const sid = s.id || s.student_id || "";
                      const name = (
                        s.full ||
                        (s.first || "") + " " + (s.last || "")
                      ).trim();
                      const checked = !!accommSelectedStudents[sid];
                      return (
                        <label
                          key={sid}
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: "10px",
                            padding: "8px 12px",
                            borderBottom:
                              "1px solid var(--input-border)",
                            cursor: "pointer",
                            background: checked
                              ? "rgba(96,165,250,0.1)"
                              : "transparent",
                            fontSize: "0.85rem",
                          }}
                        >
                          <input
                            type="checkbox"
                            checked={checked}
                            onChange={(e) => {
                              setAccommSelectedStudents((prev) => {
                                const next = { ...prev };
                                if (e.target.checked) {
                                  next[sid] = name;
                                } else {
                                  delete next[sid];
                                }
                                return next;
                              });
                            }}
                          />
                          {name}
                        </label>
                      );
                    })}
                  </div>
                )}
                {Object.keys(accommSelectedStudents).length > 0 && (
                  <div
                    style={{
                      marginTop: "6px",
                      fontSize: "0.8rem",
                      color: "#60a5fa",
                    }}
                  >
                    {Object.keys(accommSelectedStudents).length}{" "}
                    student(s) selected
                  </div>
                )}
              </div>
  );
}
