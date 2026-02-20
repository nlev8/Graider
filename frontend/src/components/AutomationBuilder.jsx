import { useState, useEffect, useRef } from "react";
import Icon from "./Icon";
import * as api from "../services/api";

const STEP_TYPES = [
  { value: "login", label: "Login", icon: "LogIn", desc: "Log in to school portal" },
  { value: "navigate", label: "Navigate", icon: "Globe", desc: "Go to a URL" },
  { value: "click", label: "Click", icon: "MousePointer2", desc: "Click an element" },
  { value: "fill", label: "Fill", icon: "PenLine", desc: "Type text into a field" },
  { value: "select", label: "Select", icon: "ChevronDown", desc: "Choose dropdown option" },
  { value: "wait", label: "Wait", icon: "Clock", desc: "Wait for time or element" },
  { value: "screenshot", label: "Screenshot", icon: "Camera", desc: "Capture the page" },
  { value: "extract_text", label: "Extract Text", icon: "FileSearch", desc: "Read text from element" },
  { value: "download", label: "Download", icon: "Download", desc: "Download a file" },
  { value: "keyboard", label: "Keyboard", icon: "Keyboard", desc: "Press keys or type" },
  { value: "loop", label: "Loop", icon: "Repeat", desc: "Repeat steps N times" },
  { value: "conditional", label: "If/Else", icon: "GitBranch", desc: "Branch on element visibility" },
];

const PARAM_FIELDS = {
  login: [{ key: "portal_url", label: "Portal URL", placeholder: "https://vportal.volusia.k12.fl.us/" }],
  navigate: [{ key: "url", label: "URL", placeholder: "https://example.com", required: true }],
  click: [{ key: "selector", label: "Selector", placeholder: "#button or text=Click Me", required: true }, { key: "timeout", label: "Timeout (ms)", placeholder: "10000", type: "number" }],
  fill: [{ key: "selector", label: "Selector", placeholder: "#input-field", required: true }, { key: "value", label: "Value", placeholder: "Text to type", required: true }],
  select: [{ key: "selector", label: "Selector", placeholder: "select#dropdown", required: true }, { key: "option", label: "Option Label", placeholder: "Option text", required: true }],
  wait: [{ key: "ms", label: "Milliseconds", placeholder: "3000", type: "number" }, { key: "selector", label: "Wait for Selector", placeholder: "#element" }],
  screenshot: [{ key: "filename", label: "Filename", placeholder: "screenshot_{index}.png" }, { key: "output_dir", label: "Output Directory", placeholder: "~/Downloads/" }],
  extract_text: [{ key: "selector", label: "Selector", placeholder: "#element", required: true }, { key: "variable", label: "Save as Variable", placeholder: "extracted_text" }],
  download: [{ key: "selector", label: "Click Selector", placeholder: "#download-btn", required: true }, { key: "output_dir", label: "Output Directory", placeholder: "~/.graider_data/downloads" }],
  keyboard: [{ key: "key", label: "Key", placeholder: "Enter, Tab, Escape..." }, { key: "text", label: "Type Text", placeholder: "Text to type character by character" }],
  loop: [{ key: "count", label: "Repeat Count", placeholder: "5", type: "number", required: true }],
  conditional: [{ key: "condition_selector", label: "Check Selector", placeholder: "#element", required: true }],
};

