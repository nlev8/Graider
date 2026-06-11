import React from "react";
import Icon from "../Icon";
import { getAuthHeaders } from "../../services/api";

export default function ScreenshotAddSection({ addToast, setAddStudentModal }) {
  return (
            <div
              data-tutorial="settings-classroom"
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
                  name="Camera"
                  size={20}
                  style={{ color: "#8b5cf6" }}
                />
                Add Student from Screenshot
              </h3>
              <p
                style={{
                  fontSize: "0.85rem",
                  color: "var(--text-secondary)",
                  marginBottom: "15px",
                }}
              >
                Paste or upload a screenshot of student info - AI will extract and add to roster
              </p>

              <div style={{ display: "flex", gap: "10px", marginBottom: "15px", flexWrap: "wrap" }}>
                <button
                  onClick={async () => {
                    try {
                      const clipboardItems = await navigator.clipboard.read();
                      for (const item of clipboardItems) {
                        if (item.types.includes("image/png")) {
                          const blob = await item.getType("image/png");
                          const reader = new FileReader();
                          reader.onload = async (e) => {
                            const base64 = e.target.result;
                            setAddStudentModal({ show: true, loading: true, image: base64, student: null, error: null });
                            try {
                              const authHdrs = await getAuthHeaders();
                              const response = await fetch("/api/extract-student-from-image", {
                                method: "POST",
                                headers: { "Content-Type": "application/json", ...authHdrs },
                                body: JSON.stringify({ image: base64 }),
                              });
                              const data = await response.json();
                              if (data.error) {
                                setAddStudentModal(prev => ({ ...prev, loading: false, error: data.error }));
                              } else {
                                setAddStudentModal(prev => ({ ...prev, loading: false, student: data.student }));
                              }
                            } catch (err) {
                              setAddStudentModal(prev => ({ ...prev, loading: false, error: err.message }));
                            }
                          };
                          reader.readAsDataURL(blob);
                          return;
                        }
                      }
                      addToast("No image found in clipboard. Copy a screenshot first.", "warning");
                    } catch (err) {
                      addToast("Could not access clipboard: " + err.message, "error");
                    }
                  }}
                  className="btn btn-primary"
                >
                  <Icon name="Clipboard" size={18} />
                  Paste from Clipboard
                </button>
                <label className="btn btn-secondary" style={{ cursor: "pointer" }}>
                  <Icon name="Upload" size={18} />
                  Upload Image
                  <input
                    type="file"
                    accept="image/*"
                    style={{ display: "none" }}
                    onChange={async (e) => {
                      const file = e.target.files?.[0];
                      if (!file) return;
                      const reader = new FileReader();
                      reader.onload = async (ev) => {
                        const base64 = ev.target.result;
                        setAddStudentModal({ show: true, loading: true, image: base64, student: null, error: null });
                        try {
                          const authHdrs = await getAuthHeaders();
                          const response = await fetch("/api/extract-student-from-image", {
                            method: "POST",
                            headers: { "Content-Type": "application/json", ...authHdrs },
                            body: JSON.stringify({ image: base64 }),
                          });
                          const data = await response.json();
                          if (data.error) {
                            setAddStudentModal(prev => ({ ...prev, loading: false, error: data.error }));
                          } else {
                            setAddStudentModal(prev => ({ ...prev, loading: false, student: data.student }));
                          }
                        } catch (err) {
                          setAddStudentModal(prev => ({ ...prev, loading: false, error: err.message }));
                        }
                      };
                      reader.readAsDataURL(file);
                      e.target.value = "";
                    }}
                  />
                </label>
              </div>
            </div>
  );
}
