import React from "react";
import Icon from "../Icon";

// Back / Next / Finish navigation row — extracted verbatim from
// QuestionPlayer.jsx (CQ wave 6 split). data-testids are pinned by the e2e
// student-flow specs; do not change them.
export default function NavigationButtons({
  canGoBack,
  currentIndex,
  totalQuestions,
  isAnswered,
  loading,
  theme,
  goToPrev,
  goToNext,
  handleFinish,
}) {
  var navBtnBorder = theme.navBtnBorder;
  var navBtnColor = theme.navBtnColor;
  var disabledBg = theme.disabledBg;
  var disabledColor = theme.disabledColor;

  return (
    <div style={{
      display: "flex",
      gap: "12px",
      marginTop: "30px",
      width: "100%",
      maxWidth: "600px",
      justifyContent: "center",
    }}>
      {canGoBack && currentIndex > 0 && (
        <button
          onClick={goToPrev}
          data-testid="btn-back"
          style={{
            padding: "14px 28px",
            fontSize: "1.05rem",
            fontWeight: 600,
            border: "2px solid " + navBtnBorder,
            borderRadius: "10px",
            cursor: "pointer",
            background: "transparent",
            color: navBtnColor,
          }}
        >
          <Icon name="ArrowLeft" size={18} /> Back
        </button>
      )}
      {currentIndex < totalQuestions - 1 ? (
        <button
          onClick={goToNext}
          disabled={!isAnswered && !canGoBack}
          data-testid="btn-next"
          style={{
            flex: 1,
            padding: "14px 28px",
            fontSize: "1.05rem",
            fontWeight: 600,
            border: "none",
            borderRadius: "10px",
            cursor: isAnswered || canGoBack ? "pointer" : "not-allowed",
            background: isAnswered ? "linear-gradient(135deg, #8b5cf6, #6366f1)" : disabledBg,
            color: isAnswered ? "white" : disabledColor,
            transition: "all 0.2s ease",
          }}
        >
          Next <Icon name="ArrowRight" size={18} />
        </button>
      ) : (
        <button
          onClick={handleFinish}
          disabled={loading}
          data-testid="btn-finish"
          style={{
            flex: 1,
            padding: "14px 28px",
            fontSize: "1.05rem",
            fontWeight: 600,
            border: "none",
            borderRadius: "10px",
            cursor: "pointer",
            background: "linear-gradient(135deg, #22c55e, #16a34a)",
            color: "white",
          }}
        >
          {loading ? "Submitting..." : "Finish"}
        </button>
      )}
    </div>
  );
}
