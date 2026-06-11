import React from "react";
import AssessmentSettingsCard from "./planner-assessment/AssessmentSettingsCard";
import SectionCategoriesCard from "./planner-assessment/SectionCategoriesCard";
import QuestionTypesCard from "./planner-assessment/QuestionTypesCard";
import DokDistributionCard from "./planner-assessment/DokDistributionCard";
import ContentSourcesPanel from "./planner-assessment/ContentSourcesPanel";
import StandardsPanel from "./planner-assessment/StandardsPanel";
import AssessmentPreview from "./planner-assessment/AssessmentPreview";
import Icon from "./Icon";

export default function PlannerAssessment(props) {
  const { assessmentLoading, generateAssessmentHandler, selectedStandards, uploadedDocs } = props;
  return (
                    <div
                      style={{
                        display: "grid",
                        gridTemplateColumns: "350px 1fr",
                        gap: "25px",
                      }}
                    >
                      {/* Assessment Config Sidebar */}
                      <div
                        style={{
                          display: "flex",
                          flexDirection: "column",
                          gap: "20px",
                        }}
                      >
                        {/* Assessment Type */}
                        <AssessmentSettingsCard {...props} />

                        {/* Section Categories Dropdown */}
                        <SectionCategoriesCard {...props} />

                        {/* Question Types */}
                        <QuestionTypesCard {...props} />

                        {/* DOK Distribution */}
                        <DokDistributionCard {...props} />

                        {/* Generate Button */}
                        <button
                          onClick={generateAssessmentHandler}
                          disabled={(selectedStandards.length === 0 && uploadedDocs.length === 0) || assessmentLoading}
                          className="btn btn-primary"
                          style={{
                            padding: "14px 24px",
                            fontSize: "1rem",
                            opacity: (selectedStandards.length === 0 && uploadedDocs.length === 0) ? 0.5 : 1,
                          }}
                        >
                          {assessmentLoading ? (
                            <>
                              <Icon name="Loader2" size={20} className="spin" />
                              Generating Assessment...
                            </>
                          ) : (
                            <>
                              <Icon name="Sparkles" size={20} />
                              Generate Assessment
                            </>
                          )}
                        </button>
                      </div>

                      {/* Main Content Area */}
                      <div
                        style={{
                          display: "flex",
                          flexDirection: "column",
                          gap: "20px",
                        }}
                      >
                        {/* Content Sources Panel */}
                        <ContentSourcesPanel {...props} />

                        {/* Standards Selection */}
                        <StandardsPanel {...props} />

                        {/* Generated Assessment Preview */}
                        <AssessmentPreview {...props} />
                      </div>
                    </div>
  );
}
