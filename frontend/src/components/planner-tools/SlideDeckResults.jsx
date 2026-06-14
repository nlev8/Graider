import React from "react";
import Icon from "../Icon";

/*
 * Pure-prop child extracted from SlideDeckGenerator (CQ wave-8 split #cq8-07).
 * Renders the generated slide deck preview list, the Download PowerPoint button,
 * and the Share with Class button. All state and handlers live in the parent.
 */
export default function SlideDeckResults({ slideDeck, onDownload, onShare }) {
  return (
    <div style={{ marginTop: "20px", borderTop: "1px solid var(--border)", paddingTop: "16px" }}>
      <h4 style={{ fontSize: "1.1rem", fontWeight: 600, marginBottom: "12px" }}>
        {slideDeck.title || 'Slide Deck'} ({(slideDeck.slides || []).length} slides)
      </h4>

      <div style={{ display: "flex", flexDirection: "column", gap: "8px", marginBottom: "16px", maxHeight: "400px", overflowY: "auto" }}>
        {(slideDeck.slides || []).map(function(slide, si) {
          return (
            <div key={si} style={{ padding: "12px 16px", borderRadius: "8px", border: "1px solid var(--border)", background: "var(--input-bg)", display: "flex", gap: "12px", alignItems: "flex-start" }}>
              <span style={{ fontSize: "0.75rem", fontWeight: 700, color: "#8b5cf6", minWidth: "24px" }}>{si + 1}</span>
              <div>
                <div style={{ fontSize: "0.9rem", fontWeight: 600 }}>{slide.title}</div>
                <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: "2px" }}>
                  {slide.layout} {slide.image_prompt ? ' + graphic' : ''}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      <button
        onClick={onDownload}
        className="btn btn-secondary"
        style={{ padding: "10px 20px", display: "flex", alignItems: "center", gap: "8px" }}
      >
        <Icon name="Download" size={16} /> Download PowerPoint (.pptx)
      </button>
      <button
        onClick={onShare}
        className="btn btn-secondary"
        style={{ padding: "10px 20px", display: "flex", alignItems: "center", gap: "8px" }}
      >
        <Icon name="Share2" size={16} /> Share with Class
      </button>
    </div>
  );
}
