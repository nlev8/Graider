import React from "react";
import Icon from "../Icon";
import * as api from "../../services/api";

export default function AccommodationStudentEntries({ addToast, setAccommEllLanguage, setAccommodationCustomNotes, setAccommodationModal, setSelectedAccommodationPresets, setStudentAccommodations, studentAccommodations }) {
  if (Object.keys(studentAccommodations).length > 0) {
    return (
      <div
        style={{
          maxHeight: "200px",
          overflowY: "auto",
          display: "flex",
          flexDirection: "column",
          gap: "8px",
        }}
      >
        {Object.entries(studentAccommodations).map(
          ([studentId, data]) => (
            <div
              key={studentId}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "10px 14px",
                background: "var(--input-bg)",
                borderRadius: "8px",
                border: "1px solid var(--input-border)",
              }}
            >
              <div>
                <div
                  style={{
                    fontWeight: 600,
                    fontSize: "0.9rem",
                  }}
                >
                  {data.student_name || "ID: " + studentId}
                </div>
                <div
                  style={{
                    display: "flex",
                    gap: "6px",
                    marginTop: "4px",
                    flexWrap: "wrap",
                  }}
                >
                  {data.presets.map((preset) => (
                    <span
                      key={preset.id}
                      style={{
                        padding: "2px 8px",
                        background:
                          preset.id === "ell_support"
                            ? "rgba(96, 165, 250, 0.15)"
                            : "rgba(244, 114, 182, 0.15)",
                        color:
                          preset.id === "ell_support"
                            ? "#60a5fa"
                            : "#f472b6",
                        borderRadius: "4px",
                        fontSize: "0.7rem",
                        fontWeight: 500,
                      }}
                    >
                      {preset.name}
                    </span>
                  ))}
                  {data.custom_notes && (
                    <span
                      style={{
                        padding: "2px 8px",
                        background:
                          "rgba(99, 102, 241, 0.15)",
                        color: "#818cf8",
                        borderRadius: "4px",
                        fontSize: "0.7rem",
                        fontWeight: 500,
                      }}
                    >
                      Custom Notes
                    </span>
                  )}
                </div>
              </div>
              <div style={{ display: "flex", gap: "6px" }}>
                <button
                  onClick={async () => {
                    setSelectedAccommodationPresets(
                      data.presets.map((p) => p.id),
                    );
                    setAccommodationCustomNotes(
                      data.custom_notes || "",
                    );
                    // Load ELL language if ELL Support is active
                    if (
                      data.presets.some(
                        (p) => p.id === "ell_support",
                      )
                    ) {
                      try {
                        const ellData =
                          await api.getEllStudents();
                        setAccommEllLanguage(
                          ellData?.[studentId]?.language ||
                            "",
                        );
                      } catch (e) {
                        setAccommEllLanguage("");
                      }
                    } else {
                      setAccommEllLanguage("");
                    }
                    setAccommodationModal({
                      show: true,
                      studentId,
                    });
                  }}
                  className="btn btn-secondary"
                  style={{ padding: "4px 8px" }}
                >
                  <Icon name="Edit2" size={14} />
                </button>
                <button
                  onClick={async () => {
                    if (
                      confirm(
                        "Remove accommodations for this student?",
                      )
                    ) {
                      try {
                        await api.deleteStudentAccommodation(
                          studentId,
                        );
                        const newData = {
                          ...studentAccommodations,
                        };
                        delete newData[studentId];
                        setStudentAccommodations(newData);
                      } catch (err) {
                        addToast(
                          "Error removing accommodation: " +
                            err.message,
                          "error",
                        );
                      }
                    }
                  }}
                  className="btn btn-secondary"
                  style={{
                    padding: "4px 8px",
                    color: "#ef4444",
                  }}
                >
                  <Icon name="Trash2" size={14} />
                </button>
              </div>
            </div>
          ),
        )}
      </div>
    );
  }
  return (
    <div
      style={{
        padding: "30px",
        textAlign: "center",
        background: "var(--input-bg)",
        borderRadius: "8px",
        border: "1px dashed var(--input-border)",
      }}
    >
      <Icon
        name="Heart"
        size={32}
        style={{
          color: "var(--text-muted)",
          marginBottom: "10px",
        }}
      />
      <p
        style={{
          color: "var(--text-muted)",
          fontSize: "0.85rem",
          margin: 0,
        }}
      >
        No students with accommodations yet. Add students
        from your roster.
      </p>
    </div>
  );
}
