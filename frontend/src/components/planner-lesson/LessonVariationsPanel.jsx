import React from "react";
import Icon from "../Icon";
import VariationCard from "./VariationCard";

export default function LessonVariationsPanel(props) {
  const { lessonPlan, lessonVariations, setLessonVariations, unitConfig } = props;
  if (!(lessonVariations.length > 0 && !lessonPlan)) return null;
  return (
                        <div
                          className="glass-card"
                          style={{
                            padding: "30px",
                            maxHeight: "80vh",
                            overflowY: "auto",
                          }}
                        >
                          <div
                            style={{
                              display: "flex",
                              justifyContent: "space-between",
                              alignItems: "center",
                              marginBottom: "25px",
                              paddingBottom: "15px",
                              borderBottom: "1px solid var(--glass-border)",
                            }}
                          >
                            <div>
                              <h2
                                style={{
                                  fontSize: "1.5rem",
                                  fontWeight: 700,
                                  marginBottom: "5px",
                                }}
                              >
                                <Icon
                                  name="Layers"
                                  size={24}
                                  style={{
                                    marginRight: "10px",
                                    verticalAlign: "middle",
                                    color: "var(--accent-primary)",
                                  }}
                                />
                                {(unitConfig.type || "Lesson Plan") + " Variations"}
                              </h2>
                              <p
                                style={{
                                  color: "var(--text-secondary)",
                                  fontSize: "0.9rem",
                                }}
                              >
                                Compare {lessonVariations.length} different
                                approaches for this {(unitConfig.type || "lesson plan").toLowerCase()}
                              </p>
                            </div>
                            <button
                              onClick={() => setLessonVariations([])}
                              className="btn btn-secondary"
                            >
                              <Icon name="X" size={16} /> Close
                            </button>
                          </div>
                          <div
                            style={{
                              display: "flex",
                              flexDirection: "column",
                              gap: "20px",
                            }}
                          >
                            {lessonVariations.map((variation, idx) => (
                              <VariationCard key={idx} {...props} variation={variation} idx={idx} />
                            ))}
                          </div>
                        </div>
  );
}
