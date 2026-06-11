import React from "react";
import Icon from "../../components/Icon";

/*
 * Period Filter — relocated verbatim from GradeTab.jsx (CQ wave-2 split).
 * `{periods.length > 0 && (...)}` at the call site became the
 * early-return-null below.
 */
export default function PeriodFilter({
  periods,
  sortedPeriods,
  selectedPeriod,
  setSelectedPeriod,
  setGradeFilterStudent,
  loadPeriodStudents,
  periodStudents,
}) {
  if (periods.length === 0) return null;
  return (
    <div
      data-tutorial="grade-period-filter"
      style={{
        padding: "15px",
        background:
          "linear-gradient(135deg, rgba(99, 102, 241, 0.1), rgba(168, 85, 247, 0.05))",
        borderRadius: "12px",
        border: "1px solid rgba(99, 102, 241, 0.2)",
        marginBottom: "20px",
      }}
    >
      <label
        className="label"
        style={{
          display: "flex",
          alignItems: "center",
          gap: "8px",
        }}
      >
        <Icon
          name="Users"
          size={16}
          style={{ color: "var(--accent-primary)" }}
        />
        Filter by Class Period
      </label>
      <select
        className="input"
        value={selectedPeriod}
        onChange={async (e) => {
          const periodFilename = e.target.value;
          setSelectedPeriod(periodFilename);
          setGradeFilterStudent(""); // Clear student filter when period changes
          await loadPeriodStudents(periodFilename);
        }}
        style={{ cursor: "pointer" }}
      >
        <option value="">All Periods (No Filter)</option>
        {sortedPeriods.map((p) => (
          <option key={p.filename} value={p.filename}>
            {p.period_name} ({p.row_count} students)
          </option>
        ))}
      </select>
      {selectedPeriod && periodStudents.length > 0 && (
        <p
          style={{
            fontSize: "0.75rem",
            color: "var(--accent-primary)",
            marginTop: "8px",
            fontWeight: 500,
          }}
        >
          ✓ Filtering to {periodStudents.length} students in{" "}
          {
            sortedPeriods.find(
              (p) => p.filename === selectedPeriod,
            )?.period_name
          }
        </p>
      )}
    </div>
  );
}
