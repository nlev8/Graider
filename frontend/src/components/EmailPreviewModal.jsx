import React from "react";
import Icon from "./Icon";

export default function EmailPreviewModal({ emailPreview, sendEmails, setEmailPreview }) {
  return (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: "var(--modal-bg)",
            zIndex: 1000,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: "20px",
          }}
        >
          <div
            style={{
              background: "var(--modal-content-bg)",
              borderRadius: "20px",
              border: "1px solid var(--glass-border)",
              width: "100%",
              maxWidth: "800px",
              maxHeight: "90vh",
              overflow: "hidden",
              display: "flex",
              flexDirection: "column",
            }}
          >
            <div
              style={{
                padding: "20px 25px",
                borderBottom: "1px solid var(--glass-border)",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
              }}
            >
              <h2
                style={{
                  fontSize: "1.3rem",
                  fontWeight: 700,
                  display: "flex",
                  alignItems: "center",
                  gap: "10px",
                }}
              >
                <Icon name="Mail" size={24} />
                Email Preview ({emailPreview.emails.length} students)
              </h2>
              <button
                onClick={() => setEmailPreview({ show: false, emails: [] })}
                style={{
                  background: "none",
                  border: "none",
                  color: "var(--text-secondary)",
                  cursor: "pointer",
                }}
              >
                <Icon name="X" size={24} />
              </button>
            </div>
            <div style={{ flex: 1, overflowY: "auto", padding: "20px" }}>
              {emailPreview.emails.map((email, i) => (
                <div
                  key={i}
                  style={{
                    background: "var(--glass-bg)",
                    borderRadius: "12px",
                    border: "1px solid var(--glass-border)",
                    marginBottom: "15px",
                    overflow: "hidden",
                  }}
                >
                  <div
                    style={{
                      padding: "15px 20px",
                      borderBottom: "1px solid var(--table-row-border)",
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                    }}
                  >
                    <div>
                      <div style={{ fontWeight: 600, marginBottom: "4px" }}>
                        {email.name}
                      </div>
                      <div
                        style={{
                          fontSize: "0.85rem",
                          color: "var(--text-muted)",
                        }}
                      >
                        {email.to}
                      </div>
                    </div>
                    <span
                      style={{
                        background: "rgba(99,102,241,0.2)",
                        color: "var(--accent-light)",
                        padding: "4px 12px",
                        borderRadius: "20px",
                        fontSize: "0.8rem",
                      }}
                    >
                      {email.assignments} assignment
                      {email.assignments > 1 ? "s" : ""}
                    </span>
                  </div>
                  <div style={{ padding: "15px 20px" }}>
                    <div
                      style={{
                        fontSize: "0.9rem",
                        color: "var(--accent-light)",
                        marginBottom: "10px",
                      }}
                    >
                      <strong>Subject:</strong> {email.subject}
                    </div>
                    <div
                      style={{
                        fontSize: "0.85rem",
                        color: "var(--text-secondary)",
                        whiteSpace: "pre-wrap",
                        maxHeight: "150px",
                        overflowY: "auto",
                        background: "var(--input-bg)",
                        padding: "12px",
                        borderRadius: "8px",
                        fontFamily: "monospace",
                      }}
                    >
                      {email.body}
                    </div>
                  </div>
                </div>
              ))}
            </div>
            <div
              style={{
                padding: "20px 25px",
                borderTop: "1px solid var(--glass-border)",
                display: "flex",
                gap: "15px",
                justifyContent: "flex-end",
              }}
            >
              <button
                onClick={() => setEmailPreview({ show: false, emails: [] })}
                className="btn btn-secondary"
              >
                Cancel
              </button>
              <button onClick={sendEmails} className="btn btn-primary">
                <Icon name="Send" size={18} />
                Send All Emails
              </button>
            </div>
          </div>
        </div>
  );
}
