import React from "react";
import Icon from "../Icon";
import GradeFeedbackTab from "./GradeFeedbackTab";
import EmailPreviewTab from "./EmailPreviewTab";

export default function ReviewPanel(props) {
  const { reviewModalRightTab, setReviewModalRightTab } = props;
  return (
                  <div
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      height: "100%",
                      background: "var(--glass-bg)",
                      borderRadius: "16px",
                      border: "1px solid var(--glass-border)",
                      overflow: "hidden",
                    }}
                  >
                    {/* Right Panel Header with Tabs */}
                    <div
                      style={{
                        padding: "16px 20px",
                        borderBottom: "1px solid var(--glass-border)",
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                      }}
                    >
                      <div style={{ display: "flex", gap: "8px" }}>
                        <button
                          onClick={() => setReviewModalRightTab("edit")}
                          style={{
                            padding: "8px 16px",
                            borderRadius: "8px",
                            border: "none",
                            background:
                              reviewModalRightTab === "edit"
                                ? "linear-gradient(135deg, var(--accent-primary), var(--accent-secondary))"
                                : "var(--glass-hover)",
                            color:
                              reviewModalRightTab === "edit"
                                ? "#fff"
                                : "var(--text-secondary)",
                            fontWeight: 600,
                            fontSize: "0.85rem",
                            cursor: "pointer",
                            transition: "all 0.2s",
                            display: "flex",
                            alignItems: "center",
                            gap: "6px",
                          }}
                        >
                          <Icon name="Award" size={14} />
                          Grade & Feedback
                        </button>
                        <button
                          onClick={() => setReviewModalRightTab("email")}
                          style={{
                            padding: "8px 16px",
                            borderRadius: "8px",
                            border: "none",
                            background:
                              reviewModalRightTab === "email"
                                ? "linear-gradient(135deg, var(--accent-primary), var(--accent-secondary))"
                                : "var(--glass-hover)",
                            color:
                              reviewModalRightTab === "email"
                                ? "#fff"
                                : "var(--text-secondary)",
                            fontWeight: 600,
                            fontSize: "0.85rem",
                            cursor: "pointer",
                            transition: "all 0.2s",
                            display: "flex",
                            alignItems: "center",
                            gap: "6px",
                          }}
                        >
                          <Icon name="Mail" size={14} />
                          Email Preview
                        </button>
                      </div>
                    </div>

                    {/* Right Panel Content */}
                    {reviewModalRightTab === "edit" ? (
                      <GradeFeedbackTab {...props} />
                    ) : (
                      <EmailPreviewTab {...props} />
                    )}
                  </div>
  );
}
