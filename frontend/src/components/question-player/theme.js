// Light/dark theme colors for QuestionPlayer — extracted verbatim from
// QuestionPlayer.jsx (CQ wave 6 split). Values must stay byte-identical to
// the originals; the e2e student-flow specs assert on the rendered UI.
export function getPlayerTheme(lm) {
  return {
    subtextColor: lm ? "#64748b" : "rgba(255,255,255,0.6)",
    borderClr: lm ? "#e2e8f0" : "rgba(255,255,255,0.1)",
    textInputBg: lm ? "white" : "rgba(0,0,0,0.3)",
    textInputBorder: lm ? "#cbd5e1" : "rgba(255,255,255,0.2)",
    textInputColor: lm ? "#1e293b" : "white",
    sectionColor: lm ? "#7c3aed" : "#8b5cf6",
    progressTrack: lm ? "#e2e8f0" : "rgba(255,255,255,0.1)",
    navBtnBorder: lm ? "#cbd5e1" : "rgba(255,255,255,0.3)",
    navBtnColor: lm ? "#1e293b" : "white",
    disabledBg: lm ? "#f1f5f9" : "rgba(255,255,255,0.1)",
    disabledColor: lm ? "#94a3b8" : "rgba(255,255,255,0.4)",
    accomBg: lm ? "rgba(59,130,246,0.08)" : "rgba(59,130,246,0.15)",
    accomBorder: lm ? "rgba(59,130,246,0.3)" : "rgba(59,130,246,0.4)",
  };
}
