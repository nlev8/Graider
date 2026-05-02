/**
 * Authenticity / AI-detection helpers used by the Results tab and other
 * surfaces that render AI / plagiarism flags on graded submissions.
 *
 * Extracted from App.jsx (2026-05-02) where the three functions were
 * defined at module scope and then prop-drilled into ResultsTab. They
 * are now imported directly by their consumers.
 *
 * - getAuthenticityStatus(result) -> { ai, plag, overallStatus, isNewFormat }
 *     Normalizes the two historic shapes (old `authenticity_flag` vs new
 *     `ai_detection` / `plagiarism_detection`) into one summary object.
 * - getAIFlagColor(flag) -> { bg, text }
 * - getPlagFlagColor(flag) -> { bg, text }
 */

export const getAuthenticityStatus = (result) => {
  // New format with separate AI and plagiarism detection
  if (result.ai_detection || result.plagiarism_detection) {
    const ai = result.ai_detection || {
      flag: "none",
      confidence: 0,
      reason: "",
    };
    const plag = result.plagiarism_detection || { flag: "none", reason: "" };

    // Determine overall status for summary views
    const aiConcern = ai.flag === "likely" || ai.flag === "possible";
    const plagConcern = plag.flag === "likely" || plag.flag === "possible";

    let overallStatus = "clean";
    if (ai.flag === "likely" || plag.flag === "likely") {
      overallStatus = "flagged";
    } else if (aiConcern || plagConcern) {
      overallStatus = "review";
    }

    return { ai, plag, overallStatus, isNewFormat: true };
  }

  // Backward compatibility with old format
  const flag = result.authenticity_flag || "clean";
  const reason = result.authenticity_reason || "";
  return {
    ai: {
      flag:
        flag === "flagged" ? "likely" : flag === "review" ? "possible" : "none",
      confidence: flag === "flagged" ? 80 : flag === "review" ? 50 : 0,
      reason: flag !== "clean" ? reason : "",
    },
    plag: { flag: "none", reason: "" },
    overallStatus: flag,
    isNewFormat: false,
  };
};

export const getAIFlagColor = (flag) => {
  switch (flag) {
    case "likely":
      return { bg: "rgba(248,113,113,0.2)", text: "#f87171" };
    case "possible":
      return { bg: "rgba(251,191,36,0.2)", text: "#fbbf24" };
    case "unlikely":
      return { bg: "rgba(96,165,250,0.2)", text: "#60a5fa" };
    default:
      return { bg: "rgba(74,222,128,0.2)", text: "#4ade80" };
  }
};

export const getPlagFlagColor = (flag) => {
  switch (flag) {
    case "likely":
      return { bg: "rgba(248,113,113,0.2)", text: "#f87171" };
    case "possible":
      return { bg: "rgba(251,191,36,0.2)", text: "#fbbf24" };
    default:
      return { bg: "rgba(74,222,128,0.2)", text: "#4ade80" };
  }
};
