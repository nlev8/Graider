import React from "react";
import Icon from "../Icon";
import StandardCard from "../StandardCard";

export default function StandardsSelectorPanel(props) {
  const { config, domainNameMap, expandedStandards, getDomains, plannerLoading, scrollToDomain, selectedStandards, setExpandedStandards, standards, standardsScrollRef, toggleStandard } = props;
  return (
                        <div className="glass-card" style={{ padding: "25px" }}>
                          <div
                            style={{
                              display: "flex",
                              justifyContent: "space-between",
                              alignItems: "center",
                              marginBottom: "15px",
                            }}
                          >
                            <h3
                              style={{
                                fontSize: "1.1rem",
                                fontWeight: 700,
                                display: "flex",
                                alignItems: "center",
                                gap: "10px",
                              }}
                            >
                              <Icon name="Library" size={20} /> Select Standards
                              ({selectedStandards.length})
                            </h3>
                            <span
                              style={{
                                fontSize: "0.9rem",
                                color: "var(--text-secondary)",
                              }}
                            >
                              {standards.length} standards available
                            </span>
                          </div>

                          {/* Current config display */}
                          <div
                            style={{
                              display: "flex",
                              gap: "10px",
                              marginBottom: "15px",
                              flexWrap: "wrap",
                            }}
                          >
                            <span
                              style={{
                                padding: "6px 12px",
                                borderRadius: "20px",
                                background: "rgba(99,102,241,0.15)",
                                color: "var(--accent-light)",
                                fontSize: "0.85rem",
                                fontWeight: 500,
                              }}
                            >
                              <Icon
                                name="MapPin"
                                size={14}
                                style={{
                                  marginRight: "6px",
                                  verticalAlign: "middle",
                                }}
                              />
                              {{
                                FL: "Florida",
                                TX: "Texas",
                                CA: "California",
                                NY: "New York",
                                GA: "Georgia",
                                NC: "North Carolina",
                                VA: "Virginia",
                                OH: "Ohio",
                                PA: "Pennsylvania",
                                IL: "Illinois",
                              }[config.state] || config.state}
                            </span>
                            <span
                              style={{
                                padding: "6px 12px",
                                borderRadius: "20px",
                                background: "rgba(74,222,128,0.15)",
                                color: "#4ade80",
                                fontSize: "0.85rem",
                                fontWeight: 500,
                              }}
                            >
                              <Icon
                                name="GraduationCap"
                                size={14}
                                style={{
                                  marginRight: "6px",
                                  verticalAlign: "middle",
                                }}
                              />
                              Grade {config.grade_level}
                            </span>
                            <span
                              style={{
                                padding: "6px 12px",
                                borderRadius: "20px",
                                background: "rgba(251,191,36,0.15)",
                                color: "#fbbf24",
                                fontSize: "0.85rem",
                                fontWeight: 500,
                              }}
                            >
                              <Icon
                                name="BookOpen"
                                size={14}
                                style={{
                                  marginRight: "6px",
                                  verticalAlign: "middle",
                                }}
                              />
                              {config.subject}
                            </span>
                          </div>

                          {/* Domain jump bar */}
                          {standards.length > 0 && getDomains(standards).length > 1 && (
                            <div style={{ display: "flex", gap: "6px", flexWrap: "wrap", marginBottom: "10px" }}>
                              {getDomains(standards).map((domain) => {
                                const count = selectedStandards.filter((c) => c.split(".")[2] === domain).length;
                                return (
                                  <button key={domain} onClick={() => scrollToDomain(standardsScrollRef, domain)}
                                    style={{
                                      padding: "4px 10px", fontSize: "0.75rem", fontWeight: 600,
                                      borderRadius: "20px", border: "none", cursor: "pointer",
                                      background: count > 0 ? "rgba(139, 92, 246, 0.2)" : "var(--glass-bg)",
                                      color: count > 0 ? "#a78bfa" : "var(--text-secondary)",
                                      transition: "all 0.2s",
                                    }}
                                  >
                                    {domainNameMap[domain] || domain}{count > 0 ? " (" + count + ")" : ""}
                                  </button>
                                );
                              })}
                            </div>
                          )}

                          <div
                            ref={standardsScrollRef}
                            style={{ maxHeight: "500px", overflowY: "auto" }}
                          >
                            {plannerLoading && standards.length === 0 ? (
                              <div
                                style={{
                                  textAlign: "center",
                                  padding: "40px",
                                  color: "var(--text-secondary)",
                                }}
                              >
                                <Icon
                                  name="Loader2"
                                  size={30}
                                  style={{
                                    animation: "spin 1s linear infinite",
                                  }}
                                />
                                <p style={{ marginTop: "10px" }}>
                                  Loading standards...
                                </p>
                              </div>
                            ) : standards.length > 0 ? (
                              standards.map((std) => (
                                <div key={std.code} data-domain={std.code.split(".")[2]}>
                                <StandardCard
                                  standard={std}
                                  isSelected={selectedStandards.includes(
                                    std.code,
                                  )}
                                  onToggle={() => toggleStandard(std.code)}
                                  isExpanded={expandedStandards.includes(
                                    std.code,
                                  )}
                                  onExpand={() =>
                                    setExpandedStandards((prev) =>
                                      prev.includes(std.code)
                                        ? prev.filter((c) => c !== std.code)
                                        : [...prev, std.code],
                                    )
                                  }
                                />
                                </div>
                              ))
                            ) : (
                              <div
                                style={{
                                  textAlign: "center",
                                  padding: "40px",
                                  background: "var(--glass-bg)",
                                  borderRadius: "12px",
                                }}
                              >
                                <Icon
                                  name="FileQuestion"
                                  size={40}
                                  style={{
                                    color: "var(--text-muted)",
                                    marginBottom: "15px",
                                  }}
                                />
                                <p
                                  style={{
                                    color: "var(--text-secondary)",
                                    marginBottom: "10px",
                                  }}
                                >
                                  No standards found for Grade{" "}
                                  {config.grade_level} {config.subject}.
                                </p>
                                <p
                                  style={{
                                    color: "var(--text-muted)",
                                    fontSize: "0.85rem",
                                  }}
                                >
                                  Try a different grade level or subject in
                                  Settings.
                                </p>
                              </div>
                            )}
                          </div>
                        </div>
  );
}
