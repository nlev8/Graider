/**
 * Student Portal Component
 * Allows students to join assessments via code and take them.
 */
import React, { useState, useEffect } from "react";
import * as api from "../services/api";
import MatchingCards from "./MatchingCards";
import FlashcardView from "./FlashcardView";
import MindMapView from "./MindMapView";

// Simple icon component for student portal
const Icon = ({ name, size = 20, style = {} }) => {
  const icons = {
    ArrowRight: "→",
    Check: "✓",
    X: "✕",
    Clock: "⏱",
    Award: "🏆",
    AlertCircle: "⚠",
    Loader: "◌",
    BookOpen: "📖",
    User: "👤",
    Send: "📤",
  };
  return (
    <span style={{ fontSize: size, ...style }}>{icons[name] || "•"}</span>
  );
};

export default function StudentPortal() {
  // URL path parsing
  const pathParts = window.location.pathname.split("/");
  const urlCode = pathParts[2] || ""; // /join/ABC123 -> ABC123

  const [stage, setStage] = useState(urlCode ? "loading" : "join"); // join, loading, assessment, results
  const [joinCode, setJoinCode] = useState(urlCode.toUpperCase());
  const [studentName, setStudentName] = useState("");
  const [assessment, setAssessment] = useState(null);
  const [answers, setAnswers] = useState({});
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [startTime, setStartTime] = useState(null);
  const [results, setResults] = useState(null);
  const [studentAccommodation, setStudentAccommodation] = useState(null);

  // Load assessment if URL has code
  useEffect(() => {
    if (urlCode && stage === "loading") {
      loadAssessment(urlCode);
    }
  }, [urlCode]);

  const loadAssessment = async (code) => {
    setLoading(true);
    setError("");
    try {
      const data = await api.getStudentAssessment(code);
      if (data.error) {
        setError(data.error);
        setStage("join");
      } else if (data.content_type && data.content_type !== "assessment") {
        setAssessment(data);
        setStage("material");
      } else {
        setAssessment(data);
        setStage("name");
      }
    } catch (e) {
      setError("Could not load assessment. Check your code and try again.");
      setStage("join");
    } finally {
      setLoading(false);
    }
  };

  const handleJoin = async (e) => {
    e.preventDefault();
    if (!joinCode.trim()) {
      setError("Please enter a join code");
      return;
    }
    await loadAssessment(joinCode.toUpperCase());
  };

  const handleStartAssessment = () => {
    if (!studentName.trim()) {
      setError("Please enter your name");
      return;
    }

    // Check if this is a restricted assessment (makeup exam)
    const settings = assessment?.settings || {};
    const isMakeup = settings.is_makeup || false;
    const restrictedStudents = settings.restricted_students || [];

    if (isMakeup && restrictedStudents.length > 0) {
      const normalizedName = studentName.trim().toLowerCase();
      const isAllowed = restrictedStudents.some(
        (s) => s.toLowerCase() === normalizedName
      );
      if (!isAllowed) {
        setError("This assessment is restricted to specific students. If you believe this is an error, please contact your teacher.");
        return;
      }
    }

    // Check if student has accommodations
    if (assessment?.student_accommodations) {
      const normalizedName = studentName.trim();
      const accommodation = assessment.student_accommodations[normalizedName];
      if (accommodation) {
        setStudentAccommodation(accommodation);
      }
    }

    setStartTime(Date.now());
    setStage("assessment");
  };

  const handleSubmit = async () => {
    setLoading(true);
    setError("");
    const timeTaken = Math.round((Date.now() - startTime) / 1000);
    try {
      const data = await api.submitStudentAssessment(
        joinCode,
        studentName,
        answers,
        timeTaken
      );
      if (data.error) {
        setError(data.error);
        if (data.previous_results) {
          setResults(data.previous_results);
          setStage("results");
        }
      } else {
        setResults({
          score: data.score,
          total_points: data.total_points,
          percentage: data.percentage,
          feedback_summary: data.feedback_summary,
          questions: data.detailed_results,
        });
        setStage("results");
      }
    } catch (e) {
      setError("Failed to submit. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const setAnswer = (key, value) => {
    setAnswers((prev) => ({ ...prev, [key]: value }));
  };

  // Styles
  const containerStyle = {
    minHeight: "100vh",
    background: "linear-gradient(135deg, #0f0f23 0%, #1a1a3e 50%, #0f0f23 100%)",
    color: "white",
    fontFamily: "system-ui, -apple-system, sans-serif",
  };

  const cardStyle = {
    background: "rgba(255, 255, 255, 0.05)",
    backdropFilter: "blur(10px)",
    border: "1px solid rgba(255, 255, 255, 0.1)",
    borderRadius: "16px",
    padding: "30px",
    maxWidth: "600px",
    width: "100%",
    margin: "0 auto",
  };

  const inputStyle = {
    width: "100%",
    padding: "15px 20px",
    fontSize: "1.2rem",
    border: "2px solid rgba(255, 255, 255, 0.2)",
    borderRadius: "10px",
    background: "rgba(0, 0, 0, 0.3)",
    color: "white",
    textAlign: "center",
    letterSpacing: "0.1em",
    textTransform: "uppercase",
    outline: "none",
  };

  const buttonStyle = {
    padding: "15px 30px",
    fontSize: "1.1rem",
    fontWeight: 600,
    border: "none",
    borderRadius: "10px",
    cursor: "pointer",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    gap: "10px",
    width: "100%",
    background: "linear-gradient(135deg, #8b5cf6, #6366f1)",
    color: "white",
  };

  // ============ JOIN SCREEN ============
  if (stage === "join" || stage === "loading") {
    return (
      <div style={containerStyle}>
        <div style={{ padding: "40px 20px", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", minHeight: "100vh" }}>
          <div style={{ textAlign: "center", marginBottom: "40px" }}>
            <h1 style={{ fontSize: "2.5rem", fontWeight: 800, marginBottom: "10px" }}>
              📝 Graider
            </h1>
            <p style={{ color: "rgba(255,255,255,0.7)", fontSize: "1.1rem" }}>
              Enter your join code to get started
            </p>
          </div>

          <div style={cardStyle}>
            <form onSubmit={handleJoin}>
              <div style={{ marginBottom: "20px" }}>
                <label style={{ display: "block", marginBottom: "10px", fontWeight: 600 }}>
                  Join Code
                </label>
                <input
                  type="text"
                  value={joinCode}
                  onChange={(e) => setJoinCode(e.target.value.toUpperCase())}
                  placeholder="ABC123"
                  maxLength={6}
                  style={inputStyle}
                  autoFocus
                />
              </div>

              {error && (
                <div style={{ background: "rgba(239, 68, 68, 0.2)", border: "1px solid #ef4444", borderRadius: "8px", padding: "12px", marginBottom: "20px", color: "#fca5a5" }}>
                  <Icon name="AlertCircle" size={16} /> {error}
                </div>
              )}

              <button type="submit" disabled={loading} style={buttonStyle}>
                {loading ? (
                  <>
                    <Icon name="Loader" /> Loading...
                  </>
                ) : (
                  <>
                    Join Assessment <Icon name="ArrowRight" />
                  </>
                )}
              </button>
            </form>
          </div>
        </div>
      </div>
    );
  }

  // ============ NAME ENTRY SCREEN ============
  if (stage === "name") {
    return (
      <div style={containerStyle}>
        <div style={{ padding: "40px 20px", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", minHeight: "100vh" }}>
          <div style={cardStyle}>
            <div style={{ textAlign: "center", marginBottom: "30px" }}>
              <Icon name="BookOpen" size={40} />
              <h2 style={{ fontSize: "1.5rem", fontWeight: 700, marginTop: "15px", marginBottom: "10px" }}>
                {assessment?.title}
              </h2>
              <p style={{ color: "rgba(255,255,255,0.7)" }}>
                By {assessment?.teacher}
              </p>
              <div style={{ display: "flex", justifyContent: "center", gap: "20px", marginTop: "15px", fontSize: "0.9rem", color: "rgba(255,255,255,0.6)" }}>
                <span>{assessment?.total_points} points</span>
                <span>•</span>
                <span>{assessment?.time_estimate || "~15 min"}</span>
              </div>
            </div>

            {/* Restricted Assessment Notice */}
            {assessment?.settings?.is_makeup && (
              <div style={{ background: "rgba(245, 158, 11, 0.15)", border: "1px solid rgba(245, 158, 11, 0.5)", borderRadius: "8px", padding: "12px 15px", marginBottom: "20px" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "10px", color: "#fbbf24" }}>
                  <Icon name="AlertCircle" size={18} />
                  <strong>Makeup Exam</strong>
                </div>
                <p style={{ fontSize: "0.9rem", color: "rgba(255,255,255,0.7)", marginTop: "5px" }}>
                  This assessment is only available to specific students. Please enter your full name exactly as it appears on your roster.
                </p>
              </div>
            )}

            {assessment?.instructions && (
              <div style={{ background: "rgba(99, 102, 241, 0.1)", border: "1px solid rgba(99, 102, 241, 0.3)", borderRadius: "8px", padding: "15px", marginBottom: "25px" }}>
                <strong>Instructions:</strong> {assessment.instructions}
              </div>
            )}

            <div style={{ marginBottom: "20px" }}>
              <label style={{ display: "block", marginBottom: "10px", fontWeight: 600 }}>
                <Icon name="User" size={16} /> Your Name
              </label>
              <input
                type="text"
                value={studentName}
                onChange={(e) => setStudentName(e.target.value)}
                placeholder="Enter your full name"
                style={{ ...inputStyle, textTransform: "none", textAlign: "left", letterSpacing: "normal" }}
                autoFocus
              />
            </div>

            {error && (
              <div style={{ background: "rgba(239, 68, 68, 0.2)", border: "1px solid #ef4444", borderRadius: "8px", padding: "12px", marginBottom: "20px", color: "#fca5a5" }}>
                <Icon name="AlertCircle" size={16} /> {error}
              </div>
            )}

            <button onClick={handleStartAssessment} style={buttonStyle}>
              Start Assessment <Icon name="ArrowRight" />
            </button>
          </div>
        </div>
      </div>
    );
  }

  // ============ ASSESSMENT SCREEN ============
  if (stage === "assessment") {
    const totalQuestions = assessment?.sections?.reduce((sum, s) => sum + (s.questions?.length || 0), 0) || 0;
    const answeredCount = Object.keys(answers).filter((k) => answers[k] !== undefined && answers[k] !== "").length;

    return (
      <div style={containerStyle}>
        {/* Header */}
        <div style={{ position: "sticky", top: 0, background: "rgba(15, 15, 35, 0.95)", borderBottom: "1px solid rgba(255,255,255,0.1)", padding: "15px 20px", zIndex: 100 }}>
          <div style={{ maxWidth: "800px", margin: "0 auto", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div>
              <h1 style={{ fontSize: "1.2rem", fontWeight: 700, marginBottom: "4px" }}>{assessment?.title}</h1>
              <span style={{ fontSize: "0.9rem", color: "rgba(255,255,255,0.6)" }}>{studentName}</span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: "20px" }}>
              <span style={{ fontSize: "0.9rem", color: "rgba(255,255,255,0.7)" }}>
                {answeredCount}/{totalQuestions} answered
              </span>
              <button
                onClick={handleSubmit}
                disabled={loading}
                style={{
                  ...buttonStyle,
                  width: "auto",
                  padding: "10px 20px",
                  fontSize: "1rem",
                  background: answeredCount === totalQuestions ? "linear-gradient(135deg, #22c55e, #16a34a)" : "linear-gradient(135deg, #8b5cf6, #6366f1)",
                }}
              >
                {loading ? "Submitting..." : "Submit"}
                <Icon name="Send" />
              </button>
            </div>
          </div>
        </div>

        {/* Questions */}
        <div style={{ maxWidth: "800px", margin: "0 auto", padding: "30px 20px" }}>
          {/* Accommodations Notice */}
          {studentAccommodation && (
            <div style={{ background: "rgba(59, 130, 246, 0.15)", border: "1px solid rgba(59, 130, 246, 0.4)", borderRadius: "10px", padding: "15px 20px", marginBottom: "25px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "10px" }}>
                <span style={{ fontSize: "1.2rem" }}>📋</span>
                <strong style={{ color: "#60a5fa" }}>Your Accommodations</strong>
              </div>
              {studentAccommodation.presets && studentAccommodation.presets.length > 0 && (
                <ul style={{ margin: "0 0 10px 20px", padding: 0, color: "rgba(255,255,255,0.8)", fontSize: "0.95rem" }}>
                  {studentAccommodation.presets.map((preset, idx) => (
                    <li key={idx} style={{ marginBottom: "5px" }}>{preset}</li>
                  ))}
                </ul>
              )}
              {studentAccommodation.custom_notes && (
                <p style={{ margin: 0, color: "rgba(255,255,255,0.7)", fontSize: "0.9rem", fontStyle: "italic" }}>
                  {studentAccommodation.custom_notes}
                </p>
              )}
            </div>
          )}

          {error && (
            <div style={{ background: "rgba(239, 68, 68, 0.2)", border: "1px solid #ef4444", borderRadius: "8px", padding: "12px", marginBottom: "20px", color: "#fca5a5" }}>
              {error}
            </div>
          )}

          {assessment?.sections?.map((section, sIdx) => (
            <div key={sIdx} style={{ marginBottom: "40px" }}>
              <h2 style={{ fontSize: "1.3rem", fontWeight: 700, marginBottom: "10px", color: "#8b5cf6" }}>
                {section.name}
              </h2>
              {section.instructions && (
                <p style={{ color: "rgba(255,255,255,0.6)", marginBottom: "20px", fontStyle: "italic" }}>
                  {section.instructions}
                </p>
              )}

              {section.questions?.map((q, qIdx) => {
                const answerKey = `${sIdx}-${qIdx}`;
                const currentAnswer = answers[answerKey];

                return (
                  <div
                    key={qIdx}
                    style={{
                      ...cardStyle,
                      marginBottom: "20px",
                      borderLeft: currentAnswer ? "4px solid #22c55e" : "4px solid rgba(255,255,255,0.2)",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "15px" }}>
                      <span style={{ fontWeight: 700, fontSize: "1.1rem" }}>
                        {q.number}. {q.question}
                      </span>
                      <span style={{ color: "rgba(255,255,255,0.5)", fontSize: "0.9rem" }}>
                        {q.points} pt{q.points > 1 ? "s" : ""}
                      </span>
                    </div>

                    {/* Multiple Choice */}
                    {q.options && q.options.length > 0 && (
                      <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                        {q.options.map((opt, oIdx) => {
                          const isSelected = currentAnswer === oIdx;
                          return (
                            <label
                              key={oIdx}
                              onClick={() => setAnswer(answerKey, oIdx)}
                              style={{
                                display: "flex",
                                alignItems: "center",
                                gap: "12px",
                                padding: "12px 15px",
                                borderRadius: "8px",
                                cursor: "pointer",
                                background: isSelected ? "rgba(139, 92, 246, 0.3)" : "rgba(255,255,255,0.05)",
                                border: isSelected ? "2px solid #8b5cf6" : "2px solid transparent",
                                transition: "all 0.15s ease",
                              }}
                            >
                              <span
                                style={{
                                  width: "22px",
                                  height: "22px",
                                  borderRadius: "50%",
                                  border: isSelected ? "6px solid #8b5cf6" : "2px solid rgba(255,255,255,0.4)",
                                  background: isSelected ? "white" : "transparent",
                                  flexShrink: 0,
                                }}
                              />
                              <span>{opt}</span>
                            </label>
                          );
                        })}
                      </div>
                    )}

                    {/* True/False */}
                    {q.type === "true_false" && (
                      <div style={{ display: "flex", gap: "15px" }}>
                        {["True", "False"].map((tf) => {
                          const isSelected = currentAnswer === tf;
                          return (
                            <label
                              key={tf}
                              onClick={() => setAnswer(answerKey, tf)}
                              style={{
                                flex: 1,
                                display: "flex",
                                alignItems: "center",
                                justifyContent: "center",
                                gap: "10px",
                                padding: "15px",
                                borderRadius: "8px",
                                cursor: "pointer",
                                background: isSelected
                                  ? tf === "True"
                                    ? "rgba(34, 197, 94, 0.3)"
                                    : "rgba(239, 68, 68, 0.3)"
                                  : "rgba(255,255,255,0.05)",
                                border: isSelected
                                  ? `2px solid ${tf === "True" ? "#22c55e" : "#ef4444"}`
                                  : "2px solid transparent",
                                fontWeight: 600,
                              }}
                            >
                              {tf}
                            </label>
                          );
                        })}
                      </div>
                    )}

                    {/* Matching - interactive card game */}
                    {(q.type === "matching" || (q.terms && q.terms.length > 0 && q.definitions && q.definitions.length > 0)) && (
                      <MatchingCards
                        terms={q.terms}
                        definitions={q.definitions}
                        onMatch={function(matches) {
                          // Store matches as letter answers for grading compatibility
                          Object.entries(matches).forEach(function(entry) {
                            var tIdx = entry[0];
                            var matchKey = sIdx + "-" + qIdx + "-match-" + tIdx;
                            setAnswer(matchKey, String.fromCharCode(65 + parseInt(tIdx)));
                          });
                        }}
                      />
                    )}

                    {/* Short Answer / Extended Response / Text Input Fallback */}
                    {(q.type === "short_answer" || q.type === "extended_response" ||
                      (!q.options && q.type !== "true_false" && q.type !== "matching" &&
                       !(q.terms && q.terms.length > 0 && q.definitions && q.definitions.length > 0))) && (
                      <textarea
                        value={currentAnswer || ""}
                        onChange={(e) => setAnswer(answerKey, e.target.value)}
                        placeholder={q.type === "extended_response"
                          ? "Write your extended response here. Include evidence and analysis to support your answer..."
                          : "Type your answer here..."}
                        rows={q.type === "extended_response" || (q.points && q.points >= 4) ? 6 : 3}
                        style={{
                          width: "100%",
                          padding: "15px",
                          borderRadius: "8px",
                          border: "1px solid rgba(255,255,255,0.2)",
                          background: "rgba(0,0,0,0.2)",
                          color: "white",
                          fontSize: "1rem",
                          resize: "vertical",
                          lineHeight: 1.6,
                          fontFamily: "inherit",
                        }}
                      />
                    )}
                  </div>
                );
              })}
            </div>
          ))}

          {/* Submit Button at Bottom */}
          <div style={{ textAlign: "center", padding: "20px 0" }}>
            <button
              onClick={handleSubmit}
              disabled={loading}
              style={{
                ...buttonStyle,
                maxWidth: "300px",
                margin: "0 auto",
                background: "linear-gradient(135deg, #22c55e, #16a34a)",
              }}
            >
              {loading ? "Submitting..." : "Submit Assessment"}
              <Icon name="Send" />
            </button>
          </div>
        </div>
      </div>
    );
  }

  // ============ RESULTS SCREEN ============
  if (stage === "results") {
    const percentage = results?.percentage || 0;
    const gradeColor = percentage >= 90 ? "#22c55e" : percentage >= 70 ? "#f59e0b" : "#ef4444";

    return (
      <div style={containerStyle}>
        <div style={{ padding: "40px 20px", maxWidth: "700px", margin: "0 auto" }}>
          {/* Score Card */}
          <div style={{ ...cardStyle, textAlign: "center", marginBottom: "30px" }}>
            <Icon name="Award" size={50} />
            <h2 style={{ fontSize: "1.8rem", fontWeight: 700, marginTop: "15px", marginBottom: "10px" }}>
              Assessment Complete!
            </h2>
            <p style={{ color: "rgba(255,255,255,0.7)", marginBottom: "25px" }}>{studentName}</p>

            <div
              style={{
                fontSize: "4rem",
                fontWeight: 800,
                color: gradeColor,
                marginBottom: "10px",
              }}
            >
              {percentage}%
            </div>
            <div style={{ fontSize: "1.2rem", color: "rgba(255,255,255,0.7)" }}>
              {results?.score}/{results?.total_points} points
            </div>

            {results?.feedback_summary && (
              <div
                style={{
                  marginTop: "25px",
                  padding: "15px",
                  background: "rgba(255,255,255,0.05)",
                  borderRadius: "10px",
                  fontStyle: "italic",
                }}
              >
                {results.feedback_summary}
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
                    borderLeft: `4px solid ${q.is_correct ? "#22c55e" : "#ef4444"}`,
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
                        background: q.is_correct ? "rgba(34, 197, 94, 0.2)" : "rgba(239, 68, 68, 0.2)",
                        color: q.is_correct ? "#22c55e" : "#ef4444",
                      }}
                    >
                      {q.points_earned}/{q.points_possible} pts
                    </span>
                  </div>

                  <div style={{ fontSize: "0.9rem", color: "rgba(255,255,255,0.7)", marginBottom: "8px" }}>
                    <strong>Your answer:</strong>{" "}
                    {q.student_answer_display || q.student_answer || "(no answer)"}
                  </div>

                  {!q.is_correct && q.correct_answer && (
                    <div style={{ fontSize: "0.9rem", color: "#22c55e", marginBottom: "8px" }}>
                      <strong>Correct answer:</strong> {q.correct_answer}
                    </div>
                  )}

                  {q.feedback && (
                    <div
                      style={{
                        marginTop: "10px",
                        padding: "10px",
                        background: "rgba(255,255,255,0.05)",
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
              onClick={() => (window.location.href = "/join")}
              style={{ ...buttonStyle, maxWidth: "300px", margin: "0 auto" }}
            >
              Take Another Assessment
            </button>
          </div>
        </div>
      </div>
    );
  }

  // ============ SHARED MATERIAL SCREEN ============
  if (stage === "material") {
    var ct = assessment?.content_type;
    var materialData = assessment?.data;
    var materialContent = assessment?.content;
    var mediaUrl = assessment?.media_url;
    var isWide = ct === "mind_map" || ct === "infographic";

    var cssVarStyle = {
      padding: "40px 20px", maxWidth: isWide ? "900px" : "600px", margin: "0 auto",
      "--bg-secondary": "rgba(255,255,255,0.05)",
      "--bg-primary": "rgba(0,0,0,0.3)",
      "--border": "rgba(255,255,255,0.15)",
      "--text-primary": "white",
      "--text-secondary": "rgba(255,255,255,0.6)",
      "--primary": "#8b5cf6",
      "--success": "#22c55e",
    };

    return (
      <div style={containerStyle}>
        <div style={cssVarStyle}>
          <div style={{ textAlign: "center", marginBottom: "30px" }}>
            <h1 style={{ fontSize: "1.8rem", fontWeight: 700, marginBottom: "8px" }}>
              {assessment?.title || "Study Material"}
            </h1>
            <p style={{ color: "rgba(255,255,255,0.6)", fontSize: "0.95rem" }}>
              By {assessment?.teacher || "Teacher"}
            </p>
          </div>

          {/* Flashcards */}
          {ct === "flashcards" && materialData && (
            <FlashcardView data={materialData} />
          )}

          {/* Quiz — practice mode, show questions then reveal answers */}
          {ct === "quiz" && materialData && (
            <div>
              {(Array.isArray(materialData) ? materialData : materialData.questions || materialData.cards || []).map(function(item, idx) {
                return (
                  <div key={idx} style={{ background: "rgba(255,255,255,0.05)", padding: "16px 18px", borderRadius: "10px", marginBottom: "10px", border: "1px solid rgba(255,255,255,0.1)" }}>
                    <div style={{ fontWeight: 600, fontSize: "0.95rem", marginBottom: "8px" }}>{"Q" + (idx + 1) + ". " + (item.question || item.text || "")}</div>
                    {item.options && (
                      <div style={{ marginBottom: "8px" }}>
                        {item.options.map(function(opt, oi) {
                          var isCorrect = opt === item.answer || opt === item.correct_answer || oi === item.correct_index;
                          return (<div key={oi} style={{ padding: "4px 0", fontSize: "0.9rem", color: isCorrect ? "#22c55e" : "rgba(255,255,255,0.7)" }}>{String.fromCharCode(65 + oi) + ") " + (typeof opt === "string" ? opt : opt.text || JSON.stringify(opt))}{isCorrect ? " " + String.fromCharCode(10003) : ""}</div>);
                        })}
                      </div>
                    )}
                    {(item.answer || item.correct_answer) && (
                      <div style={{ padding: "8px 12px", borderRadius: "8px", background: "rgba(34, 197, 94, 0.1)", fontSize: "0.85rem", color: "#22c55e" }}><strong>Answer:</strong> {item.answer || item.correct_answer}</div>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          {/* Mind Map */}
          {ct === "mind_map" && materialData && (
            <div style={{ background: "rgba(255,255,255,0.05)", borderRadius: "12px", border: "1px solid rgba(255,255,255,0.1)", padding: "16px", minHeight: "400px" }}>
              <MindMapView data={materialData} />
            </div>
          )}

          {/* Study Guide */}
          {ct === "study_guide" && materialContent && (
            <div style={{ background: "rgba(255,255,255,0.05)", borderRadius: "12px", border: "1px solid rgba(255,255,255,0.1)", padding: "24px", fontSize: "0.95rem", lineHeight: 1.7, whiteSpace: "pre-wrap", color: "rgba(255,255,255,0.85)" }}>
              {materialContent}
            </div>
          )}

          {/* Audio Overview */}
          {ct === "audio_overview" && mediaUrl && (
            <div style={{ background: "rgba(255,255,255,0.05)", borderRadius: "12px", padding: "30px", textAlign: "center" }}>
              <div style={{ fontSize: "3rem", marginBottom: "15px" }}>🎧</div>
              <audio controls style={{ width: "100%" }} src={mediaUrl}>Your browser does not support the audio element.</audio>
            </div>
          )}

          {/* Video Overview */}
          {ct === "video_overview" && mediaUrl && (
            <div style={{ background: "rgba(255,255,255,0.05)", borderRadius: "12px", padding: "12px", textAlign: "center" }}>
              <video controls style={{ width: "100%", maxHeight: "500px", borderRadius: "8px" }} src={mediaUrl}>Your browser does not support the video element.</video>
            </div>
          )}

          {/* Infographic */}
          {ct === "infographic" && mediaUrl && (
            <div style={{ background: "rgba(255,255,255,0.05)", borderRadius: "12px", padding: "12px", textAlign: "center", maxHeight: "600px", overflow: "auto" }}>
              <img src={mediaUrl} alt="Infographic" style={{ maxWidth: "100%", borderRadius: "8px" }} />
            </div>
          )}

          {/* Data Table */}
          {ct === "data_table" && mediaUrl && (
            <div style={{ background: "rgba(255,255,255,0.05)", borderRadius: "12px", padding: "20px", textAlign: "center" }}>
              <p style={{ color: "rgba(255,255,255,0.7)", marginBottom: "15px" }}>Data table available for download:</p>
              <a href={mediaUrl} download style={{ ...buttonStyle, maxWidth: "250px", margin: "0 auto", textDecoration: "none" }}>Download CSV</a>
            </div>
          )}

          {/* Slide Deck */}
          {ct === "slide_deck" && mediaUrl && (
            <div style={{ background: "rgba(255,255,255,0.05)", borderRadius: "12px", padding: "20px", textAlign: "center" }}>
              <div style={{ fontSize: "3rem", marginBottom: "15px" }}>📊</div>
              <p style={{ color: "rgba(255,255,255,0.7)", marginBottom: "15px" }}>Slide deck available for download:</p>
              <a href={mediaUrl} download style={{ ...buttonStyle, maxWidth: "250px", margin: "0 auto", textDecoration: "none" }}>Download Slides</a>
            </div>
          )}

          <div style={{ textAlign: "center", padding: "30px 0" }}>
            <button
              onClick={() => { setStage("join"); setJoinCode(""); setAssessment(null); }}
              style={{ ...buttonStyle, maxWidth: "300px", margin: "0 auto" }}
            >
              Study More
            </button>
          </div>
        </div>
      </div>
    );
  }

  return null;
}
