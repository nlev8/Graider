import React from "react";

/*
 * Pure-prop child extracted from SlideDeckGenerator (CQ wave-8 split #cq8-07).
 * Renders the options row (slide count, AI graphics, format, instructions)
 * and the resource picker. All state and handlers live in the parent.
 */
export default function SlideDeckConfigPanel({
  slideCount,
  setSlideCount,
  slideImages,
  setSlideImages,
  slideFormat,
  setSlideFormat,
  slideDeckInstructions,
  setSlideDeckInstructions,
  slideResourcesLoading,
  slideResourceList,
  slideResources,
  setSlideResources,
  onBrowseResources,
}) {
  return (
    <>
      <div style={{ display: "flex", gap: "12px", marginBottom: "12px", flexWrap: "wrap" }}>
        <div>
          <label style={{ fontSize: "0.85rem", fontWeight: 600, marginBottom: "6px", display: "block" }}>Slides</label>
          <select value={slideCount} onChange={function(e) { setSlideCount(parseInt(e.target.value)); }} className="input" style={{ maxWidth: "100px" }}>
            <option value={8}>8</option>
            <option value={10}>10</option>
            <option value={12}>12</option>
            <option value={15}>15</option>
          </select>
        </div>
        <div>
          <label style={{ fontSize: "0.85rem", fontWeight: 600, marginBottom: "6px", display: "block" }}>AI Graphics</label>
          <select value={slideImages ? "yes" : "no"} onChange={function(e) { setSlideImages(e.target.value === "yes"); }} className="input" style={{ maxWidth: "160px" }}>
            <option value="yes">With graphics</option>
            <option value="no">Text only</option>
          </select>
        </div>
        <div>
          <label style={{ fontSize: "0.85rem", fontWeight: 600, marginBottom: "6px", display: "block" }}>Format</label>
          <select value={slideFormat} onChange={function(e) { setSlideFormat(e.target.value); }} className="input" style={{ maxWidth: "180px" }}>
            <option value="detailed">Detailed Deck</option>
            <option value="presenter">Presenter Slides</option>
          </select>
        </div>
        <div style={{ flex: 1, minWidth: "200px" }}>
          <label style={{ fontSize: "0.85rem", fontWeight: 600, marginBottom: "6px", display: "block" }}>Instructions (optional)</label>
          <input type="text" value={slideDeckInstructions} onChange={function(e) { setSlideDeckInstructions(e.target.value); }} placeholder="e.g., Focus on vocabulary, include comparison slides" className="input" />
        </div>
      </div>

      {/* Resource picker */}
      <div style={{ marginBottom: "12px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "6px" }}>
          <label style={{ fontSize: "0.85rem", fontWeight: 600 }}>Include saved resources</label>
          <button
            onClick={onBrowseResources}
            className="btn btn-secondary"
            style={{ padding: "4px 10px", fontSize: "0.75rem" }}
            disabled={slideResourcesLoading}
          >
            {slideResourcesLoading ? 'Loading...' : 'Browse'}
          </button>
        </div>
        {slideResourceList.length > 0 && (
          <div style={{ maxHeight: "120px", overflowY: "auto", border: "1px solid var(--border)", borderRadius: "8px", padding: "6px" }}>
            {slideResourceList.map(function(res) {
              var isSelected = slideResources.some(function(r) { return r.id === res.id; });
              return (
                React.createElement('label', { key: res.id, style: { display: "flex", alignItems: "center", gap: "8px", padding: "4px 6px", fontSize: "0.8rem", cursor: "pointer", borderRadius: "4px", background: isSelected ? "rgba(139,92,246,0.1)" : "transparent" } },
                  React.createElement('input', {
                    type: "checkbox",
                    checked: isSelected,
                    onChange: function() {
                      if (isSelected) {
                        setSlideResources(slideResources.filter(function(r) { return r.id !== res.id; }));
                      } else {
                        setSlideResources(slideResources.concat([res]));
                      }
                    }
                  }),
                  React.createElement('span', { style: { fontWeight: 500 } }, res.title || 'Untitled'),
                  React.createElement('span', { style: { color: "var(--text-secondary)", fontSize: "0.7rem" } }, res.content_type || '')
                )
              );
            })}
          </div>
        )}
        {slideResources.length > 0 && (
          React.createElement('p', { style: { fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: "4px" } },
            slideResources.length + ' resource(s) selected')
        )}
      </div>
    </>
  );
}