export default function AutomationBuilder({ addToast }) {
  const [view, setView] = useState("list"); // list | edit | run
  const [workflows, setWorkflows] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [current, setCurrent] = useState(null);
  const [selectedStep, setSelectedStep] = useState(0);
  const [runStatus, setRunStatus] = useState(null);
  const [pickerActive, setPickerActive] = useState(false);
  const [pickerEvents, setPickerEvents] = useState([]);
  const pollRef = useRef(null);
  const pickerPollRef = useRef(null);

  useEffect(() => { loadList(); }, []);

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
      if (pickerPollRef.current) clearInterval(pickerPollRef.current);
    };
  }, []);

  async function loadList() {
    try {
      const [wfRes, tplRes] = await Promise.all([api.listAutomations(), api.listAutomationTemplates()]);
      setWorkflows(wfRes.workflows || []);
      setTemplates(tplRes.templates || []);
    } catch (e) {
      console.error("Failed to load automations:", e);
    }
  }

  function newWorkflow() {
    setCurrent({
      name: "", description: "", steps: [],
      browser: { headless: false, persistent_context: false },
    });
    setSelectedStep(0);
    setView("edit");
  }

  async function loadWorkflow(id) {
    try {
      const wf = await api.getAutomation(id);
      setCurrent(wf);
      setSelectedStep(0);
      setView("edit");
    } catch (e) {
      addToast("Failed to load workflow", "error");
    }
  }

  async function loadTemplate(id) {
    try {
      const tpl = await api.getAutomation(id);
      setCurrent({ ...tpl, id: undefined, name: tpl.name + " (Copy)" });
      setSelectedStep(0);
      setView("edit");
    } catch (e) {
      // Templates come from the templates endpoint, load via save+edit
      const tpl = templates.find(t => t.id === id);
      if (tpl) {
        setCurrent({ name: tpl.name + " (Copy)", description: tpl.description, steps: [], browser: { headless: false } });
        setView("edit");
      }
    }
  }

  async function saveWorkflow() {
    if (!current || !current.name.trim()) {
      addToast("Workflow name required", "error");
      return;
    }
    try {
      const res = await api.saveAutomation(current);
      setCurrent({ ...current, id: res.id });
      addToast("Workflow saved", "success");
      loadList();
    } catch (e) {
      addToast("Failed to save", "error");
    }
  }

  async function deleteWorkflow(id, e) {
    e.stopPropagation();
    if (!confirm("Delete this automation?")) return;
    try {
      await api.deleteAutomation(id);
      addToast("Deleted", "success");
      loadList();
    } catch (e) {
      addToast("Failed to delete", "error");
    }
  }

  async function startRun(id) {
    try {
      await api.runAutomation(id || current.id);
      setRunStatus({ status: "running", message: "Starting...", current_step: 0, total_steps: 0, log: [] });
      setView("run");
      pollRef.current = setInterval(async () => {
        try {
          const s = await api.getAutomationRunStatus();
          setRunStatus(s);
          if (s.status !== "running") {
            clearInterval(pollRef.current);
            pollRef.current = null;
          }
        } catch {}
      }, 800);
    } catch (e) {
      addToast(e.message || "Failed to start", "error");
    }
  }

  async function stopRun() {
    try {
      await api.stopAutomationRun();
      if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
      setRunStatus(prev => ({ ...prev, status: "idle", message: "Stopped" }));
    } catch {}
  }

  // Element picker
  async function startPicker() {
    try {
      await api.startElementPicker();
      setPickerActive(true);
      setPickerEvents([]);
      pickerPollRef.current = setInterval(async () => {
        try {
          const res = await api.getPickerEvents();
          if (res.events && res.events.length > 0) {
            setPickerEvents(prev => [...prev, ...res.events]);
          }
          if (res.status === "done") {
            clearInterval(pickerPollRef.current);
            pickerPollRef.current = null;
            setPickerActive(false);
          }
        } catch {}
      }, 500);
    } catch (e) {
      addToast("Failed to start picker", "error");
    }
  }

  async function stopPicker() {
    try {
      await api.stopElementPicker();
      if (pickerPollRef.current) { clearInterval(pickerPollRef.current); pickerPollRef.current = null; }
      setPickerActive(false);
    } catch {}
  }

  function usePickedSelector(selector) {
    if (!current || !current.steps[selectedStep]) return;
    const steps = [...current.steps];
    const step = { ...steps[selectedStep], params: { ...steps[selectedStep].params } };
    // Put selector in the appropriate field
    if (step.type === "click" || step.type === "extract_text" || step.type === "download") {
      step.params.selector = selector;
    } else if (step.type === "fill" || step.type === "select") {
      step.params.selector = selector;
    } else if (step.type === "wait") {
      step.params.selector = selector;
    } else if (step.type === "conditional") {
      step.params.condition_selector = selector;
    }
    steps[selectedStep] = step;
    setCurrent({ ...current, steps });
    addToast("Selector applied: " + selector, "success");
  }

  function addStep(type) {
    if (!current) return;
    const newStep = { id: "step-" + (current.steps.length + 1), type, label: "", params: {} };
    const meta = STEP_TYPES.find(s => s.value === type);
    if (meta) newStep.label = meta.label;
    setCurrent({ ...current, steps: [...current.steps, newStep] });
    setSelectedStep(current.steps.length);
  }

  function removeStep(idx) {
    if (!current) return;
    const steps = current.steps.filter((_, i) => i !== idx);
    setCurrent({ ...current, steps });
    if (selectedStep >= steps.length) setSelectedStep(Math.max(0, steps.length - 1));
  }

  function moveStep(idx, dir) {
    if (!current) return;
    const steps = [...current.steps];
    const newIdx = idx + dir;
    if (newIdx < 0 || newIdx >= steps.length) return;
    [steps[idx], steps[newIdx]] = [steps[newIdx], steps[idx]];
    setCurrent({ ...current, steps });
    setSelectedStep(newIdx);
  }

  function updateStep(idx, field, value) {
    if (!current) return;
    const steps = [...current.steps];
    if (field.startsWith("params.")) {
      const paramKey = field.slice(7);
      steps[idx] = { ...steps[idx], params: { ...steps[idx].params, [paramKey]: value } };
    } else {
      steps[idx] = { ...steps[idx], [field]: value };
    }
    setCurrent({ ...current, steps });
  }

  // ── Renders ──────────────────────────────────────────────

  const cardStyle = {
    background: "var(--card-bg)", borderRadius: 12, padding: 20,
    border: "1px solid var(--glass-border)", cursor: "pointer",
    transition: "box-shadow 0.15s", display: "flex", flexDirection: "column", gap: 8,
    color: "var(--text-primary)",
  };

  // LIST VIEW
  if (view === "list") {
    return (
      <div data-tutorial="automation-card" style={{ padding: 0 }}>
        <div data-tutorial="automation-toolbar" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
          <h2 style={{ fontSize: "1.3rem", fontWeight: 700, display: "flex", alignItems: "center", gap: 10, margin: 0 }}>
            <Icon name="Cpu" size={24} /> Automations
          </h2>
          <button onClick={newWorkflow} style={{
            background: "var(--accent-primary)", color: "#fff", border: "none",
            borderRadius: 8, padding: "8px 16px", cursor: "pointer", display: "flex", alignItems: "center", gap: 6,
            fontWeight: 600, fontSize: "0.9rem",
          }}>
            <Icon name="Plus" size={16} /> New Automation
          </button>
        </div>

        {workflows.length === 0 && templates.length === 0 && (
          <div style={{ textAlign: "center", padding: 40, color: "var(--text-secondary)" }}>
            <Icon name="Cpu" size={48} style={{ opacity: 0.3, marginBottom: 12 }} />
            <p>No automations yet. Create one or start from a template.</p>
          </div>
        )}

        {workflows.length > 0 && (
          <>
            <h3 style={{ fontSize: "1rem", fontWeight: 600, marginBottom: 10, color: "var(--text-secondary)" }}>My Automations</h3>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 12, marginBottom: 24 }}>
              {workflows.map(wf => (
                <div key={wf.id} style={cardStyle} onClick={() => loadWorkflow(wf.id)}
                  onMouseEnter={e => e.currentTarget.style.boxShadow = "0 4px 12px rgba(0,0,0,0.1)"}
                  onMouseLeave={e => e.currentTarget.style.boxShadow = "none"}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                    <span style={{ fontWeight: 600, fontSize: "1rem" }}>{wf.name}</span>
                    <div style={{ display: "flex", gap: 4 }}>
                      <button onClick={(e) => { e.stopPropagation(); startRun(wf.id); }}
                        style={{ background: "#22c55e", color: "#fff", border: "none", borderRadius: 6, padding: "4px 10px", cursor: "pointer", fontSize: "0.8rem", fontWeight: 600 }}>
                        Run
                      </button>
                      <button onClick={(e) => deleteWorkflow(wf.id, e)}
                        style={{ background: "transparent", color: "var(--text-secondary)", border: "none", cursor: "pointer", padding: 4 }}>
                        <Icon name="Trash2" size={14} />
                      </button>
                    </div>
                  </div>
                  {wf.description && <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", margin: 0 }}>{wf.description}</p>}
                  <span style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>{wf.step_count} steps</span>
                </div>
              ))}
            </div>
          </>
        )}

        {templates.length > 0 && (
          <div data-tutorial="automation-templates">
            <h3 style={{ fontSize: "1rem", fontWeight: 600, marginBottom: 10, color: "var(--text-secondary)" }}>Templates</h3>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 12 }}>
              {templates.map(tpl => (
                <div key={tpl.id} style={{ ...cardStyle, borderStyle: "dashed" }} onClick={() => loadTemplate(tpl.id)}
                  onMouseEnter={e => e.currentTarget.style.boxShadow = "0 4px 12px rgba(0,0,0,0.1)"}
                  onMouseLeave={e => e.currentTarget.style.boxShadow = "none"}>
                  <span style={{ fontWeight: 600, fontSize: "1rem" }}>{tpl.name}</span>
                  {tpl.description && <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", margin: 0 }}>{tpl.description}</p>}
                  <span style={{ fontSize: "0.8rem", color: "var(--accent-primary)" }}>Template - {tpl.step_count} steps</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  }

  // RUN VIEW
  if (view === "run" && runStatus) {
    const pct = runStatus.total_steps > 0 ? Math.round((runStatus.current_step / runStatus.total_steps) * 100) : 0;
    const isDone = runStatus.status !== "running";
    return (
      <div style={{ padding: 0 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
          <h2 style={{ fontSize: "1.3rem", fontWeight: 700, display: "flex", alignItems: "center", gap: 10, margin: 0 }}>
            <Icon name="Play" size={24} /> Running Automation
          </h2>
          <div style={{ display: "flex", gap: 8 }}>
            {!isDone && (
              <button onClick={stopRun} style={{
                background: "#ef4444", color: "#fff", border: "none", borderRadius: 8,
                padding: "8px 16px", cursor: "pointer", fontWeight: 600, fontSize: "0.9rem",
              }}>
                Stop
              </button>
            )}
            <button onClick={() => { setView("list"); loadList(); }} style={{
              background: "var(--card-bg)", color: "var(--text-primary)", border: "1px solid var(--glass-border)",
              borderRadius: 8, padding: "8px 16px", cursor: "pointer", fontWeight: 600, fontSize: "0.9rem",
            }}>
              Back
            </button>
          </div>
        </div>

        <div style={{
          background: "var(--card-bg)", borderRadius: 12, padding: 20,
          border: "1px solid var(--glass-border)", marginBottom: 16,
        }}>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
            <span style={{ fontWeight: 600 }}>
              {isDone ? (runStatus.status === "error" ? "Error" : "Complete") : "Step " + runStatus.current_step + " of " + runStatus.total_steps}
            </span>
            <span style={{ color: "var(--text-secondary)" }}>{pct}%</span>
          </div>
          <div style={{ background: "var(--glass-border)", borderRadius: 6, height: 8, overflow: "hidden" }}>
            <div style={{
              background: runStatus.status === "error" ? "#ef4444" : isDone ? "#22c55e" : "var(--accent-primary)",
              height: "100%", width: (isDone ? 100 : pct) + "%", transition: "width 0.3s",
              borderRadius: 6,
            }} />
          </div>
          <p style={{ marginTop: 10, fontSize: "0.9rem", color: "var(--text-secondary)" }}>{runStatus.message}</p>
        </div>

        <div style={{
          background: "#0f172a", color: "#e2e8f0", borderRadius: 12, padding: 16,
          fontFamily: "monospace", fontSize: "0.8rem", maxHeight: 400, overflowY: "auto",
        }}>
          {(runStatus.log || []).map((entry, i) => {
            const color = entry.type === "step_error" || entry.type === "error" ? "#f87171"
              : entry.type === "step_done" || entry.type === "done" ? "#4ade80"
              : entry.type === "step_start" ? "#60a5fa" : "#94a3b8";
            return (
              <div key={i} style={{ color, marginBottom: 2 }}>
                [{entry.type}] {entry.label || entry.message || ""}
              </div>
            );
          })}
          {(runStatus.log || []).length === 0 && <div style={{ color: "#94a3b8" }}>Waiting for output...</div>}
        </div>
      </div>
    );
  }

  // EDIT VIEW
  if (view === "edit" && current) {
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
          <div data-tutorial="automation-picker" style={{ display: "flex", gap: 8 }}>
            {pickerActive ? (
              <button onClick={stopPicker} style={{
                background: "#ef4444", color: "#fff", border: "none", borderRadius: 8,
                padding: "8px 14px", cursor: "pointer", fontWeight: 600, fontSize: "0.85rem",
              }}>
                Stop Picker
              </button>
            ) : (
              <button onClick={startPicker} style={{
                background: "var(--card-bg)", color: "var(--text-primary)",
                border: "1px solid var(--glass-border)", borderRadius: 8,
                padding: "8px 14px", cursor: "pointer", fontWeight: 600, fontSize: "0.85rem",
                display: "flex", alignItems: "center", gap: 6,
              }}>
                <Icon name="MousePointer2" size={14} /> Element Picker
              </button>
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
                    <input
                      type={f.type || "text"}
                      value={step.params[f.key] || ""}
                      onChange={e => updateStep(selectedStep, "params." + f.key, f.type === "number" ? parseInt(e.target.value) || 0 : e.target.value)}
                      placeholder={f.placeholder}
                      style={{
                        width: "100%", padding: "8px 12px", borderRadius: 8,
                        border: "1px solid var(--glass-border)", background: "var(--input-bg)",
                        color: "var(--text-primary)", fontSize: "0.9rem", boxSizing: "border-box",
                      }} />
                  </div>
                ))}

                {/* Picker events */}
                {pickerActive && pickerEvents.length > 0 && (
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

  return null;
}
