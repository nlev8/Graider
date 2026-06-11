import React from "react";
import Icon from "../../components/Icon";

/*
 * Student Filter — relocated verbatim from GradeTab.jsx (CQ wave-2 split).
 * Always rendered (no surrounding condition at the original call site).
 */
export default function StudentFilter({
  selectedPeriod,
  periodStudents,
  sortedPeriods,
  gradeFilterStudent,
  setGradeFilterStudent,
}) {
  return (
    <div
      data-tutorial="grade-student-filter"
      style={{
        padding: "15px",
        background:
          "linear-gradient(135deg, rgba(139, 92, 246, 0.1), rgba(124, 58, 237, 0.05))",
        borderRadius: "12px",
        border: "1px solid rgba(139, 92, 246, 0.2)",
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
          name="User"
          size={16}
          style={{ color: "#8b5cf6" }}
        />
        Filter by Student
      </label>
      {selectedPeriod && periodStudents.length > 0 ? (
        <select
          className="input"
          value={gradeFilterStudent}
          onChange={(e) =>
            setGradeFilterStudent(e.target.value)
          }
          style={{ cursor: "pointer" }}
        >
          <option value="">All Students in Period</option>
          {periodStudents.map((student, idx) => {
            const displayName =
              student.full ||
              student.name ||
              `${student.first || ""} ${student.last || ""}`.trim() ||
              String(student);
            return (
              <option key={idx} value={displayName}>
                {displayName}
              </option>
            );
          })}
        </select>
      ) : (
        <div style={{ position: "relative" }}>
          <input
            type="text"
            className="input"
            list="grade-student-suggestions"
            value={gradeFilterStudent}
            onChange={(e) =>
              setGradeFilterStudent(e.target.value)
            }
            onClick={(e) => {
              if (gradeFilterStudent) {
                e.target.dataset.prev = gradeFilterStudent;
                setGradeFilterStudent("");
              }
            }}
            onBlur={(e) => {
              if (
                !gradeFilterStudent &&
                e.target.dataset.prev
              ) {
                setGradeFilterStudent(e.target.dataset.prev);
                e.target.dataset.prev = "";
              }
            }}
            placeholder={
              sortedPeriods.length > 0
                ? "Type or select student..."
                : "Type student name to filter..."
            }
            style={{
              fontSize: "0.9rem",
              paddingRight: gradeFilterStudent
                ? "30px"
                : undefined,
            }}
          />
          {gradeFilterStudent && (
            <button
              onClick={(e) => {
                e.preventDefault();
                setGradeFilterStudent("");
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
          <datalist id="grade-student-suggestions">
            {sortedPeriods
              .flatMap((p) => p.students || [])
              .map((s, i) => {
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
      )}
      {gradeFilterStudent && (
        <p
          style={{
            fontSize: "0.75rem",
            color: "#8b5cf6",
            marginTop: "8px",
            fontWeight: 500,
          }}
        >
          ✓ Will only grade files for "{gradeFilterStudent}"
        </p>
      )}
    </div>
  );
}
