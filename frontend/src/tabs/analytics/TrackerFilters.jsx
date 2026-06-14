import React from "react";
import Icon from "../../components/Icon";

/**
 * TrackerFilters — pure-prop filter controls for AssignmentTrackerCard.
 * Extracted from AssignmentTrackerCard (CQ wave cq8-04 split).
 *
 * Renders the Period / Student / Assignment filter row.
 * No state, effects, or fetches — all values and handlers are props.
 */
export default function TrackerFilters({
  missingPeriodFilter,
  setMissingPeriodFilter,
  setMissingStudentFilter,
  missingStudentFilter,
  missingAssignmentFilter,
  setMissingAssignmentFilter,
  sortedPeriods,
  periodStudentMap,
  savedAssignments,
  savedAssignmentData,
}) {
  return (
    <div
      style={{
        display: "flex",
        gap: "15px",
        flexWrap: "wrap",
        marginBottom: "20px",
      }}
    >
      <div style={{ flex: "1", minWidth: "180px" }}>
        <label
          style={{
            fontSize: "0.8rem",
            color: "#888",
            marginBottom: "4px",
            display: "block",
          }}
        >
          Period
        </label>
        <select
          className="input"
          value={missingPeriodFilter}
          onChange={(e) => {
            setMissingPeriodFilter(e.target.value);
            setMissingStudentFilter("");
          }}
          style={{ width: "100%" }}
        >
          <option value="">All Periods</option>
          {sortedPeriods.map((p) => (
            <option key={p.filename} value={p.filename}>
              {p.period_name}
            </option>
          ))}
        </select>
      </div>
      <div style={{ flex: "1", minWidth: "180px" }}>
        <label
          style={{
            fontSize: "0.8rem",
            color: "#888",
            marginBottom: "4px",
            display: "block",
          }}
        >
          Student
        </label>
        <div style={{ position: "relative" }}>
          <input
            type="text"
            className="input"
            list="missing-student-suggestions"
            placeholder="Type or select student..."
            value={missingStudentFilter}
            onChange={(e) =>
              setMissingStudentFilter(e.target.value)
            }
            onClick={(e) => {
              if (missingStudentFilter) {
                e.target.dataset.prev =
                  missingStudentFilter;
                setMissingStudentFilter("");
              }
            }}
            onBlur={(e) => {
              if (
                !missingStudentFilter &&
                e.target.dataset.prev
              ) {
                setMissingStudentFilter(
                  e.target.dataset.prev,
                );
                e.target.dataset.prev = "";
              }
            }}
            style={{
              width: "100%",
              paddingRight: missingStudentFilter
                ? "30px"
                : undefined,
            }}
          />
          {missingStudentFilter && (
            <button
              onClick={(e) => {
                e.preventDefault();
                setMissingStudentFilter("");
              }}
              style={{
                position: "absolute",
                right: "8px",
                top: "50%",
                transform: "translateY(-50%)",
                background: "none",
                border: "none",
                cursor: "pointer",
                color: "#888",
                padding: "4px",
                display: "flex",
                alignItems: "center",
              }}
              title="Clear"
            >
              <Icon name="X" size={14} />
            </button>
          )}
        </div>
        <datalist id="missing-student-suggestions">
          {(missingPeriodFilter
            ? (periodStudentMap[sortedPeriods.find(
                (p) => p.filename === missingPeriodFilter,
              )?.period_name] || [])
            : Object.values(periodStudentMap).flat()
          ).map((s, i) => {
            const name =
              s.full ||
              s.name ||
              (
                (s.first || "") +
                " " +
                (s.last || "")
              ).trim();
            return <option key={i} value={name} />;
          })}
        </datalist>
      </div>
      <div style={{ flex: "1", minWidth: "180px" }}>
        <label
          style={{
            fontSize: "0.8rem",
            color: "#888",
            marginBottom: "4px",
            display: "block",
          }}
        >
          Assignment
        </label>
        <select
          className="input"
          value={missingAssignmentFilter}
          onChange={(e) =>
            setMissingAssignmentFilter(e.target.value)
          }
          style={{ width: "100%" }}
        >
          <option value="">All Assignments</option>
          {savedAssignments.map((name) => (
            <option key={name} value={name}>
              {name}
              {savedAssignmentData[name]?.completionOnly
                ? " (Completion)"
                : ""}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}
