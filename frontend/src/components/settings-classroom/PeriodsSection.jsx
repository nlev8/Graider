import React from "react";
import Icon from "../Icon";
import * as api from "../../services/api";
import PeriodUploadControls from "./PeriodUploadControls";
import PeriodStudentTable from "./PeriodStudentTable";

export default function PeriodsSection(props) {
  const { addToast, focusImportProgress, focusImporting, newPeriodName, periodInputRef, setFocusImportProgress, setFocusImporting, setNewPeriodName, setPeriods, setUploadingPeriod, sortedPeriods, uploadingPeriod } = props;
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
                  name="Clock"
                  size={20}
                  style={{ color: "#f59e0b" }}
                />
                Class Periods
              </h3>
              <p
                style={{
                  fontSize: "0.85rem",
                  color: "var(--text-secondary)",
                  marginBottom: "15px",
                }}
              >
                Upload separate rosters for each class period, or import directly from Focus SIS
              </p>

              <PeriodUploadControls
                addToast={addToast}
                focusImportProgress={focusImportProgress}
                focusImporting={focusImporting}
                newPeriodName={newPeriodName}
                periodInputRef={periodInputRef}
                setFocusImportProgress={setFocusImportProgress}
                setFocusImporting={setFocusImporting}
                setNewPeriodName={setNewPeriodName}
                setPeriods={setPeriods}
                setUploadingPeriod={setUploadingPeriod}
                uploadingPeriod={uploadingPeriod}
              />

              {/* Period Cards - Expandable */}
              {sortedPeriods.length > 0 && (
                <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                  {sortedPeriods.map((period) => (
                    <PeriodCard key={period.filename} period={period} {...props} />
                  ))}
                </div>
              )}
            </div>
  );
}

function PeriodCard(props) {
  const { addToast, expandedPeriod, period, setAddingStudent, setEditingStudentId, setExpandedPeriod, setExpandedStudents, setLoadingExpandedStudents, setPeriods } = props;
  return (
                    <div key={period.filename} style={{ borderRadius: "8px", border: "1px solid var(--glass-border)", overflow: "hidden" }}>
                      {/* Period Header Row */}
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: "10px",
                          padding: "10px 15px",
                          background: expandedPeriod === period.filename ? "rgba(245, 158, 11, 0.08)" : "var(--input-bg)",
                          cursor: "pointer",
                        }}
                        onClick={async () => {
                          if (expandedPeriod === period.filename) {
                            setExpandedPeriod(null);
                            setExpandedStudents([]);
                            setEditingStudentId(null);
                            setAddingStudent(false);
                            return;
                          }
                          setExpandedPeriod(period.filename);
                          setLoadingExpandedStudents(true);
                          setEditingStudentId(null);
                          setAddingStudent(false);
                          try {
                            const [studentsRes, contactsRes] = await Promise.all([
                              api.getPeriodStudents(period.filename),
                              api.getParentContacts(),
                            ]);
                            const students = studentsRes.students || [];
                            const contacts = contactsRes.contacts || {};
                            // Merge contact info into student list
                            // student_email comes from contacts (backend merges from grading results)
                            const merged = students.map(s => {
                              const contact = contacts[s.id] || {};
                              return {
                                ...s,
                                student_email: contact.student_email || "",
                                parent_emails: contact.parent_emails || [],
                                parent_phones: contact.parent_phones || [],
                              };
                            });
                            setExpandedStudents(merged);
                          } catch (err) {
                            addToast("Failed to load students: " + err.message, "error");
                            setExpandedStudents([]);
                          }
                          setLoadingExpandedStudents(false);
                        }}
                      >
                        <Icon
                          name={expandedPeriod === period.filename ? "ChevronDown" : "ChevronRight"}
                          size={16}
                          style={{ color: "#f59e0b", flexShrink: 0 }}
                        />
                        <Icon name="Users" size={16} style={{ color: "#f59e0b", flexShrink: 0 }} />
                        <div style={{ flex: 1 }}>
                          <div style={{ fontWeight: 600, fontSize: "0.9rem", display: "flex", alignItems: "center", gap: "8px" }}>
                            {period.period_name}
                            {period.course_codes && period.course_codes.length > 0 && (
                              <span style={{ fontSize: "0.7rem", padding: "1px 6px", borderRadius: "4px", background: "rgba(139, 92, 246, 0.15)", color: "#a78bfa", fontWeight: 500 }}>
                                {period.course_codes.join(", ")}
                              </span>
                            )}
                          </div>
                          <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                            {period.row_count} students{period.imported_from === "focus" ? " (Focus SIS)" : ""}
                          </div>
                        </div>
                        <select
                          value={period.class_level || "standard"}
                          onClick={(e) => e.stopPropagation()}
                          onChange={async (e) => {
                            e.stopPropagation();
                            const newLevel = e.target.value;
                            await api.updatePeriodLevel(period.filename, newLevel);
                            const data = await api.listPeriods();
                            setPeriods(data.periods || []);
                          }}
                          style={{
                            padding: "4px 8px",
                            borderRadius: "6px",
                            border: "1px solid var(--glass-border)",
                            background: period.class_level === "advanced" ? "rgba(139, 92, 246, 0.2)" : period.class_level === "support" ? "rgba(244, 114, 182, 0.2)" : "var(--input-bg)",
                            color: period.class_level === "advanced" ? "#a78bfa" : period.class_level === "support" ? "#f472b6" : "var(--text-primary)",
                            fontSize: "0.8rem",
                            cursor: "pointer",
                          }}
                        >
                          <option value="standard">Standard</option>
                          <option value="advanced">Advanced</option>
                          <option value="support">Support</option>
                        </select>
                        <button
                          onClick={async (e) => {
                            e.stopPropagation();
                            if (confirm("Delete " + period.period_name + "?")) {
                              await api.deletePeriod(period.filename);
                              const data = await api.listPeriods();
                              setPeriods(data.periods || []);
                              if (expandedPeriod === period.filename) {
                                setExpandedPeriod(null);
                                setExpandedStudents([]);
                              }
                            }
                          }}
                          style={{ padding: "4px 6px", background: "none", border: "none", color: "var(--text-muted)", cursor: "pointer" }}
                        >
                          <Icon name="X" size={14} />
                        </button>
                      </div>

                      {/* Expanded Student List */}
                      {expandedPeriod === period.filename && (
                        <PeriodStudentList {...props} />
                      )}
                    </div>
  );
}

