import Icon from "../Icon";

// Presentational tooltip card for the tutorial overlay: header (icon, title,
// step counter, skip), description, navigation buttons, and progress bar.
// Position is computed by the shell (TutorialOverlay.jsx), which owns all
// measurement state; `tooltipRef` is the shell's ref so its post-render
// clipping effect can re-measure the card's actual height.
export default function TutorialTooltip({
  transitioning,
  tooltipRef,
  tooltipPos,
  step,
  currentStep,
  totalSteps,
  isLast,
  onNext,
  onBack,
  onSkip,
}) {
  if (transitioning) return null;

  return (
    <div
      ref={tooltipRef}
      style={{
        position: "absolute",
        top: tooltipPos.top,
        left: tooltipPos.left,
        width: 420,
        maxHeight: "70vh",
        overflowY: "auto",
        padding: "22px",
        background: "var(--glass-bg, rgba(30,30,40,0.97))",
        backdropFilter: "blur(24px)",
        border: "1px solid var(--glass-border, rgba(255,255,255,0.1))",
        borderRadius: "16px",
        boxShadow: "0 20px 60px rgba(0,0,0,0.5)",
        pointerEvents: "auto",
        animation: "tutorial-fade-in 0.2s ease-out",
      }}
    >
      {/* Header */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "12px",
          marginBottom: "14px",
        }}
      >
        <div
          style={{
            width: 38,
            height: 38,
            borderRadius: "10px",
            background: "linear-gradient(135deg, var(--accent-primary, #6366f1), var(--accent-secondary, #8b5cf6))",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            flexShrink: 0,
          }}
        >
          <Icon name={step.icon} size={18} style={{ color: "#fff" }} />
        </div>
        <div style={{ flex: 1 }}>
          <div
            style={{
              fontWeight: 700,
              fontSize: "1.05rem",
              color: "var(--text-primary, #fff)",
            }}
          >
            {step.title}
          </div>
          <div
            style={{
              fontSize: "0.75rem",
              color: "var(--text-muted, #666)",
              marginTop: "2px",
            }}
          >
            Step {currentStep + 1} of {totalSteps}
          </div>
        </div>
        <button
          onClick={onSkip}
          style={{
            background: "none",
            border: "none",
            cursor: "pointer",
            color: "var(--text-muted, #888)",
            padding: "4px",
            display: "flex",
            alignItems: "center",
          }}
          title="Skip tutorial"
        >
          <Icon name="X" size={16} />
        </button>
      </div>

      {/* Description */}
      <p
        style={{
          fontSize: "0.88rem",
          lineHeight: 1.7,
          color: "var(--text-secondary, #bbb)",
          margin: "0 0 18px 0",
        }}
      >
        {step.description}
      </p>

      {/* Navigation buttons */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <button
          onClick={onSkip}
          style={{
            padding: "7px 14px",
            borderRadius: "8px",
            border: "none",
            background: "transparent",
            color: "var(--text-muted, #666)",
            cursor: "pointer",
            fontSize: "0.82rem",
          }}
        >
          Skip tour
        </button>
        <div style={{ display: "flex", gap: "8px" }}>
          {currentStep > 0 && (
            <button
              onClick={onBack}
              style={{
                padding: "9px 18px",
                borderRadius: "8px",
                border: "1px solid var(--glass-border, rgba(255,255,255,0.1))",
                background: "transparent",
                color: "var(--text-secondary, #aaa)",
                cursor: "pointer",
                fontSize: "0.85rem",
                fontWeight: 500,
              }}
            >
              Back
            </button>
          )}
          <button
            onClick={isLast ? onSkip : onNext}
            style={{
              padding: "9px 22px",
              borderRadius: "8px",
              border: "none",
              background: "linear-gradient(135deg, var(--accent-primary, #6366f1), var(--accent-secondary, #8b5cf6))",
              color: "#fff",
              cursor: "pointer",
              fontSize: "0.85rem",
              fontWeight: 600,
            }}
          >
            {isLast ? "Get Started" : "Next"}
          </button>
        </div>
      </div>

      {/* Progress bar */}
      <div
        style={{
          marginTop: "14px",
          height: 3,
          borderRadius: 2,
          background: "rgba(255,255,255,0.06)",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            height: "100%",
            width: ((currentStep + 1) / totalSteps * 100) + "%",
            borderRadius: 2,
            background: "linear-gradient(90deg, var(--accent-primary, #6366f1), var(--accent-secondary, #8b5cf6))",
            transition: "width 0.3s ease",
          }}
        />
      </div>
    </div>
  );
}
