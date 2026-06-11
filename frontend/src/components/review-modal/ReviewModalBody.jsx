import React from "react";
import SubmissionPanel from "./SubmissionPanel";
import ReviewPanel from "./ReviewPanel";

export default function ReviewModalBody(props) {
  const { editedResults, reviewModal, status } = props;
  // `r` is the resolved per-result object (edited-or-status), computed ONCE
  // here — it is NOT an App-level prop, so it must be injected explicitly
  // AFTER the {...props} spread below. Do not "simplify" the children to a
  // bare {...props}: that would silently feed r=undefined.
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