function PeriodStudentList({ addToast, addingStudent, editStudentData, editingStudentId, expandedStudents, loadingExpandedStudents, newStudent, period, setAddingStudent, setEditStudentData, setEditingStudentId, setExpandedStudents, setNewStudent, setPeriods }) {
  return (
                        <div style={{ borderTop: "1px solid var(--glass-border)", padding: "10px 15px", background: "var(--bg-secondary)" }}>
                          <PeriodStudentTable
                            addToast={addToast}
                            editStudentData={editStudentData}
                            editingStudentId={editingStudentId}
                            expandedStudents={expandedStudents}
                            loadingExpandedStudents={loadingExpandedStudents}
                            period={period}
                            setEditStudentData={setEditStudentData}
                            setEditingStudentId={setEditingStudentId}
                            setExpandedStudents={setExpandedStudents}
                            setPeriods={setPeriods}
                          />

                          {/* Add Student Form */}
                          {addingStudent ? (
                            <div style={{ marginTop: "10px", padding: "10px", background: "var(--input-bg)", borderRadius: "6px", border: "1px solid var(--glass-border)" }}>
                              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px", marginBottom: "8px" }}>
                                <input type="text" placeholder="Student Name (Last; First)" value={newStudent.name} onChange={(e) => setNewStudent({...newStudent, name: e.target.value})} style={{ padding: "6px 8px", borderRadius: "4px", border: "1px solid var(--glass-border)", background: "var(--bg-secondary)", color: "var(--text-primary)", fontSize: "0.8rem" }} />
                                <input type="text" placeholder="Student ID" value={newStudent.student_id} onChange={(e) => setNewStudent({...newStudent, student_id: e.target.value})} style={{ padding: "6px 8px", borderRadius: "4px", border: "1px solid var(--glass-border)", background: "var(--bg-secondary)", color: "var(--text-primary)", fontSize: "0.8rem" }} />
                                <input type="text" placeholder="Grade (e.g., 06)" value={newStudent.grade} onChange={(e) => setNewStudent({...newStudent, grade: e.target.value})} style={{ padding: "6px 8px", borderRadius: "4px", border: "1px solid var(--glass-border)", background: "var(--bg-secondary)", color: "var(--text-primary)", fontSize: "0.8rem" }} />
                                <input type="email" placeholder="Student Email" value={newStudent.student_email} onChange={(e) => setNewStudent({...newStudent, student_email: e.target.value})} style={{ padding: "6px 8px", borderRadius: "4px", border: "1px solid var(--glass-border)", background: "var(--bg-secondary)", color: "var(--text-primary)", fontSize: "0.8rem" }} />
                                <input type="text" placeholder="Parent Emails (comma-separated)" value={newStudent.parent_emails} onChange={(e) => setNewStudent({...newStudent, parent_emails: e.target.value})} style={{ padding: "6px 8px", borderRadius: "4px", border: "1px solid var(--glass-border)", background: "var(--bg-secondary)", color: "var(--text-primary)", fontSize: "0.8rem" }} />
                                <input type="text" placeholder="Parent Phones (comma-separated)" value={newStudent.parent_phones} onChange={(e) => setNewStudent({...newStudent, parent_phones: e.target.value})} style={{ padding: "6px 8px", borderRadius: "4px", border: "1px solid var(--glass-border)", background: "var(--bg-secondary)", color: "var(--text-primary)", fontSize: "0.8rem" }} />
                              </div>
                              <div style={{ display: "flex", gap: "8px" }}>
                                <button
                                  onClick={async () => {
                                    if (!newStudent.name.trim()) { addToast("Student name is required", "warning"); return; }
                                    try {
                                      const emails = newStudent.parent_emails ? newStudent.parent_emails.split(",").map(e => e.trim()).filter(Boolean) : [];
                                      const phones = newStudent.parent_phones ? newStudent.parent_phones.split(",").map(p => p.trim()).filter(Boolean) : [];
                                      const res = await api.addStudent({
                                        period_filename: period.filename,
                                        student_name: newStudent.name,
                                        student_id: newStudent.student_id,
                                        student_email: newStudent.student_email,
                                        grade: newStudent.grade,
                                        parent_emails: emails,
                                        parent_phones: phones,
                                      });
                                      if (res.error) { addToast(res.error, "error"); return; }
                                      setNewStudent({ name: '', student_id: '', grade: '', student_email: '', parent_emails: '', parent_phones: '' });
                                      setAddingStudent(false);
                                      // Refresh
                                      const [studentsRes, contactsRes] = await Promise.all([api.getPeriodStudents(period.filename), api.getParentContacts()]);
                                      const contacts = contactsRes.contacts || {};
                                      setExpandedStudents((studentsRes.students || []).map(s => ({ ...s, student_email: (contacts[s.id] || {}).student_email || "", parent_emails: (contacts[s.id] || {}).parent_emails || [], parent_phones: (contacts[s.id] || {}).parent_phones || [] })));
                                      const periodsData = await api.listPeriods();
                                      setPeriods(periodsData.periods || []);
                                      addToast("Student added", "success");
                                    } catch (err) {
                                      addToast("Add failed: " + err.message, "error");
                                    }
                                  }}
                                  className="btn btn-primary"
                                  style={{ fontSize: "0.8rem", padding: "5px 12px" }}
                                >Add Student</button>
                                <button
                                  onClick={() => { setAddingStudent(false); setNewStudent({ name: '', student_id: '', grade: '', student_email: '', parent_emails: '', parent_phones: '' }); }}
                                  className="btn btn-secondary"
                                  style={{ fontSize: "0.8rem", padding: "5px 12px" }}
                                >Cancel</button>
                              </div>
                            </div>
                          ) : (
                            <button
                              onClick={() => setAddingStudent(true)}
                              style={{
                                marginTop: "10px",
                                padding: "6px 12px",
                                background: "none",
                                border: "1px dashed var(--glass-border)",
                                borderRadius: "6px",
                                color: "var(--text-secondary)",
                                cursor: "pointer",
                                fontSize: "0.8rem",
                                display: "flex",
                                alignItems: "center",
                                gap: "6px",
                                width: "100%",
                                justifyContent: "center",
                              }}
                            >
                              <Icon name="Plus" size={14} />
                              Add Student
                            </button>
                          )}
                        </div>
  );
}
