import { useState, useEffect, useRef, useCallback } from "react";
import { TUTORIAL_STEPS } from "./tutorial-overlay/steps";
import TutorialSpotlight from "./tutorial-overlay/TutorialSpotlight";
import TutorialTooltip from "./tutorial-overlay/TutorialTooltip";

// Shell for the guided tour. Owns ALL measurement state and the full
// measure-then-render cycle (data-tutorial anchor querying, scrollIntoView,
// tooltip positioning math, resize/keyboard listeners) so rects can never go
// stale across component boundaries. The step definitions live in
// tutorial-overlay/steps.js; the spotlight cutout and tooltip card are
// stateless children in tutorial-overlay/ that receive computed positions.
export default function TutorialOverlay({
  currentStep,
  onNext,
  onBack,
  onSkip,
  setActiveTab,
  setSettingsTab,
  setPlannerMode,
}) {
  const [rect, setRect] = useState(null);
  const [tooltipPos, setTooltipPos] = useState({ top: 0, left: 0 });
  const [transitioning, setTransitioning] = useState(false);
  const overlayRef = useRef(null);
  const tooltipRef = useRef(null);
  const step = TUTORIAL_STEPS[currentStep] || TUTORIAL_STEPS[0];
  const totalSteps = TUTORIAL_STEPS.length;

  const positionTooltip = useCallback((highlighted, actualTooltipH) => {
    const tooltipW = 420;
    const tooltipH = actualTooltipH || 380;
    const gap = 16;
    let top, left;

    if (!highlighted) {
      // Center tooltip when no target
      return {
        top: Math.max(80, window.innerHeight / 2 - tooltipH / 2),
        left: Math.max(20, window.innerWidth / 2 - tooltipW / 2),
      };
    }

    // Default: below the element
    top = highlighted.y + highlighted.h + gap;
    left = highlighted.x + highlighted.w / 2 - tooltipW / 2;

    // If not enough room below, place above
    if (top + tooltipH > window.innerHeight - 20) {
      top = highlighted.y - tooltipH - gap;
    }

    // If not enough room above either, place to the right
    if (top < 20) {
      top = Math.max(20, highlighted.y);
      left = highlighted.x + highlighted.w + gap;
    }

    // Keep within viewport
    if (left < 20) left = 20;
    if (left + tooltipW > window.innerWidth - 20) {
      left = window.innerWidth - tooltipW - 20;
    }
    if (top < 20) top = 20;
    if (top + tooltipH > window.innerHeight - 20) {
      top = window.innerHeight - tooltipH - 20;
    }

    return { top, left };
  }, []);

  const measureTarget = useCallback(() => {
    const el = document.querySelector(
      '[data-tutorial="' + step.target + '"]'
    );
    if (!el) {
      setRect(null);
      setTooltipPos(positionTooltip(null));
      return;
    }
    // For elements taller than the viewport, scroll to the top of the element
    // so we can frame the visible portion properly
    const preCheck = el.getBoundingClientRect();
    if (preCheck.height > window.innerHeight * 0.7) {
      el.scrollIntoView({ behavior: "instant", block: "start" });
    } else {
      el.scrollIntoView({ behavior: "instant", block: "nearest" });
    }
    // Double rAF to ensure layout is settled
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        const r = el.getBoundingClientRect();
        const pad = 10;
        const maxH = window.innerHeight * 0.55;
        const highlighted = {
          x: r.left - pad,
          y: Math.max(r.top - pad, 10),
          w: r.width + pad * 2,
          h: Math.min(r.height + pad * 2, maxH),
        };
        setRect(highlighted);
        setTooltipPos(positionTooltip(highlighted));
      });
    });
  }, [step.target, positionTooltip]);

  // After tooltip renders, reposition based on actual height
  useEffect(() => {
    if (transitioning || !tooltipRef.current) return;
    const el = tooltipRef.current;
    const r = el.getBoundingClientRect();
    // If bottom is clipped, reposition
    if (r.bottom > window.innerHeight - 10) {
      setTooltipPos((prev) => ({
        ...prev,
        top: Math.max(20, window.innerHeight - r.height - 20),
      }));
    }
    // If top is clipped
    if (r.top < 10) {
      setTooltipPos((prev) => ({ ...prev, top: 20 }));
    }
  });

  useEffect(() => {
    setTransitioning(true);
    // Switch tab if needed
    if (step.tab) {
      setActiveTab(step.tab);
    }
    if (step.settingsTab && setSettingsTab) {
      setTimeout(() => setSettingsTab(step.settingsTab), 50);
    }
    if (step.plannerMode && setPlannerMode) {
      setTimeout(() => setPlannerMode(step.plannerMode), 50);
    }
    // Wait for tab content to render, then measure
    const timer = setTimeout(() => {
      measureTarget();
      setTransitioning(false);
    }, 250);
    return () => clearTimeout(timer);
  }, [currentStep, step.tab, step.settingsTab, step.plannerMode, setActiveTab, setSettingsTab, setPlannerMode, measureTarget]);

  // Re-measure on resize
  useEffect(() => {
    const handleResize = () => measureTarget();
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, [measureTarget]);

  // Keyboard navigation
  useEffect(() => {
    const handleKey = (e) => {
      if (e.key === "ArrowRight" || e.key === "Enter") {
        e.preventDefault();
        if (currentStep < totalSteps - 1) onNext();
        else onSkip();
      } else if (e.key === "ArrowLeft") {
        e.preventDefault();
        if (currentStep > 0) onBack();
      } else if (e.key === "Escape") {
        e.preventDefault();
        onSkip();
      }
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [currentStep, totalSteps, onNext, onBack, onSkip]);

  const isLast = currentStep >= totalSteps - 1;

  const vw = window.innerWidth;
  const vh = window.innerHeight;

  return (
    <div
      ref={overlayRef}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 10001,
        pointerEvents: "none",
      }}
    >
      <TutorialSpotlight rect={rect} vw={vw} vh={vh} onSkip={onSkip} />

      <TutorialTooltip
        transitioning={transitioning}
        tooltipRef={tooltipRef}
        tooltipPos={tooltipPos}
        step={step}
        currentStep={currentStep}
        totalSteps={totalSteps}
        isLast={isLast}
        onNext={onNext}
        onBack={onBack}
        onSkip={onSkip}
      />

      {/* Keyframes */}
      <style>{
        "@keyframes tutorial-pulse { 0%, 100% { box-shadow: 0 0 20px rgba(99,102,241,0.5), 0 0 40px rgba(99,102,241,0.2); } 50% { box-shadow: 0 0 30px rgba(99,102,241,0.7), 0 0 60px rgba(99,102,241,0.3); } }" +
        " @keyframes tutorial-fade-in { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }"
      }</style>
    </div>
  );
}

export { TUTORIAL_STEPS };
