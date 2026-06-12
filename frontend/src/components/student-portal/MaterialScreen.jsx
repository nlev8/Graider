import React from "react";
import FlashcardView from "../FlashcardView";
import MindMapView from "../MindMapView";
import { containerStyle, buttonStyle } from "./portalStyles";

// ============ SHARED MATERIAL SCREEN ============
// JSX (and the render-scoped ct/materialData/materialContent/mediaUrl/isWide
// locals) moved verbatim from StudentPortal.jsx (CQ wave-6 split). Stage
// guard replaces the shell's original `if (stage === "material")` block.
// Note: this screen intentionally has no ThemeToggle — the original didn't
// render one for the material stage.
export default function MaterialScreen(props) {
  const { stage, assessment, setStage, setJoinCode, setAssessment } = props;
  if (stage !== "material") return null;

  var ct = assessment?.content_type;
  var materialData = assessment?.data;
  var materialContent = assessment?.content;
  var mediaUrl = assessment?.media_url;
  var isWide = ct === "mind_map" || ct === "infographic";

  var cssVarStyle = {
    padding: "40px 20px", maxWidth: isWide ? "900px" : "600px", margin: "0 auto",
  };

  return (
    <div style={containerStyle}>
      <div style={cssVarStyle}>
        <div style={{ textAlign: "center", marginBottom: "30px" }}>
          <h1 style={{ fontSize: "1.8rem", fontWeight: 700, marginBottom: "8px" }}>
            {assessment?.title || "Study Material"}
          </h1>
          <p style={{ color: "var(--text-secondary)", fontSize: "0.95rem" }}>
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
                <div key={idx} style={{ background: "var(--glass-bg)", padding: "16px 18px", borderRadius: "10px", marginBottom: "10px", border: "1px solid var(--glass-border)" }}>
                  <div style={{ fontWeight: 600, fontSize: "0.95rem", marginBottom: "8px" }}>{"Q" + (idx + 1) + ". " + (item.question || item.text || "")}</div>
                  {item.options && (
                    <div style={{ marginBottom: "8px" }}>
                      {item.options.map(function(opt, oi) {
                        var isCorrect = opt === item.answer || opt === item.correct_answer || oi === item.correct_index;
                        return (<div key={oi} style={{ padding: "4px 0", fontSize: "0.9rem", color: isCorrect ? "var(--success)" : "var(--text-secondary)" }}>{String.fromCharCode(65 + oi) + ") " + (typeof opt === "string" ? opt : opt.text || JSON.stringify(opt))}{isCorrect ? " " + String.fromCharCode(10003) : ""}</div>);
                      })}
                    </div>
                  )}
                  {(item.answer || item.correct_answer) && (
                    <div style={{ padding: "8px 12px", borderRadius: "8px", background: "var(--success-bg)", fontSize: "0.85rem", color: "var(--success)" }}><strong>Answer:</strong> {item.answer || item.correct_answer}</div>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {/* Mind Map */}
        {ct === "mind_map" && materialData && (
          <div style={{ background: "var(--glass-bg)", borderRadius: "12px", border: "1px solid var(--glass-border)", padding: "16px", minHeight: "400px" }}>
            <MindMapView data={materialData} />
          </div>
        )}

        {/* Study Guide */}
        {ct === "study_guide" && materialContent && (
          <div style={{ background: "var(--glass-bg)", borderRadius: "12px", border: "1px solid var(--glass-border)", padding: "24px", fontSize: "0.95rem", lineHeight: 1.7, whiteSpace: "pre-wrap", color: "var(--text-primary)" }}>
            {materialContent}
          </div>
        )}

        {/* Audio Overview */}
        {ct === "audio_overview" && mediaUrl && (
          <div style={{ background: "var(--glass-bg)", borderRadius: "12px", padding: "30px", textAlign: "center" }}>
            <div style={{ fontSize: "3rem", marginBottom: "15px" }}>🎧</div>
            <audio controls style={{ width: "100%" }} src={mediaUrl}>Your browser does not support the audio element.</audio>
          </div>
        )}

        {/* Video Overview */}
        {ct === "video_overview" && mediaUrl && (
          <div style={{ background: "var(--glass-bg)", borderRadius: "12px", padding: "12px", textAlign: "center" }}>
            <video controls style={{ width: "100%", maxHeight: "500px", borderRadius: "8px" }} src={mediaUrl}>Your browser does not support the video element.</video>
          </div>
        )}

        {/* Infographic */}
        {ct === "infographic" && mediaUrl && (
          <div style={{ background: "var(--glass-bg)", borderRadius: "12px", padding: "12px", textAlign: "center", maxHeight: "600px", overflow: "auto" }}>
            <img src={mediaUrl} alt="Infographic" style={{ maxWidth: "100%", borderRadius: "8px" }} />
          </div>
        )}

        {/* Data Table */}
        {ct === "data_table" && mediaUrl && (
          <div style={{ background: "var(--glass-bg)", borderRadius: "12px", padding: "20px", textAlign: "center" }}>
            <p style={{ color: "var(--text-secondary)", marginBottom: "15px" }}>Data table available for download:</p>
            <a href={mediaUrl} download style={{ ...buttonStyle, maxWidth: "250px", margin: "0 auto", textDecoration: "none" }}>Download CSV</a>
          </div>
        )}

        {/* Slide Deck */}
        {ct === "slide_deck" && mediaUrl && (
          <div style={{ background: "var(--glass-bg)", borderRadius: "12px", padding: "20px", textAlign: "center" }}>
            <div style={{ fontSize: "3rem", marginBottom: "15px" }}>📊</div>
            <p style={{ color: "var(--text-secondary)", marginBottom: "15px" }}>Slide deck available for download:</p>
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
