import React from "react";
import FlashcardView from "../FlashcardView";

// ============ RESOURCE VIEWER MODAL ============
// JSX moved verbatim from StudentDashboard.jsx (CQ wave-7 split). The
// shell's original `{selectedResource && (...)}` guard becomes the
// early-return-null below; selectedResource state stays in the
// always-mounted StudentDashboard shell.
export default function ResourceViewerModal(props) {
  const { selectedResource, setSelectedResource } = props;
  if (!selectedResource) return null;

  return (
    <div style={{
      position: "fixed", top: 0, left: 0, right: 0, bottom: 0,
      background: "var(--modal-bg)", display: "flex", alignItems: "center",
      justifyContent: "center", zIndex: 1000, padding: "20px",
    }} onClick={function() { setSelectedResource(null); }}>
      <div
        style={{
          background: "var(--modal-content-bg)", borderRadius: "16px",
          padding: "24px", maxWidth: "700px", width: "100%",
          maxHeight: "80vh", overflowY: "auto",
        }}
        onClick={function(e) { e.stopPropagation(); }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
          <h3 style={{ fontSize: "1.2rem", fontWeight: 700 }}>{selectedResource.title}</h3>
          <button onClick={function() { setSelectedResource(null); }} style={{ background: "none", border: "none", fontSize: "1.5rem", cursor: "pointer", color: "var(--text-secondary)" }}>{String.fromCharCode(10005)}</button>
        </div>

        {selectedResource.content_type === 'study_guide' && selectedResource.content && (
          <div>
            {(selectedResource.content.sections || []).map(function(section, si) {
              return (
                <div key={si} style={{ marginBottom: "16px" }}>
                  <h4 style={{ fontSize: "0.95rem", fontWeight: 600, color: "var(--text-primary)", marginBottom: "8px" }}>{section.heading}</h4>
                  {section.content && section.content.map(function(point, pi) {
                    return <p key={pi} style={{ fontSize: "0.85rem", marginBottom: "4px", paddingLeft: "12px", color: "var(--text-muted)" }}>{String.fromCharCode(8226)} {point}</p>;
                  })}
                  {section.terms && section.terms.map(function(item, ti) {
                    return <p key={ti} style={{ fontSize: "0.85rem", marginBottom: "4px", paddingLeft: "12px", color: "var(--text-muted)" }}><strong>{item.term}:</strong> {item.definition}</p>;
                  })}
                  {section.questions && section.questions.map(function(qa, qi) {
                    return (
                      <div key={qi} style={{ marginBottom: "8px", paddingLeft: "12px" }}>
                        <p style={{ fontSize: "0.85rem", fontWeight: 600, color: "var(--text-primary)" }}>{qi + 1}. {qa.question}</p>
                        <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", paddingLeft: "16px" }}>Answer: {qa.answer}</p>
                      </div>
                    );
                  })}
                </div>
              );
            })}
          </div>
        )}

        {selectedResource.content_type === 'flashcards' && selectedResource.content && (
          <FlashcardView data={selectedResource.content} />
        )}

        {selectedResource.content_type === 'slide_deck' && (
          <div style={{ textAlign: "center", padding: "20px" }}>
            <p style={{ fontSize: "0.9rem", color: "var(--text-secondary)", marginBottom: "12px" }}>
              This slide deck contains {(selectedResource.content.slides || []).length} slides.
            </p>
            <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>
              Download the PowerPoint file from your teacher to view the full presentation.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
