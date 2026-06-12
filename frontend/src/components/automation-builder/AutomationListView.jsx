import React from "react";
import Icon from "../Icon";

// Workflow/template list view. Originally the `if (view === "list")` branch of
// AutomationBuilder — markup relocated verbatim (CQ wave-6 split); the
// conditional render became the early-return guard below. All state and
// handlers stay in the AutomationBuilder shell and arrive via props.
// `cardStyle` moved here with the markup — it is only used by this view.
export default function AutomationListView(props) {
  const {
    view, workflows, templates,
    newWorkflow, loadWorkflow, loadTemplate, startRun,
    deleteWorkflow, deleteTemplateItem,
  } = props;
  if (view !== "list") return null;

  const cardStyle = {
    background: "var(--card-bg)", borderRadius: 12, padding: 20,
    border: "1px solid var(--glass-border)", cursor: "pointer",
    transition: "box-shadow 0.15s", display: "flex", flexDirection: "column", gap: 8,
    color: "var(--text-primary)",
  };

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
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                    <span style={{ fontWeight: 600, fontSize: "1rem" }}>{tpl.name}</span>
                    <button onClick={(e) => deleteTemplateItem(tpl.id, e)}
                      style={{ background: "transparent", color: "var(--text-secondary)", border: "none", cursor: "pointer", padding: 4 }}>
                      <Icon name="Trash2" size={14} />
                    </button>
                  </div>
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
