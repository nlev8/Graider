import React from "react";
import Icon from "../Icon";
import ReferenceDocsSection from "./ReferenceDocsSection";
import AssignmentSectionsConfig from "./AssignmentSectionsConfig";
import SidebarActions from "./SidebarActions";

export default function PlannerSidebar(props) {
  const { config, generatedAssignment, lessonPlan, setUnitConfig, unitConfig } = props;
  if (lessonPlan && ((lessonPlan.sections && !lessonPlan.days) || generatedAssignment)) return null;
  return (
                    <div
                      style={{
                        display: "flex",
                        flexDirection: "column",
                        gap: "20px",
                      }}
                    >
                      {/* Unit Details */}
                      <div className="glass-card" style={{ padding: "20px" }}>
                        <h3
                          style={{
                            fontSize: "1.1rem",
                            fontWeight: 700,
                            marginBottom: "15px",
                            display: "flex",
                            alignItems: "center",
                            gap: "10px",
                          }}
                        >
                          <Icon name="FileText" size={20} /> Details
                        </h3>
                        <div
                          style={{
                            display: "flex",
                            flexDirection: "column",
                            gap: "15px",
                          }}
                        >
                          <div>
                            <label className="label">Content Type</label>
                            <select
                              className="input"
                              value={unitConfig.type}
                              onChange={(e) =>
                                setUnitConfig({
                                  ...unitConfig,
                                  type: e.target.value,
                                })
                              }
                            >
                              <option value="Unit Plan">Unit Plan</option>
                              <option value="Lesson Plan">Lesson Plan</option>
                              <option value="Assignment">Assignment</option>
                              <option value="Project">Project</option>
                            </select>
                          </div>
                          <div>
                            <label className="label">Title</label>
                            <input
                              type="text"
                              className="input"
                              value={unitConfig.title}
                              onChange={(e) =>
                                setUnitConfig({
                                  ...unitConfig,
                                  title: e.target.value,
                                })
                              }
                              placeholder={
                                {
                                  'Math': 'e.g., Solving Systems of Linear Equations',
                                  'Science': 'e.g., Cell Structure and Function',
                                  'English/ELA': 'e.g., Analyzing Argumentative Texts',
                                  'US History': 'e.g., Causes of the American Revolution',
                                  'World History': 'e.g., Rise and Fall of the Roman Empire',
                                  'Social Studies': 'e.g., Rights and Responsibilities of Citizens',
                                  'Civics': 'e.g., Foundations of American Government',
                                  'Geography': 'e.g., Climate Zones and Human Adaptation',
                                }[config.subject] || 'e.g., Lesson Title'
                              }
                            />
                          </div>
                          <div
                            style={{
                              display: "grid",
                              gridTemplateColumns: "1fr 1fr",
                              gap: "12px",
                            }}
                          >
                            <div>
                              <label className="label">Duration (Days)</label>
                              <input
                                type="number"
                                className="input"
                                value={unitConfig.duration}
                                onChange={(e) =>
                                  setUnitConfig({
                                    ...unitConfig,
                                    duration: parseInt(e.target.value) || 1,
                                  })
                                }
                                min="1"
                                max="20"
                              />
                            </div>
                            <div>
                              <label className="label">Period Length</label>
                              <input
                                type="number"
                                className="input"
                                value={unitConfig.periodLength}
                                onChange={(e) =>
                                  setUnitConfig({
                                    ...unitConfig,
                                    periodLength:
                                      parseInt(e.target.value) || 50,
                                  })
                                }
                                min="20"
                                max="120"
                              />
                            </div>
                          </div>
                          {unitConfig.type === "Assignment" && (
                            <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: "12px" }}>
                              <div>
                                <label className="label">Total Questions</label>
                                <input
                                  type="number"
                                  className="input"
                                  value={unitConfig.totalQuestions}
                                  onChange={(e) =>
                                    setUnitConfig({
                                      ...unitConfig,
                                      totalQuestions: parseInt(e.target.value) || 10,
                                    })
                                  }
                                  min="5"
                                  max="50"
                                />
                              </div>
                            </div>
                          )}
                          <ReferenceDocsSection {...props} />

                          <div>
                            <label className="label">
                              Additional Requirements
                            </label>
                            <textarea
                              className="input"
                              value={unitConfig.requirements}
                              onChange={(e) =>
                                setUnitConfig({
                                  ...unitConfig,
                                  requirements: e.target.value,
                                })
                              }
                              placeholder={
                                {
                                  'Math': 'e.g., Include word problems with real-world scenarios, focus on showing work step-by-step',
                                  'Science': 'e.g., Include a lab component with data collection, tie to real-world applications',
                                  'English/ELA': 'e.g., Include text-dependent questions, require evidence-based responses with citations',
                                  'US History': 'e.g., Use primary source documents, include analysis of cause and effect',
                                  'World History': 'e.g., Compare perspectives from multiple civilizations, include map analysis',
                                  'Social Studies': 'e.g., Connect to current events, include civic action component',
                                  'Civics': 'e.g., Reference the U.S. Constitution, include a debate or discussion prompt',
                                  'Geography': 'e.g., Include map skills practice, analyze human-environment interaction',
                                }[config.subject] || 'e.g., Any special instructions for this lesson...'
                              }
                              style={{ minHeight: "80px" }}
                            />
                          </div>
                          {/* Assignment Sections Dropdown - visible when content type is Assignment */}
                          <AssignmentSectionsConfig {...props} />

                          <SidebarActions {...props} />
                        </div>
                      </div>
                    </div>
  );
}
