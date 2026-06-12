// Presentational spotlight layer for the tutorial overlay: the dark SVG
// backdrop with a rounded-rect cutout around the highlighted element, plus
// the pulsing glow border. Pure render math — `rect` is measured by the
// shell (TutorialOverlay.jsx), which owns all DOM querying and listeners.
export default function TutorialSpotlight({ rect, vw, vh, onSkip }) {
  const cr = 14;
  const cutoutPath = rect
    ? "M0,0 L" + vw + ",0 L" + vw + "," + vh + " L0," + vh + " Z " +
      "M" + (rect.x + cr) + "," + rect.y + " " +
      "L" + (rect.x + rect.w - cr) + "," + rect.y + " " +
      "Q" + (rect.x + rect.w) + "," + rect.y + " " + (rect.x + rect.w) + "," + (rect.y + cr) + " " +
      "L" + (rect.x + rect.w) + "," + (rect.y + rect.h - cr) + " " +
      "Q" + (rect.x + rect.w) + "," + (rect.y + rect.h) + " " + (rect.x + rect.w - cr) + "," + (rect.y + rect.h) + " " +
      "L" + (rect.x + cr) + "," + (rect.y + rect.h) + " " +
      "Q" + rect.x + "," + (rect.y + rect.h) + " " + rect.x + "," + (rect.y + rect.h - cr) + " " +
      "L" + rect.x + "," + (rect.y + cr) + " " +
      "Q" + rect.x + "," + rect.y + " " + (rect.x + cr) + "," + rect.y + " Z"
    : "M0,0 L" + vw + ",0 L" + vw + "," + vh + " L0," + vh + " Z";

  return (
    <>
      {/* Dark overlay with cutout */}
      <svg
        width={vw}
        height={vh}
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          pointerEvents: "auto",
        }}
        onClick={onSkip}
      >
        <path
          d={cutoutPath}
          fillRule="evenodd"
          fill="rgba(0,0,0,0.6)"
        />
      </svg>

      {/* Pulsing glow border */}
      {rect && (
        <div
          style={{
            position: "absolute",
            top: rect.y,
            left: rect.x,
            width: rect.w,
            height: rect.h,
            borderRadius: cr + "px",
            border: "2px solid var(--accent-primary, #6366f1)",
            boxShadow: "0 0 20px rgba(99,102,241,0.5), 0 0 40px rgba(99,102,241,0.2)",
            animation: "tutorial-pulse 2s ease-in-out infinite",
            pointerEvents: "none",
          }}
        />
      )}
    </>
  );
}
