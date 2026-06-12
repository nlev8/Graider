import React from "react";
import RosterMappingModal from "./RosterMappingModal";
import ParentContactMappingModal from "./ParentContactMappingModal";
import AddStudentModal from "./AddStudentModal";
import AccommodationModal from "./AccommodationModal";

/*
 * SettingsModals — the always-rendered shell-level modal mounts at the bottom
 * of the SettingsTab tree, relocated from SettingsTab.jsx (CQ wave-9 split;
 * mirrors PlannerModals from the wave-3 planner split). Each modal guards its
 * own visibility internally (early-return-null on its `show` flag, exactly
 * the former inline `{x.show && ...}` guards); state ownership is unchanged
 * (modal cluster in useSettingsModalsState, the rest in the SettingsTab
 * shell / App).
 */
export default function SettingsModals(props) {
  const {
    // useSettingsModalsState cluster — spread from the shell
    accommEllLanguage, setAccommEllLanguage,
    accommPeriodFilter, setAccommPeriodFilter,
    accommSelectedStudents, setAccommSelectedStudents,
    accommStudentsList, setAccommStudentsList,
    accommodationCustomNotes, setAccommodationCustomNotes,
    accommodationModal, setAccommodationModal,
    addStudentModal, setAddStudentModal,
    parentContactMapping, setParentContactMapping,
    rosterMappingModal, setRosterMappingModal,
    selectedAccommodationPresets, setSelectedAccommodationPresets,
    // shell / App props
    accommodationPresets, addToast, setParentContacts, setRosters,
    setStudentAccommodations, setUploadingParentContacts, sortedPeriods,
    uploadingParentContacts,
  } = props;

  return (
    <>
      {/* Roster Column Mapping Modal */}
      <RosterMappingModal
        rosterMappingModal={rosterMappingModal}
        setRosterMappingModal={setRosterMappingModal}
        setRosters={setRosters}
        addToast={addToast}
      />

      {/* Parent Contact Column Mapping Modal */}
      <ParentContactMappingModal
        parentContactMapping={parentContactMapping}
        setParentContactMapping={setParentContactMapping}
        uploadingParentContacts={uploadingParentContacts}
        setUploadingParentContacts={setUploadingParentContacts}
        setParentContacts={setParentContacts}
        addToast={addToast}
      />

      {/* Add Student from Screenshot Modal */}
      <AddStudentModal
        addStudentModal={addStudentModal}
        setAddStudentModal={setAddStudentModal}
        addToast={addToast}
      />

      {/* Accommodation Assignment Modal */}
      <AccommodationModal
        accommodationModal={accommodationModal}
        setAccommodationModal={setAccommodationModal}
        accommEllLanguage={accommEllLanguage}
        setAccommEllLanguage={setAccommEllLanguage}
        accommPeriodFilter={accommPeriodFilter}
        setAccommPeriodFilter={setAccommPeriodFilter}
        accommSelectedStudents={accommSelectedStudents}
        setAccommSelectedStudents={setAccommSelectedStudents}
        accommStudentsList={accommStudentsList}
        setAccommStudentsList={setAccommStudentsList}
        accommodationCustomNotes={accommodationCustomNotes}
        setAccommodationCustomNotes={setAccommodationCustomNotes}
        selectedAccommodationPresets={selectedAccommodationPresets}
        setSelectedAccommodationPresets={setSelectedAccommodationPresets}
        accommodationPresets={accommodationPresets}
        sortedPeriods={sortedPeriods}
        setStudentAccommodations={setStudentAccommodations}
        addToast={addToast}
      />
    </>
  );
}
