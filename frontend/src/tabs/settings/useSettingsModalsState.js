import { useState } from "react";

/*
 * useSettingsModalsState — owns the state for the four shell-level modals
 * (roster column mapping, parent contact mapping, add-student-from-screenshot,
 * accommodation assignment) plus the accommodation form fields, relocated
 * verbatim from SettingsTab.jsx (CQ wave-9 split). The hook is called
 * unconditionally from the SettingsTab shell and its result is spread into
 * ClassroomSection (which opens these modals) and SettingsModals (which
 * renders them).
 */
export default function useSettingsModalsState() {
  const [accommEllLanguage, setAccommEllLanguage] = useState("");
  const [accommPeriodFilter, setAccommPeriodFilter] = useState("");
  const [accommSelectedStudents, setAccommSelectedStudents] = useState({});
  const [accommStudentsList, setAccommStudentsList] = useState([]);
  const [accommodationCustomNotes, setAccommodationCustomNotes] = useState("");
  const [accommodationModal, setAccommodationModal] = useState({
    show: false,
    studentId: null,
  });
  const [addStudentModal, setAddStudentModal] = useState({
    show: false,
    loading: false,
    image: null,
    student: null,
    error: null,
  });
  const [parentContactMapping, setParentContactMapping] = useState({ show: false, preview: null, mapping: null });
  const [rosterMappingModal, setRosterMappingModal] = useState({
    show: false,
    roster: null,
  });
  const [selectedAccommodationPresets, setSelectedAccommodationPresets] =
    useState([]);

  return {
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
  };
}
