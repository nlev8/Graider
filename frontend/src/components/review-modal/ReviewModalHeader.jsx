import React from "react";
import Icon from "../Icon";

export default function ReviewModalHeader(props) {
  const { editedResults, reviewModal, setReviewModal, status } = props;
  return (
          <div
            style={{
              padding: "20px 30px",
              borderBottom: "1px solid var(--glass-border)",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            <div>
              <h2 style={{ fontSize: "1.4rem", fontWeight: 700, margin: 0 }}>
                Review:{" "}
                {
                  (
                    editedResults[reviewModal.index] ||
                    status.results[reviewModal.index]
                  )?.student_name
                }
              </h2>
              <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", margin: "4px 0 0 0" }}>
                {
                  (
                    editedResults[reviewModal.index] ||
                    status.results[reviewModal.index]
                  )?.assignment ||
                  (
                    editedResults[reviewModal.index] ||
                    status.results[reviewModal.index]
                  )?.filename
                }
              </p>
            </div>
            <button
              onClick={() => setReviewModal({ show: false, index: -1 })}
              style={{
                background: "var(--glass-bg)",
                border: "1px solid var(--glass-border)",
                borderRadius: "8px",
                padding: "8px",
                color: "var(--text-secondary)",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                transition: "all 0.2s",
              }}
              onMouseEnter={(e) =>
                (e.currentTarget.style.background = "var(--glass-hover)")
              }
              onMouseLeave={(e) =>
                (e.currentTarget.style.background = "var(--glass-bg)")
              }
            >
              <Icon name="X" size={20} />
            </button>
          </div>
  );
}
