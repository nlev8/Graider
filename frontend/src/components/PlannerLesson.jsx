import React from "react";
import PlannerSidebar from "./planner-lesson/PlannerSidebar";
import BrainstormIdeasPanel from "./planner-lesson/BrainstormIdeasPanel";
import LessonVariationsPanel from "./planner-lesson/LessonVariationsPanel";
import LessonPlanView from "./planner-lesson/LessonPlanView";
import StandardsSelectorPanel from "./planner-lesson/StandardsSelectorPanel";

export default function PlannerLesson(props) {
  const { generatedAssignment, lessonPlan } = props;
  return (
                  <div
                    style={{
                      display: "grid",
                      gridTemplateColumns: (lessonPlan && ((lessonPlan.sections && !lessonPlan.days) || generatedAssignment)) ? "1fr" : "300px 1fr",
                      gap: "25px",
                    }}
                  >
                    {/* Sidebar — hidden when viewing a generated assignment; visible for lesson plans so user can configure & create assignments */}
                    <PlannerSidebar {...props} />

                    {/* Main Content */}
                    <div>
                      {/* Brainstormed Ideas Section - Full Width */}
                      <BrainstormIdeasPanel {...props} />
                      {/* Lesson Variations Display */}
                      <LessonVariationsPanel {...props} />

                      {/* Single Lesson Plan Display */}
                      {lessonPlan ? (
                        <LessonPlanView {...props} />
                      ) : (
                        <StandardsSelectorPanel {...props} />
                      )}
                    </div>
                  </div>
  );
}
