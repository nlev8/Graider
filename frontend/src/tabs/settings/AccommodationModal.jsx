import React from "react";
import Icon from "../../components/Icon";
import * as api from "../../services/api";
import AccommodationStudentPicker from "./AccommodationStudentPicker";
import AccommodationPresetPicker from "./AccommodationPresetPicker";

/*
 * AccommodationModal — the IEP/504 accommodation assignment modal, relocated
 * verbatim from SettingsTab.jsx (CQ wave-9 split) apart from three inner
 * blocks that moved out unchanged: the student picker
 * (./AccommodationStudentPicker), the preset picker
 * (./AccommodationPresetPicker), and the save handler
 * (createSaveAccommodations below — a factory recreated each render exactly
 * like the original inline arrow). The `{accommodationModal.show && ...}`
 * guard became the early return below.
 */

// Save-handler factory: returns the async onClick relocated verbatim from the
// original inline `onClick={async () => {...}}` (SettingsTab.jsx@main).
function createSaveAccommodations({
  accommodationModal,
  accommSelectedStudents,
  selectedAccommodationPresets,
  accommodationCustomNotes,
  accommEllLanguage,
  addToast,
  setStudentAccommodations,
  setAccommodationModal,
  setSelectedAccommodationPresets,
  setAccommodationCustomNotes,
  setAccommEllLanguage,
  setAccommSelectedStudents,
  setAccommPeriodFilter,
  setAccommStudentsList,
}) {
  return async () => {
                  // Single edit mode vs multi-select mode
                  const studentIds = accommodationModal.studentId
                    ? [accommodationModal.studentId]
                    : Object.keys(accommSelectedStudents);

                  if (studentIds.length === 0) {
                    addToast(
                      "Please select at least one student",
                      "warning",
                    );
                    return;
                  }

                  if (
                    selectedAccommodationPresets.length === 0 &&
                    !accommodationCustomNotes
                  ) {
                    addToast(
                      "Please select at least one preset or add custom notes",
                      "warning",
                    );
                    return;
                  }

                  try {
                    // Save accommodation for each selected student
                    for (const sid of studentIds) {
                      const name =
                        accommSelectedStudents[sid] || "";
                      await api.setStudentAccommodation(
                        sid,
                        selectedAccommodationPresets,
                        accommodationCustomNotes,
                        name,
                      );
                    }

                    // Save ELL language if ELL Support selected
                    if (
                      selectedAccommodationPresets.includes(
                        "ell_support",
                      ) &&
                      accommEllLanguage
                    ) {
                      try {
                        const existing =
                          await api.getEllStudents();
                        const ellData =
                          existing && typeof existing === "object"
                            ? existing
                            : {};
                        for (const sid of studentIds) {
                          ellData[sid] = {
                            student_name:
                              accommSelectedStudents[sid] || sid,
                            language: accommEllLanguage,
                          };
                        }
                        await api.saveEllStudents(ellData);
                      } catch (ellErr) {
                        // Non-blocking
                      }
                    }

                    // If editing single student & ELL Support removed, clear ELL entry
                    if (
                      accommodationModal.studentId &&
                      !selectedAccommodationPresets.includes(
                        "ell_support",
                      )
                    ) {
                      try {
                        const existing =
                          await api.getEllStudents();
                        if (
                          existing &&
                          existing[accommodationModal.studentId]
                        ) {
                          delete existing[
                            accommodationModal.studentId
                          ];
                          await api.saveEllStudents(existing);
                        }
                      } catch (ellErr) {
                        // Non-blocking
                      }
                    }

                    // Reload accommodations
                    const data = await api.getStudentAccommodations();
                    if (data.accommodations)
                      setStudentAccommodations(data.accommodations);

                    addToast(
                      studentIds.length +
                        " student(s) updated",
                      "success",
                    );
                    setAccommodationModal({
                      show: false,
                      studentId: null,
                    });
                    setSelectedAccommodationPresets([]);
                    setAccommodationCustomNotes("");
                    setAccommEllLanguage("");
                    setAccommSelectedStudents({});
                    setAccommPeriodFilter("");
                    setAccommStudentsList([]);
                  } catch (err) {
                    addToast(
                      "Error saving accommodation: " + err.message,
                      "error",
                    );
                  }
  };
}

