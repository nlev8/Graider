import React from "react";
import Icon from "../Icon";
import * as api from "../../services/api";

export default function AccommodationsSection(props) {
  const { accommodationPresets, addToast, setStudentAccommodations } = props;
  return (
            <div
              style={{
                borderTop: "1px solid var(--glass-border)",
                paddingTop: "25px",
                marginTop: "25px",
              }}
            >
              <h3
                style={{
                  fontSize: "1.1rem",
                  fontWeight: 700,
                  marginBottom: "15px",
                  display: "flex",
                  alignItems: "center",
                  gap: "10px",
                }}
              >
                <Icon
                  name="Heart"
                  size={20}
                  style={{ color: "#f472b6" }}
                />
                IEP/504 Accommodations
                <span
                  style={{
                    fontSize: "0.7rem",
                    padding: "2px 8px",
                    background: "rgba(74, 222, 128, 0.2)",
                    color: "#4ade80",
                    borderRadius: "4px",
                    fontWeight: 500,
                  }}
                >
                  FERPA Compliant
                </span>
              </h3>
              <p
                style={{
                  fontSize: "0.85rem",
                  color: "var(--text-secondary)",
                  marginBottom: "20px",
                }}
              >
                Assign accommodation presets to students for
                personalized feedback. Only accommodation types are sent
                to AI - never student names or IDs.
              </p>

              {/* Available Presets */}
              <div style={{ marginBottom: "20px" }}>
                <div
                  style={{
                    fontWeight: 600,
                    marginBottom: "12px",
                    fontSize: "0.95rem",
                  }}
                >
                  Available Presets
                </div>
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns:
                      "repeat(auto-fill, minmax(200px, 1fr))",
                    gap: "10px",
                  }}
                >
                  {accommodationPresets.map((preset) => (
                    <div
                      key={preset.id}
                      style={{
                        padding: "12px",
                        background: "var(--input-bg)",
                        borderRadius: "8px",
                        border: "1px solid var(--input-border)",
                      }}
                    >
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: "8px",
                          marginBottom: "6px",
                        }}
                      >
                        <Icon
                          name={preset.icon || "FileText"}
                          size={16}
                          style={{ color: "#f472b6" }}
                        />
                        <span
                          style={{
                            fontWeight: 600,
                            fontSize: "0.85rem",
                          }}
                        >
                          {preset.name}
                        </span>
                      </div>
                      <p
                        style={{
                          fontSize: "0.75rem",
                          color: "var(--text-muted)",
                          margin: 0,
                        }}
                      >
                        {preset.description}
                      </p>
                    </div>
                  ))}
                </div>
              </div>

              {/* Student Accommodations List */}
              <AccommodationStudentList {...props} />

              {/* Import/Export */}
              <div
                style={{
                  padding: "15px",
                  background: "var(--input-bg)",
                  borderRadius: "10px",
                  border: "1px solid var(--input-border)",
                }}
              >
                <div style={{ fontWeight: 600, marginBottom: "12px" }}>
                  Import & Export
                </div>
                <div
                  style={{
                    display: "flex",
                    gap: "10px",
                    flexWrap: "wrap",
                  }}
                >
                  <label
                    className="btn btn-secondary"
                    style={{ fontSize: "0.85rem", cursor: "pointer" }}
                  >
                    <Icon name="Upload" size={16} />
                    Import from CSV
                    <input
                      type="file"
                      accept=".csv"
                      style={{ display: "none" }}
                      onChange={async (e) => {
                        const file = e.target.files?.[0];
                        if (!file) return;
                        try {
                          const result = await api.importAccommodations(
                            file,
                            "student_id",
                            "accommodation_type",
                            "accommodation_notes",
                          );
                          addToast(
                            "Import complete: " +
                              result.imported +
                              " imported, " +
                              result.skipped +
                              " skipped",
                            "success",
                          );
                          // Reload accommodations
                          const data =
                            await api.getStudentAccommodations();
                          if (data.accommodations)
                            setStudentAccommodations(
                              data.accommodations,
                            );
                        } catch (err) {
                          addToast(
                            "Import failed: " + err.message,
                            "error",
                          );
                        }
                        e.target.value = "";
                      }}
                    />
                  </label>
                  <button
                    onClick={async () => {
                      try {
                        const data = await api.exportAccommodations();
                        const blob = new Blob(
                          [JSON.stringify(data, null, 2)],
                          { type: "application/json" },
                        );
                        const url = URL.createObjectURL(blob);
                        const a = document.createElement("a");
                        a.href = url;
                        a.download =
                          "graider_accommodations_" +
                          new Date().toISOString().split("T")[0] +
                          ".json";
                        a.click();
                        URL.revokeObjectURL(url);
                      } catch (err) {
                        addToast(
                          "Export failed: " + err.message,
                          "error",
                        );
                      }
                    }}
                    className="btn btn-secondary"
                    style={{ fontSize: "0.85rem" }}
                  >
                    <Icon name="Download" size={16} />
                    Export Accommodations
                  </button>
                </div>
                <p
                  style={{
                    fontSize: "0.75rem",
                    color: "var(--text-muted)",
                    marginTop: "10px",
                  }}
                >
                  CSV should have columns: student_id,
                  accommodation_type, accommodation_notes (optional)
                </p>
              </div>
            </div>
  );
}

function AccommodationStudentList({ addToast, setAccommEllLanguage, setAccommodationCustomNotes, setAccommodationModal, setSelectedAccommodationPresets, setStudentAccommodations, studentAccommodations }) {
  return (
              <div style={{ marginBottom: "20px" }}>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    marginBottom: "12px",
                  }}
                >
                  <div style={{ fontWeight: 600, fontSize: "0.95rem" }}>
                    Student Accommodations (
                    {Object.keys(studentAccommodations).length}{" "}
                    students)
                  </div>
                  <button
                    onClick={() =>
                      setAccommodationModal({
                        show: true,
                        studentId: null,
                      })
                    }
                    className="btn btn-primary"
                    style={{ fontSize: "0.8rem", padding: "6px 12px" }}
                  >
                    <Icon name="Plus" size={14} />
                    Add Student
                  </button>
                </div>

                {Object.keys(studentAccommodations).length > 0 ? (
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
                ) : (
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
                )}
              </div>
  );
}
