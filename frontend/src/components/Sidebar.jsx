import React from "react";
import Icon from "./Icon";

export default function Sidebar({ activeTab, TABS, handleLogout, isAdmin, setActiveTab, setSidebarCollapsed, sidebarCollapsed, theme }) {
  return (
        <div
          data-testid="sidebar"
          style={{
            width: sidebarCollapsed ? "70px" : "260px",
            background:
              theme === "dark"
                ? "#000000"
                : "linear-gradient(180deg, #ffffff 0%, #f8fafc 50%, #f1f5f9 100%)",
            borderRight: `1px solid ${theme === "dark" ? "rgba(255,255,255,0.1)" : "rgba(0,0,0,0.08)"}`,
            padding: "0",
            display: "flex",
            flexDirection: "column",
            position: "fixed",
            top: 0,
            left: 0,
            bottom: 0,
            zIndex: 100,
            transition: "width 0.3s ease",
          }}
        >
          {/* Collapse Toggle - Right Edge */}
          <button
            data-testid="sidebar-collapse-toggle"
            aria-label={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
            onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
            style={{
              position: "absolute",
              right: "-12px",
              top: "50%",
              transform: "translateY(-50%)",
              width: "24px",
              height: "24px",
              borderRadius: "50%",
              border: `1px solid ${theme === "dark" ? "rgba(255,255,255,0.15)" : "rgba(0,0,0,0.1)"}`,
              background: theme === "dark" ? "#1f1f2a" : "#ffffff",
              color: "var(--text-secondary)",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              transition: "all 0.2s",
              zIndex: 101,
              boxShadow: "0 2px 8px rgba(0,0,0,0.15)",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = "var(--accent-primary)";
              e.currentTarget.style.color = "#fff";
              e.currentTarget.style.borderColor = "var(--accent-primary)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background =
                theme === "dark" ? "#1f1f2a" : "#ffffff";
              e.currentTarget.style.color = "var(--text-secondary)";
              e.currentTarget.style.borderColor =
                theme === "dark" ? "rgba(255,255,255,0.15)" : "rgba(0,0,0,0.1)";
            }}
          >
            <Icon
              name={sidebarCollapsed ? "ChevronRight" : "ChevronLeft"}
              size={14}
            />
          </button>

          {/* Logo - expanded */}
          {!sidebarCollapsed && (
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                padding: "20px 16px 0",
                overflow: "hidden",
              }}
            >
              <img
                src={theme === "light" ? "/graider-brain-light.png" : "/graider-brain-dark.png"}
                alt="Graider brain"
                style={{ width: 80, height: 80, marginTop: 25, marginBottom: -70 }}
              />
              <img
                src={theme === "light" ? "/graider-wordmark-light.png" : "/graider-wordmark-dark.png"}
                alt="Graider"
                style={{ width: "85%", marginTop: 20, marginBottom: -35 }}
              />
            </div>
          )}

          {/* Logo - collapsed */}
          {sidebarCollapsed && (
            <div
              style={{
                padding: "20px 0",
                display: "flex",
                justifyContent: "center",
              }}
            >
              <img
                src={theme === "light" ? "/graider-brain-light.png" : "/graider-brain-dark.png"}
                alt="Graider"
                style={{ width: 40, height: 40 }}
              />
            </div>
          )}

          {/* Navigation */}
          <nav
            data-tutorial="sidebar-nav"
            style={{
              flex: 1,
              padding: sidebarCollapsed ? "10px 8px 0 8px" : "0 10px",
              marginTop: sidebarCollapsed ? "0" : "0",
            }}
          >
            {TABS.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                title={sidebarCollapsed ? tab.label : ""}
                style={{
                  width: "100%",
                  padding: sidebarCollapsed ? "14px 0" : "14px 16px",
                  marginBottom: "6px",
                  borderRadius: "10px",
                  border: "none",
                  background:
                    activeTab === tab.id
                      ? "linear-gradient(135deg, var(--accent-primary), var(--accent-secondary))"
                      : "transparent",
                  color:
                    activeTab === tab.id ? "#fff" : "var(--text-secondary)",
                  fontSize: "0.95rem",
                  fontWeight: 600,
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: sidebarCollapsed ? "center" : "flex-start",
                  gap: "12px",
                  transition: "all 0.2s",
                  textAlign: "left",
                }}
                onMouseEnter={(e) => {
                  if (activeTab !== tab.id)
                    e.target.style.background = "var(--glass-hover)";
                }}
                onMouseLeave={(e) => {
                  if (activeTab !== tab.id)
                    e.target.style.background = "transparent";
                }}
              >
                <Icon name={tab.icon} size={20} />
                {!sidebarCollapsed && tab.label}
              </button>
            ))}
            {isAdmin && (
              <button
                key="admin"
                onClick={() => setActiveTab("admin")}
                title={sidebarCollapsed ? "Admin" : ""}
                style={{
                  width: "100%",
                  padding: sidebarCollapsed ? "14px 0" : "14px 16px",
                  marginBottom: "6px",
                  borderRadius: "10px",
                  border: "none",
                  background:
                    activeTab === "admin"
                      ? "linear-gradient(135deg, var(--accent-primary), var(--accent-secondary))"
                      : "transparent",
                  color:
                    activeTab === "admin" ? "#fff" : "var(--text-secondary)",
                  fontSize: "0.95rem",
                  fontWeight: 600,
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: sidebarCollapsed ? "center" : "flex-start",
                  gap: "12px",
                  transition: "all 0.2s",
                  textAlign: "left",
                }}
                onMouseEnter={(e) => {
                  if (activeTab !== "admin")
                    e.target.style.background = "var(--glass-hover)";
                }}
                onMouseLeave={(e) => {
                  if (activeTab !== "admin")
                    e.target.style.background = "transparent";
                }}
              >
                <Icon name="Shield" size={20} />
                {!sidebarCollapsed && "Admin"}
              </button>
            )}
          </nav>

          {/* Footer */}
          {!sidebarCollapsed && (
            <div
              style={{
                padding: "15px 20px",
                borderTop: `1px solid ${theme === "dark" ? "rgba(255,255,255,0.08)" : "rgba(0,0,0,0.08)"}`,
              }}
            >
              <button
                onClick={handleLogout}
                title="Sign Out"
                style={{
                  width: "100%",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: "8px",
                  padding: "10px",
                  marginBottom: "12px",
                  borderRadius: "12px",
                  border: "1px solid var(--glass-border)",
                  background: "var(--glass-bg)",
                  color: "var(--text-secondary)",
                  cursor: "pointer",
                  fontSize: "0.85rem",
                  transition: "all 0.3s ease",
                }}
              >
                <Icon name="LogOut" size={16} />
                Sign Out
              </button>
              <div
                style={{
                  fontSize: "0.75rem",
                  color: "var(--text-muted)",
                  textAlign: "center",
                  lineHeight: "1.4",
                }}
              >
                AI-Powered Teacher's Assistant
                <br />
                Made for Educators by Educators with ❤️
              </div>
            </div>
          )}
        </div>
  );
}
