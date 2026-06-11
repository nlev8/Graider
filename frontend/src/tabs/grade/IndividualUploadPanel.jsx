import React from "react";
import Icon from "../../components/Icon";
import StudentNameAutocomplete from "./StudentNameAutocomplete";

/*
 * Individual Upload — paper/handwritten assignment panel; relocated verbatim
 * from GradeTab.jsx (CQ wave-2 split). The student-name autocomplete block and
 * the result card are further extracted (StudentNameAutocomplete + the inline
 * IndividualResultCard below) to keep every function ≤ ~250 LOC.
 */

// Result card shown after a successful individual grade. `{individualUpload
// .result && (...)}` at the original site became the early-return-null below.
export function IndividualResultCard({ result, studentName }) {
  if (!result) return null;
  return (
    <div
      style={{
        padding: "12px",
        borderRadius: "10px",
        background: "rgba(16, 185, 129, 0.15)",
        border: "1px solid rgba(16, 185, 129, 0.3)",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "12px",
        }}
      >
        <span
          style={{
            fontSize: "1.5rem",
            fontWeight: 800,
            color: "#10b981",
          }}
        >
          {result.letter_grade}
        </span>
        <div>
          <div style={{ fontWeight: 600 }}>
            {result.score}%
          </div>
          <div
            style={{
              fontSize: "0.75rem",
              color: "var(--text-muted)",
            }}
          >
            {studentName}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function IndividualUploadPanel({
  individualUpload,
  setIndividualUpload,
  periodStudents,
  getStudentSuggestions,
  handleIndividualFileSelect,
  handleIndividualGrade,
  clearIndividualUpload,
}) {
  return (
    <div
      data-tutorial="grade-individual"
      style={{
        marginTop: "20px",
        padding: "20px",
        borderRadius: "16px",
        background:
          "linear-gradient(135deg, rgba(16, 185, 129, 0.1), rgba(5, 150, 105, 0.05))",
        border: "1px solid rgba(16, 185, 129, 0.2)",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "10px",
          marginBottom: "15px",
        }}
      >
        <div
          style={{
            width: "36px",
            height: "36px",
            borderRadius: "10px",
            background: "rgba(16, 185, 129, 0.15)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <Icon
            name="Camera"
            size={20}
            style={{ color: "#10b981" }}
          />
        </div>
        <div>
          <h4 style={{ margin: 0, fontWeight: 600 }}>
            Individual Upload
          </h4>
          <p
            style={{
              margin: 0,
              fontSize: "0.75rem",
              color: "var(--text-muted)",
            }}
          >
            For paper/handwritten assignments (uses GPT-4o
            vision)
          </p>
        </div>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: individualUpload.preview
            ? "1fr 1fr"
            : "1fr",
          gap: "15px",
        }}
      >
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: "12px",
          }}
        >
          {/* Student Name with Autocomplete */}
          <StudentNameAutocomplete
            individualUpload={individualUpload}
            setIndividualUpload={setIndividualUpload}
            periodStudents={periodStudents}
            getStudentSuggestions={getStudentSuggestions}
          />

          <div
            onClick={() =>
              document
                .getElementById("individualFileInput")
                ?.click()
            }
            style={{
              padding: "20px",
              border: "2px dashed var(--glass-border)",
              borderRadius: "10px",
              textAlign: "center",
              cursor: "pointer",
              background: individualUpload.file
                ? "rgba(16, 185, 129, 0.1)"
                : "var(--glass-bg)",
            }}
          >
            <input
              id="individualFileInput"
              type="file"
              accept="image/*,.pdf,.heic,.heif"
              onChange={handleIndividualFileSelect}
              style={{ display: "none" }}
            />
            {individualUpload.file ? (
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: "8px",
                }}
              >
                <Icon
                  name="CheckCircle"
                  size={20}
                  style={{ color: "#10b981" }}
                />
                <span
                  style={{
                    fontWeight: 500,
                    fontSize: "0.9rem",
                  }}
                >
                  {individualUpload.file.name}
                </span>
              </div>
            ) : (
              <>
                <Icon
                  name="Upload"
                  size={24}
                  style={{ color: "var(--text-muted)" }}
                />
                <p
                  style={{
                    margin: "8px 0 0",
                    fontSize: "0.85rem",
                    color: "var(--text-secondary)",
                  }}
                >
                  Click to upload image
                </p>
              </>
            )}
          </div>

          <div style={{ display: "flex", gap: "8px" }}>
            <button
              onClick={handleIndividualGrade}
              disabled={
                !individualUpload.file ||
                !individualUpload.studentName.trim() ||
                individualUpload.isGrading
              }
              className="btn btn-primary"
              style={{
                flex: 1,
                opacity:
                  !individualUpload.file ||
                  !individualUpload.studentName.trim() ||
                  individualUpload.isGrading
                    ? 0.5
                    : 1,
              }}
            >
              {individualUpload.isGrading ? (
                <>Grading...</>
              ) : (
                <>
                  <Icon name="Sparkles" size={16} />
                  Grade
                </>
              )}
            </button>
            {individualUpload.file && (
              <button
                onClick={clearIndividualUpload}
                className="btn btn-secondary"
                style={{ padding: "8px 12px" }}
                aria-label="Clear individual upload"
                title="Clear individual upload"
              >
                <Icon name="X" size={16} />
              </button>
            )}
          </div>

          <IndividualResultCard
            result={individualUpload.result}
            studentName={individualUpload.studentName}
          />
        </div>

        {individualUpload.preview && (
          <div
            style={{
              borderRadius: "10px",
              overflow: "hidden",
              border: "1px solid var(--glass-border)",
            }}
          >
            <img
              src={individualUpload.preview}
              alt="Preview"
              style={{
                width: "100%",
                height: "auto",
                maxHeight: "250px",
                objectFit: "contain",
                background: "#fff",
              }}
            />
          </div>
        )}
      </div>
    </div>
  );
}
