// Step-type metadata + per-type param field definitions for the automation
// builder. Moved verbatim from module scope of AutomationBuilder.jsx (CQ
// wave-6 split); consumed by the AutomationBuilder shell (addStep) and
// AutomationEditView (step list icons + type-specific param fields).

export const STEP_TYPES = [
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

export const PARAM_FIELDS = {
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
