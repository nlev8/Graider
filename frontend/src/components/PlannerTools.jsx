import React from "react";
import ReadingLevelAdjuster from "./planner-tools/ReadingLevelAdjuster";
import StudyGuideGenerator from "./planner-tools/StudyGuideGenerator";
import FlashcardGenerator from "./planner-tools/FlashcardGenerator";
import SlideDeckGenerator from "./planner-tools/SlideDeckGenerator";

/*
 * PlannerTools — thin orchestrator (CQ wave-5 split; was one 836-LOC
 * component). Each tool card was relocated verbatim into planner-tools/*,
 * and each card owns its previously co-located useState block: all four
 * cards are unconditionally mounted here, so every state lifetime is
 * identical to the pre-split single component. Exported API unchanged
 * (`globalAINotes` was already unused pre-split — the cards read
 * `config.globalAINotes` — and is kept for call-site compatibility).
 */
export default function PlannerTools({ config, lessonPlan, generatedAssignment, globalAINotes, uploadedDocs, addToast, shareWithClass }) {
  return (
    <div className="fade-in">
      <ReadingLevelAdjuster config={config} addToast={addToast} />
      <StudyGuideGenerator config={config} lessonPlan={lessonPlan} generatedAssignment={generatedAssignment} addToast={addToast} shareWithClass={shareWithClass} />
      <FlashcardGenerator config={config} lessonPlan={lessonPlan} generatedAssignment={generatedAssignment} uploadedDocs={uploadedDocs} addToast={addToast} shareWithClass={shareWithClass} />
      <SlideDeckGenerator config={config} lessonPlan={lessonPlan} generatedAssignment={generatedAssignment} addToast={addToast} shareWithClass={shareWithClass} />
    </div>
  );
}
