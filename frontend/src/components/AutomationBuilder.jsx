import { useState, useEffect, useRef } from "react";
import * as api from "../services/api";
import { STEP_TYPES } from "./automation-builder/stepConfig";
import AutomationListView from "./automation-builder/AutomationListView";
import AutomationRunView from "./automation-builder/AutomationRunView";
import AutomationEditView from "./automation-builder/AutomationEditView";

// Shell/orchestrator for the automation builder (CQ wave-6 split). All state,
// refs, effects, and handlers live here; the three mutually-exclusive view
// branches (list / run / edit) moved verbatim to automation-builder/* as
// stateless components, each guarding on `view` with early-return-null —
// exactly one renders non-null at a time, mirroring the original if-chain.
export default function AutomationBuilder({ addToast }) {
  const [view, setView] = useState("list"); // list | edit | run
  const [workflows, setWorkflows] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [current, setCurrent] = useState(null);
  const [selectedStep, setSelectedStep] = useState(0);
  const [runStatus, setRunStatus] = useState(null);
  const [pickerActive, setPickerActive] = useState(false);
  const [pickerEvents, setPickerEvents] = useState([]);
  const [pickerAutoLogin, setPickerAutoLogin] = useState(true);
  const pollRef = useRef(null);
  const usePickedSelectorRef = useRef(null);
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
      const tpl = await api.getTemplate(id);
      setCurrent({ ...tpl, id: undefined, name: tpl.name + " (Copy)" });
      setSelectedStep(0);
      setView("edit");
    } catch (e) {
      // Fallback: use list data if direct load fails
      const tpl = templates.find(t => t.id === id);
      if (tpl) {
        setCurrent({ name: tpl.name + " (Copy)", description: tpl.description || "", steps: [], browser: { headless: false } });
        setSelectedStep(0);
        setView("edit");
      } else {
        addToast("Failed to load template", "error");
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

  async function deleteTemplateItem(id, e) {
    e.stopPropagation();
    if (!confirm("Delete this template?")) return;
    try {
      await api.deleteTemplate(id);
      addToast("Template deleted", "success");
      loadList();
    } catch (e) {
      addToast("Failed to delete template", "error");
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
      await api.startElementPicker(null, pickerAutoLogin);
      setPickerActive(true);
      setPickerEvents([]);
      pickerPollRef.current = setInterval(async () => {
        try {
          const res = await api.getPickerEvents();
          if (res.events && res.events.length > 0) {
            setPickerEvents(prev => [...prev, ...res.events]);
            // Auto-apply the last picked selector to the current step
            const lastEvent = res.events[res.events.length - 1];
            if (lastEvent && lastEvent.selector && usePickedSelectorRef.current) {
              usePickedSelectorRef.current(lastEvent.selector);
            }
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
  usePickedSelectorRef.current = usePickedSelector;

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
  // Shared prop bag for the three guard views; each destructures what it needs.
  const viewProps = {
    view, setView, loadList,
    workflows, templates, current, setCurrent, selectedStep, setSelectedStep,
    runStatus, pickerActive, pickerEvents, pickerAutoLogin, setPickerAutoLogin,
    newWorkflow, loadWorkflow, loadTemplate, saveWorkflow, deleteWorkflow,
    deleteTemplateItem, startRun, stopRun, startPicker, stopPicker,
    usePickedSelector, addStep, removeStep, moveStep, updateStep,
  };

  return (
    <>
      <AutomationListView {...viewProps} />
      <AutomationRunView {...viewProps} />
      <AutomationEditView {...viewProps} />
    </>
  );
}
