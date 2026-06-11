import React from "react";
import SubmissionPanel from "./SubmissionPanel";
import ReviewPanel from "./ReviewPanel";

export default function ReviewModalBody(props) {
  const { editedResults, reviewModal, status } = props;
  const r =
    editedResults[reviewModal.index] ||
    status.results[reviewModal.index];
  if (!r) return null;
  return (
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "1fr 1fr",
                    gap: "30px",
                    height: "100%",
                  }}
                >
                  <SubmissionPanel {...props} r={r} />
                  <ReviewPanel {...props} r={r} />
                </div>
  );
}
