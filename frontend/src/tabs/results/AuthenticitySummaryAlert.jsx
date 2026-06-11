import React from "react";
import Icon from "../../components/Icon";
import { getAuthenticityStatus } from "../../utils/authenticity";

export default function AuthenticitySummaryAlert({ status }) {
  if (status.results.length === 0) return null;

                        const authStats = status.results.reduce(
                          (acc, r) => {
                            const auth = getAuthenticityStatus(r);
                            if (auth.ai.flag === "likely") acc.aiLikely++;
                            else if (auth.ai.flag === "possible")
                              acc.aiPossible++;
                            if (auth.plag.flag === "likely") acc.plagLikely++;
                            else if (auth.plag.flag === "possible")
                              acc.plagPossible++;
                            return acc;
                          },
                          {
                            aiLikely: 0,
                            aiPossible: 0,
                            plagLikely: 0,
                            plagPossible: 0,
                          },
                        );

                        const hasConcerns =
                          authStats.aiLikely +
                            authStats.aiPossible +
                            authStats.plagLikely +
                            authStats.plagPossible >
                          0;

                        return hasConcerns ? (
                          <div
                            style={{
                              marginBottom: "20px",
                              padding: "15px 20px",
                              borderRadius: "12px",
                              background:
                                "linear-gradient(135deg, rgba(248,113,113,0.1), rgba(251,191,36,0.1))",
                              border: "1px solid rgba(248,113,113,0.3)",
                              display: "flex",
                              alignItems: "center",
                              flexWrap: "wrap",
                              gap: "15px",
                            }}
                          >
                            <Icon
                              name="Shield"
                              size={24}
                              style={{ color: "#f87171" }}
                            />
                            <div style={{ flex: 1, minWidth: 0 }}>
                              <div
                                style={{ fontWeight: 700, marginBottom: "8px" }}
                              >
                                Authenticity Summary
                              </div>
                              <div
                                style={{
                                  display: "flex",
                                  flexWrap: "wrap",
                                  gap: "20px",
                                  fontSize: "0.9rem",
                                }}
                              >
                                {/* AI Detection Stats */}
                                <div>
                                  <div
                                    style={{
                                      color: "var(--text-muted)",
                                      fontSize: "0.8rem",
                                      marginBottom: "4px",
                                    }}
                                  >
                                    <Icon
                                      name="Bot"
                                      size={12}
                                      style={{
                                        marginRight: "4px",
                                        verticalAlign: "middle",
                                      }}
                                    />
                                    AI Detection
                                  </div>
                                  <div style={{ display: "flex", gap: "10px" }}>
                                    {authStats.aiLikely > 0 && (
                                      <span style={{ color: "#f87171" }}>
                                        {authStats.aiLikely} likely
                                      </span>
                                    )}
                                    {authStats.aiPossible > 0 && (
                                      <span style={{ color: "#fbbf24" }}>
                                        {authStats.aiPossible} possible
                                      </span>
                                    )}
                                    {authStats.aiLikely === 0 &&
                                      authStats.aiPossible === 0 && (
                                        <span style={{ color: "#4ade80" }}>
                                          All clear
                                        </span>
                                      )}
                                  </div>
                                </div>
                                {/* Plagiarism Stats */}
                                <div>
                                  <div
                                    style={{
                                      color: "var(--text-muted)",
                                      fontSize: "0.8rem",
                                      marginBottom: "4px",
                                    }}
                                  >
                                    <Icon
                                      name="Copy"
                                      size={12}
                                      style={{
                                        marginRight: "4px",
                                        verticalAlign: "middle",
                                      }}
                                    />
                                    Plagiarism
                                  </div>
                                  <div style={{ display: "flex", gap: "10px" }}>
                                    {authStats.plagLikely > 0 && (
                                      <span style={{ color: "#f87171" }}>
                                        {authStats.plagLikely} likely
                                      </span>
                                    )}
                                    {authStats.plagPossible > 0 && (
                                      <span style={{ color: "#fbbf24" }}>
                                        {authStats.plagPossible} possible
                                      </span>
                                    )}
                                    {authStats.plagLikely === 0 &&
                                      authStats.plagPossible === 0 && (
                                        <span style={{ color: "#4ade80" }}>
                                          All clear
                                        </span>
                                      )}
                                  </div>
                                </div>
                              </div>
                            </div>
                            <div
                              style={{
                                fontSize: "0.85rem",
                                color: "var(--text-secondary)",
                              }}
                            >
                              Hover for details
                            </div>
                          </div>
                        ) : null;
}
