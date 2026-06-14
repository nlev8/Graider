import React from "react";
import Icon from "../../components/Icon";
import * as api from "../../services/api";
import ParentContactMappingForm from "./ParentContactMappingForm";

/*
 * ParentContactMappingModal — the parent-contact spreadsheet column-mapping
 * modal, relocated verbatim from SettingsTab.jsx (CQ wave-9 split). The
 * `{parentContactMapping.show && parentContactMapping.preview && ...}` guard
 * became the early return below.
 *
 * Form fields are in ParentContactMappingForm (CQ wave-8 split, #cq8-06).
 */
export default function ParentContactMappingModal({
  parentContactMapping,
  setParentContactMapping,
  uploadingParentContacts,
  setUploadingParentContacts,
  setParentContacts,
  addToast,
}) {
  if (!(parentContactMapping.show && parentContactMapping.preview)) return null;

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
              maxWidth: "560px",
              maxHeight: "85vh",
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
              <h3 style={{ fontSize: "1.2rem", fontWeight: 700 }}>
                Map Parent Contact Columns
              </h3>
              <button
                onClick={() => setParentContactMapping({ show: false, preview: null, mapping: null })}
                style={{ background: "none", border: "none", color: "var(--text-primary)", cursor: "pointer" }}
              >
                <Icon name="X" size={24} />
              </button>
            </div>

            <ParentContactMappingForm
              parentContactMapping={parentContactMapping}
              setParentContactMapping={setParentContactMapping}
            />

            {/* Action Buttons */}
            <div style={{ display: "flex", gap: "10px", marginTop: "20px" }}>
              <button
                onClick={async function() {
                  if (!parentContactMapping.mapping?.name_col) {
                    addToast("Please select a name column", "error");
                    return;
                  }
                  setUploadingParentContacts(true);
                  try {
                    var result = await api.saveParentContactMapping(parentContactMapping.mapping);
                    if (result.error) {
                      addToast(result.error, "error");
                    } else {
                      addToast(
                        "Imported " + result.unique_students + " students (" + result.with_email + " with email)",
                        "success"
                      );
                      var contactsData = await api.getParentContacts();
                      setParentContacts(contactsData);
                      setParentContactMapping({ show: false, preview: null, mapping: null });
                    }
                  } catch (err) {
                    addToast("Import failed: " + err.message, "error");
                  }
                  setUploadingParentContacts(false);
                }}
                className="btn btn-primary"
                disabled={uploadingParentContacts}
              >
                <Icon name="Save" size={18} />
                {uploadingParentContacts ? "Importing..." : "Save & Import"}
              </button>
              <button
                onClick={function() { setParentContactMapping({ show: false, preview: null, mapping: null }); }}
                className="btn btn-secondary"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
  );
}
