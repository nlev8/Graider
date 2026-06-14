import React from "react";
import Icon from "../Icon";
import AccommodationsImportExport from "./AccommodationsImportExport";
import AccommodationStudentEntries from "./AccommodationStudentEntries";

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
              <AccommodationsImportExport
                addToast={addToast}
                setStudentAccommodations={setStudentAccommodations}
              />
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

                <AccommodationStudentEntries
                  addToast={addToast}
                  setAccommEllLanguage={setAccommEllLanguage}
                  setAccommodationCustomNotes={setAccommodationCustomNotes}
                  setAccommodationModal={setAccommodationModal}
                  setSelectedAccommodationPresets={setSelectedAccommodationPresets}
                  setStudentAccommodations={setStudentAccommodations}
                  studentAccommodations={studentAccommodations}
                />
              </div>
  );
}
