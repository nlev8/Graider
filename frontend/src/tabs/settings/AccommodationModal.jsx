import React from "react";
import Icon from "../../components/Icon";
import * as api from "../../services/api";
import AccommodationStudentPicker from "./AccommodationStudentPicker";
import AccommodationPresetPicker from "./AccommodationPresetPicker";
import AccommodationModalFooter from "./AccommodationModalFooter";

/*
 * AccommodationModal — the IEP/504 accommodation assignment modal, relocated
 * verbatim from SettingsTab.jsx (CQ wave-9 split) apart from three inner
 * blocks that moved out unchanged: the student picker
 * (./AccommodationStudentPicker), the preset picker
 * (./AccommodationPresetPicker), and the save handler
 * (createSaveAccommodations below — a factory recreated each render exactly
 * like the original inline arrow). The `{accommodationModal.show && ...}`
 * guard became the early return below.
 *
 * CQ wave-8 split (#cq8-05): ELL language selector + custom notes + action
 * buttons extracted into ./AccommodationModalFooter (pure-prop child).
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

  const handleClose = () => {
    setAccommodationModal({ show: false, studentId: null });
    setSelectedAccommodationPresets([]);
    setAccommodationCustomNotes("");
    setAccommEllLanguage("");
    setAccommSelectedStudents({});
    setAccommPeriodFilter("");
    setAccommStudentsList([]);
  };

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
                onClick={handleClose}
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

            {/* ELL selector + custom notes + actions — ./AccommodationModalFooter */}
            <AccommodationModalFooter
              selectedAccommodationPresets={selectedAccommodationPresets}
              accommEllLanguage={accommEllLanguage}
              setAccommEllLanguage={setAccommEllLanguage}
              accommodationCustomNotes={accommodationCustomNotes}
              setAccommodationCustomNotes={setAccommodationCustomNotes}
              onSave={saveAccommodations}
              onCancel={handleClose}
            />
          </div>
        </div>
  );
}
