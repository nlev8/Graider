import React from "react";
import Icon from "../Icon";

export default function PrivacyFeaturesSection() {
  return (
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(2, 1fr)",
                  gap: "15px",
                  marginBottom: "20px",
                }}
              >
                <div
                  style={{
                    padding: "15px",
                    background: "rgba(74,222,128,0.1)",
                    borderRadius: "10px",
                    border: "1px solid rgba(74,222,128,0.2)",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "8px",
                      marginBottom: "8px",
                    }}
                  >
                    <Icon
                      name="CheckCircle"
                      size={16}
                      style={{ color: "#4ade80" }}
                    />
                    <span
                      style={{ fontWeight: 600, fontSize: "0.9rem" }}
                    >
                      PII Sanitization
                    </span>
                  </div>
                  <p
                    style={{
                      fontSize: "0.8rem",
                      color: "var(--text-secondary)",
                      margin: 0,
                    }}
                  >
                    Student names, IDs, emails, and phone numbers are
                    removed before AI processing
                  </p>
                </div>

                <div
                  style={{
                    padding: "15px",
                    background: "rgba(74,222,128,0.1)",
                    borderRadius: "10px",
                    border: "1px solid rgba(74,222,128,0.2)",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "8px",
                      marginBottom: "8px",
                    }}
                  >
                    <Icon
                      name="CheckCircle"
                      size={16}
                      style={{ color: "#4ade80" }}
                    />
                    <span
                      style={{ fontWeight: 600, fontSize: "0.9rem" }}
                    >
                      No Third-Party Sharing
                    </span>
                  </div>
                  <p
                    style={{
                      fontSize: "0.8rem",
                      color: "var(--text-secondary)",
                      margin: 0,
                    }}
                  >
                    Student data is never sold, shared with vendors, or
                    aggregated across districts
                  </p>
                </div>

                <div
                  style={{
                    padding: "15px",
                    background: "rgba(74,222,128,0.1)",
                    borderRadius: "10px",
                    border: "1px solid rgba(74,222,128,0.2)",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "8px",
                      marginBottom: "8px",
                    }}
                  >
                    <Icon
                      name="CheckCircle"
                      size={16}
                      style={{ color: "#4ade80" }}
                    />
                    <span
                      style={{ fontWeight: 600, fontSize: "0.9rem" }}
                    >
                      No AI Training
                    </span>
                  </div>
                  <p
                    style={{
                      fontSize: "0.8rem",
                      color: "var(--text-secondary)",
                      margin: 0,
                    }}
                  >
                    OpenAI and Anthropic APIs do not use submitted data
                    to train models (per their policies)
                  </p>
                </div>

                <div
                  style={{
                    padding: "15px",
                    background: "rgba(74,222,128,0.1)",
                    borderRadius: "10px",
                    border: "1px solid rgba(74,222,128,0.2)",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "8px",
                      marginBottom: "8px",
                    }}
                  >
                    <Icon
                      name="CheckCircle"
                      size={16}
                      style={{ color: "#4ade80" }}
                    />
                    <span
                      style={{ fontWeight: 600, fontSize: "0.9rem" }}
                    >
                      Audit Logging
                    </span>
                  </div>
                  <p
                    style={{
                      fontSize: "0.8rem",
                      color: "var(--text-secondary)",
                      margin: 0,
                    }}
                  >
                    All data access is logged for compliance
                    tracking and FERPA audit trails
                  </p>
                </div>
              </div>
  );
}
