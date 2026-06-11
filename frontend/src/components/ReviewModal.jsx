import React from "react";
import ReviewModalHeader from "./review-modal/ReviewModalHeader";
import ReviewModalBody from "./review-modal/ReviewModalBody";

export default function ReviewModal(props) {
  const { setReviewModal } = props;
  return (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: "var(--modal-content-bg)",
            zIndex: 1000,
            display: "flex",
            flexDirection: "column",
          }}
        >
          <ReviewModalHeader {...props} />
          <div style={{ flex: 1, overflow: "hidden", padding: "25px 30px" }}>
            <ReviewModalBody {...props} />
          </div>
          <div
            style={{
              padding: "20px 30px",
              borderTop: "1px solid var(--glass-border)",
              display: "flex",
              gap: "12px",
              justifyContent: "flex-end",
            }}
          >
            <button
              onClick={() => setReviewModal({ show: false, index: -1 })}
              className="btn btn-primary"
              style={{ padding: "10px 24px" }}
            >
              Done
            </button>
          </div>
        </div>
  );
}