export default function AccommodationModal(props) {
  const {
    accommodationModal, setAccommodationModal,
    accommEllLanguage, setAccommEllLanguage,
    accommPeriodFilter, setAccommPeriodFilter,
    accommSelectedStudents, setAccommSelectedStudents,
    accommStudentsList, setAccommStudentsList,
    accommodationCustomNotes, setAccommodationCustomNotes,
    selectedAccommodationPresets, setSelectedAccommodationPresets,
    accommodationPresets, sortedPeriods, setStudentAccommodations, addToast,
  } = props;

  const saveAccommodations = createSaveAccommodations({
    accommodationModal,
    accommSelectedStudents,
    selectedAccommodationPresets,
    accommodationCustomNotes,
    accommEllLanguage,
    addToast,
    setStudentAccommodations,
    setAccommodationModal,
    setSelectedAccommodationPresets,
    setAccommodationCustomNotes,
    setAccommEllLanguage,
    setAccommSelectedStudents,
    setAccommPeriodFilter,
    setAccommStudentsList,
  });

  if (!accommodationModal.show) return null;

  return (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "var(--modal-bg)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
          }}
        >
          <div
            className="glass-card"
            style={{
              width: "90%",
              maxWidth: "500px",
              maxHeight: "80vh",
              overflow: "auto",
              padding: "25px",
            }}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginBottom: "20px",
              }}
            >
              <h3
                style={{
                  fontSize: "1.2rem",
                  fontWeight: 700,
                  display: "flex",
                  alignItems: "center",
                  gap: "10px",
                }}
              >
                <Icon
                  name="Heart"
                  size={22}
                  style={{ color: "#f472b6" }}
                />
                {accommodationModal.studentId
                  ? "Edit Accommodations"
                  : "Add Student Accommodations"}
              </h3>
              <button
                onClick={() => {
                  setAccommodationModal({
                    show: false,
                    studentId: null,
                  });
                  setSelectedAccommodationPresets([]);
                  setAccommodationCustomNotes("");
                  setAccommEllLanguage("");
                  setAccommSelectedStudents({});

                  setAccommPeriodFilter("");
                  setAccommStudentsList([]);
                }}
                style={{
                  background: "none",
                  border: "none",
                  color: "var(--text-primary)",
                  cursor: "pointer",
                }}
              >
                <Icon name="X" size={24} />
              </button>
            </div>

            <p
              style={{
                fontSize: "0.85rem",
                color: "var(--text-secondary)",
                marginBottom: "20px",
                padding: "10px",
                background: "rgba(74, 222, 128, 0.1)",
                borderRadius: "8px",
                border: "1px solid rgba(74, 222, 128, 0.2)",
              }}
            >
              <Icon
                name="Shield"
                size={14}
                style={{ color: "#4ade80", marginRight: "6px" }}
              />
              FERPA Compliant: Only accommodation types are sent to AI,
              never student names or IDs.
            </p>

            {/* Student Selection (for new students) — ./AccommodationStudentPicker */}
            <AccommodationStudentPicker
              accommodationModal={accommodationModal}
              accommPeriodFilter={accommPeriodFilter}
              setAccommPeriodFilter={setAccommPeriodFilter}
              accommSelectedStudents={accommSelectedStudents}
              setAccommSelectedStudents={setAccommSelectedStudents}
              accommStudentsList={accommStudentsList}
              setAccommStudentsList={setAccommStudentsList}
              sortedPeriods={sortedPeriods}
            />

            {/* Preset Selection — ./AccommodationPresetPicker */}
            <AccommodationPresetPicker
              accommodationPresets={accommodationPresets}
              selectedAccommodationPresets={selectedAccommodationPresets}
              setSelectedAccommodationPresets={setSelectedAccommodationPresets}
            />

            {/* ELL Language selector — shown when ELL Support preset is selected */}
            {selectedAccommodationPresets.includes("ell_support") && (
              <div style={{ marginBottom: "20px" }}>
                <label className="label">
                  Home Language (for bilingual feedback)
                </label>
                <select
                  className="input"
                  value={accommEllLanguage}
                  onChange={(e) =>
                    setAccommEllLanguage(e.target.value)
                  }
                >
                  <option value="">English only (no translation)</option>
                  <option value="spanish">Spanish</option>
                  <option value="portuguese">Portuguese</option>
                  <option value="haitian creole">Haitian Creole</option>
                  <option value="french">French</option>
                  <option value="arabic">Arabic</option>
                  <option value="chinese (simplified)">Chinese (Simplified)</option>
                  <option value="chinese (traditional)">Chinese (Traditional)</option>
                  <option value="vietnamese">Vietnamese</option>
                  <option value="korean">Korean</option>
                  <option value="tagalog">Tagalog</option>
                  <option value="russian">Russian</option>
                  <option value="hindi">Hindi</option>
                  <option value="urdu">Urdu</option>
                  <option value="bengali">Bengali</option>
                  <option value="japanese">Japanese</option>
                  <option value="german">German</option>
                  <option value="italian">Italian</option>
                  <option value="polish">Polish</option>
                  <option value="somali">Somali</option>
                  <option value="swahili">Swahili</option>
                  <option value="burmese">Burmese</option>
                  <option value="nepali">Nepali</option>
                  <option value="gujarati">Gujarati</option>
                  <option value="amharic">Amharic</option>
                </select>
                <p
                  style={{
                    fontSize: "0.75rem",
                    color: "var(--text-muted)",
                    marginTop: "6px",
                  }}
                >
                  If set, feedback will be provided in both English and
                  the selected language.
                </p>
              </div>
            )}

            {/* Custom Notes */}
            <div style={{ marginBottom: "20px" }}>
              <label className="label">
                Additional Notes (Optional)
              </label>
              <textarea
                className="input"
                value={accommodationCustomNotes}
                onChange={(e) =>
                  setAccommodationCustomNotes(e.target.value)
                }
                placeholder="Any additional accommodation instructions..."
                style={{ minHeight: "80px", resize: "vertical" }}
              />
              <p
                style={{
                  fontSize: "0.75rem",
                  color: "var(--text-muted)",
                  marginTop: "6px",
                }}
              >
                These notes will be included in AI grading instructions
                (without student identity).
              </p>
            </div>

            {/* Actions */}
            <div
              style={{
                display: "flex",
                gap: "10px",
                justifyContent: "flex-end",
              }}
            >
              <button
                onClick={saveAccommodations}
                className="btn btn-primary"
              >
                <Icon name="Save" size={18} />
                Save Accommodations
              </button>
              <button
                onClick={() => {
                  setAccommodationModal({
                    show: false,
                    studentId: null,
                  });
                  setSelectedAccommodationPresets([]);
                  setAccommodationCustomNotes("");
                  setAccommEllLanguage("");
                  setAccommSelectedStudents({});

                  setAccommPeriodFilter("");
                  setAccommStudentsList([]);
                }}
                className="btn btn-secondary"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
  );
}
