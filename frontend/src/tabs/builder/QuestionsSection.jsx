import React from "react";
import Icon from "../../components/Icon";

/*
 * Questions list editor — relocated verbatim from BuilderTab.jsx
 * (CQ wave-9 split).
 */
export default function QuestionsSection({
  assignment,
  addQuestion,
  updateQuestion,
  removeQuestion,
  markerLibrary,
}) {
  return (
    <div data-tutorial="builder-questions" style={{ marginBottom: "20px" }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "15px",
        }}
      >
        <h3 style={{ fontSize: "1rem", fontWeight: 600 }}>
          Questions ({assignment.questions.length}) -{" "}
          {assignment.questions.reduce(
            (sum, q) => sum + (q.points || 0),
            0,
          )}{" "}
          pts
        </h3>
        <button
          onClick={addQuestion}
          className="btn btn-primary"
        >
          <Icon name="Plus" size={16} /> Add Question
        </button>
      </div>

      {assignment.questions.length === 0 ? (
        <div
          style={{
            textAlign: "center",
            padding: "40px",
            background: "var(--input-bg)",
            borderRadius: "12px",
            color: "var(--text-muted)",
          }}
        >
          <Icon name="FileQuestion" size={40} />
          <p style={{ marginTop: "10px" }}>
            No questions yet. Click "Add Question" to start
            building.
          </p>
        </div>
      ) : (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: "15px",
          }}
        >
          {assignment.questions.map((q, i) => (
            <div
              key={q.id}
              style={{
                background: "var(--glass-bg)",
                borderRadius: "12px",
                border: "1px solid var(--glass-border)",
                padding: "20px",
              }}
            >
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  marginBottom: "15px",
                }}
              >
                <span
                  style={{
                    fontSize: "0.9rem",
                    fontWeight: 600,
                    color: "#a5b4fc",
                  }}
                >
                  Question {i + 1}
                </span>
                <button
                  onClick={() => removeQuestion(i)}
                  style={{
                    padding: "6px 10px",
                    borderRadius: "6px",
                    border: "none",
                    background: "rgba(248,113,113,0.2)",
                    color: "#f87171",
                    cursor: "pointer",
                  }}
                >
                  <Icon name="Trash2" size={14} />
                </button>
              </div>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 150px 100px",
                  gap: "12px",
                  marginBottom: "12px",
                }}
              >
                <div>
                  <label
                    className="label"
                    style={{ fontSize: "0.8rem" }}
                  >
                    Marker
                  </label>
                  <select
                    className="input"
                    value={q.marker}
                    onChange={(e) =>
                      updateQuestion(
                        i,
                        "marker",
                        e.target.value,
                      )
                    }
                  >
                    {(
                      markerLibrary[assignment.subject] ||
                      markerLibrary["Other"]
                    ).map((m) => (
                      <option key={m} value={m}>
                        {m}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label
                    className="label"
                    style={{ fontSize: "0.8rem" }}
                  >
                    Type
                  </label>
                  <select
                    className="input"
                    value={q.type}
                    onChange={(e) =>
                      updateQuestion(i, "type", e.target.value)
                    }
                  >
                    <option value="short_answer">
                      Short Answer
                    </option>
                    <option value="essay">Essay</option>
                    <option value="fill_blank">
                      Fill in Blank
                    </option>
                    <option value="multiple_choice">
                      Multiple Choice
                    </option>
                  </select>
                </div>
                <div>
                  <label
                    className="label"
                    style={{ fontSize: "0.8rem" }}
                  >
                    Points
                  </label>
                  <input
                    type="number"
                    className="input"
                    value={q.points}
                    onChange={(e) =>
                      updateQuestion(
                        i,
                        "points",
                        parseInt(e.target.value) || 0,
                      )
                    }
                    min="0"
                  />
                </div>
              </div>
              <div>
                <label
                  className="label"
                  style={{ fontSize: "0.8rem" }}
                >
                  Question/Prompt
                </label>
                <textarea
                  className="input"
                  value={q.prompt}
                  onChange={(e) =>
                    updateQuestion(i, "prompt", e.target.value)
                  }
                  placeholder="Enter the question..."
                  style={{ minHeight: "60px" }}
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
