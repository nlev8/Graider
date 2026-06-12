import React from "react";
import Icon from "../Icon";
import { STEP_TYPES, PARAM_FIELDS } from "./stepConfig";

// Workflow editor view (header, description, step list, step config panel,
// picked-selector list). Originally the `if (view === "edit" && current)`
// branch of AutomationBuilder — markup relocated verbatim (CQ wave-6 split);
// the conditional render became the early-return guard below. All workflow /
// step / picker state and handlers stay in the AutomationBuilder shell and
// arrive via props; this component is stateless.
export default function AutomationEditView(props) {
  const {
    view, current, setCurrent, selectedStep, setSelectedStep,
    setView, loadList, saveWorkflow, startRun,
    pickerActive, pickerAutoLogin, setPickerAutoLogin, startPicker, stopPicker,
    pickerEvents, usePickedSelector,
    addStep, removeStep, moveStep, updateStep,
  } = props;
  if (!(view === "edit" && current)) return null;

  const step = current.steps[selectedStep];
  const fields = step ? (PARAM_FIELDS[step.type] || []) : [];

  return (
      <div style={{ padding: 0 }}>
        {/* Header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <button onClick={() => { setView("list"); loadList(); }} style={{
              background: "transparent", border: "none", cursor: "pointer", color: "var(--text-secondary)", padding: 4,
            }}>
              <Icon name="ArrowLeft" size={20} />
            </button>
            <input value={current.name} onChange={e => setCurrent({ ...current, name: e.target.value })}
              placeholder="Automation name..."
              style={{
                fontSize: "1.2rem", fontWeight: 700, border: "none", outline: "none",
                background: "transparent", color: "var(--text-primary)", width: 300,
              }} />
          </div>
          <div data-tutorial="automation-picker" style={{ display: "flex", gap: 8, alignItems: "center" }}>
            {pickerActive ? (
              <button onClick={stopPicker} style={{
                background: "#ef4444", color: "#fff", border: "none", borderRadius: 8,
                padding: "8px 14px", cursor: "pointer", fontWeight: 600, fontSize: "0.85rem",
              }}>
                Stop Picker
              </button>
            ) : (
              <>
                <button onClick={startPicker} style={{
                  background: "var(--card-bg)", color: "var(--text-primary)",
                  border: "1px solid var(--glass-border)", borderRadius: 8,
                  padding: "8px 14px", cursor: "pointer", fontWeight: 600, fontSize: "0.85rem",
                  display: "flex", alignItems: "center", gap: 6,
                }}>
                  <Icon name="MousePointer2" size={14} /> Element Picker
                </button>
                <label style={{ display: "flex", alignItems: "center", gap: 4, fontSize: "0.8rem", color: "var(--text-secondary)", cursor: "pointer" }}>
                  <input type="checkbox" checked={pickerAutoLogin} onChange={e => setPickerAutoLogin(e.target.checked)} />
                  Auto-login
                </label>
              </>
            )}
            <button onClick={saveWorkflow} style={{
              background: "var(--accent-primary)", color: "#fff", border: "none",
              borderRadius: 8, padding: "8px 16px", cursor: "pointer", fontWeight: 600, fontSize: "0.85rem",
            }}>
              Save
            </button>
            {current.id && (
              <button onClick={() => startRun()} style={{
                background: "#22c55e", color: "#fff", border: "none", borderRadius: 8,
                padding: "8px 16px", cursor: "pointer", fontWeight: 600, fontSize: "0.85rem",
              }}>
                Run
              </button>
            )}
          </div>
        </div>

        {/* Description */}
        <input value={current.description || ""} onChange={e => setCurrent({ ...current, description: e.target.value })}
          placeholder="Description (optional)..."
          style={{
            width: "100%", padding: "8px 12px", border: "1px solid var(--glass-border)",
            borderRadius: 8, background: "var(--card-bg)", color: "var(--text-primary)",
            marginBottom: 16, fontSize: "0.9rem", boxSizing: "border-box",
          }} />

        {/* Main layout: step list + config */}
        <div data-tutorial="automation-editor" style={{ display: "grid", gridTemplateColumns: "280px 1fr", gap: 16, minHeight: 400 }}>
          {/* Left: Step list */}
          <div data-tutorial="automation-steps" style={{
            background: "var(--card-bg)", borderRadius: 12, border: "1px solid var(--glass-border)",
            padding: 12, overflowY: "auto", maxHeight: 500,
          }}>
            <div style={{ marginBottom: 10, fontWeight: 600, fontSize: "0.9rem", color: "var(--text-secondary)" }}>Steps ({current.steps.length})</div>
            {current.steps.map((s, i) => {
              const meta = STEP_TYPES.find(t => t.value === s.type);
              return (
                <div key={s.id || i} onClick={() => setSelectedStep(i)}
                  style={{
                    padding: "8px 10px", borderRadius: 8, marginBottom: 4, cursor: "pointer",
                    display: "flex", alignItems: "center", gap: 8,
                    background: i === selectedStep ? "var(--accent-primary)" : "transparent",
                    color: i === selectedStep ? "#fff" : "var(--text-primary)",
                  }}>
                  <span style={{ fontSize: "0.75rem", opacity: 0.6, minWidth: 16 }}>{i + 1}</span>
                  <Icon name={meta ? meta.icon : "Circle"} size={14} />
                  <span style={{ fontSize: "0.85rem", flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {s.label || s.type}
                  </span>
                  <button onClick={e => { e.stopPropagation(); removeStep(i); }}
                    style={{ background: "transparent", border: "none", cursor: "pointer", color: "inherit", padding: 2, opacity: 0.5 }}>
                    <Icon name="X" size={12} />
                  </button>
                </div>
              );
            })}

            {/* Add step dropdown */}
            <div style={{ marginTop: 8 }}>
              <select onChange={e => { if (e.target.value) { addStep(e.target.value); e.target.value = ""; } }}
                defaultValue=""
                style={{
                  width: "100%", padding: "8px 10px", borderRadius: 8,
                  border: "1px solid var(--glass-border)", background: "var(--card-bg)",
                  color: "var(--text-primary)", fontSize: "0.85rem", cursor: "pointer",
                }}>
                <option value="" disabled>+ Add Step...</option>
                {STEP_TYPES.map(t => <option key={t.value} value={t.value}>{t.label} - {t.desc}</option>)}
              </select>
            </div>
          </div>

          {/* Right: Step config */}
          <div style={{
            background: "var(--card-bg)", borderRadius: 12, border: "1px solid var(--glass-border)", padding: 20,
          }}>
            {step ? (
              <>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
                  <div>
                    <h3 style={{ margin: 0, fontSize: "1.1rem", fontWeight: 600 }}>
                      Step {selectedStep + 1}: {STEP_TYPES.find(t => t.value === step.type)?.label || step.type}
                    </h3>
                    <span style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>
                      {STEP_TYPES.find(t => t.value === step.type)?.desc}
                    </span>
                  </div>
                  <div style={{ display: "flex", gap: 4 }}>
                    <button onClick={() => moveStep(selectedStep, -1)} disabled={selectedStep === 0}
                      style={{ background: "transparent", border: "1px solid var(--glass-border)", borderRadius: 6, padding: 4, cursor: "pointer", opacity: selectedStep === 0 ? 0.3 : 1 }}>
                      <Icon name="ChevronUp" size={14} />
                    </button>
                    <button onClick={() => moveStep(selectedStep, 1)} disabled={selectedStep >= current.steps.length - 1}
                      style={{ background: "transparent", border: "1px solid var(--glass-border)", borderRadius: 6, padding: 4, cursor: "pointer", opacity: selectedStep >= current.steps.length - 1 ? 0.3 : 1 }}>
                      <Icon name="ChevronDown" size={14} />
                    </button>
                  </div>
                </div>

                {/* Label */}
                <div style={{ marginBottom: 12 }}>
                  <label style={{ fontSize: "0.85rem", fontWeight: 600, display: "block", marginBottom: 4 }}>Label</label>
                  <input value={step.label} onChange={e => updateStep(selectedStep, "label", e.target.value)}
                    placeholder="Step description..."
                    style={{
                      width: "100%", padding: "8px 12px", borderRadius: 8,
                      border: "1px solid var(--glass-border)", background: "var(--input-bg)",
                      color: "var(--text-primary)", fontSize: "0.9rem", boxSizing: "border-box",
                    }} />
                </div>

                {/* Type-specific fields */}
                {fields.map(f => (
                  <div key={f.key} style={{ marginBottom: 12 }}>
                    <label style={{ fontSize: "0.85rem", fontWeight: 600, display: "block", marginBottom: 4 }}>
                      {f.label} {f.required && <span style={{ color: "#ef4444" }}>*</span>}
                    </label>
                    <div style={{ display: "flex", gap: 4 }}>
                      <input
                        type={f.type || "text"}
                        value={step.params[f.key] || ""}
                        onChange={e => updateStep(selectedStep, "params." + f.key, f.type === "number" ? parseInt(e.target.value) || 0 : e.target.value)}
                        placeholder={f.placeholder}
                        style={{
                          flex: 1, padding: "8px 12px", borderRadius: 8,
                          border: "1px solid var(--glass-border)", background: "var(--input-bg)",
                          color: "var(--text-primary)", fontSize: "0.9rem", boxSizing: "border-box",
                        }} />
                      {(f.key === "selector" || f.key === "condition_selector") && step.params[f.key] && (
                        <button onClick={() => updateStep(selectedStep, "params." + f.key, "")}
                          title="Clear selector"
                          style={{
                            background: "none", border: "1px solid var(--glass-border)", borderRadius: 8,
                            color: "#ef4444", cursor: "pointer", padding: "0 8px", fontSize: "1rem",
                          }}>
                          <Icon name="X" size={14} />
                        </button>
                      )}
                    </div>
                  </div>
                ))}

                {/* Picker events */}
                {pickerEvents.length > 0 && (
                  <div style={{ marginTop: 16 }}>
                    <div style={{ fontSize: "0.85rem", fontWeight: 600, marginBottom: 8, color: "var(--accent-primary)" }}>
                      Picked Selectors
                    </div>
                    {pickerEvents.slice(-5).map((ev, i) => (
                      <div key={i} onClick={() => usePickedSelector(ev.selector)} style={{
                        padding: "6px 10px", borderRadius: 6, marginBottom: 4, cursor: "pointer",
                        background: "var(--input-bg)", border: "1px solid var(--glass-border)",
                        fontSize: "0.8rem", fontFamily: "monospace",
                      }}>
                        <span style={{ color: "var(--accent-primary)" }}>{ev.selector}</span>
                        {ev.text && <span style={{ color: "var(--text-secondary)", marginLeft: 8 }}>"{ev.text.slice(0, 30)}"</span>}
                      </div>
                    ))}
                  </div>
                )}
              </>
            ) : (
              <div style={{ textAlign: "center", padding: 40, color: "var(--text-secondary)" }}>
                <Icon name="MousePointer2" size={32} style={{ opacity: 0.3, marginBottom: 8 }} />
                <p>Select a step or add a new one to configure it.</p>
              </div>
            )}
          </div>
        </div>
      </div>
  );
}
