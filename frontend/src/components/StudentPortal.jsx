/**
 * Student Portal Component
 * Allows students to join assessments via code and take them.
 */
import React, { useState, useEffect } from "react";
import * as api from "../services/api";
import MatchingCards from "./MatchingCards";
import FlashcardView from "./FlashcardView";
import MindMapView from "./MindMapView";
import QuestionPlayer from "./QuestionPlayer";
import Icon from "./Icon";

export default function StudentPortal({
  preloadedAssessment = null,
  preloadedStudentName = "",
  contentId = null,
  studentToken = null,
  onBack = null,
  preloadedSettings = null,
} = {}) {
  // URL path parsing (join-code path only)
  const pathParts = window.location.pathname.split("/");
  const urlCode = pathParts[2] || ""; // /join/ABC123 -> ABC123

  // Determine initial state based on whether content was preloaded (Clever/class path)
  const isPreloaded = !!preloadedAssessment;
  const [stage, setStage] = useState(
    isPreloaded ? "assessment" : (urlCode ? "loading" : "join")
  );
  const [joinCode, setJoinCode] = useState(urlCode.toUpperCase());
  const [studentName, setStudentName] = useState(preloadedStudentName || "");
  const [assessment, setAssessment] = useState(preloadedAssessment ? {
    ...preloadedAssessment,
    settings: preloadedSettings || preloadedAssessment.settings || {},
    student_accommodations: (preloadedSettings || {}).student_accommodations || {},
  } : null);
  const [answers, setAnswers] = useState({});
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [startTime, setStartTime] = useState(null);
  const [results, setResults] = useState(null);
  const [studentAccommodation, setStudentAccommodation] = useState(null);
  const [deliveryAccommodations, setDeliveryAccommodations] = useState([]);
  const [lightMode, setLightMode] = useState(false);

  // Delivery accommodation preset IDs for conditional checks
  var DELIVERY_PRESET_IDS = ["extended_time_1_5x", "extended_time_2x", "extended_time_unlimited",
    "large_text", "read_aloud", "reduced_distractions"];

  // Load assessment if URL has code (join-code path)
  useEffect(() => {
    if (urlCode && stage === "loading") {
      loadAssessment(urlCode);
    }
  }, [urlCode]);

  // Start timer and detect accommodations for preloaded (Clever/class) path
  useEffect(() => {
    if (isPreloaded && !startTime) {
      setStartTime(Date.now());
    }
    // Auto-detect accommodations for Clever students (they skip handleStartAssessment)
    if (isPreloaded && preloadedStudentName && assessment && assessment.student_accommodations) {
      var normalizedName = preloadedStudentName.trim().toLowerCase();
      var matchedAccom = null;
      Object.entries(assessment.student_accommodations).forEach(function(entry) {
        if (entry[0].trim().toLowerCase() === normalizedName) {
          matchedAccom = entry[1];
        }
      });
      if (matchedAccom) {
        setStudentAccommodation(matchedAccom);
        var deliveryPresets = (matchedAccom.presets || []).filter(function(p) {
          return DELIVERY_PRESET_IDS.indexOf(p) !== -1;
        });
        setDeliveryAccommodations(deliveryPresets);
      }
    }
  }, [isPreloaded]);

  const loadAssessment = async (code) => {
    setLoading(true);
    setError("");
    try {
      const data = await api.getStudentAssessment(code);
      if (data.error) {
        setError(data.error);
        setStage("join");
      } else if (data.content_type && ["study_guide", "flashcards", "slide_deck", "mind_map", "audio_overview", "video_overview", "infographic", "data_table"].indexOf(data.content_type) !== -1) {
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

    // Check if student has accommodations (case-insensitive name match)
    if (assessment?.student_accommodations) {
      var normalizedAccomName = studentName.trim().toLowerCase();
      var matchedAccom = null;
      Object.entries(assessment.student_accommodations).forEach(function(entry) {
        if (entry[0].trim().toLowerCase() === normalizedAccomName) {
          matchedAccom = entry[1];
        }
      });
      if (matchedAccom) {
        setStudentAccommodation(matchedAccom);
        var deliveryPresets = (matchedAccom.presets || []).filter(function(p) {
          return DELIVERY_PRESET_IDS.indexOf(p) !== -1;
        });
        setDeliveryAccommodations(deliveryPresets);
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
      var data;
      if (isPreloaded && contentId && studentToken) {
        // Class-based submission (Clever/authenticated student)
        var response = await fetch("/api/student/submit/" + contentId, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Student-Token": studentToken,
          },
          body: JSON.stringify({ answers: answers, time_taken_seconds: timeTaken }),
        });
        data = await response.json();
      } else {
        // Join-code submission (anonymous)
        data = await api.submitStudentAssessment(
          joinCode,
          studentName,
          answers,
          timeTaken
        );
      }
      if (data.error) {
        setError(data.error);
        if (data.previous_results) {
          setResults(data.previous_results);
          setStage("results");
        }
      } else {
        if (data.grading_status === "pending_review") {
          setResults({
            grading_status: "pending_review",
            message: data.message,
            is_late: data.is_late,
          });
        } else if (data.grading_status === "partial") {
          setResults({
            grading_status: "partial",
            mc_correct: data.mc_correct,
            mc_total: data.mc_total,
            written_pending: data.written_pending,
            message: data.message,
            questions: data.detailed_results,
            is_late: data.is_late,
          });
        } else {
          setResults({
            score: data.score,
            total_points: data.total_points,
            percentage: data.percentage,
            feedback_summary: data.feedback_summary,
            questions: data.detailed_results,
            is_late: data.is_late,
          });
        }
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

  // Styles — light/dark mode
  const containerStyle = lightMode ? {
    minHeight: "100vh",
    background: "linear-gradient(135deg, #f8fafc 0%, #e2e8f0 50%, #f8fafc 100%)",
    color: "#1e293b",
    fontFamily: "system-ui, -apple-system, sans-serif",
  } : {
    minHeight: "100vh",
    background: "linear-gradient(135deg, #0f0f23 0%, #1a1a3e 50%, #0f0f23 100%)",
    color: "white",
    fontFamily: "system-ui, -apple-system, sans-serif",
  };

  const cardStyle = lightMode ? {
    background: "white",
    border: "1px solid #e2e8f0",
    borderRadius: "16px",
    padding: "30px",
    maxWidth: "600px",
    width: "100%",
    margin: "0 auto",
    boxShadow: "0 1px 3px rgba(0,0,0,0.1)",
  } : {
    background: "rgba(255, 255, 255, 0.05)",
    backdropFilter: "blur(10px)",
    border: "1px solid rgba(255, 255, 255, 0.1)",
    borderRadius: "16px",
    padding: "30px",
    maxWidth: "600px",
    width: "100%",
    margin: "0 auto",
  };

  var subtextColor = lightMode ? "#64748b" : "rgba(255,255,255,0.7)";
  var borderColor = lightMode ? "#e2e8f0" : "rgba(255,255,255,0.2)";
  var errorBg = lightMode ? "rgba(239, 68, 68, 0.1)" : "rgba(239, 68, 68, 0.2)";
  var errorBorder = lightMode ? "#fca5a5" : "#ef4444";
  var errorText = lightMode ? "#dc2626" : "#fca5a5";
  var inputBg = lightMode ? "white" : "rgba(0, 0, 0, 0.3)";
  var inputColor = lightMode ? "#1e293b" : "white";

  const inputStyle = {
    width: "100%",
    padding: "15px 20px",
    fontSize: "1.2rem",
    border: "2px solid " + borderColor,
    borderRadius: "10px",
    background: inputBg,
    color: inputColor,
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

  // Theme toggle button
  var themeToggle = (
    <button
      onClick={function() { setLightMode(!lightMode); }}
      style={{
        position: "fixed", top: "12px", right: "12px", zIndex: 200,
        background: lightMode ? "rgba(0,0,0,0.08)" : "rgba(255,255,255,0.1)",
        border: "none", borderRadius: "8px", padding: "8px",
        cursor: "pointer", color: lightMode ? "#64748b" : "rgba(255,255,255,0.6)",
      }}
      title={lightMode ? "Switch to dark mode" : "Switch to light mode"}
    >
      <Icon name={lightMode ? "Moon" : "Sun"} size={18} />
    </button>
  );

  // ============ JOIN SCREEN ============
  if (stage === "join" || stage === "loading") {
    return (
      <div style={containerStyle}>
        {themeToggle}
        <div style={{ padding: "40px 20px", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", minHeight: "100vh" }}>
          <div style={{ textAlign: "center", marginBottom: "40px" }}>
            <h1 style={{ fontSize: "2.5rem", fontWeight: 800, marginBottom: "10px", display: "flex", alignItems: "center", justifyContent: "center", gap: "12px" }}>
              <Icon name="FileText" size={36} /> Graider
            </h1>
            <p style={{ color: subtextColor, fontSize: "1.1rem" }}>
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
                    Join <Icon name="ArrowRight" />
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
        {themeToggle}
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
                {assessment?.total_points ? <span>{assessment.total_points} points</span> : null}
                {assessment?.total_points && assessment?.settings?.content_type !== 'assignment' && assessment?.time_estimate ? <span>{String.fromCharCode(8226)}</span> : null}
                {assessment?.settings?.content_type !== 'assignment' && assessment?.time_estimate ? <span>{assessment.time_estimate}</span> : null}
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
              {(assessment?.settings?.content_type === 'assignment' || assessment?.type === 'assignment' || assessment?.type === 'project' || assessment?.type === 'essay') ? "Start Assignment" : "Start Assessment"} <Icon name="ArrowRight" />
            </button>
          </div>
        </div>
      </div>
    );
  }

  // ============ ASSESSMENT SCREEN ============
  if (stage === "assessment") {
    // Compute effective time limit with extended time accommodation
    var effectiveTimeLimit = assessment?.settings?.time_limit_minutes || null;
    if (effectiveTimeLimit && deliveryAccommodations.length > 0) {
      if (deliveryAccommodations.indexOf("extended_time_unlimited") !== -1) {
        effectiveTimeLimit = null;
      } else if (deliveryAccommodations.indexOf("extended_time_2x") !== -1) {
        effectiveTimeLimit = Math.round(effectiveTimeLimit * 2);
      } else if (deliveryAccommodations.indexOf("extended_time_1_5x") !== -1) {
        effectiveTimeLimit = Math.round(effectiveTimeLimit * 1.5);
      }
    }

    return (
      <div style={containerStyle}>
        {themeToggle}
        <QuestionPlayer
          sections={assessment?.sections}
          contentType={assessment?.settings?.content_type || "assessment"}
          settings={assessment?.settings || {}}
          accommodations={deliveryAccommodations}
          effectiveTimeLimit={effectiveTimeLimit}
          studentName={studentName}
          title={assessment?.title}
          answers={answers}
          onAnswer={setAnswer}
          onSubmit={handleSubmit}
          loading={loading}
          assessment={assessment}
          studentAccommodation={studentAccommodation}
          lightMode={lightMode}
        />
      </div>
    );
  }

  // ============ RESULTS SCREEN ============
  if (stage === "results") {
    var isPendingReview = results && results.grading_status === "pending_review";
    var isPartial = results && results.grading_status === "partial";
    var percentage = results?.percentage || 0;
    var gradeColor = percentage >= 90 ? "#22c55e" : percentage >= 70 ? "#f59e0b" : "#ef4444";

    return (
      <div style={containerStyle}>
        {themeToggle}
        <div style={{ padding: "40px 20px", maxWidth: "700px", margin: "0 auto" }}>
          {/* Late submission badge */}
          {results?.is_late && (
            <div style={{
              padding: "10px 16px", borderRadius: "10px", marginBottom: "20px",
              background: "rgba(239,68,68,0.15)", border: "1px solid rgba(239,68,68,0.3)",
              color: "#fca5a5", fontSize: "0.9rem", textAlign: "center",
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
            <p style={{ color: "rgba(255,255,255,0.7)", marginBottom: "25px" }}>{studentName}</p>

            {isPendingReview ? (
              <div>
                <div style={{
                  padding: "16px 20px", borderRadius: "10px",
                  background: "rgba(99,102,241,0.15)", border: "1px solid rgba(99,102,241,0.3)",
                  color: "#a5b4fc", fontSize: "1rem",
                }}>
                  <Icon name="Clock" size={20} style={{ marginRight: "8px", verticalAlign: "middle" }} />
                  {results.message || "Your teacher will review and share your results."}
                </div>
                <p style={{ color: "rgba(255,255,255,0.5)", fontSize: "0.85rem", marginTop: "15px" }}>
                  You will see your score once your teacher has reviewed your submission.
                </p>
              </div>
            ) : isPartial ? (
              <div>
                <div style={{ fontSize: "1.5rem", fontWeight: 700, color: "#6366f1", marginBottom: "10px" }}>
                  {results.mc_correct}/{results.mc_total} multiple choice correct
                </div>
                <div style={{
                  padding: "12px 16px", borderRadius: "10px",
                  background: "rgba(245,158,11,0.15)", border: "1px solid rgba(245,158,11,0.3)",
                  color: "#f59e0b", fontSize: "0.95rem", marginTop: "15px",
                }}>
                  <Icon name="Clock" size={16} style={{ marginRight: "8px", verticalAlign: "middle" }} />
                  {results.written_pending} written response{results.written_pending !== 1 ? "s" : ""} pending teacher review
                </div>
                <p style={{ color: "rgba(255,255,255,0.5)", fontSize: "0.85rem", marginTop: "12px" }}>
                  Your teacher will review your written responses and you'll see your full score soon.
                </p>
              </div>
            ) : (
              <div>
                <div style={{ fontSize: "4rem", fontWeight: 800, color: gradeColor, marginBottom: "10px" }}>
                  {percentage}%
                </div>
                <div style={{ fontSize: "1.2rem", color: "rgba(255,255,255,0.7)" }}>
                  {results?.score}/{results?.total_points} points
                </div>
                {results?.feedback_summary && (
                  <div style={{
                    marginTop: "25px", padding: "15px",
                    background: "rgba(255,255,255,0.05)", borderRadius: "10px", fontStyle: "italic",
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
