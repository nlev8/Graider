import React from "react";
import Icon from "../../components/Icon";

/*
 * Manual marker input row — relocated verbatim from BuilderTab.jsx
 * (CQ wave-9 split).
 */
export default function ManualMarkerInput({ assignment, setAssignment }) {
  return (
    <div
      style={{
        marginTop: "15px",
        display: "flex",
        gap: "10px",
        alignItems: "center",
      }}
    >
      <input
        type="text"
        id="manualMarkerInput"
        placeholder="Type a marker phrase and press Add..."
        className="input"
        style={{ flex: 1 }}
        onKeyDown={(e) => {
          if (e.key === "Enter" && e.target.value.trim()) {
            const newMarker = e.target.value.trim();
            if (
              !(assignment.customMarkers || []).includes(
                newMarker,
              )
            ) {
              setAssignment({
                ...assignment,
                customMarkers: [
                  ...(assignment.customMarkers || []),
                  newMarker,
                ],
              });
            }
            e.target.value = "";
          }
        }}
      />
      <button
        onClick={() => {
          const input =
            document.getElementById("manualMarkerInput");
          if (input?.value.trim()) {
            const newMarker = input.value.trim();
            if (
              !(assignment.customMarkers || []).includes(
                newMarker,
              )
            ) {
              setAssignment({
                ...assignment,
                customMarkers: [
                  ...(assignment.customMarkers || []),
                  newMarker,
                ],
              });
            }
            input.value = "";
          }
        }}
        className="btn btn-secondary"
      >
        <Icon name="Plus" size={16} />
        Add
      </button>
    </div>
  );
}
