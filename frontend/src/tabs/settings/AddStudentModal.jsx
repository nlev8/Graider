import React from "react";
import Icon from "../../components/Icon";
import { getAuthHeaders } from "../../services/api";

/*
 * AddStudentModal — the add-student-from-screenshot modal, relocated verbatim
 * from SettingsTab.jsx (CQ wave-9 split). The `{addStudentModal.show && ...}`
 * guard became the early return below.
 */
export default function AddStudentModal({
  addStudentModal,
  setAddStudentModal,
  addToast,
}) {
  if (!addStudentModal.show) return null;

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
              maxWidth: "600px",
              maxHeight: "90vh",
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
              <h3 style={{ fontSize: "1.2rem", fontWeight: 700, display: "flex", alignItems: "center", gap: "10px" }}>
                <Icon name="UserPlus" size={24} style={{ color: "#8b5cf6" }} />
                Add Student to Roster
              </h3>
              <button
                onClick={() => setAddStudentModal({ show: false, loading: false, image: null, student: null, error: null })}
                style={{ background: "none", border: "none", color: "var(--text-primary)", cursor: "pointer" }}
              >
                <Icon name="X" size={24} />
              </button>
            </div>

            {addStudentModal.loading && (
              <div style={{ textAlign: "center", padding: "40px" }}>
                <div style={{ marginBottom: "15px", color: "var(--text-secondary)" }}>
                  <Icon name="Loader2" size={32} style={{ animation: "spin 1s linear infinite" }} />
                </div>
                <p>Extracting student info with AI...</p>
              </div>
            )}

            {addStudentModal.error && (
              <div style={{ padding: "20px", background: "rgba(239,68,68,0.1)", borderRadius: "8px", marginBottom: "20px" }}>
                <p style={{ color: "#ef4444", fontWeight: 600 }}>Error: {addStudentModal.error}</p>
              </div>
            )}

            {addStudentModal.student && !addStudentModal.loading && (
              <>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "15px", marginBottom: "20px" }}>
                  <div>
                    <label className="label">First Name</label>
                    <input
                      type="text"
                      className="input"
                      value={addStudentModal.student.first_name || ""}
                      onChange={(e) => setAddStudentModal(prev => ({ ...prev, student: { ...prev.student, first_name: e.target.value } }))}
                    />
                  </div>
                  <div>
                    <label className="label">Middle Name</label>
                    <input
                      type="text"
                      className="input"
                      value={addStudentModal.student.middle_name || ""}
                      onChange={(e) => setAddStudentModal(prev => ({ ...prev, student: { ...prev.student, middle_name: e.target.value } }))}
                    />
                  </div>
                  <div>
                    <label className="label">Last Name</label>
                    <input
                      type="text"
                      className="input"
                      value={addStudentModal.student.last_name || ""}
                      onChange={(e) => setAddStudentModal(prev => ({ ...prev, student: { ...prev.student, last_name: e.target.value } }))}
                    />
                  </div>
                  <div>
                    <label className="label">Student ID</label>
                    <input
                      type="text"
                      className="input"
                      value={addStudentModal.student.student_id || ""}
                      onChange={(e) => setAddStudentModal(prev => ({ ...prev, student: { ...prev.student, student_id: e.target.value } }))}
                    />
                  </div>
                  <div>
                    <label className="label">Email</label>
                    <input
                      type="email"
                      className="input"
                      value={addStudentModal.student.email || ""}
                      onChange={(e) => setAddStudentModal(prev => ({ ...prev, student: { ...prev.student, email: e.target.value } }))}
                    />
                  </div>
                  <div>
                    <label className="label">Period *</label>
                    <input
                      type="text"
                      className="input"
                      placeholder="e.g., 2"
                      value={addStudentModal.student.period || ""}
                      onChange={(e) => setAddStudentModal(prev => ({ ...prev, student: { ...prev.student, period: e.target.value } }))}
                    />
                  </div>
                </div>

                {addStudentModal.image && (
                  <div style={{ marginBottom: "20px" }}>
                    <label className="label">Source Image</label>
                    <img
                      src={addStudentModal.image}
                      alt="Student info screenshot"
                      style={{ maxWidth: "100%", maxHeight: "200px", borderRadius: "8px", border: "1px solid var(--glass-border)" }}
                    />
                  </div>
                )}

                <div style={{ display: "flex", gap: "10px", justifyContent: "flex-end" }}>
                  <button
                    onClick={() => setAddStudentModal({ show: false, loading: false, image: null, student: null, error: null })}
                    className="btn btn-secondary"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={async () => {
                      if (!addStudentModal.student.period) {
                        addToast("Please enter a period", "warning");
                        return;
                      }
                      try {
                        const authHdrs = await getAuthHeaders();
                        const response = await fetch("/api/add-student-to-roster", {
                          method: "POST",
                          headers: { "Content-Type": "application/json", ...authHdrs },
                          body: JSON.stringify({ student: addStudentModal.student, period: addStudentModal.student.period }),
                        });
                        const data = await response.json();
                        if (data.error) {
                          addToast(data.error, "error");
                        } else {
                          addToast(data.message, "success");
                          setAddStudentModal({ show: false, loading: false, image: null, student: null, error: null });
                        }
                      } catch (err) {
                        addToast("Failed to add student: " + err.message, "error");
                      }
                    }}
                    className="btn btn-primary"
                  >
                    <Icon name="UserPlus" size={18} />
                    Add to Period {addStudentModal.student.period || "?"}
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
  );
}
