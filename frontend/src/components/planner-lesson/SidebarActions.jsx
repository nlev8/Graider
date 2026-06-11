import React from "react";
import Icon from "../Icon";

export default function SidebarActions(props) {
  const { brainstormIdeasHandler, brainstormLoading, generateLessonPlan, plannerLoading, selectedIdea, selectedStandards, unitConfig, uploadedDocs } = props;
  return (
    <>
                          {/* Brainstorm Button */}
                          <button
                            onClick={brainstormIdeasHandler}
                            disabled={
                              brainstormLoading ||
                              (selectedStandards.length === 0 && uploadedDocs.length === 0)
                            }
                            className="btn btn-secondary"
                            style={{
                              width: "100%",
                              justifyContent: "center",
                              marginBottom: "10px",
                              opacity:
                                brainstormLoading ||
                                (selectedStandards.length === 0 && uploadedDocs.length === 0)
                                  ? 0.5
                                  : 1,
                            }}
                          >
                            {brainstormLoading ? (
                              <Icon
                                name="Loader2"
                                size={18}
                                style={{ animation: "spin 1s linear infinite" }}
                              />
                            ) : (
                              <Icon name="Lightbulb" size={18} />
                            )}
                            {brainstormLoading
                              ? "Brainstorming..."
                              : "Brainstorm " + unitConfig.type + " Ideas"}
                          </button>

                          {/* Generate Plan Button */}
                          <button
                            onClick={() => generateLessonPlan(false)}
                            disabled={
                              plannerLoading || (selectedStandards.length === 0 && uploadedDocs.length === 0)
                            }
                            className="btn btn-primary"
                            style={{
                              width: "100%",
                              justifyContent: "center",
                              marginBottom: "10px",
                              opacity:
                                plannerLoading || (selectedStandards.length === 0 && uploadedDocs.length === 0)
                                  ? 0.5
                                  : 1,
                            }}
                          >
                            {plannerLoading ? (
                              <Icon
                                name="Loader2"
                                size={18}
                                style={{ animation: "spin 1s linear infinite" }}
                              />
                            ) : (
                              <Icon name="Sparkles" size={18} />
                            )}
                            {plannerLoading
                              ? (unitConfig.type === "Assignment" ? "Creating Assignment..." : "Creating...")
                              : selectedIdea
                                ? "Create from Idea"
                                : "Create"}
                          </button>

                          {/* Generate Variations Button */}
                          <button
                            onClick={() => generateLessonPlan(true)}
                            disabled={
                              plannerLoading || (selectedStandards.length === 0 && uploadedDocs.length === 0)
                            }
                            className="btn btn-secondary"
                            style={{
                              width: "100%",
                              justifyContent: "center",
                              opacity:
                                plannerLoading || (selectedStandards.length === 0 && uploadedDocs.length === 0)
                                  ? 0.5
                                  : 1,
                              fontSize: "0.85rem",
                            }}
                          >
                            <Icon name="Layers" size={16} />
                            {"Generate 3 " + unitConfig.type + " Variations"}
                          </button>
    </>
  );
}
