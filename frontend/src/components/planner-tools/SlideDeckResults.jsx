import React, { useState, useEffect } from "react";
import * as api from "../../services/api";

/*
 * Results panel for the web-rendered slide deck. Shows a live iframe preview
 * (pixel-identical to the printed PDF, since both come from the same
 * build_deck_html backend) plus the download/share actions. The PDF is the
 * primary export; PowerPoint is kept as a basic secondary download.
 *
 * Replaces the previous static slide-list + PPTX-only panel (CQ wave-8 split
 * #cq8-07). Props: { slideDeck, addToast, onShare } — onShare is the parent's
 * shareWithClass(deck, type, title).
 */
export default function SlideDeckResults({ slideDeck, addToast, onShare }) {
  const [previewHtml, setPreviewHtml] = useState("");
  const [pdfLoading, setPdfLoading] = useState(false);

  useEffect(function () {
    let cancelled = false;
    api.renderSlidesHtml(slideDeck)
      .then(function (html) { if (!cancelled) setPreviewHtml(html); })
      .catch(function () { if (!cancelled) setPreviewHtml(""); });
    return function () { cancelled = true; };
  }, [slideDeck]);

  async function downloadPdf() {
    setPdfLoading(true);
    try {
      const blob = await api.downloadSlidesPdf(slideDeck);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = (slideDeck.title || "slides") + ".pdf";
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      addToast(e.message || "Failed to generate PDF", "error");
    } finally {
      setPdfLoading(false);
    }
  }

  async function downloadPptx() {
    try {
      const resp = await fetch("/api/export-slides", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ slides: slideDeck }),
      });
      if (!resp.ok) {
        let msg = "Export failed";
        try { msg = (await resp.json()).error || msg; } catch (e) { /* non-JSON body */ }
        addToast(msg, "error");
        return;
      }
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = (slideDeck.title || "slides") + ".pptx";
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      addToast("Export failed: " + e.message, "error");
    }
  }

  return (
    <div style={{ marginTop: "20px", borderTop: "1px solid var(--border)", paddingTop: "16px" }}>
      <h4 style={{ fontSize: "1.1rem", fontWeight: 600, marginBottom: "12px" }}>
        {slideDeck.title || "Slide Deck"} ({(slideDeck.slides || []).length} slides)
      </h4>
      <iframe
        title="Slide preview"
        srcDoc={previewHtml}
        style={{ width: "100%", height: "420px", border: "1px solid var(--border)",
                 borderRadius: "8px", background: "#555" }}
      />
      <div style={{ display: "flex", gap: "10px", marginTop: "12px", flexWrap: "wrap" }}>
        <button className="btn btn-primary" onClick={downloadPdf} disabled={pdfLoading}
                style={{ padding: "10px 20px" }}>
          {pdfLoading ? "Generating PDF…" : "Download PDF"}
        </button>
        <button className="btn btn-secondary" onClick={downloadPptx}
                style={{ padding: "10px 20px" }}>
          Download PowerPoint (basic)
        </button>
        <button className="btn btn-secondary"
                onClick={function () { onShare(slideDeck, "slide_deck", slideDeck.title || "Slide Deck"); }}
                style={{ padding: "10px 20px" }}>
          Share with Class
        </button>
      </div>
    </div>
  );
}
