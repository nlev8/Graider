import React from "react";
import Icon from "../Icon";
import ThemeToggle from "./ThemeToggle";
import { containerStyle, cardStyle, buttonStyle } from "./portalStyles";

// ============ RESULTS SCREEN ============
// JSX (and the render-scoped isPendingReview/isPartial/percentage/gradeColor
// locals) moved verbatim from StudentPortal.jsx (CQ wave-6 split). Stage
// guard replaces the shell's original `if (stage === "results")` block.
export default function ResultsScreen(props) {
  const {
    stage, lightMode, setLightMode,
    results, assessment, studentName, onBack,
  } = props;
  if (stage !== "results") return null;

  var isPendingReview = results && results.grading_status === "pending_review";
  var isPartial = results && results.grading_status === "partial";
  var percentage = results?.percentage || 0;
  var gradeColor = percentage >= 90 ? "var(--success)" : percentage >= 70 ? "var(--warning)" : "var(--danger)";

  return (
    <div style={containerStyle}>
      <ThemeToggle lightMode={lightMode} setLightMode={setLightMode} />
      <div style={{ padding: "40px 20px", maxWidth: "700px", margin: "0 auto" }}>
        {/* Late submission badge */}
        {results?.is_late && (
          <div style={{
            padding: "10px 16px", borderRadius: "10px", marginBottom: "20px",
            background: "var(--danger-bg)", border: "1px solid var(--danger-border)",
            color: "var(--danger-light)", fontSize: "0.9rem", textAlign: "center",
          }}>
            <Icon name="AlertCircle" size={16} style={{ marginRight: "6px", verticalAlign: "middle" }} />
            Submitted after due date
          </div>
        )}

        {/* Score Card */}
        <div style={{ ...cardStyle, textAlign: "center", marginBottom: "30px" }}>
          <Icon name={isPendingReview ? "Clock" : isPartial ? "Clock" : "Award"} size={50} />
          <h2 style={{ fontSize: "1.8rem", fontWeight: 700, marginTop: "15px", marginBottom: "10px" }}>
            {isPendingReview ? "Submitted!" : isPartial ? "Submitted!" : (assessment?.sections ? "Assignment Complete!" : "Assessment Complete!")}
          </h2>
          <p style={{ color: "var(--text-secondary)", marginBottom: "25px" }}>{studentName}</p>

          {isPendingReview ? (
            <div>
              <div style={{
                padding: "16px 20px", borderRadius: "10px",
                background: "var(--glass-bg)", border: "1px solid var(--input-border)",
                color: "var(--accent-light)", fontSize: "1rem",
              }}>
                <Icon name="Clock" size={20} style={{ marginRight: "8px", verticalAlign: "middle" }} />
                {results.message || "Your teacher will review and share your results."}
              </div>
              <p style={{ color: "var(--text-muted)", fontSize: "0.85rem", marginTop: "15px" }}>
                You will see your score once your teacher has reviewed your submission.
              </p>
            </div>
          ) : isPartial ? (
            <div>
              <div style={{ fontSize: "1.5rem", fontWeight: 700, color: "var(--accent-primary)", marginBottom: "10px" }}>
                {results.mc_correct}/{results.mc_total} multiple choice correct
              </div>
              <div style={{
                padding: "12px 16px", borderRadius: "10px",
                background: "var(--warning-bg)", border: "1px solid var(--warning-border)",
                color: "var(--warning)", fontSize: "0.95rem", marginTop: "15px",
              }}>
                <Icon name="Clock" size={16} style={{ marginRight: "8px", verticalAlign: "middle" }} />
                {results.written_pending} written response{results.written_pending !== 1 ? "s" : ""} pending teacher review
              </div>
              <p style={{ color: "var(--text-muted)", fontSize: "0.85rem", marginTop: "12px" }}>
                Your teacher will review your written responses and you'll see your full score soon.
              </p>
            </div>
          ) : (
            <div>
              <div style={{ fontSize: "4rem", fontWeight: 800, color: gradeColor, marginBottom: "10px" }}>
                {percentage}%
              </div>
              <div style={{ fontSize: "1.2rem", color: "var(--text-secondary)" }}>
                {results?.score}/{results?.total_points} points
              </div>
              {results?.feedback_summary && (
                <div style={{
                  marginTop: "25px", padding: "15px",
                  background: "var(--glass-bg)", borderRadius: "10px", fontStyle: "italic",
                }}>
                  {results.feedback_summary}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Detailed Results */}
        {results?.questions && (
          <div>
            <h3 style={{ fontSize: "1.3rem", fontWeight: 700, marginBottom: "20px" }}>
              Question Review
            </h3>
            {results.questions.map((q, idx) => (
              <div
                key={idx}
                style={{
                  ...cardStyle,
                  marginBottom: "15px",
                  borderLeft: "4px solid " + (q.is_correct ? "var(--success)" : "var(--danger)"),
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "10px" }}>
                  <span style={{ fontWeight: 600 }}>
                    {q.number}. {q.question}
                  </span>
                  <span
                    style={{
                      padding: "4px 10px",
                      borderRadius: "12px",
                      fontSize: "0.85rem",
                      fontWeight: 600,
                      background: q.is_correct ? "var(--success-bg)" : "var(--danger-bg)",
                      color: q.is_correct ? "var(--success)" : "var(--danger)",
                    }}
                  >
                    {q.points_earned}/{q.points_possible} pts
                  </span>
                </div>

                <div style={{ fontSize: "0.9rem", color: "var(--text-secondary)", marginBottom: "8px" }}>
                  <strong>Your answer:</strong>{" "}
                  {q.student_answer_display || q.student_answer || "(no answer)"}
                </div>

                {!q.is_correct && q.correct_answer && (
                  <div style={{ fontSize: "0.9rem", color: "var(--success)", marginBottom: "8px" }}>
                    <strong>Correct answer:</strong> {q.correct_answer}
                  </div>
                )}

                {q.feedback && (
                  <div
                    style={{
                      marginTop: "10px",
                      padding: "10px",
                      background: "var(--glass-bg)",
                      borderRadius: "6px",
                      fontSize: "0.9rem",
                    }}
                  >
                    {q.feedback}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Done Button */}
        <div style={{ textAlign: "center", padding: "30px 0" }}>
          <button
            onClick={() => onBack ? onBack() : (window.location.href = "/join")}
            style={{ ...buttonStyle, maxWidth: "300px", margin: "0 auto" }}
          >
            {onBack ? "Back to Dashboard" : (assessment?.settings?.content_type === 'assignment' ? "Take Another Assignment" : "Take Another Assessment")}
          </button>
        </div>
      </div>
    </div>
  );
}
