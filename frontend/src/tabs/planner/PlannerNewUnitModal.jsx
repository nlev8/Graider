import React from "react";
import NewUnitModal from "../../components/NewUnitModal";
import * as api from "../../services/api";

/*
 * PlannerNewUnitModal — the NewUnitModal mount + its onSubmit handler,
 * relocated verbatim from PlannerTab.jsx (CQ wave-3 split; the JSX block
 * itself moved App.jsx → PlannerTab in PR 7e of the Planner extraction
 * sprint as part of the NewUnit + tag cluster).
 *
 * The newUnitModal state lives in useTagRow (renderTagRow opens this modal);
 * setSharedResources / setPublishedAssessments / addToast / fetchTeacherTags
 * remain App-shell props.
 */
export default function PlannerNewUnitModal({
  newUnitModal,
  setNewUnitModal,
  setSharedResources,
  setPublishedAssessments,
  addToast,
  fetchTeacherTags,
}) {
  return (
      <NewUnitModal
        open={!!newUnitModal}
        onClose={() => setNewUnitModal(null)}
        value={newUnitModal ? newUnitModal.value : ""}
        setValue={(val) => setNewUnitModal(newUnitModal ? { ...newUnitModal, value: val } : null)}
        mode={newUnitModal ? (newUnitModal.mode || "unit") : "unit"}
        onSubmit={async (val) => {
          if (!newUnitModal) return;
          const rid = newUnitModal.resourceId;
          const mode = newUnitModal.mode || "unit";
          const existing = newUnitModal.existingTags || [];
          setNewUnitModal(null);
          try {
            if (mode === "tag") {
              const data = await api.setContentTags(rid, existing.concat([val]));
              if (data.success) {
                const updatedTags = data.tags || existing.concat([val]);
                setSharedResources((prev) => prev.map((r) => r.id === rid ? { ...r, tags: updatedTags } : r));
                setPublishedAssessments((prev) => prev.map((a) => (a.id === rid || a.join_code === rid) ? { ...a, tags: updatedTags } : a));
                addToast('Added tag "' + val + '"', "success");
                fetchTeacherTags();
              }
            } else {
              const data2 = await api.updateSharedResourceUnit(rid, val);
              if (data2.success) {
                setSharedResources((prev) => prev.map((r) => r.id === rid ? { ...r, unit_name: val } : r));
                setPublishedAssessments((prev) => prev.map((a) => (a.id === rid || a.join_code === rid) ? { ...a, unit_name: val } : a));
                addToast('Set unit to "' + val + '"', "success");
                fetchTeacherTags();
              }
            }
          } catch (err) { addToast("Failed: " + (err.message || "unknown"), "error"); }
        }}
      />
  );
}
